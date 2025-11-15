"""
OneSoul Flow - Top Bar Component
Header with logo (left) and user info (right)
"""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtSvg import QSvgWidget
import os

# Handle imports for both standalone and package use
try:
    from ..styles.colors import Colors, Sizes, Fonts
    from ..styles.stylesheet import StyleSheet
except (ImportError, ValueError):
    from styles.colors import Colors, Sizes, Fonts
    from styles.stylesheet import StyleSheet


class TopBar(QWidget):
    """Modern top bar with branding and user info"""

    # Signals
    settings_clicked = pyqtSignal()
    license_clicked = pyqtSignal()
    user_info_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.user_name = "Toseeq Ur Rehman"
        self.license_active = True
        self.license_text = "License Active"

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        """Initialize top bar UI"""
        self.setObjectName("topBar")
        self.setFixedHeight(Sizes.TOPBAR_HEIGHT)

        # Main layout
        layout = QHBoxLayout()
        layout.setContentsMargins(
            Sizes.PADDING_MEDIUM,
            Sizes.PADDING_SMALL,
            Sizes.PADDING_MEDIUM,
            Sizes.PADDING_SMALL
        )
        layout.setSpacing(Sizes.MARGIN_MEDIUM)

        # Left side: Logo + App Title
        left_container = QWidget()
        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(Sizes.MARGIN_MEDIUM)

        # Logo (SVG)
        self.logo = QSvgWidget()
        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets",
            "onesoul_logo.svg"
        )
        if os.path.exists(logo_path):
            self.logo.load(logo_path)
            # Set logo size (maintaining aspect ratio 180:120 = 3:2)
            logo_height = Sizes.LOGO_HEIGHT_NORMAL
            logo_width = int(logo_height * 1.5)  # 3:2 aspect ratio
            self.logo.setFixedSize(logo_width, logo_height)
        else:
            # Fallback if SVG not found
            self.logo.setFixedSize(60, 40)

        left_layout.addWidget(self.logo)

        # App title
        self.app_title = QLabel("ONESOUL FLOW")
        self.app_title.setObjectName("appTitle")
        left_layout.addWidget(self.app_title)

        left_container.setLayout(left_layout)
        layout.addWidget(left_container)

        # Spacer to push right content to the right
        layout.addSpacerItem(
            QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # Right side: User Info + Action Buttons
        right_container = QWidget()
        right_layout = QHBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(Sizes.MARGIN_MEDIUM)

        # User info section (clickable)
        user_info_container = QWidget()
        user_info_container.setCursor(Qt.PointingHandCursor)
        user_info_container.mousePressEvent = lambda e: self.user_info_clicked.emit()
        user_info_layout = QHBoxLayout()
        user_info_layout.setContentsMargins(
            Sizes.PADDING_SMALL,
            Sizes.PADDING_SMALL,
            Sizes.PADDING_SMALL,
            Sizes.PADDING_SMALL
        )
        user_info_layout.setSpacing(Sizes.MARGIN_SMALL)

        # User avatar/icon (placeholder circle)
        self.avatar = QLabel("👤")
        self.avatar.setFixedSize(Sizes.AVATAR_MEDIUM, Sizes.AVATAR_MEDIUM)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setStyleSheet(f"""
            QLabel {{
                background: {Colors.BG_ELEVATED};
                border: 2px solid {Colors.CYAN};
                border-radius: {Sizes.AVATAR_MEDIUM // 2}px;
                font-size: {Sizes.ICON_MEDIUM}px;
            }}
        """)
        user_info_layout.addWidget(self.avatar)

        # User name and license status
        user_text_container = QWidget()
        user_text_layout = QVBoxLayout()
        user_text_layout.setContentsMargins(0, 0, 0, 0)
        user_text_layout.setSpacing(2)

        self.user_name_label = QLabel(self.user_name)
        self.user_name_label.setObjectName("userName")
        user_text_layout.addWidget(self.user_name_label)

        self.license_status_label = QLabel(self.license_text)
        self.update_license_status()
        user_text_layout.addWidget(self.license_status_label)

        user_text_container.setLayout(user_text_layout)
        user_info_layout.addWidget(user_text_container)

        user_info_container.setLayout(user_info_layout)
        right_layout.addWidget(user_info_container)

        # Settings button
        self.settings_button = QPushButton("⚙️")
        self.settings_button.setObjectName("iconButton")
        self.settings_button.setCursor(Qt.PointingHandCursor)
        self.settings_button.setToolTip("Settings")
        self.settings_button.setFixedSize(40, 40)
        self.settings_button.clicked.connect(self.settings_clicked.emit)
        right_layout.addWidget(self.settings_button)

        # License info button
        self.license_button = QPushButton("🔑")
        self.license_button.setObjectName("iconButton")
        self.license_button.setCursor(Qt.PointingHandCursor)
        self.license_button.setToolTip("License Information")
        self.license_button.setFixedSize(40, 40)
        self.license_button.clicked.connect(self.license_clicked.emit)
        right_layout.addWidget(self.license_button)

        right_container.setLayout(right_layout)
        layout.addWidget(right_container)

        self.setLayout(layout)

    def apply_styles(self):
        """Apply stylesheets"""
        self.setStyleSheet(StyleSheet.get_top_bar())

    def set_user_info(self, name, license_active=True, license_text=None):
        """Update user information display"""
        self.user_name = name
        self.license_active = license_active

        if license_text:
            self.license_text = license_text
        else:
            self.license_text = "✓ License Active" if license_active else "✗ License Expired"

        self.user_name_label.setText(self.user_name)
        self.license_status_label.setText(self.license_text)
        self.update_license_status()

    def update_license_status(self):
        """Update license status label styling"""
        if self.license_active:
            self.license_status_label.setObjectName("licenseStatusActive")
        else:
            self.license_status_label.setObjectName("licenseStatusExpired")
        self.license_status_label.setStyleSheet(StyleSheet.get_top_bar())

    def set_logo_size(self, height):
        """Update logo size (for responsive design)"""
        width = int(height * 1.5)  # Maintain 3:2 aspect ratio
        self.logo.setFixedSize(width, height)

    def resize_for_screen(self, screen_width):
        """Adjust top bar elements based on screen width"""
        from ..styles.colors import Breakpoints

        # Adjust logo size
        logo_size = Breakpoints.get_logo_size(screen_width)
        self.set_logo_size(logo_size)

        # Adjust font sizes
        if screen_width >= Breakpoints.EXTRA_LARGE:
            font_size = 22
        elif screen_width >= Breakpoints.LARGE:
            font_size = 20
        else:
            font_size = 18

        self.app_title.setStyleSheet(f"""
            QLabel#appTitle {{
                color: {Colors.TEXT_GOLD};
                font-size: {font_size}px;
                font-weight: {Fonts.WEIGHT_BOLD};
                letter-spacing: 4px;
            }}
        """)
