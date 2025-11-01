"""
modules/video_editor/timeline_widget_minimal.py
Minimal Timeline Widget - Removed playback controls, scrubber, middle section, ruler
Only keeps: Tools Bar, Tracks, Status Bar
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsLineItem,
    QGraphicsTextItem, QSlider, QCheckBox, QFrame, QScrollArea, QMenu,
    QGraphicsPolygonItem, QComboBox, QSpinBox
)
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QPointF, QTimer
from PyQt5.QtGui import (
    QColor, QPen, QBrush, QFont, QPainter, QPolygonF,
    QLinearGradient, QCursor
)

from modules.logging.logger import get_logger

logger = get_logger(__name__)


# ==================== TIMELINE CLIP ====================

class TimelineClip(QGraphicsRectItem):
    """Represents a video/audio/image clip on the timeline with enhanced visual design"""

    def __init__(self, x, y, width, height, clip_data, track=None, parent=None):
        super().__init__(x, y, width, height, parent)

        self.clip_data = clip_data  # MediaItem reference
        self.track_index = 0
        self.track = track  # Reference to parent track

        # Visual properties
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.ItemSendsGeometryChanges, True)

        # Enhanced colors with gradients
        clip_type = clip_data.file_type if hasattr(clip_data, 'file_type') else 'video'

        color_map = {
            'video': {'start': QColor(30, 58, 138), 'end': QColor(59, 130, 246), 'border': QColor(96, 165, 250)},  # Blue gradient
            'audio': {'start': QColor(22, 101, 52), 'end': QColor(34, 197, 94), 'border': QColor(74, 222, 128)},  # Green gradient
            'image': {'start': QColor(107, 33, 168), 'end': QColor(168, 85, 247), 'border': QColor(192, 132, 252)},  # Purple gradient
            'text': {'start': QColor(107, 33, 168), 'end': QColor(168, 85, 247), 'border': QColor(192, 132, 252)}  # Purple gradient
        }

        colors = color_map.get(clip_type, color_map['video'])

        # Create gradient brush
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, colors['start'])
        gradient.setColorAt(1, colors['end'])

        self.default_brush = QBrush(gradient)
        self.default_pen = QPen(colors['border'], 2)
        self.selected_pen = QPen(QColor(0, 188, 212), 3)  # Cyan for selection

        self.setBrush(self.default_brush)
        self.setPen(self.default_pen)

        # Add text labels
        file_name = clip_data.file_name if hasattr(clip_data, 'file_name') else "Clip"

        self.name_label = QGraphicsTextItem(self)
        self.name_label.setPlainText(file_name)
        self.name_label.setDefaultTextColor(QColor(255, 255, 255))
        self.name_label.setFont(QFont("Arial", 9, QFont.Bold))
        self.name_label.setPos(5, 5)

        # Duration label (top-right)
        if hasattr(clip_data, 'duration') and clip_data.duration > 0:
            mins, secs = divmod(int(clip_data.duration), 60)
            duration_text = f"{mins:02d}:{secs:02d}"

            self.duration_label = QGraphicsTextItem(self)
            self.duration_label.setPlainText(duration_text)
            self.duration_label.setDefaultTextColor(QColor(255, 255, 255, 200))
            self.duration_label.setFont(QFont("Arial", 8))
            self.duration_label.setPos(width - 45, 5)
        else:
            self.duration_label = None

        # Trim handles
        self.trim_handle_width = 10
        self.is_trimming = False
        self.trim_side = None
        self.original_rect = None

        # Create trim handles (initially hidden)
        self.left_handle = QGraphicsRectItem(0, 0, self.trim_handle_width, height, self)
        self.left_handle.setBrush(QBrush(QColor(0, 188, 212, 180)))
        self.left_handle.setPen(QPen(Qt.NoPen))
        self.left_handle.setVisible(False)
        self.left_handle.setCursor(Qt.SizeHorCursor)

        self.right_handle = QGraphicsRectItem(width - self.trim_handle_width, 0, self.trim_handle_width, height, self)
        self.right_handle.setBrush(QBrush(QColor(0, 188, 212, 180)))
        self.right_handle.setPen(QPen(Qt.NoPen))
        self.right_handle.setVisible(False)
        self.right_handle.setCursor(Qt.SizeHorCursor)

        # Enable hover events
        self.setAcceptHoverEvents(True)

    def itemChange(self, change, value):
        """Handle item changes (movement, selection, etc.)"""
        if change == QGraphicsRectItem.ItemPositionChange:
            pass
        elif change == QGraphicsRectItem.ItemSelectedChange:
            if value:
                self.setPen(self.selected_pen)
            else:
                self.setPen(self.default_pen)
        return super().itemChange(change, value)

    def delete(self):
        """Delete this clip from the timeline"""
        if self.track:
            self.track.remove_clip(self)

    def split_at_position(self, x_position):
        """Split this clip at the given x position"""
        if not self.track:
            return None

        clip_rect = self.sceneBoundingRect()
        clip_start = clip_rect.x()
        clip_end = clip_rect.x() + clip_rect.width()

        if x_position <= clip_start or x_position >= clip_end:
            return None

        split_offset = x_position - clip_start
        right_width = clip_rect.width() - split_offset
        right_clip = TimelineClip(
            x_position, self.pos().y(), right_width, clip_rect.height(),
            self.clip_data, track=self.track
        )

        new_rect = self.rect()
        new_rect.setWidth(split_offset)
        self.setRect(new_rect)
        self.right_handle.setPos(new_rect.width() - self.trim_handle_width, 0)

        if self.duration_label:
            self.duration_label.setPos(new_rect.width() - 45, 5)

        self.track.add_split_clip(right_clip)
        return right_clip

    def hoverEnterEvent(self, event):
        if not self.is_trimming:
            self.left_handle.setVisible(True)
            self.right_handle.setVisible(True)
            current_pen = self.pen()
            current_pen.setWidth(3)
            self.setPen(current_pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self.is_trimming and not self.isSelected():
            self.left_handle.setVisible(False)
            self.right_handle.setVisible(False)
            if not self.isSelected():
                self.setPen(self.default_pen)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
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
        if self.is_trimming:
            current_rect = self.rect()
            delta_x = event.pos().x() - event.lastPos().x()

            if self.trim_side == 'left':
                new_x = current_rect.x() + delta_x
                new_width = current_rect.width() - delta_x
                if new_width >= 50:
                    current_rect.setLeft(new_x)
                    self.setRect(current_rect)
                    self.left_handle.setPos(0, 0)
                    self.right_handle.setPos(current_rect.width() - self.trim_handle_width, 0)
            elif self.trim_side == 'right':
                new_width = current_rect.width() + delta_x
                if new_width >= 50:
                    current_rect.setWidth(new_width)
                    self.setRect(current_rect)
                    self.right_handle.setPos(current_rect.width() - self.trim_handle_width, 0)
                    if self.duration_label:
                        self.duration_label.setPos(current_rect.width() - 45, 5)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_trimming:
            self.is_trimming = False
            self.trim_side = None
            self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


# ==================== TIMELINE GRAPHICS VIEW ====================

class TimelineGraphicsView(QGraphicsView):
    """Custom graphics view for timeline track with drop support"""

    def __init__(self, track_widget, parent=None):
        super().__init__(parent)
        self.track_widget = track_widget
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.scene.setSceneRect(0, 0, 10000, 50)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("background-color: #0f0f0f; border: 1px solid #252525;")
        self.setRenderHint(QPainter.Antialiasing)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Playhead line
        self.playhead_line = None
        self.create_playhead()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #1a1a1a; border: 2px solid #00bcd4;")
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("background-color: #0f0f0f; border: 1px solid #252525;")

    def dropEvent(self, event):
        if event.mimeData().hasText():
            pos = event.pos()
            scene_pos = self.mapToScene(pos)
            self.track_widget.handle_drop(scene_pos.x(), event.mimeData())
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #0f0f0f; border: 1px solid #252525;")
        else:
            event.ignore()

    def create_playhead(self):
        """Create the playhead line"""
        self.playhead_line = QGraphicsLineItem(0, 0, 0, 50)
        self.playhead_line.setPen(QPen(QColor(255, 82, 82), 3))
        self.playhead_line.setZValue(1000)
        self.scene.addItem(self.playhead_line)

        triangle = QPolygonF([QPointF(0, 0), QPointF(-6, -10), QPointF(6, -10)])
        self.playhead_head = QGraphicsPolygonItem(triangle)
        self.playhead_head.setBrush(QBrush(QColor(255, 82, 82)))
        self.playhead_head.setPen(QPen(Qt.NoPen))
        self.playhead_head.setZValue(1001)
        self.scene.addItem(self.playhead_head)

    def set_playhead_position(self, x_position):
        if self.playhead_line:
            self.playhead_line.setLine(x_position, 0, x_position, 50)
            self.playhead_head.setPos(x_position, 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            x_pos = scene_pos.x()
            item = self.scene.itemAt(scene_pos, self.transform())
            if not isinstance(item, TimelineClip):
                if hasattr(self.track_widget, 'on_timeline_clicked'):
                    self.track_widget.on_timeline_clicked(x_pos)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            selected_items = self.scene.selectedItems()
            for item in selected_items:
                if isinstance(item, TimelineClip):
                    item.delete()
        elif event.key() == Qt.Key_S:
            parent = self.track_widget.parent()
            while parent and not isinstance(parent, TimelineWidget):
                parent = parent.parent()
            if parent and isinstance(parent, TimelineWidget):
                parent.split_selected_clips_at_playhead()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        item = self.scene.itemAt(scene_pos, self.transform())

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
                background-color: #00bcd4;
            }
        """)

        if isinstance(item, TimelineClip):
            delete_action = menu.addAction("🗑️ Delete Clip")
            delete_action.triggered.connect(lambda: item.delete())

            copy_action = menu.addAction("📋 Copy")
            duplicate_action = menu.addAction("📑 Duplicate")

            menu.addSeparator()

            split_action = menu.addAction("✂️ Split at Playhead (S)")
            def split_clip():
                parent = self.track_widget.parent()
                while parent and not isinstance(parent, TimelineWidget):
                    parent = parent.parent()
                if parent and isinstance(parent, TimelineWidget):
                    item.setSelected(True)
                    parent.split_selected_clips_at_playhead()
            split_action.triggered.connect(split_clip)

            menu.addSeparator()
            speed_menu = menu.addMenu("⚡ Speed/Duration")
            for speed in ["0.5x", "1x", "1.5x", "2x", "Custom"]:
                speed_menu.addAction(speed)

            properties_action = menu.addAction("⚙️ Properties")
        else:
            paste_action = menu.addAction("📋 Paste")
            paste_action.setEnabled(False)
            menu.addSeparator()
            import_action = menu.addAction("📁 Import Media")
            marker_action = menu.addAction("📍 Add Marker")
            menu.addSeparator()
            select_all_action = menu.addAction("Select All (Ctrl+A)")
            deselect_action = menu.addAction("Deselect All")

        menu.exec_(event.globalPos())


# ==================== TIMELINE TRACK ====================

class TimelineTrack(QFrame):
    """Represents a single timeline track (video, audio, or text)"""

    def __init__(self, track_name, track_type='video', parent=None):
        super().__init__(parent)
        self.track_name = track_name
        self.track_type = track_type
        self.clips = []
        self.graphics_view = None
        self.media_item_getter = None
        self.pixels_per_second = 30

        self.is_locked = False
        self.is_visible = True
        self.is_muted = False

        self.setFixedHeight(70)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-bottom: 1px solid #252525;
            }
            QFrame:hover {
                background-color: #1e1e1e;
            }
        """)

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Track header
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-right: 1px solid #2a2a2a;
            }
        """)
        header.setFixedWidth(150)

        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(6)

        # Track name with color indicator
        name_container = QHBoxLayout()
        color_indicator = QFrame()
        color_indicator.setFixedWidth(4)
        color_map = {
            'video': '#2196f3',
            'audio': '#4caf50',
            'text': '#9c27b0'
        }
        color_indicator.setStyleSheet(f"background-color: {color_map.get(self.track_type, '#2196f3')}; border-radius: 2px;")
        name_container.addWidget(color_indicator)

        name_label = QLabel(self.track_name)
        name_label.setStyleSheet("""
            font-weight: bold;
            color: #e0e0e0;
            font-size: 12px;
            padding-left: 5px;
        """)
        name_container.addWidget(name_label)
        name_container.addStretch()
        header_layout.addLayout(name_container)

        # Track controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(6)

        # Lock button
        self.lock_btn = QPushButton("🔓")
        self.lock_btn.setMaximumWidth(28)
        self.lock_btn.setMaximumHeight(28)
        self.lock_btn.setCheckable(True)
        self.lock_btn.setToolTip("Lock/Unlock Track")
        self.lock_btn.clicked.connect(self.toggle_lock)
        self.lock_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                color: #999999;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:checked {
                background-color: #ffa726;
                color: #ffffff;
            }
        """)
        controls_layout.addWidget(self.lock_btn)

        # Visibility button
        self.visible_btn = QPushButton("👁")
        self.visible_btn.setMaximumWidth(28)
        self.visible_btn.setMaximumHeight(28)
        self.visible_btn.setCheckable(True)
        self.visible_btn.setChecked(True)
        self.visible_btn.setToolTip("Show/Hide Track")
        self.visible_btn.clicked.connect(self.toggle_visibility)
        self.visible_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:checked {
                background-color: #00bcd4;
                color: #ffffff;
            }
        """)
        controls_layout.addWidget(self.visible_btn)

        # Mute button (for audio tracks)
        if self.track_type in ['audio', 'video']:
            self.mute_btn = QPushButton("🔊")
            self.mute_btn.setMaximumWidth(28)
            self.mute_btn.setMaximumHeight(28)
            self.mute_btn.setCheckable(True)
            self.mute_btn.setToolTip("Mute/Unmute Audio")
            self.mute_btn.clicked.connect(self.toggle_mute)
            self.mute_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a2a;
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #3a3a3a;
                }
                QPushButton:checked {
                    background-color: #f44336;
                    color: #ffffff;
                }
            """)
            controls_layout.addWidget(self.mute_btn)

        controls_layout.addStretch()
        header_layout.addLayout(controls_layout)

        header.setLayout(header_layout)
        layout.addWidget(header)

        # Track content area
        self.graphics_view = TimelineGraphicsView(self)
        layout.addWidget(self.graphics_view, 1)

        self.setLayout(layout)

    def toggle_lock(self):
        self.is_locked = self.lock_btn.isChecked()
        if self.is_locked:
            self.lock_btn.setText("🔒")
            self.graphics_view.setEnabled(False)
        else:
            self.lock_btn.setText("🔓")
            self.graphics_view.setEnabled(True)

    def toggle_visibility(self):
        self.is_visible = self.visible_btn.isChecked()
        if not self.is_visible:
            self.visible_btn.setText("👁‍🗨")
        else:
            self.visible_btn.setText("👁")

    def toggle_mute(self):
        self.is_muted = self.mute_btn.isChecked()
        if self.is_muted:
            self.mute_btn.setText("🔇")
        else:
            self.mute_btn.setText("🔊")

    def handle_drop(self, x_position, mime_data):
        file_path = mime_data.text()
        if self.media_item_getter:
            media_item = self.media_item_getter(file_path)
            if media_item:
                self.create_clip_at_position(x_position, media_item)

    def create_clip_at_position(self, x_pos, media_item):
        clip_height = 55
        if hasattr(media_item, 'duration') and media_item.duration > 0:
            clip_width = media_item.duration * self.pixels_per_second
        else:
            clip_width = 3 * self.pixels_per_second
        clip_width = max(clip_width, 60)

        clip = TimelineClip(x_pos, 5, clip_width, clip_height, media_item, track=self)
        self.graphics_view.scene.addItem(clip)
        self.clips.append(clip)

    def remove_clip(self, clip):
        if clip in self.clips:
            if self.graphics_view and self.graphics_view.scene:
                self.graphics_view.scene.removeItem(clip)
            self.clips.remove(clip)

    def add_split_clip(self, clip):
        if self.graphics_view and self.graphics_view.scene:
            self.graphics_view.scene.addItem(clip)
            self.clips.append(clip)

    def set_playhead_position(self, x_position):
        if self.graphics_view:
            self.graphics_view.set_playhead_position(x_position)

    def on_timeline_clicked(self, x_position):
        time_seconds = x_position / self.pixels_per_second
        parent = self.parent()
        while parent and not isinstance(parent, TimelineWidget):
            parent = parent.parent()
        if parent and isinstance(parent, TimelineWidget):
            parent.on_timeline_seek(time_seconds)


# ==================== TIMELINE WIDGET ====================

class TimelineWidget(QWidget):
    """Minimal timeline widget - Only Tools Bar, Tracks, Status Bar"""

    clip_selected = pyqtSignal(object)
    playhead_moved = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tracks = []
        self.clips = []
        self.playhead_position = 0.0
        self.zoom_level = 1.0
        self.snap_enabled = True
        self.media_item_getter = None
        self.pixels_per_second = 30

        # Project info
        self.project_name = "Untitled Project"
        self.project_duration = 0.0
        self.project_fps = 30

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Timeline Tools Bar
        tools_bar = self.create_timeline_tools_bar()
        main_layout.addWidget(tools_bar)

        # Main Timeline Area (Tracks)
        timeline_view = self.create_timeline_view()
        main_layout.addWidget(timeline_view, 1)

        # Timeline Status Bar
        status_bar = self.create_status_bar()
        main_layout.addWidget(status_bar)

        self.setLayout(main_layout)

    def create_timeline_tools_bar(self):
        """Create timeline tools bar"""
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #222222; border-bottom: 1px solid #2a2a2a;")
        toolbar.setFixedHeight(45)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(12)

        # Selection tools
        tools_label = QLabel("Tools:")
        tools_label.setStyleSheet("color: #888888; font-weight: bold; font-size: 11px;")
        layout.addWidget(tools_label)

        tool_buttons = [
            ("✋ Select", "V", True),
            ("✂️ Split", "S", False),
            ("📏 Trim", "T", False),
        ]

        for name, shortcut, is_default in tool_buttons:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(is_default)
            btn.setToolTip(f"Shortcut: {shortcut}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a2a;
                    color: #e0e0e0;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 14px;
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
        zoom_out_btn.setMaximumWidth(32)
        zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_out_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
        """)
        layout.addWidget(zoom_out_btn)

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setMaximumWidth(140)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        layout.addWidget(self.zoom_slider)

        zoom_in_btn = QPushButton("➕")
        zoom_in_btn.setMaximumWidth(32)
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_in_btn.setStyleSheet(zoom_out_btn.styleSheet())
        layout.addWidget(zoom_in_btn)

        fit_btn = QPushButton("⤢ Fit")
        fit_btn.clicked.connect(self.fit_to_timeline)
        fit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                color: #e0e0e0;
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
        self.snap_check.stateChanged.connect(self.on_snap_toggled)
        layout.addWidget(self.snap_check)

        # Marker button
        marker_btn = QPushButton("🚩 Marker")
        marker_btn.setStyleSheet(fit_btn.styleSheet())
        layout.addWidget(marker_btn)

        layout.addStretch()

        # Add track button
        add_track_btn = QPushButton("➕ Add Track")
        add_track_btn.clicked.connect(self.add_track)
        add_track_btn.setStyleSheet("""
            QPushButton {
                background-color: #00bcd4;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4dd0e1;
            }
        """)
        layout.addWidget(add_track_btn)

        toolbar.setLayout(layout)
        return toolbar

    def create_timeline_view(self):
        container = QFrame()
        container.setStyleSheet("background-color: #141414; border: none;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Empty state prompt
        self.import_prompt = QFrame()
        self.import_prompt.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px dashed #666666;
                border-radius: 12px;
                margin: 20px;
            }
        """)
        self.import_prompt.setMinimumHeight(200)

        import_layout = QVBoxLayout()
        import_layout.setAlignment(Qt.AlignCenter)

        import_icon = QLabel("📥")
        import_icon.setStyleSheet("font-size: 56px;")
        import_icon.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(import_icon)

        import_label = QLabel("Import media or drag from Media Library")
        import_label.setStyleSheet("font-size: 16px; color: #e0e0e0; font-weight: bold;")
        import_label.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(import_label)

        import_hint = QLabel("Double-click media items to add to timeline")
        import_hint.setStyleSheet("font-size: 13px; color: #999999;")
        import_hint.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(import_hint)

        self.import_prompt.setLayout(import_layout)
        layout.addWidget(self.import_prompt)

        # Tracks container
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

    def create_status_bar(self):
        status_bar = QFrame()
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet("""
            QFrame {
                background-color: #0a0a0a;
                border-top: 1px solid #1a1a1a;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(15)

        self.project_name_label = QLabel(self.project_name)
        self.project_name_label.setStyleSheet("color: #00bcd4; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.project_name_label)

        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #404040;")
        layout.addWidget(sep1)

        self.duration_status_label = QLabel("Duration: 00:00:00")
        self.duration_status_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(self.duration_status_label)

        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #404040;")
        layout.addWidget(sep2)

        self.clips_count_label = QLabel("Clips: 0")
        self.clips_count_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(self.clips_count_label)

        sep3 = QLabel("|")
        sep3.setStyleSheet("color: #404040;")
        layout.addWidget(sep3)

        self.fps_label = QLabel(f"FPS: {self.project_fps}")
        self.fps_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(self.fps_label)

        sep4 = QLabel("|")
        sep4.setStyleSheet("color: #404040;")
        layout.addWidget(sep4)

        self.resolution_label = QLabel("Resolution: 1920x1080")
        self.resolution_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(self.resolution_label)

        layout.addStretch()

        self.status_message_label = QLabel("")
        self.status_message_label.setStyleSheet("color: #4caf50; font-size: 11px;")
        layout.addWidget(self.status_message_label)

        status_bar.setLayout(layout)
        return status_bar

    def add_initial_tracks(self):
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
        track_num = len(self.tracks) + 1
        track = TimelineTrack(f"Track {track_num}", "video")
        self.tracks.append(track)
        self.tracks_layout.addWidget(track)

    def zoom_in(self):
        current_value = self.zoom_slider.value()
        self.zoom_slider.setValue(min(200, current_value + 10))

    def zoom_out(self):
        current_value = self.zoom_slider.value()
        self.zoom_slider.setValue(max(10, current_value - 10))

    def on_zoom_changed(self, value):
        self.zoom_level = value / 100.0

    def fit_to_timeline(self):
        self.zoom_slider.setValue(100)

    def on_snap_toggled(self, state):
        self.snap_enabled = (state == Qt.Checked)

    def set_media_item_getter(self, getter_func):
        self.media_item_getter = getter_func
        for track in self.tracks:
            track.media_item_getter = getter_func

    def add_clip(self, media_item, track_index=0):
        if len(self.clips) == 0:
            self.import_prompt.hide()

    def remove_clip(self, clip):
        if clip in self.clips:
            self.clips.remove(clip)

    def update_playhead(self, time_seconds):
        x_position = time_seconds * self.pixels_per_second
        for track in self.tracks:
            track.set_playhead_position(x_position)
        self.playhead_position = time_seconds

    def on_timeline_seek(self, time_seconds):
        self.update_playhead(time_seconds)
        self.playhead_moved.emit(time_seconds)

    def split_selected_clips_at_playhead(self):
        playhead_x = self.playhead_position * self.pixels_per_second
        split_count = 0
        for track in self.tracks:
            for clip in list(track.clips):
                if clip.isSelected():
                    clip_rect = clip.sceneBoundingRect()
                    if clip_rect.x() < playhead_x < (clip_rect.x() + clip_rect.width()):
                        clip.split_at_position(playhead_x)
                        split_count += 1
        return split_count

    def update_status_bar(self):
        total_clips = sum(len(track.clips) for track in self.tracks)
        self.clips_count_label.setText(f"Clips: {total_clips}")
