"""
modules/video_editor/unified_control_panel.py
Unified Control Panel - Playback controls below preview windows
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class UnifiedControlPanel(QWidget):
    """Unified control panel with playback controls and timeline scrubber"""

    # Signals
    play_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    skip_backward_clicked = pyqtSignal()
    skip_forward_clicked = pyqtSignal()
    scrubber_moved = pyqtSignal(int)  # Position 0-1000
    volume_changed = pyqtSignal(int)  # Volume 0-100
    fullscreen_toggled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_playing = False
        self.current_position = 0
        self.duration = 0

        self.init_ui()

    def init_ui(self):
        """Initialize control panel UI"""
        # Main container
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-top: 1px solid #2a2a2a;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(10)

        # Control row (buttons + scrubber + volume)
        control_row = QHBoxLayout()
        control_row.setSpacing(10)

        # Playback buttons
        button_style = """
            QPushButton {
                background-color: %s;
                color: white;
                border: none;
                border-radius: 18px;
                font-size: 16px;
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                max-height: 36px;
            }
            QPushButton:hover {
                background-color: %s;
            }
            QPushButton:pressed {
                background-color: %s;
            }
        """

        # Skip backward
        self.skip_back_btn = QPushButton("⏮")
        self.skip_back_btn.setStyleSheet(button_style % ("#e91e63", "#f06292", "#c2185b"))
        self.skip_back_btn.setToolTip("Skip Backward 5s")
        self.skip_back_btn.clicked.connect(self.skip_backward_clicked.emit)
        control_row.addWidget(self.skip_back_btn)

        # Play/Pause button
        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setStyleSheet(button_style % ("#00bcd4", "#4dd0e1", "#0097a7"))
        self.play_pause_btn.setToolTip("Play/Pause (Space)")
        self.play_pause_btn.clicked.connect(self.on_play_pause_clicked)
        control_row.addWidget(self.play_pause_btn)

        # Skip forward
        self.skip_forward_btn = QPushButton("⏭")
        self.skip_forward_btn.setStyleSheet(button_style % ("#e91e63", "#f06292", "#c2185b"))
        self.skip_forward_btn.setToolTip("Skip Forward 5s")
        self.skip_forward_btn.clicked.connect(self.skip_forward_clicked.emit)
        control_row.addWidget(self.skip_forward_btn)

        # Stop button
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setStyleSheet(button_style % ("#f44336", "#e57373", "#d32f2f"))
        self.stop_btn.setToolTip("Stop Playback")
        self.stop_btn.clicked.connect(self.on_stop_clicked)
        control_row.addWidget(self.stop_btn)

        control_row.addSpacing(15)

        # Timeline scrubber
        scrubber_container = QVBoxLayout()
        scrubber_container.setSpacing(4)

        # Time labels
        time_row = QHBoxLayout()
        time_row.setSpacing(0)

        self.current_time_label = QLabel("00:00")
        self.current_time_label.setStyleSheet("""
            QLabel {
                color: #00bcd4;
                font-size: 12px;
                font-family: 'Courier New', monospace;
                font-weight: bold;
            }
        """)
        time_row.addWidget(self.current_time_label)

        time_row.addStretch()

        self.total_time_label = QLabel("00:00")
        self.total_time_label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
                font-family: 'Courier New', monospace;
            }
        """)
        time_row.addWidget(self.total_time_label)

        scrubber_container.addLayout(time_row)

        # Scrubber slider
        self.scrubber = QSlider(Qt.Horizontal)
        self.scrubber.setMinimum(0)
        self.scrubber.setMaximum(1000)
        self.scrubber.setValue(0)
        self.scrubber.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #2a2a2a;
                height: 8px;
                border-radius: 4px;
                border: 1px solid #404040;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00bcd4, stop:1 #4dd0e1);
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #00bcd4;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #00bcd4;
                width: 18px;
                height: 18px;
                margin: -6px 0;
            }
        """)
        self.scrubber.sliderMoved.connect(self.on_scrubber_moved)
        self.scrubber.sliderPressed.connect(lambda: logger.debug("Scrubber pressed"))
        self.scrubber.sliderReleased.connect(lambda: logger.debug("Scrubber released"))
        scrubber_container.addWidget(self.scrubber)

        control_row.addLayout(scrubber_container, 1)

        control_row.addSpacing(15)

        # Volume control
        volume_btn = QPushButton("🔊")
        volume_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 20px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border-radius: 6px;
            }
        """)
        volume_btn.setToolTip("Volume")
        control_row.addWidget(volume_btn)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #2a2a2a;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #00bcd4;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #00bcd4;
                width: 12px;
                height: 12px;
                margin: -3px 0;
                border-radius: 6px;
            }
        """)
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        control_row.addWidget(self.volume_slider)

        control_row.addSpacing(10)

        # Fullscreen button
        fullscreen_btn = QPushButton("⛶")
        fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                font-size: 18px;
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                max-height: 36px;
            }
            QPushButton:hover {
                background-color: #00bcd4;
                color: white;
            }
        """)
        fullscreen_btn.setToolTip("Fullscreen (F)")
        fullscreen_btn.clicked.connect(self.fullscreen_toggled.emit)
        control_row.addWidget(fullscreen_btn)

        layout.addLayout(control_row)

        container.setLayout(layout)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(container)

        self.setLayout(main_layout)
        self.setFixedHeight(70)

    def on_play_pause_clicked(self):
        """Handle play/pause button click"""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        """Set to playing state"""
        self.is_playing = True
        self.play_pause_btn.setText("⏸")
        self.play_pause_btn.setToolTip("Pause (Space)")
        self.play_clicked.emit()
        logger.debug("Play clicked")

    def pause(self):
        """Set to paused state"""
        self.is_playing = False
        self.play_pause_btn.setText("▶")
        self.play_pause_btn.setToolTip("Play (Space)")
        self.pause_clicked.emit()
        logger.debug("Pause clicked")

    def on_stop_clicked(self):
        """Handle stop button click"""
        self.is_playing = False
        self.play_pause_btn.setText("▶")
        self.play_pause_btn.setToolTip("Play (Space)")
        self.scrubber.setValue(0)
        self.current_time_label.setText("00:00")
        self.stop_clicked.emit()
        logger.debug("Stop clicked")

    def on_scrubber_moved(self, position):
        """Handle scrubber movement"""
        # Calculate time from position
        if self.duration > 0:
            time_seconds = (position / 1000.0) * self.duration
            self.update_current_time(time_seconds)

        self.scrubber_moved.emit(position)

    def set_duration(self, seconds):
        """Set total duration"""
        self.duration = seconds
        self.total_time_label.setText(self.format_time(seconds))

    def update_current_time(self, seconds):
        """Update current time display"""
        self.current_time_label.setText(self.format_time(seconds))
        self.current_position = seconds

    def set_position(self, seconds):
        """Set scrubber position from time"""
        self.update_current_time(seconds)
        if self.duration > 0:
            position = int((seconds / self.duration) * 1000)
            self.scrubber.blockSignals(True)  # Prevent signal loop
            self.scrubber.setValue(position)
            self.scrubber.blockSignals(False)

    def format_time(self, seconds):
        """Format seconds as MM:SS or HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def set_volume(self, volume):
        """Set volume (0-100)"""
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(volume)
        self.volume_slider.blockSignals(False)

    def get_volume(self):
        """Get current volume (0-100)"""
        return self.volume_slider.value()

    def reset(self):
        """Reset control panel to initial state"""
        self.is_playing = False
        self.play_pause_btn.setText("▶")
        self.scrubber.setValue(0)
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
        self.duration = 0
        self.current_position = 0
