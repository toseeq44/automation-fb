"""
modules/video_editor/dual_control_panel.py
Dual Independent Control Panels for Before/After Windows
"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, 
                             QSlider, QLabel, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class SingleControlPanel(QFrame):
    """Single control panel for one preview window"""
    
    # Signals
    play_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    skip_backward_clicked = pyqtSignal()
    skip_forward_clicked = pyqtSignal()
    scrubber_moved = pyqtSignal(int)  # position 0-1000
    volume_changed = pyqtSignal(int)  # volume 0-100
    fullscreen_toggled = pyqtSignal()
    
    def __init__(self, panel_name="Control", parent=None):
        super().__init__(parent)
        self.panel_name = panel_name
        self.is_playing = False
        self.current_position = 0
        self.total_duration = 0
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the control panel UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        
        # Panel header
        header = QLabel(f"🎮 {self.panel_name}")
        header.setStyleSheet("""
            QLabel {
                color: #00bcd4;
                font-size: 14px;
                font-weight: bold;
                padding: 4px;
                background: #1a1a1a;
                border-radius: 4px;
                text-align: center;
            }
        """)
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Main controls layout
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(12)
        
        # Control buttons (minimal design: single play/pause toggle)
        self.skip_backward_btn = None
        self.stop_btn = None
        self.skip_forward_btn = None
        self.play_btn = self.create_control_button("▶", "Play / Pause", "#00bcd4", role="play")
        
        # Time display
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                padding: 6px 10px;
                background: #252525;
                border-radius: 4px;
                min-width: 100px;
            }
        """)
        self.time_label.setAlignment(Qt.AlignCenter)
        
        # Add to layout
        controls_layout.addWidget(self.play_btn)
        controls_layout.addSpacing(12)
        controls_layout.addWidget(self.time_label)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Progress slider
        slider_layout = QHBoxLayout()
        
        self.scrubber = QSlider(Qt.Horizontal)
        self.scrubber.setRange(0, 1000)
        self.scrubber.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #333333;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #00bcd4;
                width: 12px;
                height: 12px;
                border-radius: 6px;
                margin: -4px 0;
            }
            QSlider::sub-page:horizontal {
                background: #00bcd4;
                border-radius: 2px;
            }
        """)
        self.scrubber.sliderMoved.connect(self.on_scrubber_moved)
        
        slider_layout.addWidget(self.scrubber)
        layout.addLayout(slider_layout)
        
        self.setLayout(layout)
        self.setStyleSheet("""
            SingleControlPanel {
                background: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
                margin: 2px;
            }
        """)

        # Connect button handlers after UI is ready
        self._bind_button_handlers()
        
    def create_control_button(self, icon, tooltip, color, role):
        """Create a styled control button"""
        btn = QPushButton(icon)
        btn.setToolTip(tooltip)
        btn.setFixedSize(36, 36)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 18px;
                font-size: 14px;
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
        
        # Store role on button for handler lookup
        btn._control_role = role  # type: ignore[attr-defined]
        return btn
        
    def _bind_button_handlers(self):
        """Attach button click handlers that emit high-level signals."""
        if self.play_btn is not None:
            self.play_btn.clicked.connect(self._handle_play_clicked)
        if self.stop_btn is not None:
            self.stop_btn.clicked.connect(self._handle_stop_clicked)
        if self.skip_backward_btn is not None:
            self.skip_backward_btn.clicked.connect(self._handle_skip_backward_clicked)
        if self.skip_forward_btn is not None:
            self.skip_forward_btn.clicked.connect(self._handle_skip_forward_clicked)

    def _handle_skip_backward_clicked(self):
        print(f"DEBUG: {self.panel_name} skip backward button clicked")
        self.skip_backward_clicked.emit()

    def _handle_play_clicked(self):
        print(f"DEBUG: {self.panel_name} play button clicked (is_playing={self.is_playing})")
        if self.is_playing:
            self.set_paused_state(update_ui_only=True)
            self.pause_clicked.emit()
        else:
            self.set_playing_state(update_ui_only=True)
            self.play_clicked.emit()

    def _handle_stop_clicked(self):
        print(f"DEBUG: {self.panel_name} stop triggered")
        self.set_stopped_state(update_ui_only=True)
        self.stop_clicked.emit()

    def _handle_skip_forward_clicked(self):
        print(f"DEBUG: {self.panel_name} skip forward triggered")
        self.skip_forward_clicked.emit()

    def lighten_color(self, color):
        """Lighten color for hover effect"""
        return color  # Simple implementation
        
    def darken_color(self, color):
        """Darken color for pressed effect"""
        return color  # Simple implementation
        
    def on_scrubber_moved(self, position):
        """Handle scrubber movement"""
        self.scrubber_moved.emit(position)
        
    def set_position(self, position):
        """Set current position (0-1000)"""
        self.current_position = position
        self.scrubber.setValue(position)
        
    def set_duration(self, duration_seconds):
        """Set total duration"""
        self.total_duration = duration_seconds
        self.update_time_display()
        
    def update_time_display(self):
        """Update time display"""
        current_time = self.format_time((self.current_position / 1000.0) * self.total_duration)
        total_time = self.format_time(self.total_duration)
        self.time_label.setText(f"{current_time} / {total_time}")
        
    def format_time(self, seconds):
        """Format seconds to MM:SS or HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
            
    def set_playing_state(self, update_ui_only=False):
        """Set playing state without emitting signals"""
        self.is_playing = True
        if self.play_btn:
            self.play_btn.setText("⏸")
        
    def set_paused_state(self, update_ui_only=False):
        """Set paused state without emitting signals"""
        self.is_playing = False
        if self.play_btn:
            self.play_btn.setText("▶")
        
    def set_stopped_state(self, update_ui_only=False):
        """Set stopped state without emitting signals"""
        self.is_playing = False
        if self.play_btn:
            self.play_btn.setText("▶")
        self.set_position(0)


class DualControlPanel(QWidget):
    """Dual control panel container for both preview windows"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.before_controls = SingleControlPanel("BEFORE Controls")
        self.after_controls = SingleControlPanel("AFTER Controls")
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize dual control panel UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Add both control panels
        layout.addWidget(self.before_controls)
        layout.addWidget(self.after_controls)
        
        self.setLayout(layout)
