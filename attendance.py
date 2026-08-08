"""
attendance.py

Main pipeline orchestrator that binds together:
    - recognizer.py  (who is this face?)
    - tracker.py     (ENTRY/EXIT session state)
    - api.py         (deliver EXIT events to the backend)

`main.py` should only need to instantiate `AttendanceManager` and call
`process_frame()` per webcam frame + `shutdown()` on exit - all detection,
matching, session tracking, and API/logging wiring happens here.
"""

from dataclasses import dataclass
from datetime import datetime
import os
from typing import List, Tuple

import cv2
import face_recognition
import numpy as np
import pandas as pd

from api_client import AttendanceAPIClient
from config import Config
from recognizer import FaceRecognizer
from tracker import PresenceTracker
from utils import append_json_record, format_datetime, setup_logger

logger = setup_logger(__name__)

# BGR colors for OpenCV drawing
COLOR_KNOWN = (0, 200, 0)      # green
COLOR_UNKNOWN = (0, 0, 255)    # red
COLOR_TEXT_BG = (0, 0, 0)      # black label background

CSV_FILE = "attendance_records.csv"


@dataclass
class DetectedFace:
    """A single face detected+matched in a frame, in ORIGINAL frame coordinates."""

    name: str
    distance: float
    confidence_pct: float
    top: int
    right: int
    bottom: int
    left: int


def _distance_to_confidence(distance: float) -> float:
    """
    Convert a face_recognition Euclidean distance into an approximate,
    human-friendly confidence percentage for on-screen display only.

    This is NOT used for matching decisions (recognizer.py's threshold
    comparison already decided known-vs-unknown) - it's purely a UX
    convenience so the video overlay can show e.g. "Priya (87%)".

    Args:
        distance: Euclidean distance between the live encoding and the
            best-matching known encoding (0.0 = identical, higher = less similar).

    Returns:
        A confidence percentage clamped to [0, 100].
    """
    confidence = (1.0 - distance) * 100.0
    return max(0.0, min(100.0, confidence))


class AttendanceManager:
    """
    Orchestrates the full real-time attendance pipeline for one video frame
    at a time: detect faces -> match identities -> update presence sessions
    -> hand off EXIT events to logging + the backend API.
    """

    def __init__(self) -> None:
        Config.ensure_directories()

        self.recognizer = FaceRecognizer()
        self.recognizer.load_or_build_encodings()

        self.api_client = AttendanceAPIClient()
        self.tracker = PresenceTracker(on_exit=self._handle_exit_event).start()

        # Track daily marked attendance to prevent duplicate entries on the same day
        self._marked_today = set()

        # Frame-skipping state: reuse last detections on skipped frames to
        # keep the on-screen boxes stable while boosting FPS.
        self._frame_counter = 0
        self._last_detections: List[DetectedFace] = []

        logger.info(
            "AttendanceManager ready | %d known member(s) loaded.",
            self.recognizer.known_member_count,
        )

    def mark_attendance_immediate(self, name: str) -> None:
        """
        Immediately record attendance for a recognized person if not already marked today.
        Updates attendance_records.csv formatted for the Streamlit dashboard schema,
        while maintaining standard JSON logs.
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        record_key = (name, today_str)

        if record_key in self._marked_today:
            return

        now = datetime.now()
        entry_str = format_datetime(now)

        # 1. Save to local JSON log
        record_json = {
            "name": name,
            "entry_time": entry_str,
            "status": "Present",
        }
        json_saved = append_json_record(Config.ATTENDANCE_LOG_FILE, record_json)

        # 2. Update CSV for Streamlit dashboard
        csv_saved = False
        try:
            columns = [
                "Member Name",
                "Sessions Attended",
                "Total Sessions",
                "Attendance %",
                "Last Active",
            ]

            if os.path.exists(CSV_FILE):
                df = pd.read_csv(CSV_FILE)
            else:
                df = pd.DataFrame(columns=columns)

            if name in df["Member Name"].values:
                # Member exists: check if they were already active today in the CSV
                member_mask = df["Member Name"] == name
                last_active = str(df.loc[member_mask, "Last Active"].iloc[0]).strip()

                if last_active != today_str:
                    # Increment sessions attended and total sessions
                    attended = df.loc[member_mask, "Sessions Attended"].iloc[0] + 1
                    total = df.loc[member_mask, "Total Sessions"].iloc[0] + 1
                    att_pct = f"{(attended / total) * 100:.1f}%"

                    df.loc[member_mask, "Sessions Attended"] = attended
                    df.loc[member_mask, "Total Sessions"] = total
                    df.loc[member_mask, "Attendance %"] = att_pct
                    df.loc[member_mask, "Last Active"] = today_str
            else:
                # Member does not exist: add a new row
                new_row = pd.DataFrame(
                    [
                        {
                            "Member Name": name,
                            "Sessions Attended": 1,
                            "Total Sessions": 1,
                            "Attendance %": "100.0%",
                            "Last Active": today_str,
                        }
                    ]
                )
                df = pd.concat([df, new_row], ignore_index=True)

            df.to_csv(CSV_FILE, index=False)
            csv_saved = True
        except Exception as e:
            logger.error("Failed to update CSV '%s': %s", CSV_FILE, str(e))

        if json_saved or csv_saved:
            self._marked_today.add(record_key)
            logger.info("Immediate attendance saved to JSON/CSV for '%s' at %s", name, entry_str)
        else:
            logger.error("Failed to save immediate attendance record for '%s'.", name)

    # ------------------------------------------------------------------
    # EXIT event handling (called from PresenceTracker's sweep thread)
    # ------------------------------------------------------------------

    def _handle_exit_event(self, name: str, entry_time, exit_time, minutes: int) -> None:
        """
        Wired as PresenceTracker's on_exit callback. Responsible for:
            1. Saving the session locally to logs/attendance.json.
            2. Posting the event to the backend (non-blocking).

        This runs on the tracker's background sweep thread, so it must
        never touch the video frame/UI directly.
        """
        entry_str = format_datetime(entry_time)
        exit_str = format_datetime(exit_time)

        record = {
            "name": name,
            "entry_time": entry_str,
            "exit_time": exit_str,
            "duration_minutes": minutes,
        }

        # 1. Local durable log - always happens regardless of backend status.
        if not append_json_record(Config.ATTENDANCE_LOG_FILE, record):
            logger.error("Failed to write local attendance log for '%s'.", name)

        # 2. Non-blocking POST to backend (handles retries + its own fallback).
        self.api_client.send_attendance_event(name, entry_str, exit_str, minutes)

    # ------------------------------------------------------------------
    # Frame processing (called from main.py's video loop)
    # ------------------------------------------------------------------

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Run detection/matching (on a schedule) and draw annotated boxes
        onto a copy of the frame.

        Args:
            frame: BGR frame from the camera (as returned by OpenCV).

        Returns:
            A new BGR frame with bounding boxes + name labels drawn.
        """
        self._frame_counter += 1
        run_full_detection = (
            self._frame_counter % Config.PROCESS_EVERY_N_FRAMES == 0
            or not self._last_detections
        )

        if run_full_detection:
            self._last_detections = self._detect_and_match(frame)

            # Update presence sessions for every recognized (non-UNKNOWN) face.
            for detection in self._last_detections:
                if detection.name != Config.UNKNOWN_LABEL:
                    self.tracker.mark_present(detection.name)
                    self.mark_attendance_immediate(detection.name)
                    logger.info("Attendance marked present for '%s'", detection.name)

        return self._draw_annotations(frame, self._last_detections)

    def _detect_and_match(self, frame: np.ndarray) -> List[DetectedFace]:
        """
        Downscale the frame for speed, detect faces, compute encodings,
        match against known members, then scale coordinates back up to
        the original frame size.
        """
        scale = Config.FRAME_RESIZE_SCALE
        small_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)

        # face_recognition expects RGB; OpenCV frames are BGR.
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(
            rgb_small_frame, model=Config.FACE_DETECTION_MODEL
        )
        face_encodings = face_recognition.face_encodings(
            rgb_small_frame, known_face_locations=face_locations
        )

        matches: List[Tuple[str, float]] = self.recognizer.match_faces_batch(face_encodings)

        detections: List[DetectedFace] = []
        for (top, right, bottom, left), (name, distance) in zip(face_locations, matches):
            # Scale bounding box coordinates back up to the original frame size.
            inv_scale = 1.0 / scale
            detections.append(
                DetectedFace(
                    name=name,
                    distance=distance,
                    confidence_pct=_distance_to_confidence(distance),
                    top=int(top * inv_scale),
                    right=int(right * inv_scale),
                    bottom=int(bottom * inv_scale),
                    left=int(left * inv_scale),
                )
            )
        return detections

    @staticmethod
    def _draw_annotations(frame: np.ndarray, detections: List[DetectedFace]) -> np.ndarray:
        """Draw bounding boxes + name labels for every detected face."""
        annotated = frame.copy()

        for det in detections:
            is_known = det.name != Config.UNKNOWN_LABEL
            color = COLOR_KNOWN if is_known else COLOR_UNKNOWN
            label = (
                f"{det.name} ({det.confidence_pct:.0f}%)"
                if is_known
                else Config.UNKNOWN_LABEL
            )

            cv2.rectangle(annotated, (det.left, det.top), (det.right, det.bottom), color, 2)

            # Label background + text, anchored below the box.
            label_bg_top = det.bottom
            label_bg_bottom = det.bottom + 28
            cv2.rectangle(
                annotated, (det.left, label_bg_top), (det.right, label_bg_bottom), color, cv2.FILLED
            )
            cv2.putText(
                annotated,
                label,
                (det.left + 6, label_bg_bottom - 8),
                cv2.FONT_HERSHEY_DUPLEX,
                0.6,
                (255, 255, 255),
                1,
            )

        return annotated

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """
        Gracefully shut down the pipeline: force-close any still-active
        sessions (so nobody's attendance is silently dropped) and stop
        background threads.
        """
        logger.info("Shutting down AttendanceManager - closing active sessions...")
        self.tracker.force_close_all()
        self.tracker.stop()
        self.api_client.shutdown(wait=True)
        logger.info("AttendanceManager shutdown complete.")