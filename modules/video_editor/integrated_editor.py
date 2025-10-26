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
            
            # Create video player instance
            self.video_player = IntegratedVideoPlayer()
            print("DEBUG: Video player instance created")
            
            # Connect video player signals
            self.video_player.frame_ready.connect(self.on_video_frame_ready)
            self.video_player.position_changed.connect(self.on_video_position_changed)
            self.video_player.duration_changed.connect(self.on_video_duration_changed)
            self.video_player.state_changed.connect(self.on_video_state_changed)
            
            print("✅ Integrated video player setup completed")
            
        except Exception as e:
            print(f"❌ Error setting up video player: {str(e)}")
            import traceback
            traceback.print_exc()
            # Set video_player to None to avoid attribute errors
            self.video_player = None

    def setup_dual_controls(self):
        """Setup dual independent control panels"""
        try:
            from modules.video_editor.dual_control_panel import DualControlPanel
            
            # Create dual control panel
            self.dual_controls = DualControlPanel()
            
            # Connect BEFORE controls
            self.dual_controls.before_controls.play_clicked.connect(
                lambda: self.on_before_play_clicked()
            )
            self.dual_controls.before_controls.pause_clicked.connect(
                lambda: self.on_before_pause_clicked()
            )
            self.dual_controls.before_controls.stop_clicked.connect(
                lambda: self.on_before_stop_clicked()
            )
            self.dual_controls.before_controls.scrubber_moved.connect(
                lambda pos: self.on_before_scrubber_moved(pos)
            )
            
            # Connect AFTER controls  
            self.dual_controls.after_controls.play_clicked.connect(
                lambda: self.on_after_play_clicked()
            )
            self.dual_controls.after_controls.pause_clicked.connect(
                lambda: self.on_after_pause_clicked()
            )
            self.dual_controls.after_controls.stop_clicked.connect(
                lambda: self.on_after_stop_clicked()
            )
            self.dual_controls.after_controls.scrubber_moved.connect(
                lambda pos: self.on_after_scrubber_moved(pos)
            )
            
            print("✅ Dual control panels setup completed")
            
        except Exception as e:
            print(f"❌ Error setting up dual controls: {str(e)}")
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
            
            # Connect dual controls
            self.setup_dual_controls_connections()
            
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
            if hasattr(self, 'video_player') and self.video_player:
                print(f"DEBUG: Video Player State: {self.video_player.get_state()}")
                print(f"DEBUG: Video Duration: {self.video_player.get_duration()}")
                print(f"DEBUG: Video Position: {self.video_player.get_position()}")
            else:
                print("DEBUG: Video player not available")
        except Exception as e:
            print(f"DEBUG: Error checking video player state: {str(e)}")

    def setup_dual_controls_connections(self):
        """Connect dual control panels to video player - FIXED VERSION"""
        try:
            if hasattr(self, 'dual_controls') and hasattr(self, 'video_player'):
                print("DEBUG: Setting up dual controls connections...")
                
                # BEFORE controls - DIRECT CONNECTION
                self.dual_controls.before_controls.play_clicked.connect(
                    self.on_before_play_clicked
                )
                self.dual_controls.before_controls.pause_clicked.connect(
                    self.on_before_pause_clicked
                )
                self.dual_controls.before_controls.stop_clicked.connect(
                    self.on_before_stop_clicked
                )
                self.dual_controls.before_controls.scrubber_moved.connect(
                    self.on_before_scrubber_moved
                )
                
                # AFTER controls - DIRECT CONNECTION  
                self.dual_controls.after_controls.play_clicked.connect(
                    self.on_after_play_clicked
                )
                self.dual_controls.after_controls.pause_clicked.connect(
                    self.on_after_pause_clicked
                )
                self.dual_controls.after_controls.stop_clicked.connect(
                    self.on_after_stop_clicked
                )
                self.dual_controls.after_controls.scrubber_moved.connect(
                    self.on_after_scrubber_moved
                )
                
                print("✅ Dual controls connections setup completed")
                
        except Exception as e:
            print(f"❌ Error setting up dual controls connections: {str(e)}")
            import traceback
            traceback.print_exc()

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
        """Temporary thumbnail generator - replace with actual implementation"""
        try:
            print(f"DEBUG: Generating thumbnail for {file_path}")
            
            # Temporary thumbnail - ek colored box banayein
            from PyQt5.QtGui import QPixmap, QPainter, QColor
            from PyQt5.QtCore import QSize
            
            pixmap = QPixmap(QSize(160, 120))  # Thumbnail size
            pixmap.fill(QColor(70, 70, 70))  # Gray color
            
            # File type icon add karein
            painter = QPainter(pixmap)
            painter.setPen(QColor(255, 255, 255))
            
            file_ext = file_path.split('.')[-1].upper()
            painter.drawText(pixmap.rect(), Qt.AlignCenter, f"{file_ext}\nVIDEO")
            painter.end()
            
            print("DEBUG: Thumbnail generated successfully")
            return pixmap
            
        except Exception as e:
            print(f"DEBUG: Error in generate_thumbnail: {str(e)}")
            # Return empty pixmap as fallback
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
            
            # 1. Load in dual preview (UI update)
            self.dual_preview.load_video(video_path)
            
            # 2. Load in integrated video player (ACTUAL VIDEO PLAYBACK)
            if hasattr(self, 'video_player') and self.video_player:
                success = self.video_player.load_video(video_path)
                
                if success:
                    print("DEBUG: Video loaded successfully in integrated player")
                    
                    # Show first frame immediately
                    self.video_player.seek(0)
                    
                    # Update control panels with duration
                    duration = self.video_player.get_duration()
                    self.update_control_panels_duration(duration)
                else:
                    print("DEBUG: Failed to load video in player")
                    self.show_error_message("Failed to load video in player")
            else:
                print("DEBUG: Video player not available, using fallback")
                # Fallback: Just update UI without actual playback
                pass
                
            logger.info(f"Video loaded successfully: {os.path.basename(video_path)}")
            
        except Exception as e:
            print(f"DEBUG: Error in load_video: {str(e)}")
            import traceback
            traceback.print_exc()

    def update_control_panels_duration(self, duration_seconds):
        """Update both control panels with video duration"""
        try:
            if hasattr(self, 'dual_controls'):
                self.dual_controls.before_controls.set_duration(duration_seconds)
                self.dual_controls.after_controls.set_duration(duration_seconds)
            elif hasattr(self, 'control_panel'):
                self.control_panel.set_duration(duration_seconds)
        except Exception as e:
            print(f"DEBUG: Error updating control panels: {str(e)}")

    def on_video_frame_ready(self, frame_pixmap, is_before):
        """Receive video frames and display in preview windows"""
        try:
            # Display frame in appropriate preview window
            self.dual_preview.show_video_frame(frame_pixmap, is_before)
            
        except Exception as e:
            print(f"DEBUG: Error displaying video frame: {str(e)}")

    def on_video_position_changed(self, position_seconds):
        """Update UI when video position changes"""
        try:
            duration = self.video_player.get_duration()
            
            if duration > 0:
                # Convert seconds to scrubber position (0-1000)
                scrubber_position = int((position_seconds / duration) * 1000)
                
                # Update control panels
                if hasattr(self, 'dual_controls'):
                    self.dual_controls.before_controls.set_position(scrubber_position)
                    self.dual_controls.after_controls.set_position(scrubber_position)
                elif hasattr(self, 'control_panel'):
                    self.control_panel.set_position(scrubber_position)
            
            # Update dual preview time display
            self.dual_preview.update_time(position_seconds, duration)
            
        except Exception as e:
            print(f"DEBUG: Error updating position: {str(e)}")

    def on_video_duration_changed(self, duration_seconds):
        """Update UI when video duration is known"""
        try:
            # Update control panels
            self.update_control_panels_duration(duration_seconds)
            
            # Update dual preview
            self.dual_preview.update_time(0, duration_seconds)
            
        except Exception as e:
            print(f"DEBUG: Error updating duration: {str(e)}")

    def on_video_state_changed(self, state):
        """Handle video state changes - FIXED to prevent recursion"""
        try:
            print(f"DEBUG: Video state changed to: {state}")
            
            # Update control panels WITHOUT emitting signals (prevent recursion)
            if hasattr(self, 'dual_controls'):
                if state == "playing":
                    self.dual_controls.before_controls.set_playing_state(update_ui_only=True)
                    self.dual_controls.after_controls.set_playing_state(update_ui_only=True)
                elif state == "paused":
                    self.dual_controls.before_controls.set_paused_state(update_ui_only=True)
                    self.dual_controls.after_controls.set_paused_state(update_ui_only=True)
                elif state == "stopped":
                    self.dual_controls.before_controls.set_stopped_state(update_ui_only=True)
                    self.dual_controls.after_controls.set_stopped_state(update_ui_only=True)
                    
        except Exception as e:
            print(f"DEBUG: Error handling state change: {str(e)}")

    def on_scrubber_moved(self, scrubber_position):
        """Handle scrubber movement - seek video"""
        try:
            if hasattr(self, 'video_player') and self.video_player:
                # Convert scrubber position (0-1000) to seconds
                duration = self.video_player.get_duration()
                target_time = (scrubber_position / 1000.0) * duration
                self.video_player.seek(target_time)
                
        except Exception as e:
            print(f"DEBUG: Error seeking video: {str(e)}")

    # Dual control panel methods
    def on_before_play_clicked(self):
        """Handle before window play - FIXED"""
        try:
            print("DEBUG: 🎬 BEFORE Play button clicked")
            self.debug_video_player_state()
            
            if hasattr(self, 'video_player') and self.video_player:
                # Check if video is loaded
                if self.video_player.get_duration() > 0:
                    self.video_player.play()
                    print("DEBUG: ✅ Video player play command sent")
                    
                    # Update UI state
                    self.dual_controls.before_controls.set_playing_state(update_ui_only=True)
                    self.dual_controls.after_controls.set_playing_state(update_ui_only=True)
                else:
                    print("DEBUG: ❌ No video loaded to play")
            else:
                print("DEBUG: ❌ Video player not available")
                
        except Exception as e:
            print(f"DEBUG: ❌ Error in on_before_play_clicked: {str(e)}")
            import traceback
            traceback.print_exc()

    def on_before_pause_clicked(self):
        """Handle before window pause - FIXED"""
        try:
            print("DEBUG: ⏸️ BEFORE Pause button clicked")
            
            if hasattr(self, 'video_player') and self.video_player:
                self.video_player.pause()
                print("DEBUG: ✅ Video player pause command sent")
                
                # Update UI state
                self.dual_controls.before_controls.set_paused_state(update_ui_only=True)
                self.dual_controls.after_controls.set_paused_state(update_ui_only=True)
            else:
                print("DEBUG: ❌ Video player not available")
                
        except Exception as e:
            print(f"DEBUG: ❌ Error in on_before_pause_clicked: {str(e)}")

    def on_before_stop_clicked(self):
        """Handle before window stop - FIXED"""
        try:
            print("DEBUG: ⏹️ BEFORE Stop button clicked")
            
            if hasattr(self, 'video_player') and self.video_player:
                self.video_player.stop()
                print("DEBUG: ✅ Video player stop command sent")
                
                # Update UI state
                self.dual_controls.before_controls.set_stopped_state(update_ui_only=True)
                self.dual_controls.after_controls.set_stopped_state(update_ui_only=True)
            else:
                print("DEBUG: ❌ Video player not available")
                
        except Exception as e:
            print(f"DEBUG: ❌ Error in on_before_stop_clicked: {str(e)}")     
    
    def on_before_scrubber_moved(self, position):
        """Handle before window scrubber movement"""
        self.on_scrubber_moved(position)

    def on_after_play_clicked(self):
        """Handle after window play - FIXED"""
        try:
            print("DEBUG: 🎬 AFTER Play button clicked")
            self.debug_video_player_state()
            
            if hasattr(self, 'video_player') and self.video_player:
                if self.video_player.get_duration() > 0:
                    self.video_player.play()
                    print("DEBUG: ✅ Video player play command sent")
                    
                    # Update UI state
                    self.dual_controls.before_controls.set_playing_state(update_ui_only=True)
                    self.dual_controls.after_controls.set_playing_state(update_ui_only=True)
                else:
                    print("DEBUG: ❌ No video loaded to play")
            else:
                print("DEBUG: ❌ Video player not available")
                
        except Exception as e:
            print(f"DEBUG: ❌ Error in on_after_play_clicked: {str(e)}")

    def on_after_pause_clicked(self):
        """Handle after window pause - FIXED"""
        try:
            print("DEBUG: ⏸️ AFTER Pause button clicked")
            
            if hasattr(self, 'video_player') and self.video_player:
                self.video_player.pause()
                print("DEBUG: ✅ Video player pause command sent")
                
                # Update UI state
                self.dual_controls.before_controls.set_paused_state(update_ui_only=True)
                self.dual_controls.after_controls.set_paused_state(update_ui_only=True)
            else:
                print("DEBUG: ❌ Video player not available")
                
        except Exception as e:
            print(f"DEBUG: ❌ Error in on_after_pause_clicked: {str(e)}")

    def on_after_stop_clicked(self):
        """Handle after window stop - FIXED"""
        try:
            print("DEBUG: ⏹️ AFTER Stop button clicked")
            
            if hasattr(self, 'video_player') and self.video_player:
                self.video_player.stop()
                print("DEBUG: ✅ Video player stop command sent")
                
                # Update UI state
                self.dual_controls.before_controls.set_stopped_state(update_ui_only=True)
                self.dual_controls.after_controls.set_stopped_state(update_ui_only=True)
            else:
                print("DEBUG: ❌ Video player not available")
                
        except Exception as e:
            print(f"DEBUG: ❌ Error in on_after_stop_clicked: {str(e)}")   
    def on_after_scrubber_moved(self, position):
        """Handle after window scrubber movement"""
        self.on_scrubber_moved(position)

    def show_error_message(self, message):
        """Show error message to user"""
        # You can implement a proper error dialog here
        print(f"ERROR: {message}")

    def cleanup(self):
        """Clean up resources"""
        try:
            if hasattr(self, 'video_player'):
                self.video_player.cleanup()
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
        if hasattr(self, 'video_player') and self.video_player:
            self.video_player.play()

    def on_pause_clicked(self):
        """Handle pause button"""
        logger.info("Pause clicked")
        if hasattr(self, 'video_player') and self.video_player:
            self.video_player.pause()

    def on_stop_clicked(self):
        """Handle stop button"""
        logger.info("Stop clicked")
        if hasattr(self, 'video_player') and self.video_player:
            self.video_player.stop()
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
        self.cleanup()
        if self.back_callback:
            self.back_callback()
        else:
            self.close()