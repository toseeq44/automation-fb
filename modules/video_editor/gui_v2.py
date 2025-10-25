"""
modules/video_editor/gui_v2.py
Improved Video Editor with Folder-Based Batch Processing
- Simple interface: Topbar (main functionality) + Leftbar (function-specific controls)
- Video preview with live editing
- Folder-based batch processing (creator folders → edited_videos subfolder)
- Tracking system to prevent re-editing
- Bulk mode with logs-only display
- Auto title generator feature
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
    QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QColor
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

    def mark_folder_failed(self, folder_path: str, error: str):
        """Mark folder as failed"""
        if folder_path in self.data:
            self.data[folder_path]['status'] = 'failed'
            self.data[folder_path]['error'] = error
            self.data[folder_path]['failed_at'] = datetime.now().isoformat()
            self.save()

    def reset_folder(self, folder_path: str):
        """Reset folder tracking (for re-processing)"""
        if folder_path in self.data:
            del self.data[folder_path]
            self.save()

    def reset_all(self):
        """Reset all tracking"""
        self.data = {}
        self.save()


# ==================== WORKER THREADS ====================

class FolderBatchProcessor(QThread):
    """Process videos from creator folders with tracking"""
    progress = pyqtSignal(str)  # Log message
    video_progress = pyqtSignal(int, int, str)  # current, total, current_file
    finished = pyqtSignal(dict)  # results summary
    error = pyqtSignal(str)

    def __init__(self, parent_folder: str, preset: EditingPreset,
                 quality: str, delete_originals: bool, tracker: ProcessingTracker,
                 show_video: bool = False):
        super().__init__()
        self.parent_folder = parent_folder
        self.preset = preset
        self.quality = quality
        self.delete_originals = delete_originals
        self.tracker = tracker
        self.show_video = show_video
        self.is_running = True

    def stop(self):
        """Stop processing"""
        self.is_running = False

    def run(self):
        """Process all creator folders"""
        try:
            results = {
                'total_folders': 0,
                'processed_folders': 0,
                'skipped_folders': 0,
                'total_videos': 0,
                'successful_videos': 0,
                'failed_videos': 0,
                'errors': []
            }

            self.progress.emit(f"📁 Scanning parent folder: {self.parent_folder}")

            # Get all creator folders
            creator_folders = [
                os.path.join(self.parent_folder, d)
                for d in os.listdir(self.parent_folder)
                if os.path.isdir(os.path.join(self.parent_folder, d))
            ]

            results['total_folders'] = len(creator_folders)
            self.progress.emit(f"✅ Found {len(creator_folders)} creator folders")

            # Process each creator folder
            for idx, creator_folder in enumerate(creator_folders):
                if not self.is_running:
                    self.progress.emit("⏹️ Processing stopped by user")
                    break

                creator_name = os.path.basename(creator_folder)
                self.progress.emit(f"\n{'='*60}")
                self.progress.emit(f"📂 Processing creator: {creator_name} ({idx+1}/{len(creator_folders)})")

                # Check if already processed
                if self.tracker.is_folder_processed(creator_folder):
                    self.progress.emit(f"⏭️ Skipping (already processed): {creator_name}")
                    results['skipped_folders'] += 1
                    continue

                # Mark as started
                self.tracker.mark_folder_started(creator_folder)

                # Get video files
                video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
                video_files = [
                    os.path.join(creator_folder, f)
                    for f in os.listdir(creator_folder)
                    if os.path.isfile(os.path.join(creator_folder, f))
                    and os.path.splitext(f)[1].lower() in video_extensions
                ]

                if not video_files:
                    self.progress.emit(f"⚠️ No videos found in: {creator_name}")
                    self.tracker.mark_folder_completed(creator_folder, 0)
                    continue

                self.progress.emit(f"🎬 Found {len(video_files)} videos")
                results['total_videos'] += len(video_files)

                # Create edited_videos subfolder
                edited_folder = os.path.join(creator_folder, "edited_videos")
                os.makedirs(edited_folder, exist_ok=True)
                self.progress.emit(f"📁 Created output folder: edited_videos/")

                # Process each video
                successful_videos = 0
                for video_idx, video_path in enumerate(video_files):
                    if not self.is_running:
                        break

                    video_name = os.path.basename(video_path)
                    self.progress.emit(f"\n  🎥 [{video_idx+1}/{len(video_files)}] {video_name}")
                    self.video_progress.emit(video_idx + 1, len(video_files), video_name)

                    try:
                        # Output path
                        output_filename = f"edited_{video_name}"
                        output_path = os.path.join(edited_folder, output_filename)
                        output_path = get_unique_filename(output_path)

                        # Apply preset
                        self.progress.emit(f"  ⚙️ Loading video...")
                        editor = VideoEditor(video_path)

                        # Apply operations from preset
                        for op_idx, operation in enumerate(self.preset.operations):
                            op_name = operation['operation']
                            params = operation['params']

                            self.progress.emit(f"  ⚙️ Applying: {op_name} ({op_idx+1}/{len(self.preset.operations)})")

                            if hasattr(editor, op_name):
                                method = getattr(editor, op_name)
                                method(**params)

                        # Export
                        self.progress.emit(f"  💾 Exporting...")
                        editor.export(output_path, quality=self.quality)
                        editor.cleanup()

                        self.progress.emit(f"  ✅ Successfully edited: {output_filename}")
                        successful_videos += 1
                        results['successful_videos'] += 1

                        # Delete original if requested
                        if self.delete_originals:
                            try:
                                os.remove(video_path)
                                self.progress.emit(f"  🗑️ Deleted original: {video_name}")
                            except Exception as e:
                                self.progress.emit(f"  ⚠️ Could not delete original: {e}")

                    except Exception as e:
                        error_msg = f"Failed to process {video_name}: {str(e)}"
                        self.progress.emit(f"  ❌ {error_msg}")
                        results['failed_videos'] += 1
                        results['errors'].append(error_msg)
                        logger.error(error_msg)

                # Mark folder as completed
                self.tracker.mark_folder_completed(creator_folder, successful_videos)
                results['processed_folders'] += 1
                self.progress.emit(f"✅ Completed creator: {creator_name} ({successful_videos}/{len(video_files)} videos)")

            # Summary
            self.progress.emit(f"\n{'='*60}")
            self.progress.emit(f"🎉 BATCH PROCESSING COMPLETE!")
            self.progress.emit(f"{'='*60}")
            self.progress.emit(f"📊 Summary:")
            self.progress.emit(f"  • Total folders: {results['total_folders']}")
            self.progress.emit(f"  • Processed: {results['processed_folders']}")
            self.progress.emit(f"  • Skipped: {results['skipped_folders']}")
            self.progress.emit(f"  • Total videos: {results['total_videos']}")
            self.progress.emit(f"  • Successful: {results['successful_videos']}")
            self.progress.emit(f"  • Failed: {results['failed_videos']}")

            self.finished.emit(results)

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            self.error.emit(str(e))


# ==================== MAIN VIDEO EDITOR GUI ====================

class VideoEditorPageV2(QWidget):
    """
    Improved Video Editor with:
    - Topbar: Main functionality (folder selection, presets, auto title, start/stop)
    - Leftbar: Function-specific controls
    - Center: Video preview + Logs
    - Folder-based batch processing with tracking
    """

    def __init__(self, back_callback=None):
        super().__init__()
        self.back_callback = back_callback

        # Check dependencies
        deps = check_dependencies()
        if not all([deps.get('ffmpeg'), deps.get('moviepy')]):
            self.show_dependency_error()
            return

        # Initialize state
        self.preset_manager = PresetManager()
        self.tracker = ProcessingTracker()
        self.current_preset = None
        self.parent_folder = None
        self.batch_processor = None

        # Video preview
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)

        self.init_ui()
        self.load_available_presets()

    def show_dependency_error(self):
        """Show dependency error message"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        error_label = QLabel("❌ Missing Dependencies")
        error_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #E74C3C;")
        layout.addWidget(error_label)

        msg = QLabel("Please install required dependencies:\n\n"
                    "pip install moviepy pillow numpy scipy imageio imageio-ffmpeg\n\n"
                    "And install FFmpeg from: https://ffmpeg.org/download.html")
        msg.setStyleSheet("font-size: 14px; color: #F5F6F5;")
        layout.addWidget(msg)

        back_btn = QPushButton("⬅ Back")
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        layout.addWidget(back_btn)

        self.setLayout(layout)
        self.setStyleSheet("background-color: #23272A; color: #F5F6F5;")

    def init_ui(self):
        """Initialize the user interface"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Apply dark theme
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
            QPushButton:pressed {
                background-color: #128C7E;
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
            QTextEdit {
                background-color: #1E2124;
                border: 1px solid #40444B;
                border-radius: 3px;
                padding: 8px;
                color: #F5F6F5;
                font-family: 'Courier New', monospace;
            }
            QProgressBar {
                background-color: #2C2F33;
                border: 1px solid #40444B;
                border-radius: 3px;
                text-align: center;
                color: #F5F6F5;
            }
            QProgressBar::chunk {
                background-color: #1ABC9C;
                border-radius: 2px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #40444B;
                background-color: #2C2F33;
            }
            QCheckBox::indicator:checked {
                background-color: #1ABC9C;
                border-color: #1ABC9C;
            }
        """)

        # TOPBAR - Main Functionality
        main_layout.addWidget(self.create_topbar())

        # MAIN CONTENT AREA
        content_splitter = QSplitter(Qt.Horizontal)

        # LEFTBAR - Function-specific controls
        self.leftbar = self.create_leftbar()
        self.leftbar.setMaximumWidth(300)
        self.leftbar.setMinimumWidth(250)

        # CENTER - Video preview + Logs
        center_widget = self.create_center_area()

        content_splitter.addWidget(self.leftbar)
        content_splitter.addWidget(center_widget)
        content_splitter.setStretchFactor(0, 0)
        content_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(content_splitter, 1)

        self.setLayout(main_layout)

    def create_topbar(self):
        """Create topbar with main functionality"""
        topbar = QWidget()
        topbar.setStyleSheet("background-color: #2C2F33; padding: 10px;")
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Title
        title = QLabel("🎬 Video Editor Pro")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1ABC9C;")
        layout.addWidget(title)

        layout.addSpacing(20)

        # Folder Selection
        folder_btn = QPushButton("📁 Select Parent Folder")
        folder_btn.clicked.connect(self.select_parent_folder)
        layout.addWidget(folder_btn)

        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("color: #72767D; font-style: italic;")
        layout.addWidget(self.folder_label)

        layout.addSpacing(20)

        # Preset Selection
        layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(180)
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        layout.addWidget(self.preset_combo)

        # Preset Management Buttons
        new_preset_btn = QPushButton("➕ New")
        new_preset_btn.clicked.connect(self.create_new_preset)
        layout.addWidget(new_preset_btn)

        save_preset_btn = QPushButton("💾 Save")
        save_preset_btn.clicked.connect(self.save_current_preset)
        layout.addWidget(save_preset_btn)

        layout.addSpacing(20)

        # Auto Title Generator (placeholder)
        auto_title_btn = QPushButton("🤖 Auto Title Generator")
        auto_title_btn.clicked.connect(self.open_auto_title_generator)
        auto_title_btn.setStyleSheet("background-color: #3498DB;")
        layout.addWidget(auto_title_btn)

        layout.addStretch()

        # Start/Stop Processing
        self.start_btn = QPushButton("▶️ Start Processing")
        self.start_btn.clicked.connect(self.start_batch_processing)
        self.start_btn.setStyleSheet("background-color: #27AE60; padding: 10px 20px; font-size: 14px;")
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.clicked.connect(self.stop_batch_processing)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #E74C3C; padding: 10px 20px; font-size: 14px;")
        layout.addWidget(self.stop_btn)

        # Back Button
        back_btn = QPushButton("⬅ Back")
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        layout.addWidget(back_btn)

        topbar.setLayout(layout)
        return topbar

    def create_leftbar(self):
        """Create leftbar with function-specific controls"""
        leftbar = QWidget()
        leftbar.setStyleSheet("background-color: #2C2F33; border-right: 2px solid #40444B;")
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Section title
        title = QLabel("⚙️ Editing Controls")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1ABC9C; padding: 5px;")
        layout.addWidget(title)

        # Tabs for different functions
        self.function_tabs = QTabWidget()
        self.function_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #40444B;
                background-color: #23272A;
            }
            QTabBar::tab {
                background-color: #2C2F33;
                color: #F5F6F5;
                padding: 8px 12px;
                margin: 2px;
                border: 1px solid #40444B;
            }
            QTabBar::tab:selected {
                background-color: #1ABC9C;
                color: #F5F6F5;
                font-weight: bold;
            }
        """)

        # Basic Tab
        self.function_tabs.addTab(self.create_basic_tab(), "📐 Basic")

        # Filters Tab
        self.function_tabs.addTab(self.create_filters_tab(), "🎨 Filters")

        # Text Tab
        self.function_tabs.addTab(self.create_text_tab(), "📝 Text")

        # Audio Tab
        self.function_tabs.addTab(self.create_audio_tab(), "🔊 Audio")

        # Settings Tab
        self.function_tabs.addTab(self.create_settings_tab(), "⚙️ Settings")

        layout.addWidget(self.function_tabs)

        leftbar.setLayout(layout)
        return leftbar

    def create_basic_tab(self):
        """Create basic editing controls tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Crop presets
        group = QGroupBox("Crop / Resize")
        group_layout = QVBoxLayout()

        layout_btn = QPushButton("TikTok (9:16)")
        layout_btn.clicked.connect(lambda: self.add_operation('crop', {'preset': '9:16'}))
        group_layout.addWidget(layout_btn)

        layout_btn = QPushButton("Instagram (1:1)")
        layout_btn.clicked.connect(lambda: self.add_operation('crop', {'preset': '1:1'}))
        group_layout.addWidget(layout_btn)

        layout_btn = QPushButton("YouTube (16:9)")
        layout_btn.clicked.connect(lambda: self.add_operation('crop', {'preset': '16:9'}))
        group_layout.addWidget(layout_btn)

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

        apply_speed_btn = QPushButton("Apply Speed")
        apply_speed_btn.clicked.connect(lambda: self.add_operation('change_speed', {'factor': speed_spin.value()}))

        group_layout.addLayout(speed_layout)
        group_layout.addWidget(apply_speed_btn)
        group.setLayout(group_layout)
        layout.addWidget(group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_filters_tab(self):
        """Create filters tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Filter buttons
        filters = [
            ("Brightness +20%", 'adjust_brightness', {'factor': 1.2}),
            ("Contrast +20%", 'adjust_contrast', {'factor': 1.2}),
            ("Saturation +20%", 'adjust_saturation', {'factor': 1.2}),
            ("Black & White", 'apply_filter', {'filter_name': 'blackwhite'}),
            ("Sepia", 'apply_filter', {'filter_name': 'sepia'}),
            ("Vintage", 'apply_filter', {'filter_name': 'vintage'}),
            ("Cinematic", 'apply_filter', {'filter_name': 'cinematic'}),
        ]

        for name, operation, params in filters:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, o=operation, p=params: self.add_operation(o, p))
            layout.addWidget(btn)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_text_tab(self):
        """Create text overlay tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Text input
        layout.addWidget(QLabel("Text:"))
        text_input = QLineEdit()
        text_input.setPlaceholderText("Enter text to overlay")
        layout.addWidget(text_input)

        # Position
        layout.addWidget(QLabel("Position:"))
        position_combo = QComboBox()
        position_combo.addItems(['top', 'center', 'bottom'])
        layout.addWidget(position_combo)

        # Font size
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font Size:"))
        font_size = QSpinBox()
        font_size.setRange(10, 200)
        font_size.setValue(50)
        font_layout.addWidget(font_size)
        layout.addLayout(font_layout)

        # Add text button
        add_text_btn = QPushButton("Add Text Overlay")
        add_text_btn.clicked.connect(lambda: self.add_operation('add_text_overlay', {
            'text': text_input.text(),
            'position': position_combo.currentText(),
            'fontsize': font_size.value()
        }))
        layout.addWidget(add_text_btn)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_audio_tab(self):
        """Create audio controls tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Volume
        group = QGroupBox("Volume")
        group_layout = QVBoxLayout()

        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Level:"))
        volume_spin = QDoubleSpinBox()
        volume_spin.setRange(0.0, 2.0)
        volume_spin.setValue(1.0)
        volume_spin.setSingleStep(0.1)
        vol_layout.addWidget(volume_spin)

        apply_vol_btn = QPushButton("Apply Volume")
        apply_vol_btn.clicked.connect(lambda: self.add_operation('adjust_volume', {'factor': volume_spin.value()}))

        group_layout.addLayout(vol_layout)
        group_layout.addWidget(apply_vol_btn)
        group.setLayout(group_layout)
        layout.addWidget(group)

        # Mute
        mute_btn = QPushButton("🔇 Mute Audio")
        mute_btn.clicked.connect(lambda: self.add_operation('mute_audio', {}))
        layout.addWidget(mute_btn)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_settings_tab(self):
        """Create settings tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Quality
        group = QGroupBox("Export Settings")
        group_layout = QVBoxLayout()

        layout_quality = QHBoxLayout()
        layout_quality.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['low', 'medium', 'high', 'ultra'])
        self.quality_combo.setCurrentText('high')
        layout_quality.addWidget(self.quality_combo)
        group_layout.addLayout(layout_quality)

        group.setLayout(group_layout)
        layout.addWidget(group)

        # Delete originals
        self.delete_originals_check = QCheckBox("Delete original videos after editing")
        self.delete_originals_check.setChecked(False)
        layout.addWidget(self.delete_originals_check)

        # Bulk mode
        self.bulk_mode_check = QCheckBox("Bulk mode (hide video preview, show logs only)")
        self.bulk_mode_check.setChecked(True)
        self.bulk_mode_check.stateChanged.connect(self.toggle_bulk_mode)
        layout.addWidget(self.bulk_mode_check)

        # Tracking management
        group = QGroupBox("Tracking System")
        group_layout = QVBoxLayout()

        info_label = QLabel("Prevents re-editing already processed folders")
        info_label.setStyleSheet("color: #72767D; font-size: 10px;")
        group_layout.addWidget(info_label)

        reset_btn = QPushButton("Reset Tracking (Re-process All)")
        reset_btn.clicked.connect(self.reset_tracking)
        reset_btn.setStyleSheet("background-color: #E67E22;")
        group_layout.addWidget(reset_btn)

        group.setLayout(group_layout)
        layout.addWidget(group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_center_area(self):
        """Create center area with video preview and logs"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video preview (can be hidden in bulk mode)
        self.video_preview_container = QWidget()
        video_layout = QVBoxLayout()
        video_layout.setContentsMargins(10, 10, 10, 10)

        preview_label = QLabel("📺 Video Preview")
        preview_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1ABC9C; padding: 5px;")
        video_layout.addWidget(preview_label)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border: 2px solid #40444B;")
        self.video_widget.setMinimumHeight(300)
        self.media_player.setVideoOutput(self.video_widget)
        video_layout.addWidget(self.video_widget)

        # Video controls
        controls_layout = QHBoxLayout()
        play_btn = QPushButton("▶️ Play")
        play_btn.clicked.connect(self.media_player.play)
        controls_layout.addWidget(play_btn)

        pause_btn = QPushButton("⏸️ Pause")
        pause_btn.clicked.connect(self.media_player.pause)
        controls_layout.addWidget(pause_btn)

        stop_btn = QPushButton("⏹️ Stop")
        stop_btn.clicked.connect(self.media_player.stop)
        controls_layout.addWidget(stop_btn)

        controls_layout.addStretch()
        video_layout.addLayout(controls_layout)

        self.video_preview_container.setLayout(video_layout)
        layout.addWidget(self.video_preview_container)

        # Logs area
        logs_label = QLabel("📋 Processing Logs")
        logs_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1ABC9C; padding: 10px;")
        layout.addWidget(logs_label)

        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setMinimumHeight(200)
        layout.addWidget(self.logs_text, 1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        widget.setLayout(layout)
        return widget

    # ==================== FUNCTIONALITY ====================

    def select_parent_folder(self):
        """Select parent folder containing creator folders"""
        folder = QFileDialog.getExistingDirectory(self, "Select Parent Folder")
        if folder:
            self.parent_folder = folder
            self.folder_label.setText(f"📁 {os.path.basename(folder)}")
            self.folder_label.setStyleSheet("color: #1ABC9C; font-weight: bold;")
            self.log(f"✅ Selected parent folder: {folder}")

            # Show folder structure preview
            self.preview_folder_structure()

    def preview_folder_structure(self):
        """Preview creator folders in selected parent folder"""
        if not self.parent_folder:
            return

        try:
            creator_folders = [
                d for d in os.listdir(self.parent_folder)
                if os.path.isdir(os.path.join(self.parent_folder, d))
            ]

            self.log(f"\n📂 Found {len(creator_folders)} creator folders:")
            for folder in creator_folders[:10]:  # Show first 10
                folder_path = os.path.join(self.parent_folder, folder)

                # Count videos
                video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
                video_count = len([
                    f for f in os.listdir(folder_path)
                    if os.path.isfile(os.path.join(folder_path, f))
                    and os.path.splitext(f)[1].lower() in video_extensions
                ])

                # Check if processed
                status = "✅ Processed" if self.tracker.is_folder_processed(folder_path) else "⏳ Pending"

                self.log(f"  • {folder} - {video_count} videos - {status}")

            if len(creator_folders) > 10:
                self.log(f"  ... and {len(creator_folders) - 10} more folders")

        except Exception as e:
            self.log(f"❌ Error previewing folders: {e}")

    def load_available_presets(self):
        """Load available presets into combo box"""
        self.preset_combo.clear()
        self.preset_combo.addItem("-- No Preset --")

        # Add built-in templates
        templates = PresetTemplates.get_all_templates()
        for template in templates:
            self.preset_combo.addItem(f"📦 {template.name}")

        # Add saved presets
        saved_presets = self.preset_manager.list_presets()
        for preset_name in saved_presets:
            self.preset_combo.addItem(f"💾 {preset_name}")

    def on_preset_changed(self, preset_name):
        """Handle preset selection change"""
        if preset_name == "-- No Preset --":
            self.current_preset = None
            self.log("❌ No preset selected")
            return

        # Remove emoji prefix
        clean_name = preset_name.replace("📦 ", "").replace("💾 ", "")

        # Try to load from templates first
        template = PresetTemplates.get_template_by_name(clean_name)
        if template:
            self.current_preset = template
            self.log(f"✅ Loaded template: {clean_name}")
            self.log(f"   Operations: {len(template.operations)}")
            return

        # Try to load from saved presets
        try:
            preset = self.preset_manager.load_preset(clean_name)
            self.current_preset = preset
            self.log(f"✅ Loaded preset: {clean_name}")
            self.log(f"   Operations: {len(preset.operations)}")
        except Exception as e:
            self.log(f"❌ Error loading preset: {e}")
            self.current_preset = None

    def create_new_preset(self):
        """Create a new preset"""
        name, ok = QInputDialog.getText(self, "New Preset", "Enter preset name:")
        if ok and name:
            self.current_preset = EditingPreset(name)
            self.log(f"✅ Created new preset: {name}")

    def save_current_preset(self):
        """Save current preset"""
        if not self.current_preset:
            QMessageBox.warning(self, "No Preset", "Please create or select a preset first")
            return

        try:
            self.preset_manager.save_preset(self.current_preset)
            self.log(f"💾 Saved preset: {self.current_preset.name}")
            self.load_available_presets()
            QMessageBox.information(self, "Success", f"Preset '{self.current_preset.name}' saved successfully!")
        except Exception as e:
            self.log(f"❌ Error saving preset: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save preset: {e}")

    def add_operation(self, operation_name: str, params: dict):
        """Add operation to current preset"""
        if not self.current_preset:
            QMessageBox.warning(self, "No Preset", "Please create or select a preset first")
            return

        self.current_preset.add_operation(operation_name, params)
        self.log(f"➕ Added operation: {operation_name} with params {params}")

    def open_auto_title_generator(self):
        """Open auto title generator (placeholder)"""
        QMessageBox.information(
            self,
            "Auto Title Generator",
            "🤖 Auto Title Generator\n\n"
            "This feature will generate video titles automatically.\n\n"
            "Functionality coming soon!\n\n"
            "Features planned:\n"
            "• AI-powered title generation\n"
            "• Keyword extraction\n"
            "• SEO optimization\n"
            "• Multi-language support"
        )

    def start_batch_processing(self):
        """Start batch processing of creator folders"""
        # Validation
        if not self.parent_folder:
            QMessageBox.warning(self, "No Folder", "Please select a parent folder first")
            return

        if not self.current_preset or len(self.current_preset.operations) == 0:
            QMessageBox.warning(self, "No Preset", "Please select a preset with operations first")
            return

        # Confirm
        reply = QMessageBox.question(
            self,
            "Start Processing",
            f"Start batch processing?\n\n"
            f"Folder: {os.path.basename(self.parent_folder)}\n"
            f"Preset: {self.current_preset.name}\n"
            f"Operations: {len(self.current_preset.operations)}\n"
            f"Quality: {self.quality_combo.currentText()}\n"
            f"Delete originals: {'Yes' if self.delete_originals_check.isChecked() else 'No'}",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Clear logs
        self.logs_text.clear()
        self.progress_bar.setValue(0)

        # Start processing
        self.log("🚀 Starting batch processing...")

        self.batch_processor = FolderBatchProcessor(
            parent_folder=self.parent_folder,
            preset=self.current_preset,
            quality=self.quality_combo.currentText(),
            delete_originals=self.delete_originals_check.isChecked(),
            tracker=self.tracker,
            show_video=not self.bulk_mode_check.isChecked()
        )

        self.batch_processor.progress.connect(self.log)
        self.batch_processor.video_progress.connect(self.update_video_progress)
        self.batch_processor.finished.connect(self.on_processing_finished)
        self.batch_processor.error.connect(self.on_processing_error)

        self.batch_processor.start()

        # Update UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_batch_processing(self):
        """Stop batch processing"""
        if self.batch_processor:
            self.batch_processor.stop()
            self.log("\n⏹️ Stopping processing...")
            self.stop_btn.setEnabled(False)

    def on_processing_finished(self, results):
        """Handle processing finished"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        QMessageBox.information(
            self,
            "Processing Complete",
            f"✅ Batch processing complete!\n\n"
            f"Total folders: {results['total_folders']}\n"
            f"Processed: {results['processed_folders']}\n"
            f"Skipped: {results['skipped_folders']}\n\n"
            f"Total videos: {results['total_videos']}\n"
            f"Successful: {results['successful_videos']}\n"
            f"Failed: {results['failed_videos']}"
        )

    def on_processing_error(self, error):
        """Handle processing error"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log(f"\n❌ Processing error: {error}")
        QMessageBox.critical(self, "Error", f"Processing failed:\n{error}")

    def update_video_progress(self, current, total, filename):
        """Update progress bar"""
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)
        self.progress_bar.setFormat(f"{current}/{total} - {filename}")

    def log(self, message: str):
        """Add message to logs"""
        self.logs_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.logs_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def toggle_bulk_mode(self, state):
        """Toggle bulk mode (hide/show video preview)"""
        if state == Qt.Checked:
            self.video_preview_container.hide()
            self.log("📋 Bulk mode: Video preview hidden, logs only")
        else:
            self.video_preview_container.show()
            self.log("📺 Normal mode: Video preview enabled")

    def reset_tracking(self):
        """Reset tracking system"""
        reply = QMessageBox.question(
            self,
            "Reset Tracking",
            "Are you sure you want to reset tracking?\n\n"
            "This will allow re-processing of all folders.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.tracker.reset_all()
            self.log("🔄 Tracking reset! All folders can now be re-processed.")
            QMessageBox.information(self, "Success", "Tracking has been reset!")
