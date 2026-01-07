"""
modules/metadata_remover/metadata_stealth_mode_dialog.py
Stealth Mode Selector Dialog - Choose processing mode
Displays 3 stealth modes with device-based recommendations
"""

import psutil
import platform
from enum import Enum

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QRadioButton, QButtonGroup, QGroupBox, QProgressBar
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class StealthMode(Enum):
    """Stealth processing modes"""
    QUICK = "quick"
    DEEP = "deep"
    MAXIMUM = "maximum"


class DeviceCapability:
    """Device capability checker"""

    @staticmethod
    def check_device_specs():
        """Check device specifications"""
        try:
            # CPU info
            cpu_count = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            cpu_speed = cpu_freq.current if cpu_freq else 0

            # RAM info
            ram = psutil.virtual_memory()
            ram_gb = ram.total / (1024 ** 3)

            # Estimate device tier
            if cpu_count >= 8 and ram_gb >= 16 and cpu_speed >= 2500:
                tier = "high"
                recommended_mode = StealthMode.MAXIMUM
            elif cpu_count >= 4 and ram_gb >= 8 and cpu_speed >= 2000:
                tier = "medium"
                recommended_mode = StealthMode.DEEP
            else:
                tier = "low"
                recommended_mode = StealthMode.QUICK

            return {
                'cpu_cores': cpu_count,
                'cpu_speed_mhz': cpu_speed,
                'ram_gb': round(ram_gb, 1),
                'ram_available_gb': round(ram.available / (1024 ** 3), 1),
                'os': platform.system(),
                'tier': tier,
                'recommended_mode': recommended_mode
            }

        except Exception as e:
            logger.error(f"Failed to check device specs: {e}")
            return {
                'cpu_cores': 4,
                'cpu_speed_mhz': 2000,
                'ram_gb': 8,
                'ram_available_gb': 4,
                'os': platform.system(),
                'tier': 'medium',
                'recommended_mode': StealthMode.QUICK
            }


class MetadataStealthModeDialog(QDialog):
    """
    Stealth Mode Selector Dialog
    Allows user to choose processing mode based on device capabilities
    """

    def __init__(self, video_count: int, parent=None):
        super().__init__(parent)
        self.video_count = video_count
        self.selected_mode = StealthMode.QUICK  # Default
        self.device_specs = DeviceCapability.check_device_specs()

        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Choose Stealth Mode")
        self.setMinimumSize(950, 800)
        self.resize(1000, 850)
        self.setModal(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Header
        header = self.create_header()
        main_layout.addWidget(header)

        # Device specs display
        device_group = self.create_device_specs_group()
        main_layout.addWidget(device_group)

        # Stealth modes
        modes_group = self.create_modes_group()
        main_layout.addWidget(modes_group)

        # Estimated time
        time_group = self.create_time_estimate_group()
        main_layout.addWidget(time_group)

        main_layout.addStretch()

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.confirm_btn = QPushButton("Start Processing")
        self.confirm_btn.setObjectName("confirm_btn")
        self.confirm_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.confirm_btn)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def create_header(self) -> QFrame:
        """Create header"""
        header = QFrame()
        header.setObjectName("header")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("🎯 Choose Stealth Processing Mode")
        title.setFont(QFont('Segoe UI', 18, QFont.Bold))
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel(
            f"Processing {self.video_count} video{'s' if self.video_count > 1 else ''} - "
            f"Select your preferred balance between speed and undetectability"
        )
        subtitle.setFont(QFont('Segoe UI', 11))
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        return header

    def create_device_specs_group(self) -> QGroupBox:
        """Create device specs display"""
        group = QGroupBox("💻 Your Device Capabilities")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        specs = self.device_specs

        # Device info
        specs_html = (
            f"<b>CPU:</b> {specs['cpu_cores']} cores @ {specs['cpu_speed_mhz']:.0f} MHz<br>"
            f"<b>RAM:</b> {specs['ram_gb']} GB total ({specs['ram_available_gb']} GB available)<br>"
            f"<b>OS:</b> {specs['os']}"
        )
        specs_label = QLabel(specs_html)
        specs_label.setFont(QFont('Segoe UI', 11))
        layout.addWidget(specs_label)

        # Device tier indicator
        tier_labels = {
            'low': ('🟡 Basic', '#ff9800'),
            'medium': ('🟢 Good', '#4caf50'),
            'high': ('🔥 Excellent', '#9c27b0')
        }

        tier_text, tier_color = tier_labels.get(specs['tier'], ('Unknown', '#888888'))

        tier_label = QLabel(f"<b>Performance Tier:</b> {tier_text}")
        tier_label.setFont(QFont('Segoe UI', 12, QFont.Bold))
        tier_label.setStyleSheet(f"color: {tier_color}; padding: 10px; background-color: #2a2a2a; border-radius: 6px;")
        layout.addWidget(tier_label)

        # Recommendation
        recommended_mode_name = specs['recommended_mode'].value.title()
        recommendation = QLabel(
            f"💡 <b>Recommended:</b> {recommended_mode_name} Stealth mode for your device"
        )
        recommendation.setFont(QFont('Segoe UI', 10))
        recommendation.setWordWrap(True)
        recommendation.setStyleSheet("color: #4caf50; font-style: italic;")
        layout.addWidget(recommendation)

        group.setLayout(layout)
        return group

    def create_modes_group(self) -> QGroupBox:
        """Create stealth modes selection"""
        group = QGroupBox("⚡ Select Stealth Mode")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Button group for radio buttons
        self.mode_button_group = QButtonGroup(self)

        # Quick Stealth
        quick_frame = self.create_mode_card(
            title="⚡ Quick Stealth",
            speed="5-10 minutes per video",
            effectiveness="70% undetectable",
            processing=[
                "Metadata removal",
                "Edge blur effect",
                "Professional audio processing",
                "Re-encoding with different parameters"
            ],
            best_for="Fast processing, moderate PC specs",
            mode=StealthMode.QUICK,
            recommended=(self.device_specs['recommended_mode'] == StealthMode.QUICK)
        )
        layout.addWidget(quick_frame)

        # Deep Stealth
        deep_frame = self.create_mode_card(
            title="🔥 Deep Stealth",
            speed="20-30 minutes per video",
            effectiveness="90% undetectable",
            processing=[
                "Everything in Quick mode +",
                "Frame interpolation",
                "Advanced color grading",
                "Pixel-level noise injection",
                "Multi-pass encoding"
            ],
            best_for="High stealth needed, good PC specs",
            mode=StealthMode.DEEP,
            recommended=(self.device_specs['recommended_mode'] == StealthMode.DEEP)
        )
        layout.addWidget(deep_frame)

        # Maximum Stealth
        maximum_frame = self.create_mode_card(
            title="🚀 Maximum Stealth",
            speed="1-2 hours per video",
            effectiveness="99% undetectable",
            processing=[
                "Everything in Deep mode +",
                "Scene segmentation",
                "Perceptual hash targeting",
                "Temporal manipulation",
                "Complete reconstruction"
            ],
            best_for="Maximum stealth, powerful PC, overnight processing",
            mode=StealthMode.MAXIMUM,
            recommended=(self.device_specs['recommended_mode'] == StealthMode.MAXIMUM)
        )
        layout.addWidget(maximum_frame)

        # Select recommended mode by default
        for button in self.mode_button_group.buttons():
            if button.property("mode") == self.device_specs['recommended_mode']:
                button.setChecked(True)
                self.selected_mode = self.device_specs['recommended_mode']
                break

        # Connect signal
        self.mode_button_group.buttonClicked.connect(self.on_mode_selected)

        group.setLayout(layout)
        return group

    def create_mode_card(self, title: str, speed: str, effectiveness: str,
                        processing: list, best_for: str, mode: StealthMode,
                        recommended: bool = False) -> QFrame:
        """Create mode selection card"""
        frame = QFrame()
        frame.setObjectName("mode_card")
        frame.setMinimumWidth(900)
        frame.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header with radio button
        header_layout = QHBoxLayout()

        radio = QRadioButton(title)
        radio.setFont(QFont('Segoe UI', 13, QFont.Bold))
        radio.setProperty("mode", mode)
        radio.setCursor(Qt.PointingHandCursor)
        self.mode_button_group.addButton(radio)
        header_layout.addWidget(radio)

        # Make entire frame clickable
        frame.mousePressEvent = lambda event: radio.setChecked(True)

        if recommended:
            rec_label = QLabel("✨ RECOMMENDED")
            rec_label.setFont(QFont('Segoe UI', 9, QFont.Bold))
            rec_label.setStyleSheet("color: #4caf50;")
            header_layout.addWidget(rec_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Stats
        stats_html = (
            f"<b>⏱️  Speed:</b> {speed}<br>"
            f"<b>🎯 Effectiveness:</b> {effectiveness}"
        )
        stats_label = QLabel(stats_html)
        stats_label.setFont(QFont('Segoe UI', 10))
        stats_label.setStyleSheet("color: #b0b0b0; margin-left: 25px;")
        stats_label.setWordWrap(True)
        layout.addWidget(stats_label)

        # Processing details
        processing_text = "<b>🔧 Processing:</b><br>" + "<br>".join([f"  • {p}" for p in processing])
        processing_label = QLabel(processing_text)
        processing_label.setFont(QFont('Segoe UI', 9))
        processing_label.setStyleSheet("color: #a0a0a0; margin-left: 25px;")
        processing_label.setWordWrap(True)
        processing_label.setMaximumWidth(850)
        layout.addWidget(processing_label)

        # Best for
        best_label = QLabel(f"<b>✅ Best for:</b> {best_for}")
        best_label.setFont(QFont('Segoe UI', 9))
        best_label.setStyleSheet("color: #888888; margin-left: 25px; font-style: italic;")
        best_label.setWordWrap(True)
        best_label.setMaximumWidth(850)
        layout.addWidget(best_label)

        return frame

    def create_time_estimate_group(self) -> QGroupBox:
        """Create time estimate display"""
        group = QGroupBox("📊 Estimated Processing Time")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Calculate estimates
        estimates = {
            StealthMode.QUICK: (5, 10),  # min, max minutes per video
            StealthMode.DEEP: (20, 30),
            StealthMode.MAXIMUM: (60, 120)
        }

        for mode, (min_time, max_time) in estimates.items():
            mode_layout = QHBoxLayout()

            # Mode name
            mode_name = mode.value.title() + " Stealth:"
            name_label = QLabel(mode_name)
            name_label.setFont(QFont('Segoe UI', 10, QFont.Bold))
            name_label.setFixedWidth(150)
            mode_layout.addWidget(name_label)

            # Time estimate
            total_min = min_time * self.video_count
            total_max = max_time * self.video_count

            if total_min < 60:
                time_str = f"{total_min}-{total_max} minutes"
            else:
                hours_min = total_min / 60
                hours_max = total_max / 60
                time_str = f"{hours_min:.1f}-{hours_max:.1f} hours"

            time_label = QLabel(time_str)
            time_label.setFont(QFont('Segoe UI', 10))
            time_label.setStyleSheet("color: #9c27b0;")
            mode_layout.addWidget(time_label)

            mode_layout.addStretch()
            layout.addLayout(mode_layout)

        # Note
        note = QLabel(
            "<i>⚠️  Note: Actual time may vary based on video resolution, length, and system performance.</i>"
        )
        note.setFont(QFont('Segoe UI', 9))
        note.setWordWrap(True)
        note.setStyleSheet("color: #888888;")
        layout.addWidget(note)

        group.setLayout(layout)
        return group

    def on_mode_selected(self, button):
        """Handle mode selection"""
        self.selected_mode = button.property("mode")
        logger.info(f"Selected stealth mode: {self.selected_mode.value}")

    def get_selected_mode(self) -> StealthMode:
        """Get selected stealth mode"""
        return self.selected_mode

    def apply_theme(self):
        """Apply dark theme"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #e0e0e0;
            }
            QFrame#header {
                background-color: #242424;
                border-radius: 10px;
            }
            QLabel#title {
                color: #9c27b0;
            }
            QLabel#subtitle {
                color: #b0b0b0;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
                background-color: #242424;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                color: #9c27b0;
            }
            QFrame#mode_card {
                background-color: #2a2a2a;
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                padding: 15px;
                min-height: 180px;
            }
            QFrame#mode_card:hover {
                border-color: #9c27b0;
                background-color: #2f2f2f;
            }
            QRadioButton {
                color: #e0e0e0;
                spacing: 10px;
                padding: 5px;
            }
            QRadioButton:hover {
                color: #ffffff;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border-radius: 10px;
            }
            QRadioButton::indicator:checked {
                background-color: #9c27b0;
                border: 3px solid #9c27b0;
            }
            QRadioButton::indicator:unchecked {
                background-color: #2a2a2a;
                border: 3px solid #666666;
            }
            QRadioButton::indicator:unchecked:hover {
                border-color: #9c27b0;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353535;
            }
            QPushButton:pressed {
                background-color: #202020;
            }
            QPushButton#confirm_btn {
                background-color: #9c27b0;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#confirm_btn:hover {
                background-color: #ab47bc;
            }
            QPushButton#confirm_btn:pressed {
                background-color: #7b1fa2;
            }
        """)
