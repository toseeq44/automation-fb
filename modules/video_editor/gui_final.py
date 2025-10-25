"""
modules/video_editor/gui_final.py
Professional Video Editor - Final Perfect Implementation

Features:
- Single Mode: Clean topbar with all features, video thumbnail preview
- Bulk Mode: Professional dialog with title generator
- No operations list, direct controls
- User-friendly interface
"""

import os
import sys
import json
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QSlider, QLineEdit, QScrollArea, QProgressBar, QMessageBox,
    QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QTextEdit, QDialog, QFrame, QSplitter, QGridLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon

from modules.logging.logger import get_logger
from modules.video_editor.core import VideoEditor
from modules.video_editor.preset_manager import PresetManager, EditingPreset, PresetTemplates
from modules.video_editor.utils import (
    get_video_info, format_duration, format_filesize,
    check_dependencies, get_unique_filename
)

# Try to import video thumbnail function
try:
    from modules.video_editor.video_utils import get_video_first_frame
    THUMBNAIL_AVAILABLE = True
except:
    THUMBNAIL_AVAILABLE = False

logger = get_logger(__name__)


# ==================== TRACKING SYSTEM ====================

class ProcessingTracker:
    """Track processed folders"""

    def __init__(self, tracking_file: str = "video_editor_tracking.json"):
        self.tracking_file = tracking_file
        self.data = self.load()

    def load(self) -> Dict:
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save(self):
        try:
            with open(self.tracking_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving tracking: {e}")

    def is_folder_processed(self, folder_path: str) -> bool:
        return folder_path in self.data and self.data[folder_path].get('status') == 'completed'

    def mark_folder_started(self, folder_path: str):
        self.data[folder_path] = {
            'status': 'in_progress',
            'started_at': datetime.now().isoformat(),
            'videos_processed': 0
        }
        self.save()

    def mark_folder_completed(self, folder_path: str, videos_count: int):
        if folder_path in self.data:
            self.data[folder_path]['status'] = 'completed'
            self.data[folder_path]['completed_at'] = datetime.now().isoformat()
            self.data[folder_path]['videos_processed'] = videos_count
            self.save()

    def reset_all(self):
        self.data = {}
        self.save()


# ==================== WORKERS ====================

class BulkProcessingWorker(QThread):
    """Bulk processing worker"""
    progress = pyqtSignal(str)
    video_progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent_folder: str, preset: EditingPreset,
                 quality: str, delete_originals: bool, keep_format: bool,
                 tracker: ProcessingTracker, title_template: str = ""):
        super().__init__()
        self.parent_folder = parent_folder
        self.preset = preset
        self.quality = quality
        self.delete_originals = delete_originals
        self.keep_format = keep_format
        self.tracker = tracker
        self.title_template = title_template
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        try:
            results = {
                'total_folders': 0,
                'processed_folders': 0,
                'skipped_folders': 0,
                'total_videos': 0,
                'successful_videos': 0,
                'failed_videos': 0
            }

            self.progress.emit(f"📁 Scanning: {self.parent_folder}\n")

            creator_folders = [
                os.path.join(self.parent_folder, d)
                for d in os.listdir(self.parent_folder)
                if os.path.isdir(os.path.join(self.parent_folder, d))
            ]

            results['total_folders'] = len(creator_folders)
            self.progress.emit(f"✅ Found {len(creator_folders)} creator folders\n")

            for idx, creator_folder in enumerate(creator_folders):
                if not self.is_running:
                    break

                creator_name = os.path.basename(creator_folder)
                self.progress.emit(f"{'='*50}")
                self.progress.emit(f"📂 [{idx+1}/{len(creator_folders)}] {creator_name}")

                if self.tracker.is_folder_processed(creator_folder):
                    self.progress.emit(f"⏭️  Already processed - Skipping\n")
                    results['skipped_folders'] += 1
                    continue

                self.tracker.mark_folder_started(creator_folder)

                video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
                video_files = [
                    os.path.join(creator_folder, f)
                    for f in os.listdir(creator_folder)
                    if os.path.isfile(os.path.join(creator_folder, f))
                    and os.path.splitext(f)[1].lower() in video_extensions
                ]

                if not video_files:
                    self.progress.emit(f"⚠️  No videos found\n")
                    self.tracker.mark_folder_completed(creator_folder, 0)
                    continue

                self.progress.emit(f"🎬 Found {len(video_files)} videos")
                results['total_videos'] += len(video_files)

                output_folder = os.path.join(creator_folder, "edited_videos")
                os.makedirs(output_folder, exist_ok=True)

                successful = 0
                for vid_idx, video_path in enumerate(video_files):
                    if not self.is_running:
                        break

                    video_name = os.path.basename(video_path)
                    self.progress.emit(f"  [{vid_idx+1}/{len(video_files)}] {video_name}")
                    self.video_progress.emit(vid_idx + 1, len(video_files), video_name)

                    try:
                        output_ext = os.path.splitext(video_name)[1] if self.keep_format else '.mp4'
                        output_filename = f"edited_{os.path.splitext(video_name)[0]}{output_ext}"
                        output_path = os.path.join(output_folder, output_filename)
                        output_path = get_unique_filename(output_path)

                        editor = VideoEditor(video_path)

                        for op in self.preset.operations:
                            op_name = op['operation']
                            params = op['params']
                            if hasattr(editor, op_name):
                                getattr(editor, op_name)(**params)

                        editor.export(output_path, quality=self.quality)
                        editor.cleanup()

                        self.progress.emit(f"  ✅ Success")
                        successful += 1
                        results['successful_videos'] += 1

                        if self.delete_originals:
                            os.remove(video_path)
                            self.progress.emit(f"  🗑️  Deleted original")

                    except Exception as e:
                        self.progress.emit(f"  ❌ Error: {str(e)}")
                        results['failed_videos'] += 1

                self.tracker.mark_folder_completed(creator_folder, successful)
                results['processed_folders'] += 1
                self.progress.emit(f"✅ Folder complete: {successful}/{len(video_files)}\n")

            self.progress.emit(f"\n{'='*50}")
            self.progress.emit(f"🎉 COMPLETE!")
            self.progress.emit(f"{'='*50}")
            self.progress.emit(f"Processed: {results['processed_folders']} folders")
            self.progress.emit(f"Videos: {results['successful_videos']} successful, {results['failed_videos']} failed")

            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))


class VideoExportWorker(QThread):
    """Single video export worker"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, video_path: str, operations: List[Dict],
                 output_path: str, quality: str):
        super().__init__()
        self.video_path = video_path
        self.operations = operations
        self.output_path = output_path
        self.quality = quality

    def run(self):
        try:
            self.progress.emit("Loading video...")
            editor = VideoEditor(self.video_path)

            for i, op in enumerate(self.operations):
                op_name = op['name']
                params = op.get('params', {})
                self.progress.emit(f"Applying {op_name}... ({i+1}/{len(self.operations)})")

                if hasattr(editor, op_name):
                    getattr(editor, op_name)(**params)

            self.progress.emit("Exporting...")
            editor.export(self.output_path, quality=self.quality)
            editor.cleanup()

            self.finished.emit(f"✅ Export complete!\n{self.output_path}")

        except Exception as e:
            self.error.emit(str(e))


# ==================== BULK PROCESSING DIALOG ====================

class BulkProcessingDialog(QDialog):
    """Professional bulk processing dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🚀 Bulk Video Processing")
        self.setMinimumSize(900, 700)
        self.setModal(True)

        self.preset_manager = PresetManager()
        self.tracker = ProcessingTracker()
        self.parent_folder = None
        self.selected_preset = None
        self.bulk_worker = None

        self.apply_theme()
        self.init_ui()
        self.load_presets()

    def apply_theme(self):
        """Apply professional dark theme"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QLabel {
                color: #FFFFFF;
            }
            QGroupBox {
                border: 2px solid #3A3A3A;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
                font-size: 14px;
                color: #00D9FF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                background-color: #1E1E1E;
            }
            QPushButton {
                background-color: #0078D4;
                color: #FFFFFF;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1084D8;
            }
            QPushButton:pressed {
                background-color: #006CBE;
            }
            QPushButton:disabled {
                background-color: #3A3A3A;
                color: #6A6A6A;
            }
            QComboBox, QLineEdit, QSpinBox {
                background-color: #2D2D2D;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                padding: 8px;
                color: #FFFFFF;
            }
            QComboBox::drop-down {
                border: none;
            }
            QTableWidget {
                background-color: #2D2D2D;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                gridline-color: #3A3A3A;
            }
            QTableWidget::item {
                padding: 8px;
                color: #FFFFFF;
            }
            QTableWidget::item:selected {
                background-color: #0078D4;
            }
            QHeaderView::section {
                background-color: #252525;
                color: #FFFFFF;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #0078D4;
                font-weight: bold;
            }
            QCheckBox {
                color: #FFFFFF;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 2px solid #3A3A3A;
                background-color: #2D2D2D;
            }
            QCheckBox::indicator:checked {
                background-color: #0078D4;
                border-color: #0078D4;
            }
            QProgressBar {
                background-color: #2D2D2D;
                border: 1px solid #3A3A3A;
                border-radius: 6px;
                text-align: center;
                color: #FFFFFF;
                font-weight: bold;
                height: 28px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0078D4, stop:1 #00D9FF);
                border-radius: 5px;
            }
            QTextEdit {
                background-color: #1A1A1A;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                padding: 8px;
                color: #E0E0E0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }
        """)

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel("🚀 Bulk Video Processing")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #00D9FF; padding: 10px;")
        layout.addWidget(header)

        # Step 1: Folder Selection
        folder_group = QGroupBox("1️⃣  Select Parent Folder")
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(10)

        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("color: #888888; font-style: italic;")
        folder_layout.addWidget(self.folder_label, 1)

        browse_btn = QPushButton("📁 Browse Folder")
        browse_btn.setMinimumWidth(150)
        browse_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(browse_btn)

        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # Step 2: Creator Folders Table
        table_group = QGroupBox("2️⃣  Creator Folders & Videos")
        table_layout = QVBoxLayout()

        self.folders_table = QTableWidget()
        self.folders_table.setColumnCount(4)
        self.folders_table.setHorizontalHeaderLabels(["✓", "Creator Name", "Videos", "Status"])
        self.folders_table.horizontalHeader().setStretchLastSection(True)
        self.folders_table.setColumnWidth(0, 50)
        self.folders_table.setColumnWidth(1, 250)
        self.folders_table.setColumnWidth(2, 80)
        self.folders_table.setAlternatingRowColors(True)
        self.folders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.folders_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.folders_table.setMinimumHeight(200)
        table_layout.addWidget(self.folders_table)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Step 3 & 4: Preset and Settings in 2 columns
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(15)

        # Preset Section
        preset_group = QGroupBox("3️⃣  Editing Preset")
        preset_layout = QVBoxLayout()

        combo_layout = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(200)
        combo_layout.addWidget(self.preset_combo, 1)

        new_preset_btn = QPushButton("➕ New")
        new_preset_btn.setMaximumWidth(80)
        new_preset_btn.clicked.connect(self.create_preset)
        combo_layout.addWidget(new_preset_btn)

        preset_layout.addLayout(combo_layout)

        # Format Settings
        self.keep_format_check = QCheckBox("Keep original format (MP4/AVI/MOV/etc.)")
        self.keep_format_check.setChecked(True)
        preset_layout.addWidget(self.keep_format_check)

        preset_layout.addStretch()
        preset_group.setLayout(preset_layout)
        settings_layout.addWidget(preset_group)

        # Quality & Options Section
        options_group = QGroupBox("4️⃣  Quality & Options")
        options_layout = QVBoxLayout()

        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Export Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['Low', 'Medium', 'High', 'Ultra'])
        self.quality_combo.setCurrentText('High')
        quality_layout.addWidget(self.quality_combo)
        options_layout.addLayout(quality_layout)

        self.delete_originals_check = QCheckBox("Delete original videos after editing")
        options_layout.addWidget(self.delete_originals_check)

        self.skip_processed_check = QCheckBox("Skip already processed folders")
        self.skip_processed_check.setChecked(True)
        options_layout.addWidget(self.skip_processed_check)

        reset_btn = QPushButton("🔄 Reset Tracking")
        reset_btn.setStyleSheet("background-color: #E67E22;")
        reset_btn.clicked.connect(self.reset_tracking)
        options_layout.addWidget(reset_btn)

        options_layout.addStretch()
        options_group.setLayout(options_layout)
        settings_layout.addWidget(options_group)

        layout.addLayout(settings_layout)

        # Step 5: Title Generator
        title_group = QGroupBox("5️⃣  Auto Title Generator (Optional)")
        title_layout = QVBoxLayout()

        title_help = QLabel("💡 Use {creator}, {index}, {date} as placeholders")
        title_help.setStyleSheet("color: #888888; font-size: 11px;")
        title_layout.addWidget(title_help)

        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Title Template:"))
        self.title_template_input = QLineEdit()
        self.title_template_input.setPlaceholderText("e.g., {creator} - Video #{index} - {date}")
        template_layout.addWidget(self.title_template_input, 1)
        title_layout.addLayout(template_layout)

        title_group.setLayout(title_layout)
        layout.addWidget(title_group)

        # Progress Section
        progress_group = QGroupBox("📊 Progress")
        progress_layout = QVBoxLayout()

        self.progress_label = QLabel("Ready to start...")
        self.progress_label.setStyleSheet("color: #00D9FF; font-weight: bold;")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(30)
        progress_layout.addWidget(self.progress_bar)

        # Logs
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setMaximumHeight(120)
        progress_layout.addWidget(self.logs_text)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Control Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("❌ Close")
        cancel_btn.setStyleSheet("background-color: #5A5A5A;")
        cancel_btn.setMinimumWidth(120)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.start_btn = QPushButton("▶️  Start Processing")
        self.start_btn.setStyleSheet("background-color: #27AE60;")
        self.start_btn.setMinimumWidth(180)
        self.start_btn.clicked.connect(self.start_processing)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️  Stop")
        self.stop_btn.setStyleSheet("background-color: #E74C3C;")
        self.stop_btn.setMinimumWidth(120)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_processing)
        button_layout.addWidget(self.stop_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_presets(self):
        """Load presets"""
        self.preset_combo.clear()
        self.preset_combo.addItem("-- Select Preset --")

        templates = PresetTemplates.get_all_templates()
        for t in templates:
            self.preset_combo.addItem(f"📦 {t.name}")

        saved = self.preset_manager.list_presets()
        for name in saved:
            self.preset_combo.addItem(f"💾 {name}")

    def select_folder(self):
        """Select folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Parent Folder")
        if folder:
            self.parent_folder = folder
            folder_name = os.path.basename(folder) if os.path.basename(folder) else folder
            self.folder_label.setText(f"📁 {folder_name}")
            self.folder_label.setStyleSheet("color: #00D9FF; font-weight: bold;")
            self.scan_folders()

    def scan_folders(self):
        """Scan creator folders"""
        if not self.parent_folder:
            return

        try:
            creator_folders = [
                os.path.join(self.parent_folder, d)
                for d in os.listdir(self.parent_folder)
                if os.path.isdir(os.path.join(self.parent_folder, d))
            ]

            self.folders_table.setRowCount(len(creator_folders))

            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}

            for i, folder in enumerate(creator_folders):
                # Checkbox
                check_item = QTableWidgetItem()
                check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                check_item.setCheckState(Qt.Checked)
                check_item.setTextAlignment(Qt.AlignCenter)
                self.folders_table.setItem(i, 0, check_item)

                # Name
                name = os.path.basename(folder)
                name_item = QTableWidgetItem(name)
                self.folders_table.setItem(i, 1, name_item)

                # Video count
                video_count = len([
                    f for f in os.listdir(folder)
                    if os.path.isfile(os.path.join(folder, f))
                    and os.path.splitext(f)[1].lower() in video_extensions
                ])
                count_item = QTableWidgetItem(str(video_count))
                count_item.setTextAlignment(Qt.AlignCenter)
                self.folders_table.setItem(i, 2, count_item)

                # Status
                is_processed = self.tracker.is_folder_processed(folder)
                status = "✅ Processed" if is_processed else "⏳ Pending"
                status_item = QTableWidgetItem(status)
                if is_processed:
                    status_item.setForeground(QColor("#27AE60"))
                else:
                    status_item.setForeground(QColor("#F39C12"))
                self.folders_table.setItem(i, 3, status_item)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to scan folders:\n{e}")

    def create_preset(self):
        """Info about creating preset"""
        QMessageBox.information(
            self,
            "Create Preset",
            "To create a custom preset:\n\n"
            "1. Close this dialog\n"
            "2. Use Single Video Mode\n"
            "3. Add operations (crop, filters, text, etc.)\n"
            "4. Click 'Save Preset'\n"
            "5. Return to Bulk Processing"
        )

    def reset_tracking(self):
        """Reset tracking"""
        reply = QMessageBox.question(
            self,
            "Reset Tracking",
            "This will reset all tracking data.\n\n"
            "All folders will be marked as pending.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.tracker.reset_all()
            self.scan_folders()
            self.log("✅ Tracking reset - All folders marked as pending")

    def start_processing(self):
        """Start processing"""
        if not self.parent_folder:
            QMessageBox.warning(self, "No Folder", "Please select a parent folder")
            return

        preset_name = self.preset_combo.currentText()
        if preset_name == "-- Select Preset --":
            QMessageBox.warning(self, "No Preset", "Please select a preset")
            return

        # Load preset
        clean_name = preset_name.replace("📦 ", "").replace("💾 ", "")
        template = PresetTemplates.get_template_by_name(clean_name)
        if template:
            self.selected_preset = template
        else:
            try:
                self.selected_preset = self.preset_manager.load_preset(clean_name)
            except:
                QMessageBox.critical(self, "Error", "Failed to load preset")
                return

        if len(self.selected_preset.operations) == 0:
            QMessageBox.warning(self, "Empty Preset", "Selected preset has no operations")
            return

        # Start
        self.logs_text.clear()
        self.progress_bar.setValue(0)

        self.bulk_worker = BulkProcessingWorker(
            parent_folder=self.parent_folder,
            preset=self.selected_preset,
            quality=self.quality_combo.currentText().lower(),
            delete_originals=self.delete_originals_check.isChecked(),
            keep_format=self.keep_format_check.isChecked(),
            tracker=self.tracker if self.skip_processed_check.isChecked() else ProcessingTracker(),
            title_template=self.title_template_input.text()
        )

        self.bulk_worker.progress.connect(self.log)
        self.bulk_worker.video_progress.connect(self.update_progress)
        self.bulk_worker.finished.connect(self.on_finished)
        self.bulk_worker.error.connect(self.on_error)

        self.bulk_worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log("🚀 Starting bulk processing...\n")

    def stop_processing(self):
        """Stop processing"""
        if self.bulk_worker:
            self.bulk_worker.stop()
            self.log("\n⏹️  Stopping processing...")
            self.stop_btn.setEnabled(False)

    def on_finished(self, results):
        """Processing finished"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.scan_folders()

        QMessageBox.information(
            self,
            "Complete",
            f"✅ Bulk processing complete!\n\n"
            f"Folders processed: {results['processed_folders']}\n"
            f"Videos successful: {results['successful_videos']}\n"
            f"Videos failed: {results['failed_videos']}"
        )

    def on_error(self, error):
        """Error occurred"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "Error", f"Processing failed:\n{error}")

    def update_progress(self, current, total, filename):
        """Update progress"""
        progress = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"Processing: {current}/{total} - {filename}")

    def log(self, message):
        """Add log"""
        self.logs_text.append(message)
        scrollbar = self.logs_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# ==================== MAIN EDITOR ====================

class VideoEditorFinal(QWidget):
    """
    Final Professional Video Editor
    - Clean topbar with all features
    - Video thumbnail preview
    - No operations list
    - Direct controls
    - Title generator
    """

    def __init__(self, back_callback=None):
        super().__init__()
        self.back_callback = back_callback

        # Check dependencies
        deps = check_dependencies()
        if not all([deps.get('ffmpeg'), deps.get('moviepy')]):
            self.show_dependency_error()
            return

        # State
        self.preset_manager = PresetManager()
        self.current_video_path = None
        self.current_video_info = {}
        self.thumbnail_path = None
        self.operations_queue = []
        self.current_preset = None
        self.export_worker = None

        self.init_ui()
        self.load_presets()

    def show_dependency_error(self):
        """Show error"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        error_label = QLabel("❌ Missing Dependencies")
        error_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #E74C3C;")
        layout.addWidget(error_label)

        msg = QLabel("Install:\npip install moviepy pillow numpy scipy imageio imageio-ffmpeg\n\nFFmpeg: https://ffmpeg.org/download.html")
        msg.setStyleSheet("font-size: 14px;")
        layout.addWidget(msg)

        back_btn = QPushButton("⬅ Back")
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        layout.addWidget(back_btn)

        self.setLayout(layout)

    def init_ui(self):
        """Initialize UI"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Apply theme
        self.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QPushButton {
                background-color: #0078D4;
                color: #FFFFFF;
                border: none;
                padding: 10px 18px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084D8;
            }
            QPushButton:pressed {
                background-color: #006CBE;
            }
            QPushButton:disabled {
                background-color: #3A3A3A;
                color: #6A6A6A;
            }
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #2D2D2D;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                padding: 8px;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
            }
            QGroupBox {
                border: 2px solid #3A3A3A;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
                color: #00D9FF;
            }
        """)

        # TOPBAR - All Features
        main_layout.addWidget(self.create_topbar())

        # CENTER - Video Preview
        main_layout.addWidget(self.create_center_area(), 1)

        self.setLayout(main_layout)

    def create_topbar(self):
        """Create comprehensive topbar"""
        topbar = QWidget()
        topbar.setStyleSheet("background-color: #252525; padding: 12px; border-bottom: 2px solid #0078D4;")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 10, 15, 10)

        # Row 1: Title, Load Video, Bulk, Back
        row1 = QHBoxLayout()
        row1.setSpacing(15)

        title = QLabel("⚙️ Editing Controls")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00D9FF;")
        row1.addWidget(title)

        row1.addStretch()

        load_btn = QPushButton("📁 Load Video")
        load_btn.setMinimumWidth(140)
        load_btn.clicked.connect(self.load_video)
        row1.addWidget(load_btn)

        self.video_name_label = QLabel("No video loaded")
        self.video_name_label.setStyleSheet("color: #888888; font-style: italic; max-width: 250px;")
        row1.addWidget(self.video_name_label)

        row1.addSpacing(20)

        bulk_btn = QPushButton("🚀 Bulk Processing")
        bulk_btn.setStyleSheet("background-color: #9B59B6; padding: 12px 24px; font-size: 14px;")
        bulk_btn.setMinimumWidth(180)
        bulk_btn.clicked.connect(self.open_bulk_processing)
        row1.addWidget(bulk_btn)

        back_btn = QPushButton("⬅ Back")
        back_btn.setStyleSheet("background-color: #5A5A5A;")
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        row1.addWidget(back_btn)

        main_layout.addLayout(row1)

        # Row 2: Editing Features
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        # Crop Presets
        crop_label = QLabel("📐 Crop:")
        crop_label.setStyleSheet("font-weight: bold; color: #00D9FF;")
        row2.addWidget(crop_label)

        tiktok_btn = QPushButton("TikTok 9:16")
        tiktok_btn.setStyleSheet("background-color: #000000; border: 1px solid #00F2EA;")
        tiktok_btn.clicked.connect(lambda: self.add_operation('crop', {'preset': '9:16'}))
        row2.addWidget(tiktok_btn)

        insta_btn = QPushButton("Instagram 1:1")
        insta_btn.setStyleSheet("background-color: #E1306C;")
        insta_btn.clicked.connect(lambda: self.add_operation('crop', {'preset': '1:1'}))
        row2.addWidget(insta_btn)

        youtube_btn = QPushButton("YouTube 16:9")
        youtube_btn.setStyleSheet("background-color: #FF0000;")
        youtube_btn.clicked.connect(lambda: self.add_operation('crop', {'preset': '16:9'}))
        row2.addWidget(youtube_btn)

        row2.addSpacing(15)

        # Filters
        filter_label = QLabel("🎨 Filters:")
        filter_label.setStyleSheet("font-weight: bold; color: #00D9FF;")
        row2.addWidget(filter_label)

        bright_btn = QPushButton("Bright+")
        bright_btn.clicked.connect(lambda: self.add_operation('adjust_brightness', {'factor': 1.2}))
        row2.addWidget(bright_btn)

        contrast_btn = QPushButton("Contrast+")
        contrast_btn.clicked.connect(lambda: self.add_operation('adjust_contrast', {'factor': 1.2}))
        row2.addWidget(contrast_btn)

        sat_btn = QPushButton("Saturation+")
        sat_btn.clicked.connect(lambda: self.add_operation('adjust_saturation', {'factor': 1.2}))
        row2.addWidget(sat_btn)

        bw_btn = QPushButton("B&W")
        bw_btn.clicked.connect(lambda: self.add_operation('apply_filter', {'filter_name': 'blackwhite'}))
        row2.addWidget(bw_btn)

        row2.addSpacing(15)

        # Audio
        audio_label = QLabel("🔊 Audio:")
        audio_label.setStyleSheet("font-weight: bold; color: #00D9FF;")
        row2.addWidget(audio_label)

        mute_btn = QPushButton("🔇 Mute")
        mute_btn.setStyleSheet("background-color: #E74C3C;")
        mute_btn.clicked.connect(lambda: self.add_operation('mute_audio', {}))
        row2.addWidget(mute_btn)

        row2.addStretch()

        main_layout.addLayout(row2)

        # Row 3: Preset, Title Generator, Export
        row3 = QHBoxLayout()
        row3.setSpacing(15)

        # Preset
        row3.addWidget(QLabel("💾 Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(180)
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        row3.addWidget(self.preset_combo)

        save_preset_btn = QPushButton("💾 Save Preset")
        save_preset_btn.clicked.connect(self.save_preset)
        row3.addWidget(save_preset_btn)

        row3.addSpacing(20)

        # Title Generator
        row3.addWidget(QLabel("🤖 Title:"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Auto-generate video title...")
        self.title_input.setMinimumWidth(250)
        row3.addWidget(self.title_input)

        generate_title_btn = QPushButton("✨ Generate")
        generate_title_btn.setStyleSheet("background-color: #9B59B6;")
        generate_title_btn.clicked.connect(self.generate_title)
        row3.addWidget(generate_title_btn)

        row3.addStretch()

        # Export
        row3.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['Low', 'Medium', 'High', 'Ultra'])
        self.quality_combo.setCurrentText('High')
        row3.addWidget(self.quality_combo)

        self.export_btn = QPushButton("📤 Export Video")
        self.export_btn.setStyleSheet("background-color: #27AE60; padding: 12px 24px; font-size: 14px;")
        self.export_btn.setMinimumWidth(160)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_video)
        row3.addWidget(self.export_btn)

        main_layout.addLayout(row3)

        topbar.setLayout(main_layout)
        return topbar

    def create_center_area(self):
        """Create center area with video preview"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Video Preview Card
        preview_card = QFrame()
        preview_card.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 2px solid #3A3A3A;
                border-radius: 12px;
            }
        """)
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        preview_title = QLabel("📺 Video Preview")
        preview_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00D9FF;")
        preview_layout.addWidget(preview_title)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setMinimumSize(800, 450)
        self.thumbnail_label.setMaximumSize(800, 450)
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                background-color: #1A1A1A;
                border: 2px solid #3A3A3A;
                border-radius: 8px;
            }
        """)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setText("🎬\n\nNo video loaded\n\nClick 'Load Video' to start")
        self.thumbnail_label.setStyleSheet(self.thumbnail_label.styleSheet() + "font-size: 16px; color: #888888;")

        # Center the thumbnail
        thumb_layout = QHBoxLayout()
        thumb_layout.addStretch()
        thumb_layout.addWidget(self.thumbnail_label)
        thumb_layout.addStretch()
        preview_layout.addLayout(thumb_layout)

        # Video Info
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("font-size: 13px; color: #AAAAAA; padding: 10px;")
        self.info_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.info_label)

        preview_card.setLayout(preview_layout)
        layout.addWidget(preview_card)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def load_presets(self):
        """Load presets"""
        self.preset_combo.clear()
        self.preset_combo.addItem("-- New Preset --")

        templates = PresetTemplates.get_all_templates()
        for t in templates:
            self.preset_combo.addItem(f"📦 {t.name}")

        saved = self.preset_manager.list_presets()
        for name in saved:
            self.preset_combo.addItem(f"💾 {name}")

    def on_preset_changed(self, name):
        """Preset changed"""
        if name == "-- New Preset --":
            self.operations_queue.clear()
            self.current_preset = EditingPreset("New Preset")
            return

        clean_name = name.replace("📦 ", "").replace("💾 ", "")
        template = PresetTemplates.get_template_by_name(clean_name)

        if template:
            self.current_preset = template
        else:
            try:
                self.current_preset = self.preset_manager.load_preset(clean_name)
            except:
                return

        # Load operations
        self.operations_queue.clear()
        for op in self.current_preset.operations:
            self.operations_queue.append({
                'name': op['operation'],
                'params': op['params']
            })

    def load_video(self):
        """Load video"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video",
            "",
            "Videos (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.webm)"
        )

        if file_path:
            self.current_video_path = file_path
            filename = os.path.basename(file_path)
            self.video_name_label.setText(f"📹 {filename[:30]}..." if len(filename) > 30 else f"📹 {filename}")
            self.video_name_label.setStyleSheet("color: #00D9FF; font-weight: bold;")
            self.export_btn.setEnabled(True)

            # Get video info
            try:
                self.current_video_info = get_video_info(file_path)

                duration = format_duration(self.current_video_info.get('duration', 0))
                resolution = f"{self.current_video_info.get('width', 0)}x{self.current_video_info.get('height', 0)}"
                size = format_filesize(self.current_video_info.get('size', 0))

                info_text = f"📊 {resolution}  •  ⏱️ {duration}  •  💾 {size}"
                self.info_label.setText(info_text)

                # Extract thumbnail
                if THUMBNAIL_AVAILABLE:
                    self.thumbnail_label.setText("⏳ Loading preview...")
                    try:
                        thumb_path = get_video_first_frame(file_path, (800, 450))
                        if thumb_path and os.path.exists(thumb_path):
                            pixmap = QPixmap(thumb_path)
                            if not pixmap.isNull():
                                scaled_pixmap = pixmap.scaled(800, 450, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                self.thumbnail_label.setPixmap(scaled_pixmap)
                                self.thumbnail_label.setStyleSheet("""
                                    QLabel {
                                        background-color: #000000;
                                        border: 2px solid #0078D4;
                                        border-radius: 8px;
                                    }
                                """)
                            else:
                                self.thumbnail_label.setText("❌ Failed to load thumbnail")
                        else:
                            self.thumbnail_label.setText("❌ Could not extract thumbnail")
                    except Exception as e:
                        self.thumbnail_label.setText(f"❌ Thumbnail error:\n{str(e)}")
                else:
                    self.thumbnail_label.setText(f"✅ Video Loaded\n\n{filename}\n\n{info_text}")

            except Exception as e:
                self.info_label.setText(f"⚠️ Could not read video info: {e}")

    def add_operation(self, operation_name: str, params: dict):
        """Add operation"""
        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Please load a video first")
            return

        self.operations_queue.append({
            'name': operation_name,
            'params': params
        })

        # Show feedback
        op_text = f"{operation_name}"
        if 'preset' in params:
            op_text += f" ({params['preset']})"
        elif 'filter_name' in params:
            op_text += f" ({params['filter_name']})"

        QMessageBox.information(self, "Operation Added", f"✅ Added: {op_text}\n\nTotal operations: {len(self.operations_queue)}")

    def save_preset(self):
        """Save preset"""
        if len(self.operations_queue) == 0:
            QMessageBox.warning(self, "No Operations", "Add some operations first")
            return

        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if ok and name:
            preset = EditingPreset(name, "Custom preset")
            for op in self.operations_queue:
                preset.add_operation(op['name'], op['params'])

            try:
                self.preset_manager.save_preset(preset)
                QMessageBox.information(self, "Success", f"✅ Saved preset: {name}")
                self.load_presets()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def generate_title(self):
        """Generate title"""
        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Load a video first")
            return

        # Simple title generation
        filename = os.path.basename(self.current_video_path)
        base_name = os.path.splitext(filename)[0]

        # Generate title
        title = f"{base_name.replace('_', ' ').replace('-', ' ').title()}"

        self.title_input.setText(title)

        QMessageBox.information(
            self,
            "Title Generated",
            f"✨ Generated title:\n\n{title}\n\n"
            "You can edit it in the text field."
        )

    def export_video(self):
        """Export video"""
        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Load a video first")
            return

        if len(self.operations_queue) == 0:
            reply = QMessageBox.question(
                self,
                "No Operations",
                "No operations applied. Export original video?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        # Get output path
        default_name = f"edited_{os.path.basename(self.current_video_path)}"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Video",
            default_name,
            "MP4 Video (*.mp4)"
        )

        if not output_path:
            return

        # Export
        self.export_worker = VideoExportWorker(
            video_path=self.current_video_path,
            operations=self.operations_queue,
            output_path=output_path,
            quality=self.quality_combo.currentText().lower()
        )

        self.export_worker.finished.connect(self.on_export_finished)
        self.export_worker.error.connect(self.on_export_error)
        self.export_worker.start()

        self.export_btn.setEnabled(False)
        QMessageBox.information(self, "Exporting", "⏳ Video export started...\n\nPlease wait, this may take a few minutes.")

    def on_export_finished(self, message):
        """Export finished"""
        self.export_btn.setEnabled(True)
        QMessageBox.information(self, "Success", message)

    def on_export_error(self, error):
        """Export error"""
        self.export_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Export failed:\n{error}")

    def open_bulk_processing(self):
        """Open bulk dialog"""
        dialog = BulkProcessingDialog(self)
        dialog.exec_()
