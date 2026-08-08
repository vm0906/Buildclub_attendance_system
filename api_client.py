"""
api.py

API client responsible for POSTing attendance EXIT events to the backend.

Design goals:
    - NEVER block the video feed. All HTTP calls run on a background
      ThreadPoolExecutor, not the main/UI thread.
    - Resilient to a offline/unreachable backend: retries with backoff,
      then falls back to a local JSON backup file so no data is lost.
    - Simple synchronous-looking call site (`send_attendance_event(...)`)
      that internally fires-and-forgets onto the executor.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

import requests

from config import Config
from utils import append_json_record, now_str, setup_logger

logger = setup_logger(__name__)


class AttendanceAPIClient:
    """
    Thread-pool-backed HTTP client for posting attendance events to the
    backend, with automatic local fallback on failure.
    """

    def __init__(
        self,
        base_url: str = Config.API_BASE_URL,
        endpoint: str = Config.ATTENDANCE_ENDPOINT,
        max_workers: int = 4,
    ) -> None:
        """
        Args:
            base_url: Backend base URL (e.g. "http://localhost:5000").
            endpoint: API path for attendance events (e.g. "/api/attendance").
            max_workers: Size of the background thread pool for POST calls.
        """
        self.url = f"{base_url.rstrip('/')}{endpoint}"
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="api-poster"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_attendance_event(
        self,
        name: str,
        entry_time_str: str,
        exit_time_str: str,
        duration_minutes: int,
    ) -> None:
        """
        Fire-and-forget a POST of an attendance EXIT event. Returns
        immediately; the actual HTTP call (with retries) happens on a
        background thread so the caller (video loop) never blocks.

        Args:
            name: Member's name.
            entry_time_str: "YYYY-MM-DD HH:MM:SS" formatted entry time.
            exit_time_str: "YYYY-MM-DD HH:MM:SS" formatted exit time.
            duration_minutes: Total minutes spent in the space.
        """
        payload: Dict[str, Any] = {
            "name": name,
            "entry_time": entry_time_str,
            "exit_time": exit_time_str,
            "duration_minutes": duration_minutes,
        }
        # Submit to the thread pool - does not block the caller.
        self._executor.submit(self._post_with_retries, payload)

    def shutdown(self, wait: bool = True) -> None:
        """Gracefully shut down the background thread pool."""
        self._executor.shutdown(wait=wait)
        logger.info("AttendanceAPIClient thread pool shut down.")

    # ------------------------------------------------------------------
    # Internal: blocking POST logic (runs on a worker thread)
    # ------------------------------------------------------------------

    def _post_with_retries(self, payload: Dict[str, Any]) -> None:
        """
        Attempt to POST `payload` to the backend, retrying with backoff
        per Config.API_MAX_RETRIES. On total failure, save the payload to
        the local failed-posts backup so no attendance data is lost.

        Runs entirely on a background thread - safe to block here.
        """
        attempts = Config.API_MAX_RETRIES + 1

        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(
                    self.url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=Config.API_TIMEOUT_SECONDS,
                )
                if 200 <= response.status_code < 300:
                    logger.info(
                        "Posted attendance event for '%s' successfully (status %d).",
                        payload["name"],
                        response.status_code,
                    )
                    return

                logger.warning(
                    "Backend responded with status %d for '%s' (attempt %d/%d).",
                    response.status_code,
                    payload["name"],
                    attempt,
                    attempts,
                )

            except requests.exceptions.RequestException as exc:
                logger.warning(
                    "POST failed for '%s' (attempt %d/%d): %s",
                    payload["name"],
                    attempt,
                    attempts,
                    exc,
                )

            if attempt < attempts:
                time.sleep(Config.API_RETRY_BACKOFF_SECONDS * attempt)

        # All retries exhausted - back up locally so the event isn't lost.
        self._save_failed_post(payload)

    def _save_failed_post(self, payload: Dict[str, Any]) -> None:
        """Persist a payload that couldn't be delivered to the backend."""
        backup_record = {**payload, "failed_at": now_str()}
        success = append_json_record(Config.FAILED_POST_BACKUP_FILE, backup_record)
        if success:
            logger.error(
                "Backend unreachable - saved event for '%s' to %s for later retry.",
                payload["name"],
                Config.FAILED_POST_BACKUP_FILE,
            )
        else:
            logger.critical(
                "Backend unreachable AND local backup failed for '%s'. "
                "Attendance data for this session may be lost: %s",
                payload["name"],
                payload,
            )