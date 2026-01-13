"""
modules/video_editor/videos_merger/bulk_folder_tab.py
Bulk folder merge tab UI - Intelligent round-robin merging
"""

from typing import List, Optional
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QScrollArea, QGroupBox, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QLineEdit, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from .folder_item_widget import FolderItemWidget
from .merge_engine import MergeSettings
from .merge_processor import BulkMergeProcessor
from .bulk_merge_engine import BulkMergeEngine
from .utils import get_default_output_folder, generate_batch_filename
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class BulkFolderTab(QWidget):
    """Tab for bulk folder merging"""

    # Signals
    merge_started = pyqtSignal(object)  # Emits processor
    merge_completed = pyqtSignal(bool, dict)  # (success, results)

    def __init__(self):
        super().__init__()

        # Data
        self.folder_widgets: List[FolderItemWidget] = []
        self.processor: Optional[BulkMergeProcessor] = None
        self.batch_engine: Optional[BulkMergeEngine] = None

        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Top buttons row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        add_btn = QPushButton("➕ Add Folders")
        add_btn.setFixedHeight(32)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
        """)
        add_btn.clicked.connect(self.add_folders)
        button_layout.addWidget(add_btn)

        clear_btn = QPushButton("🗑️ Clear All")
        clear_btn.setFixedHeight(32)
        clear_btn.clicked.connect(self.clear_all)
        button_layout.addWidget(clear_btn)

        preview_btn = QPushButton("📊 Preview")
        preview_btn.setFixedHeight(32)
        preview_btn.clicked.connect(self.preview_batches)
        button_layout.addWidget(preview_btn)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Info label
        info_label = QLabel("ℹ️ Round-robin: Takes 1 video from each folder per batch. Skips single-video batches.")
        info_label.setStyleSheet("color: #00bcd4; font-size: 9pt; padding: 6px; background-color: #1e3a4a; border-radius: 4px;")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

        # Folder list scroll area
        folder_frame = QFrame()
        folder_frame.setFrameShape(QFrame.StyledPanel)
        folder_frame_layout = QVBoxLayout()
        folder_frame_layout.setContentsMargins(5, 5, 5, 5)

        self.folder_list_widget = QWidget()
        self.folder_list_layout = QVBoxLayout()
        self.folder_list_layout.setSpacing(6)
        self.folder_list_layout.setContentsMargins(0, 0, 0, 0)
        self.folder_list_widget.setLayout(self.folder_list_layout)

        folder_scroll = QScrollArea()
        folder_scroll.setWidgetResizable(True)
        folder_scroll.setWidget(self.folder_list_widget)
        folder_scroll.setMinimumHeight(100)
        folder_scroll.setMaximumHeight(150)
        folder_frame_layout.addWidget(folder_scroll)
        folder_frame.setLayout(folder_frame_layout)
        main_layout.addWidget(folder_frame)

        # Empty state label
        self.empty_label = QLabel("No folders added. Click 'Add Folders' to begin.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #888; font-size: 10pt; padding: 30px;")
        self.folder_list_layout.addWidget(self.empty_label)

        # Settings section in scroll area
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setMinimumHeight(300)
        settings_scroll.setMaximumHeight(420)

        settings_widget = QWidget()
        settings_main_layout = QVBoxLayout()
        settings_main_layout.setContentsMargins(5, 5, 5, 5)
        settings_main_layout.setSpacing(10)

        # Create settings in columns
        settings_row = QHBoxLayout()
        settings_row.setSpacing(10)
        settings_row.addWidget(self._create_bulk_settings())
        settings_row.addWidget(self._create_output_settings())
        settings_main_layout.addLayout(settings_row)

        settings_widget.setLayout(settings_main_layout)
        settings_scroll.setWidget(settings_widget)
        main_layout.addWidget(settings_scroll)

        # Summary row
        self.summary_label = QLabel("📊 Batches: 0  |  Folders: 0")
        self.summary_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #00bcd4; padding: 5px;")
        main_layout.addWidget(self.summary_label)

        # Start button
        self.start_btn = QPushButton("▶️ Start Batch Merging")
        self.start_btn.setFixedHeight(42)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                font-size: 11pt;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #666;
            }
        """)
        self.start_btn.clicked.connect(self.start_merge)
        self.start_btn.setEnabled(False)
        main_layout.addWidget(self.start_btn)

        self.setLayout(main_layout)

        # Apply comprehensive dark theme
        self.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;
                color: #e0e0e0;
            }
            QFrame {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
            }
            QGroupBox {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
                color: #00bcd4;
                font-size: 10pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 10px;
                color: #00bcd4;
                background-color: #252525;
            }
            QLabel {
                color: #e0e0e0;
                background-color: transparent;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                padding: 6px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #0066cc;
            }
            QPushButton:pressed {
                background-color: #202020;
            }
            QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 4px 6px;
                min-height: 20px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
                border-color: #0066cc;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                background-color: #2a2a2a;
                border-left: 1px solid #3a3a3a;
                border-radius: 0px 3px 0px 0px;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                background-color: #2a2a2a;
                border-left: 1px solid #3a3a3a;
                border-radius: 0px 0px 3px 0px;
            }
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #353535;
            }
            QComboBox {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 4px 6px;
                min-height: 20px;
            }
            QComboBox:hover {
                border-color: #0066cc;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #e0e0e0;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: #e0e0e0;
                selection-background-color: #0066cc;
                border: 1px solid #3a3a3a;
                outline: none;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #3a3a3a;
                border-radius: 3px;
                background-color: #1e1e1e;
            }
            QCheckBox::indicator:checked {
                background-color: #0066cc;
                border-color: #0066cc;
                image: none;
            }
            QCheckBox::indicator:checked:after {
                content: "✓";
                color: white;
            }
            QCheckBox::indicator:hover {
                border-color: #0066cc;
            }
            QScrollArea {
                background-color: transparent;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 10px;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #3a3a3a;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4a4a4a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

    def _create_bulk_settings(self) -> QGroupBox:
        """Create bulk settings group"""
        group = QGroupBox("⚙️ Processing Settings")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)

        # Trim start
        start_layout = QHBoxLayout()
        start_label = QLabel("Trim Start:")
        start_label.setFixedWidth(80)
        start_layout.addWidget(start_label)
        self.trim_start_spin = QSpinBox()
        self.trim_start_spin.setRange(0, 300)
        self.trim_start_spin.setValue(0)
        self.trim_start_spin.setSuffix(" sec")
        start_layout.addWidget(self.trim_start_spin, 1)
        layout.addLayout(start_layout)

        # Trim end
        end_layout = QHBoxLayout()
        end_label = QLabel("Trim End:")
        end_label.setFixedWidth(80)
        end_layout.addWidget(end_label)
        self.trim_end_spin = QSpinBox()
        self.trim_end_spin.setRange(0, 300)
        self.trim_end_spin.setValue(0)
        self.trim_end_spin.setSuffix(" sec")
        end_layout.addWidget(self.trim_end_spin, 1)
        layout.addLayout(end_layout)

        # Crop
        crop_layout = QHBoxLayout()
        self.crop_check = QCheckBox("Crop:")
        self.crop_check.setFixedWidth(80)
        self.crop_check.toggled.connect(lambda checked: self.crop_combo.setEnabled(checked))
        crop_layout.addWidget(self.crop_check)
        self.crop_combo = QComboBox()
        self.crop_combo.addItems(['9:16', '16:9', '1:1', '4:3', '4:5'])
        self.crop_combo.setEnabled(False)
        crop_layout.addWidget(self.crop_combo, 1)
        layout.addLayout(crop_layout)

        # Zoom
        zoom_layout = QHBoxLayout()
        self.zoom_check = QCheckBox("Zoom:")
        self.zoom_check.setFixedWidth(80)
        self.zoom_check.toggled.connect(lambda checked: self.zoom_spin.setEnabled(checked))
        zoom_layout.addWidget(self.zoom_check)
        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(0.1, 5.0)
        self.zoom_spin.setSingleStep(0.1)
        self.zoom_spin.setValue(1.1)
        self.zoom_spin.setSuffix("x")
        self.zoom_spin.setEnabled(False)
        zoom_layout.addWidget(self.zoom_spin, 1)
        layout.addLayout(zoom_layout)

        # Flip horizontal
        self.flip_h_check = QCheckBox("Flip Horizontal (Mirror)")
        layout.addWidget(self.flip_h_check)

        # Transition
        trans_layout = QHBoxLayout()
        trans_label = QLabel("Transition:")
        trans_label.setFixedWidth(80)
        trans_layout.addWidget(trans_label)
        self.transition_combo = QComboBox()
        self.transition_combo.addItems(['Crossfade', 'Fade', 'Slide Left', 'None'])
        trans_layout.addWidget(self.transition_combo, 1)

        self.transition_duration_spin = QDoubleSpinBox()
        self.transition_duration_spin.setRange(0.1, 5.0)
        self.transition_duration_spin.setValue(1.0)
        self.transition_duration_spin.setSuffix("s")
        self.transition_duration_spin.setFixedWidth(70)
        trans_layout.addWidget(self.transition_duration_spin)
        layout.addLayout(trans_layout)

        # Auto-delete
        self.delete_check = QCheckBox("🗑️ Auto-delete after merge")
        self.delete_check.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        layout.addWidget(self.delete_check)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def _create_output_settings(self) -> QGroupBox:
        """Create output settings"""
        group = QGroupBox("💾 Output Settings")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)

        # Output folder
        folder_label = QLabel("Output Folder:")
        layout.addWidget(folder_label)

        folder_row = QHBoxLayout()
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setText(get_default_output_folder())
        self.output_folder_edit.setReadOnly(True)
        folder_row.addWidget(self.output_folder_edit, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse_output_folder)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        # Naming
        naming_label = QLabel("Files: batch_001.mp4, batch_002.mp4, ...")
        naming_label.setStyleSheet("color: #888; font-size: 8pt; font-style: italic;")
        layout.addWidget(naming_label)

        # Quality and format
        quality_layout = QHBoxLayout()
        quality_label = QLabel("Quality:")
        quality_label.setFixedWidth(60)
        quality_layout.addWidget(quality_label)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['Low', 'Medium', 'High', 'Ultra'])
        self.quality_combo.setCurrentIndex(2)
        quality_layout.addWidget(self.quality_combo, 1)
        layout.addLayout(quality_layout)

        format_layout = QHBoxLayout()
        format_label = QLabel("Format:")
        format_label.setFixedWidth(60)
        format_layout.addWidget(format_label)

        self.format_combo = QComboBox()
        self.format_combo.addItems(['MP4', 'MOV', 'AVI'])
        format_layout.addWidget(self.format_combo, 1)
        layout.addLayout(format_layout)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def add_folders(self):
        """Add folders to merge list"""
        folder_dialog = QFileDialog()
        folder = folder_dialog.getExistingDirectory(
            self,
            "Select Folder with Videos"
        )

        if folder:
            self._add_folder_widget(folder)
            self._update_summary()
            self._check_can_merge()

    def _add_folder_widget(self, folder_path: str):
        """Add folder widget to list"""
        # Check if already added
        for widget in self.folder_widgets:
            if widget.get_folder_path() == folder_path:
                QMessageBox.warning(self, "Folder Already Added",
                                    "This folder is already in the list.")
                return

        # Hide empty label
        self.empty_label.setVisible(False)

        index = len(self.folder_widgets)
        widget = FolderItemWidget(folder_path, index)
        widget.remove_clicked.connect(self._remove_folder)
        self.folder_widgets.append(widget)
        self.folder_list_layout.addWidget(widget)

    def _remove_folder(self, widget: FolderItemWidget):
        """Remove folder from list"""
        if widget in self.folder_widgets:
            self.folder_widgets.remove(widget)
            self.folder_list_layout.removeWidget(widget)
            widget.deleteLater()

            # Update indices
            for i, w in enumerate(self.folder_widgets):
                w.set_index(i)

            self._update_summary()
            self._check_can_merge()

            if not self.folder_widgets:
                self.empty_label.setVisible(True)

    def clear_all(self):
        """Clear all folders"""
        if self.folder_widgets:
            reply = QMessageBox.question(
                self,
                "Clear All",
                "Remove all folders?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                for widget in self.folder_widgets:
                    self.folder_list_layout.removeWidget(widget)
                    widget.deleteLater()
                self.folder_widgets.clear()
                self.empty_label.setVisible(True)
                self._update_summary()
                self._check_can_merge()

    def preview_batches(self):
        """Preview merge batches"""
        if len(self.folder_widgets) < 2:
            QMessageBox.warning(self, "Preview Batches",
                                "Need at least 2 folders to preview batches.")
            return

        # Create engine and calculate batches
        engine = BulkMergeEngine()
        folder_paths = [w.get_folder_path() for w in self.folder_widgets]

        if not engine.load_folders(folder_paths):
            QMessageBox.warning(self, "Preview Failed", "Could not load folders.")
            return

        engine.create_batches()
        summary = engine.get_batch_summary()

        # Build preview text
        preview_text = f"📊 Batch Preview\n\n"
        preview_text += f"Total Folders: {len(folder_paths)}\n"
        preview_text += f"Total Batches: {summary['total_batches']}\n"
        preview_text += f"Active Batches: {summary['active_batches']}\n"
        preview_text += f"Skipped Batches: {summary['skipped_batches']}\n"
        preview_text += f"Total Videos to Merge: {summary['total_videos']}\n\n"

        preview_text += "Folder Video Counts:\n"
        for i, count in enumerate(summary['folder_counts'], 1):
            folder_name = Path(folder_paths[i - 1]).name
            preview_text += f"  {i}. {folder_name}: {count} videos\n"

        preview_text += "\nBatches:\n"
        for batch in engine.batches:
            status_icon = "✓" if batch.status != 'skipped' else "⏭"
            preview_text += f"  {status_icon} Batch {batch.batch_number}: {len(batch.video_paths)} videos"
            if batch.status == 'skipped':
                preview_text += " (SKIPPED - only 1 video)"
            preview_text += "\n"

        # Show dialog
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Batch Preview")
        dialog.setText(preview_text)
        dialog.setIcon(QMessageBox.Information)
        dialog.exec_()

    def _browse_output_folder(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.output_folder_edit.text()
        )
        if folder:
            self.output_folder_edit.setText(folder)

    def _update_summary(self):
        """Update summary label"""
        if not self.folder_widgets:
            self.summary_label.setText("📊 Batches: 0  |  Folders: 0")
            return

        # Quick batch count estimate
        max_videos = max((w.get_video_count() for w in self.folder_widgets), default=0)
        folder_count = len(self.folder_widgets)

        self.summary_label.setText(
            f"📊 Est. Batches: ~{max_videos}  |  Folders: {folder_count}"
        )

    def _check_can_merge(self):
        """Check if merge can be started"""
        can_merge = len(self.folder_widgets) >= 2
        self.start_btn.setEnabled(can_merge)

    def start_merge(self):
        """Start bulk merging"""
        if len(self.folder_widgets) < 2:
            QMessageBox.warning(self, "Cannot Merge",
                                "Need at least 2 folders for bulk merging.")
            return

        folder_paths = [w.get_folder_path() for w in self.folder_widgets]
        output_folder = self.output_folder_edit.text()
        settings = self._build_settings()

        self.processor = BulkMergeProcessor(folder_paths, output_folder, settings)
        self.processor.merge_completed.connect(self._on_merge_completed)

        self.start_btn.setEnabled(False)
        self.start_btn.setText("⏳ Processing...")

        self.merge_started.emit(self.processor)
        self.processor.start()

        logger.info(f"Started bulk merge: {len(folder_paths)} folders")

    def _build_settings(self) -> MergeSettings:
        """Build merge settings"""
        settings = MergeSettings()
        settings.trim_start = self.trim_start_spin.value()
        settings.trim_end = self.trim_end_spin.value()
        settings.crop_enabled = self.crop_check.isChecked()
        if settings.crop_enabled:
            settings.crop_preset = self.crop_combo.currentText()
        settings.zoom_enabled = self.zoom_check.isChecked()
        if settings.zoom_enabled:
            settings.zoom_factor = self.zoom_spin.value()
        settings.flip_horizontal = self.flip_h_check.isChecked()

        transition_map = {'Crossfade': 'crossfade', 'Fade': 'fade',
                          'Slide Left': 'slide_left', 'None': 'none'}
        settings.transition_type = transition_map.get(self.transition_combo.currentText(), 'crossfade')
        settings.transition_duration = self.transition_duration_spin.value()

        settings.output_quality = self.quality_combo.currentText().lower()
        settings.output_format = self.format_combo.currentText().lower()
        settings.keep_audio = True
        settings.delete_source = self.delete_check.isChecked()

        return settings

    def _on_merge_completed(self, success: bool, results: dict):
        """Handle merge completion"""
        self.start_btn.setEnabled(True)
        self.start_btn.setText("▶️ Start Batch Merging")
        self.merge_completed.emit(success, results)

        if success:
            completed = results.get('successful', 0)
            total = results.get('total_batches', 0)
            QMessageBox.information(
                self,
                "Bulk Merge Complete",
                f"Completed: {completed}/{total} batches\n"
                f"Failed: {results.get('failed', 0)}\n"
                f"Skipped: {results.get('skipped', 0)}"
            )
        else:
            error = results.get('error', 'Unknown error')
            QMessageBox.critical(self, "Bulk Merge Failed", f"Error: {error}")

    def get_processor(self) -> Optional[BulkMergeProcessor]:
        """Get current processor"""
        return self.processor
