"""
modules/metadata_remover/metadata_mapping_dialog.py
Metadata Remover Mapping Dialog - UI for folder mapping configuration
Provides intelligent folder scanning and mapping interface
"""

import os
from pathlib import Path
from typing import Optional, List

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QComboBox, QGroupBox, QRadioButton, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from modules.logging.logger import get_logger
from modules.metadata_remover.metadata_folder_manager import (
    MetadataFolderMapping, MetadataFolderMappingManager, MetadataRemovalSettings,
    SubfolderMapping, MetadataFolderScanner, MetadataPlanLimitChecker, VIDEO_EXTENSIONS
)

logger = get_logger(__name__)


class MetadataBulkProcessingDialog(QDialog):
    """
    Main Bulk Processing Dialog for Metadata Remover
    Step-by-step wizard for configuring folder mapping and processing
    """

    # Signal emitted when processing should start
    start_processing = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mapping_manager = MetadataFolderMappingManager()
        self.plan_checker = MetadataPlanLimitChecker()

        self.current_mapping: Optional[MetadataFolderMapping] = None
        self.folder_mode = 'simple'
        self.folder_info = {}
        self.source_structure = 'SIMPLE'
        self.source_info = {}

        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Bulk Metadata Removal")
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
        title = QLabel("Bulk Metadata Removal")
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
        layout.addWidget(QLabel("Source Folder (Videos with Metadata):"), 0, 0)

        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("Select folder containing videos...")
        self.source_input.textChanged.connect(self.on_folder_changed)
        layout.addWidget(self.source_input, 0, 1)

        source_btn = QPushButton("Browse")
        source_btn.clicked.connect(self.browse_source)
        layout.addWidget(source_btn, 0, 2)

        # Same as source checkbox
        self.same_as_source_checkbox = QCheckBox("Same as source (replace original files in-place)")
        self.same_as_source_checkbox.setChecked(False)
        self.same_as_source_checkbox.stateChanged.connect(self.on_same_as_source_changed)
        layout.addWidget(self.same_as_source_checkbox, 1, 0, 1, 3)

        # Destination folder
        layout.addWidget(QLabel("Destination Folder (Clean Videos):"), 2, 0)

        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("Select folder for clean videos...")
        self.dest_input.textChanged.connect(self.on_folder_changed)
        layout.addWidget(self.dest_input, 2, 1)

        self.dest_browse_btn = QPushButton("Browse")
        self.dest_browse_btn.clicked.connect(self.browse_destination)
        layout.addWidget(self.dest_browse_btn, 2, 2)

        # Scan button
        scan_layout = QHBoxLayout()
        scan_layout.addStretch()

        self.scan_btn = QPushButton("Scan Folders")
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self.scan_folders)
        scan_layout.addWidget(self.scan_btn)

        layout.addLayout(scan_layout, 3, 0, 1, 3)

        # Scan results label
        self.scan_result_label = QLabel("")
        self.scan_result_label.setWordWrap(True)
        layout.addWidget(self.scan_result_label, 4, 0, 1, 3)

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

        # Process root videos checkbox (for mixed mode)
        self.process_root_checkbox = QCheckBox("Also process videos in root folder")
        self.process_root_checkbox.setChecked(True)
        self.process_root_checkbox.setVisible(False)
        self.process_root_checkbox.stateChanged.connect(self.update_summary)
        layout.addWidget(self.process_root_checkbox)

        # Mapping table (for complex mode)
        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(4)
        self.mapping_table.setHorizontalHeaderLabels([
            "Enabled", "Source Subfolder", "Destination Subfolder", "Videos"
        ])
        self.mapping_table.setMinimumHeight(250)
        self.mapping_table.setMaximumHeight(500)

        # Disable selection behavior to prevent unwanted highlighting
        self.mapping_table.setSelectionMode(QTableWidget.NoSelection)
        self.mapping_table.setFocusPolicy(Qt.NoFocus)

        # Set proper row height
        self.mapping_table.verticalHeader().setDefaultSectionSize(45)
        self.mapping_table.verticalHeader().setVisible(False)

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

        # Metadata removal options
        layout.addWidget(QLabel("Metadata to remove:"), 0, 0)

        metadata_layout = QVBoxLayout()

        self.remove_all_radio = QRadioButton("Remove ALL metadata (recommended)")
        self.remove_all_radio.setChecked(True)
        metadata_layout.addWidget(self.remove_all_radio)

        self.remove_specific_radio = QRadioButton("Remove specific metadata:")
        metadata_layout.addWidget(self.remove_specific_radio)

        # Specific metadata checkboxes (indented)
        specific_layout = QVBoxLayout()
        specific_layout.setContentsMargins(30, 0, 0, 0)

        self.exif_checkbox = QCheckBox("EXIF data (camera info, dates)")
        self.exif_checkbox.setChecked(True)
        self.exif_checkbox.setEnabled(False)
        specific_layout.addWidget(self.exif_checkbox)

        self.xmp_checkbox = QCheckBox("XMP data (editing software info)")
        self.xmp_checkbox.setChecked(True)
        self.xmp_checkbox.setEnabled(False)
        specific_layout.addWidget(self.xmp_checkbox)

        self.gps_checkbox = QCheckBox("GPS/Location data")
        self.gps_checkbox.setChecked(True)
        self.gps_checkbox.setEnabled(False)
        specific_layout.addWidget(self.gps_checkbox)

        self.id3_checkbox = QCheckBox("ID3 tags (audio metadata)")
        self.id3_checkbox.setChecked(True)
        self.id3_checkbox.setEnabled(False)
        specific_layout.addWidget(self.id3_checkbox)

        metadata_layout.addLayout(specific_layout)
        layout.addLayout(metadata_layout, 0, 1)

        # Connect radio buttons
        self.remove_all_radio.toggled.connect(self.on_metadata_option_changed)
        self.remove_specific_radio.toggled.connect(self.on_metadata_option_changed)

        # Delete source option (only for different folder mode)
        self.delete_source_label = QLabel("Delete source after process:")
        layout.addWidget(self.delete_source_label, 1, 0)

        delete_layout = QHBoxLayout()
        self.delete_no_radio = QRadioButton("No (Keep original)")
        self.delete_no_radio.setChecked(True)
        delete_layout.addWidget(self.delete_no_radio)

        self.delete_yes_radio = QRadioButton("Yes (Delete original)")
        delete_layout.addWidget(self.delete_yes_radio)

        delete_layout.addStretch()
        layout.addLayout(delete_layout, 1, 1)

        group.setLayout(layout)
        return group

    def create_summary_group(self) -> QGroupBox:
        """Create summary group"""
        group = QGroupBox("Step 4: Summary")
        layout = QVBoxLayout()

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # Warning label for in-place mode
        self.inplace_warning = QLabel(
            "⚠️ WARNING: Original files will be permanently replaced!\n"
            "Make sure you have backups before proceeding."
        )
        self.inplace_warning.setObjectName("warning_label")
        self.inplace_warning.setWordWrap(True)
        self.inplace_warning.setVisible(False)
        layout.addWidget(self.inplace_warning)

        # Warning label for limit
        self.limit_warning = QLabel("")
        self.limit_warning.setObjectName("limit_warning")
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
                color: #9c27b0;
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
                border-color: #9c27b0;
            }
            QLineEdit:disabled {
                background-color: #1a1a1a;
                color: #666666;
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
                background-color: #9c27b0;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#start_btn:hover {
                background-color: #ab47bc;
            }
            QPushButton#start_btn:disabled {
                background-color: #4a1a4a;
            }
            QTableWidget {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                gridline-color: #3a3a3a;
                outline: none;
            }
            QTableWidget::item {
                padding: 10px;
                color: #e0e0e0;
                border: none;
                outline: none;
            }
            QTableWidget::item:selected {
                background-color: transparent;
            }
            QTableWidget::item:focus {
                background-color: transparent;
                outline: none;
            }
            QHeaderView::section {
                background-color: #353535;
                color: #e0e0e0;
                padding: 12px 8px;
                border: none;
                font-weight: bold;
                font-size: 13px;
            }
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #e0e0e0;
                min-width: 150px;
                min-height: 30px;
            }
            QComboBox:hover {
                border-color: #9c27b0;
                background-color: #353535;
            }
            QComboBox:disabled {
                background-color: #1a1a1a;
                color: #666666;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
                subcontrol-origin: padding;
                subcontrol-position: top right;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #e0e0e0;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #e0e0e0;
                selection-background-color: #9c27b0;
                selection-color: #ffffff;
                padding: 5px;
                min-width: 200px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 30px;
                padding: 5px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #353535;
            }
            QRadioButton, QCheckBox {
                color: #e0e0e0;
                spacing: 8px;
            }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton:disabled, QCheckBox:disabled {
                color: #666666;
            }
            QFrame#header {
                background-color: #0f0f0f;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel#plan_label {
                color: #9c27b0;
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
            QLabel#limit_warning {
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
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.DontUseNativeDialog, False)  # Use native dialog
        dialog.setWindowTitle("Select Source Folder")
        dialog.setDirectory(os.path.expanduser("~/Desktop"))

        # Open as standalone window with maximize/minimize buttons
        dialog.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        dialog.resize(900, 650)

        if dialog.exec_():
            folders = dialog.selectedFiles()
            if folders:
                self.source_input.setText(folders[0])

    def browse_destination(self):
        """Browse for destination folder"""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.DontUseNativeDialog, False)  # Use native dialog
        dialog.setWindowTitle("Select Destination Folder")
        dialog.setDirectory(os.path.expanduser("~/Desktop"))

        # Open as standalone window with maximize/minimize buttons
        dialog.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        dialog.resize(900, 650)

        if dialog.exec_():
            folders = dialog.selectedFiles()
            if folders:
                self.dest_input.setText(folders[0])

    def on_same_as_source_changed(self, state):
        """Handle same as source checkbox change"""
        is_same = state == Qt.Checked

        self.dest_input.setEnabled(not is_same)
        self.dest_browse_btn.setEnabled(not is_same)

        if is_same:
            self.dest_input.setText("")
            self.dest_input.setPlaceholderText("(Same as source folder)")
            # Hide delete source option for in-place mode
            self.delete_source_label.setVisible(False)
            self.delete_no_radio.setVisible(False)
            self.delete_yes_radio.setVisible(False)
        else:
            self.dest_input.setPlaceholderText("Select folder for clean videos...")
            self.delete_source_label.setVisible(True)
            self.delete_no_radio.setVisible(True)
            self.delete_yes_radio.setVisible(True)

        self.on_folder_changed()

    def on_folder_changed(self):
        """Handle folder input change"""
        source = self.source_input.text().strip()
        is_same = self.same_as_source_checkbox.isChecked()
        dest = source if is_same else self.dest_input.text().strip()

        # Enable scan button if source is provided (and dest if not same)
        can_scan = bool(source) and (is_same or bool(dest))
        self.scan_btn.setEnabled(can_scan)

        # Hide subsequent steps
        self.mapping_group.setVisible(False)
        self.settings_group.setVisible(False)
        self.summary_group.setVisible(False)
        self.start_btn.setEnabled(False)

    def on_metadata_option_changed(self):
        """Handle metadata option radio button change"""
        is_specific = self.remove_specific_radio.isChecked()
        self.exif_checkbox.setEnabled(is_specific)
        self.xmp_checkbox.setEnabled(is_specific)
        self.gps_checkbox.setEnabled(is_specific)
        self.id3_checkbox.setEnabled(is_specific)

    def scan_folders(self):
        """Scan folders and detect mode"""
        source = self.source_input.text().strip()
        is_same = self.same_as_source_checkbox.isChecked()
        dest = source if is_same else self.dest_input.text().strip()

        # Validate source exists
        if not os.path.exists(source):
            QMessageBox.warning(self, "Error", f"Source folder does not exist:\n{source}")
            return

        # Create destination if not exists (and not same as source)
        if not is_same and not os.path.exists(dest):
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

        # Detect source structure
        self.source_structure, self.source_info = MetadataFolderScanner.detect_folder_structure(source)

        if self.source_structure == 'EMPTY':
            self.scan_result_label.setText("No videos found in source folder.")
            self.scan_result_label.setStyleSheet("color: #f44336;")
            return

        # Create mapping
        self.current_mapping = MetadataFolderMapping(
            source_folder=source,
            destination_folder=dest,
            same_as_source=is_same
        )

        if is_same:
            # In-place mode
            self._setup_inplace_mode()
        else:
            # Different folders mode (like video editor)
            self._setup_different_folders_mode(dest)

        # Show settings and summary
        self.settings_group.setVisible(True)
        self.update_summary()

    def _setup_inplace_mode(self):
        """Setup UI for in-place replacement mode"""
        if self.source_structure == 'SIMPLE':
            video_count = self.source_info['root_video_count']
            self.scan_result_label.setText(
                f"In-Place Mode: Found {video_count} videos.\n"
                f"Videos will be processed and replaced in the same location."
            )
            self.scan_result_label.setStyleSheet("color: #ff9800;")

            self.current_mapping.is_simple_mode = True
            self.mapping_group.setVisible(False)

        elif self.source_structure in ('SUBFOLDERS_ONLY', 'MIXED'):
            subfolder_count = len(self.source_info['subfolders'])
            total_videos = self.source_info['total_in_subfolders']

            if self.source_structure == 'MIXED':
                total_videos += self.source_info['root_video_count']
                self.process_root_checkbox.setVisible(True)
                msg = f"In-Place Mode: Found {subfolder_count} subfolders + {self.source_info['root_video_count']} root videos.\n"
            else:
                self.process_root_checkbox.setVisible(False)
                msg = f"In-Place Mode: Found {subfolder_count} subfolders with {total_videos} videos.\n"

            msg += "Select which subfolders to process. Videos will be replaced in-place."

            self.scan_result_label.setText(msg)
            self.scan_result_label.setStyleSheet("color: #ff9800;")

            self.current_mapping.is_simple_mode = False

            # Create subfolder mappings (same source and dest for in-place)
            self.current_mapping.subfolder_mappings = [
                SubfolderMapping(
                    source_subfolder=sf,
                    destination_subfolder=sf,
                    enabled=True
                )
                for sf in self.source_info['subfolders']
            ]

            # Populate table (without destination column interaction)
            self._populate_inplace_table()
            self.mapping_group.setVisible(True)
            self.auto_match_btn.setVisible(False)
            self.create_folders_btn.setVisible(False)

    def _setup_different_folders_mode(self, dest: str):
        """Setup UI for different folders mode (like video editor)"""
        self.folder_mode, self.folder_info = MetadataFolderScanner.detect_folder_mode(
            self.current_mapping.source_folder, dest
        )

        if self.folder_mode == 'simple':
            video_count = self.folder_info['source_video_count']
            self.scan_result_label.setText(
                f"Simple Mode: Found {video_count} videos in source folder.\n"
                f"Videos will be processed and saved to destination folder."
            )
            self.scan_result_label.setStyleSheet("color: #4caf50;")

            self.current_mapping.is_simple_mode = True
            self.mapping_group.setVisible(False)

        else:  # complex mode
            source_subs = self.folder_info['source_subfolders']
            self.scan_result_label.setText(
                f"Complex Mode: Found {len(source_subs)} subfolders in source.\n"
                f"Please configure mapping for each subfolder."
            )
            self.scan_result_label.setStyleSheet("color: #9c27b0;")

            self.current_mapping.is_simple_mode = False

            # Auto-match subfolders
            dest_subs = self.folder_info['dest_subfolders']
            self.current_mapping.subfolder_mappings = MetadataFolderScanner.auto_match_subfolders(
                source_subs, dest_subs
            )

            # Show mapping table
            self.populate_mapping_table()
            self.mapping_group.setVisible(True)
            self.auto_match_btn.setVisible(True)
            self.create_folders_btn.setVisible(True)
            self.process_root_checkbox.setVisible(False)

    def _populate_inplace_table(self):
        """Populate table for in-place mode (simplified)"""
        if not self.current_mapping:
            return

        # Change headers for in-place mode
        self.mapping_table.setColumnCount(3)
        self.mapping_table.setHorizontalHeaderLabels([
            "Enabled", "Subfolder", "Videos"
        ])
        self.mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mapping_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.mapping_table.setColumnWidth(0, 60)
        self.mapping_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.mapping_table.setColumnWidth(2, 80)

        mappings = self.current_mapping.subfolder_mappings
        self.mapping_table.setRowCount(len(mappings))

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

            # Subfolder name (read-only)
            subfolder_item = QTableWidgetItem(sm.source_subfolder)
            subfolder_item.setFlags(subfolder_item.flags() & ~Qt.ItemIsEditable)
            self.mapping_table.setItem(row, 1, subfolder_item)

            # Set row height
            self.mapping_table.setRowHeight(row, 45)

            # Video count (read-only)
            video_count = self.source_info['subfolder_counts'].get(sm.source_subfolder, 0)
            count_item = QTableWidgetItem(str(video_count))
            count_item.setFlags(count_item.flags() & ~Qt.ItemIsEditable)
            count_item.setTextAlignment(Qt.AlignCenter)
            self.mapping_table.setItem(row, 2, count_item)

    def populate_mapping_table(self):
        """Populate mapping table with subfolder mappings (for different folders mode)"""
        if not self.current_mapping:
            return

        # Reset headers for different folders mode
        self.mapping_table.setColumnCount(4)
        self.mapping_table.setHorizontalHeaderLabels([
            "Enabled", "Source Subfolder", "Destination Subfolder", "Videos"
        ])

        # Reset column resize modes and widths
        header = self.mapping_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)  # Allow resizing
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.mapping_table.setColumnWidth(0, 80)  # Enabled column
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Source subfolder stretches
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Destination subfolder stretches
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.mapping_table.setColumnWidth(3, 80)  # Videos count column

        # Set minimum section sizes for better display
        header.setMinimumSectionSize(200)  # Ensure columns are at least 200px wide

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

            # Source subfolder (read-only)
            source_item = QTableWidgetItem(sm.source_subfolder)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.mapping_table.setItem(row, 1, source_item)

            # Set row height
            self.mapping_table.setRowHeight(row, 45)

            # Destination dropdown with proper sizing
            dest_combo = QComboBox()
            dest_combo.setMinimumWidth(250)  # Increased minimum width
            dest_combo.setMaximumWidth(500)
            dest_combo.setSizePolicy(dest_combo.sizePolicy().horizontalPolicy(), dest_combo.sizePolicy().verticalPolicy())
            dest_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)

            # Build unique items list
            items = dest_subs.copy()
            if sm.destination_subfolder and sm.destination_subfolder not in items:
                items.append(sm.destination_subfolder)
            items.append("-- Create New --")

            # Remove duplicates while preserving order
            seen = set()
            unique_items = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    unique_items.append(item)

            dest_combo.addItems(unique_items)
            dest_combo.setCurrentText(sm.destination_subfolder)
            dest_combo.currentTextChanged.connect(
                lambda text, r=row: self.on_dest_subfolder_changed(r, text)
            )

            # Wrap combo in widget for better control
            combo_widget = QWidget()
            combo_layout = QHBoxLayout(combo_widget)
            combo_layout.addWidget(dest_combo)
            combo_layout.setContentsMargins(4, 4, 4, 4)
            self.mapping_table.setCellWidget(row, 2, combo_widget)

            # Video count (read-only)
            source_path = os.path.join(
                self.current_mapping.source_folder,
                sm.source_subfolder
            )
            video_count = MetadataFolderScanner.count_videos_in_folder(source_path)
            count_item = QTableWidgetItem(str(video_count))
            count_item.setFlags(count_item.flags() & ~Qt.ItemIsEditable)
            count_item.setTextAlignment(Qt.AlignCenter)
            self.mapping_table.setItem(row, 3, count_item)

    def on_mapping_enabled_changed(self, row: int, state: int):
        """Handle mapping enabled checkbox change"""
        if self.current_mapping and row < len(self.current_mapping.subfolder_mappings):
            self.current_mapping.subfolder_mappings[row].enabled = state == Qt.Checked
            self.update_summary()

    def on_dest_subfolder_changed(self, row: int, text: str):
        """Handle destination subfolder change"""
        if text == "-- Create New --":
            from PyQt5.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(
                self, "Create New Folder",
                "Enter new folder name:"
            )
            if ok and name:
                if self.current_mapping and row < len(self.current_mapping.subfolder_mappings):
                    self.current_mapping.subfolder_mappings[row].destination_subfolder = name

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
        if not self.current_mapping or self.current_mapping.same_as_source:
            return

        source_subs = self.folder_info.get('source_subfolders', [])
        dest_subs = self.folder_info.get('dest_subfolders', [])

        self.current_mapping.subfolder_mappings = MetadataFolderScanner.auto_match_subfolders(
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
        if not self.current_mapping or self.current_mapping.same_as_source:
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
        self.folder_info['dest_subfolders'] = MetadataFolderScanner.get_subfolders(
            self.current_mapping.destination_folder
        )

        QMessageBox.information(
            self, "Create Folders",
            f"Created {created} new folders."
        )

    def update_summary(self):
        """Update summary display"""
        if not self.current_mapping:
            return

        # Count total videos
        total_videos = 0

        if self.current_mapping.same_as_source:
            # In-place mode
            if self.current_mapping.is_simple_mode:
                total_videos = self.source_info.get('root_video_count', 0)
            else:
                for sm in self.current_mapping.subfolder_mappings:
                    if sm.enabled:
                        total_videos += self.source_info['subfolder_counts'].get(sm.source_subfolder, 0)

                # Add root videos if mixed mode and checkbox checked
                if self.source_structure == 'MIXED' and self.process_root_checkbox.isChecked():
                    total_videos += self.source_info.get('root_video_count', 0)
                    self.current_mapping.process_root_videos = True
                else:
                    self.current_mapping.process_root_videos = False
        else:
            # Different folders mode
            if self.current_mapping.is_simple_mode:
                total_videos = MetadataFolderScanner.count_videos_in_folder(
                    self.current_mapping.source_folder
                )
            else:
                for sm in self.current_mapping.subfolder_mappings:
                    if sm.enabled:
                        source_path = os.path.join(
                            self.current_mapping.source_folder,
                            sm.source_subfolder
                        )
                        total_videos += MetadataFolderScanner.count_videos_in_folder(source_path)

        # Check daily limit
        can_process_all, can_process_count = self.plan_checker.can_process_count(total_videos)
        plan_info = self.plan_checker.get_plan_info_display()

        # Build summary
        mode_str = "In-Place (Replace)" if self.current_mapping.same_as_source else "Different Folders"
        summary_lines = [
            f"Videos to process: {total_videos}",
            f"Mode: {mode_str}",
            f"Source: {self.current_mapping.source_folder}",
        ]

        if not self.current_mapping.same_as_source:
            summary_lines.append(f"Destination: {self.current_mapping.destination_folder}")

        if not self.current_mapping.is_simple_mode:
            enabled_count = sum(1 for sm in self.current_mapping.subfolder_mappings if sm.enabled)
            summary_lines.append(f"Enabled subfolders: {enabled_count}")

        self.summary_label.setText("\n".join(summary_lines))

        # Show in-place warning
        self.inplace_warning.setVisible(self.current_mapping.same_as_source)

        # Show limit warning if exceeded
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
        self.current_mapping.settings = MetadataRemovalSettings(
            remove_all_metadata=self.remove_all_radio.isChecked(),
            remove_exif=self.exif_checkbox.isChecked(),
            remove_xmp=self.xmp_checkbox.isChecked(),
            remove_gps=self.gps_checkbox.isChecked(),
            remove_id3=self.id3_checkbox.isChecked(),
            delete_source_after_process=self.delete_yes_radio.isChecked() if not self.current_mapping.same_as_source else False
        )

        # Build video list
        video_list = []

        if self.current_mapping.same_as_source:
            # In-place mode
            if self.current_mapping.is_simple_mode:
                source_path = Path(self.current_mapping.source_folder)
                for f in source_path.iterdir():
                    if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                        video_list.append({
                            'source': str(f),
                            'destination': str(f),  # Same path
                            'in_place': True
                        })
            else:
                # Process subfolders
                for sm in self.current_mapping.subfolder_mappings:
                    if sm.enabled:
                        source_path = Path(self.current_mapping.source_folder) / sm.source_subfolder
                        for f in source_path.iterdir():
                            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                                video_list.append({
                                    'source': str(f),
                                    'destination': str(f),  # Same path
                                    'in_place': True,
                                    'subfolder': sm.source_subfolder
                                })

                # Process root videos if mixed mode
                if self.current_mapping.process_root_videos:
                    source_path = Path(self.current_mapping.source_folder)
                    for f in source_path.iterdir():
                        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                            video_list.append({
                                'source': str(f),
                                'destination': str(f),
                                'in_place': True,
                                'subfolder': None
                            })
        else:
            # Different folders mode
            if self.current_mapping.is_simple_mode:
                source_path = Path(self.current_mapping.source_folder)
                for f in source_path.iterdir():
                    if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                        video_list.append({
                            'source': str(f),
                            'destination': str(Path(self.current_mapping.destination_folder) / f.name),
                            'in_place': False
                        })
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
                                    'in_place': False,
                                    'subfolder': sm.source_subfolder
                                })

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

        # Different confirmation for in-place mode
        if self.current_mapping.same_as_source:
            reply = QMessageBox.warning(
                self, "Confirm In-Place Processing",
                f"⚠️ WARNING: You are about to process {config['total_count']} videos IN-PLACE.\n\n"
                f"Original files will be PERMANENTLY REPLACED!\n"
                f"Make sure you have backups.\n\n"
                f"Are you sure you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
        else:
            reply = QMessageBox.question(
                self, "Start Processing",
                f"Are you sure you want to process {config['total_count']} videos?\n\n"
                f"Delete source after process: {'Yes' if config['settings'].delete_source_after_process else 'No'}",
                QMessageBox.Yes | QMessageBox.No
            )

        if reply == QMessageBox.Yes:
            # Create destination folders if needed
            self.mapping_manager.create_destination_folders(self.current_mapping)

            # Emit signal and close
            self.start_processing.emit(config)
            self.accept()
