"""
modules/video_editor/timeline_widget.py
Professional Timeline Widget for Video Editing
Multi-track timeline with drag, trim, split functionality
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsLineItem,
    QGraphicsTextItem, QSlider, QCheckBox, QFrame, QScrollArea, QMenu
)
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QPointF
from PyQt5.QtGui import QColor, QPen, QBrush, QFont, QPainter

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class TimelineClip(QGraphicsRectItem):
    """Represents a video/audio/image clip on the timeline"""

    def __init__(self, x, y, width, height, clip_data, track=None, parent=None):
        super().__init__(x, y, width, height, parent)

        self.clip_data = clip_data  # MediaItem reference
        self.track_index = 0
        self.track = track  # Reference to parent track

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
        self.setPen(QPen(QColor(255, 255, 255, 180), 2))

        # Add text labels
        file_name = clip_data.file_name if hasattr(clip_data, 'file_name') else "Clip"

        self.name_label = QGraphicsTextItem(self)
        self.name_label.setPlainText(file_name)
        self.name_label.setDefaultTextColor(QColor(255, 255, 255))
        self.name_label.setFont(QFont("Arial", 9, QFont.Bold))
        self.name_label.setPos(5, 5)

        # Duration label (if available)
        if hasattr(clip_data, 'duration') and clip_data.duration > 0:
            mins, secs = divmod(int(clip_data.duration), 60)
            duration_text = f"{mins:02d}:{secs:02d}"

            self.duration_label = QGraphicsTextItem(self)
            self.duration_label.setPlainText(duration_text)
            self.duration_label.setDefaultTextColor(QColor(255, 255, 255, 200))
            self.duration_label.setFont(QFont("Arial", 8))
            self.duration_label.setPos(5, 25)
        else:
            self.duration_label = None

        # Trim handles
        self.trim_handle_width = 8
        self.is_trimming = False
        self.trim_side = None  # 'left' or 'right'
        self.original_rect = None

        # Create trim handles (initially hidden)
        self.left_handle = QGraphicsRectItem(0, 0, self.trim_handle_width, height, self)
        self.left_handle.setBrush(QBrush(QColor(0, 188, 212, 150)))
        self.left_handle.setPen(QPen(Qt.NoPen))
        self.left_handle.setVisible(False)
        self.left_handle.setCursor(Qt.SizeHorCursor)

        self.right_handle = QGraphicsRectItem(width - self.trim_handle_width, 0, self.trim_handle_width, height, self)
        self.right_handle.setBrush(QBrush(QColor(0, 188, 212, 150)))
        self.right_handle.setPen(QPen(Qt.NoPen))
        self.right_handle.setVisible(False)
        self.right_handle.setCursor(Qt.SizeHorCursor)

        # Enable hover events
        self.setAcceptHoverEvents(True)

    def itemChange(self, change, value):
        """Handle item changes (movement, selection, etc.)"""
        if change == QGraphicsRectItem.ItemPositionChange:
            # Snap to grid/clips if needed
            pass
        elif change == QGraphicsRectItem.ItemSelectedChange:
            # Highlight when selected
            if value:  # Selected
                self.setPen(QPen(QColor(0, 188, 212), 3))  # Cyan highlight
            else:  # Deselected
                self.setPen(QPen(QColor(255, 255, 255, 180), 2))
        return super().itemChange(change, value)

    def delete(self):
        """Delete this clip from the timeline"""
        if self.track:
            self.track.remove_clip(self)

    def hoverEnterEvent(self, event):
        """Show trim handles on hover"""
        if not self.is_trimming:
            self.left_handle.setVisible(True)
            self.right_handle.setVisible(True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Hide trim handles when not hovering"""
        if not self.is_trimming and not self.isSelected():
            self.left_handle.setVisible(False)
            self.right_handle.setVisible(False)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press for trimming or moving"""
        if event.button() == Qt.LeftButton:
            # Check if clicking on a trim handle
            local_pos = event.pos()

            if self.left_handle.contains(local_pos):
                self.is_trimming = True
                self.trim_side = 'left'
                self.original_rect = self.rect()
                self.setFlag(QGraphicsRectItem.ItemIsMovable, False)
                event.accept()
                return
            elif self.right_handle.contains(local_pos):
                self.is_trimming = True
                self.trim_side = 'right'
                self.original_rect = self.rect()
                self.setFlag(QGraphicsRectItem.ItemIsMovable, False)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for trimming"""
        if self.is_trimming:
            current_rect = self.rect()
            delta_x = event.pos().x() - event.lastPos().x()

            if self.trim_side == 'left':
                # Trim from left
                new_x = current_rect.x() + delta_x
                new_width = current_rect.width() - delta_x

                # Minimum width constraint
                if new_width >= 50:
                    current_rect.setLeft(new_x)
                    self.setRect(current_rect)
                    # Update handle position
                    self.left_handle.setPos(0, 0)
                    self.right_handle.setPos(current_rect.width() - self.trim_handle_width, 0)

            elif self.trim_side == 'right':
                # Trim from right
                new_width = current_rect.width() + delta_x

                # Minimum width constraint
                if new_width >= 50:
                    current_rect.setWidth(new_width)
                    self.setRect(current_rect)
                    # Update handle position
                    self.right_handle.setPos(current_rect.width() - self.trim_handle_width, 0)

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release after trimming"""
        if self.is_trimming:
            self.is_trimming = False
            self.trim_side = None
            self.setFlag(QGraphicsRectItem.ItemIsMovable, True)

            # Log trim operation
            if hasattr(self.clip_data, 'file_name'):
                logger.info(f"Trimmed clip: {self.clip_data.file_name}, new width: {self.rect().width()}px")

            event.accept()
        else:
            super().mouseReleaseEvent(event)


class TimelineGraphicsView(QGraphicsView):
    """Custom graphics view for timeline track with drop support"""

    def __init__(self, track_widget, parent=None):
        super().__init__(parent)
        self.track_widget = track_widget
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # Set scene size (will expand as needed)
        self.scene.setSceneRect(0, 0, 10000, 50)

        # View settings
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("background-color: #1a1a1a; border: none;")
        self.setRenderHint(QPainter.Antialiasing)

        # Enable drag and drop
        self.setAcceptDrops(True)

        # Enable keyboard focus for Delete key
        self.setFocusPolicy(Qt.StrongFocus)

        # Playhead line
        self.playhead_line = None
        self.create_playhead()

    def dragEnterEvent(self, event):
        """Accept drag events from media library"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Handle drag move"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop event - create clip on timeline"""
        if event.mimeData().hasText():
            # Get drop position
            pos = event.pos()
            scene_pos = self.mapToScene(pos)

            # Notify track widget
            self.track_widget.handle_drop(scene_pos.x(), event.mimeData())
            event.acceptProposedAction()
        else:
            event.ignore()

    def create_playhead(self):
        """Create the playhead line"""
        # Playhead line (red vertical line)
        self.playhead_line = QGraphicsLineItem(0, 0, 0, 50)
        self.playhead_line.setPen(QPen(QColor(255, 82, 82), 3))  # Red line, 3px thick
        self.playhead_line.setZValue(1000)  # Always on top
        self.scene.addItem(self.playhead_line)

        # Playhead head (triangle at top)
        from PyQt5.QtWidgets import QGraphicsPolygonItem
        from PyQt5.QtGui import QPolygonF

        triangle = QPolygonF([
            QPointF(0, 0),
            QPointF(-6, -10),
            QPointF(6, -10)
        ])
        self.playhead_head = QGraphicsPolygonItem(triangle)
        self.playhead_head.setBrush(QBrush(QColor(255, 82, 82)))
        self.playhead_head.setPen(QPen(Qt.NoPen))
        self.playhead_head.setZValue(1001)
        self.scene.addItem(self.playhead_head)

    def set_playhead_position(self, x_position):
        """Update playhead position"""
        if self.playhead_line:
            self.playhead_line.setLine(x_position, 0, x_position, 50)
            self.playhead_head.setPos(x_position, 0)

    def mousePressEvent(self, event):
        """Handle mouse clicks for seeking"""
        if event.button() == Qt.LeftButton:
            # Get click position in scene
            scene_pos = self.mapToScene(event.pos())
            x_pos = scene_pos.x()

            # Check if we clicked on a clip
            item = self.scene.itemAt(scene_pos, self.transform())

            # If not clicking on a clip, handle as seek
            if not isinstance(item, TimelineClip):
                # Notify track widget of click (for seeking)
                if hasattr(self.track_widget, 'on_timeline_clicked'):
                    self.track_widget.on_timeline_clicked(x_pos)

        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # Delete selected clips
            selected_items = self.scene.selectedItems()
            for item in selected_items:
                if isinstance(item, TimelineClip):
                    item.delete()
            logger.info(f"Deleted {len(selected_items)} clip(s)")
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """Show context menu for clips"""
        # Get item at position
        scene_pos = self.mapToScene(event.pos())
        item = self.scene.itemAt(scene_pos, self.transform())

        if isinstance(item, TimelineClip):
            # Create context menu
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

            # Delete action
            delete_action = menu.addAction("🗑️ Delete Clip")
            delete_action.triggered.connect(lambda: item.delete())

            menu.addSeparator()

            # Trim action (placeholder)
            trim_action = menu.addAction("✂️ Trim Clip")
            trim_action.setEnabled(False)  # Not implemented yet

            # Split action (placeholder)
            split_action = menu.addAction("✂️ Split Clip")
            split_action.setEnabled(False)  # Not implemented yet

            # Show menu
            menu.exec_(event.globalPos())
        else:
            super().contextMenuEvent(event)


class TimelineTrack(QFrame):
    """Represents a single timeline track (video, audio, or text)"""

    def __init__(self, track_name, track_type='video', parent=None):
        super().__init__(parent)
        self.track_name = track_name
        self.track_type = track_type
        self.clips = []
        self.graphics_view = None
        self.media_item_getter = None  # Function to get MediaItem by path
        self.pixels_per_second = 30  # Default: 30 pixels = 1 second

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

        # Track content area (QGraphicsView for clips)
        self.graphics_view = TimelineGraphicsView(self)
        layout.addWidget(self.graphics_view, 1)

        self.setLayout(layout)

    def handle_drop(self, x_position, mime_data):
        """Handle media drop on this track"""
        # Get file path from mime data
        file_path = mime_data.text()

        logger.info(f"Drop on track {self.track_name} at position {x_position}: {file_path}")

        # Get media item using getter function
        if self.media_item_getter:
            media_item = self.media_item_getter(file_path)
            if media_item:
                self.create_clip_at_position(x_position, media_item)
            else:
                logger.warning(f"Could not find media item for: {file_path}")
        else:
            logger.error("No media_item_getter set for timeline track")

    def create_clip_at_position(self, x_pos, media_item):
        """Create a visual clip on the timeline"""
        clip_height = 45

        # Calculate clip width based on duration
        if hasattr(media_item, 'duration') and media_item.duration > 0:
            clip_width = media_item.duration * self.pixels_per_second
        else:
            # Default width for images or items without duration (3 seconds)
            clip_width = 3 * self.pixels_per_second

        # Minimum width for visibility
        clip_width = max(clip_width, 50)

        # Create clip with track reference
        clip = TimelineClip(x_pos, 2, clip_width, clip_height, media_item, track=self)

        # Add to scene
        self.graphics_view.scene.addItem(clip)
        self.clips.append(clip)

        logger.info(f"Created clip on {self.track_name}: {media_item.file_name} (duration: {media_item.duration}s, width: {clip_width}px)")

    def remove_clip(self, clip):
        """Remove a clip from this track"""
        if clip in self.clips:
            # Remove from scene
            if self.graphics_view and self.graphics_view.scene:
                self.graphics_view.scene.removeItem(clip)

            # Remove from clips list
            self.clips.remove(clip)

            logger.info(f"Removed clip from {self.track_name}: {clip.clip_data.file_name if hasattr(clip, 'clip_data') else 'unknown'}")

    def set_playhead_position(self, x_position):
        """Update playhead position on this track"""
        if self.graphics_view:
            self.graphics_view.set_playhead_position(x_position)

    def on_timeline_clicked(self, x_position):
        """Handle timeline click for seeking"""
        # Calculate time from x position
        time_seconds = x_position / self.pixels_per_second

        # Notify parent timeline widget
        parent = self.parent()
        while parent and not isinstance(parent, TimelineWidget):
            parent = parent.parent()

        if parent and isinstance(parent, TimelineWidget):
            parent.on_timeline_seek(time_seconds)

        logger.debug(f"Timeline clicked at x={x_position}, time={time_seconds}s")


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
        self.media_item_getter = None  # Function to get MediaItem by path
        self.pixels_per_second = 30  # Default: 30 pixels = 1 second

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

    def set_media_item_getter(self, getter_func):
        """Set the function to get MediaItem by file path"""
        self.media_item_getter = getter_func

        # Pass to all tracks
        for track in self.tracks:
            track.media_item_getter = getter_func

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

    def update_playhead(self, time_seconds):
        """Update playhead position based on video time"""
        # Convert time to x position (pixels)
        x_position = time_seconds * self.pixels_per_second

        # Update on all tracks
        for track in self.tracks:
            track.set_playhead_position(x_position)

        # Store current position
        self.playhead_position = time_seconds

    def on_timeline_seek(self, time_seconds):
        """Handle seek request from timeline click"""
        logger.info(f"Seeking to {time_seconds}s")

        # Update playhead visually
        self.update_playhead(time_seconds)

        # Emit signal for video player to seek
        self.playhead_moved.emit(time_seconds)
