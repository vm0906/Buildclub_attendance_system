"""
tracker.py

Phase 3: Presence & Session Tracking Module.

Responsibilities:
    - Detect when a member ENTERS the space (first detection -> new session).
    - Continuously update a "last_seen" timestamp while they remain visible.
    - Detect EXIT: a member missing continuously for more than
      Config.EXIT_GRACE_PERIOD_SECONDS triggers session close.
    - Compute total duration (minutes) spent in the space.
    - Guarantee at most one active session per member at a time (no dupes),
      and reset the absence buffer instantly on re-detection.

This module is detection-agnostic: it only deals with names and timestamps.
`attendance.py` is responsible for calling `mark_present()` every time the
recognizer identifies a known member in a frame.
"""

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

from config import Config
from utils import duration_minutes, format_datetime, now_str, setup_logger

logger = setup_logger(__name__)

# Callback signature: (name, entry_time, exit_time, duration_minutes) -> None
ExitCallback = Callable[[str, datetime, datetime, int], None]


@dataclass
class ActiveSession:
    """Represents a member currently present in the makerspace."""

    name: str
    entry_time: datetime
    last_seen: datetime


class PresenceTracker:
    """
    Tracks per-member presence sessions and fires EXIT events after a
    configurable continuous-absence grace period.

    Thread-safety: a background sweep thread periodically scans for stale
    sessions, while the main video-processing thread calls `mark_present()`
    on every frame. Both paths are guarded by a single lock.
    """

    def __init__(
        self,
        on_exit: Optional[ExitCallback] = None,
        exit_grace_period_seconds: float = Config.EXIT_GRACE_PERIOD_SECONDS,
        sweep_interval_seconds: float = Config.TRACKER_SWEEP_INTERVAL_SECONDS,
    ) -> None:
        """
        Args:
            on_exit: Callback invoked when a session closes:
                on_exit(name, entry_time, exit_time, duration_minutes).
                Typically wired to API posting + local logging in attendance.py.
            exit_grace_period_seconds: How long a member must be continuously
                absent before an EXIT is fired.
            sweep_interval_seconds: How often the background thread checks
                for stale sessions.
        """
        self._active_sessions: Dict[str, ActiveSession] = {}
        self._lock = threading.Lock()
        self._on_exit = on_exit
        self._exit_grace_period = exit_grace_period_seconds
        self._sweep_interval = sweep_interval_seconds

        self._running = False
        self._sweep_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> "PresenceTracker":
        """Start the background sweep thread that watches for EXIT timeouts."""
        self._running = True
        self._sweep_thread = threading.Thread(target=self._sweep_loop, daemon=True)
        self._sweep_thread.start()
        logger.info(
            "PresenceTracker started (exit grace period = %.1fs).",
            self._exit_grace_period,
        )
        return self

    def stop(self) -> None:
        """Stop the sweep thread. Does NOT force-close active sessions."""
        self._running = False
        if self._sweep_thread is not None:
            self._sweep_thread.join(timeout=2.0)
        logger.info("PresenceTracker stopped.")

    # ------------------------------------------------------------------
    # Presence updates (called from the frame-processing loop)
    # ------------------------------------------------------------------

    def mark_present(self, name: str) -> None:
        """
        Register that `name` was detected in the current frame.

        - If no active session exists for this member, this starts a new
          ENTRY session (recorded at the current timestamp).
        - If a session already exists, this simply refreshes `last_seen`,
          resetting the absence buffer (so brief occlusions/false-negatives
          don't trigger a premature EXIT).

        Args:
            name: Recognized member name (never UNKNOWN - filter that out
                before calling this).
        """
        if name == Config.UNKNOWN_LABEL:
            return  # Never track sessions for unknown faces.

        with self._lock:
            now = datetime.now()
            session = self._active_sessions.get(name)

            if session is None:
                # New ENTRY event.
                self._active_sessions[name] = ActiveSession(
                    name=name, entry_time=now, last_seen=now
                )
                logger.info("ENTRY detected for '%s' at %s", name, format_datetime(now))
            else:
                # Already active - just refresh last_seen (resets absence buffer).
                session.last_seen = now

    def is_active(self, name: str) -> bool:
        """Return True if `name` currently has an open (active) session."""
        with self._lock:
            return name in self._active_sessions

    def get_active_members(self) -> List[str]:
        """Return a snapshot list of member names currently marked present."""
        with self._lock:
            return list(self._active_sessions.keys())

    # ------------------------------------------------------------------
    # EXIT detection (background sweep)
    # ------------------------------------------------------------------

    def _sweep_loop(self) -> None:
        """Background loop: periodically checks for members who exceeded
        the absence grace period and closes their sessions."""
        while self._running:
            self._check_for_exits()
            time.sleep(self._sweep_interval)

    def _check_for_exits(self) -> None:
        """Scan active sessions and fire EXIT for anyone stale beyond the
        configured grace period."""
        now = datetime.now()
        expired_names: List[str] = []

        with self._lock:
            for name, session in self._active_sessions.items():
                absent_seconds = (now - session.last_seen).total_seconds()
                if absent_seconds > self._exit_grace_period:
                    expired_names.append(name)

            # Pop expired sessions while still holding the lock to prevent
            # a race where mark_present() re-adds the member mid-pop.
            closed_sessions: List[ActiveSession] = []
            for name in expired_names:
                closed_sessions.append(self._active_sessions.pop(name))

        # Fire callbacks outside the lock so a slow/blocking callback
        # (e.g. a network call) never stalls presence tracking.
        for session in closed_sessions:
            exit_time = session.last_seen  # last confirmed sighting, not "now"
            minutes = duration_minutes(session.entry_time, exit_time)
            logger.info(
                "EXIT detected for '%s' | entry=%s exit=%s duration=%dmin",
                session.name,
                format_datetime(session.entry_time),
                format_datetime(exit_time),
                minutes,
            )
            if self._on_exit is not None:
                try:
                    self._on_exit(session.name, session.entry_time, exit_time, minutes)
                except Exception as exc:  # noqa: BLE001 - never let a bad callback kill the sweep thread
                    logger.error("on_exit callback failed for '%s': %s", session.name, exc)

    def force_close_all(self) -> None:
        """
        Force-close every active session immediately (e.g. on app shutdown)
        so no attendance data is silently lost.
        """
        now = datetime.now()
        with self._lock:
            sessions = list(self._active_sessions.values())
            self._active_sessions.clear()

        for session in sessions:
            minutes = duration_minutes(session.entry_time, now)
            logger.info("Force-closing session for '%s' on shutdown.", session.name)
            if self._on_exit is not None:
                try:
                    self._on_exit(session.name, session.entry_time, now, minutes)
                except Exception as exc:  # noqa: BLE001
                    logger.error("on_exit callback failed during shutdown for '%s': %s", session.name, exc)