"""
modules/video_editor/custom_video_player.py
Threaded video playback for dual preview integration.
"""

import os
import time
from threading import RLock
from typing import Optional

import cv2
import numpy as np
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class VideoPlaybackThread(QThread):
    """Background thread that streams frames from OpenCV into the Qt event loop."""

    frame_ready = pyqtSignal(object, bool)  # numpy.ndarray (RGB frame), is_before flag
    position_changed = pyqtSignal(float)    # current playback time in seconds
    duration_changed = pyqtSignal(float)    # total duration in seconds
    state_changed = pyqtSignal(str)         # "playing", "paused", "stopped"

    def __init__(self, is_before: bool = True) -> None:
        super().__init__()
        self.video_path: str = ""
        self.cap: Optional[cv2.VideoCapture] = None
        self.playing: bool = False
        self.position: float = 0.0
        self.duration: float = 0.0
        self.fps: float = 30.0
        self.speed_factor: float = 1.0
        self.state: str = "stopped"
        self._running: bool = True
        self.is_before: bool = is_before
        self._capture_lock = RLock()
        self._frame_interval: float = 1.0 / 30.0
        self._next_frame_time: float | None = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def load_video(self, video_path: str) -> bool:
        """Load a video file from disk using OpenCV."""
        try:
            logger.info(f"Loading video: {video_path}")

            if not os.path.exists(video_path):
                logger.error(f"Video file not found: {video_path}")
                return False

            candidate = cv2.VideoCapture(video_path)
            if not candidate or not candidate.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                if candidate:
                    candidate.release()
                return False

            fps_value = candidate.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = candidate.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            duration = frame_count / fps_value if fps_value else 0.0

            with self._capture_lock:
                self._release_capture_locked()
                self.cap = candidate
                self.fps = fps_value or 30.0
                self.duration = duration
                self.video_path = video_path
                self.playing = False
                self.position = 0.0
                self._frame_interval = 1.0 / max(self.fps or 0.0, 1e-6)
                self._next_frame_time = None

            self._update_state("stopped")

            logger.info(f"Video loaded: {self.duration:.2f}s @ {self.fps:.2f}fps")
            self.duration_changed.emit(self.duration)
            return True

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(f"Error loading video: {exc}")
            self._release_capture()
            return False

    def play(self) -> None:
        """Start or resume playback."""
        with self._capture_lock:
            if not self.cap or not self.cap.isOpened():
                logger.warning("Ignored play request: no video loaded")
                return

            if self.duration and self.position >= self.duration:
                # If we reached the end previously, restart from the beginning.
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.position = 0.0

            self.playing = True
            self._next_frame_time = time.perf_counter()

        self._update_state("playing")
        logger.debug("Playback started")

    def pause(self) -> None:
        """Pause playback."""
        with self._capture_lock:
            if not self.playing:
                return
            self.playing = False
            self._next_frame_time = None

        self._update_state("paused")
        logger.debug("Playback paused")

    def stop(self) -> None:
        """Stop playback and reset to the first frame."""
        should_emit = False
        with self._capture_lock:
            self.playing = False
            self.position = 0.0

            if self.cap and self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                should_emit = True
            self._next_frame_time = None

        if should_emit:
            self._emit_current_frame()

        self._update_state("stopped")
        logger.debug("Playback stopped and reset")

    def seek(self, position_seconds: float) -> None:
        """Seek to a specific position expressed in seconds."""
        with self._capture_lock:
            if not self.cap or not self.cap.isOpened():
                return

            target = max(0.0, min(position_seconds, self.duration or 0.0))
            frame_number = int(target * self.fps)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

            ret, frame = self.cap.read()
            if not ret:
                logger.warning(f"Seek failed to position {target:.3f}s")
                return

            self.position = target
            if self.playing:
                self._next_frame_time = time.perf_counter()

        self._emit_frame(frame, emit_position=True)
        logger.debug(f"Seeked to {target:.3f}s")

    def set_speed(self, factor: float) -> None:
        """Update playback speed factor (0.1x - 8.0x)."""
        sanitized = max(0.1, min(float(factor), 8.0))
        now = time.perf_counter()
        with self._capture_lock:
            self.speed_factor = sanitized
            if self.playing:
                self._next_frame_time = now

    def get_speed(self) -> float:
        """Return current playback speed factor."""
        with self._capture_lock:
            return self.speed_factor

    def get_state(self) -> str:
        """Return the current playback state."""
        return self.state

    def has_video(self) -> bool:
        """Return True when a video capture is loaded."""
        with self._capture_lock:
            return bool(self.cap) and self.cap.isOpened()

    # ------------------------------------------------------------------ #
    # QThread lifecycle
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """Continuously read frames while the thread is alive."""
        logger.debug("Video playback thread started")
        while self._running:
            try:
                with self._capture_lock:
                    cap = self.cap
                    is_playing = self.playing and cap and cap.isOpened()
                    speed = self.speed_factor
                    next_frame_time = self._next_frame_time
                    frame_interval = self._frame_interval

                if not is_playing or not cap:
                    QThread.msleep(20)
                    continue

                if frame_interval <= 0:
                    frame_interval = 1.0 / 30.0

                if next_frame_time is None:
                    with self._capture_lock:
                        self._next_frame_time = time.perf_counter()
                    QThread.msleep(1)
                    continue

                now = time.perf_counter()
                if now < next_frame_time:
                    sleep_seconds = next_frame_time - now
                    QThread.msleep(max(1, int(sleep_seconds * 1000)))
                    continue

                frame = None
                with self._capture_lock:
                    if cap and cap.isOpened():
                        ret, frame = cap.read()
                        if ret:
                            self.position = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                        else:
                            frame = None
                    else:
                        ret = False
                        frame = None

                if frame is not None:
                    self._emit_frame(frame, emit_position=True)

                if ret:
                    interval = frame_interval / max(speed, 1e-6)
                    with self._capture_lock:
                        self._next_frame_time = next_frame_time + interval
                    continue

                with self._capture_lock:
                    self.playing = False
                    self.position = 0.0
                    if self.cap and self.cap.isOpened():
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self._next_frame_time = None

                self._update_state("stopped")
                self._emit_current_frame()

            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception(f"Error in playback loop: {exc}")
                QThread.msleep(50)

        logger.debug("Video playback thread stopped")

    def cleanup(self) -> None:
        """Stop the thread and release resources."""
        with self._capture_lock:
            self.playing = False
            self._next_frame_time = None
        self._running = False
        self._update_state("stopped")

        # Give the loop a chance to exit.
        if self.isRunning():
            self.wait(200)

        self._release_capture()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _emit_current_frame(self) -> None:
        """Read the current frame (without advancing) and emit it."""
        with self._capture_lock:
            if not self.cap or not self.cap.isOpened():
                return

            current_index = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            ret, frame = self.cap.read()
            if ret:
                # If read advanced the frame pointer, roll back.
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, current_index)
            else:
                frame = None

        if ret and frame is not None:
            self._emit_frame(frame, emit_position=True)

    def _emit_frame(self, frame, *, emit_position: bool) -> None:
        """Convert the frame to RGB array and emit it to both preview windows."""
        if frame is None:
            return

        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except cv2.error as exc:
            logger.error(f"OpenCV failed to convert frame: {exc}")
            return

        # Ensure data is contiguous before handing off to Qt.
        frame_rgb = np.ascontiguousarray(frame_rgb)

        self.frame_ready.emit(frame_rgb, self.is_before)
        if emit_position:
            self.position_changed.emit(self.position)

    def _update_state(self, new_state: str) -> None:
        if self.state == new_state:
            return
        self.state = new_state
        self.state_changed.emit(new_state)

    def _release_capture(self) -> None:
        with self._capture_lock:
            self._release_capture_locked()

    def _release_capture_locked(self) -> None:
        if self.cap:
            try:
                self.cap.release()
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Failed to release video capture")
            finally:
                self.cap = None


class IntegratedVideoPlayer(QObject):
    """
    Lightweight video player wrapper that exposes thread signals to the UI.
    """

    frame_ready = pyqtSignal(object, bool)
    position_changed = pyqtSignal(float)
    duration_changed = pyqtSignal(float)
    state_changed = pyqtSignal(str)

    def __init__(self, preview_role: str = "before") -> None:
        super().__init__()
        self.preview_role = preview_role
        self._is_before = preview_role.lower() == "before"
        self.thread = VideoPlaybackThread(is_before=self._is_before)

        # Forward worker signals to the UI layer.
        self.thread.frame_ready.connect(self.frame_ready)
        self.thread.position_changed.connect(self.position_changed)
        self.thread.duration_changed.connect(self.duration_changed)
        self.thread.state_changed.connect(self.state_changed)

        self.thread.start()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def load_video(self, video_path: str) -> bool:
        return self.thread.load_video(video_path)

    def play(self) -> None:
        self.thread.play()

    def pause(self) -> None:
        self.thread.pause()

    def stop(self) -> None:
        self.thread.stop()

    def seek(self, position_seconds: float) -> None:
        self.thread.seek(position_seconds)

    def set_speed(self, factor: float) -> None:
        self.thread.set_speed(factor)

    def get_speed(self) -> float:
        return self.thread.get_speed()

    def get_duration(self) -> float:
        return self.thread.duration

    def get_position(self) -> float:
        return self.thread.position

    def get_state(self) -> str:
        return self.thread.get_state()

    def has_video(self) -> bool:
        return self.thread.has_video()

    def cleanup(self) -> None:
        self.thread.cleanup()
