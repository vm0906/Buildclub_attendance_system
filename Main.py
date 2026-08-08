"""
main.py

Entry point for the Face Recognition Attendance System.

Responsibilities:
    - Open the threaded webcam stream (camera.py).
    - Feed each frame through the attendance pipeline (attendance.py),
      which detects/matches faces, draws boxes + confidence %, and
      updates ENTRY/EXIT session tracking behind the scenes.
    - Overlay a live FPS counter.
    - Show a clear on-screen message if the camera disconnects, instead
      of crashing.
    - Exit cleanly on 'q', flushing any still-active sessions.
"""

import time

import cv2
import numpy as np

from attendance import AttendanceManager
from camera import CameraStream
from config import Config
from utils import setup_logger

logger = setup_logger(__name__)

QUIT_KEY = "q"


def _draw_fps(frame: np.ndarray, fps: float) -> np.ndarray:
    """Overlay the current FPS in the top-left corner of the frame."""
    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (10, 30),
        cv2.FONT_HERSHEY_DUPLEX,
        0.8,
        (0, 255, 255),
        2,
    )
    return frame


def _draw_camera_offline_banner(frame_shape=(480, 640, 3)) -> np.ndarray:
    """Build a placeholder black frame with a 'camera offline' message,
    shown when the webcam stream stops producing frames."""
    blank = np.zeros(frame_shape, dtype="uint8")
    cv2.putText(
        blank,
        "Camera disconnected - retrying...",
        (30, frame_shape[0] // 2),
        cv2.FONT_HERSHEY_DUPLEX,
        0.8,
        (0, 0, 255),
        2,
    )
    return blank


def run() -> None:
    """Run the main real-time attendance loop until the user quits."""
    Config.ensure_directories()

    try:
        camera = CameraStream().start()
    except RuntimeError as exc:
        logger.critical("Fatal: could not start camera - %s", exc)
        return

    attendance_manager = AttendanceManager()

    fps = 0.0
    prev_tick = time.time()

    logger.info("Starting main loop. Press '%s' in the video window to quit.", QUIT_KEY)

    try:
        while True:
            ok, frame = camera.read()

            if not ok or frame is None:
                display_frame = _draw_camera_offline_banner()
            else:
                display_frame = attendance_manager.process_frame(frame)

            # --- FPS calculation (simple exponential smoothing) ---
            now_tick = time.time()
            elapsed = now_tick - prev_tick
            prev_tick = now_tick
            if elapsed > 0:
                instantaneous_fps = 1.0 / elapsed
                fps = fps * 0.9 + instantaneous_fps * 0.1  # smooth out jitter

            display_frame = _draw_fps(display_frame, fps)

            cv2.imshow(Config.WINDOW_NAME, display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord(QUIT_KEY):
                logger.info("Quit key pressed - shutting down.")
                break

            # If the OS closed the window via the 'X' button, exit too.
            if cv2.getWindowProperty(Config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                logger.info("Video window closed - shutting down.")
                break

    except KeyboardInterrupt:
        logger.info("Interrupted (Ctrl+C) - shutting down.")

    finally:
        # Always attempt a clean shutdown, even if something above raised.
        camera.stop()
        attendance_manager.shutdown()
        cv2.destroyAllWindows()
        logger.info("Shutdown complete. Goodbye!")


if __name__ == "__main__":
    run()