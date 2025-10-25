"""
modules/video_editor/gui.py
Complete Video Editor GUI with PyQt5
Full-featured interface with preview, timeline, and all editing controls
"""

import os
import sys
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QSlider, QTextEdit, QLineEdit, QTabWidget, QScrollArea,
    QProgressBar, QMessageBox, QInputDialog, QListWidget, QSplitter,
    QCheckBox, QColorDialog, QFontDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

from modules.logging.logger import get_logger
from modules.video_editor.core import VideoEditor, BatchVideoEditor, merge_videos
from modules.video_editor.presets import PlatformPresets, PresetApplicator
from modules.video_editor.utils import (
    get_video_info, format_duration, format_filesize,
    check_dependencies, get_unique_filename
)

logger = get_logger(__name__)


# ==================== WORKER THREAD ====================

class VideoProcessWorker(QThread):
    """Worker thread for video processing"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, editor: VideoEditor, operations: list, output_path: str):
        super().__init__()
        self.editor = editor
        self.operations = operations
        self.output_path = output_path

    def run(self):
        """Execute video processing operations"""
        try:
            self.progress.emit("Starting video processing...")

            # Apply all operations
            for i, operation in enumerate(self.operations):
                op_name = operation['name']
                params = operation.get('params', {})

                self.progress.emit(f"Applying {op_name}... ({i+1}/{len(self.operations)})")

                # Execute operation
                if hasattr(self.editor, op_name):
                    method = getattr(self.editor, op_name)
                    method(**params)
                else:
                    logger.warning(f"Unknown operation: {op_name}")

            # Export video
            self.progress.emit("Exporting video...")
            self.editor.export(self.output_path, quality='high')

            self.finished.emit(f"Video exported successfully to:\n{self.output_path}")

        except Exception as e:
            logger.error(f"Video processing error: {e}")
            self.error.emit(f"Error: {str(e)}")


# ==================== MAIN GUI ====================

class VideoEditorPage(QWidget):
    """Complete Video Editor GUI"""

    def __init__(self, back_callback=None):
        super().__init__()
        self.back_callback = back_callback
        self.editor = None
        self.current_video_path = None
        self.operations_queue = []  # Queue of operations to apply

        # Check dependencies
        deps = check_dependencies()
        if not all([deps.get('ffmpeg'), deps.get('moviepy')]):
            self.show_dependency_error()
            return

        self.init_ui()

    def show_dependency_error(self):
        """Show dependency error message"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        error_label = QLabel("❌ Missing Dependencies")
        error_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #E74C3C;")
        layout.addWidget(error_label)

        msg = QLabel("Please install required dependencies:\n\n"
                    "pip install moviepy pillow numpy scipy\n\n"
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
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Set dark theme
        self.setStyleSheet("""
            QWidget {
                background-color: #23272A;
                color: #F5F6F5;
                font-size: 13px;
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
                padding: 8px 15px;
                border-radius: 5px;
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
                padding: 5px;
                color: #F5F6F5;
            }
            QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {
                border: 1px solid #1ABC9C;
            }
            QComboBox::drop-down {
                border: none;
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
            QTabWidget::pane {
                border: 1px solid #40444B;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #2C2F33;
                color: #F5F6F5;
                padding: 8px 15px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1ABC9C;
            }
            QProgressBar {
                border: 1px solid #40444B;
                border-radius: 5px;
                text-align: center;
                background-color: #2C2F33;
            }
            QProgressBar::chunk {
                background-color: #1ABC9C;
                border-radius: 4px;
            }
        """)

        # ==================== HEADER ====================
        header = self.create_header()
        main_layout.addWidget(header)

        # ==================== MAIN CONTENT ====================
        # Use splitter for resizable sections
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Controls
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setMinimumWidth(350)
        controls_scroll.setMaximumWidth(450)

        controls_widget = QWidget()
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(10)

        # File controls
        controls_layout.addWidget(self.create_file_controls())

        # Video info
        self.video_info_widget = self.create_video_info_widget()
        controls_layout.addWidget(self.video_info_widget)

        # Tabs for different operations
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_basic_edits_tab(), "✂️ Basic")
        self.tabs.addTab(self.create_text_tab(), "📝 Text")
        self.tabs.addTab(self.create_audio_tab(), "🎵 Audio")
        self.tabs.addTab(self.create_filters_tab(), "🎨 Filters")
        self.tabs.addTab(self.create_advanced_tab(), "⚙️ Advanced")
        controls_layout.addWidget(self.tabs)

        # Operations queue
        controls_layout.addWidget(self.create_operations_queue())

        controls_layout.addStretch()
        controls_widget.setLayout(controls_layout)
        controls_scroll.setWidget(controls_widget)

        # Right panel - Preview
        preview_widget = self.create_preview_widget()

        splitter.addWidget(controls_scroll)
        splitter.addWidget(preview_widget)
        splitter.setStretchFactor(0, 0)  # Controls don't stretch
        splitter.setStretchFactor(1, 1)  # Preview stretches

        main_layout.addWidget(splitter, 1)

        # ==================== FOOTER ====================
        footer = self.create_footer()
        main_layout.addWidget(footer)

        self.setLayout(main_layout)

    def create_header(self):
        """Create header section"""
        header = QWidget()
        layout = QHBoxLayout()

        title = QLabel("🎬 Video Editor")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1ABC9C;")
        layout.addWidget(title)

        layout.addStretch()

        # Back button
        back_btn = QPushButton("⬅ Back")
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        layout.addWidget(back_btn)

        header.setLayout(layout)
        return header

    def create_file_controls(self):
        """Create file loading/saving controls"""
        group = QGroupBox("📁 File")
        layout = QVBoxLayout()

        # Load video button
        load_btn = QPushButton("Open Video")
        load_btn.clicked.connect(self.load_video)
        layout.addWidget(load_btn)

        # Current file label
        self.current_file_label = QLabel("No video loaded")
        self.current_file_label.setStyleSheet("color: #72767D; font-size: 11px;")
        self.current_file_label.setWordWrap(True)
        layout.addWidget(self.current_file_label)

        group.setLayout(layout)
        return group

    def create_video_info_widget(self):
        """Create video info display"""
        group = QGroupBox("ℹ️ Video Info")
        layout = QVBoxLayout()

        self.info_label = QLabel("No video loaded")
        self.info_label.setStyleSheet("font-size: 11px; color: #B9BBBE;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        group.setLayout(layout)
        group.setVisible(False)
        return group

    def create_basic_edits_tab(self):
        """Create basic editing controls tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Trim/Cut
        trim_group = QGroupBox("✂️ Trim/Cut")
        trim_layout = QVBoxLayout()

        trim_layout.addWidget(QLabel("Start Time (seconds):"))
        self.trim_start = QDoubleSpinBox()
        self.trim_start.setMaximum(9999)
        self.trim_start.setValue(0)
        trim_layout.addWidget(self.trim_start)

        trim_layout.addWidget(QLabel("End Time (seconds):"))
        self.trim_end = QDoubleSpinBox()
        self.trim_end.setMaximum(9999)
        self.trim_end.setValue(10)
        trim_layout.addWidget(self.trim_end)

        trim_btn = QPushButton("Add Trim Operation")
        trim_btn.clicked.connect(self.add_trim_operation)
        trim_layout.addWidget(trim_btn)

        trim_group.setLayout(trim_layout)
        layout.addWidget(trim_group)

        # Crop
        crop_group = QGroupBox("📐 Crop / Aspect Ratio")
        crop_layout = QVBoxLayout()

        crop_layout.addWidget(QLabel("Preset:"))
        self.crop_preset = QComboBox()
        self.crop_preset.addItems([
            "Custom",
            "9:16 (TikTok, Reels, Shorts)",
            "16:9 (YouTube, Facebook)",
            "1:1 (Square)",
            "4:5 (Instagram Portrait)",
            "4:3 (Traditional)",
            "21:9 (Cinematic)"
        ])
        crop_layout.addWidget(self.crop_preset)

        crop_btn = QPushButton("Add Crop Operation")
        crop_btn.clicked.connect(self.add_crop_operation)
        crop_layout.addWidget(crop_btn)

        crop_group.setLayout(crop_layout)
        layout.addWidget(crop_group)

        # Rotate/Flip
        transform_group = QGroupBox("🔄 Rotate / Flip")
        transform_layout = QVBoxLayout()

        rotate_layout = QHBoxLayout()
        rotate_90_btn = QPushButton("↻ 90°")
        rotate_90_btn.clicked.connect(lambda: self.add_operation('rotate', {'angle': 90}))
        rotate_180_btn = QPushButton("↻ 180°")
        rotate_180_btn.clicked.connect(lambda: self.add_operation('rotate', {'angle': 180}))
        rotate_270_btn = QPushButton("↻ 270°")
        rotate_270_btn.clicked.connect(lambda: self.add_operation('rotate', {'angle': 270}))
        rotate_layout.addWidget(rotate_90_btn)
        rotate_layout.addWidget(rotate_180_btn)
        rotate_layout.addWidget(rotate_270_btn)
        transform_layout.addLayout(rotate_layout)

        flip_layout = QHBoxLayout()
        flip_h_btn = QPushButton("↔️ Flip Horizontal")
        flip_h_btn.clicked.connect(lambda: self.add_operation('flip_horizontal', {}))
        flip_v_btn = QPushButton("↕️ Flip Vertical")
        flip_v_btn.clicked.connect(lambda: self.add_operation('flip_vertical', {}))
        flip_layout.addWidget(flip_h_btn)
        flip_layout.addWidget(flip_v_btn)
        transform_layout.addLayout(flip_layout)

        transform_group.setLayout(transform_layout)
        layout.addWidget(transform_group)

        # Resize
        resize_group = QGroupBox("📏 Resize")
        resize_layout = QVBoxLayout()

        resize_layout.addWidget(QLabel("Width:"))
        self.resize_width = QSpinBox()
        self.resize_width.setMaximum(7680)
        self.resize_width.setValue(1920)
        resize_layout.addWidget(self.resize_width)

        resize_layout.addWidget(QLabel("Height:"))
        self.resize_height = QSpinBox()
        self.resize_height.setMaximum(4320)
        self.resize_height.setValue(1080)
        resize_layout.addWidget(self.resize_height)

        resize_btn = QPushButton("Add Resize Operation")
        resize_btn.clicked.connect(self.add_resize_operation)
        resize_layout.addWidget(resize_btn)

        resize_group.setLayout(resize_layout)
        layout.addWidget(resize_group)

        # Speed
        speed_group = QGroupBox("⏩ Speed")
        speed_layout = QVBoxLayout()

        speed_layout.addWidget(QLabel("Speed Factor:"))
        self.speed_factor = QDoubleSpinBox()
        self.speed_factor.setMinimum(0.1)
        self.speed_factor.setMaximum(10.0)
        self.speed_factor.setValue(1.0)
        self.speed_factor.setSingleStep(0.1)
        speed_layout.addWidget(self.speed_factor)

        speed_info = QLabel("1.0 = normal, 0.5 = half speed, 2.0 = double speed")
        speed_info.setStyleSheet("font-size: 10px; color: #72767D;")
        speed_layout.addWidget(speed_info)

        speed_btn = QPushButton("Add Speed Change")
        speed_btn.clicked.connect(self.add_speed_operation)
        speed_layout.addWidget(speed_btn)

        speed_group.setLayout(speed_layout)
        layout.addWidget(speed_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_text_tab(self):
        """Create text overlay controls tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        text_group = QGroupBox("📝 Text Overlay")
        text_layout = QVBoxLayout()

        text_layout.addWidget(QLabel("Text:"))
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter your text here...")
        text_layout.addWidget(self.text_input)

        text_layout.addWidget(QLabel("Font Size:"))
        self.text_size = QSpinBox()
        self.text_size.setMinimum(10)
        self.text_size.setMaximum(200)
        self.text_size.setValue(50)
        text_layout.addWidget(self.text_size)

        text_layout.addWidget(QLabel("Position:"))
        self.text_position = QComboBox()
        self.text_position.addItems([
            "Center - Top",
            "Center - Center",
            "Center - Bottom",
            "Left - Top",
            "Left - Bottom",
            "Right - Top",
            "Right - Bottom"
        ])
        self.text_position.setCurrentIndex(2)  # Center - Bottom
        text_layout.addWidget(self.text_position)

        text_layout.addWidget(QLabel("Color:"))
        color_layout = QHBoxLayout()
        self.text_color_btn = QPushButton("Choose Color")
        self.text_color_btn.clicked.connect(self.choose_text_color)
        self.text_color = 'white'
        color_layout.addWidget(self.text_color_btn)
        self.text_color_display = QLabel("⬤")
        self.text_color_display.setStyleSheet("color: white; font-size: 20px;")
        color_layout.addWidget(self.text_color_display)
        text_layout.addLayout(color_layout)

        text_layout.addWidget(QLabel("Duration (seconds, 0 = full video):"))
        self.text_duration = QDoubleSpinBox()
        self.text_duration.setMaximum(9999)
        self.text_duration.setValue(0)
        text_layout.addWidget(self.text_duration)

        add_text_btn = QPushButton("Add Text Overlay")
        add_text_btn.clicked.connect(self.add_text_operation)
        text_layout.addWidget(add_text_btn)

        text_group.setLayout(text_layout)
        layout.addWidget(text_group)

        # Watermark
        watermark_group = QGroupBox("🖼️ Watermark / Logo")
        watermark_layout = QVBoxLayout()

        self.watermark_path = None
        watermark_btn = QPushButton("Select Watermark Image")
        watermark_btn.clicked.connect(self.select_watermark)
        watermark_layout.addWidget(watermark_btn)

        self.watermark_label = QLabel("No watermark selected")
        self.watermark_label.setStyleSheet("font-size: 10px; color: #72767D;")
        watermark_layout.addWidget(self.watermark_label)

        watermark_layout.addWidget(QLabel("Position:"))
        self.watermark_position = QComboBox()
        self.watermark_position.addItems([
            "Right - Bottom",
            "Right - Top",
            "Left - Bottom",
            "Left - Top",
            "Center - Center"
        ])
        watermark_layout.addWidget(self.watermark_position)

        watermark_layout.addWidget(QLabel("Opacity:"))
        self.watermark_opacity = QSlider(Qt.Horizontal)
        self.watermark_opacity.setMinimum(10)
        self.watermark_opacity.setMaximum(100)
        self.watermark_opacity.setValue(100)
        watermark_layout.addWidget(self.watermark_opacity)

        add_watermark_btn = QPushButton("Add Watermark")
        add_watermark_btn.clicked.connect(self.add_watermark_operation)
        watermark_layout.addWidget(add_watermark_btn)

        watermark_group.setLayout(watermark_layout)
        layout.addWidget(watermark_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_audio_tab(self):
        """Create audio controls tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Volume
        volume_group = QGroupBox("🔊 Volume")
        volume_layout = QVBoxLayout()

        volume_layout.addWidget(QLabel("Volume Level:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(200)
        self.volume_slider.setValue(100)
        volume_layout.addWidget(self.volume_slider)

        self.volume_label = QLabel("100%")
        self.volume_label.setStyleSheet("font-size: 11px; color: #B9BBBE;")
        self.volume_slider.valueChanged.connect(lambda v: self.volume_label.setText(f"{v}%"))
        volume_layout.addWidget(self.volume_label)

        volume_btn = QPushButton("Adjust Volume")
        volume_btn.clicked.connect(self.add_volume_operation)
        volume_layout.addWidget(volume_btn)

        remove_audio_btn = QPushButton("Remove Audio")
        remove_audio_btn.clicked.connect(lambda: self.add_operation('remove_audio', {}))
        volume_layout.addWidget(remove_audio_btn)

        volume_group.setLayout(volume_layout)
        layout.addWidget(volume_group)

        # Replace audio
        replace_group = QGroupBox("🎵 Replace Audio")
        replace_layout = QVBoxLayout()

        self.audio_path = None
        audio_btn = QPushButton("Select Audio File")
        audio_btn.clicked.connect(self.select_audio)
        replace_layout.addWidget(audio_btn)

        self.audio_label = QLabel("No audio selected")
        self.audio_label.setStyleSheet("font-size: 10px; color: #72767D;")
        replace_layout.addWidget(self.audio_label)

        replace_audio_btn = QPushButton("Replace Audio")
        replace_audio_btn.clicked.connect(self.add_replace_audio_operation)
        replace_layout.addWidget(replace_audio_btn)

        replace_group.setLayout(replace_layout)
        layout.addWidget(replace_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_filters_tab(self):
        """Create filters controls tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Basic filters
        basic_group = QGroupBox("🎨 Basic Filters")
        basic_layout = QVBoxLayout()

        # Brightness
        basic_layout.addWidget(QLabel("Brightness:"))
        self.brightness = QSlider(Qt.Horizontal)
        self.brightness.setMinimum(50)
        self.brightness.setMaximum(200)
        self.brightness.setValue(100)
        basic_layout.addWidget(self.brightness)

        brightness_btn = QPushButton("Apply Brightness")
        brightness_btn.clicked.connect(lambda: self.add_filter_operation('brightness', self.brightness.value() / 100.0))
        basic_layout.addWidget(brightness_btn)

        # Contrast
        basic_layout.addWidget(QLabel("Contrast:"))
        self.contrast = QSlider(Qt.Horizontal)
        self.contrast.setMinimum(50)
        self.contrast.setMaximum(200)
        self.contrast.setValue(100)
        basic_layout.addWidget(self.contrast)

        contrast_btn = QPushButton("Apply Contrast")
        contrast_btn.clicked.connect(lambda: self.add_filter_operation('contrast', self.contrast.value() / 100.0))
        basic_layout.addWidget(contrast_btn)

        # Saturation
        basic_layout.addWidget(QLabel("Saturation:"))
        self.saturation = QSlider(Qt.Horizontal)
        self.saturation.setMinimum(0)
        self.saturation.setMaximum(200)
        self.saturation.setValue(100)
        basic_layout.addWidget(self.saturation)

        saturation_btn = QPushButton("Apply Saturation")
        saturation_btn.clicked.connect(lambda: self.add_filter_operation('saturation', self.saturation.value() / 100.0))
        basic_layout.addWidget(saturation_btn)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # Quick filters
        quick_group = QGroupBox("⚡ Quick Filters")
        quick_layout = QVBoxLayout()

        filters_row1 = QHBoxLayout()
        grayscale_btn = QPushButton("Grayscale")
        grayscale_btn.clicked.connect(lambda: self.add_filter_operation('grayscale', None))
        sepia_btn = QPushButton("Sepia")
        sepia_btn.clicked.connect(lambda: self.add_filter_operation('sepia', None))
        filters_row1.addWidget(grayscale_btn)
        filters_row1.addWidget(sepia_btn)
        quick_layout.addLayout(filters_row1)

        filters_row2 = QHBoxLayout()
        invert_btn = QPushButton("Invert")
        invert_btn.clicked.connect(lambda: self.add_filter_operation('invert', None))
        vintage_btn = QPushButton("Vintage")
        vintage_btn.clicked.connect(lambda: self.add_filter_operation('vintage', None))
        filters_row2.addWidget(invert_btn)
        filters_row2.addWidget(vintage_btn)
        quick_layout.addLayout(filters_row2)

        filters_row3 = QHBoxLayout()
        cinematic_btn = QPushButton("Cinematic")
        cinematic_btn.clicked.connect(lambda: self.add_filter_operation('cinematic', None))
        warm_btn = QPushButton("Warm")
        warm_btn.clicked.connect(lambda: self.add_filter_operation('warm', 0.3))
        filters_row3.addWidget(cinematic_btn)
        filters_row3.addWidget(warm_btn)
        quick_layout.addLayout(filters_row3)

        quick_group.setLayout(quick_layout)
        layout.addWidget(quick_group)

        # Fade effects
        fade_group = QGroupBox("✨ Fade Effects")
        fade_layout = QVBoxLayout()

        fade_layout.addWidget(QLabel("Fade Duration (seconds):"))
        self.fade_duration = QDoubleSpinBox()
        self.fade_duration.setMinimum(0.1)
        self.fade_duration.setMaximum(10.0)
        self.fade_duration.setValue(1.0)
        fade_layout.addWidget(self.fade_duration)

        fade_btns = QHBoxLayout()
        fade_in_btn = QPushButton("Fade In")
        fade_in_btn.clicked.connect(lambda: self.add_operation('fade_in', {'duration': self.fade_duration.value()}))
        fade_out_btn = QPushButton("Fade Out")
        fade_out_btn.clicked.connect(lambda: self.add_operation('fade_out', {'duration': self.fade_duration.value()}))
        fade_btns.addWidget(fade_in_btn)
        fade_btns.addWidget(fade_out_btn)
        fade_layout.addLayout(fade_btns)

        fade_group.setLayout(fade_layout)
        layout.addWidget(fade_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_advanced_tab(self):
        """Create advanced controls tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Platform presets
        preset_group = QGroupBox("📱 Platform Presets")
        preset_layout = QVBoxLayout()

        preset_layout.addWidget(QLabel("Platform:"))
        self.platform_combo = QComboBox()
        self.platform_combo.addItems([
            "TikTok Vertical",
            "Instagram Reels",
            "Instagram Story",
            "Instagram Post (Square)",
            "YouTube Shorts",
            "YouTube 1080p",
            "YouTube 4K",
            "Facebook Feed",
            "Twitter Landscape"
        ])
        preset_layout.addWidget(self.platform_combo)

        preset_btn = QPushButton("Apply Platform Preset")
        preset_btn.clicked.connect(self.apply_platform_preset)
        preset_layout.addWidget(preset_btn)

        preset_info = QLabel("Auto-crop and resize for selected platform")
        preset_info.setStyleSheet("font-size: 10px; color: #72767D;")
        preset_layout.addWidget(preset_info)

        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_operations_queue(self):
        """Create operations queue widget"""
        group = QGroupBox("📋 Operations Queue")
        layout = QVBoxLayout()

        self.operations_list = QListWidget()
        self.operations_list.setMaximumHeight(150)
        layout.addWidget(self.operations_list)

        btn_layout = QHBoxLayout()

        clear_btn = QPushButton("Clear Queue")
        clear_btn.clicked.connect(self.clear_operations)
        btn_layout.addWidget(clear_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_selected_operation)
        btn_layout.addWidget(remove_btn)

        layout.addLayout(btn_layout)

        group.setLayout(layout)
        return group

    def create_preview_widget(self):
        """Create video preview widget"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Preview label
        preview_label = QLabel("📺 Preview (Coming Soon)")
        preview_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1ABC9C;")
        preview_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(preview_label)

        # Video player (simplified placeholder)
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(640, 360)
        self.video_widget.setStyleSheet("background-color: #2C2F33; border: 2px solid #40444B; border-radius: 5px;")
        layout.addWidget(self.video_widget, 1)

        # Player controls
        player_controls = QHBoxLayout()

        self.play_btn = QPushButton("▶️ Play")
        self.play_btn.setEnabled(False)
        player_controls.addWidget(self.play_btn)

        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.setEnabled(False)
        player_controls.addWidget(self.pause_btn)

        player_controls.addStretch()

        layout.addLayout(player_controls)

        # Note about preview
        note = QLabel("Note: Live preview requires additional setup.\nUse 'Export' to see final result.")
        note.setStyleSheet("font-size: 11px; color: #72767D; font-style: italic;")
        note.setAlignment(Qt.AlignCenter)
        layout.addWidget(note)

        widget.setLayout(layout)
        return widget

    def create_footer(self):
        """Create footer with export controls"""
        footer = QWidget()
        layout = QVBoxLayout()

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #1ABC9C; font-size: 12px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Export controls
        export_layout = QHBoxLayout()

        # Quality selector
        export_layout.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Low", "Medium", "High", "Ultra"])
        self.quality_combo.setCurrentIndex(2)  # High
        export_layout.addWidget(self.quality_combo)

        export_layout.addStretch()

        # Export button
        self.export_btn = QPushButton("💾 Export Video")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_video)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                font-size: 14px;
                padding: 10px 30px;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
            QPushButton:disabled {
                background-color: #40444B;
            }
        """)
        export_layout.addWidget(self.export_btn)

        layout.addLayout(export_layout)

        footer.setLayout(layout)
        return footer

    # ==================== SLOTS / ACTIONS ====================

    def load_video(self):
        """Load video file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm *.flv *.wmv);;All Files (*.*)"
        )

        if file_path:
            try:
                # Get video info
                info = get_video_info(file_path)

                # Create editor
                self.editor = VideoEditor(file_path)
                self.current_video_path = file_path

                # Update UI
                self.current_file_label.setText(f"📄 {os.path.basename(file_path)}")

                info_text = f"Duration: {format_duration(info.get('duration', 0))}\n"
                info_text += f"Resolution: {info.get('width', 0)}x{info.get('height', 0)}\n"
                info_text += f"FPS: {info.get('fps', 0)}\n"
                info_text += f"Size: {format_filesize(info.get('filesize', 0))}"

                self.info_label.setText(info_text)
                self.video_info_widget.setVisible(True)

                # Update trim end time to video duration
                self.trim_end.setValue(info.get('duration', 10))

                # Enable export
                self.export_btn.setEnabled(True)

                self.status_label.setText("✅ Video loaded successfully!")

                logger.info(f"Video loaded: {file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load video:\n{str(e)}")
                logger.error(f"Failed to load video: {e}")

    def add_operation(self, operation_name: str, params: dict):
        """Add operation to queue"""
        self.operations_queue.append({
            'name': operation_name,
            'params': params
        })

        # Update list
        display_text = f"{operation_name}({', '.join(f'{k}={v}' for k, v in params.items())})"
        self.operations_list.addItem(display_text)

        self.status_label.setText(f"✅ Added: {operation_name}")

    def add_trim_operation(self):
        """Add trim operation"""
        start = self.trim_start.value()
        end = self.trim_end.value()

        if start >= end:
            QMessageBox.warning(self, "Invalid Range", "Start time must be less than end time!")
            return

        self.add_operation('trim', {'start_time': start, 'end_time': end})

    def add_crop_operation(self):
        """Add crop operation"""
        preset_text = self.crop_preset.currentText()

        preset_map = {
            "9:16 (TikTok, Reels, Shorts)": "9:16",
            "16:9 (YouTube, Facebook)": "16:9",
            "1:1 (Square)": "1:1",
            "4:5 (Instagram Portrait)": "4:5",
            "4:3 (Traditional)": "4:3",
            "21:9 (Cinematic)": "21:9"
        }

        if preset_text in preset_map:
            preset = preset_map[preset_text]
            self.add_operation('crop', {'preset': preset})
        else:
            QMessageBox.information(self, "Custom Crop", "Custom crop coordinates not yet implemented in GUI.\nUse presets for now.")

    def add_resize_operation(self):
        """Add resize operation"""
        width = self.resize_width.value()
        height = self.resize_height.value()
        self.add_operation('resize_video', {'width': width, 'height': height})

    def add_speed_operation(self):
        """Add speed change operation"""
        factor = self.speed_factor.value()
        self.add_operation('change_speed', {'factor': factor})

    def choose_text_color(self):
        """Choose text color"""
        color = QColorDialog.getColor()
        if color.isValid():
            self.text_color = color.name()
            self.text_color_display.setStyleSheet(f"color: {color.name()}; font-size: 20px;")

    def add_text_operation(self):
        """Add text overlay operation"""
        text = self.text_input.text()
        if not text:
            QMessageBox.warning(self, "No Text", "Please enter text to add!")
            return

        position_map = {
            "Center - Top": ('center', 'top'),
            "Center - Center": ('center', 'center'),
            "Center - Bottom": ('center', 'bottom'),
            "Left - Top": ('left', 'top'),
            "Left - Bottom": ('left', 'bottom'),
            "Right - Top": ('right', 'top'),
            "Right - Bottom": ('right', 'bottom')
        }

        position = position_map[self.text_position.currentText()]
        duration = self.text_duration.value() if self.text_duration.value() > 0 else None

        self.add_operation('add_text', {
            'text': text,
            'position': position,
            'fontsize': self.text_size.value(),
            'color': self.text_color,
            'duration': duration
        })

    def select_watermark(self):
        """Select watermark image"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Watermark Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.gif);;All Files (*.*)"
        )

        if file_path:
            self.watermark_path = file_path
            self.watermark_label.setText(f"📄 {os.path.basename(file_path)}")

    def add_watermark_operation(self):
        """Add watermark operation"""
        if not self.watermark_path:
            QMessageBox.warning(self, "No Watermark", "Please select a watermark image first!")
            return

        position_map = {
            "Right - Bottom": ('right', 'bottom'),
            "Right - Top": ('right', 'top'),
            "Left - Bottom": ('left', 'bottom'),
            "Left - Top": ('left', 'top'),
            "Center - Center": ('center', 'center')
        }

        position = position_map[self.watermark_position.currentText()]
        opacity = self.watermark_opacity.value() / 100.0

        self.add_operation('add_watermark', {
            'image_path': self.watermark_path,
            'position': position,
            'opacity': opacity
        })

    def select_audio(self):
        """Select audio file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            "",
            "Audio Files (*.mp3 *.wav *.aac *.ogg *.m4a);;All Files (*.*)"
        )

        if file_path:
            self.audio_path = file_path
            self.audio_label.setText(f"📄 {os.path.basename(file_path)}")

    def add_volume_operation(self):
        """Add volume adjustment operation"""
        volume = self.volume_slider.value() / 100.0
        self.add_operation('adjust_volume', {'volume': volume})

    def add_replace_audio_operation(self):
        """Add replace audio operation"""
        if not self.audio_path:
            QMessageBox.warning(self, "No Audio", "Please select an audio file first!")
            return

        self.add_operation('replace_audio', {'audio_path': self.audio_path})

    def add_filter_operation(self, filter_name: str, intensity):
        """Add filter operation"""
        if intensity is not None:
            self.add_operation('apply_filter', {'filter_name': filter_name, 'intensity': intensity})
        else:
            self.add_operation('apply_filter', {'filter_name': filter_name})

    def apply_platform_preset(self):
        """Apply platform preset"""
        preset_text = self.platform_combo.currentText()

        preset_map = {
            "TikTok Vertical": ('tiktok', 'vertical'),
            "Instagram Reels": ('instagram', 'reels'),
            "Instagram Story": ('instagram', 'story'),
            "Instagram Post (Square)": ('instagram', 'square'),
            "YouTube Shorts": ('youtube', 'shorts'),
            "YouTube 1080p": ('youtube', '1080p'),
            "YouTube 4K": ('youtube', '4k'),
            "Facebook Feed": ('facebook', 'feed'),
            "Twitter Landscape": ('twitter', 'landscape')
        }

        if preset_text in preset_map:
            platform, format_type = preset_map[preset_text]

            # Get preset details
            from modules.video_editor.presets import PlatformPresets

            preset_name = f"{platform.upper()}_{format_type.upper()}"
            try:
                preset = getattr(PlatformPresets, preset_name)

                # Add crop to aspect ratio
                self.add_operation('crop', {'preset': preset.aspect_ratio})

                # Add resize
                self.add_operation('resize_video', {'width': preset.width, 'height': preset.height})

                self.status_label.setText(f"✅ Applied preset: {preset_text}")

            except AttributeError:
                QMessageBox.warning(self, "Preset Error", f"Preset not found: {preset_name}")

    def clear_operations(self):
        """Clear all operations"""
        self.operations_queue.clear()
        self.operations_list.clear()
        self.status_label.setText("🗑️ Queue cleared")

    def remove_selected_operation(self):
        """Remove selected operation from queue"""
        current_row = self.operations_list.currentRow()
        if current_row >= 0:
            self.operations_list.takeItem(current_row)
            del self.operations_queue[current_row]
            self.status_label.setText("🗑️ Operation removed")

    def export_video(self):
        """Export edited video"""
        if not self.editor:
            QMessageBox.warning(self, "No Video", "Please load a video first!")
            return

        if not self.operations_queue:
            QMessageBox.warning(self, "No Operations", "Please add at least one editing operation!")
            return

        # Get output path
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Video As",
            "",
            "MP4 Video (*.mp4);;AVI Video (*.avi);;MOV Video (*.mov);;All Files (*.*)"
        )

        if not output_path:
            return

        # Ensure unique filename
        output_path = get_unique_filename(output_path)

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.export_btn.setEnabled(False)
        self.status_label.setText("⏳ Processing video...")

        # Start worker thread
        self.worker = VideoProcessWorker(self.editor, self.operations_queue, output_path)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_export_finished)
        self.worker.error.connect(self.on_export_error)
        self.worker.start()

    def on_progress(self, message: str):
        """Handle progress update"""
        self.status_label.setText(f"⏳ {message}")

    def on_export_finished(self, message: str):
        """Handle export completion"""
        self.progress_bar.setVisible(False)
        self.export_btn.setEnabled(True)
        self.status_label.setText("✅ Export complete!")

        QMessageBox.information(self, "Success", message)

        # Clear queue after successful export
        self.clear_operations()

    def on_export_error(self, error: str):
        """Handle export error"""
        self.progress_bar.setVisible(False)
        self.export_btn.setEnabled(True)
        self.status_label.setText("❌ Export failed")

        QMessageBox.critical(self, "Export Error", error)
