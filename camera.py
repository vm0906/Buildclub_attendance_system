"""
camera.py

Threaded webcam capture handler.

Reading frames from cv2.VideoCapture().read() is blocking I/O. If done on
the main thread, the main loop's FPS gets capped by camera I/O latency
instead of by processing speed. This module runs capture on a dedicated
background thread and always exposes the *latest* frame, so the main loop
(and face detection) never waits on the camera.
"""

import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from config import Config
from utils import setup_logger

logger = setup_logger(__name__)


class CameraStream:
    """
    Threaded video capture wrapper around cv2.VideoCapture.

    Usage:
        with CameraStream() as cam:
            while True:
                ok, frame = cam.read()
                if not ok:
                    break
                ...
    """

    def __init__(
        self,
        camera_index: int = Config.CAMERA_INDEX,
        frame_width: int = Config.FRAME_WIDTH,
        frame_height: int = Config.FRAME_HEIGHT,
    ) -> None:
        """
        Initialize (but do not yet start) the camera stream.

        Args:
            camera_index: OS camera device index (0 = default webcam).
            frame_width: Desired capture width in pixels.
            frame_height: Desired capture height in pixels.
        """
        self.camera_index = camera_index
        self.frame_width = frame_width
        self.frame_height = frame_height

        self._capture: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._grabbed_ok = False

    def start(self) -> "CameraStream":
        """
        Open the camera device and start the background capture thread.

        Raises:
            RuntimeError: If the camera device cannot be opened.
        """
        self._capture = cv2.VideoCapture(self.camera_index)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)

        if not self._capture.isOpened():
            raise RuntimeError(
                f"Could not open camera at index {self.camera_index}. "
                "Check that it's connected and not in use by another app."
            )

        # Prime the first frame synchronously so callers can read() immediately.
        ok, frame = self._capture.read()
        self._grabbed_ok = ok
        self._frame = frame if ok else None

        self._running = True
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()

        logger.info("Camera stream started on index %s", self.camera_index)
        return self

    def _update_loop(self) -> None:
        """Background thread loop: continuously grab the latest frame."""
        consecutive_failures = 0

        while self._running:
            if self._capture is None:
                break

            ok, frame = self._capture.read()

            if not ok:
                consecutive_failures += 1
                self._grabbed_ok = False
                if consecutive_failures % 30 == 1:
                    # Throttle log spam if the camera stays down for a while.
                    logger.warning("Camera read failed (attempt %d).", consecutive_failures)
                time.sleep(0.05)
                continue

            consecutive_failures = 0
            with self._frame_lock:
                self._frame = frame
                self._grabbed_ok = True

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Return the most recently captured frame.

        Returns:
            (success, frame) tuple. success is False if the camera has
            never produced a frame or is currently failing.
        """
        with self._frame_lock:
            if self._frame is None:
                return False, None
            return self._grabbed_ok, self._frame.copy()

    def is_healthy(self) -> bool:
        """Return True if the camera is currently producing frames."""
        return self._grabbed_ok

    def stop(self) -> None:
        """Stop the background thread and release the camera device."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._capture is not None:
            self._capture.release()
        logger.info("Camera stream stopped and released.")

    def __enter__(self) -> "CameraStream":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()