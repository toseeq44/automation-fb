import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLineEdit, QLabel, QFrame, QGridLayout, QScrollArea,
                             QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor
from dataclasses import dataclass

@dataclass
class MediaItem:
    file_path: str
    file_name: str
    file_type: str
    file_size: int
    duration: float
    width: int
    height: int
    fps: float
    thumbnail: QPixmap
    is_zoomed: bool
    is_blurred: bool
    is_ai_enhanced: bool
    speed_factor: float
    is_processing: bool
    is_new: bool

class FilterDropdown(QComboBox):
    def __init__(self, placeholder):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setStyleSheet("""
            QComboBox {
                background: #1a1a1a;
                color: white;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #888;
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background: #1a1a1a;
                color: white;
                selection-background-color: #00bcd4;
                border: 1px solid #333;
            }
        """)

class MediaCard(QFrame):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    load_requested = pyqtSignal(object)
    
    def __init__(self, media_item: MediaItem):
        super().__init__()
        self.media_item = media_item
        self.setup_ui()
        
    def setup_ui(self):
        # Card size: 140x180
        self.setFixedSize(140, 180)
        self.setStyleSheet("""
            MediaCard {
                background: #1e1e1e;
                border: 1px solid #333;
                border-radius: 6px;
                margin: 4px;
            }
            MediaCard:hover {
                background: #2a2a2a;
                border: 1px solid #00bcd4;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        
        # Thumbnail container (with relative positioning for plus button)
        thumbnail_container = QWidget()
        thumbnail_container.setFixedSize(128, 80)
        thumbnail_layout = QVBoxLayout(thumbnail_container)
        thumbnail_layout.setContentsMargins(0, 0, 0, 0)
        
        # Thumbnail label
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(128, 80)
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                background: #0f0f0f;
                border-radius: 4px;
                border: 1px solid #333;
            }
        """)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        
        # Set thumbnail
        if not self.media_item.thumbnail.isNull():
            scaled_pixmap = self.media_item.thumbnail.scaled(
                126, 78, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.thumbnail_label.setPixmap(scaled_pixmap)
        else:
            self.thumbnail_label.setText("No\nThumbnail")
            self.thumbnail_label.setStyleSheet("""
                QLabel {
                    background: #0f0f0f;
                    border-radius: 4px;
                    border: 1px solid #333;
                    color: #666;
                    font-size: 8px;
                }
            """)
        
        # Plus button - OVERLAY on thumbnail
        self.plus_button = QPushButton("+")
        self.plus_button.setFixedSize(24, 24)
        self.plus_button.setStyleSheet("""
            QPushButton {
                background: #00bcd4;
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #26c6da;
            }
            QPushButton:pressed {
                background: #0097a7;
            }
        """)
        self.plus_button.clicked.connect(lambda: self.load_requested.emit(self.media_item))
        
        # Add to thumbnail container
        thumbnail_layout.addWidget(self.thumbnail_label)
        
        # Add plus button to main layout but position it over thumbnail
        layout.addWidget(thumbnail_container)
        
        # Duration badge
        duration_badge = QLabel(self.format_duration(self.media_item.duration))
        duration_badge.setStyleSheet("""
            QLabel {
                background: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 1px 4px;
                border-radius: 3px;
                font-size: 8px;
                font-weight: bold;
            }
        """)
        duration_badge.setAlignment(Qt.AlignCenter)
        duration_badge.setFixedHeight(14)
        
        # File info
        file_name = QLabel(self.media_item.file_name)
        file_name.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 9px;")
        file_name.setWordWrap(True)
        file_name.setMaximumHeight(24)
        
        file_info = QLabel(f"{self.media_item.file_type.upper()} • {self.format_file_size(self.media_item.file_size)}")
        file_info.setStyleSheet("color: #888; font-size: 8px;")
        
        # Add to main layout
        layout.addWidget(duration_badge)
        layout.addWidget(file_name)
        layout.addWidget(file_info)
        layout.addStretch()
        
        # Position plus button over thumbnail
        self.plus_button.setParent(self)
        self.plus_button.move(102, 52)  # Position in bottom-right of thumbnail
        
    def format_duration(self, seconds):
        """Format duration as MM:SS"""
        try:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        except:
            return "00:00"
    
    def format_file_size(self, size_bytes):
        """Format file size as KB/MB"""
        try:
            if size_bytes == 0:
                return "0 B"
                
            size_kb = size_bytes / 1024
            if size_kb < 1024:
                return f"{size_kb:.1f} KB"
            else:
                size_mb = size_kb / 1024
                return f"{size_mb:.1f} MB"
        except:
            return "0 KB"
    
    def mousePressEvent(self, event):
        self.clicked.emit()
        
    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()

class EnhancedMediaLibrary(QWidget):
    media_selected = pyqtSignal(object)
    media_double_clicked = pyqtSignal(object)
    import_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.media_items = []
        self.filtered_items = []
        self.setup_ui()
        
    def setup_ui(self):
        print("DEBUG: Setting up EnhancedMediaLibrary UI")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Header with import button and search
        header_layout = QHBoxLayout()
        
        self.import_btn = QPushButton("📁 Import Media")
        self.import_btn.setStyleSheet(self.get_button_style())
        self.import_btn.setFixedHeight(32)
        self.import_btn.clicked.connect(self.import_requested.emit)
        header_layout.addWidget(self.import_btn)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search media...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 6px 10px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #00bcd4;
            }
        """)
        self.search_box.setFixedHeight(32)
        self.search_box.textChanged.connect(self.refresh_display)
        header_layout.addWidget(self.search_box)
        
        main_layout.addLayout(header_layout)
        
        # Filter dropdowns
        filters_layout = QHBoxLayout()
        
        self.zoom_combo = FilterDropdown("🔍 Zoom")
        self.zoom_combo.addItems(["All", "Zoomed", "Not Zoomed"])
        self.zoom_combo.currentTextChanged.connect(self.refresh_display)
        filters_layout.addWidget(self.zoom_combo)
        
        self.blur_combo = FilterDropdown("🌀 Blur")
        self.blur_combo.addItems(["All", "Blurred", "Not Blurred"])
        self.blur_combo.currentTextChanged.connect(self.refresh_display)
        filters_layout.addWidget(self.blur_combo)
        
        self.ai_combo = FilterDropdown("🤖 AI")
        self.ai_combo.addItems(["All", "AI Enhanced", "Not AI Enhanced"])
        self.ai_combo.currentTextChanged.connect(self.refresh_display)
        filters_layout.addWidget(self.ai_combo)
        
        self.speed_combo = FilterDropdown("⚡ Speed")
        self.speed_combo.addItems(["All", "Slow Motion", "Fast Motion", "Normal"])
        self.speed_combo.currentTextChanged.connect(self.refresh_display)
        filters_layout.addWidget(self.speed_combo)
        
        main_layout.addLayout(filters_layout)
        
        # Media grid with scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #444;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #666;
            }
        """)
        
        # Grid container widget
        self.grid_container = QWidget()
        self.media_grid = QGridLayout(self.grid_container)
        self.media_grid.setSpacing(10)
        self.media_grid.setContentsMargins(5, 5, 5, 5)
        self.media_grid.setAlignment(Qt.AlignTop)
        
        self.scroll_area.setWidget(self.grid_container)
        main_layout.addWidget(self.scroll_area)
        
        print("DEBUG: EnhancedMediaLibrary UI setup completed")
        
    def get_button_style(self):
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00bcd4, stop:1 #0097a7);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #26c6da, stop:1 #00acc1);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0097a7, stop:1 #00838f);
            }
        """
    
    def add_media_item(self, item: MediaItem):
        try:
            print(f"DEBUG: MediaLibrary.add_media_item() called for {item.file_name}")
            
            self.media_items.append(item)
            print(f"DEBUG: Added to media_items list. Total items: {len(self.media_items)}")
            
            self.refresh_display()
            
        except Exception as e:
            print(f"DEBUG: Error in add_media_item: {str(e)}")
    
    def refresh_display(self):
        try:
            print(f"DEBUG: refresh_display() called. Total media items: {len(self.media_items)}")
            
            # Clear existing cards from grid
            for i in reversed(range(self.media_grid.count())):
                item = self.media_grid.itemAt(i)
                if item and item.widget():
                    item.widget().setParent(None)
                    
            print("DEBUG: Cleared existing grid")
            
            # Apply filters
            self.apply_filters()
            print(f"DEBUG: After filtering - {len(self.filtered_items)} items to display")
            
            # Create cards for filtered items
            for i, item in enumerate(self.filtered_items):
                try:
                    card = MediaCard(item)
                    row = i // 3  # 3 cards per row
                    col = i % 3
                    self.media_grid.addWidget(card, row, col)
                    
                    # Connect signals
                    card.clicked.connect(lambda checked=False, item=item: self.on_card_clicked(item))
                    card.double_clicked.connect(lambda item=item: self.on_card_double_clicked(item))
                    card.load_requested.connect(lambda item=item: self.on_plus_button_clicked(item))
                    
                    print(f"DEBUG: Created card for {item.file_name} at row {row}, col {col}")
                    
                except Exception as e:
                    print(f"DEBUG: Error creating card for {item.file_name}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
                    
            print(f"DEBUG: Created {len(self.filtered_items)} cards in grid")
            
        except Exception as e:
            print(f"DEBUG: Error in refresh_display: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def apply_filters(self):
        """Apply all active filters to media items"""
        self.filtered_items = self.media_items.copy()
        
        # Search filter
        search_text = self.search_box.text().lower()
        if search_text:
            self.filtered_items = [item for item in self.filtered_items if search_text in item.file_name.lower()]
        
        # Zoom filter
        zoom_filter = self.zoom_combo.currentText()
        if zoom_filter == "Zoomed":
            self.filtered_items = [item for item in self.filtered_items if item.is_zoomed]
        elif zoom_filter == "Not Zoomed":
            self.filtered_items = [item for item in self.filtered_items if not item.is_zoomed]
        
        # Blur filter
        blur_filter = self.blur_combo.currentText()
        if blur_filter == "Blurred":
            self.filtered_items = [item for item in self.filtered_items if item.is_blurred]
        elif blur_filter == "Not Blurred":
            self.filtered_items = [item for item in self.filtered_items if not item.is_blurred]
        
        # AI filter
        ai_filter = self.ai_combo.currentText()
        if ai_filter == "AI Enhanced":
            self.filtered_items = [item for item in self.filtered_items if item.is_ai_enhanced]
        elif ai_filter == "Not AI Enhanced":
            self.filtered_items = [item for item in self.filtered_items if not item.is_ai_enhanced]
        
        # Speed filter
        speed_filter = self.speed_combo.currentText()
        if speed_filter == "Slow Motion":
            self.filtered_items = [item for item in self.filtered_items if item.speed_factor < 1.0]
        elif speed_filter == "Fast Motion":
            self.filtered_items = [item for item in self.filtered_items if item.speed_factor > 1.0]
        elif speed_filter == "Normal":
            self.filtered_items = [item for item in self.filtered_items if item.speed_factor == 1.0]
    
    def on_card_clicked(self, item):
        """Handle card click - select media"""
        self.media_selected.emit(item)
    
    def on_card_double_clicked(self, item):
        """Handle card double click - load media"""
        self.media_double_clicked.emit(item)
        
    def on_plus_button_clicked(self, item):
        """Handle plus button click - load media in preview"""
        print(f"DEBUG: Plus button clicked for {item.file_name}")
        self.media_double_clicked.emit(item)