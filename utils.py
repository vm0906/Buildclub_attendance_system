"""
utils.py

Shared helper utilities used across the attendance system:
    - Centralized logging setup
    - Datetime formatting/parsing helpers
    - Thread-safe local JSON read/write/append helpers

Keeping these in one place avoids duplicated boilerplate in
recognizer.py, tracker.py, attendance.py, and api.py.
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List

from config import Config

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------

# One process-wide lock to make JSON read-modify-write safe across threads
# (the tracker's sweep thread and the main thread both touch attendance.json).
_json_lock = threading.Lock()


def setup_logger(name: str = "attendance_ai") -> logging.Logger:
    """
    Configure and return a shared logger that writes to both console and
    a rotating-free file (kept simple for a hackathon timeline).

    Safe to call multiple times (e.g. once per module) - handlers are only
    attached once thanks to the `logger.handlers` check.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A configured logging.Logger instance.
    """
    Config.ensure_directories()
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured (e.g. called again from another module) - skip.
        return logger

    logger.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
    formatter = logging.Formatter(Config.LOG_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(Config.APP_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


# ----------------------------------------------------------------------
# Datetime helpers
# ----------------------------------------------------------------------

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_str() -> str:
    """Return the current local timestamp formatted per the API contract."""
    return datetime.now().strftime(DATETIME_FORMAT)


def format_datetime(dt: datetime) -> str:
    """Format a datetime object to the standard 'YYYY-MM-DD HH:MM:SS' string."""
    return dt.strftime(DATETIME_FORMAT)


def parse_datetime(dt_str: str) -> datetime:
    """Parse a 'YYYY-MM-DD HH:MM:SS' string back into a datetime object."""
    return datetime.strptime(dt_str, DATETIME_FORMAT)


def duration_minutes(entry_time: datetime, exit_time: datetime) -> int:
    """
    Calculate whole minutes spent between entry and exit.

    Args:
        entry_time: When the member entered.
        exit_time: When the member exited.

    Returns:
        Duration in minutes, rounded down to nearest whole minute (min 0).
    """
    delta_seconds = (exit_time - entry_time).total_seconds()
    return max(0, int(delta_seconds // 60))


# ----------------------------------------------------------------------
# JSON persistence helpers (thread-safe)
# ----------------------------------------------------------------------

def load_json(filepath: str, default: Any = None) -> Any:
    """
    Load JSON content from a file, returning `default` if the file
    doesn't exist or is empty/corrupted.

    Args:
        filepath: Path to the JSON file.
        default: Value to return if the file is missing or unreadable.

    Returns:
        Parsed JSON content, or `default`.
    """
    if default is None:
        default = []

    with _json_lock:
        if not os.path.exists(filepath):
            return default
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return default
                return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return default


def save_json(filepath: str, data: Any) -> bool:
    """
    Overwrite a JSON file with the given data.

    Args:
        filepath: Path to the JSON file.
        data: JSON-serializable data to write.

    Returns:
        True on success, False on failure (e.g. disk/permission error).
    """
    with _json_lock:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except OSError:
            return False


def append_json_record(filepath: str, record: Dict[str, Any]) -> bool:
    """
    Append a single record to a JSON file that stores a list of records.
    Reads the existing list, appends, and rewrites (fine for hackathon-scale
    attendance logs; swap for a real DB/backend at scale).

    Args:
        filepath: Path to the JSON file (expects a top-level list).
        record: Dictionary record to append.

    Returns:
        True on success, False on failure.
    """
    records: List[Dict[str, Any]] = load_json(filepath, default=[])
    records.append(record)
    return save_json(filepath, records)