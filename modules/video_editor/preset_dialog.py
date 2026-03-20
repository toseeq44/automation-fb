"""
modules/video_editor/preset_dialog.py
Enhanced Preset Manager Dialog - Wrapper for new preset system
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QTabWidget, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from modules.logging.logger import get_logger
from modules.video_editor.preset_manager import PresetManager
from modules.video_editor.preset_manager_dialog import PresetManagerDialog as AdvancedPresetManager
from modules.video_editor.preset_builder_dialog import PresetBuilderDialog

logger = get_logger(__name__)


class PresetManagerDialog(QDialog):
    """
    Enhanced Preset Manager Dialog
    Main entry point for preset management in video editor
    """

    preset_selected = pyqtSignal(object)  # Emits selected EditingPreset object

    def __init__(self, parent=None, preset_manager=None):
        super().__init__(parent)
        self.preset_manager = preset_manager or PresetManager()
        self.selected_preset = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("🎬 Video Editing Presets")
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel("Video Editing Presets")
        header.setFont(QFont("Arial", 18, QFont.Bold))
        header.setStyleSheet("color: #00bcd4; padding: 10px;")
        layout.addWidget(header)

        # Description
        desc = QLabel(
            "Create and manage professional video editing presets.\n"
            "Apply preset operations to your videos with one click!"
        )
        desc.setStyleSheet("color: #a0a0a0; padding-bottom: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        # Visual Preset Builder
        builder_btn = QPushButton("🎨 Visual Preset Builder")
        builder_btn.setMinimumHeight(60)
        builder_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: #ffffff;
                border: none;
                border-radius: 12px;
                padding: 15px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #764ba2, stop:1 #667eea);
            }
        """)
        builder_btn.clicked.connect(self.open_visual_builder)
        btn_layout.addWidget(builder_btn)

        # Browse & Manage Presets
        browse_btn = QPushButton("📦 Browse & Manage Presets")
        browse_btn.setMinimumHeight(60)
        browse_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f093fb, stop:1 #f5576c);
                color: #ffffff;
                border: none;
                border-radius: 12px;
                padding: 15px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f5576c, stop:1 #f093fb);
            }
        """)
        browse_btn.clicked.connect(self.open_preset_manager)
        btn_layout.addWidget(browse_btn)

        layout.addLayout(btn_layout)

        # Info section
        info_widget = self.create_info_section()
        layout.addWidget(info_widget, 1)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 10px;
                padding: 10px 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
        """)
        close_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(close_btn)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)
        self.apply_dark_theme()

    def create_info_section(self) -> QWidget:
        """Create information section"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info_text = QLabel(
            "<h3 style='color: #00bcd4;'>✨ Features:</h3>"
            "<ul style='color: #a0a0a0; line-height: 1.8;'>"
            "<li><b>Visual Preset Builder:</b> Create presets with 3-panel interface</li>"
            "<li><b>Operation Library:</b> 16+ operations organized by category</li>"
            "<li><b>Parameter Editor:</b> Dynamic controls for each operation</li>"
            "<li><b>Preset Manager:</b> Browse, edit, duplicate, import/export presets</li>"
            "<li><b>System Templates:</b> TikTok, Instagram, YouTube presets included</li>"
            "<li><b>Folder Organization:</b> System, User, and Imported presets</li>"
            "<li><b>Validation:</b> Real-time parameter validation</li>"
            "<li><b>Export/Import:</b> Share presets as JSON files</li>"
            "</ul>"
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("padding: 15px; background-color: #1e1e1e; border-radius: 10px;")
        layout.addWidget(info_text)

        return widget

    def apply_dark_theme(self):
        """Apply dark theme to dialog"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)

    def open_visual_builder(self):
        """Open visual preset builder"""
        dialog = PresetBuilderDialog(preset=None, parent=self)

        if dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(
                self,
                "Success",
                f"Preset '{dialog.preset.name}' created successfully!\n\n"
                "You can now use it in bulk processing or edit it in the preset manager."
            )

    def open_preset_manager(self):
        """Open advanced preset manager"""
        dialog = AdvancedPresetManager(parent=self)

        # Connect signal to capture selected preset
        dialog.preset_selected.connect(self.on_preset_selected_from_manager)

        dialog.exec_()

    def on_preset_selected_from_manager(self, preset_name: str, folder: str):
        """Handle preset selection from manager"""
        # Load the preset
        preset = self.preset_manager.load_preset(preset_name)

        if preset:
            self.selected_preset = preset
            self.preset_selected.emit(preset)

            QMessageBox.information(
                self,
                "Preset Selected",
                f"Preset '{preset_name}' has been selected.\n\n"
                f"Category: {preset.category}\n"
                f"Operations: {len(preset.operations)}"
            )

            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load preset: {preset_name}"
            )
