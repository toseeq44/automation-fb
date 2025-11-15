"""
OneSoul Flow - PyQt5 Stylesheet Generator
Modern neon-themed stylesheets for all components
"""

from .colors import Colors, Sizes, Fonts, Effects


class StyleSheet:
    """Generate PyQt5 stylesheets for various components"""

    @staticmethod
    def get_main_window():
        """Main window stylesheet"""
        return f"""
            QMainWindow {{
                background: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                font-family: {Fonts.FAMILY_PRIMARY};
                font-size: {Sizes.FONT_BODY}px;
            }}
        """

    @staticmethod
    def get_top_bar():
        """Top bar stylesheet"""
        return f"""
            QWidget#topBar {{
                background: {Colors.BG_SIDEBAR};
                border-bottom: 1px solid {Colors.BORDER_PRIMARY};
                min-height: {Sizes.TOPBAR_HEIGHT}px;
                max-height: {Sizes.TOPBAR_HEIGHT}px;
            }}

            QLabel#appTitle {{
                color: {Colors.TEXT_GOLD};
                font-size: {Sizes.FONT_HEADING_2}px;
                font-weight: {Fonts.WEIGHT_BOLD};
                padding-left: {Sizes.PADDING_SMALL}px;
            }}

            QLabel#userName {{
                color: {Colors.TEXT_GOLD};
                font-size: {Sizes.FONT_BODY}px;
                font-weight: {Fonts.WEIGHT_SEMIBOLD};
            }}

            QLabel#licenseStatus {{
                color: {Colors.TEXT_CYAN};
                font-size: {Sizes.FONT_SMALL}px;
            }}

            QLabel#licenseStatusActive {{
                color: {Colors.SUCCESS};
            }}

            QLabel#licenseStatusExpired {{
                color: {Colors.ERROR};
            }}
        """

    @staticmethod
    def get_sidebar(expanded=True):
        """Sidebar stylesheet"""
        width = Sizes.SIDEBAR_EXPANDED if expanded else Sizes.SIDEBAR_COLLAPSED

        return f"""
            QWidget#sidebar {{
                background: {Colors.BG_SIDEBAR};
                border-right: 1px solid {Colors.BORDER_PRIMARY};
                min-width: {width}px;
                max-width: {width}px;
            }}

            QPushButton#sidebarButton {{
                background: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-left: 3px solid transparent;
                text-align: left;
                padding: {Sizes.PADDING_MEDIUM}px;
                font-size: {Sizes.FONT_BODY}px;
                font-weight: {Fonts.WEIGHT_NORMAL};
            }}

            QPushButton#sidebarButton:hover {{
                background: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}

            QPushButton#sidebarButton:pressed {{
                background: {Colors.BG_ACTIVE};
            }}

            QPushButton#sidebarButtonActive {{
                background: {Colors.BG_ACTIVE};
                color: {Colors.TEXT_GOLD};
                border-left: 3px solid {Colors.CYAN};
                font-weight: {Fonts.WEIGHT_SEMIBOLD};
            }}

            QPushButton#toggleButton {{
                background: transparent;
                color: {Colors.TEXT_CYAN};
                border: none;
                padding: {Sizes.PADDING_SMALL}px;
                font-size: {Sizes.FONT_HEADING_3}px;
            }}

            QPushButton#toggleButton:hover {{
                background: {Colors.BG_HOVER};
                color: {Colors.CYAN};
            }}
        """

    @staticmethod
    def get_content_area():
        """Content area stylesheet"""
        return f"""
            QWidget#contentArea {{
                background: {Colors.BG_PRIMARY};
                padding: {Sizes.PADDING_LARGE}px;
            }}

            QWidget#contentCard {{
                background: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_PRIMARY};
                border-radius: {Sizes.RADIUS_MEDIUM}px;
                padding: {Sizes.PADDING_MEDIUM}px;
            }}

            QLabel#contentTitle {{
                color: {Colors.TEXT_GOLD};
                font-size: {Sizes.FONT_HEADING_1}px;
                font-weight: {Fonts.WEIGHT_BOLD};
                padding-bottom: {Sizes.PADDING_MEDIUM}px;
            }}

            QLabel#contentSubtitle {{
                color: {Colors.TEXT_CYAN};
                font-size: {Sizes.FONT_HEADING_3}px;
                font-weight: {Fonts.WEIGHT_SEMIBOLD};
                padding-bottom: {Sizes.PADDING_SMALL}px;
            }}
        """

    @staticmethod
    def get_buttons():
        """Button stylesheets"""
        return f"""
            /* Primary Button (Cyan) */
            QPushButton#primaryButton {{
                background: {Colors.BTN_PRIMARY_BG};
                color: {Colors.BG_PRIMARY};
                border: none;
                border-radius: {Sizes.RADIUS_MEDIUM}px;
                padding: {Sizes.PADDING_SMALL}px {Sizes.PADDING_MEDIUM}px;
                font-size: {Sizes.FONT_BUTTON}px;
                font-weight: {Fonts.WEIGHT_BOLD};
                text-transform: uppercase;
            }}

            QPushButton#primaryButton:hover {{
                background: {Colors.BTN_PRIMARY_HOVER};
            }}

            QPushButton#primaryButton:pressed {{
                background: {Colors.BTN_PRIMARY_HOVER};
                padding-top: {Sizes.PADDING_SMALL + 2}px;
            }}

            QPushButton#primaryButton:disabled {{
                background: {Colors.TEXT_MUTED};
                color: {Colors.BG_SIDEBAR};
            }}

            /* Secondary Button (Magenta) */
            QPushButton#secondaryButton {{
                background: {Colors.BTN_SECONDARY_BG};
                color: {Colors.TEXT_PRIMARY};
                border: none;
                border-radius: {Sizes.RADIUS_MEDIUM}px;
                padding: {Sizes.PADDING_SMALL}px {Sizes.PADDING_MEDIUM}px;
                font-size: {Sizes.FONT_BUTTON}px;
                font-weight: {Fonts.WEIGHT_BOLD};
                text-transform: uppercase;
            }}

            QPushButton#secondaryButton:hover {{
                background: {Colors.BTN_SECONDARY_HOVER};
            }}

            QPushButton#secondaryButton:pressed {{
                background: {Colors.BTN_SECONDARY_HOVER};
                padding-top: {Sizes.PADDING_SMALL + 2}px;
            }}

            /* Success Button (Gold) */
            QPushButton#successButton {{
                background: {Colors.BTN_SUCCESS_BG};
                color: {Colors.BG_PRIMARY};
                border: none;
                border-radius: {Sizes.RADIUS_MEDIUM}px;
                padding: {Sizes.PADDING_SMALL}px {Sizes.PADDING_MEDIUM}px;
                font-size: {Sizes.FONT_BUTTON}px;
                font-weight: {Fonts.WEIGHT_BOLD};
                text-transform: uppercase;
            }}

            QPushButton#successButton:hover {{
                background: #ffcc00;
            }}

            /* Danger Button (Red) */
            QPushButton#dangerButton {{
                background: {Colors.BTN_DANGER_BG};
                color: {Colors.TEXT_PRIMARY};
                border: none;
                border-radius: {Sizes.RADIUS_MEDIUM}px;
                padding: {Sizes.PADDING_SMALL}px {Sizes.PADDING_MEDIUM}px;
                font-size: {Sizes.FONT_BUTTON}px;
                font-weight: {Fonts.WEIGHT_BOLD};
                text-transform: uppercase;
            }}

            QPushButton#dangerButton:hover {{
                background: #ff2050;
            }}

            /* Icon Button */
            QPushButton#iconButton {{
                background: transparent;
                border: 1px solid {Colors.BORDER_PRIMARY};
                border-radius: {Sizes.RADIUS_SMALL}px;
                padding: {Sizes.PADDING_SMALL}px;
                color: {Colors.TEXT_CYAN};
            }}

            QPushButton#iconButton:hover {{
                background: {Colors.BG_HOVER};
                border-color: {Colors.CYAN};
            }}
        """

    @staticmethod
    def get_input_fields():
        """Input field stylesheets"""
        return f"""
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_PRIMARY};
                border-radius: {Sizes.RADIUS_SMALL}px;
                padding: {Sizes.PADDING_SMALL}px;
                font-size: {Sizes.FONT_BODY}px;
                selection-background-color: {Colors.CYAN};
                selection-color: {Colors.BG_PRIMARY};
            }}

            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                border: 2px solid {Colors.CYAN};
                padding: {Sizes.PADDING_SMALL - 1}px;
            }}

            QLineEdit:disabled, QTextEdit:disabled {{
                background: {Colors.BG_SIDEBAR};
                color: {Colors.TEXT_MUTED};
                border-color: {Colors.TEXT_MUTED};
            }}

            QComboBox {{
                background: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_PRIMARY};
                border-radius: {Sizes.RADIUS_SMALL}px;
                padding: {Sizes.PADDING_SMALL}px;
                font-size: {Sizes.FONT_BODY}px;
            }}

            QComboBox:hover {{
                border-color: {Colors.CYAN};
            }}

            QComboBox::drop-down {{
                border: none;
                padding-right: {Sizes.PADDING_SMALL}px;
            }}

            QComboBox QAbstractItemView {{
                background: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_ACTIVE};
                selection-background-color: {Colors.BG_ACTIVE};
                selection-color: {Colors.TEXT_GOLD};
            }}
        """

    @staticmethod
    def get_progress_bar():
        """Progress bar stylesheet"""
        return f"""
            QProgressBar {{
                background: {Colors.BG_ELEVATED};
                border: 1px solid {Colors.BORDER_PRIMARY};
                border-radius: {Sizes.RADIUS_SMALL}px;
                text-align: center;
                color: {Colors.TEXT_PRIMARY};
                font-weight: {Fonts.WEIGHT_SEMIBOLD};
            }}

            QProgressBar::chunk {{
                background: {Colors.GRADIENT_CYAN};
                border-radius: {Sizes.RADIUS_SMALL}px;
            }}
        """

    @staticmethod
    def get_scrollbar():
        """Scrollbar stylesheet"""
        return f"""
            QScrollBar:vertical {{
                background: {Colors.BG_SIDEBAR};
                width: 12px;
                border-radius: 6px;
            }}

            QScrollBar::handle:vertical {{
                background: {Colors.BORDER_ACTIVE};
                border-radius: 6px;
                min-height: 20px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: {Colors.CYAN};
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            QScrollBar:horizontal {{
                background: {Colors.BG_SIDEBAR};
                height: 12px;
                border-radius: 6px;
            }}

            QScrollBar::handle:horizontal {{
                background: {Colors.BORDER_ACTIVE};
                border-radius: 6px;
                min-width: 20px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background: {Colors.CYAN};
            }}

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """

    @staticmethod
    def get_log_output():
        """Log output text area stylesheet"""
        return f"""
            QPlainTextEdit#logOutput {{
                background: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_PRIMARY};
                border-radius: {Sizes.RADIUS_SMALL}px;
                padding: {Sizes.PADDING_SMALL}px;
                font-family: {Fonts.FAMILY_MONO};
                font-size: {Sizes.FONT_SMALL}px;
            }}
        """

    @staticmethod
    def get_complete_stylesheet():
        """Get complete combined stylesheet"""
        return f"""
            {StyleSheet.get_main_window()}
            {StyleSheet.get_top_bar()}
            {StyleSheet.get_sidebar()}
            {StyleSheet.get_content_area()}
            {StyleSheet.get_buttons()}
            {StyleSheet.get_input_fields()}
            {StyleSheet.get_progress_bar()}
            {StyleSheet.get_scrollbar()}
            {StyleSheet.get_log_output()}

            /* Additional Global Styles */
            QToolTip {{
                background: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.CYAN};
                padding: {Sizes.PADDING_SMALL}px;
                font-size: {Sizes.FONT_SMALL}px;
            }}

            QMessageBox {{
                background: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}

            QMessageBox QPushButton {{
                background: {Colors.CYAN};
                color: {Colors.BG_PRIMARY};
                border: none;
                border-radius: {Sizes.RADIUS_SMALL}px;
                padding: {Sizes.PADDING_SMALL}px {Sizes.PADDING_MEDIUM}px;
                font-weight: {Fonts.WEIGHT_BOLD};
                min-width: 80px;
            }}

            QDialog {{
                background: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
            }}
        """
