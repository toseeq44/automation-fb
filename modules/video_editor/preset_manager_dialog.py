"""
modules/video_editor/preset_manager_dialog.py
Preset Manager Dialog - Browse, manage, import/export presets
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QGroupBox, QLabel, QTextEdit,
    QMessageBox, QFileDialog, QHeaderView, QWidget, QFormLayout,
    QMenu, QAction, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from typing import Dict, Any, Optional, List
import os

from modules.logging.logger import get_logger
from modules.video_editor.preset_manager import EditingPreset, PresetManager
from modules.video_editor.preset_builder_dialog import PresetBuilderDialog

logger = get_logger(__name__)


class PresetManagerDialog(QDialog):
    """
    Preset Manager Dialog
    Browse, manage, import, and export presets
    """

    preset_selected = pyqtSignal(str, str)  # preset_name, folder

    def __init__(self, parent=None):
        super().__init__(parent)

        self.preset_manager = PresetManager()
        self.current_preset_data = None
        self.current_folder = None

        self.setup_ui()
        self.refresh_preset_list()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Preset Manager")
        self.setMinimumSize(1000, 700)

        main_layout = QVBoxLayout()

        # ========== TOP: Title and Actions ==========
        title_layout = QHBoxLayout()

        title_label = QLabel("Video Editing Presets")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        self.new_preset_btn = QPushButton("➕ New Preset")
        self.new_preset_btn.clicked.connect(self.create_new_preset)
        title_layout.addWidget(self.new_preset_btn)

        self.import_btn = QPushButton("📥 Import")
        self.import_btn.clicked.connect(self.import_preset)
        title_layout.addWidget(self.import_btn)

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_preset_list)
        title_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(title_layout)

        # ========== MIDDLE: Tabbed Preset Lists ==========
        self.tabs = QTabWidget()

        # System Presets Tab
        self.system_table = self.create_preset_table()
        self.tabs.addTab(self.system_table, "📦 System Presets")

        # User Presets Tab
        self.user_table = self.create_preset_table()
        self.tabs.addTab(self.user_table, "👤 User Presets")

        # Imported Presets Tab
        self.imported_table = self.create_preset_table()
        self.tabs.addTab(self.imported_table, "📥 Imported Presets")

        self.tabs.currentChanged.connect(self.on_tab_changed)

        main_layout.addWidget(self.tabs, 1)

        # ========== BOTTOM: Preset Details Panel ==========
        details_group = QGroupBox("Preset Details")
        details_layout = QVBoxLayout()

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setText("Select a preset to view details")
        details_layout.addWidget(self.details_text)

        details_group.setLayout(details_layout)
        main_layout.addWidget(details_group)

        # ========== ACTION BUTTONS ==========
        action_layout = QHBoxLayout()

        self.apply_btn = QPushButton("✓ Apply Preset")
        self.apply_btn.clicked.connect(self.apply_preset)
        self.apply_btn.setEnabled(False)
        action_layout.addWidget(self.apply_btn)

        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self.edit_preset)
        self.edit_btn.setEnabled(False)
        action_layout.addWidget(self.edit_btn)

        self.duplicate_btn = QPushButton("📋 Duplicate")
        self.duplicate_btn.clicked.connect(self.duplicate_preset)
        self.duplicate_btn.setEnabled(False)
        action_layout.addWidget(self.duplicate_btn)

        self.export_btn = QPushButton("📤 Export")
        self.export_btn.clicked.connect(self.export_preset)
        self.export_btn.setEnabled(False)
        action_layout.addWidget(self.export_btn)

        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.clicked.connect(self.delete_preset)
        self.delete_btn.setEnabled(False)
        action_layout.addWidget(self.delete_btn)

        action_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        action_layout.addWidget(self.close_btn)

        main_layout.addLayout(action_layout)

        self.setLayout(main_layout)

    def create_preset_table(self) -> QTableWidget:
        """Create a preset table widget"""
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Name", "Category", "Author", "Operations", "Modified", "Version"
        ])

        # Configure table
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSortingEnabled(True)

        # Set column widths
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Category
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Author
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Operations
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Modified
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Version

        # Connect selection signal
        table.itemSelectionChanged.connect(self.on_preset_selected)
        table.itemDoubleClicked.connect(self.on_preset_double_clicked)

        # Add context menu
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self.show_context_menu)

        return table

    def refresh_preset_list(self):
        """Refresh all preset lists"""
        presets_by_folder = self.preset_manager.list_presets_by_folder()

        # Update system presets
        self.populate_table(
            self.system_table,
            presets_by_folder[PresetManager.FOLDER_SYSTEM],
            PresetManager.FOLDER_SYSTEM
        )

        # Update user presets
        self.populate_table(
            self.user_table,
            presets_by_folder[PresetManager.FOLDER_USER],
            PresetManager.FOLDER_USER
        )

        # Update imported presets
        self.populate_table(
            self.imported_table,
            presets_by_folder[PresetManager.FOLDER_IMPORTED],
            PresetManager.FOLDER_IMPORTED
        )

        logger.info("Preset lists refreshed")

    def populate_table(self, table: QTableWidget, presets: List[Dict[str, Any]], folder: str):
        """Populate table with preset data"""
        table.setSortingEnabled(False)
        table.setRowCount(0)

        for preset_data in presets:
            row = table.rowCount()
            table.insertRow(row)

            # Name
            name_item = QTableWidgetItem(preset_data['name'])
            name_item.setData(Qt.UserRole, preset_data)  # Store full preset data
            name_item.setData(Qt.UserRole + 1, folder)   # Store folder
            table.setItem(row, 0, name_item)

            # Category
            table.setItem(row, 1, QTableWidgetItem(preset_data.get('category', 'Custom')))

            # Author
            table.setItem(row, 2, QTableWidgetItem(preset_data.get('author', 'Unknown')))

            # Operations count
            table.setItem(row, 3, QTableWidgetItem(str(preset_data['operations_count'])))

            # Modified date
            modified = preset_data['modified_at'][:10]  # Just date part
            table.setItem(row, 4, QTableWidgetItem(modified))

            # Version
            version = preset_data.get('preset_version', '1.0')
            table.setItem(row, 5, QTableWidgetItem(version))

        table.setSortingEnabled(True)
        table.sortItems(4, Qt.DescendingOrder)  # Sort by modified date

    def on_tab_changed(self, index: int):
        """Handle tab change"""
        self.on_preset_selected()

    def on_preset_selected(self):
        """Handle preset selection"""
        current_table = self.tabs.currentWidget()

        if not isinstance(current_table, QTableWidget):
            return

        selected_items = current_table.selectedItems()

        if not selected_items:
            self.details_text.setText("Select a preset to view details")
            self.current_preset_data = None
            self.current_folder = None
            self.update_button_states()
            return

        # Get selected preset data
        name_item = current_table.item(selected_items[0].row(), 0)
        preset_data = name_item.data(Qt.UserRole)
        folder = name_item.data(Qt.UserRole + 1)

        self.current_preset_data = preset_data
        self.current_folder = folder

        # Update details
        self.show_preset_details(preset_data)
        self.update_button_states()

    def on_preset_double_clicked(self, item):
        """Handle preset double-click - apply preset"""
        self.apply_preset()

    def show_preset_details(self, preset_data: Dict[str, Any]):
        """Show preset details in details panel"""
        details = f"""
<h3>{preset_data['name']}</h3>

<p><b>Description:</b> {preset_data.get('description', 'No description')}</p>

<p>
<b>Author:</b> {preset_data.get('author', 'Unknown')}<br>
<b>Category:</b> {preset_data.get('category', 'Custom')}<br>
<b>Version:</b> {preset_data.get('preset_version', '1.0')}<br>
<b>Schema:</b> {preset_data.get('schema_version', '1.0')}
</p>

<p>
<b>Operations:</b> {preset_data['operations_count']}<br>
<b>Tags:</b> {', '.join(preset_data.get('tags', [])) if preset_data.get('tags') else 'None'}
</p>

<p>
<b>Created:</b> {preset_data['created_at'][:10]}<br>
<b>Modified:</b> {preset_data['modified_at'][:10]}
</p>
        """

        self.details_text.setHtml(details)

    def update_button_states(self):
        """Update button enabled states based on selection"""
        has_selection = self.current_preset_data is not None
        is_system = self.current_folder == PresetManager.FOLDER_SYSTEM

        self.apply_btn.setEnabled(has_selection)
        self.edit_btn.setEnabled(has_selection and not is_system)
        self.duplicate_btn.setEnabled(has_selection)
        self.export_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection and not is_system)

    def create_new_preset(self):
        """Create a new preset"""
        dialog = PresetBuilderDialog(preset=None, parent=self)

        if dialog.exec_() == QDialog.Accepted:
            self.refresh_preset_list()
            QMessageBox.information(self, "Success", "Preset created successfully!")

    def edit_preset(self):
        """Edit selected preset"""
        if not self.current_preset_data:
            return

        # Load preset
        preset = self.preset_manager.load_preset_from_file(
            self.current_preset_data['filepath']
        )

        if not preset:
            QMessageBox.critical(self, "Error", "Failed to load preset")
            return

        # Open builder dialog
        dialog = PresetBuilderDialog(preset=preset, parent=self)

        if dialog.exec_() == QDialog.Accepted:
            self.refresh_preset_list()
            QMessageBox.information(self, "Success", "Preset updated successfully!")

    def duplicate_preset(self):
        """Duplicate selected preset"""
        if not self.current_preset_data:
            return

        original_name = self.current_preset_data['name']

        # Ask for new name
        new_name, ok = QInputDialog.getText(
            self, "Duplicate Preset",
            f"Enter name for duplicate of '{original_name}':",
            text=f"{original_name} (Copy)"
        )

        if not ok or not new_name:
            return

        # Duplicate
        success = self.preset_manager.duplicate_preset(original_name, new_name)

        if success:
            self.refresh_preset_list()
            QMessageBox.information(self, "Success", f"Preset duplicated as '{new_name}'")
        else:
            QMessageBox.critical(self, "Error", "Failed to duplicate preset")

    def export_preset(self):
        """Export selected preset to file"""
        if not self.current_preset_data:
            return

        preset_name = self.current_preset_data['name']

        # Ask for save location
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Preset",
            f"{preset_name}.preset.json",
            "Preset Files (*.preset.json);;All Files (*)"
        )

        if not filepath:
            return

        # Export
        success = self.preset_manager.export_preset(preset_name, filepath)

        if success:
            QMessageBox.information(self, "Success", f"Preset exported to:\n{filepath}")
        else:
            QMessageBox.critical(self, "Error", "Failed to export preset")

    def import_preset(self):
        """Import preset from file"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Import Preset",
            "",
            "Preset Files (*.preset.json);;All Files (*)"
        )

        if not filepath:
            return

        # Import
        preset = self.preset_manager.import_preset(filepath)

        if preset:
            self.refresh_preset_list()
            QMessageBox.information(
                self, "Success",
                f"Preset '{preset.name}' imported successfully!"
            )
        else:
            QMessageBox.critical(self, "Error", "Failed to import preset")

    def delete_preset(self):
        """Delete selected preset"""
        if not self.current_preset_data:
            return

        if self.current_folder == PresetManager.FOLDER_SYSTEM:
            QMessageBox.warning(self, "Error", "Cannot delete system presets")
            return

        preset_name = self.current_preset_data['name']

        # Confirm deletion
        reply = QMessageBox.question(
            self, "Delete Preset",
            f"Are you sure you want to delete preset '{preset_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        # Delete (pass folder for proper lookup)
        success = self.preset_manager.delete_preset(preset_name, folder=self.current_folder)

        if success:
            self.refresh_preset_list()
            self.current_preset_data = None
            self.current_folder = None
            QMessageBox.information(self, "Success", "Preset deleted")
        else:
            QMessageBox.critical(self, "Error", "Failed to delete preset")

    def apply_preset(self):
        """Apply selected preset (emit signal)"""
        if not self.current_preset_data:
            return

        preset_name = self.current_preset_data['name']
        folder = self.current_folder

        self.preset_selected.emit(preset_name, folder)
        self.accept()

    def show_context_menu(self, position):
        """Show context menu for preset table"""
        current_table = self.tabs.currentWidget()

        if not isinstance(current_table, QTableWidget):
            return

        item = current_table.itemAt(position)

        if not item:
            return

        menu = QMenu()

        apply_action = QAction("✓ Apply Preset", self)
        apply_action.triggered.connect(self.apply_preset)
        menu.addAction(apply_action)

        menu.addSeparator()

        if self.current_folder != PresetManager.FOLDER_SYSTEM:
            edit_action = QAction("✏️ Edit", self)
            edit_action.triggered.connect(self.edit_preset)
            menu.addAction(edit_action)

        duplicate_action = QAction("📋 Duplicate", self)
        duplicate_action.triggered.connect(self.duplicate_preset)
        menu.addAction(duplicate_action)

        menu.addSeparator()

        export_action = QAction("📤 Export", self)
        export_action.triggered.connect(self.export_preset)
        menu.addAction(export_action)

        if self.current_folder != PresetManager.FOLDER_SYSTEM:
            delete_action = QAction("🗑 Delete", self)
            delete_action.triggered.connect(self.delete_preset)
            menu.addAction(delete_action)

        menu.exec_(current_table.viewport().mapToGlobal(position))
