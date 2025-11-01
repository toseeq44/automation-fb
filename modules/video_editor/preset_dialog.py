"""
modules/video_editor/preset_dialog.py
Preset Manager Dialog - Basic Implementation
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from modules.logging.logger import get_logger
from modules.video_editor.preset_manager import PresetManager

logger = get_logger(__name__)


class PresetManagerDialog(QDialog):
    """Dialog for managing and applying presets"""

    def __init__(self, parent=None, preset_manager=None):
        super().__init__(parent)
        self.preset_manager = preset_manager or PresetManager()
        self.selected_preset = None
        self.init_ui()
        self.load_presets()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("📦 Preset Manager")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel("Editing Presets")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        header.setStyleSheet("color: #00bcd4; padding: 10px;")
        layout.addWidget(header)

        # Description
        desc = QLabel("Select a preset to apply to your video:")
        desc.setStyleSheet("color: #a0a0a0; padding-bottom: 10px;")
        layout.addWidget(desc)

        # Preset list
        self.preset_list = QListWidget()
        self.preset_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 10px;
                padding: 8px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #252525;
                border-radius: 8px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #2a4a5a;
                color: #ffffff;
            }
            QListWidget::item:hover:!selected {
                background-color: #252525;
            }
        """)
        self.preset_list.itemDoubleClicked.connect(self.apply_preset)
        layout.addWidget(self.preset_list, 1)

        # Preset info
        self.info_label = QLabel("Select a preset to see details")
        self.info_label.setStyleSheet("color: #888888; font-size: 12px; padding: 8px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # New Preset button
        new_btn = QPushButton("➕ New Preset")
        new_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 10px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353535;
            }
        """)
        new_btn.clicked.connect(self.create_preset)
        btn_layout.addWidget(new_btn)

        # Delete Preset button
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #d63031;
            }
        """)
        delete_btn.clicked.connect(self.delete_preset)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        # Apply button
        apply_btn = QPushButton("✅ Apply Preset")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #00bcd4;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00d4ea;
            }
        """)
        apply_btn.clicked.connect(self.apply_preset)
        btn_layout.addWidget(apply_btn)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
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
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.apply_dark_theme()

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

    def load_presets(self):
        """Load available presets"""
        self.preset_list.clear()

        # Get all available presets
        preset_names = self.preset_manager.list_presets()

        if not preset_names:
            # Add default presets
            self.add_default_presets()
            preset_names = self.preset_manager.list_presets()

        for preset_summary in preset_names:
            # Extract preset name from summary dict
            preset_name = preset_summary['name']
            preset_desc = preset_summary.get('description', '')
            ops_count = preset_summary.get('operations_count', 0)

            # Create display text
            display_text = f"📦 {preset_name}"
            if preset_desc:
                display_text += f"\n   {preset_desc}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, preset_name)  # Store just the name string
            self.preset_list.addItem(item)

        self.info_label.setText(f"Found {len(preset_names)} preset(s)")

    def add_default_presets(self):
        """Add default presets for common platforms"""
        default_presets = {
            "TikTok Standard": {
                "crop": {"aspect_ratio": "9:16", "width": 1080, "height": 1920},
                "description": "Vertical format optimized for TikTok"
            },
            "Instagram Reels": {
                "crop": {"aspect_ratio": "9:16", "width": 1080, "height": 1920},
                "description": "Vertical format for Instagram Reels"
            },
            "YouTube Shorts": {
                "crop": {"aspect_ratio": "9:16", "width": 1080, "height": 1920},
                "description": "Vertical format for YouTube Shorts"
            },
            "YouTube Standard": {
                "crop": {"aspect_ratio": "16:9", "width": 1920, "height": 1080},
                "description": "Standard HD format for YouTube"
            },
            "Instagram Square": {
                "crop": {"aspect_ratio": "1:1", "width": 1080, "height": 1080},
                "description": "Square format for Instagram posts"
            }
        }

        for name, config in default_presets.items():
            preset = self.preset_manager.create_preset(name, config.get("description", ""))
            if "crop" in config:
                preset.add_operation("crop", config["crop"])
            self.preset_manager.save_preset(preset)

        logger.info(f"Added {len(default_presets)} default presets")

    def create_preset(self):
        """Create a new preset"""
        name, ok = QInputDialog.getText(
            self,
            "New Preset",
            "Enter preset name:",
            text="My Custom Preset"
        )

        if ok and name:
            if name in self.preset_manager.list_presets():
                QMessageBox.warning(self, "Preset Exists", f"A preset named '{name}' already exists.")
                return

            desc, ok = QInputDialog.getText(
                self,
                "Preset Description",
                "Enter description (optional):",
            )

            preset = self.preset_manager.create_preset(name, desc if ok else "")
            self.preset_manager.save_preset(preset)
            self.load_presets()
            self.info_label.setText(f"Created preset: {name}")

    def delete_preset(self):
        """Delete selected preset"""
        current_item = self.preset_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a preset to delete.")
            return

        preset_name = current_item.data(Qt.UserRole)

        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f"Are you sure you want to delete the preset '{preset_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.preset_manager.delete_preset(preset_name)
                self.load_presets()
                self.info_label.setText(f"Deleted preset: {preset_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete preset: {str(e)}")

    def apply_preset(self):
        """Apply selected preset"""
        current_item = self.preset_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a preset to apply.")
            return

        preset_name = current_item.data(Qt.UserRole)
        self.selected_preset = self.preset_manager.load_preset(preset_name)

        if self.selected_preset:
            logger.info(f"Preset selected: {preset_name}")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", f"Failed to load preset: {preset_name}")
