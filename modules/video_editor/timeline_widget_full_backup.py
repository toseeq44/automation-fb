"""
modules/video_editor/timeline_widget.py
Professional Timeline Widget for Video Editing - COMPLETE V2
Multi-track timeline with comprehensive features:
- Upper Timeline Area (playback controls, scrubber, time display)
- Middle Control Section (navigation, speed control)
- Timeline Ruler & Zoom Bar
- Timeline Tools Bar (selection tools, zoom, snap, markers)
- Track Headers with full controls
- Timeline Canvas with empty state
- Clips with visual design and interactions
- Playhead with full functionality
- Context menus and keyboard shortcuts
- Timeline Status Bar
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
        self.trim_side = None  # 'left' or 'right'
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
            # Snap to grid/clips if needed
            pass
        elif change == QGraphicsRectItem.ItemSelectedChange:
            # Highlight when selected
            if value:  # Selected
                self.setPen(self.selected_pen)
            else:  # Deselected
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

        # Get clip bounds
        clip_rect = self.sceneBoundingRect()
        clip_start = clip_rect.x()
        clip_end = clip_rect.x() + clip_rect.width()

        # Check if position is within clip bounds
        if x_position <= clip_start or x_position >= clip_end:
            logger.warning("Split position outside clip bounds")
            return None

        # Calculate split point relative to clip
        split_offset = x_position - clip_start

        # Create right clip (from split to end)
        right_width = clip_rect.width() - split_offset
        right_clip = TimelineClip(
            x_position,
            self.pos().y(),
            right_width,
            clip_rect.height(),
            self.clip_data,
            track=self.track
        )

        # Resize this clip (left part)
        new_rect = self.rect()
        new_rect.setWidth(split_offset)
        self.setRect(new_rect)
        self.right_handle.setPos(new_rect.width() - self.trim_handle_width, 0)

        # Update duration label position
        if self.duration_label:
            self.duration_label.setPos(new_rect.width() - 45, 5)

        # Add right clip to track
        self.track.add_split_clip(right_clip)

        logger.info(f"Split clip '{self.clip_data.file_name}' at position {split_offset}px")

        return right_clip

    def hoverEnterEvent(self, event):
        """Show trim handles on hover"""
        if not self.is_trimming:
            self.left_handle.setVisible(True)
            self.right_handle.setVisible(True)
            # Brighten clip on hover
            current_pen = self.pen()
            current_pen.setWidth(3)
            self.setPen(current_pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Hide trim handles when not hovering"""
        if not self.is_trimming and not self.isSelected():
            self.left_handle.setVisible(False)
            self.right_handle.setVisible(False)
            # Reset pen width
            if not self.isSelected():
                self.setPen(self.default_pen)
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
                    # Update duration label position
                    if self.duration_label:
                        self.duration_label.setPos(current_rect.width() - 45, 5)

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


# ==================== TIMELINE GRAPHICS VIEW ====================

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
        self.setStyleSheet("background-color: #0f0f0f; border: 1px solid #252525;")
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
            # Highlight drop zone
            self.setStyleSheet("background-color: #1a1a1a; border: 2px solid #00bcd4;")
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Handle drag move"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Reset styling when drag leaves"""
        self.setStyleSheet("background-color: #0f0f0f; border: 1px solid #252525;")

    def dropEvent(self, event):
        """Handle drop event - create clip on timeline"""
        if event.mimeData().hasText():
            # Get drop position
            pos = event.pos()
            scene_pos = self.mapToScene(pos)

            # Notify track widget
            self.track_widget.handle_drop(scene_pos.x(), event.mimeData())
            event.acceptProposedAction()

            # Reset styling
            self.setStyleSheet("background-color: #0f0f0f; border: 1px solid #252525;")
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
        elif event.key() == Qt.Key_S:
            # Split selected clips at playhead
            # Need to access parent timeline widget
            parent = self.track_widget.parent()
            while parent and not isinstance(parent, TimelineWidget):
                parent = parent.parent()

            if parent and isinstance(parent, TimelineWidget):
                parent.split_selected_clips_at_playhead()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """Show context menu for clips"""
        # Get item at position
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
            QMenu::separator {
                height: 1px;
                background: #3a3a3a;
                margin: 4px 0;
            }
        """)

        if isinstance(item, TimelineClip):
            # Clip-specific menu
            # Delete action
            delete_action = menu.addAction("🗑️ Delete Clip")
            delete_action.triggered.connect(lambda: item.delete())

            # Copy action
            copy_action = menu.addAction("📋 Copy")

            # Duplicate action
            duplicate_action = menu.addAction("📑 Duplicate")

            menu.addSeparator()

            # Split action
            split_action = menu.addAction("✂️ Split at Playhead (S)")
            split_action.setToolTip("Split clip at playhead position")

            def split_clip():
                # Get parent timeline widget
                parent = self.track_widget.parent()
                while parent and not isinstance(parent, TimelineWidget):
                    parent = parent.parent()

                if parent and isinstance(parent, TimelineWidget):
                    # Select the clip first
                    item.setSelected(True)
                    parent.split_selected_clips_at_playhead()

            split_action.triggered.connect(split_clip)

            menu.addSeparator()

            # Speed/Duration submenu
            speed_menu = menu.addMenu("⚡ Speed/Duration")
            for speed in ["0.5x", "1x", "1.5x", "2x", "Custom"]:
                speed_menu.addAction(speed)

            # Properties action
            properties_action = menu.addAction("⚙️ Properties")

        else:
            # Empty timeline menu
            paste_action = menu.addAction("📋 Paste")
            paste_action.setEnabled(False)  # Enable if clipboard has content

            menu.addSeparator()

            import_action = menu.addAction("📁 Import Media")
            marker_action = menu.addAction("📍 Add Marker")

            menu.addSeparator()

            select_all_action = menu.addAction("Select All (Ctrl+A)")
            deselect_action = menu.addAction("Deselect All")

        # Show menu
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
        self.media_item_getter = None  # Function to get MediaItem by path
        self.pixels_per_second = 30  # Default: 30 pixels = 1 second

        # Track state
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
        """Initialize track UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Track header (controls)
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

        # Color indicator
        color_indicator = QFrame()
        color_indicator.setFixedWidth(4)
        color_map = {
            'video': '#2196f3',  # Blue
            'audio': '#4caf50',  # Green
            'text': '#9c27b0'    # Purple
        }
        color_indicator.setStyleSheet(f"background-color: {color_map.get(self.track_type, '#2196f3')}; border-radius: 2px;")
        name_container.addWidget(color_indicator)

        name_label = QLabel(self.track_name)
        name_label.setStyleSheet(f"""
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

        # Track content area (QGraphicsView for clips)
        self.graphics_view = TimelineGraphicsView(self)
        layout.addWidget(self.graphics_view, 1)

        self.setLayout(layout)

    def toggle_lock(self):
        """Toggle track lock state"""
        self.is_locked = self.lock_btn.isChecked()
        if self.is_locked:
            self.lock_btn.setText("🔒")
            self.graphics_view.setEnabled(False)
            self.setStyleSheet("""
                QFrame {
                    background-color: #151515;
                    border-bottom: 1px solid #252525;
                    opacity: 0.7;
                }
            """)
        else:
            self.lock_btn.setText("🔓")
            self.graphics_view.setEnabled(True)
            self.setStyleSheet("""
                QFrame {
                    background-color: #1a1a1a;
                    border-bottom: 1px solid #252525;
                }
            """)
        logger.info(f"Track '{self.track_name}' locked: {self.is_locked}")

    def toggle_visibility(self):
        """Toggle track visibility"""
        self.is_visible = self.visible_btn.isChecked()
        if not self.is_visible:
            self.visible_btn.setText("👁‍🗨")  # Hidden eye
            self.graphics_view.setStyleSheet("background-color: #0f0f0f; border: 1px solid #252525; opacity: 0.5;")
        else:
            self.visible_btn.setText("👁")
            self.graphics_view.setStyleSheet("background-color: #0f0f0f; border: 1px solid #252525;")
        logger.info(f"Track '{self.track_name}' visible: {self.is_visible}")

    def toggle_mute(self):
        """Toggle track mute state"""
        self.is_muted = self.mute_btn.isChecked()
        if self.is_muted:
            self.mute_btn.setText("🔇")
        else:
            self.mute_btn.setText("🔊")
        logger.info(f"Track '{self.track_name}' muted: {self.is_muted}")

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
        clip_height = 55

        # Calculate clip width based on duration
        if hasattr(media_item, 'duration') and media_item.duration > 0:
            clip_width = media_item.duration * self.pixels_per_second
        else:
            # Default width for images or items without duration (3 seconds)
            clip_width = 3 * self.pixels_per_second

        # Minimum width for visibility
        clip_width = max(clip_width, 60)

        # Create clip with track reference
        clip = TimelineClip(x_pos, 5, clip_width, clip_height, media_item, track=self)

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

    def add_split_clip(self, clip):
        """Add a clip created from split operation"""
        if self.graphics_view and self.graphics_view.scene:
            self.graphics_view.scene.addItem(clip)
            self.clips.append(clip)
            logger.info(f"Added split clip to {self.track_name}")

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


# ==================== TIMELINE WIDGET ====================

class TimelineWidget(QWidget):
    """
    Professional multi-track timeline widget with comprehensive features
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
        self.playback_speed = 1.0

        # Project info
        self.project_name = "Untitled Project"
        self.project_duration = 0.0
        self.project_fps = 30

        self.init_ui()

    def init_ui(self):
        """Initialize timeline UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === SECTION 1: UPPER TIMELINE AREA ===
        upper_area = self.create_upper_timeline_area()
        main_layout.addWidget(upper_area)

        # === SECTION 2: MIDDLE CONTROL SECTION ===
        middle_controls = self.create_middle_control_section()
        main_layout.addWidget(middle_controls)

        # === SECTION 3: TIMELINE RULER ===
        timeline_ruler = self.create_timeline_ruler()
        main_layout.addWidget(timeline_ruler)

        # === SECTION 4: TIMELINE TOOLS BAR ===
        tools_bar = self.create_timeline_tools_bar()
        main_layout.addWidget(tools_bar)

        # === SECTION 5-10: MAIN TIMELINE AREA (Tracks) ===
        timeline_view = self.create_timeline_view()
        main_layout.addWidget(timeline_view, 1)

        # === SECTION 13: TIMELINE STATUS BAR ===
        status_bar = self.create_status_bar()
        main_layout.addWidget(status_bar)

        self.setLayout(main_layout)

    # ==================== SECTION 1: UPPER TIMELINE AREA ====================

    def create_upper_timeline_area(self):
        """Create upper timeline area with playback controls, scrubber, time display"""
        container = QFrame()
        container.setFixedHeight(80)
        container.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-bottom: 1px solid #2a2a2a;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # Row 1: Playback controls and time display
        controls_row = QHBoxLayout()

        # Playback control buttons
        button_style = """
            QPushButton {
                background-color: %s;
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 16px;
                min-width: 40px;
                max-width: 40px;
                min-height: 40px;
                max-height: 40px;
            }
            QPushButton:hover {
                background-color: %s;
                transform: scale(1.05);
            }
            QPushButton:pressed {
                transform: scale(0.95);
            }
        """

        # Skip backward button
        self.skip_back_btn = QPushButton("⏮")
        self.skip_back_btn.setStyleSheet(button_style % ("#e91e63", "#f06292"))
        self.skip_back_btn.setToolTip("Skip Backward 5s")
        self.skip_back_btn.clicked.connect(lambda: self.skip_playhead(-5))
        controls_row.addWidget(self.skip_back_btn)

        # Play/Pause button
        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setStyleSheet(button_style % ("#00bcd4", "#4dd0e1"))
        self.play_pause_btn.setToolTip("Play/Pause (Space)")
        controls_row.addWidget(self.play_pause_btn)

        # Stop button
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setStyleSheet(button_style % ("#f44336", "#e57373"))
        self.stop_btn.setToolTip("Stop Playback")
        controls_row.addWidget(self.stop_btn)

        controls_row.addSpacing(20)

        # Time display (left)
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setStyleSheet("""
            font-family: 'Courier New', monospace;
            font-size: 14px;
            color: #00bcd4;
            font-weight: bold;
            background-color: #1a1a1a;
            padding: 4px 10px;
            border-radius: 4px;
        """)
        controls_row.addWidget(self.current_time_label)

        controls_row.addStretch()

        # Status indicator
        self.status_indicator = QLabel("⏸ Paused")
        self.status_indicator.setStyleSheet("""
            font-size: 12px;
            color: #ffeb3b;
            background-color: rgba(0, 0, 0, 0.4);
            padding: 4px 12px;
            border-radius: 3px;
            font-weight: bold;
        """)
        controls_row.addWidget(self.status_indicator)

        controls_row.addStretch()

        # Time display (right) - total duration
        self.total_time_label = QLabel("00:00")
        self.total_time_label.setStyleSheet("""
            font-family: 'Courier New', monospace;
            font-size: 14px;
            color: #e0e0e0;
            background-color: #1a1a1a;
            padding: 4px 10px;
            border-radius: 4px;
        """)
        controls_row.addWidget(self.total_time_label)

        layout.addLayout(controls_row)

        # Row 2: Timeline scrubber
        scrubber_row = QHBoxLayout()

        self.timeline_scrubber = QSlider(Qt.Horizontal)
        self.timeline_scrubber.setMinimum(0)
        self.timeline_scrubber.setMaximum(1000)
        self.timeline_scrubber.setValue(0)
        self.timeline_scrubber.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #2a2a2a;
                height: 8px;
                border-radius: 4px;
                border: 1px solid #404040;
            }
            QSlider::sub-page:horizontal {
                background: #00bcd4;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #00bcd4;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #00bcd4;
                box-shadow: 0 2px 8px rgba(0, 188, 212, 0.5);
            }
        """)
        self.timeline_scrubber.sliderMoved.connect(self.on_scrubber_moved)

        scrubber_row.addWidget(self.timeline_scrubber)

        layout.addLayout(scrubber_row)

        container.setLayout(layout)
        return container

    # ==================== SECTION 2: MIDDLE CONTROL SECTION ====================

    def create_middle_control_section(self):
        """Create middle control section with navigation and speed control"""
        container = QFrame()
        container.setFixedHeight(55)
        container.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-bottom: 1px solid #2a2a2a;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # Navigation buttons
        nav_button_style = """
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 4px;
                font-size: 14px;
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                max-height: 36px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
        """

        # Jump to start
        jump_start_btn = QPushButton("⏮")
        jump_start_btn.setStyleSheet(nav_button_style)
        jump_start_btn.setToolTip("Jump to Start (Home)")
        jump_start_btn.clicked.connect(lambda: self.jump_to_position(0))
        layout.addWidget(jump_start_btn)

        # Previous frame
        prev_frame_btn = QPushButton("◀")
        prev_frame_btn.setStyleSheet(nav_button_style)
        prev_frame_btn.setToolTip("Previous Frame (←)")
        prev_frame_btn.clicked.connect(lambda: self.step_frame(-1))
        layout.addWidget(prev_frame_btn)

        # Play (larger)
        play_large_btn = QPushButton("▶")
        play_large_btn.setStyleSheet("""
            QPushButton {
                background-color: #00bcd4;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                min-width: 45px;
                max-width: 45px;
                min-height: 36px;
                max-height: 36px;
            }
            QPushButton:hover {
                background-color: #4dd0e1;
            }
        """)
        play_large_btn.setToolTip("Play (Space)")
        layout.addWidget(play_large_btn)

        # Next frame
        next_frame_btn = QPushButton("▶")
        next_frame_btn.setStyleSheet(nav_button_style)
        next_frame_btn.setToolTip("Next Frame (→)")
        next_frame_btn.clicked.connect(lambda: self.step_frame(1))
        layout.addWidget(next_frame_btn)

        # Jump to end
        jump_end_btn = QPushButton("⏭")
        jump_end_btn.setStyleSheet(nav_button_style)
        jump_end_btn.setToolTip("Jump to End (End)")
        jump_end_btn.clicked.connect(lambda: self.jump_to_end())
        layout.addWidget(jump_end_btn)

        layout.addSpacing(20)

        # Speed control
        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet("color: #999999; font-size: 12px;")
        layout.addWidget(speed_label)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25x", "0.5x", "0.75x", "1x", "1.25x", "1.5x", "2x", "3x", "5x", "10x"])
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.setMinimumWidth(100)
        self.speed_combo.setStyleSheet("""
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px 12px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QComboBox:hover {
                background-color: #3a3a3a;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #404040;
                selection-background-color: #00bcd4;
            }
        """)
        self.speed_combo.currentTextChanged.connect(self.on_speed_changed)
        layout.addWidget(self.speed_combo)

        layout.addStretch()

        container.setLayout(layout)
        return container

    # ==================== SECTION 3: TIMELINE RULER ====================

    def create_timeline_ruler(self):
        """Create timeline ruler with time markers"""
        container = QFrame()
        container.setFixedHeight(35)
        container.setStyleSheet("""
            QFrame {
                background-color: #282828;
                border-bottom: 1px solid #404040;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(150, 0, 0, 0)  # Offset for track headers
        layout.setSpacing(0)

        # Time ruler label (placeholder - would need custom painting for actual ruler)
        ruler_label = QLabel("Time Ruler: 0:00 | 0:05 | 0:10 | 0:15 | 0:20 | 0:25 | 0:30...")
        ruler_label.setStyleSheet("""
            color: #999999;
            font-size: 11px;
            font-family: 'Courier New', monospace;
            padding: 8px;
        """)
        layout.addWidget(ruler_label)

        container.setLayout(layout)
        return container

    # ==================== SECTION 4: TIMELINE TOOLS BAR ====================

    def create_timeline_tools_bar(self):
        """Create timeline tools bar with selection tools, zoom, snap, markers"""
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
        zoom_out_btn.setToolTip("Zoom out (Ctrl+-)")
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
        self.zoom_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #2a2a2a;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #00bcd4;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00bcd4;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        layout.addWidget(self.zoom_slider)

        zoom_in_btn = QPushButton("➕")
        zoom_in_btn.setMaximumWidth(32)
        zoom_in_btn.setToolTip("Zoom in (Ctrl++)")
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_in_btn.setStyleSheet(zoom_out_btn.styleSheet())
        layout.addWidget(zoom_in_btn)

        fit_btn = QPushButton("⤢ Fit")
        fit_btn.setToolTip("Fit to timeline (Shift+Z)")
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
        self.snap_check.setToolTip("Enable snapping to clips/markers (S)")
        self.snap_check.stateChanged.connect(self.on_snap_toggled)
        self.snap_check.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
                font-size: 11px;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #404040;
                background-color: #2a2a2a;
            }
            QCheckBox::indicator:checked {
                background-color: #00bcd4;
                border-color: #00bcd4;
            }
        """)
        layout.addWidget(self.snap_check)

        # Marker button
        marker_btn = QPushButton("🚩 Marker")
        marker_btn.setToolTip("Add marker at playhead (M)")
        marker_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                color: #e0e0e0;
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

    # ==================== SECTION 5-10: MAIN TIMELINE AREA ====================

    def create_timeline_view(self):
        """Create the main timeline view with tracks"""
        container = QFrame()
        container.setStyleSheet("background-color: #141414; border: none;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Empty state prompt (when no clips)
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

    # ==================== SECTION 13: STATUS BAR ====================

    def create_status_bar(self):
        """Create timeline status bar"""
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

        # Project name
        self.project_name_label = QLabel(self.project_name)
        self.project_name_label.setStyleSheet("color: #00bcd4; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.project_name_label)

        # Separator
        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #404040;")
        layout.addWidget(sep1)

        # Duration
        self.duration_status_label = QLabel("Duration: 00:00:00")
        self.duration_status_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(self.duration_status_label)

        # Separator
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #404040;")
        layout.addWidget(sep2)

        # Clips count
        self.clips_count_label = QLabel("Clips: 0")
        self.clips_count_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(self.clips_count_label)

        # Separator
        sep3 = QLabel("|")
        sep3.setStyleSheet("color: #404040;")
        layout.addWidget(sep3)

        # FPS
        self.fps_label = QLabel(f"FPS: {self.project_fps}")
        self.fps_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(self.fps_label)

        # Separator
        sep4 = QLabel("|")
        sep4.setStyleSheet("color: #404040;")
        layout.addWidget(sep4)

        # Resolution
        self.resolution_label = QLabel("Resolution: 1920x1080")
        self.resolution_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(self.resolution_label)

        layout.addStretch()

        # Status message
        self.status_message_label = QLabel("")
        self.status_message_label.setStyleSheet("color: #4caf50; font-size: 11px;")
        layout.addWidget(self.status_message_label)

        status_bar.setLayout(layout)
        return status_bar

    # ==================== HELPER METHODS ====================

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

    def on_scrubber_moved(self, position):
        """Handle timeline scrubber movement"""
        # Convert slider position to time
        time_seconds = (position / 1000.0) * self.project_duration
        self.update_playhead(time_seconds)
        self.current_time_label.setText(self.format_time(time_seconds))

    def on_speed_changed(self, speed_text):
        """Handle playback speed change"""
        try:
            self.playback_speed = float(speed_text.replace('x', ''))
            logger.info(f"Playback speed changed to: {self.playback_speed}x")
        except ValueError:
            pass

    def skip_playhead(self, seconds):
        """Skip playhead by specified seconds"""
        new_time = max(0, self.playhead_position + seconds)
        self.update_playhead(new_time)
        logger.info(f"Skipped to {new_time}s")

    def jump_to_position(self, position):
        """Jump to specific position"""
        self.update_playhead(position)
        logger.info(f"Jumped to {position}s")

    def jump_to_end(self):
        """Jump to end of timeline"""
        self.update_playhead(self.project_duration)
        logger.info("Jumped to end")

    def step_frame(self, direction):
        """Step one frame forward or backward"""
        frame_duration = 1.0 / self.project_fps
        new_time = self.playhead_position + (direction * frame_duration)
        new_time = max(0, min(new_time, self.project_duration))
        self.update_playhead(new_time)
        logger.debug(f"Stepped frame: {direction}, new time: {new_time}s")

    def format_time(self, seconds):
        """Format seconds to MM:SS or HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

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

        # Update time displays
        self.current_time_label.setText(self.format_time(time_seconds))

    def on_timeline_seek(self, time_seconds):
        """Handle seek request from timeline click"""
        logger.info(f"Seeking to {time_seconds}s")

        # Update playhead visually
        self.update_playhead(time_seconds)

        # Emit signal for video player to seek
        self.playhead_moved.emit(time_seconds)

    def split_selected_clips_at_playhead(self):
        """Split all selected clips at current playhead position"""
        playhead_x = self.playhead_position * self.pixels_per_second
        split_count = 0

        for track in self.tracks:
            # Get all selected clips in this track
            for clip in list(track.clips):  # Use list() to avoid modification during iteration
                if clip.isSelected():
                    # Check if playhead is within clip bounds
                    clip_rect = clip.sceneBoundingRect()
                    if clip_rect.x() < playhead_x < (clip_rect.x() + clip_rect.width()):
                        # Split at playhead
                        clip.split_at_position(playhead_x)
                        split_count += 1

        if split_count > 0:
            logger.info(f"Split {split_count} clip(s) at playhead position {self.playhead_position}s")
        else:
            logger.info("No clips to split at playhead position")

        return split_count

    def update_status_bar(self):
        """Update status bar information"""
        total_clips = sum(len(track.clips) for track in self.tracks)
        self.clips_count_label.setText(f"Clips: {total_clips}")
        self.duration_status_label.setText(f"Duration: {self.format_time(self.project_duration)}")
