"""
Folder Mapping Configuration Dialog
UI for configuring folder mappings between Links Grabber and Creators Data
"""

from pathlib import Path
from typing import Optional, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
    QCheckBox, QFileDialog, QMessageBox, QGroupBox, QComboBox,
    QFrame, QWidget, QSizePolicy, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from .folder_mapping_manager import FolderMappingManager, FolderMapping


class FolderMappingDialog(QDialog):
    """Dialog for configuring folder mappings"""

    mappings_updated = pyqtSignal()  # Signal emitted when mappings are saved

    def __init__(self, parent=None, mapping_manager: Optional[FolderMappingManager] = None):
        super().__init__(parent)
        self.mapping_manager = mapping_manager or FolderMappingManager()

        self.setWindowTitle("Folder Mapping Configuration")
        self.setMinimumSize(1000, 600)

        # Style
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
            }
            QTableWidget {
                background-color: #16213e;
                color: #ffffff;
                border: 1px solid #00d4ff;
                border-radius: 5px;
                gridline-color: #2a2a4e;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #00d4ff;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #0f3460;
                color: #00d4ff;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            QPushButton {
                background-color: #00d4ff;
                color: #000000;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #00a8cc;
            }
            QPushButton:pressed {
                background-color: #0088aa;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
            QPushButton#deleteBtn {
                background-color: #e74c3c;
            }
            QPushButton#deleteBtn:hover {
                background-color: #c0392b;
            }
            QSpinBox, QComboBox {
                background-color: #16213e;
                color: #ffffff;
                border: 1px solid #00d4ff;
                border-radius: 3px;
                padding: 5px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #00d4ff;
            }
            QCheckBox {
                color: #ffffff;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #00d4ff;
                border-radius: 3px;
                background-color: #16213e;
            }
            QCheckBox::indicator:checked {
                background-color: #00d4ff;
            }
            QGroupBox {
                border: 2px solid #00d4ff;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #00d4ff;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        self.init_ui()
        self.load_existing_mappings()

    def init_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Header
        header_label = QLabel("Configure Folder Mappings")
        header_label.setFont(QFont("Arial", 16, QFont.Bold))
        header_label.setStyleSheet("color: #00d4ff; padding: 10px;")
        layout.addWidget(header_label)

        # Info label
        info_label = QLabel(
            "Map source folders (Links Grabber) to destination folders (Creators Data). "
            "Videos will be automatically moved based on your settings."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #aaaaaa; padding: 5px;")
        layout.addWidget(info_label)

        # Mappings table
        self.create_mappings_table()
        layout.addWidget(self.mappings_table)

        # Control buttons
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        self.add_btn = QPushButton("➕ Add Mapping")
        self.add_btn.clicked.connect(self.add_new_mapping)
        control_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ Edit Selected")
        self.edit_btn.clicked.connect(self.edit_selected_mapping)
        self.edit_btn.setEnabled(False)
        control_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑️ Delete Selected")
        self.delete_btn.setObjectName("deleteBtn")
        self.delete_btn.clicked.connect(self.delete_selected_mapping)
        self.delete_btn.setEnabled(False)
        control_layout.addWidget(self.delete_btn)

        self.scan_btn = QPushButton("🔍 Scan Source Folders")
        self.scan_btn.clicked.connect(self.scan_source_folders)
        control_layout.addWidget(self.scan_btn)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        # Statistics group
        stats_group = self.create_stats_group()
        layout.addWidget(stats_group)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.import_btn = QPushButton("📥 Import Config")
        self.import_btn.clicked.connect(self.import_config)
        button_layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("📤 Export Config")
        self.export_btn.clicked.connect(self.export_config)
        button_layout.addWidget(self.export_btn)

        button_layout.addStretch()

        self.save_btn = QPushButton("💾 Save & Close")
        self.save_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_mappings_table(self):
        """Create the mappings table widget"""
        self.mappings_table = QTableWidget()
        self.mappings_table.setColumnCount(6)
        self.mappings_table.setHorizontalHeaderLabels([
            "Enabled", "Source Folder", "Destination Folder",
            "Daily Limit", "Move Condition", "Stats"
        ])

        # Table settings
        self.mappings_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.mappings_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.mappings_table.verticalHeader().setVisible(False)
        self.mappings_table.setAlternatingRowColors(True)

        # Column widths
        header = self.mappings_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        # Connect selection change
        self.mappings_table.itemSelectionChanged.connect(self.on_selection_changed)

        # Double click to edit
        self.mappings_table.doubleClicked.connect(self.edit_selected_mapping)

    def create_stats_group(self) -> QGroupBox:
        """Create statistics group box"""
        stats_group = QGroupBox("Statistics")
        stats_layout = QHBoxLayout()

        stats = self.mapping_manager.get_stats()

        self.total_label = QLabel(f"Total Mappings: {stats['total_mappings']}")
        self.active_label = QLabel(f"Active: {stats['active_mappings']}")
        self.moved_label = QLabel(f"Total Videos Moved: {stats['total_videos_moved']}")

        for label in [self.total_label, self.active_label, self.moved_label]:
            label.setStyleSheet("color: #ffffff; font-size: 11px;")
            stats_layout.addWidget(label)

        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)

        return stats_group

    def load_existing_mappings(self):
        """Load existing mappings into the table"""
        self.mappings_table.setRowCount(0)

        mappings = self.mapping_manager.get_all_mappings()

        for mapping in mappings:
            self.add_mapping_to_table(mapping)

        self.update_stats()

    def add_mapping_to_table(self, mapping: FolderMapping):
        """Add a mapping to the table"""
        row = self.mappings_table.rowCount()
        self.mappings_table.insertRow(row)

        # Enabled checkbox
        enabled_widget = QWidget()
        enabled_layout = QHBoxLayout(enabled_widget)
        enabled_layout.setContentsMargins(0, 0, 0, 0)
        enabled_layout.setAlignment(Qt.AlignCenter)

        enabled_checkbox = QCheckBox()
        enabled_checkbox.setChecked(mapping.enabled)
        enabled_checkbox.stateChanged.connect(
            lambda state, m=mapping: self.on_enabled_changed(m, state)
        )
        enabled_layout.addWidget(enabled_checkbox)
        self.mappings_table.setCellWidget(row, 0, enabled_widget)

        # Source folder
        source_item = QTableWidgetItem(mapping.source_folder)
        source_item.setData(Qt.UserRole, mapping.id)
        self.mappings_table.setItem(row, 1, source_item)

        # Destination folder
        dest_item = QTableWidgetItem(mapping.destination_folder)
        self.mappings_table.setItem(row, 2, dest_item)

        # Daily limit
        limit_item = QTableWidgetItem(str(mapping.daily_limit))
        limit_item.setTextAlignment(Qt.AlignCenter)
        self.mappings_table.setItem(row, 3, limit_item)

        # Move condition
        condition_text = "Empty Only" if mapping.move_only_if_empty else "Always"
        condition_item = QTableWidgetItem(condition_text)
        condition_item.setTextAlignment(Qt.AlignCenter)
        self.mappings_table.setItem(row, 4, condition_item)

        # Stats
        stats_text = f"Moved: {mapping.total_moved}"
        if mapping.last_move_date:
            stats_text += f"\nLast: {mapping.last_move_date[:10]}"
        stats_item = QTableWidgetItem(stats_text)
        stats_item.setTextAlignment(Qt.AlignCenter)
        self.mappings_table.setItem(row, 5, stats_item)

        # Color code the row based on validation
        is_valid, _ = mapping.validate()
        if not is_valid:
            for col in range(6):
                item = self.mappings_table.item(row, col)
                if item:
                    item.setBackground(QColor("#3d2020"))

    def on_enabled_changed(self, mapping: FolderMapping, state: int):
        """Handle enabled checkbox state change"""
        mapping.enabled = (state == Qt.Checked)

    def on_selection_changed(self):
        """Handle table selection change"""
        has_selection = len(self.mappings_table.selectedItems()) > 0
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def add_new_mapping(self):
        """Add a new mapping"""
        dialog = MappingEditDialog(self, None, self.mapping_manager)
        if dialog.exec_() == QDialog.Accepted:
            mapping = dialog.get_mapping()
            if self.mapping_manager.add_mapping(mapping):
                self.load_existing_mappings()
                QMessageBox.information(self, "Success", "Mapping added successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to add mapping. Check if source folder already mapped.")

    def edit_selected_mapping(self):
        """Edit the selected mapping"""
        selected_rows = self.mappings_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        mapping_id = self.mappings_table.item(row, 1).data(Qt.UserRole)
        mapping = self.mapping_manager.get_mapping(mapping_id)

        if mapping:
            dialog = MappingEditDialog(self, mapping, self.mapping_manager)
            if dialog.exec_() == QDialog.Accepted:
                updated_mapping = dialog.get_mapping()
                if self.mapping_manager.update_mapping(mapping_id, updated_mapping):
                    self.load_existing_mappings()
                    QMessageBox.information(self, "Success", "Mapping updated successfully!")
                else:
                    QMessageBox.warning(self, "Error", "Failed to update mapping.")

    def delete_selected_mapping(self):
        """Delete the selected mapping"""
        selected_rows = self.mappings_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to delete this mapping?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            row = selected_rows[0].row()
            mapping_id = self.mappings_table.item(row, 1).data(Qt.UserRole)

            if self.mapping_manager.delete_mapping(mapping_id):
                self.load_existing_mappings()
                QMessageBox.information(self, "Success", "Mapping deleted successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to delete mapping.")

    def scan_source_folders(self):
        """Scan for source folders and suggest new mappings"""
        links_grabber_path = Path.home() / "Desktop" / "Links Grabber"

        if not links_grabber_path.exists():
            QMessageBox.warning(
                self, "Folder Not Found",
                f"Links Grabber folder not found at:\n{links_grabber_path}\n\n"
                "Please ensure the folder exists."
            )
            return

        # Get all subdirectories
        subdirs = [d for d in links_grabber_path.iterdir() if d.is_dir()]

        if not subdirs:
            QMessageBox.information(
                self, "No Folders Found",
                "No subdirectories found in Links Grabber folder."
            )
            return

        # Check which ones are not already mapped
        existing_sources = {m.source_folder for m in self.mapping_manager.get_all_mappings()}
        new_folders = [str(d) for d in subdirs if str(d) not in existing_sources]

        if not new_folders:
            QMessageBox.information(
                self, "All Mapped",
                "All folders are already mapped!"
            )
            return

        # Show dialog with new folders
        msg = f"Found {len(new_folders)} unmapped folders:\n\n"
        msg += "\n".join(new_folders[:10])
        if len(new_folders) > 10:
            msg += f"\n... and {len(new_folders) - 10} more"

        msg += "\n\nClick OK to add them (you'll need to set destination folders)."

        reply = QMessageBox.question(
            self, "Add New Mappings",
            msg,
            QMessageBox.Ok | QMessageBox.Cancel
        )

        if reply == QMessageBox.Ok:
            for folder in new_folders:
                self.add_new_mapping()

    def import_config(self):
        """Import configuration from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Configuration",
            str(Path.home() / "Desktop"),
            "JSON Files (*.json)"
        )

        if file_path:
            reply = QMessageBox.question(
                self, "Import Mode",
                "Merge with existing mappings?\n\n"
                "Yes = Merge (keep existing + add new)\n"
                "No = Replace (delete existing)",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )

            if reply == QMessageBox.Cancel:
                return

            merge = (reply == QMessageBox.Yes)

            if self.mapping_manager.import_config(Path(file_path), merge=merge):
                self.load_existing_mappings()
                QMessageBox.information(self, "Success", "Configuration imported successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to import configuration.")

    def export_config(self):
        """Export configuration to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Configuration",
            str(Path.home() / "Desktop" / "folder_mappings.json"),
            "JSON Files (*.json)"
        )

        if file_path:
            if self.mapping_manager.export_config(Path(file_path)):
                QMessageBox.information(self, "Success", f"Configuration exported to:\n{file_path}")
            else:
                QMessageBox.warning(self, "Error", "Failed to export configuration.")

    def update_stats(self):
        """Update statistics labels"""
        stats = self.mapping_manager.get_stats()
        self.total_label.setText(f"Total Mappings: {stats['total_mappings']}")
        self.active_label.setText(f"Active: {stats['active_mappings']}")
        self.moved_label.setText(f"Total Videos Moved: {stats['total_videos_moved']}")

    def accept(self):
        """Save and close dialog"""
        if self.mapping_manager.save():
            self.mappings_updated.emit()
            super().accept()
        else:
            QMessageBox.warning(self, "Error", "Failed to save mappings.")


class MappingEditDialog(QDialog):
    """Dialog for editing a single mapping"""

    def __init__(self, parent, mapping: Optional[FolderMapping], mapping_manager: FolderMappingManager):
        super().__init__(parent)
        self.mapping = mapping
        self.mapping_manager = mapping_manager
        self.is_edit_mode = mapping is not None

        title = "Edit Mapping" if self.is_edit_mode else "Add New Mapping"
        self.setWindowTitle(title)
        self.setMinimumWidth(600)

        # Apply dark theme
        self.setStyleSheet(parent.styleSheet())

        self.init_ui()

        if self.is_edit_mode:
            self.load_mapping_data()

    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Source folder
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Source Folder:"))
        self.source_edit = QLabel("Not selected")
        self.source_edit.setStyleSheet(
            "background-color: #16213e; padding: 8px; border: 1px solid #00d4ff; border-radius: 3px;"
        )
        self.source_edit.setWordWrap(True)
        source_layout.addWidget(self.source_edit, 1)

        self.source_browse_btn = QPushButton("📁 Browse")
        self.source_browse_btn.clicked.connect(self.browse_source)
        source_layout.addWidget(self.source_browse_btn)
        layout.addLayout(source_layout)

        # Destination folder
        dest_layout = QHBoxLayout()
        dest_layout.addWidget(QLabel("Destination Folder:"))
        self.dest_edit = QLabel("Not selected")
        self.dest_edit.setStyleSheet(
            "background-color: #16213e; padding: 8px; border: 1px solid #00d4ff; border-radius: 3px;"
        )
        self.dest_edit.setWordWrap(True)
        dest_layout.addWidget(self.dest_edit, 1)

        self.dest_browse_btn = QPushButton("📁 Browse")
        self.dest_browse_btn.clicked.connect(self.browse_destination)
        dest_layout.addWidget(self.dest_browse_btn)
        layout.addLayout(dest_layout)

        # Daily limit
        limit_layout = QHBoxLayout()
        limit_layout.addWidget(QLabel("Daily Limit (videos per day):"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setMinimum(1)
        self.limit_spin.setMaximum(100)
        self.limit_spin.setValue(5)
        limit_layout.addWidget(self.limit_spin)
        limit_layout.addStretch()
        layout.addLayout(limit_layout)

        # Move condition
        condition_layout = QHBoxLayout()
        condition_layout.addWidget(QLabel("Move Condition:"))
        self.condition_combo = QComboBox()
        self.condition_combo.addItem("Only when destination is empty", True)
        self.condition_combo.addItem("Always move (regardless of existing files)", False)
        condition_layout.addWidget(self.condition_combo)
        condition_layout.addStretch()
        layout.addLayout(condition_layout)

        # Enabled checkbox
        self.enabled_checkbox = QCheckBox("Enable this mapping")
        self.enabled_checkbox.setChecked(True)
        layout.addWidget(self.enabled_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_btn = QPushButton("✅ OK")
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_mapping_data(self):
        """Load data from existing mapping"""
        if not self.mapping:
            return

        self.source_edit.setText(self.mapping.source_folder)
        self.dest_edit.setText(self.mapping.destination_folder)
        self.limit_spin.setValue(self.mapping.daily_limit)

        # Set condition combo
        index = 0 if self.mapping.move_only_if_empty else 1
        self.condition_combo.setCurrentIndex(index)

        self.enabled_checkbox.setChecked(self.mapping.enabled)

    def browse_source(self):
        """Browse for source folder"""
        default_path = Path.home() / "Desktop" / "Links Grabber"
        folder = QFileDialog.getExistingDirectory(
            self, "Select Source Folder",
            str(default_path)
        )

        if folder:
            self.source_edit.setText(folder)

    def browse_destination(self):
        """Browse for destination folder"""
        default_path = Path.home() / "Desktop" / "creators data"
        folder = QFileDialog.getExistingDirectory(
            self, "Select Destination Folder",
            str(default_path)
        )

        if folder:
            self.dest_edit.setText(folder)

    def get_mapping(self) -> FolderMapping:
        """Get the configured mapping"""
        mapping_id = self.mapping.id if self.is_edit_mode else None

        return FolderMapping(
            mapping_id=mapping_id,
            source_folder=self.source_edit.text(),
            destination_folder=self.dest_edit.text(),
            daily_limit=self.limit_spin.value(),
            move_only_if_empty=self.condition_combo.currentData(),
            enabled=self.enabled_checkbox.isChecked()
        )

    def accept(self):
        """Validate and accept"""
        mapping = self.get_mapping()
        is_valid, error = mapping.validate()

        if not is_valid:
            QMessageBox.warning(self, "Validation Error", error)
            return

        super().accept()
