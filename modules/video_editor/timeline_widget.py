"""
modules/video_editor/timeline_widget.py
Professional Timeline Widget for Video Editing
Multi-track timeline with drag, trim, split functionality
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsLineItem,
    QGraphicsTextItem, QSlider, QCheckBox, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QPointF
from PyQt5.QtGui import QColor, QPen, QBrush, QFont, QPainter

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class TimelineClip(QGraphicsRectItem):
    """Represents a video/audio/image clip on the timeline"""

    def __init__(self, x, y, width, height, clip_data, parent=None):
        super().__init__(x, y, width, height, parent)

        self.clip_data = clip_data  # MediaItem reference
        self.track_index = 0

        # Visual properties
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.ItemSendsGeometryChanges, True)

        # Set color based on clip type
        color_map = {
            'video': QColor(64, 123, 255),  # Blue
            'audio': QColor(0, 203, 184),    # Cyan
            'image': QColor(255, 111, 97)    # Orange
        }

        clip_type = clip_data.file_type if hasattr(clip_data, 'file_type') else 'video'
        color = color_map.get(clip_type, QColor(128, 128, 128))

        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor(255, 255, 255, 100), 1))

        # Add text label
        self.label = QGraphicsTextItem(self)
        self.label.setPlainText(clip_data.file_name if hasattr(clip_data, 'file_name') else "Clip")
        self.label.setDefaultTextColor(QColor(255, 255, 255))
        self.label.setFont(QFont("Arial", 9))
        self.label.setPos(5, 5)

        # Trim handles (invisible for now, will activate on hover)
        self.left_handle = None
        self.right_handle = None

    def itemChange(self, change, value):
        """Handle item changes (movement, selection, etc.)"""
        if change == QGraphicsRectItem.ItemPositionChange:
            # Snap to grid/clips if needed
            pass
        return super().itemChange(change, value)


class TimelineTrack(QFrame):
    """Represents a single timeline track (video, audio, or text)"""

    def __init__(self, track_name, track_type='video', parent=None):
        super().__init__(parent)
        self.track_name = track_name
        self.track_type = track_type
        self.clips = []

        self.setFixedHeight(60)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-bottom: 1px solid #2a2a2a;
            }
        """)

        self.init_ui()

    def init_ui(self):
        """Initialize track UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Track header (controls)
        header = QFrame()
        header.setStyleSheet("background-color: #252525; border-right: 1px solid #2a2a2a;")
        header.setFixedWidth(120)

        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(4)

        # Track name
        name_label = QLabel(self.track_name)
        name_label.setStyleSheet("font-weight: bold; color: #e0e0e0; font-size: 11px;")
        header_layout.addWidget(name_label)

        # Track controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(4)

        lock_btn = QPushButton("🔒")
        lock_btn.setMaximumWidth(25)
        lock_btn.setMaximumHeight(25)
        lock_btn.setCheckable(True)
        lock_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:checked {
                background-color: #c0392b;
            }
        """)
        controls_layout.addWidget(lock_btn)

        visible_btn = QPushButton("👁")
        visible_btn.setMaximumWidth(25)
        visible_btn.setMaximumHeight(25)
        visible_btn.setCheckable(True)
        visible_btn.setChecked(True)
        visible_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:checked {
                background-color: #00bcd4;
            }
        """)
        controls_layout.addWidget(visible_btn)

        if self.track_type == 'audio':
            mute_btn = QPushButton("🔇")
            mute_btn.setMaximumWidth(25)
            mute_btn.setMaximumHeight(25)
            mute_btn.setCheckable(True)
            mute_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a2a;
                    border: none;
                    border-radius: 4px;
                    font-size: 10px;
                }
                QPushButton:checked {
                    background-color: #f39c12;
                }
            """)
            controls_layout.addWidget(mute_btn)

        controls_layout.addStretch()
        header_layout.addLayout(controls_layout)

        header.setLayout(header_layout)
        layout.addWidget(header)

        # Track content area (will contain QGraphicsView for clips)
        content = QFrame()
        content.setStyleSheet("background-color: #1a1a1a; border: none;")
        layout.addWidget(content, 1)

        self.setLayout(layout)


class TimelineWidget(QWidget):
    """
    Professional multi-track timeline widget
    Handles video, audio, image clips with drag, trim, split functionality
    """

    # Signals
    clip_selected = pyqtSignal(object)  # Emits selected clip data
    playhead_moved = pyqtSignal(float)  # Emits time position

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tracks = []
        self.clips = []
        self.playhead_position = 0.0
        self.zoom_level = 1.0
        self.snap_enabled = True

        self.init_ui()

    def init_ui(self):
        """Initialize timeline UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Timeline toolbar
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        # Timeline view (with tracks)
        timeline_view = self.create_timeline_view()
        main_layout.addWidget(timeline_view, 1)

        self.setLayout(main_layout)

    def create_toolbar(self):
        """Create timeline toolbar with controls"""
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #2a2a2a;")
        toolbar.setFixedHeight(45)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        # Timeline tools
        tools_label = QLabel("Tools:")
        tools_label.setStyleSheet("color: #888888; font-weight: bold; font-size: 11px;")
        layout.addWidget(tools_label)

        tool_buttons = [
            ("✋ Select", "V"),
            ("✂️ Split", "S"),
            ("📏 Trim", "T"),
        ]

        for name, shortcut in tool_buttons:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setToolTip(f"Shortcut: {shortcut}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a2a;
                    color: #e0e0e0;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 12px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #353535;
                }
                QPushButton:checked {
                    background-color: #00bcd4;
                    color: #ffffff;
                }
            """)
            layout.addWidget(btn)

        layout.addSpacing(20)

        # Zoom controls
        zoom_label = QLabel("Zoom:")
        zoom_label.setStyleSheet("color: #888888; font-weight: bold; font-size: 11px;")
        layout.addWidget(zoom_label)

        zoom_out_btn = QPushButton("➖")
        zoom_out_btn.setMaximumWidth(30)
        zoom_out_btn.setToolTip("Zoom out (Ctrl+-)")
        zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
        """)
        layout.addWidget(zoom_out_btn)

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setMaximumWidth(120)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        layout.addWidget(self.zoom_slider)

        zoom_in_btn = QPushButton("➕")
        zoom_in_btn.setMaximumWidth(30)
        zoom_in_btn.setToolTip("Zoom in (Ctrl++)")
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_in_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
        """)
        layout.addWidget(zoom_in_btn)

        fit_btn = QPushButton("⬌ Fit")
        fit_btn.setToolTip("Fit to timeline")
        fit_btn.clicked.connect(self.fit_to_timeline)
        fit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
        """)
        layout.addWidget(fit_btn)

        layout.addSpacing(20)

        # Snap toggle
        self.snap_check = QCheckBox("🧲 Snap")
        self.snap_check.setChecked(True)
        self.snap_check.setToolTip("Enable snapping to clips/markers")
        self.snap_check.stateChanged.connect(self.on_snap_toggled)
        self.snap_check.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        layout.addWidget(self.snap_check)

        # Marker
        marker_btn = QPushButton("📍 Marker")
        marker_btn.setToolTip("Add marker at playhead (M)")
        marker_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
        """)
        layout.addWidget(marker_btn)

        layout.addStretch()

        # Add track button
        add_track_btn = QPushButton("➕ Add Track")
        add_track_btn.setToolTip("Add new video/audio track")
        add_track_btn.clicked.connect(self.add_track)
        add_track_btn.setStyleSheet("""
            QPushButton {
                background-color: #00bcd4;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #00d4ea;
            }
        """)
        layout.addWidget(add_track_btn)

        toolbar.setLayout(layout)
        return toolbar

    def create_timeline_view(self):
        """Create the main timeline view with tracks"""
        container = QFrame()
        container.setStyleSheet("background-color: #1a1a1a; border: none;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Import prompt (when empty)
        self.import_prompt = QFrame()
        self.import_prompt.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px dashed #3a3a3a;
                border-radius: 12px;
            }
        """)
        self.import_prompt.setMinimumHeight(150)

        import_layout = QVBoxLayout()
        import_layout.setAlignment(Qt.AlignCenter)

        import_icon = QLabel("📥")
        import_icon.setStyleSheet("font-size: 48px;")
        import_icon.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(import_icon)

        import_label = QLabel("Import media or drag from Media Library")
        import_label.setStyleSheet("font-size: 14px; color: #888888; font-weight: bold;")
        import_label.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(import_label)

        import_hint = QLabel("Double-click media items to add to timeline")
        import_hint.setStyleSheet("font-size: 12px; color: #666666;")
        import_hint.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(import_hint)

        self.import_prompt.setLayout(import_layout)
        layout.addWidget(self.import_prompt)

        # Tracks container (scrollable)
        self.tracks_container = QWidget()
        self.tracks_layout = QVBoxLayout()
        self.tracks_layout.setContentsMargins(0, 0, 0, 0)
        self.tracks_layout.setSpacing(2)
        self.tracks_container.setLayout(self.tracks_layout)

        # Create initial tracks
        self.add_initial_tracks()

        layout.addWidget(self.tracks_container)
        layout.addStretch()

        container.setLayout(layout)
        return container

    def add_initial_tracks(self):
        """Add initial default tracks"""
        default_tracks = [
            ("Video 1", "video"),
            ("Video 2", "video"),
            ("Audio 1", "audio"),
            ("Text 1", "text")
        ]

        for name, track_type in default_tracks:
            track = TimelineTrack(name, track_type)
            self.tracks.append(track)
            self.tracks_layout.addWidget(track)

    def add_track(self):
        """Add a new track to the timeline"""
        track_num = len(self.tracks) + 1
        track = TimelineTrack(f"Track {track_num}", "video")
        self.tracks.append(track)
        self.tracks_layout.addWidget(track)
        logger.info(f"Added new track: Track {track_num}")

    def zoom_in(self):
        """Zoom in the timeline"""
        current_value = self.zoom_slider.value()
        self.zoom_slider.setValue(min(200, current_value + 10))

    def zoom_out(self):
        """Zoom out the timeline"""
        current_value = self.zoom_slider.value()
        self.zoom_slider.setValue(max(10, current_value - 10))

    def on_zoom_changed(self, value):
        """Handle zoom level change"""
        self.zoom_level = value / 100.0
        logger.debug(f"Zoom level changed to: {self.zoom_level}")

    def fit_to_timeline(self):
        """Fit all content to timeline view"""
        self.zoom_slider.setValue(100)
        logger.info("Fit to timeline")

    def on_snap_toggled(self, state):
        """Handle snap toggle"""
        self.snap_enabled = (state == Qt.Checked)
        logger.info(f"Snap enabled: {self.snap_enabled}")

    def add_clip(self, media_item, track_index=0):
        """Add a media clip to the timeline"""
        # Hide import prompt when first clip is added
        if len(self.clips) == 0:
            self.import_prompt.hide()

        # Create clip representation
        # This will be implemented with QGraphicsView in next iteration
        logger.info(f"Added clip to timeline: {media_item.file_name}")

    def remove_clip(self, clip):
        """Remove a clip from the timeline"""
        if clip in self.clips:
            self.clips.remove(clip)
            logger.info("Removed clip from timeline")
