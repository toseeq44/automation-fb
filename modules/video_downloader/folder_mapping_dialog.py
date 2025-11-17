"""
Folder Mapping Configuration Dialog
UI for configuring folder mappings between Links Grabber and Creators Data
Enhanced Professional Version
"""

from pathlib import Path
from typing import Optional, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
    QCheckBox, QFileDialog, QMessageBox, QGroupBox, QComboBox,
    QFrame, QWidget, QSizePolicy, QAbstractItemView, QLineEdit,
    QGridLayout, QButtonGroup, QRadioButton, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QFont, QIcon, QPalette

from .folder_mapping_manager import FolderMappingManager, FolderMapping


class FolderMappingDialog(QDialog):
    """Dialog for configuring folder mappings"""

    mappings_updated = pyqtSignal()  # Signal emitted when mappings are saved

    def __init__(self, parent=None, mapping_manager: Optional[FolderMappingManager] = None):
        super().__init__(parent)
        self.mapping_manager = mapping_manager or FolderMappingManager()

        self.setWindowTitle("📁 Folder Mapping Configuration")

        # Responsive sizing - set default size and minimum size
        self.resize(1100, 700)  # Default size
        self.setMinimumSize(800, 500)  # Minimum size for usability

        # Make dialog resizable
        self.setSizeGripEnabled(True)

        # Modern professional style
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QLabel#headerLabel {
                color: #00d4ff;
                font-size: 20px;
                font-weight: bold;
                padding: 15px;
            }
            QLabel#infoLabel {
                color: #aaaaaa;
                font-size: 12px;
                padding: 8px;
                background-color: rgba(0, 212, 255, 0.1);
                border-left: 3px solid #00d4ff;
                border-radius: 4px;
            }
            QTableWidget {
                background-color: #1e1e2e;
                alternate-background-color: #252535;
                color: #ffffff;
                border: 2px solid #00d4ff;
                border-radius: 8px;
                gridline-color: #2a2a4e;
                selection-background-color: #00d4ff;
                selection-color: #000000;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2a2a4e;
            }
            QTableWidget::item:hover {
                background-color: rgba(0, 212, 255, 0.2);
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0f3460, stop:1 #1a1a2e);
                color: #00d4ff;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #00d4ff;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00d4ff, stop:1 #00a8cc);
                color: #000000;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 13px;
                min-height: 36px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00f0ff, stop:1 #00c8ee);
            }
            QPushButton:pressed {
                background: #0088aa;
            }
            QPushButton:disabled {
                background: #3a3a4a;
                color: #707070;
            }
            QPushButton#deleteBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e74c3c, stop:1 #c0392b);
                color: white;
            }
            QPushButton#deleteBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff5c4c, stop:1 #d0493b);
            }
            QPushButton#actionBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #9B59B6, stop:1 #8E44AD);
                color: white;
                padding: 10px 20px;
                min-height: 32px;
            }
            QPushButton#actionBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #AB69C6, stop:1 #9E54BD);
            }
            QSpinBox, QComboBox {
                background-color: #1e1e2e;
                color: #ffffff;
                border: 2px solid #3a3a4a;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                min-height: 32px;
            }
            QSpinBox:focus, QComboBox:focus {
                border: 2px solid #00d4ff;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #00d4ff;
                border-radius: 3px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #00f0ff;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #00d4ff;
                border-radius: 3px;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #000000;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e2e;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
                border: 2px solid #00d4ff;
                border-radius: 6px;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                min-height: 30px;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 10px;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #3a3a4a;
                border-radius: 4px;
                background-color: #1e1e2e;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #00d4ff;
            }
            QCheckBox::indicator:checked {
                background-color: #00d4ff;
                border: 2px solid #00d4ff;
                image: none;
            }
            QCheckBox::indicator:checked:after {
                content: "✓";
                color: #000000;
            }
            QGroupBox {
                border: 2px solid #3a3a4a;
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 20px;
                background-color: rgba(30, 30, 46, 0.5);
                font-weight: bold;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #00d4ff;
                background-color: transparent;
            }
            QFrame#separator {
                background-color: #3a3a4a;
                max-height: 2px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #1e1e2e;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #00d4ff;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #00f0ff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #1e1e2e;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #00d4ff;
                border-radius: 6px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #00f0ff;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        self.init_ui()
        self.load_existing_mappings()

    def init_ui(self):
        """Initialize the UI components with scrollable content"""
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        # Content widget inside scroll area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_label = QLabel("Folder Mapping Configuration")
        header_label.setObjectName("headerLabel")
        content_layout.addWidget(header_label)

        # Info label
        info_label = QLabel(
            "💡 Map source folders (Links Grabber) to destination folders (Creators Data). "
            "Videos will be automatically moved based on your daily limits and conditions."
        )
        info_label.setObjectName("infoLabel")
        info_label.setWordWrap(True)
        content_layout.addWidget(info_label)

        # Separator
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.HLine)
        content_layout.addWidget(separator)

        # Mappings table
        self.create_mappings_table()
        self.mappings_table.setMinimumHeight(200)  # Ensure table has minimum height
        content_layout.addWidget(self.mappings_table)

        # Control buttons in a more organized layout
        control_group = QGroupBox("📋 Mapping Actions")
        control_layout = QGridLayout()
        control_layout.setSpacing(10)

        # Row 1: Primary actions
        self.add_btn = QPushButton("➕ Add New Mapping")
        self.add_btn.setObjectName("actionBtn")
        self.add_btn.setToolTip("Create a new folder mapping configuration")
        self.add_btn.clicked.connect(self.add_new_mapping)
        control_layout.addWidget(self.add_btn, 0, 0)

        self.edit_btn = QPushButton("✏️ Edit Selected")
        self.edit_btn.setObjectName("actionBtn")
        self.edit_btn.setToolTip("Edit the selected mapping")
        self.edit_btn.clicked.connect(self.edit_selected_mapping)
        self.edit_btn.setEnabled(False)
        control_layout.addWidget(self.edit_btn, 0, 1)

        self.delete_btn = QPushButton("🗑️ Delete Selected")
        self.delete_btn.setObjectName("deleteBtn")
        self.delete_btn.setToolTip("Remove the selected mapping")
        self.delete_btn.clicked.connect(self.delete_selected_mapping)
        self.delete_btn.setEnabled(False)
        control_layout.addWidget(self.delete_btn, 0, 2)

        # Row 2: Secondary actions
        self.scan_btn = QPushButton("🔍 Scan Source Folders")
        self.scan_btn.setObjectName("actionBtn")
        self.scan_btn.setToolTip("Automatically scan for unmapped folders in Links Grabber")
        self.scan_btn.clicked.connect(self.scan_source_folders)
        control_layout.addWidget(self.scan_btn, 1, 0)

        self.import_btn = QPushButton("📥 Import Config")
        self.import_btn.setObjectName("actionBtn")
        self.import_btn.setToolTip("Import mappings from a JSON file")
        self.import_btn.clicked.connect(self.import_config)
        control_layout.addWidget(self.import_btn, 1, 1)

        self.export_btn = QPushButton("📤 Export Config")
        self.export_btn.setObjectName("actionBtn")
        self.export_btn.setToolTip("Export mappings to a JSON file")
        self.export_btn.clicked.connect(self.export_config)
        control_layout.addWidget(self.export_btn, 1, 2)

        control_group.setLayout(control_layout)
        content_layout.addWidget(control_group)

        # Statistics group with enhanced design
        stats_group = self.create_stats_group()
        content_layout.addWidget(stats_group)

        # Set the content widget in scroll area
        scroll_area.setWidget(content_widget)

        # Add scroll area to main layout
        main_layout.addWidget(scroll_area, 1)  # Stretch factor 1

        # Bottom buttons (outside scroll area - always visible)
        button_container = QWidget()
        button_container.setStyleSheet("background-color: #1a1a2e; padding: 10px;")
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(15)
        button_layout.setContentsMargins(20, 10, 20, 10)

        button_layout.addStretch()

        self.save_btn = QPushButton("💾 Save & Close")
        self.save_btn.setToolTip("Save all changes and close the dialog")
        self.save_btn.clicked.connect(self.accept)
        self.save_btn.setMinimumWidth(140)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.setToolTip("Discard changes and close")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumWidth(140)
        button_layout.addWidget(self.cancel_btn)

        # Add button container to main layout
        main_layout.addWidget(button_container, 0)  # Stretch factor 0 (fixed height)

        self.setLayout(main_layout)

    def create_mappings_table(self):
        """Create the mappings table widget"""
        self.mappings_table = QTableWidget()
        self.mappings_table.setColumnCount(6)
        self.mappings_table.setHorizontalHeaderLabels([
            "✓", "📂 Source Folder", "📁 Destination Folder",
            "📊 Daily Limit", "⚙️ Condition", "📈 Statistics"
        ])

        # Table settings
        self.mappings_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.mappings_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.mappings_table.verticalHeader().setVisible(False)
        self.mappings_table.setAlternatingRowColors(True)
        self.mappings_table.setShowGrid(True)

        # Column widths
        header = self.mappings_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        # Row height
        self.mappings_table.verticalHeader().setDefaultSectionSize(50)

        # Connect selection change
        self.mappings_table.itemSelectionChanged.connect(self.on_selection_changed)

        # Double click to edit
        self.mappings_table.doubleClicked.connect(self.edit_selected_mapping)

    def create_stats_group(self) -> QGroupBox:
        """Create statistics group box"""
        stats_group = QGroupBox("📊 Overview Statistics")
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(30)

        stats = self.mapping_manager.get_stats()

        # Create styled stat labels
        self.total_label = self.create_stat_label(
            "Total Mappings",
            str(stats['total_mappings']),
            "#00d4ff"
        )
        self.active_label = self.create_stat_label(
            "Active",
            str(stats['active_mappings']),
            "#00ff88"
        )
        self.moved_label = self.create_stat_label(
            "Videos Moved",
            str(stats['total_videos_moved']),
            "#ffd700"
        )

        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.active_label)
        stats_layout.addWidget(self.moved_label)
        stats_layout.addStretch()

        stats_group.setLayout(stats_layout)
        return stats_group

    def create_stat_label(self, title: str, value: str, color: str) -> QLabel:
        """Create a styled statistic label"""
        label = QLabel(f"<b>{title}:</b> <span style='color: {color}; font-size: 16px;'>{value}</span>")
        label.setStyleSheet(f"padding: 8px; background-color: rgba(0, 0, 0, 0.2); border-radius: 6px; border-left: 3px solid {color};")
        return label

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
        enabled_checkbox.setToolTip("Enable/disable this mapping")
        enabled_checkbox.stateChanged.connect(
            lambda state, m=mapping: self.on_enabled_changed(m, state)
        )
        enabled_layout.addWidget(enabled_checkbox)
        self.mappings_table.setCellWidget(row, 0, enabled_widget)

        # Source folder with icon
        source_item = QTableWidgetItem(f"  {mapping.source_folder}")
        source_item.setData(Qt.UserRole, mapping.id)
        source_item.setToolTip(f"Source: {mapping.source_folder}")
        self.mappings_table.setItem(row, 1, source_item)

        # Destination folder with icon
        dest_item = QTableWidgetItem(f"  {mapping.destination_folder}")
        dest_item.setToolTip(f"Destination: {mapping.destination_folder}")
        self.mappings_table.setItem(row, 2, dest_item)

        # Daily limit with styling
        limit_item = QTableWidgetItem(f"{mapping.daily_limit} videos/day")
        limit_item.setTextAlignment(Qt.AlignCenter)
        limit_item.setToolTip(f"Maximum {mapping.daily_limit} videos per day")
        # Color code based on limit
        if mapping.daily_limit <= 3:
            limit_item.setForeground(QColor("#ffd700"))
        elif mapping.daily_limit <= 10:
            limit_item.setForeground(QColor("#00ff88"))
        else:
            limit_item.setForeground(QColor("#ff6b6b"))
        self.mappings_table.setItem(row, 3, limit_item)

        # Move condition with icon
        condition_icon = "🔒" if mapping.move_only_if_empty else "🔓"
        condition_text = "Empty Only" if mapping.move_only_if_empty else "Always Move"
        condition_item = QTableWidgetItem(f"{condition_icon} {condition_text}")
        condition_item.setTextAlignment(Qt.AlignCenter)
        condition_item.setToolTip(
            "Only moves when destination is empty" if mapping.move_only_if_empty
            else "Moves regardless of existing files"
        )
        self.mappings_table.setItem(row, 4, condition_item)

        # Stats with enhanced display
        stats_text = f"✅ {mapping.total_moved} moved"
        if mapping.last_move_date:
            date_str = mapping.last_move_date[:10]
            stats_text += f"\n🕒 {date_str}"
        stats_item = QTableWidgetItem(stats_text)
        stats_item.setTextAlignment(Qt.AlignCenter)
        stats_item.setToolTip(f"Total moved: {mapping.total_moved}\nLast: {mapping.last_move_date or 'Never'}")
        self.mappings_table.setItem(row, 5, stats_item)

        # Color code the row based on validation
        is_valid, _ = mapping.validate()
        if not is_valid:
            for col in range(6):
                item = self.mappings_table.item(row, col)
                if item:
                    item.setBackground(QColor("#3d2020"))
                    item.setForeground(QColor("#ff8888"))

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
                QMessageBox.information(self, "✅ Success", "Mapping added successfully!")
            else:
                QMessageBox.warning(self, "⚠️ Error", "Failed to add mapping. Check if source folder already mapped.")

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
                    QMessageBox.information(self, "✅ Success", "Mapping updated successfully!")
                else:
                    QMessageBox.warning(self, "⚠️ Error", "Failed to update mapping.")

    def delete_selected_mapping(self):
        """Delete the selected mapping"""
        selected_rows = self.mappings_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        reply = QMessageBox.question(
            self, "🗑️ Confirm Delete",
            "Are you sure you want to delete this mapping?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            row = selected_rows[0].row()
            mapping_id = self.mappings_table.item(row, 1).data(Qt.UserRole)

            if self.mapping_manager.delete_mapping(mapping_id):
                self.load_existing_mappings()
                QMessageBox.information(self, "✅ Success", "Mapping deleted successfully!")
            else:
                QMessageBox.warning(self, "⚠️ Error", "Failed to delete mapping.")

    def scan_source_folders(self):
        """Scan for source folders and suggest new mappings"""
        links_grabber_path = Path.home() / "Desktop" / "Links Grabber"

        if not links_grabber_path.exists():
            QMessageBox.warning(
                self, "📁 Folder Not Found",
                f"Links Grabber folder not found at:\n{links_grabber_path}\n\n"
                "Please ensure the folder exists."
            )
            return

        # Get all subdirectories
        subdirs = [d for d in links_grabber_path.iterdir() if d.is_dir()]

        if not subdirs:
            QMessageBox.information(
                self, "ℹ️ No Folders Found",
                "No subdirectories found in Links Grabber folder."
            )
            return

        # Check which ones are not already mapped
        existing_sources = {m.source_folder for m in self.mapping_manager.get_all_mappings()}
        new_folders = [str(d) for d in subdirs if str(d) not in existing_sources]

        if not new_folders:
            QMessageBox.information(
                self, "✅ All Mapped",
                "All folders are already mapped!"
            )
            return

        # Show dialog with new folders
        msg = f"Found {len(new_folders)} unmapped folders:\n\n"
        msg += "\n".join([f"📂 {Path(f).name}" for f in new_folders[:10]])
        if len(new_folders) > 10:
            msg += f"\n... and {len(new_folders) - 10} more"

        msg += "\n\nWould you like to add mappings for these folders?"

        reply = QMessageBox.question(
            self, "🔍 Add New Mappings",
            msg,
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Add first unmapped folder
            for folder in new_folders[:1]:  # Add one at a time
                self.add_new_mapping()
                break

    def import_config(self):
        """Import configuration from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "📥 Import Configuration",
            str(Path.home() / "Desktop"),
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            reply = QMessageBox.question(
                self, "📥 Import Mode",
                "How would you like to import?\n\n"
                "✅ Merge: Keep existing mappings and add new ones\n"
                "🔄 Replace: Delete existing mappings and import new ones",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )

            if reply == QMessageBox.Cancel:
                return

            merge = (reply == QMessageBox.Yes)

            if self.mapping_manager.import_config(Path(file_path), merge=merge):
                self.load_existing_mappings()
                mode_text = "merged" if merge else "replaced"
                QMessageBox.information(self, "✅ Success", f"Configuration {mode_text} successfully!")
            else:
                QMessageBox.warning(self, "⚠️ Error", "Failed to import configuration.")

    def export_config(self):
        """Export configuration to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "📤 Export Configuration",
            str(Path.home() / "Desktop" / "folder_mappings.json"),
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            if self.mapping_manager.export_config(Path(file_path)):
                QMessageBox.information(
                    self, "✅ Success",
                    f"Configuration exported successfully to:\n\n{file_path}"
                )
            else:
                QMessageBox.warning(self, "⚠️ Error", "Failed to export configuration.")

    def update_stats(self):
        """Update statistics labels"""
        stats = self.mapping_manager.get_stats()

        # Update with color-coded values
        self.total_label.setText(
            f"<b>Total Mappings:</b> <span style='color: #00d4ff; font-size: 16px;'>{stats['total_mappings']}</span>"
        )
        self.active_label.setText(
            f"<b>Active:</b> <span style='color: #00ff88; font-size: 16px;'>{stats['active_mappings']}</span>"
        )
        self.moved_label.setText(
            f"<b>Videos Moved:</b> <span style='color: #ffd700; font-size: 16px;'>{stats['total_videos_moved']}</span>"
        )

    def accept(self):
        """Save and close dialog"""
        if self.mapping_manager.save():
            self.mappings_updated.emit()
            super().accept()
        else:
            QMessageBox.warning(self, "⚠️ Error", "Failed to save mappings.")


class MappingEditDialog(QDialog):
    """Dialog for editing a single mapping - Enhanced Professional Version"""

    def __init__(self, parent, mapping: Optional[FolderMapping], mapping_manager: FolderMappingManager):
        super().__init__(parent)
        self.mapping = mapping
        self.mapping_manager = mapping_manager
        self.is_edit_mode = mapping is not None

        title = "✏️ Edit Mapping" if self.is_edit_mode else "➕ Add New Mapping"
        self.setWindowTitle(title)

        # Responsive sizing
        self.resize(750, 600)  # Default size
        self.setMinimumSize(600, 450)  # Minimum size for usability

        # Make dialog resizable
        self.setSizeGripEnabled(True)

        # Apply enhanced dark theme
        self.setStyleSheet(parent.styleSheet())

        self.init_ui()

        if self.is_edit_mode:
            self.load_mapping_data()

    def init_ui(self):
        """Initialize the UI with scrollable content"""
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        # Content widget inside scroll area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(25, 25, 25, 25)

        # Header
        header_label = QLabel("✏️ Edit Mapping" if self.is_edit_mode else "➕ Add New Mapping")
        header_label.setObjectName("headerLabel")
        content_layout.addWidget(header_label)

        # Info label
        info_label = QLabel(
            "📝 Configure the folder mapping settings. Select source and destination folders, "
            "set daily limits, and choose move conditions."
        )
        info_label.setObjectName("infoLabel")
        info_label.setWordWrap(True)
        content_layout.addWidget(info_label)

        # Source folder group
        source_group = QGroupBox("📂 Source Folder (Links Grabber)")
        source_layout = QVBoxLayout()
        source_layout.setSpacing(10)

        self.source_display = QLineEdit()
        self.source_display.setPlaceholderText("No folder selected...")
        self.source_display.setReadOnly(True)
        self.source_display.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e2e;
                color: #00d4ff;
                padding: 12px;
                border: 2px solid #3a3a4a;
                border-radius: 6px;
                font-size: 13px;
            }
        """)
        source_layout.addWidget(self.source_display)

        source_btn_layout = QHBoxLayout()
        self.source_browse_btn = QPushButton("📁 Browse Source Folder")
        self.source_browse_btn.setObjectName("actionBtn")
        self.source_browse_btn.setToolTip("Select the source folder containing downloaded videos")
        self.source_browse_btn.clicked.connect(self.browse_source)
        source_btn_layout.addWidget(self.source_browse_btn)

        self.source_quick_btn = QPushButton("⚡ Quick: Links Grabber")
        self.source_quick_btn.setObjectName("actionBtn")
        self.source_quick_btn.setToolTip("Quickly browse to Desktop/Links Grabber")
        self.source_quick_btn.clicked.connect(self.quick_select_source)
        source_btn_layout.addWidget(self.source_quick_btn)

        source_layout.addLayout(source_btn_layout)
        source_group.setLayout(source_layout)
        content_layout.addWidget(source_group)

        # Destination folder group
        dest_group = QGroupBox("📁 Destination Folder (Creators Data)")
        dest_layout = QVBoxLayout()
        dest_layout.setSpacing(10)

        self.dest_display = QLineEdit()
        self.dest_display.setPlaceholderText("No folder selected...")
        self.dest_display.setReadOnly(True)
        self.dest_display.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e2e;
                color: #00ff88;
                padding: 12px;
                border: 2px solid #3a3a4a;
                border-radius: 6px;
                font-size: 13px;
            }
        """)
        dest_layout.addWidget(self.dest_display)

        dest_btn_layout = QHBoxLayout()
        self.dest_browse_btn = QPushButton("📁 Browse Destination Folder")
        self.dest_browse_btn.setObjectName("actionBtn")
        self.dest_browse_btn.setToolTip("Select the destination folder for videos")
        self.dest_browse_btn.clicked.connect(self.browse_destination)
        dest_btn_layout.addWidget(self.dest_browse_btn)

        self.dest_quick_btn = QPushButton("⚡ Quick: Creators Data")
        self.dest_quick_btn.setObjectName("actionBtn")
        self.dest_quick_btn.setToolTip("Quickly browse to Desktop/creators data")
        self.dest_quick_btn.clicked.connect(self.quick_select_dest)
        dest_btn_layout.addWidget(self.dest_quick_btn)

        dest_layout.addLayout(dest_btn_layout)
        dest_group.setLayout(dest_layout)
        content_layout.addWidget(dest_group)

        # Settings group
        settings_group = QGroupBox("⚙️ Move Settings")
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(15)

        # Daily limit
        limit_layout = QHBoxLayout()
        limit_label = QLabel("📊 Daily Limit (videos per day):")
        limit_label.setMinimumWidth(200)
        limit_layout.addWidget(limit_label)

        self.limit_spin = QSpinBox()
        self.limit_spin.setMinimum(1)
        self.limit_spin.setMaximum(100)
        self.limit_spin.setValue(5)
        self.limit_spin.setSuffix(" videos")
        self.limit_spin.setToolTip("Maximum number of videos to move per day")
        limit_layout.addWidget(self.limit_spin)
        limit_layout.addStretch()
        settings_layout.addLayout(limit_layout)

        # Move condition with radio buttons
        condition_label = QLabel("⚙️ Move Condition:")
        settings_layout.addWidget(condition_label)

        self.condition_group = QButtonGroup()

        self.empty_radio = QRadioButton("🔒 Move only when destination is empty")
        self.empty_radio.setChecked(True)
        self.empty_radio.setToolTip("Videos will only be moved if the destination folder is empty")
        self.condition_group.addButton(self.empty_radio, 0)
        settings_layout.addWidget(self.empty_radio)

        self.always_radio = QRadioButton("🔓 Always move (regardless of existing files)")
        self.always_radio.setToolTip("Videos will be moved even if destination folder contains files")
        self.condition_group.addButton(self.always_radio, 1)
        settings_layout.addWidget(self.always_radio)

        settings_group.setLayout(settings_layout)
        content_layout.addWidget(settings_group)

        # Enabled checkbox
        self.enabled_checkbox = QCheckBox("✅ Enable this mapping immediately")
        self.enabled_checkbox.setChecked(True)
        self.enabled_checkbox.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        self.enabled_checkbox.setToolTip("If unchecked, this mapping will be saved but not used")
        content_layout.addWidget(self.enabled_checkbox)

        # Set the content widget in scroll area
        scroll_area.setWidget(content_widget)

        # Add scroll area to main layout
        main_layout.addWidget(scroll_area, 1)  # Stretch factor 1

        # Bottom buttons (outside scroll area - always visible)
        button_container = QWidget()
        button_container.setStyleSheet("background-color: #1a1a2e; padding: 10px;")
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(15)
        button_layout.setContentsMargins(20, 10, 20, 10)
        button_layout.addStretch()

        self.ok_btn = QPushButton("✅ Save Mapping")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setMinimumWidth(140)
        self.ok_btn.setToolTip("Save this mapping configuration")
        button_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumWidth(140)
        self.cancel_btn.setToolTip("Discard changes")
        button_layout.addWidget(self.cancel_btn)

        # Add button container to main layout
        main_layout.addWidget(button_container, 0)  # Stretch factor 0 (fixed height)

        self.setLayout(main_layout)

    def load_mapping_data(self):
        """Load data from existing mapping"""
        if not self.mapping:
            return

        self.source_display.setText(self.mapping.source_folder)
        self.dest_display.setText(self.mapping.destination_folder)
        self.limit_spin.setValue(self.mapping.daily_limit)

        # Set condition radio button
        if self.mapping.move_only_if_empty:
            self.empty_radio.setChecked(True)
        else:
            self.always_radio.setChecked(True)

        self.enabled_checkbox.setChecked(self.mapping.enabled)

    def quick_select_source(self):
        """Quick select Links Grabber folder"""
        default_path = Path.home() / "Desktop" / "Links Grabber"
        if default_path.exists():
            folder = QFileDialog.getExistingDirectory(
                self, "Select Source Folder (Creator Folder)",
                str(default_path)
            )
            if folder:
                self.source_display.setText(folder)
        else:
            QMessageBox.warning(
                self, "⚠️ Folder Not Found",
                f"Links Grabber folder not found at:\n{default_path}"
            )

    def quick_select_dest(self):
        """Quick select Creators Data folder"""
        default_path = Path.home() / "Desktop" / "creators data"
        if default_path.exists():
            folder = QFileDialog.getExistingDirectory(
                self, "Select Destination Folder (Page Folder)",
                str(default_path)
            )
            if folder:
                self.dest_display.setText(folder)
        else:
            QMessageBox.warning(
                self, "⚠️ Folder Not Found",
                f"Creators Data folder not found at:\n{default_path}"
            )

    def browse_source(self):
        """Browse for source folder"""
        default_path = Path.home() / "Desktop"
        folder = QFileDialog.getExistingDirectory(
            self, "Select Source Folder",
            str(default_path)
        )

        if folder:
            self.source_display.setText(folder)

    def browse_destination(self):
        """Browse for destination folder"""
        default_path = Path.home() / "Desktop"
        folder = QFileDialog.getExistingDirectory(
            self, "Select Destination Folder",
            str(default_path)
        )

        if folder:
            self.dest_display.setText(folder)

    def get_mapping(self) -> FolderMapping:
        """Get the configured mapping"""
        mapping_id = self.mapping.id if self.is_edit_mode else None

        return FolderMapping(
            mapping_id=mapping_id,
            source_folder=self.source_display.text(),
            destination_folder=self.dest_display.text(),
            daily_limit=self.limit_spin.value(),
            move_only_if_empty=self.empty_radio.isChecked(),
            enabled=self.enabled_checkbox.isChecked()
        )

    def accept(self):
        """Validate and accept"""
        if not self.source_display.text():
            QMessageBox.warning(self, "⚠️ Validation Error", "Please select a source folder.")
            return

        if not self.dest_display.text():
            QMessageBox.warning(self, "⚠️ Validation Error", "Please select a destination folder.")
            return

        mapping = self.get_mapping()
        is_valid, error = mapping.validate()

        if not is_valid:
            QMessageBox.warning(self, "⚠️ Validation Error", error)
            return

        super().accept()
