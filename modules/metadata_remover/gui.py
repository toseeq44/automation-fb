"""
modules/metadata_remover/gui.py
Metadata Remover Module - Main GUI Page
Provides bulk metadata removal with folder mapping support
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class MetadataRemoverPage(QWidget):
    """Main page for Metadata Remover module"""

    def __init__(self, back_callback=None):
        super().__init__()
        self.back_callback = back_callback
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Apply theme
        self.apply_theme()

        # Header
        header = self.create_header()
        main_layout.addWidget(header)

        # Info section (What is Metadata?)
        info_group = self.create_info_section()
        main_layout.addWidget(info_group)

        # Stealth Modes section (3 processing options)
        stealth_modes_group = self.create_stealth_modes_section()
        main_layout.addWidget(stealth_modes_group)

        # Features section
        features_group = self.create_features_section()
        main_layout.addWidget(features_group)

        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.setSpacing(15)

        # Bulk Processing button
        self.bulk_btn = QPushButton("🚀 Start Bulk Processing")
        self.bulk_btn.setObjectName("primary_btn")
        self.bulk_btn.setMinimumHeight(50)
        self.bulk_btn.setFont(QFont('Segoe UI', 14, QFont.Bold))
        self.bulk_btn.setToolTip("Remove metadata and make videos undetectable")
        self.bulk_btn.clicked.connect(self.open_bulk_processing)
        action_layout.addWidget(self.bulk_btn)

        main_layout.addLayout(action_layout)

        main_layout.addStretch()

        # Bottom section with back button
        bottom_layout = QHBoxLayout()

        back_btn = QPushButton("⬅ Back to Menu")
        back_btn.setObjectName("back_btn")
        back_btn.clicked.connect(self.go_back)
        bottom_layout.addWidget(back_btn)

        bottom_layout.addStretch()

        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

    def create_header(self) -> QFrame:
        """Create header section"""
        header = QFrame()
        header.setObjectName("header")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("🔒 Metadata Remover")
        title.setFont(QFont('Segoe UI', 24, QFont.Bold))
        title.setObjectName("title")
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Remove metadata from videos to protect your privacy")
        subtitle.setFont(QFont('Segoe UI', 12))
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        return header

    def create_info_section(self) -> QGroupBox:
        """Create info section with detailed metadata explanation"""
        group = QGroupBox("🔍 What is Metadata & Why Remove It?")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Main explanation
        info_text = QLabel(
            "<b>Video metadata contains hidden tracking information that can expose your identity:</b>"
        )
        info_text.setWordWrap(True)
        info_text.setFont(QFont('Segoe UI', 11))
        layout.addWidget(info_text)

        # Metadata types with detailed explanations
        metadata_details = QLabel(
            "• 📷 <b>Camera/Device Info:</b> Make, model, serial number, unique device ID<br>"
            "• 📅 <b>Timestamps:</b> Exact date/time of recording, editing sessions<br>"
            "• 📍 <b>GPS Location:</b> Your exact coordinates when video was recorded<br>"
            "• 🖥️ <b>Software Data:</b> Editing tools used, version numbers, system info<br>"
            "• 👤 <b>Creator Info:</b> Author name, copyright data, organization<br>"
            "• 🌐 <b>Network Data:</b> IP address, internet connection details<br>"
            "• 🎬 <b>Technical Specs:</b> Codec, bitrate, resolution, frame rate settings"
        )
        metadata_details.setWordWrap(True)
        metadata_details.setFont(QFont('Segoe UI', 10))
        metadata_details.setStyleSheet("color: #b0b0b0; margin-left: 10px;")
        layout.addWidget(metadata_details)

        # Privacy warning
        warning_text = QLabel(
            "<br><b>⚠️ Privacy Risk:</b> Platforms use this data to track and identify videos, "
            "even after editing. Our tool removes ALL metadata and applies advanced stealth "
            "techniques to make videos undetectable."
        )
        warning_text.setWordWrap(True)
        warning_text.setFont(QFont('Segoe UI', 10))
        warning_text.setStyleSheet("color: #ff9800; background-color: #2a2a2a; padding: 10px; border-radius: 5px;")
        layout.addWidget(warning_text)

        group.setLayout(layout)
        return group

    def create_stealth_modes_section(self) -> QGroupBox:
        """Create stealth modes overview section"""
        group = QGroupBox("🎯 3 Stealth Processing Modes")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Introduction
        intro = QLabel(
            "Choose your preferred balance between processing speed and undetectability:"
        )
        intro.setWordWrap(True)
        intro.setFont(QFont('Segoe UI', 10))
        intro.setStyleSheet("color: #b0b0b0;")
        layout.addWidget(intro)

        # Mode 1: Quick Stealth
        mode1_frame = QFrame()
        mode1_frame.setObjectName("stealth_mode_card")
        mode1_layout = QVBoxLayout(mode1_frame)

        mode1_title = QLabel("⚡ <b>Quick Stealth</b> (Recommended)")
        mode1_title.setFont(QFont('Segoe UI', 12, QFont.Bold))
        mode1_layout.addWidget(mode1_title)

        mode1_desc = QLabel(
            "• <b>Speed:</b> 5-10 minutes per video<br>"
            "• <b>Effectiveness:</b> 70% undetectable<br>"
            "• <b>Processing:</b> Metadata removal + Edge blur + Audio processing + Re-encoding<br>"
            "• <b>Best for:</b> Fast processing, moderate PC specs"
        )
        mode1_desc.setWordWrap(True)
        mode1_desc.setFont(QFont('Segoe UI', 9))
        mode1_desc.setStyleSheet("color: #a0a0a0; margin-left: 10px;")
        mode1_layout.addWidget(mode1_desc)
        layout.addWidget(mode1_frame)

        # Mode 2: Deep Stealth
        mode2_frame = QFrame()
        mode2_frame.setObjectName("stealth_mode_card")
        mode2_layout = QVBoxLayout(mode2_frame)

        mode2_title = QLabel("🔥 <b>Deep Stealth</b> (Advanced)")
        mode2_title.setFont(QFont('Segoe UI', 12, QFont.Bold))
        mode2_layout.addWidget(mode2_title)

        mode2_desc = QLabel(
            "• <b>Speed:</b> 20-30 minutes per video<br>"
            "• <b>Effectiveness:</b> 90% undetectable<br>"
            "• <b>Processing:</b> Quick + Frame interpolation + Color grading + Noise injection<br>"
            "• <b>Best for:</b> High stealth needed, good PC specs"
        )
        mode2_desc.setWordWrap(True)
        mode2_desc.setFont(QFont('Segoe UI', 9))
        mode2_desc.setStyleSheet("color: #a0a0a0; margin-left: 10px;")
        mode2_layout.addWidget(mode2_desc)
        layout.addWidget(mode2_frame)

        # Mode 3: Maximum Stealth
        mode3_frame = QFrame()
        mode3_frame.setObjectName("stealth_mode_card")
        mode3_layout = QVBoxLayout(mode3_frame)

        mode3_title = QLabel("🚀 <b>Maximum Stealth</b> (Professional)")
        mode3_title.setFont(QFont('Segoe UI', 12, QFont.Bold))
        mode3_layout.addWidget(mode3_title)

        mode3_desc = QLabel(
            "• <b>Speed:</b> 1-2 hours per video<br>"
            "• <b>Effectiveness:</b> 99% undetectable<br>"
            "• <b>Processing:</b> Deep + Scene segmentation + Perceptual hash targeting + Complete reconstruction<br>"
            "• <b>Best for:</b> Maximum stealth, powerful PC, overnight processing"
        )
        mode3_desc.setWordWrap(True)
        mode3_desc.setFont(QFont('Segoe UI', 9))
        mode3_desc.setStyleSheet("color: #a0a0a0; margin-left: 10px;")
        mode3_layout.addWidget(mode3_desc)
        layout.addWidget(mode3_frame)

        # Note about device specs
        device_note = QLabel(
            "<br><b>📱 Device Check:</b> We'll recommend the best mode based on your PC specs during processing."
        )
        device_note.setWordWrap(True)
        device_note.setFont(QFont('Segoe UI', 9))
        device_note.setStyleSheet("color: #4caf50; font-style: italic;")
        layout.addWidget(device_note)

        group.setLayout(layout)
        return group

    def create_features_section(self) -> QGroupBox:
        """Create features section"""
        group = QGroupBox("✨ Key Features")
        layout = QVBoxLayout()

        features = [
            "✅ <b>Advanced Stealth:</b> 3 processing modes (Quick, Deep, Maximum)",
            "✅ <b>Bulk Processing:</b> Process hundreds of videos automatically",
            "✅ <b>Smart Detection Bypass:</b> Evades YouTube Content ID, Facebook Rights Manager",
            "✅ <b>Audio Processing:</b> 6-stage professional audio chain (voice isolation, pitch shift)",
            "✅ <b>Visual Effects:</b> Edge blur, color grading, frame manipulation",
            "✅ <b>Folder Mapping:</b> Preserve folder structure during processing",
            "✅ <b>In-place Mode:</b> Replace originals or save to different location",
            "✅ <b>Quality Control:</b> High/Medium/Low quality presets"
        ]

        for feature in features:
            feature_label = QLabel(feature)
            feature_label.setWordWrap(True)
            feature_label.setFont(QFont('Segoe UI', 10))
            layout.addWidget(feature_label)

        group.setLayout(layout)
        return group

    def apply_theme(self):
        """Apply dark theme"""
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
            }
            QFrame#header {
                background-color: #242424;
                border-radius: 12px;
            }
            QLabel#title {
                color: #9c27b0;
            }
            QLabel#subtitle {
                color: #888888;
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
            QFrame#stealth_mode_card {
                background-color: #2a2a2a;
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                padding: 12px;
                margin: 5px 0px;
            }
            QFrame#stealth_mode_card:hover {
                border-color: #9c27b0;
                background-color: #2f2f2f;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353535;
            }
            QPushButton:pressed {
                background-color: #202020;
            }
            QPushButton#primary_btn {
                background-color: #9c27b0;
                color: #ffffff;
            }
            QPushButton#primary_btn:hover {
                background-color: #ab47bc;
            }
            QPushButton#primary_btn:pressed {
                background-color: #7b1fa2;
            }
            QPushButton#back_btn {
                background-color: transparent;
                color: #888888;
                border: 1px solid #3a3a3a;
            }
            QPushButton#back_btn:hover {
                background-color: #2a2a2a;
                color: #e0e0e0;
            }
        """)

    def open_bulk_processing(self):
        """Open bulk processing dialog"""
        try:
            from modules.metadata_remover.metadata_mapping_dialog import MetadataBulkProcessingDialog
            from modules.metadata_remover.metadata_progress_dialog import MetadataProgressDialog

            # Open configuration dialog
            config_dialog = MetadataBulkProcessingDialog(self)

            # Connect signal for when processing should start
            def on_start_processing(config):
                # Open progress dialog
                progress_dialog = MetadataProgressDialog(config, self)
                progress_dialog.exec_()

            config_dialog.start_processing.connect(on_start_processing)

            # Show dialog
            config_dialog.exec_()

            logger.info("Bulk processing dialog closed")

        except Exception as e:
            logger.error(f"Failed to open bulk processing: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open bulk processing dialog:\n{str(e)}"
            )

    def go_back(self):
        """Go back to main menu"""
        if self.back_callback:
            self.back_callback()
