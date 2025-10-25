"""
modules/video_editor/gui_professional.py
Professional Video Editor - PERFECT Implementation

Features:
- Interactive crop (CapCut-style)
- Filter dropdown with values
- Audio: Extract, Remove vocals*, Remove music* (*requires ML)
- Text overlay
- Title display with regenerate
- Professional footer
- Working video preview
- Bulk processing dialog
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QSlider, QLineEdit, QProgressBar, QMessageBox,
    QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QTextEdit, QDialog, QFrame, QSplitter, QGridLayout,
    QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPixmap, QPalette

from modules.logging.logger import get_logger
from modules.video_editor.core import VideoEditor
from modules.video_editor.preset_manager import PresetManager, EditingPreset, PresetTemplates
from modules.video_editor.utils import (
    get_video_info, format_duration, format_filesize,
    check_dependencies, get_unique_filename
)
from modules.video_editor.crop_dialog import CropDialog

# Try to import video utils
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
                    self.progress.emit(f"⏭️  Already processed\n")
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
                self.progress.emit(f"✅ Complete: {successful}/{len(video_files)}\n")

            self.progress.emit(f"\n{'='*50}")
            self.progress.emit(f"🎉 COMPLETE!")
            self.progress.emit(f"Processed: {results['processed_folders']} folders")
            self.progress.emit(f"Videos: {results['successful_videos']} successful")

            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))


class VideoExportWorker(QThread):
    """Export worker"""
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


# ====================BULK DIALOG ====================

class BulkProcessingDialog(QDialog):
    """Bulk processing dialog"""

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
        """Apply theme"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                border: 2px solid #3A3A3A;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
                color: #00D9FF;
            }
            QPushButton {
                background-color: #0078D4;
                color: #FFFFFF;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084D8;
            }
            QComboBox, QLineEdit {
                background-color: #2D2D2D;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                padding: 8px;
                color: #FFFFFF;
            }
            QTableWidget {
                background-color: #2D2D2D;
                border: 1px solid #3A3A3A;
                gridline-color: #3A3A3A;
            }
            QHeaderView::section {
                background-color: #252525;
                color: #FFFFFF;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #0078D4;
            }
            QCheckBox {
                color: #FFFFFF;
            }
            QProgressBar {
                background-color: #2D2D2D;
                border: 1px solid #3A3A3A;
                border-radius: 6px;
                text-align: center;
                color: #FFFFFF;
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
                font-family: 'Consolas', monospace;
            }
        """)

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel("🚀 Bulk Video Processing")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #00D9FF;")
        layout.addWidget(header)

        # Folder
        folder_group = QGroupBox("1️⃣  Parent Folder")
        folder_layout = QHBoxLayout()

        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("color: #888888;")
        folder_layout.addWidget(self.folder_label, 1)

        browse_btn = QPushButton("📁 Browse")
        browse_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(browse_btn)

        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # Table
        table_group = QGroupBox("2️⃣  Creator Folders")
        table_layout = QVBoxLayout()

        self.folders_table = QTableWidget()
        self.folders_table.setColumnCount(4)
        self.folders_table.setHorizontalHeaderLabels(["✓", "Name", "Videos", "Status"])
        self.folders_table.horizontalHeader().setStretchLastSection(True)
        self.folders_table.setColumnWidth(0, 50)
        self.folders_table.setColumnWidth(1, 250)
        self.folders_table.setMinimumHeight(200)
        table_layout.addWidget(self.folders_table)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Settings
        settings_layout = QHBoxLayout()

        # Preset
        preset_group = QGroupBox("3️⃣  Preset")
        preset_layout = QVBoxLayout()

        self.preset_combo = QComboBox()
        preset_layout.addWidget(self.preset_combo)

        self.keep_format_check = QCheckBox("Keep original format")
        self.keep_format_check.setChecked(True)
        preset_layout.addWidget(self.keep_format_check)

        preset_group.setLayout(preset_layout)
        settings_layout.addWidget(preset_group)

        # Quality
        quality_group = QGroupBox("4️⃣  Options")
        quality_layout = QVBoxLayout()

        q_layout = QHBoxLayout()
        q_layout.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['Low', 'Medium', 'High', 'Ultra'])
        self.quality_combo.setCurrentText('High')
        q_layout.addWidget(self.quality_combo)
        quality_layout.addLayout(q_layout)

        self.delete_originals_check = QCheckBox("Delete originals")
        quality_layout.addWidget(self.delete_originals_check)

        self.skip_processed_check = QCheckBox("Skip processed")
        self.skip_processed_check.setChecked(True)
        quality_layout.addWidget(self.skip_processed_check)

        reset_btn = QPushButton("🔄 Reset Tracking")
        reset_btn.setStyleSheet("background-color: #E67E22;")
        reset_btn.clicked.connect(self.reset_tracking)
        quality_layout.addWidget(reset_btn)

        quality_group.setLayout(quality_layout)
        settings_layout.addWidget(quality_group)

        layout.addLayout(settings_layout)

        # Title template
        title_group = QGroupBox("5️⃣  Title Template (Optional)")
        title_layout = QHBoxLayout()

        title_layout.addWidget(QLabel("Template:"))
        self.title_template_input = QLineEdit()
        self.title_template_input.setPlaceholderText("{creator} - Video #{index}")
        title_layout.addWidget(self.title_template_input)

        title_group.setLayout(title_layout)
        layout.addWidget(title_group)

        # Progress
        progress_group = QGroupBox("📊 Progress")
        progress_layout = QVBoxLayout()

        self.progress_label = QLabel("Ready")
        self.progress_label.setStyleSheet("color: #00D9FF;")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(30)
        progress_layout.addWidget(self.progress_bar)

        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setMaximumHeight(120)
        progress_layout.addWidget(self.logs_text)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("❌ Close")
        cancel_btn.setStyleSheet("background-color: #5A5A5A;")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.start_btn = QPushButton("▶️  Start")
        self.start_btn.setStyleSheet("background-color: #27AE60;")
        self.start_btn.clicked.connect(self.start_processing)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️  Stop")
        self.stop_btn.setStyleSheet("background-color: #E74C3C;")
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
            self.folder_label.setText(f"📁 {os.path.basename(folder)}")
            self.folder_label.setStyleSheet("color: #00D9FF;")
            self.scan_folders()

    def scan_folders(self):
        """Scan folders"""
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
                self.folders_table.setItem(i, 1, QTableWidgetItem(os.path.basename(folder)))

                # Videos
                video_count = len([
                    f for f in os.listdir(folder)
                    if os.path.isfile(os.path.join(folder, f))
                    and os.path.splitext(f)[1].lower() in video_extensions
                ])
                count_item = QTableWidgetItem(str(video_count))
                count_item.setTextAlignment(Qt.AlignCenter)
                self.folders_table.setItem(i, 2, count_item)

                # Status
                status = "✅ Processed" if self.tracker.is_folder_processed(folder) else "⏳ Pending"
                status_item = QTableWidgetItem(status)
                self.folders_table.setItem(i, 3, status_item)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to scan:\n{e}")

    def reset_tracking(self):
        """Reset tracking"""
        reply = QMessageBox.question(self, "Reset", "Reset tracking?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.tracker.reset_all()
            self.scan_folders()
            self.log("✅ Tracking reset")

    def start_processing(self):
        """Start"""
        if not self.parent_folder:
            QMessageBox.warning(self, "No Folder", "Select a folder")
            return

        preset_name = self.preset_combo.currentText()
        if preset_name == "-- Select Preset --":
            QMessageBox.warning(self, "No Preset", "Select a preset")
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

    def stop_processing(self):
        """Stop"""
        if self.bulk_worker:
            self.bulk_worker.stop()
            self.log("⏹️  Stopping...")
            self.stop_btn.setEnabled(False)

    def on_finished(self, results):
        """Finished"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.scan_folders()

        QMessageBox.information(
            self,
            "Complete",
            f"✅ Complete!\n\nFolders: {results['processed_folders']}\nVideos: {results['successful_videos']}"
        )

    def on_error(self, error):
        """Error"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "Error", f"Failed:\n{error}")

    def update_progress(self, current, total, filename):
        """Update progress"""
        progress = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"{current}/{total} - {filename}")

    def log(self, message):
        """Log"""
        self.logs_text.append(message)
        scrollbar = self.logs_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# ==================== MAIN EDITOR ====================

class VideoProfessional(QWidget):
    """
    Professional Video Editor - PERFECT Implementation
    All features working correctly
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
        self.current_title = ""
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

        error = QLabel("❌ Missing Dependencies")
        error.setStyleSheet("font-size: 24px; font-weight: bold; color: #E74C3C;")
        layout.addWidget(error)

        msg = QLabel("Install:\npip install moviepy pillow numpy scipy imageio imageio-ffmpeg\n\nFFmpeg: https://ffmpeg.org/download.html")
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

        # Theme
        self.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial;
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
            QPushButton:disabled {
                background-color: #3A3A3A;
                color: #6A6A6A;
            }
            QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #2D2D2D;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                padding: 8px;
                color: #FFFFFF;
            }
            QSlider::groove:horizontal {
                background: #3A3A3A;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0078D4;
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QLabel {
                color: #FFFFFF;
            }
        """)

        # TOPBAR
        main_layout.addWidget(self.create_topbar())

        # CENTER
        main_layout.addWidget(self.create_center(), 1)

        # FOOTER
        main_layout.addWidget(self.create_footer())

        self.setLayout(main_layout)

    def create_topbar(self):
        """Create topbar"""
        topbar = QWidget()
        topbar.setStyleSheet("background-color: #252525; border-bottom: 2px solid #0078D4;")

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 10, 15, 10)

        # Row 1: Load, Bulk, Back
        row1 = QHBoxLayout()
        row1.setSpacing(15)

        title = QLabel("⚙️ Editing Controls")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00D9FF;")
        row1.addWidget(title)

        row1.addStretch()

        load_btn = QPushButton("📁 Load Video")
        load_btn.clicked.connect(self.load_video)
        row1.addWidget(load_btn)

        self.video_info_label = QLabel("No video loaded")
        self.video_info_label.setStyleSheet("color: #888888;")
        row1.addWidget(self.video_info_label)

        row1.addSpacing(20)

        bulk_btn = QPushButton("🚀 Bulk Processing")
        bulk_btn.setStyleSheet("background-color: #9B59B6;")
        bulk_btn.clicked.connect(self.open_bulk_processing)
        row1.addWidget(bulk_btn)

        back_btn = QPushButton("⬅ Back")
        back_btn.setStyleSheet("background-color: #5A5A5A;")
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        row1.addWidget(back_btn)

        layout.addLayout(row1)

        # Row 2: Tools
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        # Crop
        crop_label = QLabel("🔲 Crop:")
        crop_label.setStyleSheet("font-weight: bold; color: #00D9FF;")
        row2.addWidget(crop_label)

        crop_btn = QPushButton("Open Crop Tool")
        crop_btn.clicked.connect(self.open_crop_dialog)
        row2.addWidget(crop_btn)

        row2.addSpacing(15)

        # Filter
        filter_label = QLabel("🎨 Filter:")
        filter_label.setStyleSheet("font-weight: bold; color: #00D9FF;")
        row2.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.setMinimumWidth(150)
        self.filter_combo.addItems([
            '-- Select Filter --',
            'Brightness +20%',
            'Brightness -20%',
            'Contrast +20%',
            'Contrast -20%',
            'Saturation +20%',
            'Saturation -20%',
            'Black & White',
            'Sepia',
            'Vintage',
            'Cinematic'
        ])
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)
        row2.addWidget(self.filter_combo)

        row2.addSpacing(15)

        # Audio
        audio_label = QLabel("🔊 Audio:")
        audio_label.setStyleSheet("font-weight: bold; color: #00D9FF;")
        row2.addWidget(audio_label)

        self.audio_combo = QComboBox()
        self.audio_combo.setMinimumWidth(150)
        self.audio_combo.addItems([
            '-- Select Audio --',
            'Extract Audio',
            'Mute Video',
            'Volume +20%',
            'Volume -20%',
            'Remove Vocals (ML)',
            'Remove Music (ML)'
        ])
        self.audio_combo.currentIndexChanged.connect(self.apply_audio)
        row2.addWidget(self.audio_combo)

        row2.addSpacing(15)

        # Text
        text_label = QLabel("📝 Text:")
        text_label.setStyleSheet("font-weight: bold; color: #00D9FF;")
        row2.addWidget(text_label)

        text_btn = QPushButton("Add Text")
        text_btn.clicked.connect(self.add_text)
        row2.addWidget(text_btn)

        row2.addStretch()

        layout.addLayout(row2)

        # Row 3: Title, Preset, Export
        row3 = QHBoxLayout()
        row3.setSpacing(15)

        # Title
        row3.addWidget(QLabel("🎬 Title:"))
        self.title_display = QLineEdit()
        self.title_display.setReadOnly(True)
        self.title_display.setPlaceholderText("No video loaded")
        self.title_display.setMinimumWidth(250)
        row3.addWidget(self.title_display)

        regen_btn = QPushButton("🔄 Regenerate")
        regen_btn.clicked.connect(self.regenerate_title)
        row3.addWidget(regen_btn)

        row3.addSpacing(20)

        # Preset
        row3.addWidget(QLabel("💾 Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(180)
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        row3.addWidget(self.preset_combo)

        save_preset_btn = QPushButton("💾 Save")
        save_preset_btn.clicked.connect(self.save_preset)
        row3.addWidget(save_preset_btn)

        row3.addStretch()

        # Export
        row3.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['Low', 'Medium', 'High', 'Ultra'])
        self.quality_combo.setCurrentText('High')
        row3.addWidget(self.quality_combo)

        self.export_btn = QPushButton("📤 Export Video")
        self.export_btn.setStyleSheet("background-color: #27AE60; padding: 12px 24px;")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_video)
        row3.addWidget(self.export_btn)

        layout.addLayout(row3)

        topbar.setLayout(layout)
        return topbar

    def create_center(self):
        """Create center"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        # Video preview
        preview_frame = QFrame()
        preview_frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 2px solid #3A3A3A;
                border-radius: 12px;
            }
        """)
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(20, 20, 20, 20)

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

        thumb_layout = QHBoxLayout()
        thumb_layout.addStretch()
        thumb_layout.addWidget(self.thumbnail_label)
        thumb_layout.addStretch()
        preview_layout.addLayout(thumb_layout)

        self.details_label = QLabel("")
        self.details_label.setStyleSheet("color: #AAAAAA; padding: 10px;")
        self.details_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.details_label)

        preview_frame.setLayout(preview_layout)
        layout.addWidget(preview_frame)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def create_footer(self):
        """Create footer"""
        footer = QWidget()
        footer.setStyleSheet("background-color: #252525; border-top: 2px solid #0078D4;")
        layout = QHBoxLayout()
        layout.setContentsMargins(15, 10, 15, 10)

        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #00D9FF; font-weight: bold;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Operations count
        self.ops_count_label = QLabel("Operations: 0")
        layout.addWidget(self.ops_count_label)

        layout.addSpacing(20)

        # Clear button
        clear_btn = QPushButton("🗑️ Clear All")
        clear_btn.setStyleSheet("background-color: #E74C3C;")
        clear_btn.clicked.connect(self.clear_operations)
        layout.addWidget(clear_btn)

        footer.setLayout(layout)
        return footer

    # ==================== FUNCTIONALITY ====================

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
            self.update_status()
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

        self.update_status()
        self.status_label.setText(f"Loaded preset: {clean_name}")

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

            # Generate title
            self.current_title = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').title()
            self.title_display.setText(self.current_title)

            self.video_info_label.setText(f"📹 {filename[:25]}..." if len(filename) > 25 else f"📹 {filename}")
            self.video_info_label.setStyleSheet("color: #00D9FF;")
            self.export_btn.setEnabled(True)

            # Get info
            try:
                self.current_video_info = get_video_info(file_path)

                duration = format_duration(self.current_video_info.get('duration', 0))
                resolution = f"{self.current_video_info.get('width', 0)}x{self.current_video_info.get('height', 0)}"
                size = format_filesize(self.current_video_info.get('size', 0))

                self.details_label.setText(f"📊 {resolution}  •  ⏱️ {duration}  •  💾 {size}")

                # Load thumbnail
                if THUMBNAIL_AVAILABLE:
                    self.thumbnail_label.setText("⏳ Loading...")
                    try:
                        thumb_path = get_video_first_frame(file_path, (800, 450))
                        if thumb_path and os.path.exists(thumb_path):
                            pixmap = QPixmap(thumb_path)
                            if not pixmap.isNull():
                                scaled = pixmap.scaled(800, 450, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                self.thumbnail_label.setPixmap(scaled)
                                self.thumbnail_label.setStyleSheet("""
                                    QLabel {
                                        background-color: #000000;
                                        border: 2px solid #0078D4;
                                        border-radius: 8px;
                                    }
                                """)
                            else:
                                self.thumbnail_label.setText("❌ Failed to load")
                        else:
                            self.thumbnail_label.setText("❌ Could not extract thumbnail")
                    except Exception as e:
                        self.thumbnail_label.setText(f"❌ Error:\n{str(e)}")
                else:
                    self.thumbnail_label.setText(f"✅ Video Loaded\n\n{filename}")

                self.status_label.setText("✅ Video loaded successfully")

            except Exception as e:
                self.details_label.setText(f"⚠️ Could not read video info: {e}")
                self.status_label.setText("⚠️ Video loaded with warnings")

    def open_crop_dialog(self):
        """Open crop dialog"""
        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Load a video first")
            return

        dialog = CropDialog(self.current_video_path, self.current_video_info, self)
        if dialog.exec_() == QDialog.Accepted:
            crop_params = dialog.get_crop_params()
            if crop_params:
                self.operations_queue.append({
                    'name': 'crop',
                    'params': {
                        'x1': crop_params['x1'],
                        'y1': crop_params['y1'],
                        'x2': crop_params['x2'],
                        'y2': crop_params['y2']
                    }
                })
                self.update_status()
                self.status_label.setText(f"✅ Crop added: {crop_params['width']}x{crop_params['height']}")

    def apply_filter(self, index):
        """Apply filter"""
        if index == 0:  # -- Select Filter --
            return

        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Load a video first")
            self.filter_combo.setCurrentIndex(0)
            return

        filter_name = self.filter_combo.currentText()

        if 'Brightness +20%' in filter_name:
            self.operations_queue.append({'name': 'adjust_brightness', 'params': {'factor': 1.2}})
        elif 'Brightness -20%' in filter_name:
            self.operations_queue.append({'name': 'adjust_brightness', 'params': {'factor': 0.8}})
        elif 'Contrast +20%' in filter_name:
            self.operations_queue.append({'name': 'adjust_contrast', 'params': {'factor': 1.2}})
        elif 'Contrast -20%' in filter_name:
            self.operations_queue.append({'name': 'adjust_contrast', 'params': {'factor': 0.8}})
        elif 'Saturation +20%' in filter_name:
            self.operations_queue.append({'name': 'adjust_saturation', 'params': {'factor': 1.2}})
        elif 'Saturation -20%' in filter_name:
            self.operations_queue.append({'name': 'adjust_saturation', 'params': {'factor': 0.8}})
        elif 'Black & White' in filter_name:
            self.operations_queue.append({'name': 'apply_filter', 'params': {'filter_name': 'blackwhite'}})
        elif 'Sepia' in filter_name:
            self.operations_queue.append({'name': 'apply_filter', 'params': {'filter_name': 'sepia'}})
        elif 'Vintage' in filter_name:
            self.operations_queue.append({'name': 'apply_filter', 'params': {'filter_name': 'vintage'}})
        elif 'Cinematic' in filter_name:
            self.operations_queue.append({'name': 'apply_filter', 'params': {'filter_name': 'cinematic'}})

        self.update_status()
        self.status_label.setText(f"✅ Applied: {filter_name}")
        self.filter_combo.setCurrentIndex(0)

    def apply_audio(self, index):
        """Apply audio"""
        if index == 0:  # -- Select Audio --
            return

        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Load a video first")
            self.audio_combo.setCurrentIndex(0)
            return

        audio_name = self.audio_combo.currentText()

        if 'Extract Audio' in audio_name:
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Audio",
                f"{os.path.splitext(os.path.basename(self.current_video_path))[0]}.mp3",
                "Audio Files (*.mp3 *.wav)"
            )
            if output_path:
                try:
                    editor = VideoEditor(self.current_video_path)
                    editor.extract_audio(output_path)
                    editor.cleanup()
                    QMessageBox.information(self, "Success", f"✅ Audio extracted:\n{output_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to extract audio:\n{e}")

        elif 'Mute Video' in audio_name:
            self.operations_queue.append({'name': 'mute_audio', 'params': {}})
            self.status_label.setText("✅ Mute applied")

        elif 'Volume +20%' in audio_name:
            self.operations_queue.append({'name': 'adjust_volume', 'params': {'factor': 1.2}})
            self.status_label.setText("✅ Volume +20% applied")

        elif 'Volume -20%' in audio_name:
            self.operations_queue.append({'name': 'adjust_volume', 'params': {'factor': 0.8}})
            self.status_label.setText("✅ Volume -20% applied")

        elif 'Remove Vocals' in audio_name or 'Remove Music' in audio_name:
            QMessageBox.information(
                self,
                "ML Feature",
                "🤖 Vocal/Music separation requires ML models (Spleeter/Demucs).\n\n"
                "This feature is planned for future updates.\n\n"
                "Currently available:\n"
                "• Extract Audio\n"
                "• Mute Video\n"
                "• Volume Adjustment"
            )

        self.update_status()
        self.audio_combo.setCurrentIndex(0)

    def add_text(self):
        """Add text"""
        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Load a video first")
            return

        text, ok = QInputDialog.getText(self, "Add Text", "Enter text:")
        if ok and text:
            # Simple text dialog
            from PyQt5.QtWidgets import QDialog, QFormLayout

            dialog = QDialog(self)
            dialog.setWindowTitle("Text Settings")
            dialog_layout = QFormLayout()

            position_combo = QComboBox()
            position_combo.addItems(['top', 'center', 'bottom'])
            dialog_layout.addRow("Position:", position_combo)

            font_size = QSpinBox()
            font_size.setRange(10, 200)
            font_size.setValue(50)
            dialog_layout.addRow("Font Size:", font_size)

            buttons = QHBoxLayout()
            ok_btn = QPushButton("OK")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(dialog.reject)
            buttons.addWidget(ok_btn)
            buttons.addWidget(cancel_btn)
            dialog_layout.addRow(buttons)

            dialog.setLayout(dialog_layout)

            if dialog.exec_() == QDialog.Accepted:
                self.operations_queue.append({
                    'name': 'add_text_overlay',
                    'params': {
                        'text': text,
                        'position': position_combo.currentText(),
                        'fontsize': font_size.value()
                    }
                })
                self.update_status()
                self.status_label.setText(f"✅ Text added: {text}")

    def regenerate_title(self):
        """Regenerate title"""
        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Load a video first")
            return

        filename = os.path.basename(self.current_video_path)
        self.current_title = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').title()
        self.title_display.setText(self.current_title)
        self.status_label.setText("✅ Title regenerated")

    def save_preset(self):
        """Save preset"""
        if len(self.operations_queue) == 0:
            QMessageBox.warning(self, "No Operations", "Add some operations first")
            return

        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if ok and name:
            preset = EditingPreset(name)
            for op in self.operations_queue:
                preset.add_operation(op['name'], op['params'])

            try:
                self.preset_manager.save_preset(preset)
                QMessageBox.information(self, "Success", f"✅ Saved: {name}")
                self.load_presets()
                self.status_label.setText(f"✅ Preset saved: {name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed:\n{e}")

    def clear_operations(self):
        """Clear operations"""
        if len(self.operations_queue) > 0:
            reply = QMessageBox.question(self, "Clear", "Clear all operations?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.operations_queue.clear()
                self.update_status()
                self.status_label.setText("✅ Operations cleared")

    def export_video(self):
        """Export video"""
        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Load a video first")
            return

        if len(self.operations_queue) == 0:
            reply = QMessageBox.question(self, "No Operations", "No operations. Export original?", QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

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
        self.status_label.setText("⏳ Exporting...")

        QMessageBox.information(self, "Exporting", "⏳ Export started...\n\nPlease wait.")

    def on_export_finished(self, message):
        """Export finished"""
        self.export_btn.setEnabled(True)
        self.status_label.setText("✅ Export complete!")
        QMessageBox.information(self, "Success", message)

    def on_export_error(self, error):
        """Export error"""
        self.export_btn.setEnabled(True)
        self.status_label.setText("❌ Export failed")
        QMessageBox.critical(self, "Error", f"Export failed:\n{error}")

    def open_bulk_processing(self):
        """Open bulk dialog"""
        dialog = BulkProcessingDialog(self)
        dialog.exec_()

    def update_status(self):
        """Update status"""
        self.ops_count_label.setText(f"Operations: {len(self.operations_queue)}")
