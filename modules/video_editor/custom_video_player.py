"""
modules/video_editor/custom_video_player.py
Custom Video Player using MoviePy (no DirectShow dependency)
"""

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
import numpy as np

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class CustomVideoPlayer(QWidget):
    """
    Custom video player widget using MoviePy for frame extraction
    No dependency on DirectShow codecs - works with any format MoviePy supports
    """

    # Signals
    position_changed = pyqtSignal(int)  # Position in milliseconds
    duration_changed = pyqtSignal(int)  # Duration in milliseconds
    state_changed = pyqtSignal(str)     # "playing", "paused", "stopped"
    error_occurred = pyqtSignal(str)    # Error message

    def __init__(self, parent=None):
        super().__init__(parent)

        # Video properties
        self.video_clip = None
        self.current_frame = 0
        self.total_frames = 0
        self.fps = 30
        self.duration = 0
        self.is_playing = False

        # Playback timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Video display label
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #000000;")
        self.video_label.setMinimumSize(800, 450)
        self.video_label.setScaledContents(False)

        layout.addWidget(self.video_label)
        self.setLayout(layout)

    def load_video(self, video_path):
        """Load video file using MoviePy"""
        try:
            logger.info(f"Loading video with custom player: {video_path}")

            # Try MoviePy 2.x import first
            try:
                from moviepy import VideoFileClip
            except ImportError:
                from moviepy.editor import VideoFileClip

            # Load video
            self.video_clip = VideoFileClip(video_path)
            self.duration = self.video_clip.duration
            self.fps = self.video_clip.fps
            self.total_frames = int(self.duration * self.fps)
            self.current_frame = 0

            logger.info(f"Video loaded: duration={self.duration}s, fps={self.fps}, frames={self.total_frames}")

            # Emit duration
            self.duration_changed.emit(int(self.duration * 1000))

            # Show first frame
            self.show_frame(0)

            return True

        except Exception as e:
            error_msg = f"Failed to load video: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def show_frame(self, frame_number):
        """Display a specific frame"""
        try:
            if not self.video_clip:
                return

            # Calculate time from frame number
            time_position = frame_number / self.fps

            # Ensure we don't go beyond duration
            if time_position >= self.duration:
                time_position = self.duration - 0.001
                self.stop()
                return

            # Get frame from video
            frame = self.video_clip.get_frame(time_position)

            # Convert numpy array to QImage
            height, width, channel = frame.shape
            bytes_per_line = 3 * width

            q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)

            # Convert to pixmap and display
            pixmap = QPixmap.fromImage(q_image)

            # Scale to fit label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.video_label.setPixmap(scaled_pixmap)

            # Update current frame
            self.current_frame = frame_number

            # Emit position
            self.position_changed.emit(int(time_position * 1000))

        except Exception as e:
            logger.error(f"Error showing frame {frame_number}: {e}")

    def play(self):
        """Start playback"""
        if not self.video_clip:
            logger.warning("No video loaded")
            return

        self.is_playing = True

        # Calculate timer interval based on FPS
        interval = int(1000 / self.fps)  # milliseconds per frame
        self.timer.start(interval)

        self.state_changed.emit("playing")
        logger.info(f"Playback started (fps={self.fps}, interval={interval}ms)")

    def pause(self):
        """Pause playback"""
        self.is_playing = False
        self.timer.stop()
        self.state_changed.emit("paused")
        logger.info("Playback paused")

    def stop(self):
        """Stop playback"""
        self.is_playing = False
        self.timer.stop()
        self.current_frame = 0
        if self.video_clip:
            self.show_frame(0)
        self.state_changed.emit("stopped")
        logger.info("Playback stopped")

    def update_frame(self):
        """Update to next frame (called by timer)"""
        if not self.is_playing:
            return

        # Move to next frame
        self.current_frame += 1

        # Check if reached end
        if self.current_frame >= self.total_frames:
            self.stop()
            return

        # Show the frame
        self.show_frame(self.current_frame)

    def seek(self, position_ms):
        """Seek to position in milliseconds"""
        if not self.video_clip:
            return

        time_position = position_ms / 1000.0
        frame_number = int(time_position * self.fps)

        # Ensure frame is within bounds
        frame_number = max(0, min(frame_number, self.total_frames - 1))

        self.current_frame = frame_number
        self.show_frame(frame_number)

        logger.debug(f"Seeked to {time_position}s (frame {frame_number})")

    def get_state(self):
        """Get current playback state"""
        if self.is_playing:
            return "playing"
        elif self.video_clip and self.current_frame > 0:
            return "paused"
        else:
            return "stopped"

    def cleanup(self):
        """Clean up resources"""
        self.timer.stop()
        if self.video_clip:
            try:
                self.video_clip.close()
            except:
                pass
        self.video_clip = None
        logger.info("Custom video player cleaned up")

    def __del__(self):
        """Destructor"""
        self.cleanup()
