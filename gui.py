"""
gui.py
Main GUI for the Video Tool Suite with navigation between modules.
"""
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QStackedWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from modules.link_grabber.gui import LinkGrabberPage
from modules.video_downloader.gui import VideoDownloaderPage
from modules.video_editor.integrated_editor import IntegratedVideoEditor
from modules.metadata_remover.gui import MetadataRemoverPage
from modules.auto_uploader.gui import AutoUploaderPage
from modules.api_manager.gui import APIConfigPage

class MainMenuPage(QWidget):
    """Main menu with buttons for each module"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Powerd by Toseeq Ur Rehman | Contact: 0307-7361139")
        title.setFont(QFont("Arial", 28, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1ABC9C; padding: 20px;")
        layout.addWidget(title)

        subtitle = QLabel("Professional Video Management & Automation")
        subtitle.setFont(QFont("Arial", 16))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #F5F6F5; padding-bottom: 15px;")
        layout.addWidget(subtitle)

        self.modules = [
            ("🔗", "Link Grabber", "Extract video links from platforms"),
            ("⬇️", "Video Downloader", "Download videos from any platform"),
            ("✂️", "Video Editor", "Edit and trim videos"),
            ("🔒", "Metadata Remover", "Remove metadata from videos"),
            ("☁️", "Auto Uploader", "Automate video uploads"),
            ("🔑", "API Config", "Configure API keys")
        ]

        self.buttons = []
        button_style = """
            QPushButton {
                background-color: #1ABC9C;
                color: #F5F6F5;
                border: none;
                padding: 15px 30px;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
            QPushButton:pressed {
                background-color: #128C7E;
            }
        """
        for icon, title, desc in self.modules:
            btn = QPushButton(f"{icon} {title}")
            btn.setStyleSheet(button_style)
            btn.setProperty("module_title", title)
            self.buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        footer = QLabel("Powered Toseeq Ur Rehman | Contact: 0307-7361139 |   Version 1.0.0 | ")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #F5F6F5; font-size: 12px; padding: 15px;")
        layout.addWidget(footer)

        self.setLayout(layout)

class VideoToolSuiteGUI(QMainWindow):
    """Main application window with page navigation"""
    def __init__(self, license_manager, config):
        super().__init__()
        self.license_manager = license_manager
        self.config = config
        self.links = []  # Shared list for grabbed links
        self.init_ui()
        self.apply_dark_theme()
        self.update_license_status()

    def init_ui(self):
        self.setWindowTitle("ContentFlow Pro - Video Automation Suite")
        self.setGeometry(100, 100, 950, 750)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.main_menu = MainMenuPage()
        self.link_grabber = LinkGrabberPage(go_back_callback=self.go_to_main_menu, shared_links=self.links)
        self.video_downloader = VideoDownloaderPage(back_callback=self.go_to_main_menu, links=self.links)
        self.video_editor = IntegratedVideoEditor(self.go_to_main_menu)
        self.metadata_remover = MetadataRemoverPage(self.go_to_main_menu)
        self.auto_uploader = AutoUploaderPage(self.go_to_main_menu)
        self.api_config = APIConfigPage(self.go_to_main_menu)

        self.stacked_widget.addWidget(self.main_menu)
        self.stacked_widget.addWidget(self.link_grabber)
        self.stacked_widget.addWidget(self.video_downloader)
        self.stacked_widget.addWidget(self.video_editor)
        self.stacked_widget.addWidget(self.metadata_remover)
        self.stacked_widget.addWidget(self.auto_uploader)
        self.stacked_widget.addWidget(self.api_config)

        for btn in self.main_menu.buttons:
            btn.clicked.connect(self.navigate_to_module)

        # Add status bar
        self.status_bar = self.statusBar()
        self.license_status_label = QLabel()
        self.status_bar.addPermanentWidget(self.license_status_label)
        self.license_status_label.setStyleSheet("padding: 5px 10px; font-weight: bold;")
        self.license_status_label.setCursor(Qt.PointingHandCursor)
        self.license_status_label.mousePressEvent = lambda event: self.show_license_info()

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #23272A;
                color: #F5F6F5;
            }
            QLabel {
                color: #F5F6F5;
            }
        """)

    def navigate_to_module(self):
        sender = self.sender()
        module_title = sender.property("module_title")
        module_map = {
            "Link Grabber": 1,
            "Video Downloader": 2,
            "Video Editor": 3,
            "Metadata Remover": 4,
            "Auto Uploader": 5,
            "API Config": 6
        }
        self.stacked_widget.setCurrentIndex(module_map.get(module_title, 0))

    def go_to_main_menu(self):
        self.video_downloader.update_links(self.links)  # Update downloader links before switching
        self.stacked_widget.setCurrentIndex(0)

    def update_license_status(self):
        """Update license status in status bar"""
        status_text = self.license_manager.get_license_status_text()
        self.license_status_label.setText(status_text)

        # Color based on status
        if "✅" in status_text:
            self.license_status_label.setStyleSheet("padding: 5px 10px; font-weight: bold; color: #1ABC9C;")
        else:
            self.license_status_label.setStyleSheet("padding: 5px 10px; font-weight: bold; color: #E74C3C;")

    def show_license_info(self):
        """Show license information dialog"""
        from modules.ui import LicenseInfoDialog
        dialog = LicenseInfoDialog(self.license_manager, self)
        dialog.exec_()
        # Update status after dialog closes
        self.update_license_status()