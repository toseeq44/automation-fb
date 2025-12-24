"""
modules/video_editor/preset_builder_dialog.py
Visual Preset Builder - Create and edit video editing presets
Like Adobe Premiere/CapCut preset editor
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
    QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QScrollArea, QWidget, QFormLayout, QMessageBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from typing import Dict, Any, Optional, List
import os

from modules.logging.logger import get_logger
from modules.video_editor.preset_manager import EditingPreset, PresetManager
from modules.video_editor.operation_library import OperationLibrary, ParameterDef

logger = get_logger(__name__)


class OperationParameterWidget(QWidget):
    """Widget for editing a single operation parameter"""

    valueChanged = pyqtSignal()

    def __init__(self, param_def: ParameterDef, initial_value: Any = None):
        super().__init__()
        self.param_def = param_def
        self.value_widget = None

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Create appropriate widget based on parameter type
        if param_def.param_type == 'int':
            self.value_widget = QSpinBox()
            if param_def.min_val is not None:
                self.value_widget.setMinimum(int(param_def.min_val))
            else:
                self.value_widget.setMinimum(-999999)
            if param_def.max_val is not None:
                self.value_widget.setMaximum(int(param_def.max_val))
            else:
                self.value_widget.setMaximum(999999)
            if initial_value is not None:
                self.value_widget.setValue(int(initial_value))
            elif param_def.default is not None:
                self.value_widget.setValue(int(param_def.default))
            self.value_widget.valueChanged.connect(self.valueChanged.emit)

        elif param_def.param_type == 'float':
            self.value_widget = QDoubleSpinBox()
            self.value_widget.setDecimals(2)
            self.value_widget.setSingleStep(0.1)
            if param_def.min_val is not None:
                self.value_widget.setMinimum(float(param_def.min_val))
            else:
                self.value_widget.setMinimum(-999999.0)
            if param_def.max_val is not None:
                self.value_widget.setMaximum(float(param_def.max_val))
            else:
                self.value_widget.setMaximum(999999.0)
            if initial_value is not None:
                self.value_widget.setValue(float(initial_value))
            elif param_def.default is not None:
                self.value_widget.setValue(float(param_def.default))
            self.value_widget.valueChanged.connect(self.valueChanged.emit)

        elif param_def.param_type == 'bool':
            self.value_widget = QCheckBox()
            if initial_value is not None:
                self.value_widget.setChecked(bool(initial_value))
            elif param_def.default is not None:
                self.value_widget.setChecked(bool(param_def.default))
            self.value_widget.stateChanged.connect(self.valueChanged.emit)

        elif param_def.param_type == 'str':
            if param_def.choices:
                # Dropdown for choices
                self.value_widget = QComboBox()
                self.value_widget.addItems(param_def.choices)
                if initial_value is not None:
                    index = self.value_widget.findText(str(initial_value))
                    if index >= 0:
                        self.value_widget.setCurrentIndex(index)
                elif param_def.default is not None:
                    index = self.value_widget.findText(str(param_def.default))
                    if index >= 0:
                        self.value_widget.setCurrentIndex(index)
                self.value_widget.currentTextChanged.connect(self.valueChanged.emit)
            else:
                # Line edit for free text
                self.value_widget = QLineEdit()
                if initial_value is not None:
                    self.value_widget.setText(str(initial_value))
                elif param_def.default is not None:
                    self.value_widget.setText(str(param_def.default))
                self.value_widget.textChanged.connect(self.valueChanged.emit)

        else:
            # Generic line edit for other types
            self.value_widget = QLineEdit()
            if initial_value is not None:
                self.value_widget.setText(str(initial_value))
            elif param_def.default is not None:
                self.value_widget.setText(str(param_def.default))
            self.value_widget.textChanged.connect(self.valueChanged.emit)

        layout.addWidget(self.value_widget)
        self.setLayout(layout)

    def get_value(self) -> Any:
        """Get current parameter value"""
        if isinstance(self.value_widget, QSpinBox):
            return self.value_widget.value()
        elif isinstance(self.value_widget, QDoubleSpinBox):
            return self.value_widget.value()
        elif isinstance(self.value_widget, QCheckBox):
            return self.value_widget.isChecked()
        elif isinstance(self.value_widget, QComboBox):
            return self.value_widget.currentText()
        elif isinstance(self.value_widget, QLineEdit):
            text = self.value_widget.text()
            # Try to parse as appropriate type
            if self.param_def.param_type == 'int':
                try:
                    return int(text)
                except ValueError:
                    return 0
            elif self.param_def.param_type == 'float':
                try:
                    return float(text)
                except ValueError:
                    return 0.0
            return text
        return None


class PresetBuilderDialog(QDialog):
    """
    Visual Preset Builder Dialog
    3-panel layout for creating/editing video editing presets
    """

    def __init__(self, preset: EditingPreset = None, parent=None):
        super().__init__(parent)

        self.preset = preset
        self.operation_library = OperationLibrary()
        self.preset_manager = PresetManager()

        self.current_operation_index = -1
        self.param_widgets: Dict[str, OperationParameterWidget] = {}

        self.setup_ui()
        self.load_preset_data()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Preset Builder - Visual Editor")
        self.setMinimumSize(1200, 800)

        main_layout = QVBoxLayout()

        # ========== TOP: Preset Metadata ==========
        metadata_group = QGroupBox("Preset Information")
        metadata_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter preset name...")
        metadata_layout.addRow("Name:", self.name_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText("Enter preset description...")
        metadata_layout.addRow("Description:", self.description_edit)

        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("Your name")
        metadata_layout.addRow("Author:", self.author_edit)

        self.category_combo = QComboBox()
        self.category_combo.addItems([
            EditingPreset.CATEGORY_VIDEO,
            EditingPreset.CATEGORY_AUDIO,
            EditingPreset.CATEGORY_SOCIAL_MEDIA,
            EditingPreset.CATEGORY_PROFESSIONAL,
            EditingPreset.CATEGORY_ARTISTIC,
            EditingPreset.CATEGORY_CUSTOM
        ])
        metadata_layout.addRow("Category:", self.category_combo)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Comma-separated tags (e.g., tiktok, vertical, social)")
        metadata_layout.addRow("Tags:", self.tags_edit)

        metadata_group.setLayout(metadata_layout)
        main_layout.addWidget(metadata_group)

        # ========== MIDDLE: 3-Panel Splitter ==========
        splitter = QSplitter(Qt.Horizontal)

        # LEFT PANEL: Operation Library
        left_panel = self.create_operation_library_panel()
        splitter.addWidget(left_panel)

        # CENTER PANEL: Operation Stack
        center_panel = self.create_operation_stack_panel()
        splitter.addWidget(center_panel)

        # RIGHT PANEL: Parameter Editor
        right_panel = self.create_parameter_editor_panel()
        splitter.addWidget(right_panel)

        # Set splitter sizes (30% - 30% - 40%)
        splitter.setSizes([360, 360, 480])

        main_layout.addWidget(splitter, 1)

        # ========== BOTTOM: Export Settings & Actions ==========
        bottom_layout = QHBoxLayout()

        # Export Settings Group
        export_group = QGroupBox("Export Settings")
        export_layout = QFormLayout()

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['high', 'medium', 'low'])
        export_layout.addRow("Quality:", self.quality_combo)

        self.format_combo = QComboBox()
        self.format_combo.addItems(['mp4', 'avi', 'mov', 'mkv', 'webm'])
        export_layout.addRow("Format:", self.format_combo)

        export_group.setLayout(export_layout)
        bottom_layout.addWidget(export_group)

        # Action Buttons
        button_layout = QVBoxLayout()

        self.save_btn = QPushButton("💾 Save Preset")
        self.save_btn.clicked.connect(self.save_preset)
        button_layout.addWidget(self.save_btn)

        self.validate_btn = QPushButton("✓ Validate")
        self.validate_btn.clicked.connect(self.validate_preset)
        button_layout.addWidget(self.validate_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        button_layout.addStretch()

        bottom_layout.addLayout(button_layout)

        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

    def create_operation_library_panel(self) -> QWidget:
        """Create the operation library panel (left)"""
        panel = QWidget()
        layout = QVBoxLayout()

        label = QLabel("Operation Library")
        label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(label)

        # Category tabs
        self.category_tabs = QTabWidget()

        categories = self.operation_library.get_categories()
        for category in categories:
            operations = self.operation_library.get_operations_by_category(category)

            list_widget = QListWidget()
            for op in operations:
                display_text = f"{op.icon or '•'} {op.display_name}"
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, op.name)  # Store operation name
                item.setToolTip(op.description)
                list_widget.addItem(item)

            list_widget.itemDoubleClicked.connect(self.add_operation_to_stack)

            self.category_tabs.addTab(list_widget, category)

        layout.addWidget(self.category_tabs)

        # Add button
        add_btn = QPushButton("➕ Add to Stack")
        add_btn.clicked.connect(self.add_selected_operation)
        layout.addWidget(add_btn)

        panel.setLayout(layout)
        return panel

    def create_operation_stack_panel(self) -> QWidget:
        """Create the operation stack panel (center)"""
        panel = QWidget()
        layout = QVBoxLayout()

        label = QLabel("Operation Stack")
        label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(label)

        info_label = QLabel("Operations are applied in order from top to bottom")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)

        self.stack_list = QListWidget()
        self.stack_list.currentRowChanged.connect(self.on_stack_selection_changed)
        layout.addWidget(self.stack_list)

        # Stack controls
        controls_layout = QHBoxLayout()

        self.move_up_btn = QPushButton("↑ Move Up")
        self.move_up_btn.clicked.connect(self.move_operation_up)
        controls_layout.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("↓ Move Down")
        self.move_down_btn.clicked.connect(self.move_operation_down)
        controls_layout.addWidget(self.move_down_btn)

        self.remove_btn = QPushButton("🗑 Remove")
        self.remove_btn.clicked.connect(self.remove_operation)
        controls_layout.addWidget(self.remove_btn)

        layout.addLayout(controls_layout)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_stack)
        layout.addWidget(self.clear_btn)

        panel.setLayout(layout)
        return panel

    def create_parameter_editor_panel(self) -> QWidget:
        """Create the parameter editor panel (right)"""
        panel = QWidget()
        layout = QVBoxLayout()

        label = QLabel("Parameter Editor")
        label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(label)

        self.param_info_label = QLabel("Select an operation to edit parameters")
        self.param_info_label.setStyleSheet("color: gray;")
        layout.addWidget(self.param_info_label)

        # Scrollable parameter form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(400)

        self.param_container = QWidget()
        self.param_layout = QFormLayout()
        self.param_container.setLayout(self.param_layout)

        scroll.setWidget(self.param_container)
        layout.addWidget(scroll)

        # Apply button
        self.apply_params_btn = QPushButton("✓ Apply Changes")
        self.apply_params_btn.clicked.connect(self.apply_parameter_changes)
        self.apply_params_btn.setEnabled(False)
        layout.addWidget(self.apply_params_btn)

        panel.setLayout(layout)
        return panel

    def add_selected_operation(self):
        """Add selected operation from library to stack"""
        current_tab = self.category_tabs.currentWidget()
        if isinstance(current_tab, QListWidget):
            current_item = current_tab.currentItem()
            if current_item:
                self.add_operation_to_stack(current_item)

    def add_operation_to_stack(self, item: QListWidgetItem):
        """Add operation to stack"""
        op_name = item.data(Qt.UserRole)
        op_def = self.operation_library.get_operation(op_name)

        if not op_def:
            return

        # Create default parameters
        params = {}
        for param_name, param_def in op_def.parameters.items():
            if param_def.default is not None:
                params[param_name] = param_def.default
            elif not param_def.required:
                params[param_name] = None

        # Add to stack
        display_text = f"{op_def.icon or '•'} {op_def.display_name}"
        stack_item = QListWidgetItem(display_text)
        stack_item.setData(Qt.UserRole, {'operation': op_name, 'params': params})

        self.stack_list.addItem(stack_item)

        logger.info(f"Added operation to stack: {op_name}")

    def on_stack_selection_changed(self, index: int):
        """Handle stack selection change"""
        self.current_operation_index = index

        if index < 0:
            self.param_info_label.setText("Select an operation to edit parameters")
            self.clear_parameter_editor()
            self.apply_params_btn.setEnabled(False)
            return

        # Get selected operation
        item = self.stack_list.item(index)
        op_data = item.data(Qt.UserRole)
        op_name = op_data['operation']
        op_params = op_data['params']

        op_def = self.operation_library.get_operation(op_name)

        if not op_def:
            return

        # Update parameter editor
        self.param_info_label.setText(f"Editing: {op_def.display_name}")
        self.load_parameter_editor(op_def, op_params)
        self.apply_params_btn.setEnabled(True)

    def load_parameter_editor(self, op_def, current_params: Dict[str, Any]):
        """Load parameter editor for operation"""
        # Clear previous widgets
        self.clear_parameter_editor()

        # Create parameter widgets
        for param_name, param_def in op_def.parameters.items():
            current_value = current_params.get(param_name)

            param_widget = OperationParameterWidget(param_def, current_value)
            self.param_widgets[param_name] = param_widget

            # Create label with description tooltip
            label = QLabel(f"{param_name}:")
            if param_def.description:
                label.setToolTip(param_def.description)

            # Add required indicator
            if param_def.required:
                label.setText(f"{param_name}*:")
                label.setStyleSheet("font-weight: bold;")

            self.param_layout.addRow(label, param_widget)

    def clear_parameter_editor(self):
        """Clear parameter editor"""
        # Remove all widgets from layout
        while self.param_layout.count():
            item = self.param_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.param_widgets.clear()

    def apply_parameter_changes(self):
        """Apply parameter changes to selected operation"""
        if self.current_operation_index < 0:
            return

        item = self.stack_list.item(self.current_operation_index)
        op_data = item.data(Qt.UserRole)

        # Get updated parameters
        updated_params = {}
        for param_name, param_widget in self.param_widgets.items():
            updated_params[param_name] = param_widget.get_value()

        # Update operation data
        op_data['params'] = updated_params
        item.setData(Qt.UserRole, op_data)

        logger.info(f"Updated parameters for operation at index {self.current_operation_index}")
        QMessageBox.information(self, "Success", "Parameters updated!")

    def move_operation_up(self):
        """Move selected operation up in stack"""
        current_row = self.stack_list.currentRow()

        if current_row > 0:
            item = self.stack_list.takeItem(current_row)
            self.stack_list.insertItem(current_row - 1, item)
            self.stack_list.setCurrentRow(current_row - 1)

    def move_operation_down(self):
        """Move selected operation down in stack"""
        current_row = self.stack_list.currentRow()

        if current_row < self.stack_list.count() - 1:
            item = self.stack_list.takeItem(current_row)
            self.stack_list.insertItem(current_row + 1, item)
            self.stack_list.setCurrentRow(current_row + 1)

    def remove_operation(self):
        """Remove selected operation from stack"""
        current_row = self.stack_list.currentRow()

        if current_row >= 0:
            self.stack_list.takeItem(current_row)
            self.current_operation_index = -1
            self.clear_parameter_editor()

    def clear_stack(self):
        """Clear all operations from stack"""
        reply = QMessageBox.question(
            self, "Clear Stack",
            "Are you sure you want to remove all operations?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.stack_list.clear()
            self.current_operation_index = -1
            self.clear_parameter_editor()

    def load_preset_data(self):
        """Load preset data into UI"""
        if not self.preset:
            # New preset - set defaults
            self.name_edit.setText("")
            self.description_edit.setText("")
            self.author_edit.setText("User")
            self.category_combo.setCurrentText(EditingPreset.CATEGORY_CUSTOM)
            self.tags_edit.setText("")
            self.quality_combo.setCurrentText("high")
            self.format_combo.setCurrentText("mp4")
            return

        # Load existing preset
        self.name_edit.setText(self.preset.name)
        self.description_edit.setText(self.preset.description)
        self.author_edit.setText(self.preset.author)
        self.category_combo.setCurrentText(self.preset.category)
        self.tags_edit.setText(", ".join(self.preset.tags))

        # Load operations
        for op in self.preset.operations:
            op_name = op['operation']
            op_params = op['params']

            op_def = self.operation_library.get_operation(op_name)
            if op_def:
                display_text = f"{op_def.icon or '•'} {op_def.display_name}"
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, {'operation': op_name, 'params': op_params})
                self.stack_list.addItem(item)

        # Load export settings
        if self.preset.export_settings:
            self.quality_combo.setCurrentText(self.preset.export_settings.get('quality', 'high'))
            self.format_combo.setCurrentText(self.preset.export_settings.get('format', 'mp4'))

    def validate_preset(self):
        """Validate current preset configuration"""
        from modules.video_editor.preset_validator import PresetValidator

        preset = self.build_preset()
        if not preset:
            QMessageBox.warning(self, "Validation Error", "Please fill in preset name")
            return

        validator = PresetValidator()
        validator.set_operation_registry(self.operation_library)

        result = validator.validate_preset_data(preset.to_dict())

        if result.valid:
            msg = f"✓ Preset is valid!\n\n{len(preset.operations)} operations configured."
            if result.warnings:
                msg += f"\n\nWarnings:\n" + "\n".join(f"  • {w}" for w in result.warnings)
            QMessageBox.information(self, "Validation Success", msg)
        else:
            msg = "✗ Validation failed!\n\nErrors:\n" + "\n".join(f"  • {e}" for e in result.errors)
            if result.warnings:
                msg += f"\n\nWarnings:\n" + "\n".join(f"  • {w}" for w in result.warnings)
            QMessageBox.critical(self, "Validation Failed", msg)

    def build_preset(self) -> Optional[EditingPreset]:
        """Build preset from UI data"""
        name = self.name_edit.text().strip()

        if not name:
            return None

        preset = EditingPreset(
            name=name,
            description=self.description_edit.toPlainText(),
            author=self.author_edit.text() or "User",
            category=self.category_combo.currentText()
        )

        # Add tags
        tags_text = self.tags_edit.text()
        if tags_text:
            preset.tags = [t.strip() for t in tags_text.split(',') if t.strip()]

        # Add operations
        for i in range(self.stack_list.count()):
            item = self.stack_list.item(i)
            op_data = item.data(Qt.UserRole)
            preset.add_operation(op_data['operation'], op_data['params'])

        # Add export settings
        preset.export_settings['quality'] = self.quality_combo.currentText()
        preset.export_settings['format'] = self.format_combo.currentText()

        return preset

    def save_preset(self):
        """Save preset"""
        preset = self.build_preset()

        if not preset:
            QMessageBox.warning(self, "Error", "Please enter a preset name")
            return

        if len(preset.operations) == 0:
            reply = QMessageBox.question(
                self, "No Operations",
                "This preset has no operations. Save anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        try:
            filepath = self.preset_manager.save_preset(preset, folder=PresetManager.FOLDER_USER)
            QMessageBox.information(
                self, "Success",
                f"Preset saved successfully!\n\n{filepath}"
            )
            self.preset = preset
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save preset: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save preset:\n{e}")
