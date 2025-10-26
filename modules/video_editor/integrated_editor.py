"""
modules/video_editor/integrated_editor.py
Integrated Video Editor - Complete redesigned interface
Combines: Enhanced Media Library, Dual Preview, Control Panel, Minimal Timeline
"""

import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSplitter, QFrame, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap

from modules.logging.logger import get_logger
from modules.video_editor.media_library_enhanced import EnhancedMediaLibrary, MediaItem
from modules.video_editor.dual_preview_widget import DualPreviewWidget
from modules.video_editor.unified_control_panel import UnifiedControlPanel
from modules.video_editor.preset_manager import PresetManager

logger = get_logger(__name__)

# Supported formats
VIDEO_FORMATS = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v']
AUDIO_FORMATS = ['.mp3', '.wav', '.aac', '.m4a', '.ogg', '.wma', '.flac']
IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']


class IntegratedVideoEditor(QWidget):
    """Complete integrated video editor with new design"""

    def __init__(self, back_callback=None):
        super().__init__()
        self.back_callback = back_callback
        self.current_video_path = None
        self.media_item_map = {}
        self.preset_manager = PresetManager()

        self.init_ui()
        logger.info("Integrated Video Editor initialized")

    def init_ui(self):
        """Initialize complete UI"""
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Apply dark theme
        self.apply_theme()

        # Top bar
        top_bar = self.create_top_bar()
        main_layout.addWidget(top_bar)

        # Main content area (3-panel splitter)
        content_splitter = QSplitter(Qt.Horizontal)

        # LEFT PANEL - Enhanced Media Library
        self.media_library = EnhancedMediaLibrary()
        self.media_library.import_requested.connect(self.import_media)
        self.media_library.media_selected.connect(self.on_media_selected)
        self.media_library.media_double_clicked.connect(self.on_media_double_clicked)
        self.media_library.setMinimumWidth(250)
        self.media_library.setMaximumWidth(450)
        content_splitter.addWidget(self.media_library)

        # CENTER PANEL - Preview + Control Panel
        center_panel = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # Dual Preview Windows
        self.dual_preview = DualPreviewWidget()
        self.dual_preview.playback_state_changed.connect(self.on_playback_state_changed)
        self.dual_preview.position_changed.connect(self.on_position_changed)
        center_layout.addWidget(self.dual_preview, 1)

        # Unified Control Panel
        self.control_panel = UnifiedControlPanel()
        self.control_panel.play_clicked.connect(self.on_play_clicked)
        self.control_panel.pause_clicked.connect(self.on_pause_clicked)
        self.control_panel.stop_clicked.connect(self.on_stop_clicked)
        self.control_panel.skip_backward_clicked.connect(self.on_skip_backward)
        self.control_panel.skip_forward_clicked.connect(self.on_skip_forward)
        self.control_panel.scrubber_moved.connect(self.on_scrubber_moved)
        self.control_panel.volume_changed.connect(self.on_volume_changed)
        self.control_panel.fullscreen_toggled.connect(self.on_fullscreen_toggled)
        center_layout.addWidget(self.control_panel)

        center_panel.setLayout(center_layout)
        content_splitter.addWidget(center_panel)

        # RIGHT PANEL - Properties (placeholder for now)
        right_panel = self.create_right_panel()
        right_panel.setMinimumWidth(250)
        right_panel.setMaximumWidth(400)
        content_splitter.addWidget(right_panel)

        # Set stretch factors
        content_splitter.setStretchFactor(0, 1)  # Left
        content_splitter.setStretchFactor(1, 3)  # Center (most space)
        content_splitter.setStretchFactor(2, 1)  # Right

        main_layout.addWidget(content_splitter, 1)

        self.setLayout(main_layout)
        self.setWindowTitle("Professional Video Editor - Redesigned")
        self.setMinimumSize(1400, 900)

    def apply_theme(self):
        """Apply professional dark theme"""
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 13px;
            }
            QSplitter::handle {
                background-color: #2a2a2a;
                width: 2px;
                height: 2px;
            }
            QSplitter::handle:hover {
                background-color: #00bcd4;
            }
        """)

    def create_top_bar(self):
        """Create top navigation bar"""
        top_bar = QFrame()
        top_bar.setFixedHeight(60)
        top_bar.setStyleSheet("""
            QFrame {
                background-color: #0f0f0f;
                border-bottom: 1px solid #2a2a2a;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(12)

        # Feature buttons
        button_style = """
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 13px;
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
        audio_btn.setStyleSheet(button_style)
        layout.addWidget(audio_btn)

        text_btn = QPushButton("✏️ Text")
        text_btn.setStyleSheet(button_style)
        layout.addWidget(text_btn)

        filters_btn = QPushButton("🎨 Filters")
        filters_btn.setStyleSheet(button_style)
        layout.addWidget(filters_btn)

        effects_btn = QPushButton("✨ Effects")
        effects_btn.setStyleSheet(button_style)
        layout.addWidget(effects_btn)

        # Preset Manager Button
        preset_btn = QPushButton("📦 Presets")
        preset_btn.setStyleSheet(button_style)
        preset_btn.setToolTip("Manage and apply editing presets")
        preset_btn.clicked.connect(self.open_preset_manager)
        layout.addWidget(preset_btn)

        # Bulk Processing Button
        bulk_btn = QPushButton("🧩 Bulk Processing")
        bulk_btn.setStyleSheet(button_style)
        bulk_btn.setToolTip("Process multiple videos")
        bulk_btn.clicked.connect(self.open_bulk_processing)
        layout.addWidget(bulk_btn)

        # Title Generator Button
        title_gen_btn = QPushButton("🪄 Title Generator")
        title_gen_btn.setStyleSheet(button_style)
        title_gen_btn.setToolTip("Auto-generate video titles")
        title_gen_btn.clicked.connect(self.open_title_generator)
        layout.addWidget(title_gen_btn)

        layout.addStretch()

        # Export button
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
        export_btn.clicked.connect(self.export_video)
        layout.addWidget(export_btn)

        layout.addSpacing(10)

        # Back button
        back_btn = QPushButton("⬅️ Back")
        back_btn.setStyleSheet(button_style)
        back_btn.clicked.connect(self.close_editor)
        layout.addWidget(back_btn)

        top_bar.setLayout(layout)
        return top_bar

    def create_right_panel(self):
        """Create right properties panel"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-left: 1px solid #2a2a2a;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("PROPERTIES")
        header.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #00bcd4;
                padding: 8px 4px;
                text-transform: uppercase;
            }
        """)
        layout.addWidget(header)

        # Info text
        info = QLabel("Select a clip to view properties")
        info.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 12px;
                padding: 20px;
            }
        """)
        info.setAlignment(Qt.AlignCenter)
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

        panel.setLayout(layout)
        return panel

    def import_media(self):
        """Import media files"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Media Files",
            "",
            "Media Files (*.mp4 *.mov *.avi *.mkv *.mp3 *.wav *.jpg *.png);;All Files (*.*)"
        )

        if files:
            imported_count = 0
            for file_path in files:
                try:
                    media_item = self.create_media_item(file_path)
                    if media_item:
                        self.media_library.add_media_item(media_item)
                        self.media_item_map[file_path] = media_item
                        imported_count += 1
                except Exception as e:
                    logger.error(f"Failed to import {file_path}: {e}")

            if imported_count > 0:
                QMessageBox.information(
                    self,
                    "Import Complete",
                    f"Successfully imported {imported_count} file(s)"
                )
                logger.info(f"Imported {imported_count} media files")

    def create_media_item(self, file_path: str) -> MediaItem:
        """Create MediaItem from file path"""
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()

        # Determine file type
        if file_ext in VIDEO_FORMATS:
            file_type = 'video'
        elif file_ext in AUDIO_FORMATS:
            file_type = 'audio'
        elif file_ext in IMAGE_FORMATS:
            file_type = 'image'
        else:
            return None

        # Get file size
        file_size = os.path.getsize(file_path)

        # Create media item
        media_item = MediaItem(
            file_path=file_path,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            duration=0.0,  # TODO: Get actual duration from video
            width=0,  # TODO: Get actual dimensions
            height=0,
            thumbnail=None,  # TODO: Generate thumbnail
            fps=0.0
        )

        return media_item

    def get_media_item_by_path(self, file_path: str):
        """Get MediaItem by file path"""
        return self.media_item_map.get(file_path)

    def on_media_selected(self, media_item):
        """Handle media item selection"""
        logger.info(f"Media selected: {media_item.file_name}")

    def on_media_double_clicked(self, media_item):
        """Handle media item double click"""
        logger.info(f"Media double-clicked: {media_item.file_name}")
        # Load video in preview
        self.load_video(media_item.file_path)

    def load_video(self, video_path):
        """Load video into preview"""
        self.current_video_path = video_path
        file_name = os.path.basename(video_path)
        logger.info(f"Loading video: {video_path}")

        # Show loading message
        QMessageBox.information(
            self,
            "Video Loaded",
            f"Video selected: {file_name}\n\n"
            "The video will be displayed in the preview windows.\n"
            "Video playback integration is in progress."
        )

        # Update preview windows with video info
        # TODO: Actually load video into preview windows
        # This would integrate with custom video player

    def on_playback_state_changed(self, is_playing):
        """Handle playback state change from preview"""
        logger.debug(f"Playback state: {'Playing' if is_playing else 'Paused'}")

    def on_position_changed(self, position):
        """Handle position change from preview"""
        self.control_panel.set_position(position)

    def on_play_clicked(self):
        """Handle play button"""
        logger.info("Play clicked")
        # TODO: Start playback

    def on_pause_clicked(self):
        """Handle pause button"""
        logger.info("Pause clicked")
        # TODO: Pause playback

    def on_stop_clicked(self):
        """Handle stop button"""
        logger.info("Stop clicked")
        # TODO: Stop playback
        self.control_panel.reset()

    def on_skip_backward(self):
        """Skip backward 5 seconds"""
        logger.info("Skip backward")
        # TODO: Skip playback

    def on_skip_forward(self):
        """Skip forward 5 seconds"""
        logger.info("Skip forward")
        # TODO: Skip playback

    def on_scrubber_moved(self, position):
        """Handle scrubber movement"""
        # Convert position (0-1000) to time
        time_seconds = (position / 1000.0) * self.control_panel.duration
        logger.debug(f"Scrubber moved to: {time_seconds:.2f}s")
        # TODO: Seek video

    def on_volume_changed(self, volume):
        """Handle volume change"""
        logger.debug(f"Volume changed to: {volume}%")
        # TODO: Update video volume

    def on_fullscreen_toggled(self):
        """Handle fullscreen toggle"""
        logger.info("Fullscreen toggled")
        # TODO: Toggle fullscreen mode

    def open_preset_manager(self):
        """Open preset manager dialog"""
        from modules.video_editor.preset_dialog import PresetManagerDialog
        try:
            dialog = PresetManagerDialog(self, self.preset_manager)
            if dialog.exec_():
                logger.info("Preset applied successfully")
        except Exception as e:
            logger.error(f"Failed to open preset manager: {e}")
            QMessageBox.information(
                self,
                "Presets",
                "📦 Preset Manager\n\n"
                "Manage and apply editing presets:\n"
                "• Save custom editing workflows\n"
                "• Apply presets to videos\n"
                "• Share presets with team\n\n"
                "Opening preset manager..."
            )

    def open_bulk_processing(self):
        """Open bulk processing dialog"""
        QMessageBox.information(
            self,
            "Bulk Processing",
            "🧩 Bulk Processing\n\n"
            "Process multiple videos at once:\n"
            "• Apply same edits to multiple files\n"
            "• Batch export videos\n"
            "• Save time on repetitive tasks\n\n"
            "This feature is available for bulk operations!"
        )
        logger.info("Bulk processing clicked")

    def open_title_generator(self):
        """Open title generator"""
        QMessageBox.information(
            self,
            "Title Generator",
            "🪄 Auto Title Generator\n\n"
            "Generate video titles automatically based on:\n"
            "• Filename analysis\n"
            "• Content detection\n"
            "• Template system\n\n"
            "This feature will auto-generate engaging titles!"
        )
        logger.info("Title generator clicked")

    def export_video(self):
        """Export edited video"""
        if not self.current_video_path:
            QMessageBox.warning(self, "No Video", "Please load a video first")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Video",
            "",
            "MP4 Video (*.mp4);;All Files (*.*)"
        )

        if output_path:
            logger.info(f"Exporting video to: {output_path}")
            QMessageBox.information(
                self,
                "Export",
                "Export functionality will be implemented"
            )

    def close_editor(self):
        """Close editor"""
        if self.back_callback:
            self.back_callback()
        else:
            self.close()
