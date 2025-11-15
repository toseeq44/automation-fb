"""
OneSoul Flow - Content Area Component
Dynamic content area that changes based on selected module
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QStackedWidget,
    QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont

# Handle imports for both standalone and package use
try:
    from ..styles.colors import Colors, Sizes, Fonts
    from ..styles.stylesheet import StyleSheet
except (ImportError, ValueError):
    from styles.colors import Colors, Sizes, Fonts
    from styles.stylesheet import StyleSheet


class ContentCard(QWidget):
    """Reusable card widget for content sections"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contentCard")
        self.init_ui()

    def init_ui(self):
        """Initialize card UI"""
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(
            Sizes.PADDING_MEDIUM,
            Sizes.PADDING_MEDIUM,
            Sizes.PADDING_MEDIUM,
            Sizes.PADDING_MEDIUM
        )
        self.layout.setSpacing(Sizes.MARGIN_MEDIUM)
        self.setLayout(self.layout)


class ModuleContentPage(QWidget):
    """Base class for module content pages"""

    def __init__(self, module_id, title, subtitle=None, parent=None):
        super().__init__(parent)
        self.module_id = module_id
        self.title_text = title
        self.subtitle_text = subtitle

        self.init_base_ui()

    def init_base_ui(self):
        """Initialize base UI structure"""
        # Main layout with scroll area
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Content container
        content_container = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(
            Sizes.PADDING_LARGE,
            Sizes.PADDING_LARGE,
            Sizes.PADDING_LARGE,
            Sizes.PADDING_LARGE
        )
        self.content_layout.setSpacing(Sizes.MARGIN_LARGE)

        # Title
        self.title_label = QLabel(self.title_text)
        self.title_label.setObjectName("contentTitle")
        self.content_layout.addWidget(self.title_label)

        # Subtitle (optional)
        if self.subtitle_text:
            self.subtitle_label = QLabel(self.subtitle_text)
            self.subtitle_label.setObjectName("contentSubtitle")
            self.content_layout.addWidget(self.subtitle_label)

        # Placeholder for module-specific content
        # Subclasses should add widgets to self.content_layout

        content_container.setLayout(self.content_layout)
        scroll_area.setWidget(content_container)

        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)

    def add_card(self, card):
        """Add a card to the content layout"""
        self.content_layout.addWidget(card)

    def add_widget(self, widget):
        """Add any widget to the content layout"""
        self.content_layout.addWidget(widget)


class WelcomePage(ModuleContentPage):
    """Welcome/home page when no module is selected"""

    def __init__(self, parent=None):
        super().__init__(
            "welcome",
            "Welcome to OneSoul Flow",
            "Professional Video Management & Automation Suite",
            parent
        )

        self.build_welcome_content()

    def build_welcome_content(self):
        """Build welcome page content"""
        # Welcome card
        welcome_card = ContentCard()

        welcome_text = QLabel(
            "Select a module from the sidebar to get started.\n\n"
            "Available Modules:\n"
            "• Link Grabber - Extract video links\n"
            "• Video Downloader - Download videos efficiently\n"
            "• Grab + Download - Combined workflow\n"
            "• Video Editor - Edit and enhance videos\n"
            "• Metadata Remover - Clean video metadata\n"
            "• Auto Uploader - Automated video uploads\n"
            "• API Config - Configure API credentials"
        )
        welcome_text.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: {Sizes.FONT_BODY}px;
                line-height: 1.6;
            }}
        """)
        welcome_text.setWordWrap(True)

        welcome_card.layout.addWidget(welcome_text)
        self.add_card(welcome_card)


class PlaceholderModulePage(ModuleContentPage):
    """Placeholder page for modules during development"""

    def __init__(self, module_id, title, parent=None):
        super().__init__(
            module_id,
            title,
            f"This is the {title} module",
            parent
        )

        self.build_placeholder_content()

    def build_placeholder_content(self):
        """Build placeholder content"""
        placeholder_card = ContentCard()

        placeholder_text = QLabel(
            "This module's interface is being redesigned.\n\n"
            "The new modern UI will provide:\n"
            "• Improved user experience\n"
            "• Better visual feedback\n"
            "• Enhanced functionality\n"
            "• Responsive design\n\n"
            "Stay tuned for updates!"
        )
        placeholder_text.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: {Sizes.FONT_BODY}px;
                line-height: 1.6;
            }}
        """)
        placeholder_text.setWordWrap(True)

        placeholder_card.layout.addWidget(placeholder_text)
        self.add_card(placeholder_card)


class ContentArea(QWidget):
    """Main content area with module page switching"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contentArea")

        self.current_module = None
        self.pages = {}

        self.init_ui()
        self.create_default_pages()
        self.apply_styles()

    def init_ui(self):
        """Initialize content area UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Stacked widget for switching between module pages
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        self.setLayout(layout)

    def create_default_pages(self):
        """Create default pages for all modules"""
        # Welcome page
        welcome_page = WelcomePage()
        self.add_page("welcome", welcome_page)
        self.show_page("welcome")

        # Placeholder pages for each module
        modules = [
            ("link_grabber", "Link Grabber"),
            ("video_downloader", "Video Downloader"),
            ("combo_workflow", "Grab + Download"),
            ("video_editor", "Video Editor"),
            ("metadata_remover", "Metadata Remover"),
            ("auto_uploader", "Auto Uploader"),
            ("api_config", "API Configuration"),
        ]

        for module_id, title in modules:
            page = PlaceholderModulePage(module_id, title)
            self.add_page(module_id, page)

    def add_page(self, page_id, page_widget):
        """Add a page to the content area"""
        self.pages[page_id] = page_widget
        self.stacked_widget.addWidget(page_widget)

    def show_page(self, page_id):
        """Show a specific page with fade animation"""
        if page_id in self.pages:
            # Simple switch (fade animation would require additional setup)
            self.stacked_widget.setCurrentWidget(self.pages[page_id])
            self.current_module = page_id

    def get_current_page_id(self):
        """Get currently displayed page ID"""
        return self.current_module

    def replace_page(self, page_id, new_page_widget):
        """Replace an existing page with a new widget"""
        if page_id in self.pages:
            old_widget = self.pages[page_id]
            self.stacked_widget.removeWidget(old_widget)
            old_widget.deleteLater()

        self.pages[page_id] = new_page_widget
        self.stacked_widget.addWidget(new_page_widget)

    def apply_styles(self):
        """Apply stylesheets"""
        self.setStyleSheet(StyleSheet.get_content_area())
