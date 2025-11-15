"""
gui_modern.py
Modern OneSoul Flow UI integrated with existing modules
This is a drop-in replacement for gui.py with modern design
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QSpacerItem, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont
from PyQt5.QtSvg import QSvgWidget
import os

# Import existing module pages
from modules.link_grabber.gui import LinkGrabberPage
from modules.video_downloader.gui import VideoDownloaderPage
from modules.video_editor.integrated_editor import IntegratedVideoEditor
from modules.metadata_remover.gui import MetadataRemoverPage
from modules.auto_uploader.gui import AutoUploaderPage
from modules.api_manager.gui import APIConfigPage
from modules.workflows.combo import CombinedWorkflowPage


# ==================== OneSoul Flow Design System ====================

class Colors:
    """OneSoul Flow color palette"""
    BG_PRIMARY = "#050712"
    BG_SIDEBAR = "#0a0e1a"
    BG_ELEVATED = "#161b22"
    CYAN = "#00d4ff"
    MAGENTA = "#ff00ff"
    GOLD = "#ffd700"
    TEXT_PRIMARY = "#ffffff"
    TEXT_GOLD = "#ffd700"
    TEXT_CYAN = "#00d4ff"
    BORDER_PRIMARY = "rgba(0, 212, 255, 0.2)"
    BG_HOVER = "rgba(0, 212, 255, 0.05)"
    BG_ACTIVE = "rgba(0, 212, 255, 0.1)"


class Sizes:
    """Size constants"""
    SIDEBAR_EXPANDED = 250
    SIDEBAR_COLLAPSED = 60
    TOPBAR_HEIGHT = 60


# ==================== Modern Sidebar ====================

class ModernSidebar(QWidget):
    """Modern collapsible sidebar navigation"""

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
        self.apply_styles()

    def init_ui(self):
        """Initialize sidebar UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toggle button
        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setFixedHeight(Sizes.TOPBAR_HEIGHT)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        layout.addWidget(self.toggle_btn)

        # Module buttons
        for module_id, display_text, icon in self.modules:
            btn = QPushButton(f"{icon}  {display_text}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("module_id", module_id)
            btn.setProperty("active", False)
            btn.clicked.connect(lambda checked, m=module_id: self.select_module(m))
            self.module_buttons[module_id] = btn
            layout.addWidget(btn)

        layout.addStretch()
        self.setLayout(layout)
        self.setFixedWidth(Sizes.SIDEBAR_EXPANDED)

    def apply_styles(self):
        """Apply sidebar styles"""
        self.setStyleSheet(f"""
            QWidget {{
                background: {Colors.BG_SIDEBAR};
                border-right: 1px solid {Colors.BORDER_PRIMARY};
            }}

            QPushButton {{
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                border-left: 3px solid transparent;
                text-align: left;
                padding: 20px;
                font-size: 14px;
                font-weight: normal;
            }}

            QPushButton:hover {{
                background: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}

            QPushButton[active="true"] {{
                background: {Colors.BG_ACTIVE};
                color: {Colors.TEXT_GOLD};
                border-left: 3px solid {Colors.CYAN};
                font-weight: bold;
            }}
        """)

    def toggle_sidebar(self):
        """Toggle sidebar collapse/expand"""
        self.is_collapsed = not self.is_collapsed
        target_width = Sizes.SIDEBAR_COLLAPSED if self.is_collapsed else Sizes.SIDEBAR_EXPANDED

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
            else:
                btn.setText(f"{icon}  {display_text}")
                btn.setToolTip("")

    def select_module(self, module_id):
        """Select a module"""
        # Deactivate previous
        if self.active_module and self.active_module in self.module_buttons:
            self.module_buttons[self.active_module].setProperty("active", False)
            self.module_buttons[self.active_module].setStyle(self.module_buttons[self.active_module].style())

        # Activate new
        if module_id in self.module_buttons:
            self.module_buttons[module_id].setProperty("active", True)
            self.module_buttons[module_id].setStyle(self.module_buttons[module_id].style())
            self.active_module = module_id
            self.module_selected.emit(module_id)


# ==================== Modern Top Bar ====================

class ModernTopBar(QWidget):
    """Modern top bar with logo and user info"""

    license_clicked = pyqtSignal()

    def __init__(self, license_manager, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        """Initialize top bar"""
        self.setFixedHeight(Sizes.TOPBAR_HEIGHT)

        layout = QHBoxLayout()
        layout.setContentsMargins(20, 10, 20, 10)

        # Left: Logo + Title
        left_layout = QHBoxLayout()

        # Logo (try to load SVG, fallback to text)
        logo_path = os.path.join("gui-redesign", "assets", "onesoul_logo.svg")
        if os.path.exists(logo_path):
            self.logo = QSvgWidget(logo_path)
            self.logo.setFixedSize(60, 40)
            left_layout.addWidget(self.logo)

        title = QLabel("ONESOUL FLOW")
        title.setStyleSheet(f"""
            color: {Colors.TEXT_GOLD};
            font-size: 20px;
            font-weight: bold;
            letter-spacing: 4px;
        """)
        left_layout.addWidget(title)

        layout.addLayout(left_layout)
        layout.addStretch()

        # Right: License status
        self.license_label = QLabel()
        self.license_label.setCursor(Qt.PointingHandCursor)
        self.license_label.mousePressEvent = lambda e: self.license_clicked.emit()
        layout.addWidget(self.license_label)

        self.setLayout(layout)

    def apply_styles(self):
        """Apply top bar styles"""
        self.setStyleSheet(f"""
            QWidget {{
                background: {Colors.BG_SIDEBAR};
                border-bottom: 1px solid {Colors.BORDER_PRIMARY};
            }}
        """)

    def update_license_status(self):
        """Update license status display"""
        status_text = self.license_manager.get_license_status_text()
        self.license_label.setText(status_text)

        if "✅" in status_text:
            color = Colors.CYAN
        else:
            color = "#ff3860"

        self.license_label.setStyleSheet(f"""
            color: {color};
            font-weight: bold;
            padding: 5px 10px;
        """)


# ==================== Main Modern Window ====================

class VideoToolSuiteGUI(QMainWindow):
    """Modern OneSoul Flow main window - drop-in replacement for old GUI"""

    def __init__(self, license_manager, config):
        super().__init__()
        self.license_manager = license_manager
        self.config = config
        self.links = []  # Shared links between modules

        self.init_ui()
        self.apply_theme()
        self.update_license_status()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("OneSoul Flow - Video Automation Suite")
        self.setGeometry(100, 100, 1280, 800)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar
        self.top_bar = ModernTopBar(self.license_manager)
        self.top_bar.license_clicked.connect(self.show_license_info)
        main_layout.addWidget(self.top_bar)

        # Content row (sidebar + pages)
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        # Sidebar
        self.sidebar = ModernSidebar()
        self.sidebar.module_selected.connect(self.navigate_to_module)
        content_row.addWidget(self.sidebar)

        # Content area (stacked widget for modules)
        self.stacked_widget = QStackedWidget()

        # Create module pages (same as old GUI)
        self.link_grabber = LinkGrabberPage(
            go_back_callback=self.go_to_main_menu,
            shared_links=self.links
        )
        self.video_downloader = VideoDownloaderPage(
            back_callback=self.go_to_main_menu,
            links=self.links
        )
        self.combined_workflow = CombinedWorkflowPage(
            go_back_callback=self.go_to_main_menu,
            shared_links=self.links
        )
        self.video_editor = IntegratedVideoEditor(self.go_to_main_menu)
        self.metadata_remover = MetadataRemoverPage(self.go_to_main_menu)
        self.auto_uploader = AutoUploaderPage(self.go_to_main_menu)
        self.api_config = APIConfigPage(self.go_to_main_menu)

        # Add pages to stacked widget
        self.stacked_widget.addWidget(self.link_grabber)  # index 0
        self.stacked_widget.addWidget(self.video_downloader)  # index 1
        self.stacked_widget.addWidget(self.combined_workflow)  # index 2
        self.stacked_widget.addWidget(self.video_editor)  # index 3
        self.stacked_widget.addWidget(self.metadata_remover)  # index 4
        self.stacked_widget.addWidget(self.auto_uploader)  # index 5
        self.stacked_widget.addWidget(self.api_config)  # index 6

        content_row.addWidget(self.stacked_widget, 1)

        content_widget = QWidget()
        content_widget.setLayout(content_row)
        main_layout.addWidget(content_widget, 1)

        central.setLayout(main_layout)

    def apply_theme(self):
        """Apply modern dark theme"""
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}

            QStackedWidget {{
                background: {Colors.BG_PRIMARY};
            }}
        """)

        # Set Fusion style for modern look
        from PyQt5.QtWidgets import QApplication
        QApplication.setStyle("Fusion")

    def navigate_to_module(self, module_id):
        """Navigate to a module by ID"""
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

    def go_to_main_menu(self):
        """Go back to first module (Link Grabber acts as home)"""
        self.video_downloader.update_links(self.links)
        self.stacked_widget.setCurrentIndex(0)
        # Reset sidebar selection
        if self.sidebar.active_module:
            btn = self.sidebar.module_buttons.get(self.sidebar.active_module)
            if btn:
                btn.setProperty("active", False)
                btn.setStyle(btn.style())
            self.sidebar.active_module = None

    def update_license_status(self):
        """Update license status in top bar"""
        self.top_bar.update_license_status()

    def show_license_info(self):
        """Show license information dialog"""
        from modules.ui import LicenseInfoDialog
        dialog = LicenseInfoDialog(self.license_manager, self)
        dialog.exec_()
        self.update_license_status()
