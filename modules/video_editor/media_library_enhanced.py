import os
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QFrame,
    QGridLayout,
    QScrollArea,
    QMenu,
    QSizePolicy,
    QInputDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor
from dataclasses import dataclass
from functools import partial

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

class FilterMenuButton(QPushButton):
    """Header-inspired button that opens a styled dropdown menu."""

    option_selected = pyqtSignal(object)

    def __init__(self, base_title: str, options=None, *, button_style: str, menu_style: str) -> None:
        super().__init__()
        self.base_title = base_title
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setStyleSheet(button_style)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._menu = QMenu(self)
        self._menu.setStyleSheet(menu_style)
        self._submenus = {}

        self.current_label = None
        self.current_payload = None
        self._default_payload = None

        self.clicked.connect(self.show_menu)

        if options:
            self.set_options(options)
        else:
            self._update_text()

    def set_options(self, options) -> None:
        """Populate the dropdown menu from the provided option list."""
        self._menu.clear()
        self._submenus.clear()
        self._default_payload = None

        if not options:
            self._set_selection(None, None)
            return

        for entry in options:
            self._add_entry(entry)

        if self._default_payload:
            self._set_selection(self._default_payload.get("display"), self._default_payload)
        else:
            self._set_selection(None, None)

    def show_menu(self) -> None:
        """Display the dropdown menu below the button."""
        self._menu.popup(self.mapToGlobal(self.rect().bottomLeft()))

    def _get_or_create_submenu(self, title: str) -> QMenu:
        submenu = self._submenus.get(title)
        if submenu is None:
            submenu = self._menu.addMenu(title)
            submenu.setStyleSheet(self._menu.styleSheet())
            self._submenus[title] = submenu
        return submenu

    def _add_entry(self, entry) -> None:
        if isinstance(entry, tuple):
            submenu_title, children = entry
            submenu = self._get_or_create_submenu(submenu_title)
            for child in children:
                child_entry = dict(child)
                child_entry["submenu"] = submenu_title
                self._add_entry(child_entry)
            return

        if isinstance(entry, dict):
            label = entry.get("label", "")
            display = entry.get("display", label)
            value = entry.get("value", label)
            default = entry.get("default", False)
            submenu_title = entry.get("submenu")

            target_menu = self._menu if not submenu_title else self._get_or_create_submenu(submenu_title)
            action = target_menu.addAction(label)
            payload = {
                "value": value,
                "display": display,
                "label": label,
                "metadata": entry,
            }
            action.setData(payload)
            action.triggered.connect(partial(self._handle_action, action))
            if default:
                self._default_payload = payload
            return

        # Fallback simple string option
        label = str(entry)
        action = self._menu.addAction(label)
        payload = {"value": entry, "display": label, "label": label, "metadata": {"label": label}}
        action.setData(payload)
        action.triggered.connect(partial(self._handle_action, action))

    def _handle_action(self, action) -> None:
        payload = action.data() or {}
        value = payload.get("value")

        if isinstance(value, dict) and value.get("mode") == "custom":
            # Let the caller handle custom prompts so we don't update prematurely.
            self.option_selected.emit(payload)
            return

        display = payload.get("display") or payload.get("label")
        self._set_selection(display, payload)
        self.option_selected.emit(payload)

    def _set_selection(self, display_label, payload) -> None:
        label = (display_label or "").strip() if display_label else None
        if label and label.lower() == "all":
            label = None

        self.current_label = label
        self.current_payload = payload
        self._update_text()

    def _update_text(self) -> None:
        """Show base title and highlight selection when not default."""
        if not self.current_label:
            self.setText(self.base_title)
        else:
            self.setText(f"{self.base_title}: {self.current_label}")

    def set_custom_selection(self, display_label: str | None, payload: dict | None) -> None:
        """Allow callers to set a custom selection (used after dialogs)."""
        payload = payload or {}
        if display_label:
            payload.setdefault("display", display_label)
        self._set_selection(display_label, payload)

    def reset_to_default(self) -> None:
        if self._default_payload:
            self._set_selection(self._default_payload.get("display"), self._default_payload)

    def current_selection(self):
        return self.current_payload

class MediaCard(QFrame):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    load_requested = pyqtSignal(object)
    
    def __init__(self, media_item: MediaItem):
        super().__init__()
        self.media_item = media_item
        self.setup_ui()
        
    def setup_ui(self):
        # Compact card footprint (width unchanged, height reduced)
        self.setFixedSize(140, 150)
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
        layout.setSpacing(3)
        
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
        self.plus_button.setCursor(Qt.PointingHandCursor)
        self.plus_button.clicked.connect(lambda: self.load_requested.emit(self.media_item))
        
        # Add to thumbnail container
        thumbnail_layout.addWidget(self.thumbnail_label)
        
        # Add plus button to main layout but position it over thumbnail
        layout.addWidget(thumbnail_container, alignment=Qt.AlignCenter)
        
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
        display_title = self._get_display_title(self.media_item.file_name)
        title_label = QLabel(display_title)
        title_label.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 9px;")
        title_label.setWordWrap(False)
        title_label.setFixedHeight(16)
        title_label.setToolTip(self.media_item.file_name)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        file_info = QLabel(f"{self.media_item.file_type.upper()} - {self.format_file_size(self.media_item.file_size)}")
        file_info.setStyleSheet("color: #888; font-size: 8px;")
        file_info.setFixedHeight(14)
        file_info.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # Add to main layout
        layout.addWidget(duration_badge)
        layout.addWidget(title_label)
        layout.addWidget(file_info)
        layout.addStretch()
        
        # Position plus button over thumbnail
        self.plus_button.setParent(thumbnail_container)
        self.plus_button.move(6, 6)  # Position in top-left of thumbnail
        self.plus_button.raise_()

    def _get_display_title(self, file_name: str) -> str:
        """Return a short, two-word title for compact display."""
        base_name, _ = os.path.splitext(file_name or "")
        sanitized = base_name.replace("_", " ").replace("-", " ")
        words = [word for word in sanitized.split() if word]
        if not words:
            return file_name
        if len(words) <= 2:
            return " ".join(words)
        return " ".join(words[:2]) + "..."
        
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
    effect_requested = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.media_items = []
        self.filtered_items = []
        self.zoom_filter_state = {"mode": "all"}
        self.blur_filter_state = {"mode": "all"}
        self.ai_filter_state = {"mode": "all"}
        self.speed_filter_state = {"mode": "all"}
        self.setup_ui()
        
    def setup_ui(self):
        print("DEBUG: Setting up EnhancedMediaLibrary UI")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Filter controls row (header-inspired buttons)
        button_style = self.get_filter_button_style()
        menu_style = self.get_filter_menu_style()

        zoom_presets = [90, 95, 105, 110, 115]
        zoom_options = [
            {"label": "All", "display": "All", "value": {"filter": "zoom", "mode": "all"}, "default": True},
        ]
        for pct in zoom_presets:
            zoom_options.append({
                "label": f"{pct}%",
                "display": f"{pct}%",
                "value": {"filter": "zoom", "mode": "preset", "percent": pct},
            })
        zoom_options.append({
            "label": "Custom...",
            "display": "Custom",
            "value": {"filter": "zoom", "mode": "custom"},
        })

        blur_presets = [1, 2, 4, 6, 8, 10]
        blur_targets = [
            ("All Sides Blur", "all_sides"),
            ("Top & Bottom", "top_bottom"),
            ("Left & Right", "left_right"),
        ]
        blur_options = [
            {"label": "All", "display": "All", "value": {"filter": "blur", "mode": "all"}, "default": True},
        ]
        for title, key in blur_targets:
            submenu_entries = [
                {
                    "label": "Custom...",
                    "display": "Custom",
                    "value": {"filter": "blur", "mode": "custom", "target": key, "friendly": title},
                }
            ]
            for percent in blur_presets:
                submenu_entries.append({
                    "label": f"{percent}%",
                    "display": f"{title} {percent}%",
                    "value": {
                        "filter": "blur",
                        "mode": "preset",
                        "target": key,
                        "percent": percent,
                        "friendly": title,
                    },
                })
            blur_options.append((title, submenu_entries))

        ai_options = [
            {"label": "All", "display": "All", "value": {"filter": "ai", "mode": "all"}, "default": True},
            {"label": "Body Modification", "display": "Body Modification", "value": {"filter": "ai", "mode": "tag", "tag": "body"}},
            {"label": "Eyes", "display": "Eyes", "value": {"filter": "ai", "mode": "tag", "tag": "eyes"}},
            {"label": "Face", "display": "Face", "value": {"filter": "ai", "mode": "tag", "tag": "face"}},
        ]

        speed_presets = [-1.0, -0.5, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
        speed_options = [
            {"label": "All", "display": "All", "value": {"filter": "speed", "mode": "all"}, "default": True},
        ]
        for factor in speed_presets:
            label = self._format_speed_label(factor)
            speed_options.append({
                "label": label,
                "display": label,
                "value": {"filter": "speed", "mode": "preset", "factor": factor},
            })
        speed_options.append({
            "label": "Custom...",
            "display": "Custom",
            "value": {"filter": "speed", "mode": "custom"},
        })

        filter_grid = QGridLayout()
        filter_grid.setContentsMargins(0, 0, 0, 0)
        filter_grid.setHorizontalSpacing(12)
        filter_grid.setVerticalSpacing(8)
        filter_grid.setColumnStretch(0, 1)
        filter_grid.setColumnStretch(1, 1)

        self.zoom_button = FilterMenuButton("Zoom", button_style=button_style, menu_style=menu_style)
        self.zoom_button.set_options(zoom_options)
        self.zoom_button.option_selected.connect(self.on_zoom_filter_changed)
        filter_grid.addWidget(self.zoom_button, 0, 0)

        self.blur_button = FilterMenuButton("Blur", button_style=button_style, menu_style=menu_style)
        self.blur_button.set_options(blur_options)
        self.blur_button.option_selected.connect(self.on_blur_filter_changed)
        filter_grid.addWidget(self.blur_button, 0, 1)

        self.ai_button = FilterMenuButton("AI Feature", button_style=button_style, menu_style=menu_style)
        self.ai_button.set_options(ai_options)
        self.ai_button.option_selected.connect(self.on_ai_filter_changed)
        filter_grid.addWidget(self.ai_button, 1, 0)

        self.speed_button = FilterMenuButton("Speed", button_style=button_style, menu_style=menu_style)
        self.speed_button.set_options(speed_options)
        self.speed_button.option_selected.connect(self.on_speed_filter_changed)
        filter_grid.addWidget(self.speed_button, 1, 1)

        main_layout.addLayout(filter_grid)
        main_layout.addSpacing(10)

# Header with import button and search
        header_layout = QHBoxLayout()

        self.import_btn = QPushButton("Import Media")
        self.import_btn.setStyleSheet(self.get_button_style())
        self.import_btn.setFixedHeight(32)
        self.import_btn.clicked.connect(self.import_requested.emit)
        header_layout.addWidget(self.import_btn)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search media...")
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

    def on_zoom_filter_changed(self, payload) -> None:
        payload = payload or {}
        value_info = payload.get("value", {}) or {}
        mode = value_info.get("mode")

        if mode == "custom":
            percent, ok = QInputDialog.getDouble(
                self,
                "Custom Zoom",
                "Enter zoom percentage:",
                100.0,
                1.0,
                500.0,
                1,
            )
            if not ok:
                return
            display = f"{percent:.0f}%"
            new_value = {"filter": "zoom", "mode": "custom_value", "percent": percent}
            new_payload = {"value": new_value, "display": display}
            self.zoom_button.set_custom_selection(display, new_payload)
            self.zoom_filter_state = new_value
            payload = new_payload
        else:
            display = payload.get("display")
            if mode == "all":
                self.zoom_filter_state = {"mode": "all"}
                self.zoom_button.set_custom_selection(None, payload)
            else:
                self.zoom_filter_state = value_info
                self.zoom_button.set_custom_selection(display, payload)

        self.refresh_display()
        self._emit_speed_effect_change(payload)
        self._emit_zoom_effect_change(payload)

    def _emit_zoom_effect_change(self, payload) -> None:
        """Notify listeners when zoom preset changes so effects can be applied."""
        try:
            state = self.zoom_filter_state or {}
            mode = state.get("mode")
            display = payload.get("display") if payload else None

            if mode in {"preset", "custom_value"}:
                percent = state.get("percent")
                if percent is None:
                    return
                effect_payload = {
                    "type": "zoom",
                    "mode": mode,
                    "percent": float(percent),
                    "display": display or f"{percent:.0f}%",
                }
            elif mode in {"all", None}:
                effect_payload = {
                    "type": "zoom",
                    "mode": "reset",
                    "percent": 100.0,
                    "display": display or "100%",
                }
            else:
                return

            self.effect_requested.emit(effect_payload)
        except Exception as exc:
            print(f"DEBUG: Failed to emit zoom effect change: {exc}")

    def on_blur_filter_changed(self, payload) -> None:
        payload = payload or {}
        value_info = payload.get("value", {}) or {}
        mode = value_info.get("mode")
        friendly = value_info.get("friendly", "Blur")

        if mode == "custom":
            percent, ok = QInputDialog.getInt(
                self,
                f"{friendly} Blur",
                "Enter blur intensity (%):",
                5,
                0,
                100,
                1,
            )
            if not ok:
                return
            display = f"{friendly} {percent}%"
            new_value = {
                "filter": "blur",
                "mode": "custom_value",
                "target": value_info.get("target"),
                "percent": percent,
                "friendly": friendly,
            }
            new_payload = {"value": new_value, "display": display}
            self.blur_button.set_custom_selection(display, new_payload)
            self.blur_filter_state = new_value
            payload = new_payload
        else:
            display = payload.get("display")
            if mode == "all":
                self.blur_filter_state = {"mode": "all"}
                self.blur_button.set_custom_selection(None, payload)
            else:
                self.blur_filter_state = value_info
                self.blur_button.set_custom_selection(display, payload)

        self.refresh_display()
        self._emit_blur_effect_change(payload)

    def _emit_blur_effect_change(self, payload) -> None:
        """Notify listeners when blur presets change."""
        try:
            state = self.blur_filter_state or {}
            mode = state.get("mode")
            display = payload.get("display") if payload else None

            if mode in {"preset", "custom_value"}:
                percent = state.get("percent")
                if percent is None:
                    return
                effect_payload = {
                    "type": "blur",
                    "mode": mode,
                    "intensity": float(percent),
                    "target": state.get("target"),
                    "display": display or f"Blur {percent:.0f}%",
                }
            elif mode in {"all", None}:
                effect_payload = {
                    "type": "blur",
                    "mode": "reset",
                    "intensity": 0.0,
                    "target": state.get("target"),
                    "display": display or "Blur Off",
                }
            else:
                return

            self.effect_requested.emit(effect_payload)
        except Exception as exc:
            print(f"DEBUG: Failed to emit blur effect change: {exc}")

    def _emit_speed_effect_change(self, payload) -> None:
        """Notify listeners when speed presets change."""
        try:
            state = self.speed_filter_state or {}
            mode = state.get("mode")
            display = payload.get("display") if payload else None

            if mode in {"preset", "custom_value"}:
                factor = state.get("factor")
                if factor is None:
                    return
                effect_payload = {
                    "type": "speed",
                    "mode": mode,
                    "factor": float(factor),
                    "display": display or self._format_speed_label(factor),
                }
            elif mode in {"all", None}:
                effect_payload = {
                    "type": "speed",
                    "mode": "reset",
                    "factor": 1.0,
                    "display": self._format_speed_label(1.0),
                }
            else:
                return

            self.effect_requested.emit(effect_payload)
        except Exception as exc:
            print(f"DEBUG: Failed to emit speed effect change: {exc}")

    def on_ai_filter_changed(self, payload) -> None:
        payload = payload or {}
        value_info = payload.get("value", {}) or {}
        mode = value_info.get("mode")

        if mode == "all":
            self.ai_filter_state = {"mode": "all"}
            self.ai_button.set_custom_selection(None, payload)
        else:
            display = payload.get("display")
            self.ai_filter_state = value_info
            self.ai_button.set_custom_selection(display, payload)

        self.refresh_display()

    def on_speed_filter_changed(self, payload) -> None:
        payload = payload or {}
        value_info = payload.get("value", {}) or {}
        mode = value_info.get("mode")

        if mode == "custom":
            factor, ok = QInputDialog.getDouble(
                self,
                "Custom Speed",
                "Enter playback speed (-1.0x to 5.0x):",
                1.0,
                -1.0,
                5.0,
                2,
            )
            if not ok:
                return
            display = self._format_speed_label(factor)
            new_value = {"filter": "speed", "mode": "custom_value", "factor": factor}
            new_payload = {"value": new_value, "display": display}
            self.speed_button.set_custom_selection(display, new_payload)
            self.speed_filter_state = new_value
        else:
            display = payload.get("display")
            if mode == "all":
                self.speed_filter_state = {"mode": "all"}
                self.speed_button.set_custom_selection(None, payload)
            else:
                self.speed_filter_state = value_info
                self.speed_button.set_custom_selection(display, payload)

        self.refresh_display()
        self._emit_speed_effect_change(payload)
        
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

    def get_filter_button_style(self):
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2f2f2f, stop:1 #1c1c1c);
                color: #f0f0f0;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
                padding: 8px 18px;
                font-weight: 600;
                font-size: 12px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                border-color: #00bcd4;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #353535, stop:1 #212121);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1f1f1f, stop:1 #161616);
            }
        """

    def get_filter_menu_style(self):
        return """
            QMenu {
                background-color: #141414;
                color: #f0f0f0;
                border: 1px solid #00bcd4;
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 6px;
                margin: 2px 0;
            }
            QMenu::item:selected {
                background-color: #00bcd4;
                color: #0a0a0a;
            }
        """

    def _format_speed_label(self, value: float) -> str:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return f"{text}x"

    def _speed_matches(self, candidate, target) -> bool:
        try:
            candidate_val = float(candidate)
            target_val = float(target)
        except (TypeError, ValueError):
            return False
        return abs(candidate_val - target_val) <= 0.05
    
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
        zoom_mode = self.zoom_filter_state.get("mode")
        if zoom_mode and zoom_mode not in (None, "all"):
            if zoom_mode == "not_zoomed":
                self.filtered_items = [
                    item for item in self.filtered_items if not getattr(item, "is_zoomed", False)
                ]
            else:
                self.filtered_items = [
                    item for item in self.filtered_items if getattr(item, "is_zoomed", False)
                ]

        # Blur filter
        blur_mode = self.blur_filter_state.get("mode")
        if blur_mode and blur_mode not in (None, "all"):
            if blur_mode == "not_blurred":
                self.filtered_items = [
                    item for item in self.filtered_items if not getattr(item, "is_blurred", False)
                ]
            else:
                self.filtered_items = [
                    item for item in self.filtered_items if getattr(item, "is_blurred", False)
                ]

        # AI filter
        ai_mode = self.ai_filter_state.get("mode")
        if ai_mode and ai_mode not in (None, "all"):
            if ai_mode == "disabled":
                self.filtered_items = [
                    item for item in self.filtered_items if not getattr(item, "is_ai_enhanced", False)
                ]
            else:
                self.filtered_items = [
                    item for item in self.filtered_items if getattr(item, "is_ai_enhanced", False)
                ]

        # Speed filter
        speed_mode = self.speed_filter_state.get("mode")
        if speed_mode in {"preset", "custom_value"}:
            target_factor = self.speed_filter_state.get("factor")
            if target_factor is not None:
                self.filtered_items = [
                    item
                    for item in self.filtered_items
                    if self._speed_matches(getattr(item, "speed_factor", 1.0), target_factor)
                ]
    
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
