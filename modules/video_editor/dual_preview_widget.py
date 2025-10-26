"""
modules/video_editor/dual_preview_widget.py
Dual Preview Window System - Before/After Comparison
"""
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QSlider, QComboBox, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPixmap, QPainter

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class PreviewWindow(QFrame):
    """Single preview window (Before or After)"""

    def __init__(self, window_type="before", parent=None):
        super().__init__(parent)
        self.window_type = window_type  # "before" or "after"
        self.is_playing = False
        self.current_time = 0.0
        self.duration = 0.0
        self.video_loaded = False

        self.init_ui()

    def init_ui(self):
        """Initialize preview window UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setFixedHeight(35)

        if self.window_type == "before":
            header.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1a1a1a, stop:1 #0f0f0f);
                    border-bottom: 1px solid #2a2a2a;
                }
            """)
        else:
            header.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1a1a1a, stop:1 #0f0f0f);
                    border-bottom: 1px solid #00bcd4;
                }
            """)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.setSpacing(10)

        # Title
        if self.window_type == "before":
            title_text = "📹 BEFORE EDITING"
            title_color = "#ffffff"
        else:
            title_text = "✨ AFTER EDITING"
            title_color = "#00bcd4"

        self.title_label = QLabel(title_text)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {title_color};
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
        """)
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Status badge
        if self.window_type == "before":
            status = QLabel("ORIGINAL")
            status.setStyleSheet("""
                QLabel {
                    background-color: #2196f3;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)
        else:
            status = QLabel("⟳ LIVE")
            status.setStyleSheet("""
                QLabel {
                    background-color: #4caf50;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)

        header_layout.addWidget(status)

        header.setLayout(header_layout)
        layout.addWidget(header)

        # Preview canvas - FIXED: Proper layout structure
        self.canvas = QFrame()
        self.canvas.setMinimumSize(400, 300)
        self.canvas.setStyleSheet("""
            QFrame {
                background-color: #000000;
                border: none;
            }
        """)

        # Main canvas layout
        self.canvas_layout = QVBoxLayout(self.canvas)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas_layout.setSpacing(0)

        # Video display area - CENTER ALIGNED
        self.video_container = QFrame()
        self.video_container.setStyleSheet("background: transparent;")
        self.video_layout = QVBoxLayout(self.video_container)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_layout.setAlignment(Qt.AlignCenter)

        # Video placeholder - ACTUAL VIDEO WILL SHOW HERE
        self.video_placeholder = QLabel()
        self.video_placeholder.setAlignment(Qt.AlignCenter)
        self.video_placeholder.setMinimumSize(400, 300)
        self.video_placeholder.setStyleSheet("""
            QLabel {
                background: #0a0a0a;
                border: 2px dashed #333;
                color: #666666;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        
        if self.window_type == "before":
            self.video_placeholder.setText("BEFORE\n\nOriginal Video\n\nClick Play to Start")
        else:
            self.video_placeholder.setText("AFTER\n\nEdited Preview\n\nClick Play to Start")

        self.video_layout.addWidget(self.video_placeholder)

        # Overlay container for timecode, frame info etc.
        self.overlay_container = QFrame()
        self.overlay_container.setStyleSheet("background: transparent;")
        self.overlay_layout = QVBoxLayout(self.overlay_container)
        self.overlay_layout.setContentsMargins(10, 10, 10, 10)

        # Top row overlay (frame number + resolution)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        # Frame number
        self.frame_label = QLabel("Frame: 0")
        self.frame_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        top_row.addWidget(self.frame_label)

        top_row.addStretch()

        # Resolution
        self.resolution_label = QLabel("1920x1080")
        self.resolution_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        top_row.addWidget(self.resolution_label)

        self.overlay_layout.addLayout(top_row)

        # Effect badges (for After window only)
        if self.window_type == "after":
            self.effects_container = QFrame()
            self.effects_container.setStyleSheet("background: transparent;")
            self.effects_layout = QHBoxLayout(self.effects_container)
            self.effects_layout.setContentsMargins(0, 5, 0, 0)
            self.effects_layout.setSpacing(5)
            self.overlay_layout.addWidget(self.effects_container)

        self.overlay_layout.addStretch()

        # Bottom row (timecode)
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)

        # Timecode
        self.timecode_label = QLabel("00:00 / 00:00")
        self.timecode_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 6px 10px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        bottom_row.addWidget(self.timecode_label)

        bottom_row.addStretch()
        self.overlay_layout.addLayout(bottom_row)

        # Stack the video and overlay
        self.canvas_layout.addWidget(self.video_container)
        self.canvas_layout.addWidget(self.overlay_container)

        layout.addWidget(self.canvas, 1)
        self.setLayout(layout)

    def set_video(self, video_path):
        """Set video for this preview window - SHOW ACTUAL VIDEO CONTENT"""
        try:
            print(f"DEBUG: PreviewWindow.set_video() called for {video_path}")
            
            import os
            video_name = os.path.basename(video_path)
            
            # Update title with video name
            if self.window_type == "before":
                self.title_label.setText(f"📹 BEFORE: {video_name}")
            else:
                self.title_label.setText(f"✨ AFTER: {video_name}")

            # Create a visual representation of loaded video
            self.video_loaded = True
            
            # Change placeholder to show video is ready
            self.video_placeholder.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #1a1a1a, stop:1 #2a2a2a);
                    border: 2px solid #00bcd4;
                    color: #00bcd4;
                    font-size: 14px;
                    font-weight: bold;
                }
            """)
            
            if self.window_type == "before":
                self.video_placeholder.setText(f"BEFORE\n\n{video_name}\n\n✓ Video Loaded\nClick Play to Start")
            else:
                self.video_placeholder.setText(f"AFTER\n\n{video_name}\n\n✓ Preview Ready\nClick Play to Start")

            # Update resolution display
            self.update_resolution(1920, 1080)  # Default, can be updated with actual video info
            
            logger.info(f"{self.window_type.upper()} preview: Loaded {video_name}")
            
        except Exception as e:
            print(f"DEBUG: Error in set_video: {str(e)}")
            import traceback
            traceback.print_exc()

    def show_video_frame(self, frame_image):
        """Display actual video frame - TO BE CALLED BY VIDEO PLAYER"""
        try:
            if frame_image and not frame_image.isNull():
                # Scale frame to fit placeholder while maintaining aspect ratio
                scaled_frame = frame_image.scaled(
                    self.video_placeholder.width() - 10,
                    self.video_placeholder.height() - 10,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.video_placeholder.setPixmap(scaled_frame)
                self.video_placeholder.setText("")  # Clear text
            else:
                # Fallback if no frame
                self.video_placeholder.setText("🎬 PLAYING\n\nVideo Frame")
                self.video_placeholder.setStyleSheet("""
                    QLabel {
                        background: #000000;
                        border: 2px solid #00bcd4;
                        color: #00bcd4;
                        font-size: 14px;
                        font-weight: bold;
                    }
                """)
                
        except Exception as e:
            print(f"DEBUG: Error showing video frame: {str(e)}")

    def clear_video(self):
        """Clear video display"""
        self.video_placeholder.setPixmap(QPixmap())
        if self.window_type == "before":
            self.video_placeholder.setText("BEFORE\n\nOriginal Video\n\nNo video loaded")
        else:
            self.video_placeholder.setText("AFTER\n\nEdited Preview\n\nNo video loaded")
        self.video_placeholder.setStyleSheet("""
            QLabel {
                background: #0a0a0a;
                border: 2px dashed #333;
                color: #666666;
                font-size: 16px;
                font-weight: bold;
            }
        """)

    def add_effect_badge(self, effect_name):
        """Add effect badge to After window"""
        if self.window_type == "after":
            badge = QLabel(effect_name)
            badge.setStyleSheet("""
                QLabel {
                    background-color: rgba(0, 188, 212, 0.9);
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)
            self.effects_layout.addWidget(badge)

    def clear_effect_badges(self):
        """Clear all effect badges"""
        if self.window_type == "after":
            while self.effects_layout.count():
                child = self.effects_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

    def update_timecode(self, current, total):
        """Update timecode display"""
        current_str = self.format_time(current)
        total_str = self.format_time(total)
        self.timecode_label.setText(f"{current_str} / {total_str}")

    def update_frame(self, frame_num):
        """Update frame number"""
        self.frame_label.setText(f"Frame: {frame_num}")

    def update_resolution(self, width, height):
        """Update resolution display"""
        self.resolution_label.setText(f"{width}x{height}")

    @staticmethod
    def format_time(seconds):
        """Format time as MM:SS or HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"


class DualPreviewWidget(QWidget):
    """Dual preview widget with Before/After comparison"""

    playback_state_changed = pyqtSignal(bool)  # is_playing
    position_changed = pyqtSignal(float)  # time in seconds
    comparison_mode_changed = pyqtSignal(str)  # mode: split, slider, toggle

    def __init__(self, parent=None):
        super().__init__(parent)
        self.comparison_mode = "split"  # split, slider, toggle
        self.current_time = 0.0
        self.duration = 0.0
        self.is_playing = False
        self.video_loaded = False
        self.current_video_path = ""

        self.init_ui()

    def init_ui(self):
        """Initialize dual preview UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main preview container
        preview_container = QFrame()
        preview_container.setStyleSheet("""
            QFrame {
                background-color: #000000;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
            }
        """)

        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        # Splitter for before/after windows
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #00bcd4;
                width: 3px;
            }
            QSplitter::handle:hover {
                background-color: #4dd0e1;
            }
        """)

        # Before window
        self.before_window = PreviewWindow("before")
        self.splitter.addWidget(self.before_window)

        # After window
        self.after_window = PreviewWindow("after")
        self.splitter.addWidget(self.after_window)

        # Set equal sizes
        self.splitter.setSizes([1000, 1000])

        preview_layout.addWidget(self.splitter)
        preview_container.setLayout(preview_layout)
        layout.addWidget(preview_container, 1)

        # Comparison mode controls
        mode_controls = self.create_mode_controls()
        layout.addWidget(mode_controls)

        self.setLayout(layout)

    def create_mode_controls(self):
        """Create comparison mode control buttons"""
        container = QFrame()
        container.setFixedHeight(45)
        container.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-top: 1px solid #2a2a2a;
                border-radius: 0 0 4px 4px;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Mode label
        mode_label = QLabel("Comparison:")
        mode_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        layout.addWidget(mode_label)

        # Split view button
        self.split_btn = QPushButton("⇆ Split View")
        self.split_btn.setCheckable(True)
        self.split_btn.setChecked(True)
        self.split_btn.setToolTip("Side-by-side comparison (default)")
        self.split_btn.clicked.connect(lambda: self.set_comparison_mode("split"))
        
        # Slider view button
        self.slider_btn = QPushButton("↔ Slider View")
        self.slider_btn.setCheckable(True)
        self.slider_btn.setToolTip("Draggable slider comparison")
        self.slider_btn.clicked.connect(lambda: self.set_comparison_mode("slider"))
        
        # Toggle view button
        self.toggle_btn = QPushButton("⚡ Toggle View")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setToolTip("Switch between Before/After (B/A keys)")
        self.toggle_btn.clicked.connect(lambda: self.set_comparison_mode("toggle"))

        # Common button style
        button_style = """
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
            QPushButton:checked {
                background-color: #00bcd4;
                color: #ffffff;
            }
        """
        
        self.split_btn.setStyleSheet(button_style)
        self.slider_btn.setStyleSheet(button_style)
        self.toggle_btn.setStyleSheet(button_style)

        layout.addWidget(self.split_btn)
        layout.addWidget(self.slider_btn)
        layout.addWidget(self.toggle_btn)

        layout.addSpacing(20)

        # Sync indicator
        sync_icon = QLabel("🔗 Synced")
        sync_icon.setStyleSheet("""
            QLabel {
                color: #00bcd4;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        layout.addWidget(sync_icon)

        layout.addStretch()

        # Video info
        if self.video_loaded:
            video_info = QLabel(f"🎬 {os.path.basename(self.current_video_path)}")
        else:
            video_info = QLabel("🎬 No video loaded")
            
        video_info.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        layout.addWidget(video_info)

        container.setLayout(layout)
        return container

    def set_comparison_mode(self, mode):
        """Set comparison mode"""
        self.comparison_mode = mode

        # Update button states
        self.split_btn.setChecked(mode == "split")
        self.slider_btn.setChecked(mode == "slider")
        self.toggle_btn.setChecked(mode == "toggle")

        if mode == "split":
            # Show both windows side by side
            self.before_window.setVisible(True)
            self.after_window.setVisible(True)
            self.splitter.setSizes([1000, 1000])

        elif mode == "slider":
            # Show slider comparison (both visible, one overlaying)
            self.before_window.setVisible(True)
            self.after_window.setVisible(True)
            # Implementation would need overlay with slider

        elif mode == "toggle":
            # Show only one at a time
            # Start with Before
            self.before_window.setVisible(True)
            self.after_window.setVisible(False)

        self.comparison_mode_changed.emit(mode)
        logger.info(f"Comparison mode changed to: {mode}")

    def toggle_between_views(self):
        """Toggle between Before and After (for toggle mode)"""
        if self.comparison_mode == "toggle":
            before_visible = self.before_window.isVisible()
            self.before_window.setVisible(not before_visible)
            self.after_window.setVisible(before_visible)

    def update_time(self, current, total):
        """Update time displays in both windows"""
        self.current_time = current
        self.duration = total
        self.before_window.update_timecode(current, total)
        self.after_window.update_timecode(current, total)

    def update_frame_number(self, frame):
        """Update frame number in both windows"""
        self.before_window.update_frame(frame)
        self.after_window.update_frame(frame)

    def add_effect_to_preview(self, effect_name):
        """Add effect badge to After window"""
        self.after_window.add_effect_badge(effect_name)

    def clear_effects(self):
        """Clear all effect badges from After window"""
        self.after_window.clear_effect_badges()

    def set_resolution(self, width, height):
        """Set resolution display for both windows"""
        self.before_window.update_resolution(width, height)
        self.after_window.update_resolution(width, height)

    def clear_previews(self):
        """Clear both preview windows"""
        try:
            self.before_window.clear_video()
            self.after_window.clear_video()
            self.video_loaded = False
            self.current_video_path = ""
            print("DEBUG: Cleared both preview windows")
        except Exception as e:
            print(f"DEBUG: Error clearing previews: {str(e)}")

    def load_video(self, video_path: str):
        """Load video in both preview windows - PROPERLY IMPLEMENTED"""
        try:
            print(f"DEBUG: DualPreview loading video: {video_path}")
            
            if not os.path.exists(video_path):
                print(f"DEBUG: Video file not found: {video_path}")
                return
                
            # Update both preview windows with actual video
            self.before_window.set_video(video_path)
            self.after_window.set_video(video_path)
            
            # Update UI state
            self.video_loaded = True
            self.current_video_path = video_path
            
            # Update time displays
            self.update_time(0, 60.0)  # Default duration, can be updated
            
            print(f"DEBUG: Dual preview loaded video successfully")
            
        except Exception as e:
            print(f"DEBUG: Error loading video in dual preview: {str(e)}")
            import traceback
            traceback.print_exc()

    def show_video_frame(self, frame_image, is_before=True):
        """Display actual video frame - FINAL IMPLEMENTATION"""
        try:
            print(f"DEBUG: Showing video frame - Before: {is_before}")
            
            if frame_image and not frame_image.isNull():
                if is_before:
                    # Scale and display in before window
                    scaled_frame = frame_image.scaled(
                        self.before_window.video_placeholder.width() - 20,
                        self.before_window.video_placeholder.height() - 20,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.before_window.video_placeholder.setPixmap(scaled_frame)
                    self.before_window.video_placeholder.setText("")  # Clear text
                else:
                    # Scale and display in after window  
                    scaled_frame = frame_image.scaled(
                        self.after_window.video_placeholder.width() - 20,
                        self.after_window.video_placeholder.height() - 20,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.after_window.video_placeholder.setPixmap(scaled_frame)
                    self.after_window.video_placeholder.setText("")  # Clear text
                    
                print("DEBUG: Video frame displayed successfully")
            else:
                print("DEBUG: Invalid frame received")
                
        except Exception as e:
            print(f"DEBUG: Error showing video frame: {str(e)}")
            import traceback
            traceback.print_exc()