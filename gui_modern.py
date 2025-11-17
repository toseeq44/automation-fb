"""
gui_modern.py
OneSoul Flow - Professional 3D Modern UI
Integrated with existing modules + Centralized theming
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QSpacerItem, QSizePolicy, QScrollArea,
    QGraphicsDropShadowEffect, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer, QSize, QUrl
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtSvg import QSvgWidget
import os

# Try to import QWebEngineView for animated logo
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    HAS_WEB_ENGINE = True
except ImportError:
    HAS_WEB_ENGINE = False

# Import existing module pages
from modules.link_grabber.gui import LinkGrabberPage
from modules.video_downloader.gui import VideoDownloaderPage
from modules.video_editor.integrated_editor import IntegratedVideoEditor
from modules.metadata_remover.gui import MetadataRemoverPage
from modules.auto_uploader.gui import AutoUploaderPage
from modules.api_manager.gui import APIConfigPage
from modules.workflows.combo import CombinedWorkflowPage


# ==================== CENTRALIZED THEME SYSTEM ====================

class OneSoulTheme:
    """
    CENTRALIZED THEME - Change colors here, applies everywhere!
    Single source of truth for entire application
    """

    # Background Colors
    BG_PRIMARY = "#050712"          # Main background
    BG_SIDEBAR = "#0a0e1a"          # Sidebar background
    BG_ELEVATED = "#161b22"         # Raised elements (cards, panels)
    BG_ELEVATED_HOVER = "#1c2128"   # Hover state for cards

    # Accent Colors (from OneSoul logo)
    CYAN = "#00d4ff"                # Primary accent
    MAGENTA = "#ff00ff"             # Secondary accent
    GOLD = "#ffd700"                # Highlights

    # Text Colors
    TEXT_PRIMARY = "#ffffff"        # Main text
    TEXT_SECONDARY = "rgba(255, 255, 255, 0.7)"  # Secondary text
    TEXT_MUTED = "rgba(255, 255, 255, 0.5)"      # Muted text
    TEXT_GOLD = "#ffd700"           # Important headings
    TEXT_CYAN = "#00d4ff"           # Links, subheadings

    # Border & Shadow Colors
    BORDER_PRIMARY = "rgba(0, 212, 255, 0.2)"
    BORDER_GLOW = "rgba(0, 212, 255, 0.4)"
    SHADOW_3D = "rgba(0, 212, 255, 0.3)"

    # State Colors
    BG_HOVER = "rgba(0, 212, 255, 0.08)"
    BG_ACTIVE = "rgba(0, 212, 255, 0.15)"
    BG_PRESSED = "rgba(0, 212, 255, 0.25)"

    # Button Colors
    BTN_PRIMARY = "#00d4ff"
    BTN_PRIMARY_HOVER = "#00b8e6"
    BTN_SUCCESS = "#43B581"
    BTN_DANGER = "#E74C3C"
    BTN_WARNING = "#F39C12"

    # Size Constants
    SIDEBAR_EXPANDED = 250
    SIDEBAR_COLLAPSED = 60
    TOPBAR_HEIGHT = 120  # Height for logo area with OneSoul text visible
    LOGO_SIZE = 80  # 2x original (was 40)

    @staticmethod
    def get_global_stylesheet():
        """
        MASTER STYLESHEET - Applied to entire application
        This ensures ALL modules have consistent theme
        """
        return f"""
            /* ========== GLOBAL STYLES ========== */
            QMainWindow, QWidget {{
                background: {OneSoulTheme.BG_PRIMARY};
                color: {OneSoulTheme.TEXT_PRIMARY};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }}

            /* ========== LABELS ========== */
            QLabel {{
                color: {OneSoulTheme.TEXT_PRIMARY};
                background: transparent;
            }}

            /* ========== BUTTONS ========== */
            QPushButton {{
                background: {OneSoulTheme.BG_ELEVATED};
                color: {OneSoulTheme.TEXT_PRIMARY};
                border: 1px solid {OneSoulTheme.BORDER_PRIMARY};
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }}

            QPushButton:hover {{
                background: {OneSoulTheme.BG_ELEVATED_HOVER};
                border-color: {OneSoulTheme.CYAN};
            }}

            QPushButton:pressed {{
                background: {OneSoulTheme.BG_ACTIVE};
            }}

            QPushButton:disabled {{
                background: {OneSoulTheme.BG_SIDEBAR};
                color: {OneSoulTheme.TEXT_MUTED};
                border-color: {OneSoulTheme.TEXT_MUTED};
            }}

            /* ========== INPUT FIELDS ========== */
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background: {OneSoulTheme.BG_ELEVATED};
                color: {OneSoulTheme.TEXT_PRIMARY};
                border: 1px solid {OneSoulTheme.BORDER_PRIMARY};
                border-radius: 4px;
                padding: 8px;
                selection-background-color: {OneSoulTheme.CYAN};
                selection-color: {OneSoulTheme.BG_PRIMARY};
            }}

            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                border: 2px solid {OneSoulTheme.CYAN};
                padding: 7px;
            }}

            /* ========== COMBO BOXES ========== */
            QComboBox {{
                background: {OneSoulTheme.BG_ELEVATED};
                color: {OneSoulTheme.TEXT_PRIMARY};
                border: 1px solid {OneSoulTheme.BORDER_PRIMARY};
                border-radius: 4px;
                padding: 8px;
            }}

            QComboBox:hover {{
                border-color: {OneSoulTheme.CYAN};
            }}

            QComboBox::drop-down {{
                border: none;
            }}

            QComboBox QAbstractItemView {{
                background: {OneSoulTheme.BG_ELEVATED};
                color: {OneSoulTheme.TEXT_PRIMARY};
                border: 1px solid {OneSoulTheme.CYAN};
                selection-background-color: {OneSoulTheme.BG_ACTIVE};
                selection-color: {OneSoulTheme.TEXT_GOLD};
            }}

            /* ========== PROGRESS BARS ========== */
            QProgressBar {{
                background: {OneSoulTheme.BG_ELEVATED};
                border: 1px solid {OneSoulTheme.BORDER_PRIMARY};
                border-radius: 4px;
                text-align: center;
                color: {OneSoulTheme.TEXT_PRIMARY};
            }}

            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {OneSoulTheme.CYAN}, stop:1 {OneSoulTheme.MAGENTA});
                border-radius: 4px;
            }}

            /* ========== SCROLLBARS ========== */
            QScrollBar:vertical {{
                background: {OneSoulTheme.BG_SIDEBAR};
                width: 12px;
                border-radius: 6px;
            }}

            QScrollBar::handle:vertical {{
                background: {OneSoulTheme.BORDER_GLOW};
                border-radius: 6px;
                min-height: 20px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: {OneSoulTheme.CYAN};
            }}

            QScrollBar:horizontal {{
                background: {OneSoulTheme.BG_SIDEBAR};
                height: 12px;
                border-radius: 6px;
            }}

            QScrollBar::handle:horizontal {{
                background: {OneSoulTheme.BORDER_GLOW};
                border-radius: 6px;
                min-width: 20px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background: {OneSoulTheme.CYAN};
            }}

            QScrollBar::add-line, QScrollBar::sub-line {{
                height: 0px;
                width: 0px;
            }}

            /* ========== LIST WIDGETS ========== */
            QListWidget {{
                background: {OneSoulTheme.BG_ELEVATED};
                color: {OneSoulTheme.TEXT_PRIMARY};
                border: 1px solid {OneSoulTheme.BORDER_PRIMARY};
                border-radius: 4px;
            }}

            QListWidget::item {{
                padding: 8px;
            }}

            QListWidget::item:hover {{
                background: {OneSoulTheme.BG_HOVER};
            }}

            QListWidget::item:selected {{
                background: {OneSoulTheme.BG_ACTIVE};
                color: {OneSoulTheme.TEXT_GOLD};
            }}

            /* ========== TABLES ========== */
            QTableWidget {{
                background: {OneSoulTheme.BG_ELEVATED};
                color: {OneSoulTheme.TEXT_PRIMARY};
                gridline-color: {OneSoulTheme.BORDER_PRIMARY};
                border: 1px solid {OneSoulTheme.BORDER_PRIMARY};
                border-radius: 4px;
            }}

            QTableWidget::item {{
                padding: 5px;
            }}

            QTableWidget::item:hover {{
                background: {OneSoulTheme.BG_HOVER};
            }}

            QTableWidget::item:selected {{
                background: {OneSoulTheme.BG_ACTIVE};
                color: {OneSoulTheme.TEXT_GOLD};
            }}

            QHeaderView::section {{
                background: {OneSoulTheme.BG_SIDEBAR};
                color: {OneSoulTheme.TEXT_CYAN};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {OneSoulTheme.CYAN};
                font-weight: bold;
            }}

            /* ========== DIALOGS ========== */
            QDialog {{
                background: {OneSoulTheme.BG_PRIMARY};
                color: {OneSoulTheme.TEXT_PRIMARY};
            }}

            QMessageBox {{
                background: {OneSoulTheme.BG_PRIMARY};
            }}

            /* ========== TOOLTIPS ========== */
            QToolTip {{
                background: {OneSoulTheme.BG_ELEVATED};
                color: {OneSoulTheme.TEXT_PRIMARY};
                border: 1px solid {OneSoulTheme.CYAN};
                padding: 5px;
                border-radius: 4px;
            }}

            /* ========== STACKED WIDGET ========== */
            QStackedWidget {{
                background: {OneSoulTheme.BG_PRIMARY};
            }}
        """


# ==================== 3D SIDEBAR WITH DEPTH ====================

class Modern3DSidebar(QWidget):
    """Professional 3D sidebar with depth and shadows"""

    module_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.active_module = None
        self.module_buttons = {}

        self.modules = [
            ("link_grabber", "Link Grabber", "🔗"),
            ("video_downloader", "Video Downloader", "⬇️"),
            ("combo_workflow", "Grab + Download", "🚀"),
            ("video_editor", "Video Editor", "✂️"),
            ("metadata_remover", "Metadata Remover", "🔒"),
            ("auto_uploader", "Auto Uploader", "☁️"),
            ("api_config", "API Config", "🔑"),
        ]

        self.init_ui()
        self.apply_3d_styles()
        self.add_3d_shadow()

    def init_ui(self):
        """Initialize sidebar UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Toggle button
        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setFixedHeight(OneSoulTheme.TOPBAR_HEIGHT)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {OneSoulTheme.TEXT_CYAN};
                font-size: 24px;
            }}
            QPushButton:hover {{
                background: {OneSoulTheme.BG_HOVER};
            }}
        """)
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        layout.addWidget(self.toggle_btn)

        # Spacer
        layout.addSpacing(10)

        # Module buttons
        for module_id, display_text, icon in self.modules:
            btn = QPushButton(f"{icon}  {display_text}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("module_id", module_id)
            btn.setProperty("active", False)
            btn.setMinimumHeight(42)
            btn.clicked.connect(lambda checked, m=module_id: self.select_module(m))
            self.module_buttons[module_id] = btn
            layout.addWidget(btn)

        layout.addStretch()
        self.setLayout(layout)
        self.setFixedWidth(OneSoulTheme.SIDEBAR_EXPANDED)

    def apply_3d_styles(self):
        """Apply 3D depth styles to sidebar"""
        self.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {OneSoulTheme.BG_SIDEBAR},
                    stop:0.95 {OneSoulTheme.BG_SIDEBAR},
                    stop:1 rgba(0, 212, 255, 0.1));
                border-right: 2px solid {OneSoulTheme.BORDER_GLOW};
            }}

            QPushButton {{
                background: transparent;
                color: {OneSoulTheme.TEXT_SECONDARY};
                border: none;
                border-left: 4px solid transparent;
                border-radius: 0px;
                text-align: left;
                padding: 10px 15px;
                font-size: 14px;
                font-weight: normal;
            }}

            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {OneSoulTheme.BG_HOVER},
                    stop:1 {OneSoulTheme.BG_ACTIVE});
                color: {OneSoulTheme.TEXT_PRIMARY};
                border-left: 4px solid {OneSoulTheme.CYAN};
            }}

            QPushButton[active="true"] {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {OneSoulTheme.BG_ACTIVE},
                    stop:0.5 {OneSoulTheme.BG_ACTIVE},
                    stop:1 rgba(0, 212, 255, 0.2));
                color: {OneSoulTheme.TEXT_GOLD};
                border-left: 4px solid {OneSoulTheme.GOLD};
                font-weight: bold;
            }}
        """)

    def add_3d_shadow(self):
        """Add 3D shadow effect to sidebar"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 212, 255, 80))
        shadow.setOffset(5, 0)
        self.setGraphicsEffect(shadow)

    def toggle_sidebar(self):
        """Toggle sidebar with animation"""
        self.is_collapsed = not self.is_collapsed
        target_width = OneSoulTheme.SIDEBAR_COLLAPSED if self.is_collapsed else OneSoulTheme.SIDEBAR_EXPANDED

        # Animate width
        self.anim = QPropertyAnimation(self, b"minimumWidth")
        self.anim.setDuration(300)
        self.anim.setStartValue(self.width())
        self.anim.setEndValue(target_width)
        self.anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.anim.start()

        self.anim2 = QPropertyAnimation(self, b"maximumWidth")
        self.anim2.setDuration(300)
        self.anim2.setStartValue(self.width())
        self.anim2.setEndValue(target_width)
        self.anim2.setEasingCurve(QEasingCurve.InOutCubic)
        self.anim2.start()

        # Update button text
        for module_id, display_text, icon in self.modules:
            btn = self.module_buttons[module_id]
            if self.is_collapsed:
                btn.setText(icon)
                btn.setToolTip(display_text)
                btn.setStyleSheet(btn.styleSheet() + "text-align: center;")
            else:
                btn.setText(f"{icon}  {display_text}")
                btn.setToolTip("")
                self.apply_3d_styles()

    def select_module(self, module_id):
        """Select a module"""
        # Deactivate previous
        if self.active_module in self.module_buttons:
            self.module_buttons[self.active_module].setProperty("active", False)
            self.module_buttons[self.active_module].setStyle(self.module_buttons[self.active_module].style())

        # Activate new
        if module_id in self.module_buttons:
            self.module_buttons[module_id].setProperty("active", True)
            self.module_buttons[module_id].setStyle(self.module_buttons[module_id].style())
            self.active_module = module_id
            self.module_selected.emit(module_id)


# ==================== MODERN TOP BAR ====================

class ModernTopBar(QWidget):
    """Top bar with LARGE logo only (no text)"""

    license_clicked = pyqtSignal()

    def __init__(self, license_manager, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        """Initialize top bar"""
        self.setFixedHeight(OneSoulTheme.TOPBAR_HEIGHT)

        layout = QHBoxLayout()
        layout.setContentsMargins(20, 5, 20, 5)  # Reduced vertical margins for compact look

        # Left: ANIMATED Logo (2x size, no text)
        animated_logo_path = os.path.join("gui-redesign", "assets", "onesoul_animated_logo.html")
        static_logo_path = os.path.join("gui-redesign", "assets", "onesoul_logo.svg")

        # Try animated HTML logo first (if QWebEngineView available)
        if HAS_WEB_ENGINE and os.path.exists(animated_logo_path):
            self.logo = QWebEngineView()
            self.logo.setFixedSize(240, 145)  # Increased height for OneSoul text visibility

            # Make background transparent
            self.logo.setStyleSheet("background: transparent;")

            # Set page background to transparent
            from PyQt5.QtGui import QColor
            self.logo.page().setBackgroundColor(QColor(0, 0, 0, 0))  # Fully transparent

            # Load animated HTML logo
            logo_url = QUrl.fromLocalFile(os.path.abspath(animated_logo_path))
            self.logo.setUrl(logo_url)
            layout.addWidget(self.logo)

        elif os.path.exists(static_logo_path):
            # Fallback to static SVG
            self.logo = QSvgWidget(static_logo_path)
            self.logo.setFixedSize(120, 80)  # 2x original (was 60x40)
            layout.addWidget(self.logo)
        else:
            # Final fallback: text logo
            logo_text = QLabel("◈ ONESOUL")
            logo_text.setStyleSheet(f"""
                color: {OneSoulTheme.TEXT_GOLD};
                font-size: 28px;
                font-weight: bold;
                letter-spacing: 6px;
            """)
            layout.addWidget(logo_text)

        layout.addStretch()

        # Right: License status (aligned to top)
        self.license_label = QLabel()
        self.license_label.setCursor(Qt.PointingHandCursor)
        self.license_label.mousePressEvent = lambda e: self.license_clicked.emit()
        layout.addWidget(self.license_label, alignment=Qt.AlignTop)

        self.setLayout(layout)

    def apply_styles(self):
        """Apply top bar styles"""
        self.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {OneSoulTheme.BG_SIDEBAR},
                    stop:1 rgba(5, 7, 18, 0.95));
                border-bottom: 2px solid {OneSoulTheme.BORDER_GLOW};
            }}
        """)

        # Add 3D shadow to top bar
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 212, 255, 60))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

    def update_license_status(self):
        """Update license status"""
        status_text = self.license_manager.get_license_status_text()
        self.license_label.setText(status_text)

        if "✅" in status_text:
            color = OneSoulTheme.CYAN
        else:
            color = OneSoulTheme.BTN_DANGER

        self.license_label.setStyleSheet(f"""
            color: {color};
            font-weight: bold;
            font-size: 11px;
            padding: 3px 24px;
            background: {OneSoulTheme.BG_ELEVATED};
            border: 1px solid {color};
            border-radius: 4px;
        """)


# ==================== 3D CONTENT WRAPPER ====================

class Content3DWrapper(QWidget):
    """Wraps module content in 3D card with depth and scrolling"""

    def __init__(self, content_widget, parent=None):
        super().__init__(parent)
        self.content_widget = content_widget

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        # Scroll area for content (prevents overlap)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        # Card container with 3D effect
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {OneSoulTheme.BG_ELEVATED},
                    stop:1 rgba(22, 27, 34, 0.8));
                border: 1px solid {OneSoulTheme.BORDER_GLOW};
                border-radius: 12px;
            }}
        """)

        # Add 3D shadow to card
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 212, 255, 70))
        shadow.setOffset(0, 8)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.addWidget(content_widget)
        card.setLayout(card_layout)

        # Add card to scroll area
        scroll_area.setWidget(card)

        layout.addWidget(scroll_area)
        self.setLayout(layout)


# ==================== MAIN WINDOW ====================

class VideoToolSuiteGUI(QMainWindow):
    """OneSoul Flow - Professional 3D Modern UI"""

    def __init__(self, license_manager, config):
        super().__init__()
        self.license_manager = license_manager
        self.config = config
        self.links = []

        self.init_ui()
        self.apply_global_theme()
        self.update_license_status()
        self.setup_responsive()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("OneSoul Flow - Video Automation Suite")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(1024, 768)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar
        self.top_bar = ModernTopBar(self.license_manager)
        self.top_bar.license_clicked.connect(self.show_license_info)
        main_layout.addWidget(self.top_bar)

        # Content row
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        # Sidebar
        self.sidebar = Modern3DSidebar()
        self.sidebar.module_selected.connect(self.navigate_to_module)
        content_row.addWidget(self.sidebar)

        # Content area with stacked widget
        self.stacked_widget = QStackedWidget()

        # Create module pages wrapped in 3D cards
        self.link_grabber = self.wrap_in_3d(
            LinkGrabberPage(
                shared_links=self.links,
                download_callback=self.open_video_downloader_from_grabber
            )
        )
        self.video_downloader = self.wrap_in_3d(
            VideoDownloaderPage(back_callback=self.go_to_main_menu, links=self.links)
        )
        self.combined_workflow = self.wrap_in_3d(
            CombinedWorkflowPage(go_back_callback=self.go_to_main_menu, shared_links=self.links)
        )
        self.video_editor = self.wrap_in_3d(
            IntegratedVideoEditor(self.go_to_main_menu)
        )
        self.metadata_remover = self.wrap_in_3d(
            MetadataRemoverPage(self.go_to_main_menu)
        )
        self.auto_uploader = self.wrap_in_3d(
            AutoUploaderPage(self.go_to_main_menu)
        )
        self.api_config = self.wrap_in_3d(
            APIConfigPage(self.go_to_main_menu)
        )

        self.stacked_widget.addWidget(self.link_grabber)
        self.stacked_widget.addWidget(self.video_downloader)
        self.stacked_widget.addWidget(self.combined_workflow)
        self.stacked_widget.addWidget(self.video_editor)
        self.stacked_widget.addWidget(self.metadata_remover)
        self.stacked_widget.addWidget(self.auto_uploader)
        self.stacked_widget.addWidget(self.api_config)

        content_row.addWidget(self.stacked_widget, 1)

        content_widget = QWidget()
        content_widget.setLayout(content_row)
        main_layout.addWidget(content_widget, 1)

        central.setLayout(main_layout)

    def wrap_in_3d(self, widget):
        """Wrap module widget in 3D container"""
        return Content3DWrapper(widget)

    def apply_global_theme(self):
        """Apply centralized theme to entire app"""
        # Apply global stylesheet
        self.setStyleSheet(OneSoulTheme.get_global_stylesheet())

        # Set Fusion style for modern look
        QApplication.setStyle("Fusion")

    def setup_responsive(self):
        """Setup responsive behavior"""
        # Auto-adjust on window resize
        self.resizeEvent = self.on_window_resize

    def on_window_resize(self, event):
        """Handle window resize for responsiveness"""
        width = event.size().width()

        # Auto-collapse sidebar on small screens
        if width < 1200 and not self.sidebar.is_collapsed:
            self.sidebar.toggle_sidebar()
        elif width >= 1200 and self.sidebar.is_collapsed:
            self.sidebar.toggle_sidebar()

    def navigate_to_module(self, module_id):
        """Navigate to module"""
        module_map = {
            "link_grabber": 0,
            "video_downloader": 1,
            "combo_workflow": 2,
            "video_editor": 3,
            "metadata_remover": 4,
            "auto_uploader": 5,
            "api_config": 6
        }

        index = module_map.get(module_id, 0)
        self.stacked_widget.setCurrentIndex(index)

    def open_video_downloader_from_grabber(self):
        """Push freshly grabbed links into the downloader and switch view"""
        downloader_wrapper = getattr(self, "video_downloader", None)
        downloader_widget = getattr(downloader_wrapper, "content_widget", downloader_wrapper)

        if downloader_widget and hasattr(downloader_widget, "update_links"):
            downloader_widget.update_links(self.links)

        if hasattr(self.sidebar, "select_module"):
            self.sidebar.select_module("video_downloader")
        else:
            self.navigate_to_module("video_downloader")

    def go_to_main_menu(self):
        """Go back to first module"""
        self.stacked_widget.setCurrentIndex(0)

        # Deselect sidebar
        if self.sidebar.active_module:
            btn = self.sidebar.module_buttons.get(self.sidebar.active_module)
            if btn:
                btn.setProperty("active", False)
                btn.setStyle(btn.style())
            self.sidebar.active_module = None

    def update_license_status(self):
        """Update license status"""
        self.top_bar.update_license_status()

    def show_license_info(self):
        """Show license dialog"""
        from modules.ui import LicenseInfoDialog
        dialog = LicenseInfoDialog(self.license_manager, self)
        # Apply theme to dialog
        dialog.setStyleSheet(OneSoulTheme.get_global_stylesheet())
        dialog.exec_()
        self.update_license_status()
