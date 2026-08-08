"""
config.py

Central configuration for the Face Recognition Attendance System.
All tunable thresholds, paths, and endpoints live here so the rest of the
codebase never hardcodes a magic number or path.
"""

import os


class Config:
    """Static configuration container for the entire attendance module."""

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))

    # Root folder containing one subfolder per member: dataset/<MemberName>/*.jpg
    DATASET_DIR: str = os.path.join(BASE_DIR, "dataset")

    # Where computed face encodings are cached (avoids recomputation each run)
    ENCODINGS_DIR: str = os.path.join(BASE_DIR, "encodings")
    ENCODINGS_FILE: str = os.path.join(ENCODINGS_DIR, "encodings.pkl")

    # Local logs directory (attendance history + fallback backup)
    LOGS_DIR: str = os.path.join(BASE_DIR, "logs")
    ATTENDANCE_LOG_FILE: str = os.path.join(LOGS_DIR, "attendance.json")
    FAILED_POST_BACKUP_FILE: str = os.path.join(LOGS_DIR, "failed_posts.json")
    APP_LOG_FILE: str = os.path.join(LOGS_DIR, "app.log")

    # ------------------------------------------------------------------
    # Face Recognition / Matching
    # ------------------------------------------------------------------
    # Euclidean distance threshold below which a face is considered a match.
    # Lower = stricter matching. Typical range: 0.4 (strict) - 0.6 (lenient).
    FACE_MATCH_THRESHOLD: float = 0.5

    # Which face_recognition model to use for encoding: "hog" (fast, CPU)
    # or "cnn" (accurate, needs GPU for real-time speed).
    FACE_DETECTION_MODEL: str = "hog"

    # Number of times to re-sample when computing face encodings (higher = more
    # accurate but slower). 1 is the standard default.
    NUM_JITTERS: int = 1

    # Label shown for a detected face that doesn't match anyone in the dataset
    UNKNOWN_LABEL: str = "UNKNOWN"

    # ------------------------------------------------------------------
    # Camera / Real-time Performance
    # ------------------------------------------------------------------
    CAMERA_INDEX: int = 0
    FRAME_WIDTH: int = 640
    FRAME_HEIGHT: int = 480

    # Resize factor applied to frames before detection to boost FPS
    # (0.25 = process at 1/4 resolution, then scale coordinates back up).
    FRAME_RESIZE_SCALE: float = 0.25

    # Run full face detection/encoding every N frames; reuse last-known
    # boxes on the skipped frames to keep the display smooth and fast.
    PROCESS_EVERY_N_FRAMES: int = 3

    # Display window name
    WINDOW_NAME: str = "Attendance AI - Live Feed"

    # ------------------------------------------------------------------
    # Session / Presence Tracking
    # ------------------------------------------------------------------
    # A member is marked EXITED if they are missing continuously for
    # more than this many seconds.
    EXIT_GRACE_PERIOD_SECONDS: float = 20.0

    # How often (seconds) the tracker's background sweep checks for
    # stale (timed-out) sessions.
    TRACKER_SWEEP_INTERVAL_SECONDS: float = 1.0

    # ------------------------------------------------------------------
    # Backend API
    # ------------------------------------------------------------------
    # Fully configurable backend base URL. Point this at the teammate's
    # real backend, or at mock_server.py for standalone testing.
    API_BASE_URL: str = os.environ.get("ATTENDANCE_API_BASE_URL", "http://localhost:5000")
    ATTENDANCE_ENDPOINT: str = "/api/attendance"

    API_TIMEOUT_SECONDS: float = 5.0
    API_MAX_RETRIES: int = 2
    API_RETRY_BACKOFF_SECONDS: float = 1.5

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    @classmethod
    def ensure_directories(cls) -> None:
        """Create all required directories if they don't already exist."""
        for directory in (cls.ENCODINGS_DIR, cls.LOGS_DIR, cls.DATASET_DIR):
            os.makedirs(directory, exist_ok=True)