"""
modules/video_editor/editor_mapping_dialog.py
Editor Folder Mapping Dialog - UI for folder mapping configuration
Provides intelligent folder scanning and mapping interface
"""

import os
from pathlib import Path
from typing import Optional, List

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QComboBox, QGroupBox, QRadioButton, QButtonGroup, QFrame,
    QScrollArea, QSpinBox, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from modules.logging.logger import get_logger
from modules.video_editor.editor_folder_manager import (
    EditorFolderMapping, EditorFolderMappingManager, EditorMappingSettings,
    SubfolderMapping, FolderScanner, PlanLimitChecker, VIDEO_EXTENSIONS
)
from modules.video_editor.preset_manager import PresetManager

logger = get_logger(__name__)


class BulkProcessingDialog(QDialog):
    """
    Main Bulk Processing Dialog
    Step-by-step wizard for configuring folder mapping and processing
    """

    # Signal emitted when processing should start
    start_processing = pyqtSignal(dict)

    def __init__(self, parent=None, preset_manager: PresetManager = None):
        super().__init__(parent)
        self.preset_manager = preset_manager or PresetManager()
        self.mapping_manager = EditorFolderMappingManager()
        self.plan_checker = PlanLimitChecker()

        self.current_mapping: Optional[EditorFolderMapping] = None
        self.folder_mode = 'simple'
        self.folder_info = {}

        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Bulk Video Processing")
        self.setMinimumSize(1000, 750)
        self.resize(1100, 800)
        self.setModal(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header with plan info
        header = self.create_header()
        main_layout.addWidget(header)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)

        # Step 1: Folder Selection
        folder_group = self.create_folder_selection_group()
        content_layout.addWidget(folder_group)

        # Step 2: Mapping Configuration (shown after scan)
        self.mapping_group = self.create_mapping_group()
        self.mapping_group.setVisible(False)
        content_layout.addWidget(self.mapping_group)

        # Step 3: Settings
        self.settings_group = self.create_settings_group()
        self.settings_group.setVisible(False)
        content_layout.addWidget(self.settings_group)

        # Step 4: Summary
        self.summary_group = self.create_summary_group()
        self.summary_group.setVisible(False)
        content_layout.addWidget(self.summary_group)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, 1)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.start_btn = QPushButton("Start Processing")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.on_start_processing)
        button_layout.addWidget(self.start_btn)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def create_header(self) -> QWidget:
        """Create header with plan info"""
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)

        # Title
        title = QLabel("Bulk Video Processing")
        title.setFont(QFont('Segoe UI', 16, QFont.Bold))
        layout.addWidget(title)

        layout.addStretch()

        # Plan info
        plan_info = self.plan_checker.get_plan_info_display()
        plan_label = QLabel(f"Plan: {plan_info['plan_display']}")
        plan_label.setObjectName("plan_label")
        layout.addWidget(plan_label)

        # Today's usage
        if not plan_info['is_unlimited']:
            usage_label = QLabel(
                f"Today: {plan_info['processed_today']}/{plan_info['daily_limit']} | "
                f"Remaining: {plan_info['remaining_today']}"
            )
            usage_label.setObjectName("usage_label")
            layout.addWidget(usage_label)

        return header

    def create_folder_selection_group(self) -> QGroupBox:
        """Create folder selection group"""
        group = QGroupBox("Step 1: Select Folders")
        layout = QGridLayout()
        layout.setSpacing(10)

        # Source folder
        layout.addWidget(QLabel("Source Folder (Raw Videos):"), 0, 0)

        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("Select folder containing raw videos...")
        self.source_input.textChanged.connect(self.on_folder_changed)
        layout.addWidget(self.source_input, 0, 1)

        source_btn = QPushButton("Browse")
        source_btn.clicked.connect(self.browse_source)
        layout.addWidget(source_btn, 0, 2)

        # Destination folder
        layout.addWidget(QLabel("Destination Folder (Edited Videos):"), 1, 0)

        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("Select folder for edited videos...")
        self.dest_input.textChanged.connect(self.on_folder_changed)
        layout.addWidget(self.dest_input, 1, 1)

        dest_btn = QPushButton("Browse")
        dest_btn.clicked.connect(self.browse_destination)
        layout.addWidget(dest_btn, 1, 2)

        # Scan button
        scan_layout = QHBoxLayout()
        scan_layout.addStretch()

        self.scan_btn = QPushButton("Scan Folders")
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self.scan_folders)
        scan_layout.addWidget(self.scan_btn)

        layout.addLayout(scan_layout, 2, 0, 1, 3)

        # Scan results label
        self.scan_result_label = QLabel("")
        self.scan_result_label.setWordWrap(True)
        layout.addWidget(self.scan_result_label, 3, 0, 1, 3)

        group.setLayout(layout)
        return group

    def create_mapping_group(self) -> QGroupBox:
        """Create mapping configuration group"""
        group = QGroupBox("Step 2: Folder Mapping")
        layout = QVBoxLayout()

        # Mode label
        self.mode_label = QLabel("")
        self.mode_label.setWordWrap(True)
        layout.addWidget(self.mode_label)

        # Mapping table (for complex mode)
        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(4)
        self.mapping_table.setHorizontalHeaderLabels([
            "Enabled", "Source Subfolder", "Destination Subfolder", "Videos"
        ])
        self.mapping_table.setMinimumHeight(200)
        self.mapping_table.setMaximumHeight(400)
        self.mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mapping_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.mapping_table.setColumnWidth(0, 60)
        self.mapping_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.mapping_table.setColumnWidth(3, 80)
        layout.addWidget(self.mapping_table)

        # Mapping actions
        action_layout = QHBoxLayout()

        self.auto_match_btn = QPushButton("Auto-Match by Name")
        self.auto_match_btn.clicked.connect(self.auto_match_folders)
        action_layout.addWidget(self.auto_match_btn)

        self.create_folders_btn = QPushButton("Create Missing Folders")
        self.create_folders_btn.clicked.connect(self.create_missing_folders)
        action_layout.addWidget(self.create_folders_btn)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        group.setLayout(layout)
        return group

    def create_settings_group(self) -> QGroupBox:
        """Create settings group"""
        group = QGroupBox("Step 3: Processing Settings")
        layout = QGridLayout()
        layout.setSpacing(15)

        # Delete source after edit
        layout.addWidget(QLabel("Delete source after edit:"), 0, 0)
        delete_layout = QHBoxLayout()

        self.delete_no_radio = QRadioButton("No (Keep original)")
        self.delete_no_radio.setChecked(True)
        delete_layout.addWidget(self.delete_no_radio)

        self.delete_yes_radio = QRadioButton("Yes (Delete original)")
        delete_layout.addWidget(self.delete_yes_radio)

        delete_layout.addStretch()
        layout.addLayout(delete_layout, 0, 1)

        # Preset selection
        layout.addWidget(QLabel("Apply Preset:"), 1, 0)
        preset_layout = QHBoxLayout()

        self.no_preset_radio = QRadioButton("None (No effects)")
        self.no_preset_radio.setChecked(True)
        self.no_preset_radio.toggled.connect(self.on_preset_toggle)
        preset_layout.addWidget(self.no_preset_radio)

        self.use_preset_radio = QRadioButton("Select Preset:")
        self.use_preset_radio.toggled.connect(self.on_preset_toggle)
        preset_layout.addWidget(self.use_preset_radio)

        self.preset_combo = QComboBox()
        self.preset_combo.setEnabled(False)
        self.preset_combo.setMinimumWidth(200)
        self.load_presets()
        preset_layout.addWidget(self.preset_combo)

        preset_layout.addStretch()
        layout.addLayout(preset_layout, 1, 1)

        # Output format
        layout.addWidget(QLabel("Output Format:"), 2, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(['mp4', 'mkv', 'avi', 'mov', 'webm'])
        self.format_combo.setCurrentText('mp4')
        layout.addWidget(self.format_combo, 2, 1)

        # Quality
        layout.addWidget(QLabel("Quality:"), 3, 0)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['high', 'medium', 'low'])
        self.quality_combo.setCurrentText('high')
        layout.addWidget(self.quality_combo, 3, 1)

        group.setLayout(layout)
        return group

    def create_summary_group(self) -> QGroupBox:
        """Create summary group"""
        group = QGroupBox("Step 4: Summary")
        layout = QVBoxLayout()

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # Warning label for limit
        self.limit_warning = QLabel("")
        self.limit_warning.setObjectName("warning_label")
        self.limit_warning.setWordWrap(True)
        self.limit_warning.setVisible(False)
        layout.addWidget(self.limit_warning)

        group.setLayout(layout)
        return group

    def apply_theme(self):
        """Apply dark theme"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #e0e0e0;
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
                color: #00bcd4;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #00bcd4;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353535;
            }
            QPushButton:pressed {
                background-color: #202020;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #666666;
            }
            QPushButton#start_btn {
                background-color: #00bcd4;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#start_btn:hover {
                background-color: #00d4ea;
            }
            QPushButton#start_btn:disabled {
                background-color: #1a5a5a;
            }
            QTableWidget {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                gridline-color: #3a3a3a;
            }
            QTableWidget::item {
                padding: 8px;
                color: #e0e0e0;
            }
            QTableWidget::item:selected {
                background-color: #00bcd4;
            }
            QHeaderView::section {
                background-color: #353535;
                color: #e0e0e0;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #e0e0e0;
                min-width: 100px;
            }
            QComboBox:disabled {
                background-color: #1a1a1a;
                color: #666666;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #e0e0e0;
                selection-background-color: #00bcd4;
            }
            QRadioButton {
                color: #e0e0e0;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox {
                color: #e0e0e0;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QFrame#header {
                background-color: #0f0f0f;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel#plan_label {
                color: #00bcd4;
                font-weight: bold;
            }
            QLabel#usage_label {
                color: #888888;
            }
            QLabel#warning_label {
                color: #ff9800;
                font-weight: bold;
                padding: 10px;
                background-color: #3d2d00;
                border-radius: 6px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        # Set start button style
        self.start_btn.setObjectName("start_btn")

    def browse_source(self):
        """Browse for source folder"""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Source Folder",
            os.path.expanduser("~/Desktop")
        )
        if folder:
            self.source_input.setText(folder)

    def browse_destination(self):
        """Browse for destination folder"""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Destination Folder",
            os.path.expanduser("~/Desktop")
        )
        if folder:
            self.dest_input.setText(folder)

    def on_folder_changed(self):
        """Handle folder input change"""
        source = self.source_input.text().strip()
        dest = self.dest_input.text().strip()

        self.scan_btn.setEnabled(bool(source and dest))

        # Hide subsequent steps
        self.mapping_group.setVisible(False)
        self.settings_group.setVisible(False)
        self.summary_group.setVisible(False)
        self.start_btn.setEnabled(False)

    def scan_folders(self):
        """Scan folders and detect mode"""
        source = self.source_input.text().strip()
        dest = self.dest_input.text().strip()

        # Validate source exists
        if not os.path.exists(source):
            QMessageBox.warning(self, "Error", f"Source folder does not exist:\n{source}")
            return

        # Create destination if not exists
        if not os.path.exists(dest):
            reply = QMessageBox.question(
                self, "Create Folder",
                f"Destination folder does not exist:\n{dest}\n\nCreate it now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    os.makedirs(dest, exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to create folder:\n{e}")
                    return
            else:
                return

        # Detect folder mode
        self.folder_mode, self.folder_info = FolderScanner.detect_folder_mode(source, dest)

        # Update scan result
        if self.folder_mode == 'simple':
            video_count = self.folder_info['source_video_count']
            self.scan_result_label.setText(
                f"Simple Mode: Found {video_count} videos in source folder.\n"
                f"Videos will be processed and saved to destination folder."
            )
            self.scan_result_label.setStyleSheet("color: #4caf50;")

            # Create simple mapping
            self.current_mapping = EditorFolderMapping(
                source_folder=source,
                destination_folder=dest,
                is_simple_mode=True
            )

            # Hide mapping table, show settings
            self.mapping_group.setVisible(False)
            self.settings_group.setVisible(True)

        else:  # complex mode
            source_subs = self.folder_info['source_subfolders']
            self.scan_result_label.setText(
                f"Complex Mode: Found {len(source_subs)} subfolders in source.\n"
                f"Please configure mapping for each subfolder."
            )
            self.scan_result_label.setStyleSheet("color: #00bcd4;")

            # Create mapping with subfolders
            self.current_mapping = EditorFolderMapping(
                source_folder=source,
                destination_folder=dest,
                is_simple_mode=False
            )

            # Auto-match subfolders
            dest_subs = self.folder_info['dest_subfolders']
            self.current_mapping.subfolder_mappings = FolderScanner.auto_match_subfolders(
                source_subs, dest_subs
            )

            # Show mapping table
            self.populate_mapping_table()
            self.mapping_group.setVisible(True)
            self.settings_group.setVisible(True)

        # Update summary
        self.update_summary()

    def populate_mapping_table(self):
        """Populate mapping table with subfolder mappings"""
        if not self.current_mapping:
            return

        mappings = self.current_mapping.subfolder_mappings
        self.mapping_table.setRowCount(len(mappings))

        dest_subs = self.folder_info.get('dest_subfolders', [])

        for row, sm in enumerate(mappings):
            # Enabled checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(sm.enabled)
            checkbox.stateChanged.connect(lambda state, r=row: self.on_mapping_enabled_changed(r, state))

            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.mapping_table.setCellWidget(row, 0, checkbox_widget)

            # Source subfolder
            self.mapping_table.setItem(row, 1, QTableWidgetItem(sm.source_subfolder))

            # Destination dropdown
            dest_combo = QComboBox()
            dest_combo.addItems(dest_subs + [sm.destination_subfolder])
            dest_combo.addItem("-- Create New --")

            # Remove duplicates
            items = []
            for i in range(dest_combo.count()):
                text = dest_combo.itemText(i)
                if text not in items:
                    items.append(text)
            dest_combo.clear()
            dest_combo.addItems(items)

            dest_combo.setCurrentText(sm.destination_subfolder)
            dest_combo.currentTextChanged.connect(
                lambda text, r=row: self.on_dest_subfolder_changed(r, text)
            )
            self.mapping_table.setCellWidget(row, 2, dest_combo)

            # Video count
            source_path = os.path.join(
                self.current_mapping.source_folder,
                sm.source_subfolder
            )
            video_count = FolderScanner.count_videos_in_folder(source_path)
            self.mapping_table.setItem(row, 3, QTableWidgetItem(str(video_count)))

    def on_mapping_enabled_changed(self, row: int, state: int):
        """Handle mapping enabled checkbox change"""
        if self.current_mapping and row < len(self.current_mapping.subfolder_mappings):
            self.current_mapping.subfolder_mappings[row].enabled = state == Qt.Checked
            self.update_summary()

    def on_dest_subfolder_changed(self, row: int, text: str):
        """Handle destination subfolder change"""
        if text == "-- Create New --":
            # Ask for new folder name
            from PyQt5.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(
                self, "Create New Folder",
                "Enter new folder name:"
            )
            if ok and name:
                # Update mapping
                if self.current_mapping and row < len(self.current_mapping.subfolder_mappings):
                    self.current_mapping.subfolder_mappings[row].destination_subfolder = name

                # Update combo
                combo = self.mapping_table.cellWidget(row, 2)
                if combo:
                    combo.blockSignals(True)
                    combo.insertItem(combo.count() - 1, name)
                    combo.setCurrentText(name)
                    combo.blockSignals(False)
        else:
            if self.current_mapping and row < len(self.current_mapping.subfolder_mappings):
                self.current_mapping.subfolder_mappings[row].destination_subfolder = text

        self.update_summary()

    def auto_match_folders(self):
        """Auto-match folders by name"""
        if not self.current_mapping:
            return

        source_subs = self.folder_info.get('source_subfolders', [])
        dest_subs = self.folder_info.get('dest_subfolders', [])

        self.current_mapping.subfolder_mappings = FolderScanner.auto_match_subfolders(
            source_subs, dest_subs
        )

        self.populate_mapping_table()
        self.update_summary()

        QMessageBox.information(
            self, "Auto-Match",
            f"Auto-matched {len(self.current_mapping.subfolder_mappings)} subfolders by name."
        )

    def create_missing_folders(self):
        """Create missing destination folders"""
        if not self.current_mapping:
            return

        dest_base = Path(self.current_mapping.destination_folder)
        created = 0

        for sm in self.current_mapping.subfolder_mappings:
            if sm.enabled:
                dest_path = dest_base / sm.destination_subfolder
                if not dest_path.exists():
                    try:
                        dest_path.mkdir(parents=True, exist_ok=True)
                        created += 1
                    except Exception as e:
                        logger.error(f"Failed to create folder {dest_path}: {e}")

        # Refresh folder info
        self.folder_info['dest_subfolders'] = FolderScanner.get_subfolders(
            self.current_mapping.destination_folder
        )

        QMessageBox.information(
            self, "Create Folders",
            f"Created {created} new folders."
        )

    def load_presets(self):
        """Load presets into combo"""
        self.preset_combo.clear()
        self.preset_combo.addItem("-- Select Preset --")

        try:
            presets = self.preset_manager.list_presets()
            for preset in presets:
                self.preset_combo.addItem(preset['name'])
        except Exception as e:
            logger.error(f"Error loading presets: {e}")

    def on_preset_toggle(self):
        """Handle preset radio toggle"""
        self.preset_combo.setEnabled(self.use_preset_radio.isChecked())

    def update_summary(self):
        """Update summary display"""
        if not self.current_mapping:
            return

        # Count total videos
        total_videos = 0
        if self.current_mapping.is_simple_mode:
            total_videos = FolderScanner.count_videos_in_folder(
                self.current_mapping.source_folder
            )
        else:
            for sm in self.current_mapping.subfolder_mappings:
                if sm.enabled:
                    source_path = os.path.join(
                        self.current_mapping.source_folder,
                        sm.source_subfolder
                    )
                    total_videos += FolderScanner.count_videos_in_folder(source_path)

        # Check daily limit
        can_process_all, can_process_count = self.plan_checker.can_process_count(total_videos)
        plan_info = self.plan_checker.get_plan_info_display()

        # Build summary
        summary_lines = [
            f"Videos to process: {total_videos}",
            f"Mode: {'Simple' if self.current_mapping.is_simple_mode else 'Subfolder Mapping'}",
            f"Source: {self.current_mapping.source_folder}",
            f"Destination: {self.current_mapping.destination_folder}"
        ]

        if not self.current_mapping.is_simple_mode:
            enabled_count = sum(1 for sm in self.current_mapping.subfolder_mappings if sm.enabled)
            summary_lines.append(f"Enabled mappings: {enabled_count}")

        self.summary_label.setText("\n".join(summary_lines))

        # Show warning if limit exceeded
        if not plan_info['is_unlimited'] and not can_process_all:
            self.limit_warning.setText(
                f"Daily limit reached! You can only process {can_process_count} more videos today.\n"
                f"Upgrade to Pro for unlimited processing."
            )
            self.limit_warning.setVisible(True)
        else:
            self.limit_warning.setVisible(False)

        self.summary_group.setVisible(True)

        # Enable start button if we have videos to process
        self.start_btn.setEnabled(total_videos > 0 and can_process_count > 0)

    def get_processing_config(self) -> dict:
        """Get complete processing configuration"""
        if not self.current_mapping:
            return {}

        # Update settings
        self.current_mapping.settings = EditorMappingSettings(
            delete_source_after_edit=self.delete_yes_radio.isChecked(),
            preset_id=self.preset_combo.currentText() if self.use_preset_radio.isChecked() and self.preset_combo.currentIndex() > 0 else None,
            output_format=self.format_combo.currentText(),
            quality=self.quality_combo.currentText()
        )

        # Calculate videos to process
        total_videos = 0
        video_list = []

        if self.current_mapping.is_simple_mode:
            source_path = Path(self.current_mapping.source_folder)
            for f in source_path.iterdir():
                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                    video_list.append({
                        'source': str(f),
                        'destination': str(Path(self.current_mapping.destination_folder) / f.name)
                    })
            total_videos = len(video_list)
        else:
            for sm in self.current_mapping.subfolder_mappings:
                if sm.enabled:
                    source_path = Path(self.current_mapping.source_folder) / sm.source_subfolder
                    dest_path = Path(self.current_mapping.destination_folder) / sm.destination_subfolder

                    for f in source_path.iterdir():
                        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                            video_list.append({
                                'source': str(f),
                                'destination': str(dest_path / f.name),
                                'subfolder': sm.source_subfolder
                            })
                    total_videos += len([v for v in video_list if v.get('subfolder') == sm.source_subfolder])

        # Apply daily limit
        can_process_all, can_process_count = self.plan_checker.can_process_count(len(video_list))
        if not can_process_all:
            video_list = video_list[:can_process_count]

        return {
            'mapping': self.current_mapping,
            'videos': video_list,
            'total_count': len(video_list),
            'settings': self.current_mapping.settings,
            'plan_checker': self.plan_checker
        }

    def on_start_processing(self):
        """Handle start processing button"""
        config = self.get_processing_config()

        if not config.get('videos'):
            QMessageBox.warning(self, "No Videos", "No videos found to process.")
            return

        # Confirm
        reply = QMessageBox.question(
            self, "Start Processing",
            f"Are you sure you want to process {config['total_count']} videos?\n\n"
            f"Delete source after edit: {'Yes' if config['settings'].delete_source_after_edit else 'No'}\n"
            f"Preset: {config['settings'].preset_id or 'None'}\n"
            f"Output format: {config['settings'].output_format}\n"
            f"Quality: {config['settings'].quality}",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Create destination folders if needed
            self.mapping_manager.create_destination_folders(self.current_mapping)

            # Emit signal and close
            self.start_processing.emit(config)
            self.accept()
