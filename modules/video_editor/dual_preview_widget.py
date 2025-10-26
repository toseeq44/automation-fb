"""
modules/video_editor/dual_preview_widget.py
Dual Preview Window System - Before/After Comparison
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QSlider, QComboBox, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor

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

        title = QLabel(title_text)
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {title_color};
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
        """)
        header_layout.addWidget(title)

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

        # Preview canvas
        self.canvas = QFrame()
        self.canvas.setMinimumSize(400, 300)
        self.canvas.setStyleSheet("""
            QFrame {
                background-color: #000000;
                border: none;
            }
        """)

        canvas_layout = QVBoxLayout()
        canvas_layout.setAlignment(Qt.AlignCenter)

        # Placeholder
        self.placeholder = QLabel()
        self.placeholder.setAlignment(Qt.AlignCenter)

        if self.window_type == "before":
            self.placeholder.setText("📹\n\nORIGINAL VIDEO\n\nNo video loaded")
        else:
            self.placeholder.setText("✨\n\nPREVIEW WITH EFFECTS\n\nNo video loaded")

        self.placeholder.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 16px;
                line-height: 1.5;
            }
        """)
        canvas_layout.addWidget(self.placeholder)

        # Overlay elements
        overlay_container = QFrame()
        overlay_container.setStyleSheet("background: transparent;")
        overlay_layout = QVBoxLayout()
        overlay_layout.setContentsMargins(10, 10, 10, 10)

        # Time code (top row)
        top_row = QHBoxLayout()

        # Frame number (top-left)
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
        top_row.addWidget(self.frame_label, 0, Qt.AlignLeft | Qt.AlignTop)

        top_row.addStretch()

        # Resolution (top-right)
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
        top_row.addWidget(self.resolution_label, 0, Qt.AlignRight | Qt.AlignTop)

        overlay_layout.addLayout(top_row)

        # Effect badges (for After window)
        if self.window_type == "after":
            self.effects_container = QFrame()
            effects_layout = QHBoxLayout()
            effects_layout.setSpacing(4)
            effects_layout.setContentsMargins(0, 0, 0, 0)

            # Example effect badges
            # These will be dynamically added based on active effects
            self.effects_layout = effects_layout

            self.effects_container.setLayout(effects_layout)
            overlay_layout.addWidget(self.effects_container, 0, Qt.AlignLeft | Qt.AlignTop)

        overlay_layout.addStretch()

        # Time code (bottom-left)
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
        overlay_layout.addWidget(self.timecode_label, 0, Qt.AlignLeft | Qt.AlignBottom)

        overlay_container.setLayout(overlay_layout)
        canvas_layout.addWidget(overlay_container)

        self.canvas.setLayout(canvas_layout)
        layout.addWidget(self.canvas, 1)

        self.setLayout(layout)

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

    def set_video(self, video_path):
        """Set video for this preview window"""
        import os
        video_name = os.path.basename(video_path)
        if self.window_type == "before":
            self.placeholder.setText(f"📹\n\nORIGINAL VIDEO\n\n{video_name}\n\nReady to play")
        else:
            self.placeholder.setText(f"✨\n\nPREVIEW WITH EFFECTS\n\n{video_name}\n\nReady to play")
        self.placeholder.setStyleSheet("""
            QLabel {
                color: #00bcd4;
                font-size: 14px;
                line-height: 1.8;
                font-weight: 500;
            }
        """)
        logger.info(f"{self.window_type.upper()} preview: Loaded {video_name}")

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
        split_btn = QPushButton("⇆ Split View")
        split_btn.setCheckable(True)
        split_btn.setChecked(True)
        split_btn.setToolTip("Side-by-side comparison (default)")
        split_btn.clicked.connect(lambda: self.set_comparison_mode("split"))
        split_btn.setStyleSheet("""
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
        """)
        self.split_btn = split_btn
        layout.addWidget(split_btn)

        # Slider view button
        slider_btn = QPushButton("↔ Slider View")
        slider_btn.setCheckable(True)
        slider_btn.setToolTip("Draggable slider comparison")
        slider_btn.clicked.connect(lambda: self.set_comparison_mode("slider"))
        slider_btn.setStyleSheet(split_btn.styleSheet())
        self.slider_btn = slider_btn
        layout.addWidget(slider_btn)

        # Toggle view button
        toggle_btn = QPushButton("⚡ Toggle View")
        toggle_btn.setCheckable(True)
        toggle_btn.setToolTip("Switch between Before/After (B/A keys)")
        toggle_btn.clicked.connect(lambda: self.set_comparison_mode("toggle"))
        toggle_btn.setStyleSheet(split_btn.styleSheet())
        self.toggle_btn = toggle_btn
        layout.addWidget(toggle_btn)

        layout.addSpacing(20)

        # Zoom controls
        zoom_label = QLabel("Zoom:")
        zoom_label.setStyleSheet(mode_label.styleSheet())
        layout.addWidget(zoom_label)

        zoom_out_btn = QPushButton("➖")
        zoom_out_btn.setFixedSize(30, 30)
        zoom_out_btn.setToolTip("Zoom out")
        zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
        """)
        layout.addWidget(zoom_out_btn)

        zoom_combo = QComboBox()
        zoom_combo.addItems(["25%", "50%", "100%", "150%", "200%", "Fit"])
        zoom_combo.setCurrentText("100%")
        zoom_combo.setStyleSheet("""
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 6px 10px;
                color: #e0e0e0;
                font-size: 11px;
                min-width: 70px;
            }
            QComboBox:hover {
                border-color: #00bcd4;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #00bcd4;
                selection-background-color: #00bcd4;
            }
        """)
        layout.addWidget(zoom_combo)

        zoom_in_btn = QPushButton("➕")
        zoom_in_btn.setFixedSize(30, 30)
        zoom_in_btn.setToolTip("Zoom in")
        zoom_in_btn.setStyleSheet(zoom_out_btn.styleSheet())
        layout.addWidget(zoom_in_btn)

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

        # Quality selector (for After window)
        quality_label = QLabel("Preview Quality:")
        quality_label.setStyleSheet(mode_label.styleSheet())
        layout.addWidget(quality_label)

        quality_combo = QComboBox()
        quality_combo.addItems(["Draft", "Standard", "Full"])
        quality_combo.setCurrentText("Standard")
        quality_combo.setStyleSheet(zoom_combo.styleSheet())
        quality_combo.setToolTip("Preview quality for After window")
        layout.addWidget(quality_combo)

        # Fullscreen button
        fullscreen_btn = QPushButton("⛶")
        fullscreen_btn.setFixedSize(32, 32)
        fullscreen_btn.setToolTip("Fullscreen (F)")
        fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #00bcd4;
                color: white;
            }
        """)
        layout.addWidget(fullscreen_btn)

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

    def load_video(self, video_path):
        """Load video into both preview windows"""
        self.before_window.set_video(video_path)
        self.after_window.set_video(video_path)
        logger.info(f"Dual preview: Loaded video {video_path}")
