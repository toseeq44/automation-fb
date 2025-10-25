"""
modules/video_editor/gui_v3.py
Professional Video Editor with Single & Bulk Editing Modes

Features:
- Single Video Editing Mode (default): Live preview, timeline, operations list
- Bulk Processing Mode (dialog): Folder-based batch editing
- Real-time preview of operations
- Timeline scrubber
- Professional UI like Premiere/CapCut
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
    QSlider, QLineEdit, QTabWidget, QScrollArea,
    QProgressBar, QMessageBox, QInputDialog, QListWidget, QSplitter,
    QCheckBox, QColorDialog, QListWidgetItem, QTextEdit, QFrame,
    QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QStyle,
    QTimeEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QTime
from PyQt5.QtGui import QFont, QColor, QIcon
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

from modules.logging.logger import get_logger
from modules.video_editor.core import VideoEditor
from modules.video_editor.preset_manager import PresetManager, EditingPreset, PresetTemplates
from modules.video_editor.utils import (
    get_video_info, format_duration, format_filesize,
    check_dependencies, get_unique_filename
)

logger = get_logger(__name__)


# ==================== TRACKING SYSTEM ====================

class ProcessingTracker:
    """Track processed folders to avoid re-editing"""

    def __init__(self, tracking_file: str = "video_editor_tracking.json"):
        self.tracking_file = tracking_file
        self.data = self.load()

    def load(self) -> Dict:
        """Load tracking data from JSON"""
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading tracking file: {e}")
                return {}
        return {}

    def save(self):
        """Save tracking data to JSON"""
        try:
            with open(self.tracking_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving tracking file: {e}")

    def is_folder_processed(self, folder_path: str) -> bool:
        """Check if folder has already been processed"""
        return folder_path in self.data and self.data[folder_path].get('status') == 'completed'

    def mark_folder_started(self, folder_path: str):
        """Mark folder as started"""
        self.data[folder_path] = {
            'status': 'in_progress',
            'started_at': datetime.now().isoformat(),
            'videos_processed': 0
        }
        self.save()

    def mark_folder_completed(self, folder_path: str, videos_count: int):
        """Mark folder as completed"""
        if folder_path in self.data:
            self.data[folder_path]['status'] = 'completed'
            self.data[folder_path]['completed_at'] = datetime.now().isoformat()
            self.data[folder_path]['videos_processed'] = videos_count
            self.save()

    def reset_all(self):
        """Reset all tracking"""
        self.data = {}
        self.save()


# ==================== BULK PROCESSING WORKER ====================

class BulkProcessingWorker(QThread):
    """Process videos from creator folders in bulk"""
    progress = pyqtSignal(str)  # Log message
    video_progress = pyqtSignal(int, int, str)  # current, total, filename
    finished = pyqtSignal(dict)  # results
    error = pyqtSignal(str)

    def __init__(self, parent_folder: str, preset: EditingPreset,
                 quality: str, delete_originals: bool, keep_format: bool,
                 tracker: ProcessingTracker):
        super().__init__()
        self.parent_folder = parent_folder
        self.preset = preset
        self.quality = quality
        self.delete_originals = delete_originals
        self.keep_format = keep_format
        self.tracker = tracker
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

            self.progress.emit(f"📁 Scanning: {self.parent_folder}")

            # Get creator folders
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

                # Check tracking
                if self.tracker.is_folder_processed(creator_folder):
                    self.progress.emit(f"⏭️  Skipped (already processed)")
                    results['skipped_folders'] += 1
                    continue

                self.tracker.mark_folder_started(creator_folder)

                # Get videos
                video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
                video_files = [
                    os.path.join(creator_folder, f)
                    for f in os.listdir(creator_folder)
                    if os.path.isfile(os.path.join(creator_folder, f))
                    and os.path.splitext(f)[1].lower() in video_extensions
                ]

                if not video_files:
                    self.progress.emit(f"⚠️  No videos found")
                    self.tracker.mark_folder_completed(creator_folder, 0)
                    continue

                self.progress.emit(f"🎬 Found {len(video_files)} videos")
                results['total_videos'] += len(video_files)

                # Create output folder
                output_folder = os.path.join(creator_folder, "edited_videos")
                os.makedirs(output_folder, exist_ok=True)

                # Process videos
                successful = 0
                for vid_idx, video_path in enumerate(video_files):
                    if not self.is_running:
                        break

                    video_name = os.path.basename(video_path)
                    self.progress.emit(f"  [{vid_idx+1}/{len(video_files)}] {video_name}")
                    self.video_progress.emit(vid_idx + 1, len(video_files), video_name)

                    try:
                        # Determine output format
                        if self.keep_format:
                            output_ext = os.path.splitext(video_name)[1]
                        else:
                            output_ext = '.mp4'

                        output_filename = f"edited_{os.path.splitext(video_name)[0]}{output_ext}"
                        output_path = os.path.join(output_folder, output_filename)
                        output_path = get_unique_filename(output_path)

                        # Apply preset
                        editor = VideoEditor(video_path)

                        for op in self.preset.operations:
                            op_name = op['operation']
                            params = op['params']
                            if hasattr(editor, op_name):
                                getattr(editor, op_name)(**params)

                        editor.export(output_path, quality=self.quality)
                        editor.cleanup()

                        self.progress.emit(f"  ✅ Exported: {output_filename}")
                        successful += 1
                        results['successful_videos'] += 1

                        # Delete original
                        if self.delete_originals:
                            os.remove(video_path)
                            self.progress.emit(f"  🗑️  Deleted original")

                    except Exception as e:
                        self.progress.emit(f"  ❌ Error: {str(e)}")
                        results['failed_videos'] += 1

                self.tracker.mark_folder_completed(creator_folder, successful)
                results['processed_folders'] += 1
                self.progress.emit(f"✅ Completed: {successful}/{len(video_files)} videos\n")

            # Summary
            self.progress.emit(f"\n{'='*50}")
            self.progress.emit(f"🎉 BULK PROCESSING COMPLETE!")
            self.progress.emit(f"{'='*50}")
            self.progress.emit(f"Folders: {results['processed_folders']} processed, {results['skipped_folders']} skipped")
            self.progress.emit(f"Videos: {results['successful_videos']} successful, {results['failed_videos']} failed")

            self.finished.emit(results)

        except Exception as e:
            logger.error(f"Bulk processing error: {e}")
            self.error.emit(str(e))


# ==================== SINGLE VIDEO EXPORT WORKER ====================

class VideoExportWorker(QThread):
    """Export single video with all operations"""
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

            self.progress.emit("Exporting video...")
            editor.export(self.output_path, quality=self.quality)
            editor.cleanup()

            self.finished.emit(f"Video exported successfully!\n{self.output_path}")

        except Exception as e:
            logger.error(f"Export error: {e}")
            self.error.emit(str(e))


# ==================== BULK PROCESSING DIALOG ====================

class BulkProcessingDialog(QDialog):
    """Separate dialog for bulk video processing"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Video Processing")
        self.setMinimumSize(800, 600)
        self.setModal(True)

        self.preset_manager = PresetManager()
        self.tracker = ProcessingTracker()
        self.parent_folder = None
        self.creator_folders = []
        self.selected_preset = None
        self.bulk_worker = None

        self.init_ui()
        self.load_presets()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("🚀 Bulk Video Processing")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1ABC9C;")
        layout.addWidget(title)

        # Step 1: Folder Selection
        folder_group = QGroupBox("1️⃣  Select Main Folder")
        folder_layout = QHBoxLayout()

        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("color: #72767D; font-style: italic;")
        folder_layout.addWidget(self.folder_label)

        browse_btn = QPushButton("📁 Browse...")
        browse_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(browse_btn)

        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # Step 2: Creator Folders Table
        table_group = QGroupBox("2️⃣  Creator Folders Found")
        table_layout = QVBoxLayout()

        self.folders_table = QTableWidget()
        self.folders_table.setColumnCount(4)
        self.folders_table.setHorizontalHeaderLabels(["✓", "Creator Name", "Videos", "Status"])
        self.folders_table.horizontalHeader().setStretchLastSection(True)
        self.folders_table.setAlternatingRowColors(True)
        self.folders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.folders_table.setSelectionBehavior(QTableWidget.SelectRows)
        table_layout.addWidget(self.folders_table)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Step 3: Preset Selection
        preset_group = QGroupBox("3️⃣  Select Preset")
        preset_layout = QHBoxLayout()

        preset_layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(250)
        preset_layout.addWidget(self.preset_combo)

        new_preset_btn = QPushButton("➕ New")
        new_preset_btn.clicked.connect(self.create_preset)
        preset_layout.addWidget(new_preset_btn)

        preset_layout.addStretch()

        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # Step 4: Format Settings
        format_group = QGroupBox("4️⃣  Format Settings")
        format_layout = QVBoxLayout()

        self.keep_format_radio = QCheckBox("Keep original format (MP4/AVI/MOV/etc.)")
        self.keep_format_radio.setChecked(True)
        format_layout.addWidget(self.keep_format_radio)

        info = QLabel("💡 Recommended: Keep original format to preserve quality and avoid compatibility issues")
        info.setStyleSheet("color: #72767D; font-size: 10px; padding-left: 20px;")
        format_layout.addWidget(info)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # Step 5: Quality & Options
        options_group = QGroupBox("5️⃣  Quality & Options")
        options_layout = QVBoxLayout()

        # Quality
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['low', 'medium', 'high', 'ultra'])
        self.quality_combo.setCurrentText('high')
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()
        options_layout.addLayout(quality_layout)

        # Options
        self.delete_originals_check = QCheckBox("Delete original videos after editing")
        options_layout.addWidget(self.delete_originals_check)

        self.skip_processed_check = QCheckBox("Skip already processed folders (recommended)")
        self.skip_processed_check.setChecked(True)
        options_layout.addWidget(self.skip_processed_check)

        # Reset tracking
        reset_btn = QPushButton("🔄 Reset Tracking (Re-process All)")
        reset_btn.clicked.connect(self.reset_tracking)
        reset_btn.setStyleSheet("background-color: #E67E22;")
        options_layout.addWidget(reset_btn)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Progress
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #1ABC9C; font-weight: bold;")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Logs
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setMaximumHeight(150)
        self.logs_text.setStyleSheet("background-color: #1E2124; font-family: 'Courier New';")
        layout.addWidget(self.logs_text)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.start_btn = QPushButton("▶️  Start Bulk Processing")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setStyleSheet("background-color: #27AE60; padding: 10px 20px; font-size: 14px;")
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️  Stop")
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #E74C3C; padding: 10px 20px; font-size: 14px;")
        button_layout.addWidget(self.stop_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Apply theme
        self.setStyleSheet("""
            QDialog {
                background-color: #23272A;
                color: #F5F6F5;
            }
            QGroupBox {
                border: 1px solid #40444B;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #1ABC9C;
                color: #F5F6F5;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
            QComboBox, QLineEdit {
                background-color: #2C2F33;
                border: 1px solid #40444B;
                border-radius: 3px;
                padding: 6px;
                color: #F5F6F5;
            }
            QTableWidget {
                background-color: #2C2F33;
                border: 1px solid #40444B;
                gridline-color: #40444B;
            }
            QHeaderView::section {
                background-color: #1ABC9C;
                color: #F5F6F5;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
            QCheckBox {
                spacing: 8px;
            }
        """)

    def load_presets(self):
        """Load available presets"""
        self.preset_combo.clear()
        self.preset_combo.addItem("-- Select Preset --")

        # Built-in templates
        templates = PresetTemplates.get_all_templates()
        for template in templates:
            self.preset_combo.addItem(f"📦 {template.name}")

        # Saved presets
        saved = self.preset_manager.list_presets()
        for name in saved:
            self.preset_combo.addItem(f"💾 {name}")

    def select_folder(self):
        """Select parent folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Parent Folder")
        if folder:
            self.parent_folder = folder
            self.folder_label.setText(f"📁 {os.path.basename(folder)}")
            self.folder_label.setStyleSheet("color: #1ABC9C; font-weight: bold;")
            self.scan_creator_folders()

    def scan_creator_folders(self):
        """Scan and display creator folders"""
        if not self.parent_folder:
            return

        try:
            self.creator_folders = [
                os.path.join(self.parent_folder, d)
                for d in os.listdir(self.parent_folder)
                if os.path.isdir(os.path.join(self.parent_folder, d))
            ]

            self.folders_table.setRowCount(len(self.creator_folders))

            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}

            for i, folder in enumerate(self.creator_folders):
                # Checkbox
                check_item = QTableWidgetItem()
                check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                check_item.setCheckState(Qt.Checked)
                self.folders_table.setItem(i, 0, check_item)

                # Creator name
                name = os.path.basename(folder)
                self.folders_table.setItem(i, 1, QTableWidgetItem(name))

                # Video count
                video_count = len([
                    f for f in os.listdir(folder)
                    if os.path.isfile(os.path.join(folder, f))
                    and os.path.splitext(f)[1].lower() in video_extensions
                ])
                self.folders_table.setItem(i, 2, QTableWidgetItem(str(video_count)))

                # Status
                status = "✅ Processed" if self.tracker.is_folder_processed(folder) else "⏳ Pending"
                status_item = QTableWidgetItem(status)
                if "✅" in status:
                    status_item.setForeground(QColor("#27AE60"))
                self.folders_table.setItem(i, 3, status_item)

            self.folders_table.resizeColumnsToContents()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to scan folders: {e}")

    def create_preset(self):
        """Create new preset"""
        QMessageBox.information(
            self,
            "Create Preset",
            "To create a preset:\n\n"
            "1. Close this dialog\n"
            "2. Use Single Video Mode to add operations\n"
            "3. Click 'Save Preset' button\n"
            "4. Return to Bulk Processing"
        )

    def reset_tracking(self):
        """Reset tracking"""
        reply = QMessageBox.question(
            self,
            "Reset Tracking",
            "Reset tracking?\n\nAll folders will be re-processed.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.tracker.reset_all()
            self.scan_creator_folders()
            QMessageBox.information(self, "Success", "Tracking reset!")

    def start_processing(self):
        """Start bulk processing"""
        # Validation
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
            QMessageBox.warning(self, "Empty Preset", "Preset has no operations")
            return

        # Confirm
        reply = QMessageBox.question(
            self,
            "Start Processing",
            f"Start bulk processing?\n\n"
            f"Folder: {os.path.basename(self.parent_folder)}\n"
            f"Preset: {self.selected_preset.name}\n"
            f"Operations: {len(self.selected_preset.operations)}\n"
            f"Quality: {self.quality_combo.currentText()}",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Start worker
        self.logs_text.clear()
        self.progress_bar.setValue(0)

        self.bulk_worker = BulkProcessingWorker(
            parent_folder=self.parent_folder,
            preset=self.selected_preset,
            quality=self.quality_combo.currentText(),
            delete_originals=self.delete_originals_check.isChecked(),
            keep_format=self.keep_format_radio.isChecked(),
            tracker=self.tracker if self.skip_processed_check.isChecked() else ProcessingTracker()
        )

        self.bulk_worker.progress.connect(self.log)
        self.bulk_worker.video_progress.connect(self.update_progress)
        self.bulk_worker.finished.connect(self.on_finished)
        self.bulk_worker.error.connect(self.on_error)

        self.bulk_worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_processing(self):
        """Stop processing"""
        if self.bulk_worker:
            self.bulk_worker.stop()
            self.log("⏹️  Stopping...")
            self.stop_btn.setEnabled(False)

    def on_finished(self, results):
        """Processing finished"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.scan_creator_folders()  # Refresh table

        QMessageBox.information(
            self,
            "Complete",
            f"Bulk processing complete!\n\n"
            f"Folders: {results['processed_folders']} processed\n"
            f"Videos: {results['successful_videos']} successful"
        )

    def on_error(self, error):
        """Processing error"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "Error", f"Processing failed:\n{error}")

    def update_progress(self, current, total, filename):
        """Update progress"""
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"{current}/{total} - {filename}")

    def log(self, message):
        """Add log message"""
        self.logs_text.append(message)
        scrollbar = self.logs_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# ==================== MAIN VIDEO EDITOR ====================

class VideoEditorPageV3(QWidget):
    """
    Professional Video Editor
    - Default: Single video editing with live preview
    - Button: Bulk processing dialog
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
        self.operations_queue = []  # List of operations to apply
        self.current_preset = None
        self.export_worker = None

        # Media player
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)

        self.init_ui()
        self.load_presets()

    def show_dependency_error(self):
        """Show dependency error"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        error_label = QLabel("❌ Missing Dependencies")
        error_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #E74C3C;")
        layout.addWidget(error_label)

        msg = QLabel("Please install:\n\npip install moviepy pillow numpy scipy imageio imageio-ffmpeg\n\nFFmpeg: https://ffmpeg.org/download.html")
        msg.setStyleSheet("font-size: 14px; color: #F5F6F5;")
        layout.addWidget(msg)

        back_btn = QPushButton("⬅ Back")
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        layout.addWidget(back_btn)

        self.setLayout(layout)
        self.setStyleSheet("background-color: #23272A; color: #F5F6F5;")

    def init_ui(self):
        """Initialize UI"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Apply theme
        self.setStyleSheet("""
            QWidget {
                background-color: #23272A;
                color: #F5F6F5;
                font-size: 12px;
            }
            QPushButton {
                background-color: #1ABC9C;
                color: #F5F6F5;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
            QPushButton:disabled {
                background-color: #40444B;
                color: #72767D;
            }
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #2C2F33;
                border: 1px solid #40444B;
                border-radius: 3px;
                padding: 6px;
                color: #F5F6F5;
            }
            QGroupBox {
                border: 1px solid #40444B;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QListWidget {
                background-color: #2C2F33;
                border: 1px solid #40444B;
            }
            QSlider::groove:horizontal {
                background: #40444B;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #1ABC9C;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
        """)

        # TOPBAR
        main_layout.addWidget(self.create_topbar())

        # MAIN CONTENT
        content_splitter = QSplitter(Qt.Horizontal)

        # LEFTBAR - Editing Controls
        self.leftbar = self.create_leftbar()
        self.leftbar.setMaximumWidth(300)
        self.leftbar.setMinimumWidth(250)

        # CENTER - Video preview + operations
        center_widget = self.create_center_area()

        content_splitter.addWidget(self.leftbar)
        content_splitter.addWidget(center_widget)
        content_splitter.setStretchFactor(0, 0)
        content_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(content_splitter, 1)

        self.setLayout(main_layout)

    def create_topbar(self):
        """Create topbar"""
        topbar = QWidget()
        topbar.setStyleSheet("background-color: #2C2F33; padding: 10px;")
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("⚙️ Editing Controls")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1ABC9C;")
        layout.addWidget(title)

        layout.addSpacing(20)

        # Load Video
        load_btn = QPushButton("📁 Load Video")
        load_btn.clicked.connect(self.load_video)
        layout.addWidget(load_btn)

        self.video_name_label = QLabel("No video loaded")
        self.video_name_label.setStyleSheet("color: #72767D; font-style: italic;")
        layout.addWidget(self.video_name_label)

        layout.addStretch()

        # Bulk Processing Button
        bulk_btn = QPushButton("🚀 Bulk Processing")
        bulk_btn.clicked.connect(self.open_bulk_processing)
        bulk_btn.setStyleSheet("background-color: #3498DB; padding: 10px 20px; font-size: 14px;")
        layout.addWidget(bulk_btn)

        # Back
        back_btn = QPushButton("⬅ Back")
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        layout.addWidget(back_btn)

        topbar.setLayout(layout)
        return topbar

    def create_leftbar(self):
        """Create leftbar with editing controls"""
        leftbar = QWidget()
        leftbar.setStyleSheet("background-color: #2C2F33; border-right: 2px solid #40444B;")
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Preset Management
        preset_group = QGroupBox("📦 Presets")
        preset_layout = QVBoxLayout()

        combo_layout = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(150)
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        combo_layout.addWidget(self.preset_combo)

        new_btn = QPushButton("➕")
        new_btn.setMaximumWidth(40)
        new_btn.clicked.connect(self.create_new_preset)
        combo_layout.addWidget(new_btn)

        save_btn = QPushButton("💾")
        save_btn.setMaximumWidth(40)
        save_btn.clicked.connect(self.save_preset)
        combo_layout.addWidget(save_btn)

        preset_layout.addLayout(combo_layout)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # Editing tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background-color: #2C2F33;
                color: #F5F6F5;
                padding: 8px;
                border: 1px solid #40444B;
            }
            QTabBar::tab:selected {
                background-color: #1ABC9C;
            }
        """)

        self.tabs.addTab(self.create_basic_tab(), "📐 Basic")
        self.tabs.addTab(self.create_filters_tab(), "🎨 Filters")
        self.tabs.addTab(self.create_text_tab(), "📝 Text")
        self.tabs.addTab(self.create_audio_tab(), "🔊 Audio")

        layout.addWidget(self.tabs)

        # Export section
        export_group = QGroupBox("💾 Export")
        export_layout = QVBoxLayout()

        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['low', 'medium', 'high', 'ultra'])
        self.quality_combo.setCurrentText('high')
        quality_layout.addWidget(self.quality_combo)
        export_layout.addLayout(quality_layout)

        self.export_btn = QPushButton("📤 Export Video")
        self.export_btn.clicked.connect(self.export_video)
        self.export_btn.setEnabled(False)
        export_layout.addWidget(self.export_btn)

        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        leftbar.setLayout(layout)
        return leftbar

    def create_basic_tab(self):
        """Create basic tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Crop
        group = QGroupBox("Crop / Resize")
        group_layout = QVBoxLayout()

        for name, preset in [("TikTok (9:16)", '9:16'), ("Instagram (1:1)", '1:1'), ("YouTube (16:9)", '16:9')]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, p=preset: self.add_operation('crop', {'preset': p}))
            group_layout.addWidget(btn)

        group.setLayout(group_layout)
        layout.addWidget(group)

        # Speed
        group = QGroupBox("Speed")
        group_layout = QVBoxLayout()

        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Factor:"))
        speed_spin = QDoubleSpinBox()
        speed_spin.setRange(0.1, 10.0)
        speed_spin.setValue(1.0)
        speed_spin.setSingleStep(0.1)
        speed_layout.addWidget(speed_spin)
        group_layout.addLayout(speed_layout)

        apply_btn = QPushButton("Apply Speed")
        apply_btn.clicked.connect(lambda: self.add_operation('change_speed', {'factor': speed_spin.value()}))
        group_layout.addWidget(apply_btn)

        group.setLayout(group_layout)
        layout.addWidget(group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_filters_tab(self):
        """Create filters tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        filters = [
            ("Brightness +20%", 'adjust_brightness', {'factor': 1.2}),
            ("Contrast +20%", 'adjust_contrast', {'factor': 1.2}),
            ("Saturation +20%", 'adjust_saturation', {'factor': 1.2}),
            ("Black & White", 'apply_filter', {'filter_name': 'blackwhite'}),
            ("Sepia", 'apply_filter', {'filter_name': 'sepia'}),
            ("Vintage", 'apply_filter', {'filter_name': 'vintage'}),
        ]

        for name, op, params in filters:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, o=op, p=params: self.add_operation(o, p))
            layout.addWidget(btn)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_text_tab(self):
        """Create text tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Text:"))
        text_input = QLineEdit()
        layout.addWidget(text_input)

        layout.addWidget(QLabel("Position:"))
        pos_combo = QComboBox()
        pos_combo.addItems(['top', 'center', 'bottom'])
        layout.addWidget(pos_combo)

        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Size:"))
        font_size = QSpinBox()
        font_size.setRange(10, 200)
        font_size.setValue(50)
        font_layout.addWidget(font_size)
        layout.addLayout(font_layout)

        add_btn = QPushButton("Add Text")
        add_btn.clicked.connect(lambda: self.add_operation('add_text_overlay', {
            'text': text_input.text(),
            'position': pos_combo.currentText(),
            'fontsize': font_size.value()
        }))
        layout.addWidget(add_btn)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_audio_tab(self):
        """Create audio tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Volume:"))
        vol_spin = QDoubleSpinBox()
        vol_spin.setRange(0.0, 2.0)
        vol_spin.setValue(1.0)
        vol_spin.setSingleStep(0.1)
        vol_layout.addWidget(vol_spin)
        layout.addLayout(vol_layout)

        apply_btn = QPushButton("Apply Volume")
        apply_btn.clicked.connect(lambda: self.add_operation('adjust_volume', {'factor': vol_spin.value()}))
        layout.addWidget(apply_btn)

        mute_btn = QPushButton("🔇 Mute")
        mute_btn.clicked.connect(lambda: self.add_operation('mute_audio', {}))
        layout.addWidget(mute_btn)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_center_area(self):
        """Create center area with video preview and operations list"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Video Preview
        preview_label = QLabel("📺 Video Preview")
        preview_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1ABC9C;")
        layout.addWidget(preview_label)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border: 2px solid #40444B;")
        self.video_widget.setMinimumHeight(350)
        self.media_player.setVideoOutput(self.video_widget)
        layout.addWidget(self.video_widget)

        # Timeline
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.sliderMoved.connect(self.seek_video)
        layout.addWidget(self.timeline_slider)

        # Time labels
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.total_time_label = QLabel("00:00")
        time_layout.addWidget(self.current_time_label)
        time_layout.addStretch()
        self.total_time_label = QLabel("00:00")
        time_layout.addWidget(self.total_time_label)
        layout.addLayout(time_layout)

        # Controls
        controls_layout = QHBoxLayout()
        play_btn = QPushButton("▶️")
        play_btn.clicked.connect(self.media_player.play)
        controls_layout.addWidget(play_btn)

        pause_btn = QPushButton("⏸️")
        pause_btn.clicked.connect(self.media_player.pause)
        controls_layout.addWidget(pause_btn)

        stop_btn = QPushButton("⏹️")
        stop_btn.clicked.connect(self.media_player.stop)
        controls_layout.addWidget(stop_btn)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Operations List
        ops_label = QLabel("📋 Operations Applied")
        ops_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1ABC9C; margin-top: 10px;")
        layout.addWidget(ops_label)

        self.operations_list = QListWidget()
        self.operations_list.setMaximumHeight(150)
        layout.addWidget(self.operations_list)

        # Operations controls
        ops_controls = QHBoxLayout()

        clear_btn = QPushButton("🗑️ Clear All")
        clear_btn.clicked.connect(self.clear_operations)
        ops_controls.addWidget(clear_btn)

        remove_btn = QPushButton("➖ Remove Selected")
        remove_btn.clicked.connect(self.remove_selected_operation)
        ops_controls.addWidget(remove_btn)

        ops_controls.addStretch()
        layout.addLayout(ops_controls)

        widget.setLayout(layout)
        return widget

    # ==================== FUNCTIONALITY ====================

    def load_video(self):
        """Load video file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video",
            "",
            "Videos (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.webm)"
        )

        if file_path:
            self.current_video_path = file_path
            self.video_name_label.setText(f"📹 {os.path.basename(file_path)}")
            self.video_name_label.setStyleSheet("color: #1ABC9C; font-weight: bold;")

            # Load in media player
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
            self.export_btn.setEnabled(True)

            # Get video info
            try:
                info = get_video_info(file_path)
                QMessageBox.information(
                    self,
                    "Video Loaded",
                    f"Video: {os.path.basename(file_path)}\n"
                    f"Duration: {format_duration(info.get('duration', 0))}\n"
                    f"Resolution: {info.get('width', 0)}x{info.get('height', 0)}\n"
                    f"Size: {format_filesize(info.get('size', 0))}"
                )
            except:
                pass

    def load_presets(self):
        """Load presets"""
        self.preset_combo.clear()
        self.preset_combo.addItem("-- No Preset --")

        templates = PresetTemplates.get_all_templates()
        for t in templates:
            self.preset_combo.addItem(f"📦 {t.name}")

        saved = self.preset_manager.list_presets()
        for name in saved:
            self.preset_combo.addItem(f"💾 {name}")

    def on_preset_changed(self, name):
        """Preset selection changed"""
        if name == "-- No Preset --":
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

        # Load operations from preset
        self.operations_queue.clear()
        for op in self.current_preset.operations:
            self.operations_queue.append({
                'name': op['operation'],
                'params': op['params']
            })

        self.update_operations_list()

    def create_new_preset(self):
        """Create new preset"""
        name, ok = QInputDialog.getText(self, "New Preset", "Preset name:")
        if ok and name:
            self.current_preset = EditingPreset(name)
            QMessageBox.information(self, "Success", f"Created preset: {name}")

    def save_preset(self):
        """Save current preset"""
        if not self.current_preset:
            QMessageBox.warning(self, "No Preset", "Create a preset first")
            return

        # Add operations to preset
        self.current_preset.operations.clear()
        for op in self.operations_queue:
            self.current_preset.add_operation(op['name'], op['params'])

        try:
            self.preset_manager.save_preset(self.current_preset)
            QMessageBox.information(self, "Success", f"Saved preset: {self.current_preset.name}")
            self.load_presets()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def add_operation(self, operation_name: str, params: dict):
        """Add operation to queue"""
        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Load a video first")
            return

        self.operations_queue.append({
            'name': operation_name,
            'params': params
        })

        self.update_operations_list()

    def update_operations_list(self):
        """Update operations list display"""
        self.operations_list.clear()
        for i, op in enumerate(self.operations_queue):
            item_text = f"{i+1}. {op['name']} - {op['params']}"
            self.operations_list.addItem(item_text)

    def remove_selected_operation(self):
        """Remove selected operation"""
        current_row = self.operations_list.currentRow()
        if current_row >= 0:
            del self.operations_queue[current_row]
            self.update_operations_list()

    def clear_operations(self):
        """Clear all operations"""
        reply = QMessageBox.question(
            self,
            "Clear Operations",
            "Clear all operations?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.operations_queue.clear()
            self.update_operations_list()

    def export_video(self):
        """Export video with all operations"""
        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Load a video first")
            return

        if len(self.operations_queue) == 0:
            QMessageBox.warning(self, "No Operations", "Add at least one operation")
            return

        # Get output path
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Video",
            f"edited_{os.path.basename(self.current_video_path)}",
            "MP4 Video (*.mp4)"
        )

        if not output_path:
            return

        # Start export
        self.export_worker = VideoExportWorker(
            video_path=self.current_video_path,
            operations=self.operations_queue,
            output_path=output_path,
            quality=self.quality_combo.currentText()
        )

        self.export_worker.progress.connect(lambda msg: print(msg))
        self.export_worker.finished.connect(self.on_export_finished)
        self.export_worker.error.connect(self.on_export_error)

        self.export_worker.start()
        self.export_btn.setEnabled(False)

        QMessageBox.information(self, "Exporting", "Video export started...\nPlease wait.")

    def on_export_finished(self, message):
        """Export finished"""
        self.export_btn.setEnabled(True)
        QMessageBox.information(self, "Success", message)

    def on_export_error(self, error):
        """Export error"""
        self.export_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Export failed:\n{error}")

    def open_bulk_processing(self):
        """Open bulk processing dialog"""
        dialog = BulkProcessingDialog(self)
        dialog.exec_()

    def position_changed(self, position):
        """Timeline position changed"""
        self.timeline_slider.setValue(position)
        self.current_time_label.setText(self.format_time(position))

    def duration_changed(self, duration):
        """Video duration changed"""
        self.timeline_slider.setRange(0, duration)
        self.total_time_label.setText(self.format_time(duration))

    def seek_video(self, position):
        """Seek video to position"""
        self.media_player.setPosition(position)

    def format_time(self, ms):
        """Format milliseconds to MM:SS"""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
