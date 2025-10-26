"""
modules/video_editor/capcut_editor.py
Professional CapCut-Style Video Editor - Complete GUI Design
Step 1: Complete UI Layout
Step 2-N: Add functionality incrementally
"""

import os
import sys
from typing import Optional, List, Dict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QSlider, QLineEdit, QProgressBar, QMessageBox, QSplitter,
    QCheckBox, QTextEdit, QFrame, QGridLayout, QScrollArea,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QTabWidget, QMenuBar, QMenu, QAction, QToolBar, QStatusBar,
    QTreeWidget, QTreeWidgetItem
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPalette

from modules.logging.logger import get_logger
from modules.video_editor.preset_manager import PresetManager, EditingPreset

logger = get_logger(__name__)


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
        self.media_items = []
        self.timeline_clips = []

        self.init_ui()

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
        main_layout.addWidget(self.create_timeline_section())

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
            QCheckBox::indicator:checked::after {
                content: "✓";
                color: white;
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

        # Media List
        self.media_list = QListWidget()
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

        # Preview Label
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                color: #666666;
                font-size: 24px;
                border: 2px dashed #2a2a2a;
            }
        """)
        self.preview_label.setMinimumSize(800, 450)
        self.preview_label.setText("🎬\n\nNo video loaded\n\nImport media and add to timeline")
        preview_layout.addWidget(self.preview_label)

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

    def create_timeline_section(self):
        """Create bottom timeline section"""
        timeline_container = QFrame()
        timeline_container.setObjectName("darkPanel")
        timeline_container.setMinimumHeight(250)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Timeline Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #2a2a2a;")
        toolbar.setFixedHeight(45)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        toolbar_layout.setSpacing(8)

        # Timeline Tools
        tools_label = QLabel("Tools:")
        tools_label.setStyleSheet("color: #888888; font-weight: bold;")
        toolbar_layout.addWidget(tools_label)

        tool_buttons = [
            ("✋ Select", "V"),
            ("✂️ Split", "C"),
            ("📏 Slip", "Y"),
            ("🔍 Zoom", "Z")
        ]

        for name, shortcut in tool_buttons:
            btn = QPushButton(name)
            btn.setToolTip(f"Shortcut: {shortcut}")
            btn.setCheckable(True)
            toolbar_layout.addWidget(btn)

        toolbar_layout.addSpacing(20)

        # Zoom Controls
        zoom_label = QLabel("Zoom:")
        zoom_label.setStyleSheet("color: #888888; font-weight: bold;")
        toolbar_layout.addWidget(zoom_label)

        zoom_out_btn = QPushButton("➖")
        zoom_out_btn.setMaximumWidth(35)
        zoom_out_btn.setToolTip("Zoom out (Ctrl+-)")
        toolbar_layout.addWidget(zoom_out_btn)

        zoom_slider = QSlider(Qt.Horizontal)
        zoom_slider.setRange(0, 100)
        zoom_slider.setValue(50)
        zoom_slider.setMaximumWidth(150)
        toolbar_layout.addWidget(zoom_slider)

        zoom_in_btn = QPushButton("➕")
        zoom_in_btn.setMaximumWidth(35)
        zoom_in_btn.setToolTip("Zoom in (Ctrl++)")
        toolbar_layout.addWidget(zoom_in_btn)

        fit_btn = QPushButton("⬌ Fit")
        fit_btn.setToolTip("Fit to timeline (Shift+Z)")
        toolbar_layout.addWidget(fit_btn)

        toolbar_layout.addSpacing(20)

        # Snap Toggle
        snap_check = QCheckBox("🧲 Snap")
        snap_check.setChecked(True)
        snap_check.setToolTip("Enable snapping to clips/markers")
        toolbar_layout.addWidget(snap_check)

        # Marker
        marker_btn = QPushButton("📍 Add Marker")
        marker_btn.setToolTip("Add marker at playhead (M)")
        toolbar_layout.addWidget(marker_btn)

        toolbar_layout.addStretch()

        # Track Management
        add_track_btn = QPushButton("➕ Add Track")
        add_track_btn.setToolTip("Add new video/audio track")
        toolbar_layout.addWidget(add_track_btn)

        toolbar.setLayout(toolbar_layout)
        layout.addWidget(toolbar)

        # Timeline Tracks Area
        tracks_scroll = QScrollArea()
        tracks_scroll.setWidgetResizable(True)
        tracks_scroll.setFrameShape(QFrame.NoFrame)

        tracks_widget = QWidget()
        tracks_layout = QVBoxLayout()
        tracks_layout.setContentsMargins(0, 0, 0, 0)
        tracks_layout.setSpacing(2)

        # Import Prompt (when empty)
        import_prompt = QFrame()
        import_prompt.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px dashed #3a3a3a;
                border-radius: 8px;
            }
        """)
        import_prompt.setMinimumHeight(150)

        import_layout = QVBoxLayout()
        import_layout.setAlignment(Qt.AlignCenter)

        import_icon = QLabel("📥")
        import_icon.setStyleSheet("font-size: 48px;")
        import_icon.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(import_icon)

        import_label = QLabel("Import media here or to the Media Library")
        import_label.setStyleSheet("font-size: 14px; color: #888888; font-weight: bold;")
        import_label.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(import_label)

        import_hint = QLabel("Drag and drop files or click to browse")
        import_hint.setStyleSheet("font-size: 12px; color: #666666;")
        import_hint.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(import_hint)

        import_prompt.setLayout(import_layout)
        tracks_layout.addWidget(import_prompt)

        # Sample Tracks (will be replaced with actual tracks)
        track_names = ["Video 1", "Video 2", "Audio 1", "Text 1"]
        for track_name in track_names:
            track = self.create_timeline_track(track_name)
            tracks_layout.addWidget(track)

        tracks_layout.addStretch()
        tracks_widget.setLayout(tracks_layout)
        tracks_scroll.setWidget(tracks_widget)
        layout.addWidget(tracks_scroll)

        timeline_container.setLayout(layout)
        return timeline_container

    def create_timeline_track(self, name: str):
        """Create a single timeline track"""
        track = QFrame()
        track.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-bottom: 1px solid #2a2a2a;
            }
        """)
        track.setFixedHeight(60)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Track header
        header = QFrame()
        header.setStyleSheet("background-color: #252525; border-right: 1px solid #2a2a2a;")
        header.setFixedWidth(120)

        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(4)

        # Track name
        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        header_layout.addWidget(name_label)

        # Track controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(4)

        lock_btn = QPushButton("🔒")
        lock_btn.setMaximumWidth(25)
        lock_btn.setMaximumHeight(25)
        lock_btn.setCheckable(True)
        lock_btn.setToolTip("Lock track")
        controls_layout.addWidget(lock_btn)

        visible_btn = QPushButton("👁")
        visible_btn.setMaximumWidth(25)
        visible_btn.setMaximumHeight(25)
        visible_btn.setCheckable(True)
        visible_btn.setChecked(True)
        visible_btn.setToolTip("Toggle visibility")
        controls_layout.addWidget(visible_btn)

        mute_btn = QPushButton("🔇")
        mute_btn.setMaximumWidth(25)
        mute_btn.setMaximumHeight(25)
        mute_btn.setCheckable(True)
        mute_btn.setToolTip("Mute track")
        controls_layout.addWidget(mute_btn)

        controls_layout.addStretch()
        header_layout.addLayout(controls_layout)

        header.setLayout(header_layout)
        layout.addWidget(header)

        # Track content area (for clips)
        content = QFrame()
        content.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: none;
            }
        """)
        layout.addWidget(content, 1)

        track.setLayout(layout)
        return track

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

    def export_video(self):
        """Export video - Placeholder"""
        self.status_label.setText("Export dialog - Coming soon")
        QMessageBox.information(self, "Export", "Export functionality will be added next!")
        logger.info("Export clicked")

    def import_media(self):
        """Import media - Placeholder"""
        self.status_label.setText("Import media - Coming soon")
        QMessageBox.information(self, "Import", "Import functionality will be added next!")
        logger.info("Import media clicked")

    def toggle_playback(self):
        """Toggle play/pause - Placeholder"""
        if self.play_btn.text() == "▶":
            self.play_btn.setText("⏸")
            self.status_label.setText("Playing...")
        else:
            self.play_btn.setText("▶")
            self.status_label.setText("Paused")

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

    def close_editor(self):
        """Close editor"""
        if self.back_callback:
            self.back_callback()
        else:
            self.close()
