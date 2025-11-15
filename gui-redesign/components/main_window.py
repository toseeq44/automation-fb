"""
OneSoul Flow - Main Application Window
Modern responsive window combining all UI components
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QApplication, QDesktopWidget
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont, QIcon

# Handle imports for both standalone and package use
try:
    from .topbar import TopBar
    from .sidebar import Sidebar
    from .content_area import ContentArea
    from ..styles.colors import Colors, Sizes, Fonts, Breakpoints
    from ..styles.stylesheet import StyleSheet
except (ImportError, ValueError):
    from components.topbar import TopBar
    from components.sidebar import Sidebar
    from components.content_area import ContentArea
    from styles.colors import Colors, Sizes, Fonts, Breakpoints
    from styles.stylesheet import StyleSheet


class OneSoulFlowWindow(QMainWindow):
    """Main application window with modern responsive design"""

    def __init__(self):
        super().__init__()

        # Window properties
        self.setWindowTitle("OneSoul Flow - Video Automation Suite")
        self.setMinimumSize(
            Breakpoints.SMALL + Sizes.SIDEBAR_COLLAPSED,
            480  # Minimum height
        )

        # Initialize components
        self.top_bar = None
        self.sidebar = None
        self.content_area = None

        self.init_ui()
        self.connect_signals()
        self.apply_styles()
        self.center_window()

        # Set initial size based on screen
        self.resize_for_screen()

    def init_ui(self):
        """Initialize main UI structure"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout (vertical: top bar + content row)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar
        self.top_bar = TopBar()
        main_layout.addWidget(self.top_bar)

        # Content row (horizontal: sidebar + content area)
        content_row = QWidget()
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        content_layout.addWidget(self.sidebar)

        # Content area
        self.content_area = ContentArea()
        content_layout.addWidget(self.content_area, 1)  # Stretch factor 1

        content_row.setLayout(content_layout)
        main_layout.addWidget(content_row, 1)  # Stretch factor 1

        central_widget.setLayout(main_layout)

    def connect_signals(self):
        """Connect component signals"""
        # Sidebar module selection
        self.sidebar.module_selected.connect(self.on_module_selected)

        # Sidebar toggle
        self.sidebar.toggled.connect(self.on_sidebar_toggled)

        # Top bar actions
        self.top_bar.settings_clicked.connect(self.on_settings_clicked)
        self.top_bar.license_clicked.connect(self.on_license_clicked)
        self.top_bar.user_info_clicked.connect(self.on_user_info_clicked)

    def apply_styles(self):
        """Apply global stylesheet"""
        # Set application-wide style
        self.setStyleSheet(StyleSheet.get_complete_stylesheet())

        # Set Fusion style for modern look
        QApplication.setStyle("Fusion")

    def center_window(self):
        """Center window on screen"""
        frame_geometry = self.frameGeometry()
        screen_center = QDesktopWidget().availableGeometry().center()
        frame_geometry.moveCenter(screen_center)
        self.move(frame_geometry.topLeft())

    def resize_for_screen(self):
        """Resize window based on available screen size"""
        screen = QDesktopWidget().availableGeometry()
        screen_width = screen.width()
        screen_height = screen.height()

        # Determine initial window size
        if screen_width >= Breakpoints.EXTRA_LARGE:
            # 4K screens: Use 60% of screen
            width = int(screen_width * 0.6)
            height = int(screen_height * 0.7)
        elif screen_width >= Breakpoints.LARGE:
            # Full HD: Use 70% of screen
            width = int(screen_width * 0.7)
            height = int(screen_height * 0.75)
        elif screen_width >= Breakpoints.MEDIUM:
            # HD: Use 80% of screen
            width = int(screen_width * 0.8)
            height = int(screen_height * 0.8)
        else:
            # Small screens: Use 90% of screen
            width = int(screen_width * 0.9)
            height = int(screen_height * 0.85)

        self.resize(width, height)

        # Auto-collapse sidebar on small screens
        if screen_width < Breakpoints.MEDIUM:
            self.sidebar.set_collapsed(True)

        # Adjust top bar for screen size
        self.top_bar.resize_for_screen(screen_width)

    def resizeEvent(self, event):
        """Handle window resize events for responsive behavior"""
        super().resizeEvent(event)

        # Get new window width
        new_width = event.size().width()

        # Adjust top bar elements
        self.top_bar.resize_for_screen(new_width)

        # Auto-collapse/expand sidebar based on width
        if new_width < Breakpoints.MEDIUM and not self.sidebar.is_collapsed:
            self.sidebar.set_collapsed(True)

    # ==================== Event Handlers ====================

    def on_module_selected(self, module_id):
        """Handle module selection from sidebar"""
        print(f"Module selected: {module_id}")
        self.content_area.show_page(module_id)

    def on_sidebar_toggled(self, is_collapsed):
        """Handle sidebar toggle"""
        state = "collapsed" if is_collapsed else "expanded"
        print(f"Sidebar {state}")

    def on_settings_clicked(self):
        """Handle settings button click"""
        print("Settings clicked")
        # TODO: Open settings dialog

    def on_license_clicked(self):
        """Handle license button click"""
        print("License info clicked")
        # TODO: Open license dialog

    def on_user_info_clicked(self):
        """Handle user info click"""
        print("User info clicked")
        # TODO: Open user profile dialog

    # ==================== Public Methods ====================

    def set_user_info(self, name, license_active=True, license_text=None):
        """Update user information in top bar"""
        self.top_bar.set_user_info(name, license_active, license_text)

    def select_module(self, module_id):
        """Programmatically select a module"""
        self.sidebar.select_module(module_id)

    def get_active_module(self):
        """Get currently active module ID"""
        return self.sidebar.get_active_module()

    def show_welcome(self):
        """Show welcome page"""
        self.content_area.show_page("welcome")
        self.sidebar.set_active_module(None)

    def add_custom_page(self, page_id, page_widget):
        """Add a custom content page"""
        self.content_area.add_page(page_id, page_widget)

    def replace_module_page(self, module_id, new_page_widget):
        """Replace a module's placeholder page with actual implementation"""
        self.content_area.replace_page(module_id, new_page_widget)
