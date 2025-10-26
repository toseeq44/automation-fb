"""
modules/video_editor/media_library_enhanced.py
Enhanced Media Library with Professional Filters and Card Grid
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QFrame, QScrollArea, QGridLayout,
    QMenu, QAction, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QMimeData
from PyQt5.QtGui import QPixmap, QFont, QColor, QPalette, QDrag, QCursor
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
import os

from modules.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MediaItem:
    """Enhanced media item with filter attributes"""
    file_path: str
    file_name: str
    file_type: str  # 'video', 'audio', 'image'
    file_size: int
    duration: float = 0.0
    width: int = 0
    height: int = 0
    thumbnail: Optional[QPixmap] = None
    fps: float = 0.0
    imported_at: datetime = None

    # Filter attributes
    is_zoomed: bool = False
    is_blurred: bool = False
    blur_level: str = "none"  # "none", "low", "medium", "high"
    is_ai_enhanced: bool = False
    ai_features: List[str] = None
    speed_factor: float = 1.0
    is_processing: bool = False
    is_new: bool = False

    def __post_init__(self):
        if self.imported_at is None:
            self.imported_at = datetime.now()
        if self.ai_features is None:
            self.ai_features = []
        # Check if new (imported in last 24 hours)
        if self.imported_at:
            hours_since_import = (datetime.now() - self.imported_at).total_seconds() / 3600
            self.is_new = hours_since_import < 24


class FilterDropdown(QComboBox):
    """Custom styled dropdown for filters"""

    def __init__(self, icon_text, parent=None):
        super().__init__(parent)
        self.icon_text = icon_text
        self.setMinimumWidth(110)
        self.setMaximumWidth(120)
        self.setStyleSheet("""
            QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }
            QComboBox:hover {
                background-color: #353535;
                border-color: #00bcd4;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                border: 1px solid #00bcd4;
                border-radius: 6px;
                selection-background-color: #00bcd4;
                selection-color: #ffffff;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                padding: 10px 15px;
                border-radius: 4px;
                color: #e0e0e0;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #00bcd4;
                color: #ffffff;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #00bcd4;
                color: #ffffff;
            }
        """)


class MediaCard(QFrame):
    """Professional media card with thumbnail, info, and interactions"""

    clicked = pyqtSignal(object)  # Emits MediaItem
    double_clicked = pyqtSignal(object)

    def __init__(self, media_item: MediaItem, parent=None):
        super().__init__(parent)
        self.media_item = media_item
        self.is_selected = False
        self.setFixedSize(170, 240)
        self.setCursor(Qt.PointingHandCursor)

        self.init_ui()
        self.update_style()

    def init_ui(self):
        """Initialize card UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Thumbnail area
        self.thumbnail_frame = QFrame()
        self.thumbnail_frame.setFixedHeight(120)
        self.thumbnail_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
        """)

        thumb_layout = QVBoxLayout()
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        thumb_layout.setAlignment(Qt.AlignCenter)

        # Thumbnail or icon
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        if self.media_item.thumbnail:
            scaled = self.media_item.thumbnail.scaled(
                170, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)
        else:
            # Show icon based on type
            icons = {
                'video': '🎬',
                'audio': '🎵',
                'image': '🖼️'
            }
            self.thumb_label.setText(icons.get(self.media_item.file_type, '📄'))
            self.thumb_label.setStyleSheet("font-size: 48px;")

        thumb_layout.addWidget(self.thumb_label)

        # Play button overlay (for video)
        if self.media_item.file_type == 'video':
            play_overlay = QLabel('▶')
            play_overlay.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 32px;
                    background-color: rgba(0, 0, 0, 0.5);
                    border-radius: 20px;
                    padding: 8px 12px;
                }
            """)
            play_overlay.setAlignment(Qt.AlignCenter)
            thumb_layout.addWidget(play_overlay, 0, Qt.AlignCenter)

        # Duration badge
        if self.media_item.duration > 0:
            mins, secs = divmod(int(self.media_item.duration), 60)
            duration_text = f"{mins:02d}:{secs:02d}"

            duration_badge = QLabel(duration_text)
            duration_badge.setStyleSheet("""
                QLabel {
                    background-color: rgba(0, 0, 0, 0.8);
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-family: 'Courier New', monospace;
                }
            """)
            thumb_layout.addWidget(duration_badge, 0, Qt.AlignRight | Qt.AlignBottom)

        # Badges (NEW, Processing, etc.)
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(4)

        if self.media_item.is_new:
            new_badge = QLabel("NEW")
            new_badge.setStyleSheet("""
                QLabel {
                    background-color: #4caf50;
                    color: white;
                    padding: 3px 8px;
                    border-radius: 3px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)
            badges_layout.addWidget(new_badge)

        if self.media_item.is_processing:
            proc_badge = QLabel("⟳ Processing")
            proc_badge.setStyleSheet("""
                QLabel {
                    background-color: #ff9800;
                    color: white;
                    padding: 3px 8px;
                    border-radius: 3px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)
            badges_layout.addWidget(proc_badge)

        badges_layout.addStretch()
        thumb_layout.addLayout(badges_layout)

        self.thumbnail_frame.setLayout(thumb_layout)
        layout.addWidget(self.thumbnail_frame)

        # Info area
        info_frame = QFrame()
        info_frame.setFixedHeight(120)
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(10, 10, 10, 10)
        info_layout.setSpacing(6)

        # Type icon and file name
        name_row = QHBoxLayout()
        name_row.setSpacing(6)

        type_icons = {
            'video': '🎬',
            'audio': '🎵',
            'image': '🖼️'
        }
        type_icon = QLabel(type_icons.get(self.media_item.file_type, '📄'))
        type_icon.setStyleSheet("font-size: 14px;")
        name_row.addWidget(type_icon)

        name_label = QLabel(self.media_item.file_name)
        name_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: 500;
            }
        """)
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(32)
        name_row.addWidget(name_label, 1)

        info_layout.addLayout(name_row)

        # Type and resolution
        if self.media_item.file_type == 'video' and self.media_item.width > 0:
            res_text = f"Video • {self.media_item.width}x{self.media_item.height}"
        elif self.media_item.file_type == 'audio':
            res_text = f"Audio • {os.path.splitext(self.media_item.file_name)[1].upper()[1:]}"
        elif self.media_item.file_type == 'image' and self.media_item.width > 0:
            res_text = f"Image • {self.media_item.width}x{self.media_item.height}"
        else:
            res_text = self.media_item.file_type.capitalize()

        res_label = QLabel(res_text)
        res_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
            }
        """)
        info_layout.addWidget(res_label)

        # File size
        size_mb = self.media_item.file_size / (1024 * 1024)
        if size_mb < 1:
            size_text = f"{self.media_item.file_size / 1024:.1f} KB"
        else:
            size_text = f"{size_mb:.1f} MB"

        size_label = QLabel(f"Size: {size_text}")
        size_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 10px;
            }
        """)
        info_layout.addWidget(size_label)

        # Filter badges
        filter_badges = QHBoxLayout()
        filter_badges.setSpacing(3)

        if self.media_item.is_zoomed:
            filter_badges.addWidget(self.create_mini_badge("🔍", "#2196f3"))
        if self.media_item.is_blurred:
            filter_badges.addWidget(self.create_mini_badge("🌫️", "#9c27b0"))
        if self.media_item.is_ai_enhanced:
            filter_badges.addWidget(self.create_mini_badge("🤖", "#ff9800"))
        if self.media_item.speed_factor != 1.0:
            filter_badges.addWidget(self.create_mini_badge("⚡", "#4caf50"))

        filter_badges.addStretch()
        info_layout.addLayout(filter_badges)

        info_layout.addStretch()

        info_frame.setLayout(info_layout)
        layout.addWidget(info_frame)

        self.setLayout(layout)

    def create_mini_badge(self, icon, color):
        """Create small filter badge"""
        badge = QLabel(icon)
        badge.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 2px 4px;
                border-radius: 3px;
                font-size: 10px;
            }}
        """)
        badge.setFixedSize(18, 18)
        badge.setAlignment(Qt.AlignCenter)
        return badge

    def update_style(self):
        """Update card style based on state"""
        if self.is_selected:
            self.setStyleSheet("""
                QFrame {
                    border: 3px solid #00bcd4;
                    border-radius: 8px;
                    background-color: #1e1e1e;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    border: 1px solid #2a2a2a;
                    border-radius: 8px;
                    background-color: #1e1e1e;
                }
                QFrame:hover {
                    border: 2px solid #00bcd4;
                    background-color: #252525;
                }
            """)

    def mousePressEvent(self, event):
        """Handle mouse press"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.media_item)

    def mouseDoubleClickEvent(self, event):
        """Handle double click"""
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.media_item)

    def set_selected(self, selected: bool):
        """Set selection state"""
        self.is_selected = selected
        self.update_style()


class EnhancedMediaLibrary(QWidget):
    """Enhanced media library with filters and professional card grid"""

    media_selected = pyqtSignal(object)  # Emits MediaItem
    media_double_clicked = pyqtSignal(object)
    import_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_items: List[MediaItem] = []
        self.filtered_items: List[MediaItem] = []
        self.selected_item: Optional[MediaItem] = None
        self.media_cards: List[MediaCard] = []

        # Filter states
        self.zoom_filter = "All Videos"
        self.blur_filter = "All Videos"
        self.ai_filter = "All Videos"
        self.speed_filter = "All Videos"
        self.search_text = ""

        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("MEDIA LIBRARY")
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

        # Import button
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
        import_btn.clicked.connect(self.import_requested.emit)
        layout.addWidget(import_btn)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search media...")
        self.search_box.setStyleSheet("""
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
        self.search_box.textChanged.connect(self.on_search_changed)
        layout.addWidget(self.search_box)

        # Filter dropdowns
        filters_label = QLabel("FILTERS")
        filters_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: bold;
                color: #888888;
                padding: 4px 0;
            }
        """)
        layout.addWidget(filters_label)

        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(8)

        # Zoom filter
        self.zoom_combo = FilterDropdown("🔍 Zoom")
        self.zoom_combo.addItems([
            "All Videos",
            "Zoomed Only",
            "Non-Zoomed"
        ])
        self.zoom_combo.currentTextChanged.connect(self.on_zoom_filter_changed)
        filters_layout.addWidget(self.zoom_combo)

        # Blur filter
        self.blur_combo = FilterDropdown("🌫️ Blur")
        self.blur_combo.addItems([
            "All Videos",
            "Blurred",
            "Sharp/Clear",
            "─────────",
            "Low Blur",
            "Medium Blur",
            "High Blur"
        ])
        self.blur_combo.currentTextChanged.connect(self.on_blur_filter_changed)
        filters_layout.addWidget(self.blur_combo)

        filters_layout.addStretch()
        layout.addLayout(filters_layout)

        # Second row of filters
        filters_layout2 = QHBoxLayout()
        filters_layout2.setSpacing(8)

        # AI filter
        self.ai_combo = FilterDropdown("🤖 AI")
        self.ai_combo.addItems([
            "All Videos",
            "AI Enhanced",
            "AI Generated",
            "Original"
        ])
        self.ai_combo.currentTextChanged.connect(self.on_ai_filter_changed)
        filters_layout2.addWidget(self.ai_combo)

        # Speed filter
        self.speed_combo = FilterDropdown("⚡ Speed")
        self.speed_combo.addItems([
            "All Videos",
            "Normal Speed",
            "Slow Motion",
            "Fast Forward",
            "─────────",
            "0.25x - 0.5x",
            "0.5x - 1x",
            "1x (Normal)",
            "1x - 2x",
            "2x+"
        ])
        self.speed_combo.currentTextChanged.connect(self.on_speed_filter_changed)
        filters_layout2.addWidget(self.speed_combo)

        filters_layout2.addStretch()
        layout.addLayout(filters_layout2)

        # Clear filters button
        clear_filters_container = QHBoxLayout()
        clear_filters_container.addStretch()

        self.clear_filters_btn = QPushButton("✕ Clear Filters")
        self.clear_filters_btn.setVisible(False)
        self.clear_filters_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: none;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #00bcd4;
                text-decoration: underline;
            }
        """)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        clear_filters_container.addWidget(self.clear_filters_btn)

        layout.addLayout(clear_filters_container)

        # Filter count display
        self.filter_count_label = QLabel("")
        self.filter_count_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 12px;
                padding: 4px 0;
            }
        """)
        layout.addWidget(self.filter_count_label)

        # Media cards grid (scrollable)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #00bcd4;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.cards_container = QWidget()
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(15)
        self.cards_layout.setContentsMargins(5, 5, 5, 5)
        self.cards_container.setLayout(self.cards_layout)

        scroll_area.setWidget(self.cards_container)
        layout.addWidget(scroll_area, 1)

        # Media info
        self.media_info_label = QLabel("No media imported")
        self.media_info_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                padding: 8px 4px;
            }
        """)
        self.media_info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.media_info_label)

        self.setLayout(layout)

    def add_media_item(self, media_item: MediaItem):
        """Add a media item to the library"""
        self.media_items.append(media_item)
        self.refresh_display()

    def add_media_items(self, items: List[MediaItem]):
        """Add multiple media items"""
        self.media_items.extend(items)
        self.refresh_display()

    def refresh_display(self):
        """Refresh the media cards display"""
        # Apply filters
        self.apply_filters()

        # Clear existing cards
        for card in self.media_cards:
            card.deleteLater()
        self.media_cards.clear()

        # Remove all widgets from grid
        for i in reversed(range(self.cards_layout.count())):
            self.cards_layout.itemAt(i).widget().setParent(None)

        # Create new cards
        row = 0
        col = 0
        max_cols = 2  # 2 cards per row

        for item in self.filtered_items:
            card = MediaCard(item)
            card.clicked.connect(self.on_card_clicked)
            card.double_clicked.connect(self.on_card_double_clicked)

            self.cards_layout.addWidget(card, row, col)
            self.media_cards.append(card)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Update info label
        total = len(self.media_items)
        filtered = len(self.filtered_items)
        if filtered < total:
            self.filter_count_label.setText(f"Showing {filtered} of {total} items")
        else:
            self.filter_count_label.setText("")

        self.media_info_label.setText(f"{total} items imported")

    def apply_filters(self):
        """Apply all active filters"""
        self.filtered_items = self.media_items.copy()

        # Search filter
        if self.search_text:
            self.filtered_items = [
                item for item in self.filtered_items
                if self.search_text.lower() in item.file_name.lower()
            ]

        # Zoom filter
        if self.zoom_filter == "Zoomed Only":
            self.filtered_items = [item for item in self.filtered_items if item.is_zoomed]
        elif self.zoom_filter == "Non-Zoomed":
            self.filtered_items = [item for item in self.filtered_items if not item.is_zoomed]

        # Blur filter
        if self.blur_filter == "Blurred":
            self.filtered_items = [item for item in self.filtered_items if item.is_blurred]
        elif self.blur_filter == "Sharp/Clear":
            self.filtered_items = [item for item in self.filtered_items if not item.is_blurred]
        elif self.blur_filter == "Low Blur":
            self.filtered_items = [item for item in self.filtered_items if item.blur_level == "low"]
        elif self.blur_filter == "Medium Blur":
            self.filtered_items = [item for item in self.filtered_items if item.blur_level == "medium"]
        elif self.blur_filter == "High Blur":
            self.filtered_items = [item for item in self.filtered_items if item.blur_level == "high"]

        # AI filter
        if self.ai_filter == "AI Enhanced":
            self.filtered_items = [item for item in self.filtered_items if item.is_ai_enhanced]
        elif self.ai_filter == "Original":
            self.filtered_items = [item for item in self.filtered_items if not item.is_ai_enhanced]

        # Speed filter
        if self.speed_filter == "Normal Speed":
            self.filtered_items = [item for item in self.filtered_items if item.speed_factor == 1.0]
        elif self.speed_filter == "Slow Motion":
            self.filtered_items = [item for item in self.filtered_items if item.speed_factor < 1.0]
        elif self.speed_filter == "Fast Forward":
            self.filtered_items = [item for item in self.filtered_items if item.speed_factor > 1.0]
        elif self.speed_filter == "0.25x - 0.5x":
            self.filtered_items = [item for item in self.filtered_items if 0.25 <= item.speed_factor <= 0.5]
        elif self.speed_filter == "0.5x - 1x":
            self.filtered_items = [item for item in self.filtered_items if 0.5 <= item.speed_factor < 1.0]
        elif self.speed_filter == "1x - 2x":
            self.filtered_items = [item for item in self.filtered_items if 1.0 < item.speed_factor <= 2.0]
        elif self.speed_filter == "2x+":
            self.filtered_items = [item for item in self.filtered_items if item.speed_factor > 2.0]

        # Update clear filters button visibility
        has_active_filters = (
            self.zoom_filter != "All Videos" or
            self.blur_filter != "All Videos" or
            self.ai_filter != "All Videos" or
            self.speed_filter != "All Videos" or
            self.search_text
        )
        self.clear_filters_btn.setVisible(has_active_filters)

    def on_search_changed(self, text):
        """Handle search text change"""
        self.search_text = text
        self.refresh_display()

    def on_zoom_filter_changed(self, value):
        """Handle zoom filter change"""
        self.zoom_filter = value
        self.refresh_display()

    def on_blur_filter_changed(self, value):
        """Handle blur filter change"""
        if value == "─────────":
            return
        self.blur_filter = value
        self.refresh_display()

    def on_ai_filter_changed(self, value):
        """Handle AI filter change"""
        self.ai_filter = value
        self.refresh_display()

    def on_speed_filter_changed(self, value):
        """Handle speed filter change"""
        if value == "─────────":
            return
        self.speed_filter = value
        self.refresh_display()

    def clear_all_filters(self):
        """Clear all filters"""
        self.search_box.clear()
        self.zoom_combo.setCurrentText("All Videos")
        self.blur_combo.setCurrentText("All Videos")
        self.ai_combo.setCurrentText("All Videos")
        self.speed_combo.setCurrentText("All Videos")
        self.search_text = ""
        self.zoom_filter = "All Videos"
        self.blur_filter = "All Videos"
        self.ai_filter = "All Videos"
        self.speed_filter = "All Videos"
        self.refresh_display()

    def on_card_clicked(self, media_item):
        """Handle card click"""
        # Deselect previous
        if self.selected_item:
            for card in self.media_cards:
                if card.media_item == self.selected_item:
                    card.set_selected(False)

        # Select new
        self.selected_item = media_item
        for card in self.media_cards:
            if card.media_item == media_item:
                card.set_selected(True)

        self.media_selected.emit(media_item)

    def on_card_double_clicked(self, media_item):
        """Handle card double click"""
        self.media_double_clicked.emit(media_item)

    def get_selected_item(self) -> Optional[MediaItem]:
        """Get currently selected media item"""
        return self.selected_item
