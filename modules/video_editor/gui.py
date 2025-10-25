"""
modules/video_editor/gui.py
Complete Video Editor GUI with Preset Project Management
CapCut-style workflow: Edit -> Save Preset -> Apply to Multiple Videos
"""

import os
import sys
from typing import Optional, List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QSlider, QLineEdit, QTabWidget, QScrollArea,
    QProgressBar, QMessageBox, QInputDialog, QListWidget, QSplitter,
    QCheckBox, QColorDialog, QListWidgetItem, QTextEdit, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from modules.logging.logger import get_logger
from modules.video_editor.core import VideoEditor
from modules.video_editor.preset_manager import PresetManager, EditingPreset, PresetTemplates
from modules.video_editor.utils import (
    get_video_info, format_duration, format_filesize,
    check_dependencies, get_unique_filename
)

logger = get_logger(__name__)


# ==================== WORKER THREADS ====================

class VideoProcessWorker(QThread):
    """Worker thread for single video processing"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, operations: list, video_path: str, output_path: str, quality: str):
        super().__init__()
        self.operations = operations
        self.video_path = video_path
        self.output_path = output_path
        self.quality = quality

    def run(self):
        try:
            self.progress.emit("Loading video...")
            editor = VideoEditor(self.video_path)

            # Apply operations
            for i, operation in enumerate(self.operations):
                op_name = operation['name']
                params = operation.get('params', {})
                self.progress.emit(f"Applying {op_name}... ({i+1}/{len(self.operations)})")

                if hasattr(editor, op_name):
                    method = getattr(editor, op_name)
                    method(**params)

            # Export
            self.progress.emit("Exporting video...")
            editor.export(self.output_path, quality=self.quality)
            editor.cleanup()

            self.finished.emit(f"Video exported successfully!\n{self.output_path}")

        except Exception as e:
            logger.error(f"Video processing error: {e}")
            self.error.emit(f"Error: {str(e)}")


class BatchProcessWorker(QThread):
    """Worker thread for batch processing with preset"""
    progress = pyqtSignal(int, int, str, str)  # current, total, filename, message
    finished = pyqtSignal(list)  # results
    error = pyqtSignal(str)

    def __init__(self, preset: EditingPreset, video_paths: List[str],
                 output_dir: str, quality: str):
        super().__init__()
        self.preset = preset
        self.video_paths = video_paths
        self.output_dir = output_dir
        self.quality = quality

    def run(self):
        try:
            from modules.video_editor.preset_manager import PresetManager

            manager = PresetManager()

            def progress_callback(current, total, filename, message):
                self.progress.emit(current, total, filename, message)

            results = manager.apply_preset_to_multiple_videos(
                self.preset,
                self.video_paths,
                self.output_dir,
                self.quality,
                progress_callback=progress_callback
            )

            self.finished.emit(results)

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            self.error.emit(f"Error: {str(e)}")


# ==================== MAIN GUI ====================

class VideoEditorPage(QWidget):
    """
    Complete Video Editor with Preset Project Management
    CapCut-style workflow
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
        self.selected_videos = []  # List of selected video paths
        self.operations_queue = []  # Current operations
        self.current_preset = None  # Currently loaded preset

        self.init_ui()

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
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Apply dark theme
        self.setStyleSheet("""
            QWidget {
                background-color: #23272A;
                color: #F5F6F5;
                font-size: 12px;
            }
            QGroupBox {
                border: 1px solid #40444B;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
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
                padding: 6px 12px;
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
                padding: 4px;
                color: #F5F6F5;
            }
            QListWidget {
                background-color: #2C2F33;
                border: 1px solid #40444B;
                border-radius: 3px;
            }
            QSlider::groove:horizontal {
                background: #40444B;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #1ABC9C;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """)

        # Header
        main_layout.addWidget(self.create_header())

        # Preset Management Bar
        main_layout.addWidget(self.create_preset_bar())

        # Main Content Area
        content_splitter = QSplitter(Qt.Horizontal)

        # Left: Feature Sidebar (collapsible)
        self.features_sidebar = self.create_features_sidebar()
        self.features_sidebar.setMaximumWidth(280)
        self.features_sidebar.setMinimumWidth(200)

        # Center: Video Selection + Operations
        center_widget = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setSpacing(5)

        center_layout.addWidget(self.create_video_selection_area())
        center_layout.addWidget(self.create_operations_queue())

        center_widget.setLayout(center_layout)

        content_splitter.addWidget(self.features_sidebar)
        content_splitter.addWidget(center_widget)
        content_splitter.setStretchFactor(0, 0)
        content_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(content_splitter, 1)

        # Footer: Export Controls
        main_layout.addWidget(self.create_export_footer())

        self.setLayout(main_layout)

    def create_header(self):
        """Create header section"""
        header = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)

        title = QLabel("🎬 Video Editor - Preset Project System")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1ABC9C;")
        layout.addWidget(title)

        layout.addStretch()

        back_btn = QPushButton("⬅ Back")
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        layout.addWidget(back_btn)

        header.setLayout(layout)
        return header

    def create_preset_bar(self):
        """Create preset management bar"""
        bar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)

        # Preset selection
        layout.addWidget(QLabel("Current Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(200)
        self.preset_combo.addItem("-- No Preset --")
        self.preset_combo.currentTextChanged.connect(self.on_preset_selected)
        layout.addWidget(self.preset_combo)

        # Preset actions
        new_preset_btn = QPushButton("📝 New Preset")
        new_preset_btn.clicked.connect(self.create_new_preset)
        layout.addWidget(new_preset_btn)

        save_preset_btn = QPushButton("💾 Save Preset")
        save_preset_btn.clicked.connect(self.save_current_preset)
        layout.addWidget(save_preset_btn)

        load_preset_btn = QPushButton("📂 Load Preset")
        load_preset_btn.clicked.connect(self.load_preset)
        layout.addWidget(load_preset_btn)

        delete_preset_btn = QPushButton("🗑️ Delete")
        delete_preset_btn.clicked.connect(self.delete_preset)
        layout.addWidget(delete_preset_btn)

        layout.addStretch()

        # Templates
        templates_btn = QPushButton("⭐ Templates")
        templates_btn.clicked.connect(self.show_templates)
        layout.addWidget(templates_btn)

        bar.setLayout(layout)
        return bar

    def create_features_sidebar(self):
        """Create left sidebar with editing features"""
        sidebar = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # Feature tabs
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.West)

        tabs.addTab(self.create_basic_tab(), "Basic")
        tabs.addTab(self.create_text_tab(), "Text")
        tabs.addTab(self.create_audio_tab(), "Audio")
        tabs.addTab(self.create_filters_tab(), "Filters")

        layout.addWidget(tabs)

        sidebar.setLayout(layout)
        return sidebar

    def create_basic_tab(self):
        """Basic editing features"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)

        # Trim
        layout.addWidget(QLabel("⏱️ Trim (seconds):"))
        trim_layout = QHBoxLayout()
        self.trim_start = QDoubleSpinBox()
        self.trim_start.setMaximum(9999)
        self.trim_end = QDoubleSpinBox()
        self.trim_end.setMaximum(9999)
        self.trim_end.setValue(30)
        trim_layout.addWidget(self.trim_start)
        trim_layout.addWidget(QLabel("-"))
        trim_layout.addWidget(self.trim_end)
        layout.addLayout(trim_layout)

        trim_btn = QPushButton("Add Trim")
        trim_btn.clicked.connect(self.add_trim_operation)
        layout.addWidget(trim_btn)

        # Crop
        layout.addWidget(QLabel("📐 Crop:"))
        self.crop_preset = QComboBox()
        self.crop_preset.addItems(["9:16 (TikTok)", "16:9 (YouTube)", "1:1 (Square)", "4:5 (Portrait)"])
        layout.addWidget(self.crop_preset)

        crop_btn = QPushButton("Add Crop")
        crop_btn.clicked.connect(self.add_crop_operation)
        layout.addWidget(crop_btn)

        # Rotate/Flip
        layout.addWidget(QLabel("🔄 Transform:"))
        rotate_layout = QHBoxLayout()
        r90 = QPushButton("90°")
        r90.clicked.connect(lambda: self.add_operation('rotate', {'angle': 90}))
        r180 = QPushButton("180°")
        r180.clicked.connect(lambda: self.add_operation('rotate', {'angle': 180}))
        rotate_layout.addWidget(r90)
        rotate_layout.addWidget(r180)
        layout.addLayout(rotate_layout)

        flip_layout = QHBoxLayout()
        fh = QPushButton("Flip H")
        fh.clicked.connect(lambda: self.add_operation('flip_horizontal', {}))
        fv = QPushButton("Flip V")
        fv.clicked.connect(lambda: self.add_operation('flip_vertical', {}))
        flip_layout.addWidget(fh)
        flip_layout.addWidget(fv)
        layout.addLayout(flip_layout)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_text_tab(self):
        """Text overlay features"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)

        layout.addWidget(QLabel("📝 Text:"))
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter text...")
        layout.addWidget(self.text_input)

        layout.addWidget(QLabel("Size:"))
        self.text_size = QSpinBox()
        self.text_size.setRange(10, 200)
        self.text_size.setValue(50)
        layout.addWidget(self.text_size)

        layout.addWidget(QLabel("Position:"))
        self.text_position = QComboBox()
        self.text_position.addItems(["Center-Bottom", "Center-Top", "Left-Bottom", "Right-Bottom"])
        layout.addWidget(self.text_position)

        self.text_color = 'white'
        color_btn = QPushButton("Choose Color")
        color_btn.clicked.connect(self.choose_text_color)
        layout.addWidget(color_btn)

        add_text_btn = QPushButton("Add Text")
        add_text_btn.clicked.connect(self.add_text_operation)
        layout.addWidget(add_text_btn)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_audio_tab(self):
        """Audio features"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)

        layout.addWidget(QLabel("🔊 Volume:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 200)
        self.volume_slider.setValue(100)
        layout.addWidget(self.volume_slider)

        vol_btn = QPushButton("Adjust Volume")
        vol_btn.clicked.connect(self.add_volume_operation)
        layout.addWidget(vol_btn)

        remove_audio_btn = QPushButton("Remove Audio")
        remove_audio_btn.clicked.connect(lambda: self.add_operation('remove_audio', {}))
        layout.addWidget(remove_audio_btn)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_filters_tab(self):
        """Filter features"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)

        layout.addWidget(QLabel("🎨 Quick Filters:"))

        filters = [
            ("Cinematic", 'cinematic'),
            ("Vintage", 'vintage'),
            ("Grayscale", 'grayscale'),
            ("Sepia", 'sepia'),
            ("Warm", 'warm'),
            ("Cool", 'cool')
        ]

        for name, filter_id in filters:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, f=filter_id: self.add_filter(f))
            layout.addWidget(btn)

        layout.addWidget(QLabel("✨ Fade:"))
        fade_layout = QHBoxLayout()
        fade_in_btn = QPushButton("Fade In")
        fade_in_btn.clicked.connect(lambda: self.add_operation('fade_in', {'duration': 1.0}))
        fade_out_btn = QPushButton("Fade Out")
        fade_out_btn.clicked.connect(lambda: self.add_operation('fade_out', {'duration': 1.0}))
        fade_layout.addWidget(fade_in_btn)
        fade_layout.addWidget(fade_out_btn)
        layout.addLayout(fade_layout)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_video_selection_area(self):
        """Video selection and management"""
        group = QGroupBox("📹 Selected Videos")
        layout = QVBoxLayout()

        # Buttons
        btn_layout = QHBoxLayout()

        add_video_btn = QPushButton("➕ Add Video(s)")
        add_video_btn.clicked.connect(self.add_videos)
        btn_layout.addWidget(add_video_btn)

        remove_video_btn = QPushButton("➖ Remove Selected")
        remove_video_btn.clicked.connect(self.remove_selected_video)
        btn_layout.addWidget(remove_video_btn)

        clear_videos_btn = QPushButton("🗑️ Clear All")
        clear_videos_btn.clicked.connect(self.clear_videos)
        btn_layout.addWidget(clear_videos_btn)

        layout.addLayout(btn_layout)

        # Video list
        self.videos_list = QListWidget()
        self.videos_list.setMaximumHeight(150)
        layout.addWidget(self.videos_list)

        group.setLayout(layout)
        return group

    def create_operations_queue(self):
        """Operations queue"""
        group = QGroupBox("📋 Operations Queue")
        layout = QVBoxLayout()

        self.operations_list = QListWidget()
        self.operations_list.setMaximumHeight(150)
        layout.addWidget(self.operations_list)

        btn_layout = QHBoxLayout()

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_operations)
        btn_layout.addWidget(clear_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_selected_operation)
        btn_layout.addWidget(remove_btn)

        layout.addLayout(btn_layout)

        group.setLayout(layout)
        return group

    def create_export_footer(self):
        """Export controls footer"""
        footer = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(10, 5, 10, 5)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #1ABC9C; font-size: 11px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Export controls
        export_layout = QHBoxLayout()

        export_layout.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Low", "Medium", "High", "Ultra"])
        self.quality_combo.setCurrentIndex(2)
        export_layout.addWidget(self.quality_combo)

        export_layout.addStretch()

        # Export button
        self.export_btn = QPushButton("💾 Export Video(s)")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                font-size: 13px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
        """)
        self.export_btn.clicked.connect(self.export_videos)
        export_layout.addWidget(self.export_btn)

        layout.addLayout(export_layout)

        footer.setLayout(layout)
        return footer

    # ==================== OPERATIONS ====================

    def add_operation(self, operation_name: str, params: dict):
        """Add operation to queue"""
        self.operations_queue.append({
            'name': operation_name,
            'params': params
        })

        display_text = f"{operation_name}({', '.join(f'{k}={v}' for k, v in params.items())})"
        self.operations_list.addItem(display_text)
        self.status_label.setText(f"✅ Added: {operation_name}")

    def add_trim_operation(self):
        start = self.trim_start.value()
        end = self.trim_end.value()
        if start >= end:
            QMessageBox.warning(self, "Invalid", "Start must be < End")
            return
        self.add_operation('trim', {'start_time': start, 'end_time': end})

    def add_crop_operation(self):
        preset_map = {
            "9:16 (TikTok)": "9:16",
            "16:9 (YouTube)": "16:9",
            "1:1 (Square)": "1:1",
            "4:5 (Portrait)": "4:5"
        }
        preset = preset_map[self.crop_preset.currentText()]
        self.add_operation('crop', {'preset': preset})

    def choose_text_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.text_color = color.name()

    def add_text_operation(self):
        text = self.text_input.text()
        if not text:
            QMessageBox.warning(self, "No Text", "Enter text first!")
            return

        position_map = {
            "Center-Bottom": ('center', 'bottom'),
            "Center-Top": ('center', 'top'),
            "Left-Bottom": ('left', 'bottom'),
            "Right-Bottom": ('right', 'bottom')
        }

        self.add_operation('add_text', {
            'text': text,
            'position': position_map[self.text_position.currentText()],
            'fontsize': self.text_size.value(),
            'color': self.text_color
        })

    def add_volume_operation(self):
        volume = self.volume_slider.value() / 100.0
        self.add_operation('adjust_volume', {'volume': volume})

    def add_filter(self, filter_name: str):
        self.add_operation('apply_filter', {'filter_name': filter_name})

    def clear_operations(self):
        self.operations_queue.clear()
        self.operations_list.clear()
        self.status_label.setText("🗑️ Queue cleared")

    def remove_selected_operation(self):
        current_row = self.operations_list.currentRow()
        if current_row >= 0:
            self.operations_list.takeItem(current_row)
            del self.operations_queue[current_row]

    # ==================== VIDEO MANAGEMENT ====================

    def add_videos(self):
        """Add videos to selection"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video(s)",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;All Files (*.*)"
        )

        for file_path in files:
            if file_path not in self.selected_videos:
                self.selected_videos.append(file_path)
                self.videos_list.addItem(os.path.basename(file_path))

        self.status_label.setText(f"✅ {len(files)} video(s) added")

    def remove_selected_video(self):
        current_row = self.videos_list.currentRow()
        if current_row >= 0:
            self.videos_list.takeItem(current_row)
            del self.selected_videos[current_row]

    def clear_videos(self):
        self.selected_videos.clear()
        self.videos_list.clear()

    # ==================== PRESET MANAGEMENT ====================

    def create_new_preset(self):
        """Create new preset"""
        name, ok = QInputDialog.getText(self, "New Preset", "Preset Name:")
        if ok and name:
            self.current_preset = EditingPreset(name)
            self.preset_combo.addItem(name)
            self.preset_combo.setCurrentText(name)
            self.status_label.setText(f"✅ Created preset: {name}")

    def save_current_preset(self):
        """Save current operations as preset"""
        if not self.operations_queue:
            QMessageBox.warning(self, "No Operations", "Add operations first!")
            return

        if not self.current_preset:
            name, ok = QInputDialog.getText(self, "Save Preset", "Preset Name:")
            if not ok or not name:
                return
            self.current_preset = EditingPreset(name)

        # Clear and add operations
        self.current_preset.clear_operations()
        for op in self.operations_queue:
            self.current_preset.add_operation(op['name'], op['params'])

        # Save to file
        filepath = self.preset_manager.save_preset(self.current_preset)

        # Update combo
        if self.current_preset.name not in [self.preset_combo.itemText(i)
                                            for i in range(self.preset_combo.count())]:
            self.preset_combo.addItem(self.current_preset.name)

        self.preset_combo.setCurrentText(self.current_preset.name)

        QMessageBox.information(self, "Success", f"Preset saved!\n{filepath}")

    def load_preset(self):
        """Load preset file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Preset",
            self.preset_manager.presets_dir,
            "Preset Files (*.preset.json);;All Files (*.*)"
        )

        if file_path:
            preset = self.preset_manager.load_preset_from_file(file_path)
            if preset:
                self.current_preset = preset

                # Load operations
                self.clear_operations()
                for op in preset.operations:
                    self.operations_queue.append(op)
                    self.operations_list.addItem(f"{op['operation']}(...)")

                # Update combo
                if preset.name not in [self.preset_combo.itemText(i)
                                      for i in range(self.preset_combo.count())]:
                    self.preset_combo.addItem(preset.name)
                self.preset_combo.setCurrentText(preset.name)

                self.status_label.setText(f"✅ Loaded preset: {preset.name}")

    def on_preset_selected(self, preset_name: str):
        """When preset is selected from combo"""
        if preset_name == "-- No Preset --":
            self.current_preset = None
            return

        preset = self.preset_manager.load_preset(preset_name)
        if preset:
            self.current_preset = preset

            # Load operations
            self.clear_operations()
            for op in preset.operations:
                self.operations_queue.append({
                    'name': op['operation'],
                    'params': op['params']
                })
                self.operations_list.addItem(f"{op['operation']}(...)")

            self.status_label.setText(f"✅ Loaded: {preset_name}")

    def delete_preset(self):
        """Delete selected preset"""
        if not self.current_preset:
            QMessageBox.warning(self, "No Preset", "Select a preset first!")
            return

        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f"Delete preset '{self.current_preset.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success = self.preset_manager.delete_preset(self.current_preset.name)
            if success:
                # Remove from combo
                index = self.preset_combo.findText(self.current_preset.name)
                if index >= 0:
                    self.preset_combo.removeItem(index)

                self.current_preset = None
                self.preset_combo.setCurrentIndex(0)
                QMessageBox.information(self, "Success", "Preset deleted!")

    def show_templates(self):
        """Show template presets"""
        templates = PresetTemplates.get_all_templates()

        items = [t.name for t in templates]
        item, ok = QInputDialog.getItem(
            self,
            "Templates",
            "Select a template:",
            items,
            0,
            False
        )

        if ok and item:
            # Find template
            template = next((t for t in templates if t.name == item), None)
            if template:
                # Save template
                self.preset_manager.save_preset(template)

                # Load it
                self.current_preset = template
                self.clear_operations()
                for op in template.operations:
                    self.operations_queue.append({
                        'name': op['operation'],
                        'params': op['params']
                    })
                    self.operations_list.addItem(f"{op['operation']}(...)")

                # Update combo
                if template.name not in [self.preset_combo.itemText(i)
                                        for i in range(self.preset_combo.count())]:
                    self.preset_combo.addItem(template.name)
                self.preset_combo.setCurrentText(template.name)

                self.status_label.setText(f"✅ Loaded template: {item}")

    # ==================== EXPORT ====================

    def export_videos(self):
        """Export selected videos"""
        if not self.selected_videos:
            QMessageBox.warning(self, "No Videos", "Add videos first!")
            return

        if not self.operations_queue:
            QMessageBox.warning(self, "No Operations", "Add operations or load a preset!")
            return

        quality = self.quality_combo.currentText().lower()

        if len(self.selected_videos) == 1:
            # Single video export
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Video As",
                "",
                "MP4 Video (*.mp4);;All Files (*.*)"
            )

            if output_path:
                self.export_single_video(self.selected_videos[0], output_path, quality)

        else:
            # Batch export
            output_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Output Directory"
            )

            if output_dir:
                self.export_batch_videos(output_dir, quality)

    def export_single_video(self, video_path: str, output_path: str, quality: str):
        """Export single video"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.export_btn.setEnabled(False)

        self.worker = VideoProcessWorker(self.operations_queue, video_path, output_path, quality)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_export_finished)
        self.worker.error.connect(self.on_export_error)
        self.worker.start()

    def export_batch_videos(self, output_dir: str, quality: str):
        """Export multiple videos with current operations"""
        # Create preset from current operations
        if not self.current_preset:
            self.current_preset = EditingPreset("Temp Batch Preset")
            for op in self.operations_queue:
                self.current_preset.add_operation(op['name'], op['params'])

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.selected_videos))
        self.export_btn.setEnabled(False)

        self.batch_worker = BatchProcessWorker(
            self.current_preset,
            self.selected_videos,
            output_dir,
            quality
        )
        self.batch_worker.progress.connect(self.on_batch_progress)
        self.batch_worker.finished.connect(self.on_batch_finished)
        self.batch_worker.error.connect(self.on_export_error)
        self.batch_worker.start()

    def on_progress(self, message: str):
        self.status_label.setText(f"⏳ {message}")

    def on_batch_progress(self, current: int, total: int, filename: str, message: str):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"⏳ [{current}/{total}] {os.path.basename(filename)}: {message}")

    def on_export_finished(self, message: str):
        self.progress_bar.setVisible(False)
        self.export_btn.setEnabled(True)
        self.status_label.setText("✅ Export complete!")
        QMessageBox.information(self, "Success", message)

    def on_batch_finished(self, results: list):
        self.progress_bar.setVisible(False)
        self.export_btn.setEnabled(True)

        success_count = sum(1 for r in results if r['status'] == 'success')
        failed_count = len(results) - success_count

        message = f"Batch processing complete!\n\n"
        message += f"✅ Success: {success_count}\n"
        message += f"❌ Failed: {failed_count}"

        self.status_label.setText(f"✅ Batch complete: {success_count}/{len(results)}")
        QMessageBox.information(self, "Batch Complete", message)

    def on_export_error(self, error: str):
        self.progress_bar.setVisible(False)
        self.export_btn.setEnabled(True)
        self.status_label.setText("❌ Export failed")
        QMessageBox.critical(self, "Error", error)
