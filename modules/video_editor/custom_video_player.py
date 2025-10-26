"""
modules/video_editor/custom_video_player.py
Fixed Custom Video Player with proper MoviePy imports and error handling
"""

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSlider
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
import numpy as np
import os

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class CustomVideoPlayer(QWidget):
    """
    Professional video player widget with MoviePy backend
    Compatible with your video editor project structure
    """

    # Signals
    position_changed = pyqtSignal(int)  # Position in milliseconds
    duration_changed = pyqtSignal(int)  # Duration in milliseconds
    state_changed = pyqtSignal(str)     # "playing", "paused", "stopped"
    error_occurred = pyqtSignal(str)    # Error message
    video_loaded = pyqtSignal(str)      # Video file path when loaded

    def __init__(self, parent=None):
        super().__init__(parent)

        # Video properties
        self.video_clip = None
        self.current_frame = 0
        self.total_frames = 0
        self.fps = 30
        self.duration = 0
        self.is_playing = False
        self.video_path = None
        self.slider_dragging = False
        self.was_playing_before_drag = False

        # Playback timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        # Import moviepy (handle different versions)
        self.moviepy_available = False
        self.VideoFileClip = None
        self.import_moviepy()

        self.init_ui()
        self.setup_connections()

    def import_moviepy(self):
        """Import MoviePy with proper error handling for different versions"""
        try:
            # Method 1: Try moviepy.editor (most common)
            try:
                from moviepy.editor import VideoFileClip
                self.VideoFileClip = VideoFileClip
                self.moviepy_available = True
                logger.info("✅ MoviePy imported successfully via moviepy.editor")
                return
            except ImportError as e:
                logger.warning(f"Method 1 failed: {e}")

            # Method 2: Try direct moviepy import
            try:
                import moviepy
                if hasattr(moviepy, 'VideoFileClip'):
                    self.VideoFileClip = moviepy.VideoFileClip
                    self.moviepy_available = True
                    logger.info("✅ MoviePy imported successfully via direct import")
                    return
            except (ImportError, AttributeError) as e:
                logger.warning(f"Method 2 failed: {e}")

            # Method 3: Try alternative import path
            try:
                from moviepy.video.io.VideoFileClip import VideoFileClip
                self.VideoFileClip = VideoFileClip
                self.moviepy_available = True
                logger.info("✅ MoviePy imported successfully via moviepy.video.io")
                return
            except ImportError as e:
                logger.warning(f"Method 3 failed: {e}")

            # If all methods fail
            self.moviepy_available = False
            logger.error("❌ All MoviePy import methods failed")
            
        except Exception as e:
            logger.error(f"❌ Unexpected error importing MoviePy: {e}")
            self.moviepy_available = False

    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Video display area
        self.setup_video_display(layout)
        
        # Playback controls
        self.setup_playback_controls(layout)
        
        # Progress slider
        self.setup_progress_slider(layout)
        
        # Status area
        self.setup_status_area(layout)

        self.setLayout(layout)

    def setup_video_display(self, layout):
        """Setup video display label"""
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border: 2px solid #333333;
                border-radius: 6px;
                min-height: 400px;
            }
        """)
        self.video_label.setMinimumSize(800, 450)
        self.video_label.setScaledContents(False)
        
        # Default message
        self.video_label.setText(
            "<div style='color: #666666; font-size: 16px; padding: 20px;'>"
            "🎬 Video Player Ready<br>"
            "<span style='font-size: 12px;'>Load a video to begin editing</span>"
            "</div>"
        )
        
        layout.addWidget(self.video_label)

    def setup_playback_controls(self, layout):
        """Setup playback control buttons"""
        controls_layout = QHBoxLayout()
        
        # Playback buttons
        self.play_btn = self.create_control_button("▶️", "Play", "#00bcd4")
        self.pause_btn = self.create_control_button("⏸️", "Pause", "#ff9800")
        self.stop_btn = self.create_control_button("⏹️", "Stop", "#f44336")
        self.restart_btn = self.create_control_button("⏮️", "Restart", "#9c27b0")
        
        # Time display
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-family: 'Consolas', monospace;
                font-size: 14px;
                padding: 8px 12px;
                background: #252525;
                border-radius: 6px;
                min-width: 120px;
                text-align: center;
            }
        """)
        self.time_label.setAlignment(Qt.AlignCenter)
        
        # Add to layout
        controls_layout.addWidget(self.restart_btn)
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.pause_btn)
        controls_layout.addWidget(self.stop_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(self.time_label)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)

    def setup_progress_slider(self, layout):
        """Setup progress slider"""
        slider_layout = QHBoxLayout()
        
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #333333;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00bcd4;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -5px 0;
            }
            QSlider::sub-page:horizontal {
                background: #00bcd4;
                border-radius: 3px;
            }
        """)
        self.progress_slider.sliderPressed.connect(self.on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self.on_slider_released)
        self.progress_slider.sliderMoved.connect(self.on_slider_moved)
        
        slider_layout.addWidget(self.progress_slider)
        layout.addLayout(slider_layout)

    def setup_status_area(self, layout):
        """Setup status information area"""
        self.status_label = QLabel("Ready to load video")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 12px;
                padding: 8px;
                background: #1a1a1a;
                border-radius: 4px;
                border: 1px solid #333333;
            }
        """)
        layout.addWidget(self.status_label)

    def create_control_button(self, icon, tooltip, color):
        """Create a styled control button"""
        btn = QPushButton(icon)
        btn.setToolTip(tooltip)
        btn.setFixedSize(40, 40)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.lighten_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self.darken_color(color)};
            }}
            QPushButton:disabled {{
                background-color: #666666;
                color: #999999;
            }}
        """)
        return btn

    def setup_connections(self):
        """Connect signals and slots"""
        self.play_btn.clicked.connect(self.play)
        self.pause_btn.clicked.connect(self.pause)
        self.stop_btn.clicked.connect(self.stop)
        self.restart_btn.clicked.connect(self.restart)

    def load_video(self, video_path):
        """Load a video file with comprehensive error handling"""
        try:
            if not self.moviepy_available:
                error_msg = (
                    "MoviePy not available!\n\n"
                    "Please install MoviePy:\n"
                    "pip install moviepy"
                )
                self.show_error_message(error_msg)
                self.error_occurred.emit(error_msg)
                return False

            if not os.path.exists(video_path):
                error_msg = f"Video file not found:\n{video_path}"
                self.show_error_message(error_msg)
                self.error_occurred.emit(error_msg)
                return False

            logger.info(f"🎥 Loading video: {video_path}")
            self.video_path = video_path
            self.show_status_message("Loading video...", "info")

            # Clean up previous video
            self.cleanup()

            # Load video with MoviePy
            self.video_clip = self.VideoFileClip(video_path)
            
            # Get video properties
            self.duration = self.video_clip.duration
            self.fps = self.video_clip.fps or 30  # Default to 30 if None
            self.total_frames = int(self.duration * self.fps)
            self.current_frame = 0

            logger.info(f"✅ Video loaded: {self.duration:.2f}s, {self.fps}fps, {self.total_frames} frames")

            # Emit signals
            self.duration_changed.emit(int(self.duration * 1000))
            self.video_loaded.emit(video_path)

            # Show first frame
            self.show_frame(0)
            
            # Update UI state
            self.update_controls_state()
            self.show_status_message(
                f"Loaded: {os.path.basename(video_path)} "
                f"({self.duration:.1f}s, {int(self.fps)}fps)",
                "success"
            )

            return True

        except Exception as e:
            error_msg = f"Failed to load video:\n{str(e)}"
            logger.error(f"❌ {error_msg}")
            self.show_error_message(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def show_frame(self, frame_number):
        """Display a specific frame with comprehensive error handling"""
        try:
            if not self.video_clip:
                return

            # Calculate time from frame number
            time_position = frame_number / self.fps

            # Ensure we don't go beyond duration
            if time_position >= self.duration:
                time_position = self.duration - 0.001
                if self.is_playing:
                    self.stop()
                return

            # Get frame from video
            frame = self.video_clip.get_frame(time_position)

            # Convert numpy array to QImage
            height, width, channel = frame.shape
            bytes_per_line = 3 * width

            # Ensure frame is in correct format (RGB)
            if frame.dtype != np.uint8:
                frame = (frame * 255).astype(np.uint8)

            # Create QImage from numpy array
            q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)

            # Convert to pixmap
            pixmap = QPixmap.fromImage(q_image)

            # Scale to fit label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            self.video_label.setPixmap(scaled_pixmap)

            # Update current frame and emit position
            self.current_frame = frame_number
            position_ms = int(time_position * 1000)
            self.position_changed.emit(position_ms)
            
            # Update progress slider (if not being dragged)
            if not self.slider_dragging:
                self.progress_slider.setValue(position_ms)
            
            # Update time display
            self.update_time_display(position_ms)

        except Exception as e:
            logger.error(f"❌ Error showing frame {frame_number}: {e}")
            self.show_error_message(f"Frame error: {str(e)}")

    def update_time_display(self, position_ms):
        """Update the time display label"""
        total_ms = int(self.duration * 1000)
        
        current_time = self.format_time(position_ms)
        total_time = self.format_time(total_ms)
        
        self.time_label.setText(f"{current_time} / {total_time}")

    def format_time(self, milliseconds):
        """Format milliseconds to HH:MM:SS or MM:SS"""
        seconds = milliseconds // 1000
        minutes = seconds // 60
        hours = minutes // 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes % 60:02d}:{seconds % 60:02d}"
        else:
            return f"{minutes:02d}:{seconds % 60:02d}"

    def play(self):
        """Start video playback"""
        if not self.video_clip:
            self.show_error_message("No video loaded to play")
            return

        if self.current_frame >= self.total_frames - 1:
            self.current_frame = 0  # Restart from beginning

        self.is_playing = True

        # Calculate timer interval based on FPS
        interval = max(1, int(1000 / self.fps))
        self.timer.start(interval)

        self.state_changed.emit("playing")
        self.show_status_message("Playing...", "info")
        self.update_controls_state()
        
        logger.info(f"▶️ Playback started (fps={self.fps}, interval={interval}ms)")

    def pause(self):
        """Pause video playback"""
        self.is_playing = False
        self.timer.stop()
        self.state_changed.emit("paused")
        self.show_status_message("Paused", "warning")
        self.update_controls_state()
        logger.info("⏸️ Playback paused")

    def stop(self):
        """Stop video playback and reset to beginning"""
        self.is_playing = False
        self.timer.stop()
        self.current_frame = 0
        if self.video_clip:
            self.show_frame(0)
        self.state_changed.emit("stopped")
        self.show_status_message("Stopped", "info")
        self.update_controls_state()
        logger.info("⏹️ Playback stopped")

    def restart(self):
        """Restart video from beginning"""
        self.current_frame = 0
        if self.video_clip:
            self.show_frame(0)
        if self.is_playing:
            self.play()  # Continue playing from start
        logger.info("⏮️ Playback restarted")

    def update_frame(self):
        """Update to next frame (called by timer)"""
        if not self.is_playing or not self.video_clip:
            return

        # Move to next frame
        self.current_frame += 1

        # Check if reached end
        if self.current_frame >= self.total_frames:
            self.stop()
            self.show_status_message("Playback finished", "success")
            return

        # Show the frame
        self.show_frame(self.current_frame)

    def seek(self, position_ms):
        """Seek to specific position in milliseconds"""
        if not self.video_clip:
            return

        time_position = position_ms / 1000.0
        frame_number = int(time_position * self.fps)

        # Ensure frame is within bounds
        frame_number = max(0, min(frame_number, self.total_frames - 1))

        # Pause if playing to avoid timer conflicts
        was_playing = self.is_playing
        if was_playing:
            self.pause()

        self.current_frame = frame_number
        self.show_frame(frame_number)

        # Resume if was playing
        if was_playing:
            self.play()

        logger.debug(f"🔍 Seeked to {time_position:.2f}s (frame {frame_number})")

    # Slider event handlers
    def on_slider_pressed(self):
        """Handle slider press - pause playback during dragging"""
        self.slider_dragging = True
        if self.is_playing:
            self.was_playing_before_drag = True
            self.pause()
        else:
            self.was_playing_before_drag = False

    def on_slider_released(self):
        """Handle slider release - seek to position and resume if needed"""
        self.slider_dragging = False
        position_ms = self.progress_slider.value()
        self.seek(position_ms)
        
        if self.was_playing_before_drag:
            self.play()

    def on_slider_moved(self, position):
        """Handle slider movement - update time display"""
        if self.slider_dragging:
            self.update_time_display(position)

    def update_controls_state(self):
        """Update control buttons state based on playback state"""
        has_video = self.video_clip is not None
        
        self.play_btn.setEnabled(has_video and not self.is_playing)
        self.pause_btn.setEnabled(has_video and self.is_playing)
        self.stop_btn.setEnabled(has_video)
        self.restart_btn.setEnabled(has_video)
        self.progress_slider.setEnabled(has_video)

        # Set maximum for progress slider
        if has_video:
            self.progress_slider.setMaximum(int(self.duration * 1000))

    def show_error_message(self, message):
        """Display error message in the video area"""
        self.video_label.setText(
            f"<div style='color: #ff4444; font-size: 14px; padding: 20px; text-align: center;'>"
            f"❌ Error<br>"
            f"<span style='font-size: 12px; color: #cccccc;'>{message}</span>"
            f"</div>"
        )
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #2a1a1a;
                border: 2px solid #ff4444;
                border-radius: 6px;
                color: #ff4444;
            }
        """)
        self.status_label.setText(f"Error: {message.splitlines()[0]}")
        self.status_label.setStyleSheet("color: #ff4444; background: #2a1a1a;")

    def show_status_message(self, message, message_type="info"):
        """Display status message"""
        colors = {
            "info": ("#888888", "#1a1a1a"),
            "success": ("#4CAF50", "#1a2a1a"),
            "warning": ("#FF9800", "#2a2a1a"),
            "error": ("#ff4444", "#2a1a1a")
        }
        
        color, bg_color = colors.get(message_type, colors["info"])
        
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            color: {color}; 
            background: {bg_color};
            font-size: 12px;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid {color}33;
        """)

    def get_state(self):
        """Get current playback state"""
        if self.is_playing:
            return "playing"
        elif self.video_clip and self.current_frame > 0:
            return "paused"
        else:
            return "stopped"

    def get_video_info(self):
        """Get video information dictionary"""
        if not self.video_clip:
            return None
            
        return {
            "path": self.video_path,
            "duration": self.duration,
            "fps": self.fps,
            "total_frames": self.total_frames,
            "current_frame": self.current_frame,
            "current_time": self.current_frame / self.fps,
            "state": self.get_state()
        }

    def resizeEvent(self, event):
        """Handle resize events to update video scaling"""
        super().resizeEvent(event)
        if self.video_clip and self.video_label.pixmap():
            # Re-scale the current frame to fit new size
            current_frame = self.current_frame
            self.show_frame(current_frame)

    def cleanup(self):
        """Clean up resources properly"""
        self.timer.stop()
        self.is_playing = False
        self.slider_dragging = False
        
        if self.video_clip:
            try:
                self.video_clip.close()
            except Exception as e:
                logger.warning(f"⚠️ Error closing video clip: {e}")
            finally:
                self.video_clip = None
                
        self.video_path = None
        self.current_frame = 0
        self.total_frames = 0
        
        # Reset UI
        self.progress_slider.setValue(0)
        self.progress_slider.setMaximum(100)
        self.time_label.setText("00:00 / 00:00")
        self.update_controls_state()
        
        logger.info("🧹 Video player cleaned up")

    @staticmethod
    def lighten_color(color):
        """Lighten a hex color for hover effects"""
        # Simple implementation - you can enhance this
        return color

    @staticmethod
    def darken_color(color):
        """Darken a hex color for pressed effects"""
        # Simple implementation - you can enhance this
        return color

    def __del__(self):
        """Destructor"""
        self.cleanup()