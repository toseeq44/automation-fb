"""
modules/video_editor/capcut_editor.py
Professional CapCut-Style Video Editor - Complete GUI Design
Step 1: Complete UI Layout
Step 2-N: Add functionality incrementally
"""

import os
import sys
from typing import Optional, List, Dict
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QSlider, QLineEdit, QProgressBar, QMessageBox, QSplitter,
    QCheckBox, QTextEdit, QFrame, QGridLayout, QScrollArea,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QTabWidget, QMenuBar, QMenu, QAction, QToolBar, QStatusBar,
    QTreeWidget, QTreeWidgetItem, QShortcut
)
from PyQt5.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal, QUrl, QMimeData
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPalette, QKeySequence, QDragEnterEvent, QDropEvent, QDrag
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

from modules.logging.logger import get_logger
from modules.video_editor.preset_manager import PresetManager, EditingPreset
from modules.video_editor.timeline_widget import TimelineWidget
from modules.video_editor.custom_video_player import CustomVideoPlayer

logger = get_logger(__name__)


# Supported file formats
VIDEO_FORMATS = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v']
AUDIO_FORMATS = ['.mp3', '.wav', '.aac', '.m4a', '.ogg', '.wma', '.flac']
IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']


@dataclass
class MediaItem:
    """Represents an imported media file"""
    file_path: str
    file_name: str
    file_type: str  # 'video', 'audio', 'image'
    file_size: int
    duration: float = 0.0  # For video/audio
    width: int = 0  # For video/image
    height: int = 0  # For video/image
    thumbnail: Optional[QPixmap] = None
    fps: float = 0.0  # For video
    imported_at: datetime = None

    def __post_init__(self):
        if self.imported_at is None:
            self.imported_at = datetime.now()


class DraggableMediaList(QListWidget):
    """Custom list widget with enhanced drag support"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragOnly)

    def startDrag(self, supportedActions):
        """Custom drag start to include media item data"""
        item = self.currentItem()
        if not item:
            return

        media_item = item.data(Qt.UserRole)
        if not media_item:
            return

        # Create drag object
        drag = QDrag(self)
        mime_data = QMimeData()

        # Set file path as text
        mime_data.setText(media_item.file_path)

        # Also set as URL for compatibility
        mime_data.setUrls([QUrl.fromLocalFile(media_item.file_path)])

        drag.setMimeData(mime_data)

        # Execute drag
        drag.exec_(Qt.CopyAction)


class CapCutEditor(QWidget):
    """
    Professional CapCut-Style Video Editor
    Complete GUI Design - Functionality to be added incrementally
    """

    def __init__(self, back_callback=None):
        super().__init__()
        self.back_callback = back_callback

        # State
        self.preset_manager = PresetManager()
        self.current_project = None
        self.media_items: List[MediaItem] = []
        self.timeline_clips = []
        self.current_video_path = None
        self.media_item_map = {}  # Map file paths to MediaItem objects

        # Enable drag and drop
        self.setAcceptDrops(True)

        self.init_ui()
        self.setup_keyboard_shortcuts()

        logger.info("CapCutEditor initialized successfully")

    def init_ui(self):
        """Initialize complete UI layout"""
        # Main layout - vertical
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Apply professional dark theme
        self.apply_dark_theme()

        # 1. TOP NAVIGATION BAR
        main_layout.addWidget(self.create_top_navigation())

        # 2. MAIN CONTENT AREA (3-panel layout)
        content_splitter = QSplitter(Qt.Horizontal)

        # Left Panel - Media Library
        left_panel = self.create_left_panel()
        left_panel.setMinimumWidth(250)
        left_panel.setMaximumWidth(400)

        # Center Panel - Preview + Timeline
        center_panel = self.create_center_panel()

        # Right Panel - Properties
        right_panel = self.create_right_panel()
        right_panel.setMinimumWidth(250)
        right_panel.setMaximumWidth(400)

        content_splitter.addWidget(left_panel)
        content_splitter.addWidget(center_panel)
        content_splitter.addWidget(right_panel)

        # Set stretch factors (center gets most space)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 3)
        content_splitter.setStretchFactor(2, 1)

        main_layout.addWidget(content_splitter, 1)

        # 3. TIMELINE SECTION (Bottom)
        self.timeline_widget = TimelineWidget()
        self.timeline_widget.setMinimumHeight(250)
        self.timeline_widget.set_media_item_getter(self.get_media_item_by_path)
        # Connect timeline playhead to video seeking
        self.timeline_widget.playhead_moved.connect(self.seek_video_to_position)
        main_layout.addWidget(self.timeline_widget)

        # 4. FOOTER STATUS BAR
        main_layout.addWidget(self.create_footer())

        self.setLayout(main_layout)
        self.setWindowTitle("Professional Video Editor - CapCut Style")
        self.setMinimumSize(1400, 800)

    def apply_dark_theme(self):
        """Apply professional dark theme (CapCut-style)"""
        self.setStyleSheet("""
            /* Main Widget */
            QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 13px;
            }

            /* Menu Bar */
            QMenuBar {
                background-color: #0f0f0f;
                color: #e0e0e0;
                border-bottom: 1px solid #2a2a2a;
                padding: 4px;
            }
            QMenuBar::item {
                padding: 6px 12px;
                background-color: transparent;
            }
            QMenuBar::item:selected {
                background-color: #2a2a2a;
            }
            QMenu {
                background-color: #252525;
                border: 1px solid #3a3a3a;
            }
            QMenu::item {
                padding: 8px 30px;
            }
            QMenu::item:selected {
                background-color: #2a2a2a;
            }

            /* Buttons - Modern Flat Style */
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 10px;
                padding: 8px 16px;
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
                color: #555555;
            }

            /* Primary Action Button (Export, etc.) */
            QPushButton#primaryButton {
                background-color: #00bcd4;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-weight: bold;
            }
            QPushButton#primaryButton:hover {
                background-color: #00d4ea;
            }
            QPushButton#primaryButton:pressed {
                background-color: #00a4b8;
            }

            /* Labels */
            QLabel {
                color: #e0e0e0;
            }
            QLabel#sectionHeader {
                font-size: 12px;
                font-weight: bold;
                color: #00bcd4;
                padding: 8px 4px;
                text-transform: uppercase;
            }

            /* Group Boxes */
            QGroupBox {
                border: 1px solid #2a2a2a;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
                color: #00bcd4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                background-color: #1a1a1a;
            }

            /* Frames/Panels */
            QFrame#panel {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 10px;
            }
            QFrame#darkPanel {
                background-color: #141414;
                border: 1px solid #2a2a2a;
            }

            /* Tabs */
            QTabWidget::pane {
                border: 1px solid #2a2a2a;
                background-color: #1a1a1a;
                border-radius: 10px;
            }
            QTabBar::tab {
                background-color: #1e1e1e;
                color: #a0a0a0;
                padding: 10px 20px;
                margin-right: 2px;
                border: 1px solid #2a2a2a;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QTabBar::tab:selected {
                background-color: #1a1a1a;
                color: #00bcd4;
                border-bottom: 2px solid #00bcd4;
            }
            QTabBar::tab:hover:!selected {
                background-color: #252525;
            }

            /* Input Fields */
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 6px;
                color: #e0e0e0;
            }
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #00bcd4;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #a0a0a0;
                margin-right: 6px;
            }

            /* Sliders */
            QSlider::groove:horizontal {
                background: #2a2a2a;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00bcd4;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #00d4ea;
            }

            /* List/Table Widgets */
            QListWidget, QTableWidget, QTreeWidget {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 10px;
                alternate-background-color: #1a1a1a;
            }
            QListWidget::item, QTableWidget::item, QTreeWidget::item {
                padding: 8px;
                border-bottom: 1px solid #252525;
            }
            QListWidget::item:selected, QTableWidget::item:selected, QTreeWidget::item:selected {
                background-color: #2a4a5a;
                color: #ffffff;
            }
            QListWidget::item:hover:!selected, QTableWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {
                background-color: #252525;
            }
            QHeaderView::section {
                background-color: #1a1a1a;
                color: #a0a0a0;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #2a2a2a;
                font-weight: bold;
            }

            /* Scrollbars */
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #3a3a3a;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4a4a4a;
            }
            QScrollBar:horizontal {
                background: #1a1a1a;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #3a3a3a;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #4a4a4a;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                border: none;
                background: none;
            }

            /* Progress Bar */
            QProgressBar {
                background-color: #2a2a2a;
                border: none;
                border-radius: 10px;
                text-align: center;
                color: #e0e0e0;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00bcd4, stop:1 #00d4ea);
                border-radius: 10px;
            }

            /* Checkboxes */
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #3a3a3a;
                border-radius: 5px;
                background-color: #252525;
            }
            QCheckBox::indicator:checked {
                background-color: #00bcd4;
                border-color: #00bcd4;
            }

            /* Tooltips */
            QToolTip {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
            }

            /* Status Bar */
            QStatusBar {
                background-color: #0f0f0f;
                color: #a0a0a0;
                border-top: 1px solid #2a2a2a;
            }
        """)

    def create_top_navigation(self):
        """Create simplified top navigation bar with feature buttons"""
        header = QFrame()
        header.setObjectName("darkPanel")
        header.setFixedHeight(65)

        layout = QHBoxLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(10)

        # Feature Buttons (Left Side)
        feature_style = """
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353535;
            }
            QPushButton:pressed {
                background-color: #202020;
            }
        """

        audio_btn = QPushButton("🎧 Audio")
        audio_btn.setStyleSheet(feature_style)
        audio_btn.setToolTip("Audio controls and effects")
        audio_btn.clicked.connect(self.open_audio_feature)
        layout.addWidget(audio_btn)

        text_btn = QPushButton("✏️ Text")
        text_btn.setStyleSheet(feature_style)
        text_btn.setToolTip("Add text overlays")
        text_btn.clicked.connect(self.open_text_feature)
        layout.addWidget(text_btn)

        filters_btn = QPushButton("🎨 Filters")
        filters_btn.setStyleSheet(feature_style)
        filters_btn.setToolTip("Apply video filters")
        filters_btn.clicked.connect(self.open_filters_feature)
        layout.addWidget(filters_btn)

        preset_btn = QPushButton("📦 Presets")
        preset_btn.setStyleSheet(feature_style)
        preset_btn.setToolTip("Manage and apply editing presets")
        preset_btn.clicked.connect(self.open_preset_manager)
        layout.addWidget(preset_btn)

        bulk_btn = QPushButton("🧩 Bulk Processing")
        bulk_btn.setStyleSheet(feature_style)
        bulk_btn.setToolTip("Process multiple videos")
        bulk_btn.clicked.connect(self.open_bulk_processing)
        layout.addWidget(bulk_btn)

        title_gen_btn = QPushButton("🪄 Title Generator")
        title_gen_btn.setStyleSheet(feature_style)
        title_gen_btn.setToolTip("Auto-generate video titles")
        title_gen_btn.clicked.connect(self.open_title_generator)
        layout.addWidget(title_gen_btn)

        layout.addSpacing(15)

        # Current Video Title Input (Center)
        title_label = QLabel("📄")
        title_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(title_label)

        self.video_title_input = QLineEdit()
        self.video_title_input.setPlaceholderText("No video loaded")
        self.video_title_input.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 10px 15px;
                color: #e0e0e0;
                font-size: 13px;
                min-width: 250px;
            }
            QLineEdit:focus {
                border-color: #00bcd4;
            }
        """)
        layout.addWidget(self.video_title_input)

        layout.addStretch()

        # Export Button
        export_btn = QPushButton("📤 Export Video")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #00bcd4;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #00d4ea;
            }
            QPushButton:pressed {
                background-color: #00a4b8;
            }
        """)
        export_btn.setToolTip("Export/Render video")
        export_btn.clicked.connect(self.export_video)
        layout.addWidget(export_btn)

        layout.addSpacing(15)

        # Navigation Controls (Right Side)
        back_btn = QPushButton("⬅️ Back")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 10px;
                padding: 10px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
        """)
        back_btn.setToolTip("Go back to main menu")
        back_btn.clicked.connect(self.close_editor)
        layout.addWidget(back_btn)

        close_btn = QPushButton("❌ Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 10px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #d63031;
            }
        """)
        close_btn.setToolTip("Close project")
        close_btn.clicked.connect(self.close_editor)
        layout.addWidget(close_btn)

        header.setLayout(layout)
        return header

    def create_left_panel(self):
        """Create left sidebar - Media Library (simplified)"""
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("Media Library")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #00bcd4; padding: 8px 4px;")
        layout.addWidget(header)

        # Import Button
        import_btn = QPushButton("📥 Import Media")
        import_btn.setMinimumHeight(45)
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #00bcd4;
                color: #ffffff;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00d4ea;
            }
            QPushButton:pressed {
                background-color: #00a4b8;
            }
        """)
        import_btn.setToolTip("Import videos, images, audio")
        import_btn.clicked.connect(self.import_media)
        layout.addWidget(import_btn)

        # Search
        search_box = QLineEdit()
        search_box.setPlaceholderText("🔍 Search media...")
        search_box.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 8px 12px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #00bcd4;
            }
        """)
        layout.addWidget(search_box)

        # Media List (draggable)
        self.media_list = DraggableMediaList()
        self.media_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 10px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #252525;
                border-radius: 8px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #2a4a5a;
                color: #ffffff;
            }
            QListWidget::item:hover:!selected {
                background-color: #252525;
            }
        """)
        self.media_list.setToolTip("Drag media to timeline to add to project")
        self.media_list.itemDoubleClicked.connect(self.preview_media_item)
        self.media_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.media_list.customContextMenuRequested.connect(self.show_media_context_menu)
        layout.addWidget(self.media_list, 1)

        # Media info
        self.media_info_label = QLabel("No media imported")
        self.media_info_label.setStyleSheet("color: #888888; font-size: 11px; padding: 8px 4px;")
        self.media_info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.media_info_label)

        panel.setLayout(layout)
        return panel

    def create_center_panel(self):
        """Create center panel - Preview + Playback"""
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Preview Window
        preview_container = QFrame()
        preview_container.setObjectName("darkPanel")
        preview_container.setMinimumHeight(400)

        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)

        # Create a container for video player and placeholder
        self.preview_stack = QFrame()
        stack_layout = QVBoxLayout()
        stack_layout.setContentsMargins(0, 0, 0, 0)

        # Custom Video Player (uses MoviePy - no DirectShow dependency)
        self.custom_player = CustomVideoPlayer()
        self.custom_player.position_changed.connect(self.update_playback_position)
        self.custom_player.duration_changed.connect(self.update_playback_duration)
        self.custom_player.state_changed.connect(self.update_playback_state)
        self.custom_player.error_occurred.connect(self.handle_playback_error)

        # Placeholder label (shown when no video)
        self.preview_placeholder = QLabel()
        self.preview_placeholder.setAlignment(Qt.AlignCenter)
        self.preview_placeholder.setStyleSheet("""
            QLabel {
                background-color: #000000;
                color: #666666;
                font-size: 20px;
                border: 2px dashed #2a2a2a;
            }
        """)
        self.preview_placeholder.setMinimumSize(800, 450)
        self.preview_placeholder.setText("🎬\n\nNo video loaded\n\nImport media and double-click to preview")

        # Add both to stack (only one will be visible at a time)
        stack_layout.addWidget(self.custom_player)
        stack_layout.addWidget(self.preview_placeholder)
        self.preview_stack.setLayout(stack_layout)

        # Show placeholder by default
        self.custom_player.hide()
        self.preview_placeholder.show()

        preview_layout.addWidget(self.preview_stack)
        preview_container.setLayout(preview_layout)
        layout.addWidget(preview_container)

        # Playback Controls
        controls_frame = QFrame()
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(20, 10, 20, 10)
        controls_layout.setSpacing(10)

        # Playback buttons
        controls_layout.addStretch()

        skip_back_btn = QPushButton("⏮")
        skip_back_btn.setMinimumSize(40, 40)
        skip_back_btn.setToolTip("Previous frame (←)")
        controls_layout.addWidget(skip_back_btn)

        self.play_btn = QPushButton("▶")
        self.play_btn.setMinimumSize(50, 50)
        self.play_btn.setStyleSheet("font-size: 18px; background-color: #00bcd4;")
        self.play_btn.setToolTip("Play/Pause (Space)")
        self.play_btn.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.play_btn)

        skip_forward_btn = QPushButton("⏭")
        skip_forward_btn.setMinimumSize(40, 40)
        skip_forward_btn.setToolTip("Next frame (→)")
        controls_layout.addWidget(skip_forward_btn)

        stop_btn = QPushButton("⏹")
        stop_btn.setMinimumSize(40, 40)
        stop_btn.setToolTip("Stop")
        controls_layout.addWidget(stop_btn)

        controls_layout.addSpacing(20)

        loop_btn = QPushButton("🔁")
        loop_btn.setMinimumSize(40, 40)
        loop_btn.setCheckable(True)
        loop_btn.setToolTip("Loop playback")
        controls_layout.addWidget(loop_btn)

        # Speed control
        speed_label = QLabel("Speed:")
        controls_layout.addWidget(speed_label)

        speed_combo = QComboBox()
        speed_combo.addItems(["0.25x", "0.5x", "1x", "1.5x", "2x"])
        speed_combo.setCurrentText("1x")
        speed_combo.setMinimumWidth(80)
        controls_layout.addWidget(speed_combo)

        controls_layout.addStretch()

        controls_frame.setLayout(controls_layout)
        layout.addWidget(controls_frame)

        # Timeline Scrubber
        scrubber_frame = QFrame()
        scrubber_layout = QVBoxLayout()
        scrubber_layout.setContentsMargins(10, 5, 10, 5)

        # Time display
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00:00")
        self.current_time_label.setStyleSheet("color: #00bcd4; font-weight: bold;")
        time_layout.addWidget(self.current_time_label)

        # Scrubber slider
        self.scrubber_slider = QSlider(Qt.Horizontal)
        self.scrubber_slider.setMinimum(0)
        self.scrubber_slider.setMaximum(100)
        self.scrubber_slider.setValue(0)
        time_layout.addWidget(self.scrubber_slider, 1)

        self.total_time_label = QLabel("00:00:00")
        self.total_time_label.setStyleSheet("color: #888888;")
        time_layout.addWidget(self.total_time_label)

        scrubber_layout.addLayout(time_layout)
        scrubber_frame.setLayout(scrubber_layout)
        layout.addWidget(scrubber_frame)

        panel.setLayout(layout)
        return panel

    def create_right_panel(self):
        """Create right sidebar - Properties Panel"""
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        header = QLabel("Properties")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # Scrollable area for properties
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        props_widget = QWidget()
        props_layout = QVBoxLayout()
        props_layout.setSpacing(12)

        # Player Info Group
        player_group = QGroupBox("Player Info")
        player_layout = QGridLayout()
        player_layout.setSpacing(8)

        player_layout.addWidget(QLabel("Name:"), 0, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Untitled")
        player_layout.addWidget(self.name_input, 0, 1)

        player_layout.addWidget(QLabel("Resolution:"), 1, 0)
        res_label = QLabel("1920 x 1080")
        res_label.setStyleSheet("color: #888888;")
        player_layout.addWidget(res_label, 1, 1)

        player_layout.addWidget(QLabel("Type:"), 2, 0)
        type_label = QLabel("Video")
        type_label.setStyleSheet("color: #888888;")
        player_layout.addWidget(type_label, 2, 1)

        player_group.setLayout(player_layout)
        props_layout.addWidget(player_group)

        # Transform Group
        transform_group = QGroupBox("Transform")
        transform_layout = QVBoxLayout()
        transform_layout.setSpacing(10)

        # Position
        pos_layout = QGridLayout()
        pos_layout.addWidget(QLabel("Position X:"), 0, 0)
        pos_x = QSpinBox()
        pos_x.setRange(-9999, 9999)
        pos_x.setValue(0)
        pos_layout.addWidget(pos_x, 0, 1)

        pos_layout.addWidget(QLabel("Position Y:"), 1, 0)
        pos_y = QSpinBox()
        pos_y.setRange(-9999, 9999)
        pos_y.setValue(0)
        pos_layout.addWidget(pos_y, 1, 1)

        transform_layout.addLayout(pos_layout)

        # Scale
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scale:"))
        scale_slider = QSlider(Qt.Horizontal)
        scale_slider.setRange(10, 500)
        scale_slider.setValue(100)
        scale_layout.addWidget(scale_slider)
        scale_value = QLabel("100%")
        scale_layout.addWidget(scale_value)
        transform_layout.addLayout(scale_layout)

        # Rotation
        rotation_layout = QHBoxLayout()
        rotation_layout.addWidget(QLabel("Rotation:"))
        rotation_slider = QSlider(Qt.Horizontal)
        rotation_slider.setRange(-360, 360)
        rotation_slider.setValue(0)
        rotation_layout.addWidget(rotation_slider)
        rotation_value = QLabel("0°")
        rotation_layout.addWidget(rotation_value)
        transform_layout.addLayout(rotation_layout)

        # Flip buttons
        flip_layout = QHBoxLayout()
        flip_h_btn = QPushButton("Flip H")
        flip_v_btn = QPushButton("Flip V")
        flip_layout.addWidget(flip_h_btn)
        flip_layout.addWidget(flip_v_btn)
        transform_layout.addLayout(flip_layout)

        transform_group.setLayout(transform_layout)
        props_layout.addWidget(transform_group)

        # Opacity
        opacity_group = QGroupBox("Opacity & Blending")
        opacity_layout = QVBoxLayout()

        opacity_slider_layout = QHBoxLayout()
        opacity_slider_layout.addWidget(QLabel("Opacity:"))
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setRange(0, 100)
        opacity_slider.setValue(100)
        opacity_slider_layout.addWidget(opacity_slider)
        opacity_val = QLabel("100%")
        opacity_slider_layout.addWidget(opacity_val)
        opacity_layout.addLayout(opacity_slider_layout)

        blend_layout = QHBoxLayout()
        blend_layout.addWidget(QLabel("Blend Mode:"))
        blend_combo = QComboBox()
        blend_combo.addItems(["Normal", "Multiply", "Screen", "Overlay", "Soft Light"])
        blend_layout.addWidget(blend_combo)
        opacity_layout.addLayout(blend_layout)

        opacity_group.setLayout(opacity_layout)
        props_layout.addWidget(opacity_group)

        # Action Buttons
        modify_btn = QPushButton("✏️ Modify")
        modify_btn.setMinimumHeight(35)
        props_layout.addWidget(modify_btn)

        reset_btn = QPushButton("🔄 Reset")
        reset_btn.setMinimumHeight(35)
        props_layout.addWidget(reset_btn)

        props_layout.addStretch()

        props_widget.setLayout(props_layout)
        scroll.setWidget(props_widget)
        layout.addWidget(scroll)

        panel.setLayout(layout)
        return panel

    def create_footer(self):
        """Create footer status bar"""
        footer = QFrame()
        footer.setStyleSheet("background-color: #0f0f0f; border-top: 1px solid #2a2a2a;")
        footer.setFixedHeight(30)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(15)

        # Project info
        self.project_label = QLabel("Untitled Project")
        self.project_label.setStyleSheet("color: #00bcd4; font-weight: bold;")
        layout.addWidget(self.project_label)

        layout.addWidget(QLabel("|"))

        # Duration
        duration_label = QLabel("Duration: 00:00:00")
        duration_label.setStyleSheet("color: #888888;")
        layout.addWidget(duration_label)

        layout.addWidget(QLabel("|"))

        # Clips count
        clips_label = QLabel("Clips: 0")
        clips_label.setStyleSheet("color: #888888;")
        layout.addWidget(clips_label)

        layout.addWidget(QLabel("|"))

        # FPS
        fps_label = QLabel("30 fps")
        fps_label.setStyleSheet("color: #888888;")
        layout.addWidget(fps_label)

        layout.addWidget(QLabel("|"))

        # Resolution
        res_label = QLabel("1920x1080")
        res_label.setStyleSheet("color: #888888;")
        layout.addWidget(res_label)

        layout.addStretch()

        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #00d4ea;")
        layout.addWidget(self.status_label)

        footer.setLayout(layout)
        return footer

    # ==================== PLACEHOLDER METHODS ====================
    # These will be implemented incrementally

    def open_audio_feature(self):
        """Open audio feature dialog - Placeholder"""
        self.status_label.setText("Audio feature - Coming soon")
        QMessageBox.information(
            self,
            "🎧 Audio Feature",
            "Audio controls will include:\n\n"
            "• Extract audio from video\n"
            "• Remove vocals (ML)\n"
            "• Remove music (ML)\n"
            "• Volume control\n"
            "• Fade in/out\n"
            "• Audio effects\n\n"
            "This feature will be implemented next!"
        )
        logger.info("Audio feature clicked")

    def open_text_feature(self):
        """Open text overlay feature - Placeholder"""
        self.status_label.setText("Text feature - Coming soon")
        QMessageBox.information(
            self,
            "✏️ Text Feature",
            "Text overlay will include:\n\n"
            "• Add text to video\n"
            "• Custom fonts and colors\n"
            "• Text animations\n"
            "• Position control\n"
            "• Opacity and styling\n\n"
            "This feature will be implemented next!"
        )
        logger.info("Text feature clicked")

    def open_filters_feature(self):
        """Open filters feature - Placeholder"""
        self.status_label.setText("Filters feature - Coming soon")
        QMessageBox.information(
            self,
            "🎨 Filters Feature",
            "Video filters will include:\n\n"
            "• Color correction\n"
            "• Brightness/Contrast\n"
            "• Saturation control\n"
            "• Artistic effects\n"
            "• Vintage/Cinematic looks\n"
            "• Filter intensity control\n\n"
            "This feature will be implemented next!"
        )
        logger.info("Filters feature clicked")

    def open_preset_manager(self):
        """Open preset manager dialog"""
        from modules.video_editor.preset_dialog import PresetManagerDialog
        try:
            dialog = PresetManagerDialog(self, self.preset_manager)
            if dialog.exec_():
                # Preset was selected/applied
                self.status_label.setText("Preset applied successfully")
        except Exception as e:
            logger.error(f"Error opening preset manager: {e}")
            self.status_label.setText("Error opening preset manager")

    def export_video(self):
        """Export video - Placeholder"""
        self.status_label.setText("Export dialog - Coming soon")
        QMessageBox.information(self, "Export", "Export functionality will be added next!")
        logger.info("Export clicked")

    def import_media(self):
        """Import media files via file dialog"""
        # Define file filter
        file_filter = "Media Files ("
        file_filter += " ".join([f"*{ext}" for ext in VIDEO_FORMATS + AUDIO_FORMATS + IMAGE_FORMATS])
        file_filter += ");;Video Files ("
        file_filter += " ".join([f"*{ext}" for ext in VIDEO_FORMATS])
        file_filter += ");;Audio Files ("
        file_filter += " ".join([f"*{ext}" for ext in AUDIO_FORMATS])
        file_filter += ");;Image Files ("
        file_filter += " ".join([f"*{ext}" for ext in IMAGE_FORMATS])
        file_filter += ");;All Files (*.*)"

        # Open file dialog
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Media Files",
            "",
            file_filter
        )

        if file_paths:
            self.process_imported_files(file_paths)

    def process_imported_files(self, file_paths: List[str]):
        """Process and add imported files to media library"""
        imported_count = 0
        for file_path in file_paths:
            try:
                media_item = self.create_media_item(file_path)
                if media_item:
                    self.media_items.append(media_item)
                    self.add_media_to_list(media_item)
                    imported_count += 1
            except Exception as e:
                logger.error(f"Error importing file {file_path}: {e}")
                QMessageBox.warning(
                    self,
                    "Import Error",
                    f"Failed to import:\n{os.path.basename(file_path)}\n\nError: {str(e)}"
                )

        if imported_count > 0:
            self.status_label.setText(f"Imported {imported_count} file(s)")
            self.media_info_label.setText(f"{len(self.media_items)} item(s) in library")
        else:
            self.status_label.setText("No files imported")

    def create_media_item(self, file_path: str) -> Optional[MediaItem]:
        """Create a MediaItem from a file path"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        path = Path(file_path)
        file_ext = path.suffix.lower()
        file_name = path.name
        file_size = path.stat().st_size

        # Determine file type
        if file_ext in VIDEO_FORMATS:
            file_type = 'video'
        elif file_ext in AUDIO_FORMATS:
            file_type = 'audio'
        elif file_ext in IMAGE_FORMATS:
            file_type = 'image'
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")

        # Create media item
        media_item = MediaItem(
            file_path=str(file_path),
            file_name=file_name,
            file_type=file_type,
            file_size=file_size
        )

        # Get metadata based on type
        try:
            if file_type == 'video':
                self.extract_video_metadata(media_item)
            elif file_type == 'audio':
                self.extract_audio_metadata(media_item)
            elif file_type == 'image':
                self.extract_image_metadata(media_item)
        except Exception as e:
            logger.warning(f"Could not extract metadata for {file_name}: {e}")

        return media_item

    def extract_video_metadata(self, media_item: MediaItem):
        """Extract metadata from video file using moviepy"""
        try:
            # Try moviepy 2.x import path first
            try:
                from moviepy import VideoFileClip
            except ImportError:
                # Fallback to old import path
                from moviepy.editor import VideoFileClip

            clip = VideoFileClip(media_item.file_path)
            media_item.duration = clip.duration
            media_item.width = clip.w
            media_item.height = clip.h
            media_item.fps = clip.fps

            # Generate thumbnail from first frame
            try:
                frame = clip.get_frame(0)
                from PIL import Image

                img = Image.fromarray(frame)
                # Resize to thumbnail
                img.thumbnail((160, 90), Image.Resampling.LANCZOS)

                # Convert to QPixmap - simplified approach
                # For now, skip actual conversion - will be implemented later
                # media_item.thumbnail = qimage
            except Exception as e:
                logger.warning(f"Could not generate thumbnail: {e}")

            clip.close()
        except Exception as e:
            logger.error(f"Error extracting video metadata: {e}")
            # Don't raise - allow import to continue without metadata
            logger.warning(f"Continuing import without metadata for: {media_item.file_name}")

    def extract_audio_metadata(self, media_item: MediaItem):
        """Extract metadata from audio file"""
        try:
            # Try moviepy 2.x import path first
            try:
                from moviepy import AudioFileClip
            except ImportError:
                # Fallback to old import path
                from moviepy.editor import AudioFileClip

            clip = AudioFileClip(media_item.file_path)
            media_item.duration = clip.duration
            clip.close()
        except Exception as e:
            logger.error(f"Error extracting audio metadata: {e}")
            # Don't raise - allow import to continue without metadata
            logger.warning(f"Continuing import without metadata for: {media_item.file_name}")

    def extract_image_metadata(self, media_item: MediaItem):
        """Extract metadata from image file"""
        try:
            from PIL import Image

            img = Image.open(media_item.file_path)
            media_item.width, media_item.height = img.size

            # Generate thumbnail
            img.thumbnail((160, 90), Image.Resampling.LANCZOS)
            img_bytes = img.tobytes('raw', img.mode)

            # For now, skip thumbnail - will implement later if needed

        except Exception as e:
            logger.error(f"Error extracting image metadata: {e}")
            raise

    def add_media_to_list(self, media_item: MediaItem):
        """Add media item to the list widget"""
        # Format file size
        size_mb = media_item.file_size / (1024 * 1024)
        size_str = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_mb/1024:.1f} GB"

        # Format duration
        duration_str = ""
        if media_item.duration > 0:
            mins, secs = divmod(int(media_item.duration), 60)
            duration_str = f" | {mins:02d}:{secs:02d}"

        # Format resolution
        res_str = ""
        if media_item.width > 0 and media_item.height > 0:
            res_str = f" | {media_item.width}x{media_item.height}"

        # Create list item
        icon_map = {'video': '🎬', 'audio': '🎵', 'image': '🖼️'}
        icon = icon_map.get(media_item.file_type, '📄')

        item_text = f"{icon} {media_item.file_name}\n{size_str}{duration_str}{res_str}"

        list_item = QListWidgetItem(item_text)
        list_item.setData(Qt.UserRole, media_item)

        # Set tooltip for drag hint
        list_item.setToolTip(f"Double-click to PREVIEW\nDrag to TIMELINE to add")

        self.media_list.addItem(list_item)

        # Store reference for drag operations
        self.media_item_map[media_item.file_path] = media_item

        logger.info(f"Added to media library: {media_item.file_name} (type: {media_item.file_type}, duration: {media_item.duration}s)")
        logger.debug(f"Media item map size: {len(self.media_item_map)}")

    def show_media_context_menu(self, position):
        """Show context menu for media items"""
        item = self.media_list.itemAt(position)
        if not item:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                color: #e0e0e0;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2a4a5a;
            }
        """)

        # Preview action
        preview_action = menu.addAction("👁️ Preview")
        preview_action.triggered.connect(lambda: self.preview_media_item(item))

        menu.addSeparator()

        # Delete action
        delete_action = menu.addAction("🗑️ Remove from Library")
        delete_action.triggered.connect(lambda: self.delete_media_item(item))

        # Show menu at cursor position
        menu.exec_(self.media_list.mapToGlobal(position))

    def delete_media_item(self, item: QListWidgetItem):
        """Delete a media item from the library"""
        media_item: MediaItem = item.data(Qt.UserRole)

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Remove Media",
            f"Remove '{media_item.file_name}' from library?\n\nThis will not delete the original file.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Remove from media list
            row = self.media_list.row(item)
            self.media_list.takeItem(row)

            # Remove from media_items array
            if media_item in self.media_items:
                self.media_items.remove(media_item)

            # Update info label
            self.media_info_label.setText(f"{len(self.media_items)} item(s) in library")
            self.status_label.setText(f"Removed: {media_item.file_name}")

            logger.info(f"Removed media item: {media_item.file_name}")

    def preview_media_item(self, item: QListWidgetItem):
        """Preview a media item when double-clicked"""
        media_item: MediaItem = item.data(Qt.UserRole)

        if media_item.file_type == 'video':
            # Load video for preview
            self.load_video_preview(media_item.file_path)
            self.video_title_input.setText(media_item.file_name)
            self.current_video_path = media_item.file_path
            self.status_label.setText(f"Loaded: {media_item.file_name}")
        elif media_item.file_type == 'audio':
            # Load audio for preview
            self.load_audio_preview(media_item.file_path)
            self.video_title_input.setText(media_item.file_name)
            self.status_label.setText(f"Loaded audio: {media_item.file_name}")
        elif media_item.file_type == 'image':
            self.status_label.setText(f"Image preview - Coming soon: {media_item.file_name}")

    def load_video_preview(self, video_path: str):
        """Load a video file into the custom player"""
        try:
            logger.info(f"Loading video for preview: {video_path}")

            # Show custom player, hide placeholder
            self.preview_placeholder.hide()
            self.custom_player.show()

            # Load video using custom player
            success = self.custom_player.load_video(video_path)

            if success:
                logger.info(f"Video loaded successfully, starting playback...")
                # Auto-play
                self.custom_player.play()
            else:
                logger.error("Failed to load video")
                self.custom_player.hide()
                self.preview_placeholder.show()

        except Exception as e:
            logger.error(f"Error loading video: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load video:\n{str(e)}")
            # Show placeholder again on error
            self.custom_player.hide()
            self.preview_placeholder.show()

    def handle_playback_error(self, error_msg):
        """Handle custom player errors"""
        logger.error(f"Playback error: {error_msg}")
        QMessageBox.warning(
            self,
            "Playback Error",
            f"Cannot play video:\n{error_msg}"
        )
        # Show placeholder on error
        self.custom_player.hide()
        self.preview_placeholder.show()

    def load_audio_preview(self, audio_path: str):
        """Load an audio file - placeholder for now"""
        self.status_label.setText("Audio preview - coming soon")
        logger.info(f"Audio preview requested: {audio_path}")

    def update_playback_position(self, position: int):
        """Update scrubber position when playback position changes"""
        # position is in milliseconds from custom player
        # Get duration
        duration = self.custom_player.duration * 1000 if self.custom_player.duration > 0 else 1

        if duration > 0:
            # Update scrubber
            self.scrubber_slider.setValue(int(position * 100 / duration))

            # Update time label
            secs = position // 1000
            mins, secs = divmod(secs, 60)
            hrs, mins = divmod(mins, 60)
            self.current_time_label.setText(f"{hrs:02d}:{mins:02d}:{secs:02d}")

            # Update timeline playhead
            time_seconds = position / 1000.0
            self.timeline_widget.update_playhead(time_seconds)

    def update_playback_duration(self, duration: int):
        """Update total duration label"""
        if duration > 0:
            secs = duration // 1000
            mins, secs = divmod(secs, 60)
            hrs, mins = divmod(mins, 60)
            self.total_time_label.setText(f"{hrs:02d}:{mins:02d}:{secs:02d}")
            self.scrubber_slider.setMaximum(100)

    def update_playback_state(self, state):
        """Update UI when playback state changes"""
        if state == "playing":
            self.play_btn.setText("⏸")
            self.status_label.setText("Playing...")
        elif state == "paused":
            self.play_btn.setText("▶")
            self.status_label.setText("Paused")
        elif state == "stopped":
            self.play_btn.setText("▶")
            self.status_label.setText("Stopped")

    def toggle_playback(self):
        """Toggle play/pause"""
        current_state = self.custom_player.get_state()

        if current_state == "playing":
            self.custom_player.pause()
        elif current_state in ["paused", "stopped"]:
            self.custom_player.play()
        else:
            logger.warning(f"Unknown playback state: {current_state}")

    def seek_video_to_position(self, time_seconds: float):
        """Seek video to timeline position"""
        if self.custom_player and self.custom_player.video_clip:
            # Convert seconds to milliseconds
            position_ms = int(time_seconds * 1000)
            self.custom_player.seek(position_ms)
            logger.info(f"Video seeked to {time_seconds:.2f}s via timeline click")

    def apply_quick_preset(self, preset_id):
        """Apply quick preset - Placeholder"""
        self.status_label.setText(f"Applied preset: {preset_id}")
        logger.info(f"Quick preset applied: {preset_id}")

    def open_bulk_processing(self):
        """Open bulk processing dialog"""
        from modules.video_editor.gui_professional import BulkProcessingDialog
        try:
            dialog = BulkProcessingDialog(self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.information(self, "Bulk Processing", "Bulk processing dialog will open here!")
            logger.info("Bulk processing clicked")

    def open_title_generator(self):
        """Open title generator"""
        QMessageBox.information(
            self,
            "Title Generator",
            "🤖 Auto Title Generator\n\n"
            "Generate video titles automatically based on:\n"
            "• Filename analysis\n"
            "• Content detection\n"
            "• Template system\n\n"
            "This feature will be fully implemented!"
        )
        logger.info("Title generator clicked")

    def get_media_item_by_path(self, file_path: str) -> Optional[MediaItem]:
        """Get media item by file path"""
        logger.debug(f"Looking up media item for: {file_path}")
        logger.debug(f"Available paths in map: {list(self.media_item_map.keys())}")

        media_item = self.media_item_map.get(file_path)

        if media_item:
            logger.info(f"Found media item: {media_item.file_name}")
        else:
            logger.warning(f"Media item not found for path: {file_path}")

        return media_item

    def close_editor(self):
        """Close editor"""
        if self.back_callback:
            self.back_callback()
        else:
            self.close()

    # ==================== DRAG AND DROP ====================

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.status_label.setText("Drop files to import...")
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle drop event"""
        urls = event.mimeData().urls()
        file_paths = []

        for url in urls:
            if url.isLocalFile():
                file_path = url.toLocalFile()
                file_paths.append(file_path)

        if file_paths:
            self.process_imported_files(file_paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    # ==================== KEYBOARD SHORTCUTS ====================

    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for the editor"""
        # Import
        QShortcut(QKeySequence("Ctrl+I"), self, self.import_media)

        # Playback
        QShortcut(QKeySequence(Qt.Key_Space), self, self.toggle_playback)

        # Export
        QShortcut(QKeySequence("Ctrl+E"), self, self.export_video)

        # Save/Open (placeholders for now)
        QShortcut(QKeySequence("Ctrl+S"), self, lambda: self.status_label.setText("Save project - Coming soon"))
        QShortcut(QKeySequence("Ctrl+N"), self, lambda: self.status_label.setText("New project - Coming soon"))
        QShortcut(QKeySequence("Ctrl+O"), self, lambda: self.status_label.setText("Open project - Coming soon"))

        logger.info("Keyboard shortcuts initialized")
