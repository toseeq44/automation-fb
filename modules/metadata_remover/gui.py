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

        # Info section
        info_group = self.create_info_section()
        main_layout.addWidget(info_group)

        # Features section
        features_group = self.create_features_section()
        main_layout.addWidget(features_group)

        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.setSpacing(15)

        # Bulk Processing button
        self.bulk_btn = QPushButton("🔒 Bulk Metadata Removal")
        self.bulk_btn.setObjectName("primary_btn")
        self.bulk_btn.setMinimumHeight(50)
        self.bulk_btn.setFont(QFont('Segoe UI', 14, QFont.Bold))
        self.bulk_btn.setToolTip("Remove metadata from multiple videos at once")
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
        """Create info section"""
        group = QGroupBox("What is Metadata?")
        layout = QVBoxLayout()

        info_text = QLabel(
            "Video metadata includes hidden information such as:\n\n"
            "• 📷 Camera/device information\n"
            "• 📅 Date and time of recording\n"
            "• 📍 GPS location data\n"
            "• 🖥️ Software used for editing\n"
            "• 👤 Author/creator information\n\n"
            "Removing metadata helps protect your privacy when sharing videos online."
        )
        info_text.setWordWrap(True)
        info_text.setFont(QFont('Segoe UI', 11))
        layout.addWidget(info_text)

        group.setLayout(layout)
        return group

    def create_features_section(self) -> QGroupBox:
        """Create features section"""
        group = QGroupBox("Features")
        layout = QVBoxLayout()

        features = [
            "✅ Bulk processing - Remove metadata from multiple videos at once",
            "✅ Folder mapping - Process entire folders with subfolders",
            "✅ In-place replacement - Replace original files directly",
            "✅ Different folder mode - Save clean videos to a new location",
            "✅ Fast processing - Uses FFmpeg stream copy (no re-encoding)",
            "✅ Daily limits - Basic (200/day) or Pro (unlimited)"
        ]

        for feature in features:
            feature_label = QLabel(feature)
            feature_label.setFont(QFont('Segoe UI', 11))
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
