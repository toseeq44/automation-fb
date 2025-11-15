"""
OneSoul Flow - Modern Sidebar Navigation Component
Left-side module navigation with collapse/expand functionality
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel,
    QSpacerItem, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QIcon, QFont

# Handle imports for both standalone and package use
try:
    from ..styles.colors import Colors, Sizes, Fonts
    from ..styles.stylesheet import StyleSheet
except (ImportError, ValueError):
    from styles.colors import Colors, Sizes, Fonts
    from styles.stylesheet import StyleSheet


class ModuleButton(QPushButton):
    """Custom button for sidebar module items"""

    def __init__(self, text, icon_text, parent=None):
        super().__init__(parent)
        self.module_text = text
        self.icon_text = icon_text
        self.is_active = False
        self.is_collapsed = False

        # Set object name for styling
        self.setObjectName("sidebarButton")

        # Set initial properties
        self.setCursor(Qt.PointingHandCursor)
        self.update_text()

    def update_text(self):
        """Update button text based on collapsed state"""
        if self.is_collapsed:
            self.setText(self.icon_text)
        else:
            self.setText(f"{self.icon_text}  {self.module_text}")

    def set_active(self, active):
        """Set button active state"""
        self.is_active = active
        if active:
            self.setObjectName("sidebarButtonActive")
        else:
            self.setObjectName("sidebarButton")
        self.setStyleSheet(StyleSheet.get_sidebar())

    def set_collapsed(self, collapsed):
        """Update button for collapsed state"""
        self.is_collapsed = collapsed
        self.update_text()
        if collapsed:
            self.setToolTip(self.module_text)
        else:
            self.setToolTip("")


class Sidebar(QWidget):
    """Modern sidebar navigation with module buttons"""

    # Signal emitted when module is selected (module_name)
    module_selected = pyqtSignal(str)

    # Signal emitted when sidebar is toggled (is_collapsed)
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.is_collapsed = False
        self.active_module = None

        # Module definitions: (name, display_text, icon)
        self.modules = [
            ("link_grabber", "Link Grabber", "🔗"),
            ("video_downloader", "Video Downloader", "⬇️"),
            ("combo_workflow", "Grab + Download", "🚀"),
            ("video_editor", "Video Editor", "✂️"),
            ("metadata_remover", "Metadata Remover", "🔒"),
            ("auto_uploader", "Auto Uploader", "☁️"),
            ("api_config", "API Config", "🔑"),
        ]

        # Store button references
        self.module_buttons = {}

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        """Initialize sidebar UI"""
        self.setObjectName("sidebar")

        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toggle button at top
        self.toggle_button = QPushButton("☰")
        self.toggle_button.setObjectName("toggleButton")
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.setToolTip("Toggle Sidebar")
        self.toggle_button.setFixedHeight(Sizes.TOPBAR_HEIGHT)
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        layout.addWidget(self.toggle_button)

        # Scroll area for modules (in case of many modules)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Container for module buttons
        modules_container = QWidget()
        modules_layout = QVBoxLayout()
        modules_layout.setContentsMargins(0, Sizes.PADDING_MEDIUM, 0, 0)
        modules_layout.setSpacing(Sizes.MARGIN_SMALL)

        # Create module buttons
        for module_id, display_text, icon in self.modules:
            btn = ModuleButton(display_text, icon, self)
            btn.clicked.connect(lambda checked, m=module_id: self.select_module(m))
            self.module_buttons[module_id] = btn
            modules_layout.addWidget(btn)

        # Add spacer to push buttons to top
        modules_layout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        modules_container.setLayout(modules_layout)
        scroll_area.setWidget(modules_container)

        layout.addWidget(scroll_area)

        self.setLayout(layout)

        # Set initial size
        self.setFixedWidth(Sizes.SIDEBAR_EXPANDED)

    def apply_styles(self):
        """Apply stylesheets to sidebar"""
        self.setStyleSheet(StyleSheet.get_sidebar(not self.is_collapsed))

    def toggle_sidebar(self):
        """Toggle sidebar between expanded and collapsed state"""
        self.is_collapsed = not self.is_collapsed

        # Animate width change
        target_width = Sizes.SIDEBAR_COLLAPSED if self.is_collapsed else Sizes.SIDEBAR_EXPANDED

        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(target_width)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.start()

        # Also animate maximum width
        self.animation2 = QPropertyAnimation(self, b"maximumWidth")
        self.animation2.setDuration(300)
        self.animation2.setStartValue(self.width())
        self.animation2.setEndValue(target_width)
        self.animation2.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation2.start()

        # Update button states
        for btn in self.module_buttons.values():
            btn.set_collapsed(self.is_collapsed)

        # Update toggle button
        if self.is_collapsed:
            self.toggle_button.setText("☰")
            self.toggle_button.setToolTip("Expand Sidebar")
        else:
            self.toggle_button.setText("☰")
            self.toggle_button.setToolTip("Collapse Sidebar")

        # Re-apply styles
        self.apply_styles()

        # Emit signal
        self.toggled.emit(self.is_collapsed)

    def select_module(self, module_id):
        """Select a module and update UI"""
        # Deactivate previous module
        if self.active_module and self.active_module in self.module_buttons:
            self.module_buttons[self.active_module].set_active(False)

        # Activate new module
        if module_id in self.module_buttons:
            self.module_buttons[module_id].set_active(True)
            self.active_module = module_id

            # Emit signal
            self.module_selected.emit(module_id)

    def set_active_module(self, module_id):
        """Programmatically set active module (without triggering signal)"""
        if self.active_module and self.active_module in self.module_buttons:
            self.module_buttons[self.active_module].set_active(False)

        if module_id in self.module_buttons:
            self.module_buttons[module_id].set_active(True)
            self.active_module = module_id

    def get_active_module(self):
        """Get currently active module ID"""
        return self.active_module

    def set_collapsed(self, collapsed):
        """Programmatically set collapsed state"""
        if self.is_collapsed != collapsed:
            self.toggle_sidebar()

    def add_module(self, module_id, display_text, icon):
        """Dynamically add a new module to sidebar"""
        if module_id not in self.module_buttons:
            self.modules.append((module_id, display_text, icon))
            # Would need to rebuild UI to add new button
            # For now, modules should be defined at initialization

    def remove_module(self, module_id):
        """Remove a module from sidebar"""
        if module_id in self.module_buttons:
            self.module_buttons[module_id].deleteLater()
            del self.module_buttons[module_id]
            self.modules = [m for m in self.modules if m[0] != module_id]
