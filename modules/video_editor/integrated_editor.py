"""
modules/video_editor/integrated_editor.py
Integrated Video Editor - Complete redesigned interface
Combines: Enhanced Media Library, Dual Preview, Control Panel, Minimal Timeline
"""

import os
from pathlib import Path

import numpy as np

try:
    import cv2  # type: ignore
except ImportError:  # pragma: no cover - environments without OpenCV
    cv2 = None

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSplitter, QFrame, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QFont

from modules.logging.logger import get_logger
from modules.video_editor.media_library_enhanced import EnhancedMediaLibrary, MediaItem
from modules.video_editor.dual_preview_widget import DualPreviewWidget
from modules.video_editor.unified_control_panel import UnifiedControlPanel
from modules.video_editor.preset_manager import PresetManager
from modules.video_editor.effects import EffectManager

from PyQt5.QtCore import Qt, QFileInfo
from PyQt5.QtWidgets import QApplication, QFileDialog
from PyQt5.QtGui import QPixmap

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
        self.effect_manager = EffectManager(cv2)

        self.init_ui()
        self.setup_video_player()
        self.setup_dual_controls()
        
        logger.info("Integrated Video Editor initialized")

    def setup_video_player(self):
        """Setup integrated video player with error handling"""
        try:
            print("DEBUG: Setting up video player...")
            
            # Import the fixed video player
            from modules.video_editor.custom_video_player import IntegratedVideoPlayer
            
            # Create independent players for BEFORE and AFTER panels
            self.before_player = IntegratedVideoPlayer(preview_role="before")
            self.after_player = IntegratedVideoPlayer(preview_role="after")

            print("DEBUG: Video player instances created (before & after)")

            # Connect BEFORE player signals
            self.before_player.frame_ready.connect(self._on_before_frame_signal)
            self.before_player.position_changed.connect(self.on_before_position_changed)
            self.before_player.duration_changed.connect(self.on_before_duration_changed)
            self.before_player.state_changed.connect(self.on_before_state_changed)

            # Connect AFTER player signals
            self.after_player.frame_ready.connect(self._on_after_frame_signal)
            self.after_player.position_changed.connect(self.on_after_position_changed)
            self.after_player.duration_changed.connect(self.on_after_duration_changed)
            self.after_player.state_changed.connect(self.on_after_state_changed)

            print("✅ Integrated video players setup completed")
            
        except Exception as e:
            print(f"❌ Error setting up video player: {str(e)}")
            import traceback
            traceback.print_exc()
            # Set video_player to None to avoid attribute errors
            self.before_player = None
            self.after_player = None

    def setup_dual_controls(self):
        """Wire up dual control panels after UI creation."""
        if hasattr(self, "control_panel"):
            # Using legacy unified control panel; skip dual wiring
            return
        try:
            if not hasattr(self, 'dual_controls'):
                from modules.video_editor.dual_control_panel import DualControlPanel
                self.dual_controls = DualControlPanel()

            controls = self.dual_controls

            # BEFORE controls
            controls.before_controls.play_clicked.connect(self.on_before_play_clicked)
            controls.before_controls.pause_clicked.connect(self.on_before_pause_clicked)
            controls.before_controls.stop_clicked.connect(self.on_before_stop_clicked)
            controls.before_controls.scrubber_moved.connect(self.on_before_scrubber_moved)

            # AFTER controls  
            controls.after_controls.play_clicked.connect(self.on_after_play_clicked)
            controls.after_controls.pause_clicked.connect(self.on_after_pause_clicked)
            controls.after_controls.stop_clicked.connect(self.on_after_stop_clicked)
            controls.after_controls.scrubber_moved.connect(self.on_after_scrubber_moved)

            print("DEBUG: Dual control panels connected")

        except Exception as e:
            print(f"DEBUG: Error setting up dual controls: {str(e)}")
            import traceback
            traceback.print_exc()

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
        self.media_library.effect_requested.connect(self.on_library_effect_requested)
        self.media_library.setMinimumWidth(250)
        self.media_library.setMaximumWidth(450)
        content_splitter.addWidget(self.media_library)

        # CENTER PANEL - Preview + Dual Control Panel
        center_panel = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # Dual Preview Windows
        self.dual_preview = DualPreviewWidget()
        self.dual_preview.playback_state_changed.connect(self.on_playback_state_changed)
        self.dual_preview.position_changed.connect(self.on_position_changed)
        center_layout.addWidget(self.dual_preview, 1)

        # DUAL Control Panel (NEW - Replaces UnifiedControlPanel)
        try:
            from modules.video_editor.dual_control_panel import DualControlPanel
            self.dual_controls = DualControlPanel()
            center_layout.addWidget(self.dual_controls)

        except ImportError:
            # Fallback to old control panel
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

    def debug_video_player_state(self):
        """Debug video player state"""
        try:
            for label, player in (
                ("BEFORE", getattr(self, 'before_player', None)),
                ("AFTER", getattr(self, 'after_player', None)),
            ):
                if player:
                    print(f"DEBUG: {label} Player State: {player.get_state()}")
                    print(f"DEBUG: {label} Duration: {player.get_duration()}")
                    print(f"DEBUG: {label} Position: {player.get_position()}")
                else:
                    print(f"DEBUG: {label} player not available")
        except Exception as e:
            print(f"DEBUG: Error checking video player state: {str(e)}")

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
        try:
            print("DEBUG: import_media() called")
            
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Import Media Files", 
                "",
                "Video Files (*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.m4v)"
            )
            
            print(f"DEBUG: Selected {len(files)} files")
            
            if not files:
                return
                
            successful_imports = 0
            
            for file_path in files:
                print(f"DEBUG: Processing {file_path}")
                
                # Check if file already exists
                existing_files = [item.file_path for item in self.media_library.media_items]
                if file_path in existing_files:
                    print(f"DEBUG: File already exists - {file_path}")
                    continue
                    
                # Create media item
                media_item = self.create_media_item(file_path)
                if media_item:
                    print(f"DEBUG: Adding to library - {media_item.file_name}")
                    self.media_library.add_media_item(media_item)
                    successful_imports += 1
                    print(f"DEBUG: Successfully added - {media_item.file_name}")
                else:
                    print(f"DEBUG: Failed to create MediaItem for {file_path}")
                    
            print(f"DEBUG: Import completed. {successful_imports} files imported")
            
            # Force UI update
            if successful_imports > 0:
                print("DEBUG: Forcing UI update...")
                QApplication.processEvents()
                
            # Auto-load first video
            if successful_imports > 0 and not self.current_video_path:
                first_item = self.media_library.media_items[0]
                print(f"DEBUG: Auto-loading first video: {first_item.file_path}")
                self.load_video(first_item.file_path)
                
        except Exception as e:
            print(f"DEBUG: Error in import_media: {str(e)}")
            import traceback
            traceback.print_exc()

    def get_video_info(self, file_path: str) -> dict:
        """Temporary video info function - replace with actual implementation"""
        try:
            print(f"DEBUG: Getting video info for {file_path}")
            
            # Basic file info
            file_info = QFileInfo(file_path)
            file_size = file_info.size()
            
            # Temporary dummy data - replace with actual video analysis
            video_info = {
                'duration': 60.0,  # 60 seconds dummy
                'width': 1920,
                'height': 1080, 
                'fps': 30.0,
                'file_size': file_size
            }
            
            print(f"DEBUG: Video info: {video_info}")
            return video_info
            
        except Exception as e:
            print(f"DEBUG: Error in get_video_info: {str(e)}")
            return {
                'duration': 0,
                'width': 0,
                'height': 0,
                'fps': 0,
                'file_size': 0
            }

    def generate_thumbnail(self, file_path: str, time_sec: int = 5) -> QPixmap:
        """Generate a thumbnail preview for imported media."""
        suffix = Path(file_path).suffix.lower()
        try:
            print(f"DEBUG: Generating thumbnail for {file_path}")

            # Directly load image thumbnails
            if suffix in IMAGE_FORMATS:
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    print("DEBUG: Loaded thumbnail from image file")
                    return pixmap

            # Extract a frame from video using OpenCV (if available)
            if suffix in VIDEO_FORMATS:
                if cv2 is None:
                    print("DEBUG: OpenCV not available; falling back to placeholder thumbnail")
                else:
                    capture = cv2.VideoCapture(file_path)
                    if capture.isOpened():
                        try:
                            fps = capture.get(cv2.CAP_PROP_FPS) or 0
                            total_frames = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                            target_frame = int(min(time_sec * fps, max(total_frames - 1, 0))) if fps else 0
                            capture.set(cv2.CAP_PROP_POS_FRAMES, max(target_frame, 0))

                            success, frame = capture.read()
                            if not success or frame is None:
                                print("DEBUG: Primary frame grab failed; retrying from start")
                                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                success, frame = capture.read()

                            if success and frame is not None:
                                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                height, width, _ = frame.shape
                                bytes_per_line = width * 3
                                image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).copy()
                                pixmap = QPixmap.fromImage(image)
                                if not pixmap.isNull():
                                    print("DEBUG: Thumbnail generated from video frame")
                                    return pixmap
                            else:
                                print("DEBUG: Unable to read video frame for thumbnail")
                        finally:
                            capture.release()
                    else:
                        capture.release()
                        print("DEBUG: Video capture failed to open for thumbnail generation")

            # Fallback placeholder thumbnail
            from PyQt5.QtGui import QPainter, QColor

            pixmap = QPixmap(160, 120)
            pixmap.fill(QColor(24, 24, 24))

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)

            # Accent block for better visual hierarchy
            accent_rect = pixmap.rect().adjusted(12, 12, -12, -40)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 188, 212))
            painter.drawRoundedRect(accent_rect, 8, 8)

            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(accent_rect, Qt.AlignCenter, suffix.replace(".", "").upper() or "MEDIA")

            painter.setPen(QColor(180, 180, 180))
            helper_font = QFont(font)
            helper_font.setPointSize(8)
            helper_font.setBold(False)
            painter.setFont(helper_font)
            painter.drawText(pixmap.rect().adjusted(12, 0, -12, -12), Qt.AlignBottom | Qt.AlignHCenter, "Preview N/A")

            painter.end()
            print("DEBUG: Fallback thumbnail generated")
            return pixmap

        except Exception as e:
            print(f"DEBUG: Error in generate_thumbnail: {str(e)}")
            return QPixmap()

    def create_media_item(self, file_path: str):
        try:
            print(f"DEBUG: Creating MediaItem for {file_path}")
            
            file_info = QFileInfo(file_path)
            if not file_info.exists():
                print(f"DEBUG: File doesn't exist - {file_path}")
                return None
                
            # Use temporary functions
            video_info = self.get_video_info(file_path)  # Self use karein
            thumbnail = self.generate_thumbnail(file_path)  # Self use karein
            
            # MediaItem banayein
            from modules.video_editor.media_library_enhanced import MediaItem
            
            media_item = MediaItem(
                file_path=file_path,
                file_name=file_info.fileName(),
                file_type=file_info.suffix().lower(),
                file_size=file_info.size(),
                duration=video_info.get('duration', 0),
                width=video_info.get('width', 0),
                height=video_info.get('height', 0),
                fps=video_info.get('fps', 0),
                thumbnail=thumbnail,
                is_zoomed=False,
                is_blurred=False,
                is_ai_enhanced=False,
                speed_factor=1.0,
                is_processing=False,
                is_new=True
            )
            
            print(f"DEBUG: MediaItem created successfully: {media_item.file_name}")
            return media_item
            
        except Exception as e:
            print(f"DEBUG: Error in create_media_item: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

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

    def load_video(self, video_path: str):
        """Load video in both preview windows AND video player"""
        try:
            print(f"DEBUG: Loading video: {video_path}")
            
            if not os.path.exists(video_path):
                print(f"DEBUG: Video file not found: {video_path}")
                return
            
            self.current_video_path = video_path

            speed_factor = self._current_speed_factor()
            
            # 1. Load in dual preview (UI update)
            self.dual_preview.load_video(video_path)
            
            # 2. Load BEFORE player
            before_success = False
            if hasattr(self, 'before_player') and self.before_player:
                before_success = self.before_player.load_video(video_path)
                if before_success:
                    self.before_player.set_speed(1.0)
                    self.before_player.seek(0)
                    before_duration = self.before_player.get_duration()
                    self._update_panel_duration(before_duration, getattr(self.dual_controls, 'before_controls', None), True)
                else:
                    print("DEBUG: Failed to load video in BEFORE player")

            # 3. Load AFTER player
            after_success = False
            if hasattr(self, 'after_player') and self.after_player:
                after_success = self.after_player.load_video(video_path)
                if after_success:
                    self.after_player.set_speed(speed_factor)
                    self.after_player.seek(0)
                    after_duration = self.after_player.get_duration()
                    self._update_panel_duration(after_duration, getattr(self.dual_controls, 'after_controls', None), False)
                else:
                    print("DEBUG: Failed to load video in AFTER player")

            if not before_success or not after_success:
                self.show_error_message("One of the preview players failed to load the video.")

            self._apply_current_speed_to_players()
            self._sync_after_speed_ui()
            self._update_preview_effect_badges()
            self._refresh_after_preview()

            logger.info(f"Video loaded successfully: {os.path.basename(video_path)}")
            
        except Exception as e:
            print(f"DEBUG: Error in load_video: {str(e)}")
            import traceback
            traceback.print_exc()

    def _on_before_frame_signal(self, frame_data, _is_before):
        self._display_frame(frame_data, True)

    def _on_after_frame_signal(self, frame_data, _is_before):
        self._display_frame(frame_data, False)

    def _display_frame(self, frame_data, is_before):
        """Render a frame into the appropriate preview panel."""
        try:
            labels = None
            processed_frame = frame_data
            if not is_before:
                result = self.effect_manager.apply_after_effects(frame_data)
                processed_frame = result.frame
                labels = None
                if result.metadata:
                    labels = result.metadata.get("labels")
                if isinstance(labels, str):
                    labels = [labels]
                if not labels:
                    labels = self.effect_manager.active_labels()

            frame_pixmap = self._frame_data_to_pixmap(processed_frame)
            self.dual_preview.show_video_frame(frame_pixmap, is_before)

            if not is_before:
                self._update_preview_effect_badges(labels)
        except Exception as e:
            print(f"DEBUG: Error displaying video frame: {str(e)}")

    def _frame_data_to_pixmap(self, frame_data):
        """Convert numpy frame data to QPixmap."""
        frame_pixmap = QPixmap()

        if isinstance(frame_data, np.ndarray) and frame_data.size:
            height, width = frame_data.shape[:2]
            channels = frame_data.shape[2] if frame_data.ndim == 3 else 1

            if channels == 3:
                bytes_per_line = channels * width
                q_image = QImage(frame_data.data, width, height, bytes_per_line, QImage.Format_RGB888)
            elif channels == 4:
                bytes_per_line = channels * width
                image_format = QImage.Format_RGBA8888 if hasattr(QImage, "Format_RGBA8888") else QImage.Format_RGB32
                q_image = QImage(frame_data.data, width, height, bytes_per_line, image_format)
            else:
                q_image = QImage()

            if not q_image.isNull():
                frame_pixmap = QPixmap.fromImage(q_image.copy())

        return frame_pixmap

    def on_library_effect_requested(self, effect_payload):
        """Handle effect requests originating from the media library header buttons."""
        try:
            if not effect_payload:
                return

            effect_type = effect_payload.get("type")
            handled = False

            if effect_type == "zoom":
                mode = effect_payload.get("mode") or "preset"
                percent = float(effect_payload.get("percent", 100.0))
                label = effect_payload.get("display")

                if mode == "reset":
                    self.effect_manager.reset_zoom()
                else:
                    self.effect_manager.set_zoom_percent(percent, mode=mode, label=label)

                logger.info("Zoom effect applied: %.2f%%", percent)
                handled = True

            elif effect_type == "blur":
                mode = effect_payload.get("mode") or "preset"
                intensity = float(effect_payload.get("intensity", 0.0))
                label = effect_payload.get("display")
                target = effect_payload.get("target")

                if mode == "reset":
                    self.effect_manager.reset_blur()
                else:
                    self.effect_manager.set_blur_intensity(intensity, label=label, target=target)

                logger.info("Blur effect applied: %.2f", intensity)
                handled = True
            elif effect_type == "speed":
                mode = effect_payload.get("mode") or "preset"
                factor = float(effect_payload.get("factor", 1.0))
                label = effect_payload.get("display")

                if mode == "reset":
                    self.effect_manager.reset_speed()
                else:
                    self.effect_manager.set_speed_factor(factor, label=label)

                self._apply_current_speed_to_players()
                self._sync_after_speed_ui()
                logger.info("Playback speed applied: %.2fx", factor)
                handled = True
            else:
                return

            if handled:
                self._update_preview_effect_badges()
                self._refresh_after_preview()

        except Exception as exc:
            logger.error(f"Failed to handle effect request: {exc}")

    def _update_preview_effect_badges(self, labels=None):
        """Sync effect badges on the AFTER preview."""
        try:
            if not hasattr(self, "dual_preview"):
                return

            self.dual_preview.clear_effects()

            if isinstance(labels, str):
                labels = [labels]

            active = labels if labels is not None else self.effect_manager.active_labels()
            for label in active or []:
                self.dual_preview.add_effect_to_preview(label)

        except Exception as exc:
            print(f"DEBUG: Failed to update effect badges: {exc}")

    def _refresh_after_preview(self):
        """Force the AFTER preview to redraw the current frame with new effects."""
        try:
            after_player = getattr(self, "after_player", None)
            if after_player and hasattr(after_player, "thread"):
                after_player.thread._emit_current_frame()
        except Exception as exc:
            print(f"DEBUG: Unable to refresh after preview: {exc}")

    def on_before_position_changed(self, position_seconds):
        """Update BEFORE panel when its playback position changes."""
        self._update_panel_position(
            position_seconds=position_seconds,
            player=getattr(self, 'before_player', None),
            control=getattr(self.dual_controls, 'before_controls', None),
            is_before=True,
        )

    def on_after_position_changed(self, position_seconds):
        """Update AFTER panel when its playback position changes."""
        self._update_panel_position(
            position_seconds=position_seconds,
            player=getattr(self, 'after_player', None),
            control=getattr(self.dual_controls, 'after_controls', None),
            is_before=False,
        )

    def _update_panel_position(self, position_seconds, player, control, is_before):
        try:
            if not player:
                return

            duration = player.get_duration()
            effective_duration, effective_position = self._effective_timing(duration, position_seconds, is_before)

            if duration > 0 and control:
                scrubber_position = int((position_seconds / duration) * 1000)
                control.set_position(scrubber_position)

            self.dual_preview.update_time_for_panel(is_before, effective_position, effective_duration)
        except Exception as e:
            print(f"DEBUG: Error updating position for panel ({'before' if is_before else 'after'}): {str(e)}")

    def on_before_duration_changed(self, duration_seconds):
        """Update BEFORE panel when duration is known."""
        self._update_panel_duration(
            duration_seconds,
            control=getattr(self.dual_controls, 'before_controls', None),
            is_before=True,
        )

    def on_after_duration_changed(self, duration_seconds):
        """Update AFTER panel when duration is known."""
        self._update_panel_duration(
            duration_seconds,
            control=getattr(self.dual_controls, 'after_controls', None),
            is_before=False,
        )

    def _update_panel_duration(self, duration_seconds, control, is_before):
        try:
            effective_duration, _ = self._effective_timing(duration_seconds, 0.0, is_before)

            if control:
                control.set_duration(effective_duration)
            self.dual_preview.update_time_for_panel(is_before, 0, effective_duration)
        except Exception as e:
            print(f"DEBUG: Error updating duration for panel ({'before' if is_before else 'after'}): {str(e)}")

    def on_before_state_changed(self, state):
        self._update_panel_state(state, getattr(self.dual_controls, 'before_controls', None), "before")

    def on_after_state_changed(self, state):
        self._update_panel_state(state, getattr(self.dual_controls, 'after_controls', None), "after")

    def _update_panel_state(self, state, control_panel, label):
        """Update panel buttons without re-triggering signals."""
        try:
            if not control_panel:
                return

            print(f"DEBUG: {label.upper()} panel state -> {state}")

            if state == "playing":
                control_panel.set_playing_state(update_ui_only=True)
            elif state == "paused":
                control_panel.set_paused_state(update_ui_only=True)
            elif state == "stopped":
                control_panel.set_stopped_state(update_ui_only=True)
        except Exception as e:
            print(f"DEBUG: Error handling state change for {label}: {str(e)}")

    def _seek_player(self, player, scrubber_position, label):
        """Seek the given player based on a 0-1000 scrubber value."""
        try:
            if not player or not player.has_video():
                return

            duration = player.get_duration()
            if duration <= 0:
                return

            target_time = (scrubber_position / 1000.0) * duration
            player.seek(target_time)
            print(f"DEBUG: {label} seek -> {target_time:.2f}s ({scrubber_position}/1000)")

        except Exception as e:
            print(f"DEBUG: Error seeking video for {label}: {str(e)}")

    # Dual control panel methods
    def _current_speed_factor(self) -> float:
        """Return the active speed factor while guarding against invalid values."""
        speed = 1.0
        try:
            if hasattr(self, "effect_manager"):
                speed = float(self.effect_manager.speed_factor())
        except Exception as exc:
            print(f"DEBUG: Unable to read speed factor: {exc}")
            speed = 1.0
        return max(speed, 0.1)

    def _effective_timing(self, duration_seconds, position_seconds, is_before):
        """Adjust duration/position to reflect the speed effect on AFTER preview."""
        if is_before:
            return duration_seconds, position_seconds

        speed = self._current_speed_factor()
        if speed <= 0.0:
            return duration_seconds, position_seconds

        return duration_seconds / speed, position_seconds / speed

    def _apply_current_speed_to_players(self) -> None:
        """Sync playback speed effect with both preview players."""
        speed = self._current_speed_factor()

        before_player = getattr(self, "before_player", None)
        after_player = getattr(self, "after_player", None)

        try:
            if before_player:
                before_player.set_speed(1.0)
        except Exception as exc:
            print(f"DEBUG: Failed to reset BEFORE player speed: {exc}")

        try:
            if after_player:
                after_player.set_speed(speed)
        except Exception as exc:
            print(f"DEBUG: Failed to apply AFTER player speed: {exc}")

    def _sync_after_speed_ui(self) -> None:
        """Refresh AFTER preview controls/timecodes to match current speed."""
        try:
            after_player = getattr(self, "after_player", None)
            if not after_player:
                return

            controls = getattr(self, "dual_controls", None)
            control = getattr(controls, "after_controls", None) if controls else None
            duration = after_player.get_duration() if hasattr(after_player, "get_duration") else 0.0
            position = after_player.get_position() if hasattr(after_player, "get_position") else 0.0

            self._update_panel_duration(duration, control, is_before=False)
            self._update_panel_position(position, after_player, control, is_before=False)
        except Exception as exc:
            print(f"DEBUG: Failed to sync AFTER speed UI: {exc}")

    def on_before_play_clicked(self):
        """Handle before window play - FIXED"""
        try:
            print("DEBUG: BEFORE Controls -> play clicked")
            self.debug_video_player_state()
            
            player = getattr(self, 'before_player', None)
            control = getattr(self.dual_controls, 'before_controls', None)

            if player and player.has_video():
                player.play()
                print("DEBUG: BEFORE player play command sent")
                if control:
                    control.set_playing_state(update_ui_only=True)
            else:
                print("DEBUG: BEFORE player not ready")
                
        except Exception as e:
            print(f"DEBUG: Error in on_before_play_clicked: {str(e)}")
            import traceback
            traceback.print_exc()

    def on_before_pause_clicked(self):
        """Handle before window pause - FIXED"""
        try:
            print("DEBUG: BEFORE Controls -> pause clicked")
            
            player = getattr(self, 'before_player', None)
            control = getattr(self.dual_controls, 'before_controls', None)

            if player and player.has_video():
                player.pause()
                print("DEBUG: BEFORE player pause command sent")
                if control:
                    control.set_paused_state(update_ui_only=True)
            else:
                print("DEBUG: BEFORE player not available")
                
        except Exception as e:
            print(f"DEBUG: Error in on_before_pause_clicked: {str(e)}")

    def on_before_stop_clicked(self):
        """Handle before window stop - FIXED"""
        try:
            print("DEBUG: BEFORE Controls -> stop clicked")
            
            player = getattr(self, 'before_player', None)
            control = getattr(self.dual_controls, 'before_controls', None)

            if player and player.has_video():
                player.stop()
                print("DEBUG: BEFORE player stop command sent")
                if control:
                    control.set_stopped_state(update_ui_only=True)
            else:
                print("DEBUG: BEFORE player not available")
                
        except Exception as e:
            print(f"DEBUG: Error in on_before_stop_clicked: {str(e)}")     
    
    def on_before_scrubber_moved(self, position):
        """Handle before window scrubber movement"""
        self._seek_player(getattr(self, 'before_player', None), position, "before")

    def on_after_play_clicked(self):
        """Handle after window play - FIXED"""
        try:
            print("DEBUG: AFTER Controls -> play clicked")
            self.debug_video_player_state()
            
            player = getattr(self, 'after_player', None)
            control = getattr(self.dual_controls, 'after_controls', None)

            if player and player.has_video():
                player.play()
                print("DEBUG: AFTER player play command sent")
                if control:
                    control.set_playing_state(update_ui_only=True)
            else:
                print("DEBUG: AFTER player not ready")
                
        except Exception as e:
            print(f"DEBUG: Error in on_after_play_clicked: {str(e)}")

    def on_after_pause_clicked(self):
        """Handle after window pause - FIXED"""
        try:
            print("DEBUG: AFTER Controls -> pause clicked")
            
            player = getattr(self, 'after_player', None)
            control = getattr(self.dual_controls, 'after_controls', None)

            if player and player.has_video():
                player.pause()
                print("DEBUG: AFTER player pause command sent")
                if control:
                    control.set_paused_state(update_ui_only=True)
            else:
                print("DEBUG: AFTER player not available")
                
        except Exception as e:
            print(f"DEBUG: Error in on_after_pause_clicked: {str(e)}")

    def on_after_stop_clicked(self):
        """Handle after window stop - FIXED"""
        try:
            print("DEBUG: AFTER Controls -> stop clicked")
            
            player = getattr(self, 'after_player', None)
            control = getattr(self.dual_controls, 'after_controls', None)

            if player and player.has_video():
                player.stop()
                print("DEBUG: AFTER player stop command sent")
                if control:
                    control.set_stopped_state(update_ui_only=True)
            else:
                print("DEBUG: AFTER player not available")
                
        except Exception as e:
            print(f"DEBUG: Error in on_after_stop_clicked: {str(e)}")  
    def on_after_scrubber_moved(self, position):
        """Handle after window scrubber movement"""
        self._seek_player(getattr(self, 'after_player', None), position, "after")

    def show_error_message(self, message):
        """Show error message to user"""
        # You can implement a proper error dialog here
        print(f"ERROR: {message}")

    def cleanup(self):
        """Clean up resources"""
        try:
            for player in (getattr(self, 'before_player', None), getattr(self, 'after_player', None)):
                if player:
                    player.cleanup()
        except Exception as e:
            print(f"DEBUG: Error during cleanup: {str(e)}")

    def on_playback_state_changed(self, is_playing):
        """Handle playback state change from preview"""
        logger.debug(f"Playback state: {'Playing' if is_playing else 'Paused'}")

    def on_position_changed(self, position):
        """Handle position change from preview"""
        if hasattr(self, 'control_panel'):
            self.control_panel.set_position(position)

    def on_play_clicked(self):
        """Handle play button"""
        logger.info("Play clicked")
        for player in (getattr(self, 'before_player', None), getattr(self, 'after_player', None)):
            if player and player.has_video():
                player.play()

    def on_pause_clicked(self):
        """Handle pause button"""
        logger.info("Pause clicked")
        for player in (getattr(self, 'before_player', None), getattr(self, 'after_player', None)):
            if player and player.has_video():
                player.pause()

    def on_stop_clicked(self):
        """Handle stop button"""
        logger.info("Stop clicked")
        for player in (getattr(self, 'before_player', None), getattr(self, 'after_player', None)):
            if player and player.has_video():
                player.stop()
        if hasattr(self, 'control_panel'):
            self.control_panel.reset()

    def on_skip_backward(self):
        """Skip backward 5 seconds"""
        logger.info("Skip backward")
        # TODO: Skip playback

    def on_skip_forward(self):
        """Skip forward 5 seconds"""
        logger.info("Skip forward")
        # TODO: Skip playback

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
        """Open bulk processing dialog with folder mapping"""
        try:
            from modules.video_editor.editor_mapping_dialog import BulkProcessingDialog
            from modules.video_editor.editor_progress_dialog import EditorProgressDialog

            # Open configuration dialog
            config_dialog = BulkProcessingDialog(self, self.preset_manager)

            # Connect signal for when processing should start
            def on_start_processing(config):
                logger.info("📨 Signal handler called - on_start_processing")
                logger.info(f"   Received config with {len(config.get('videos', []))} videos")
                logger.info("   Creating EditorProgressDialog...")

                # Open progress dialog
                progress_dialog = EditorProgressDialog(config, self)
                logger.info("   EditorProgressDialog created, showing...")
                progress_dialog.exec_()
                logger.info("   EditorProgressDialog closed")

            config_dialog.start_processing.connect(on_start_processing)
            logger.info("✅ Signal handler connected")

            # Show dialog
            config_dialog.exec_()

            logger.info("Bulk processing dialog closed")

        except Exception as e:
            logger.error(f"Failed to open bulk processing: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open bulk processing dialog:\n{str(e)}"
            )

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
        self.cleanup()
        if self.back_callback:
            self.back_callback()
        else:
            self.close()
