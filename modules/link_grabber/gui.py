"""
modules/link_grabber/gui.py
GUI for the link grabber using PyQt5.
- User-friendly interface with simplified layout and larger fonts.
- Improved color scheme with soft dark theme and vibrant accents.
- Shares grabbed links with VideoDownloaderPage.
- Matches specified output format for status log.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QTextEdit, QSpinBox, QMessageBox, QListWidget, QMenu, QAction, QCheckBox,
    QGroupBox, QFileDialog
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread
from pathlib import Path
import json
import pyperclip
import shutil
from datetime import datetime
from modules.shared.auth_network_hub import AuthNetworkHub
from .core import (
    LinkGrabberThread,
    BulkLinkGrabberThread,
    _extract_creator_from_url,
    _detect_platform_key,
    _safe_filename,
    _create_creator_folder,
    _save_links_to_file
)
from .cookie_validator import EnhancedCookieValidator, validate_cookie_file

class _AutoDetectWorker(QThread):
    """QThread for auto-detecting cookies (thread-safe GUI updates via signals)."""
    log_msg   = pyqtSignal(str)    # log line to append
    status_ok  = pyqtSignal(str)   # green status text
    status_err = pyqtSignal(str)   # red status text
    finished_signal = pyqtSignal() # re-enable button

    def __init__(self, cookies_dir: Path):
        super().__init__()
        self.cookies_dir = cookies_dir

    def run(self):
        from modules.shared.browser_extractor import extract_all_platforms_to_master
        try:
            save_path = self.cookies_dir / "chrome_cookies.txt"
            success = extract_all_platforms_to_master(
                save_path=save_path,
                cb=lambda msg: self.log_msg.emit(msg),
            )
            if success:
                self.status_ok.emit(f"Cookies saved → chrome_cookies.txt")
                self.log_msg.emit(f"Auto-detect complete: cookies → {save_path.name}")
            else:
                self.status_err.emit("No cookies found – open Chrome and log in first")
                self.log_msg.emit("Auto-detect: no cookies found in any browser")
        except Exception as e:
            self.log_msg.emit(f"Auto-detect error: {e}")
            self.status_err.emit("Auto-detect failed – see log")
        finally:
            self.finished_signal.emit()


class _BrowserLoginWorker(QThread):
    """Runs ChromiumAuthManager.open_login_browser() off the GUI thread."""

    status_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool, dict)  # also emits per-platform status

    def __init__(self, auth_manager):
        super().__init__()
        self.auth_manager = auth_manager

    def run(self):
        success = False
        platform_status = {}
        try:
            if self.auth_manager:
                success = bool(
                    self.auth_manager.open_login_browser(
                        callback=lambda platform, status: self.status_signal.emit(
                            str(platform), str(status)
                        ),
                        open_even_if_logged_in=True,
                    )
                )
                # Use the status captured from the live context inside
                # open_login_browser — no separate headless launch needed.
                platform_status = getattr(
                    self.auth_manager, "_last_login_status", {}
                )
        except Exception as e:
            self.status_signal.emit("system", f"error: {str(e)[:120]}")
            success = False
        finally:
            self.finished_signal.emit(success, platform_status)



class LinkGrabberPage(QWidget):
    @staticmethod
    def _repair_log_text(msg: str) -> str:
        """Best-effort fix for mojibake text from legacy log strings."""
        text = str(msg or "")
        try:
            if "ðŸ" in text or "â" in text:
                repaired = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
                if repaired:
                    text = repaired
        except Exception:
            pass
        return text.replace("\ufeff", "").strip("\r")

    def __init__(self, go_back_callback=None, shared_links=None, download_callback=None):
        super().__init__()
        self.thread = None
        self.browser_login_worker = None
        self.go_back_callback = go_back_callback
        self.download_callback = download_callback
        self.links = shared_links if shared_links is not None else []  # Use shared links
        self.creator = "unknown"
        self.creator_results = {}
        self.auth_hub = AuthNetworkHub()

        # Root cookies folder - use persistent path (works in dev and EXE mode)
        self.cookies_dir = self.auth_hub.cookies_dir

        # Proxy settings file
        self.config_dir = self.auth_hub.config_dir
        self.proxy_config_file = self.auth_hub.proxy_config_file

        # Store validated proxies
        self.validated_proxies = []

        # Chromium auth manager (optional dependency)
        self.auth_manager = None
        try:
            from .browser_auth import ChromiumAuthManager
            self.auth_manager = ChromiumAuthManager()
        except ImportError:
            self.auth_manager = None

        self.init_ui()

        # Load saved proxies after UI is initialized
        self.load_proxy_settings()

        self._refresh_auth_status_indicators()

    def closeEvent(self, event):
        """Properly cleanup thread on close to prevent crash"""
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.thread.wait(2000)  # Wait max 2 seconds
            self.thread.quit()
        if self.browser_login_worker and self.browser_login_worker.isRunning():
            self.browser_login_worker.quit()
            self.browser_login_worker.wait(2000)
        event.accept()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        self.setStyleSheet("""
            QWidget {
                background-color: #23272A;
                color: #F5F6F5;
                font-family: Arial, sans-serif;
            }
        """)

        self.title = QLabel("Fast Link Grabber")
        self.title.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #1ABC9C;
            margin-bottom: 15px;
        """)
        layout.addWidget(self.title)

        auth_row = QHBoxLayout()
        auth_label = QLabel("Platform Login Status:")
        auth_label.setStyleSheet("color: #F5F6F5; font-size: 13px; font-weight: bold;")
        self.platform_status_label = QLabel("Checking...")
        self.platform_status_label.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        self.relogin_btn = QPushButton("Re-login to Platforms")
        self.relogin_btn.setStyleSheet("""
            QPushButton {
                background-color: #E67E22;
                color: #F5F6F5;
                border: none;
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #D35400; }
            QPushButton:disabled { background-color: #555; color: #AAA; }
        """)
        self.relogin_btn.setEnabled(bool(self.auth_manager))
        self.relogin_btn.clicked.connect(self._run_browser_login)

        auth_row.addWidget(auth_label)
        auth_row.addWidget(self.platform_status_label, 1)
        auth_row.addWidget(self.relogin_btn)
        layout.addLayout(auth_row)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter URL(s) for YouTube, TikTok, Instagram, etc. (comma-separated)")
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                padding: 10px;
                border-radius: 8px;
                font-size: 16px;
            }
            QLineEdit:focus {
                border: 2px solid #1ABC9C;
            }
        """)
        self.url_input.setMinimumHeight(40)
        layout.addWidget(self.url_input)

        # ===== COOKIE SECTION =====
        cookie_group = QGroupBox("Cookies (Optional - For Private Content)")
        cookie_group.setCheckable(True)
        cookie_group.setChecked(True)  # EXPANDED BY DEFAULT so user can see it!
        cookie_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #4B5057;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        cookie_layout = QVBoxLayout()

        # ── Auto-detect row (Workflow 1 trigger) ──
        auto_row = QHBoxLayout()
        self.auto_detect_btn = QPushButton("Auto-Detect Cookies from Browser")
        self.auto_detect_btn.setToolTip(
            "Detects running Chrome/Edge, copies cookies automatically.\n"
            "If no browser is open, opens the default browser briefly."
        )
        self.auto_detect_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980B9;
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2471A3; }
            QPushButton:disabled { background-color: #555; }
        """)
        auto_row.addWidget(self.auto_detect_btn)
        auto_row.addStretch()
        cookie_layout.addLayout(auto_row)

        # ── Manual paste area ──
        self.cookie_text = QTextEdit()
        self.cookie_text.setPlaceholderText(
            "Or paste cookies manually here (Netscape format)...\n"
            "TIP: Use 'Get cookies.txt' Chrome extension to export\n"
            "Example: .instagram.com\tTRUE\t/\tTRUE\t1234567890\tsessionid\tABC123"
        )
        self.cookie_text.setMaximumHeight(75)
        self.cookie_text.setStyleSheet("""
            QTextEdit {
                background-color: #2C2F33;
                border: 1px solid #4B5057;
                border-radius: 5px;
                padding: 5px;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        cookie_layout.addWidget(self.cookie_text)

        # ── Manual cookie buttons ──
        cookie_btn_row = QHBoxLayout()
        self.upload_cookie_btn = QPushButton("Upload Cookie File")
        self.save_cookie_btn   = QPushButton("Save")
        self.clear_cookie_btn  = QPushButton("Clear")

        btn_style = """
            QPushButton {
                background-color: #1ABC9C;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #16A085; }
        """
        for btn in [self.upload_cookie_btn, self.save_cookie_btn, self.clear_cookie_btn]:
            btn.setStyleSheet(btn_style)

        cookie_btn_row.addWidget(self.upload_cookie_btn)
        cookie_btn_row.addWidget(self.save_cookie_btn)
        cookie_btn_row.addWidget(self.clear_cookie_btn)
        cookie_btn_row.addStretch()
        cookie_layout.addLayout(cookie_btn_row)

        # ── Cookie status label ──
        self.cookie_status = QLabel("Auto-detection will run before each extraction")
        self.cookie_status.setStyleSheet("color: #888; font-size: 11px;")
        cookie_layout.addWidget(self.cookie_status)

        # ── Per-platform cookie validity indicators ──
        self.cookie_validity_label = QLabel("")
        self.cookie_validity_label.setStyleSheet("color: #888; font-size: 11px;")
        cookie_layout.addWidget(self.cookie_validity_label)
        self._refresh_cookie_validity()

        cookie_group.setLayout(cookie_layout)
        layout.addWidget(cookie_group)

        # Connect cookie signals
        self.auto_detect_btn.clicked.connect(self.run_auto_detect_cookies)
        self.upload_cookie_btn.clicked.connect(self.upload_cookie_file)
        self.save_cookie_btn.clicked.connect(self.save_cookies)
        self.clear_cookie_btn.clicked.connect(self.clear_cookies)

        # ===== PROXY SECTION (2026 Upgrade) =====
        proxy_group = QGroupBox("Proxy Settings (Optional - Max 2 Proxies)")
        proxy_group.setCheckable(True)
        proxy_group.setChecked(False)  # Collapsed by default
        proxy_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #4B5057;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        proxy_layout = QVBoxLayout()

        # Proxy 1 Input
        proxy1_row = QHBoxLayout()
        proxy1_label = QLabel("Proxy 1:")
        proxy1_label.setStyleSheet("color: #F5F6F5; font-size: 13px;")
        self.proxy1_input = QLineEdit()
        self.proxy1_input.setPlaceholderText("e.g., 123.45.67.89:8080 or user:pass@ip:port")
        self.proxy1_input.setStyleSheet("""
            QLineEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                padding: 5px;
                border-radius: 5px;
                font-size: 12px;
            }
            QLineEdit:focus { border: 2px solid #1ABC9C; }
        """)
        self.validate_proxy1_btn = QPushButton("Validate")
        self.validate_proxy1_btn.setStyleSheet("""
            QPushButton {
                background-color: #1ABC9C;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #16A085; }
        """)
        self.proxy1_status = QLabel("Not validated")
        self.proxy1_status.setStyleSheet("color: #888; font-size: 11px;")

        proxy1_row.addWidget(proxy1_label)
        proxy1_row.addWidget(self.proxy1_input, 3)
        proxy1_row.addWidget(self.validate_proxy1_btn)
        proxy1_row.addWidget(self.proxy1_status, 1)
        proxy_layout.addLayout(proxy1_row)

        # Proxy 2 Input
        proxy2_row = QHBoxLayout()
        proxy2_label = QLabel("Proxy 2:")
        proxy2_label.setStyleSheet("color: #F5F6F5; font-size: 13px;")
        self.proxy2_input = QLineEdit()
        self.proxy2_input.setPlaceholderText("e.g., 98.76.54.32:3128 (optional)")
        self.proxy2_input.setStyleSheet("""
            QLineEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                padding: 5px;
                border-radius: 5px;
                font-size: 12px;
            }
            QLineEdit:focus { border: 2px solid #1ABC9C; }
        """)
        self.validate_proxy2_btn = QPushButton("Validate")
        self.validate_proxy2_btn.setStyleSheet("""
            QPushButton {
                background-color: #1ABC9C;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #16A085; }
        """)
        self.proxy2_status = QLabel("Not validated")
        self.proxy2_status.setStyleSheet("color: #888; font-size: 11px;")

        proxy2_row.addWidget(proxy2_label)
        proxy2_row.addWidget(self.proxy2_input, 3)
        proxy2_row.addWidget(self.validate_proxy2_btn)
        proxy2_row.addWidget(self.proxy2_status, 1)
        proxy_layout.addLayout(proxy2_row)

        # Proxy info/tip
        proxy_tip = QLabel("Proxies help bypass IP blocks and rate limits. Leave empty to use direct connection.")
        proxy_tip.setStyleSheet("color: #888; font-size: 11px; font-style: italic;")
        proxy_layout.addWidget(proxy_tip)

        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)

        # Connect proxy validation signals
        self.validate_proxy1_btn.clicked.connect(lambda: self.validate_proxy(1))
        self.validate_proxy2_btn.clicked.connect(lambda: self.validate_proxy(2))

        options_row = QHBoxLayout()
        options_row.setSpacing(10)

        self.all_videos_check = QCheckBox("Fetch All Videos")
        self.all_videos_check.setChecked(True)
        self.all_videos_check.setStyleSheet("""
            QCheckBox {
                color: #F5F6F5;
                font-size: 16px;
                font-weight: bold;
                background-color: #2C2F33;
                padding: 8px;
                border-radius: 5px;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
                background-color: #2C2F33;
                border: 2px solid #4B5057;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #1ABC9C;
                border: 2px solid #1ABC9C;
            }
        """)
        self.all_videos_check.stateChanged.connect(self.toggle_limit_spin)
        options_row.addWidget(self.all_videos_check)

        self.limit_label = QLabel("Limit:")
        self.limit_label.setStyleSheet("color: #F5F6F5; font-size: 16px;")
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 500)
        self.limit_spin.setValue(0)
        self.limit_spin.setEnabled(False)
        self.limit_spin.setStyleSheet("""
            QSpinBox {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                padding: 8px;
                border-radius: 5px;
                font-size: 16px;
            }
        """)
        options_row.addWidget(self.limit_label)
        options_row.addWidget(self.limit_spin)
        options_row.addStretch()
        layout.addLayout(options_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.start_btn = QPushButton("Start")
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Save")
        self.copy_btn = QPushButton("Copy All")
        self.clear_btn = QPushButton("Clear")
        self.download_btn = QPushButton("Download Links")  # New button to switch to downloader
        self.help_btn = QPushButton("Help")  # New help button

        button_style = """
            QPushButton {
                background-color: #1ABC9C;
                color: #F5F6F5;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
            QPushButton:pressed {
                background-color: #128C7E;
            }
            QPushButton:disabled {
                background-color: #4B5057;
                color: #888;
            }
        """
        self.start_btn.setStyleSheet(button_style)
        self.cancel_btn.setStyleSheet(button_style)
        self.save_btn.setStyleSheet(button_style)
        self.copy_btn.setStyleSheet(button_style)
        self.clear_btn.setStyleSheet(button_style)
        self.download_btn.setStyleSheet(button_style)
        self.help_btn.setStyleSheet(button_style)

        self.save_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.download_btn.setEnabled(False)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.copy_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.help_btn)
        btn_row.addWidget(self.download_btn)
        layout.addLayout(btn_row)

        self.link_list = QListWidget()
        self.link_list.setSelectionMode(QListWidget.MultiSelection)
        self.link_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.link_list.customContextMenuRequested.connect(self.show_context_menu)
        self.link_list.setStyleSheet("""
            QListWidget {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }
            QListWidget::item:selected {
                background-color: #1ABC9C;
                color: #F5F6F5;
            }
        """)
        layout.addWidget(self.link_list)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2C2F33;
                border: 2px solid #4B5057;
                border-radius: 8px;
                text-align: center;
                color: #F5F6F5;
                font-size: 14px;
            }
            QProgressBar::chunk {
                background-color: #1ABC9C;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # ===== LOGS SECTION WITH TOGGLE =====
        logs_header_row = QHBoxLayout()
        logs_header_label = QLabel("Activity Logs")
        logs_header_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #1ABC9C;
        """)

        maximize_btn = QPushButton("Maximize Output")
        maximize_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: #F5F6F5;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2980B9; }
            QPushButton:pressed { background-color: #1F618D; }
        """)
        maximize_btn.clicked.connect(self.show_maximized_output)

        logs_header_row.addWidget(logs_header_label)
        logs_header_row.addStretch()
        logs_header_row.addWidget(maximize_btn)
        layout.addLayout(logs_header_row)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(200)  # Default expanded height
        self.log_area.setMaximumHeight(400)  # Can expand up to this
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.log_area)

        self.setLayout(layout)

        self.start_btn.clicked.connect(self.start_grabbing)
        self.cancel_btn.clicked.connect(self.cancel_grab)
        self.save_btn.clicked.connect(self.save_to_folder)
        self.copy_btn.clicked.connect(self.copy_all_links)
        self.clear_btn.clicked.connect(self.clear_interface)
        self.download_btn.clicked.connect(self.start_download_page)
        self.help_btn.clicked.connect(self.show_help)

        # Populate link list if shared links exist
        for link in self.links:
            self.link_list.addItem(link['url'])
            self.save_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)
            self.download_btn.setEnabled(True)

    def start_download_page(self):
        aggregated = self._collect_all_links()
        if not aggregated:
            QMessageBox.warning(self, "No Links", "Please grab links before sending them to the downloader.")
            return

        cleaned = self._update_shared_links(aggregated)
        if not cleaned:
            QMessageBox.warning(self, "Error", "Unable to prepare links for the downloader.")
            return

        if self.download_callback:
            self.download_callback()
            self.log_area.append(f" Sent {len(cleaned)} link(s) to Video Downloader (Single Mode).")
        else:
            QMessageBox.information(
                self,
                "Links Ready",
                f"Prepared {len(cleaned)} link(s). Switch to the Video Downloader module to continue."
            )
            self.log_area.append(" Links ready for downloader - open the Video Downloader module to continue.")

    def load_proxy_settings(self):
        """Load saved proxy settings from config file"""
        try:
            settings = self.auth_hub.load_proxy_settings()

            # Load proxies into input fields
            proxy1 = settings.get('proxy1', '')
            proxy2 = settings.get('proxy2', '')

            if proxy1:
                self.proxy1_input.setText(proxy1)
                # Mark as previously validated (will re-validate on use)
                self.proxy1_status.setText("Saved")
                self.proxy1_status.setStyleSheet("color: #FFA500; font-size: 11px;")
                self.validated_proxies.append(proxy1)

            if proxy2:
                self.proxy2_input.setText(proxy2)
                self.proxy2_status.setText("Saved")
                self.proxy2_status.setStyleSheet("color: #FFA500; font-size: 11px;")
                self.validated_proxies.append(proxy2)

            if proxy1 or proxy2:
                self.log_area.append(f" Loaded {len([p for p in [proxy1, proxy2] if p])} saved proxy(ies)")

        except Exception as e:
            # Silently fail if can't load (first time use)
            pass

    def save_proxy_settings(self):
        """Save current proxies to config file"""
        try:
            # Get current proxies from input fields
            proxy1 = self.proxy1_input.text().strip()
            proxy2 = self.proxy2_input.text().strip()

            if self.auth_hub.save_proxy_settings(proxy1, proxy2):
                self.log_area.append(" Proxy settings saved")
            else:
                self.log_area.append(" Failed to save proxy settings")

        except Exception as e:
            self.log_area.append(f" Failed to save proxy settings: {str(e)[:50]}")

    def show_maximized_output(self):
        """Show activity logs in maximized window with copy and close buttons"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, QApplication
        from PyQt5.QtCore import Qt

        # Create maximized dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(" Link Grabber Activity Logs - Full Output")
        dialog.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)

        # Set dialog size to 90% of screen
        screen = QApplication.desktop().screenGeometry()
        dialog.resize(int(screen.width() * 0.9), int(screen.height() * 0.9))

        # Center dialog on screen
        dialog.move((screen.width() - dialog.width()) // 2,
                    (screen.height() - dialog.height()) // 2)

        # Dark theme
        dialog.setStyleSheet("""
            QDialog {
                background-color: #23272A;
                color: #F5F6F5;
            }
        """)

        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Title
        title = QLabel("Link Grabber Activity Logs")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1ABC9C; margin-bottom: 10px;")
        layout.addWidget(title)

        # Full output text
        output_text = QTextEdit()
        output_text.setReadOnly(True)
        output_text.setPlainText(self.log_area.toPlainText())  # Copy current log
        output_text.setStyleSheet("""
            QTextEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
        """)
        layout.addWidget(output_text)

        # Button bar
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Copy All button
        copy_btn = QPushButton("Copy All")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: #F5F6F5;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2980B9; }
            QPushButton:pressed { background-color: #1F618D; }
        """)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(output_text.toPlainText()))
        button_layout.addWidget(copy_btn)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: #F5F6F5;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #C0392B; }
            QPushButton:pressed { background-color: #A93226; }
        """)
        close_btn.clicked.connect(dialog.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        dialog.setLayout(layout)
        dialog.exec_()

    def validate_proxy(self, proxy_num):
        """Validate proxy and update status"""
        from .core import _validate_proxy

        # Get proxy input
        if proxy_num == 1:
            proxy = self.proxy1_input.text().strip()
            status_label = self.proxy1_status
        else:
            proxy = self.proxy2_input.text().strip()
            status_label = self.proxy2_status

        if not proxy:
            status_label.setText("Not validated")
            status_label.setStyleSheet("color: #888; font-size: 11px;")
            return

        # Show validating message
        status_label.setText("Validating...")
        status_label.setStyleSheet("color: #FFA500; font-size: 11px;")
        self.log_area.append(f" Validating Proxy {proxy_num}: {proxy}")

        # Validate proxy
        result = _validate_proxy(proxy, timeout=10)

        if result['working']:
            # Proxy is working
            status_label.setText(f" Working ({result['response_time']}s)")
            status_label.setStyleSheet("color: #1ABC9C; font-size: 11px;")
            self.log_area.append(f" Proxy {proxy_num} validated: {result['ip']} ({result['response_time']}s)")

            # Add to validated list
            if proxy not in self.validated_proxies:
                self.validated_proxies.append(proxy)

            # Auto-save validated proxies
            self.save_proxy_settings()

        else:
            # Proxy failed - Show detailed error
            error_msg = result.get('error', 'Unknown error')

            # Truncate error for status label (max 30 chars)
            short_error = error_msg[:30] + "..." if len(error_msg) > 30 else error_msg
            status_label.setText(f" {short_error}")
            status_label.setStyleSheet("color: #E74C3C; font-size: 10px;")
            status_label.setToolTip(error_msg)  # Full error in tooltip

            # Show full error in log
            self.log_area.append(f" Proxy {proxy_num} validation failed")
            self.log_area.append(f"   Error: {error_msg}")

            # Remove from validated list if exists
            if proxy in self.validated_proxies:
                self.validated_proxies.remove(proxy)

    def toggle_limit_spin(self, state):
        self.limit_spin.setEnabled(state != Qt.Checked)

    def start_grabbing(self):
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "Error", "Process already running. Please wait or cancel.")
            return

        urls = [url.strip() for url in self.url_input.text().split(',') if url.strip()]
        if not urls:
            QMessageBox.warning(self, "Error", "Please enter at least one URL.")
            return

        self.link_list.clear()
        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.links.clear()
        self.creator_results = {}
        self.save_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.start_btn.setEnabled(False)

        max_videos = 0 if self.all_videos_check.isChecked() else self.limit_spin.value()

        # Cookies are handled automatically (Workflow 1) – no manual source selection
        # Collect proxies (if provided)
        proxies = []
        proxy1 = self.proxy1_input.text().strip()
        proxy2 = self.proxy2_input.text().strip()

        if proxy1 and proxy1 in self.validated_proxies:
            proxies.append(proxy1)
        if proxy2 and proxy2 in self.validated_proxies:
            proxies.append(proxy2)

        if proxies:
            self.log_area.append(f" Using {len(proxies)} validated proxy(ies)")

        options = {
            "max_videos": max_videos,
            "cookie_browser": None,       # Always auto (Workflow 1 handles detection)
            "proxies": proxies,
            "use_enhancements": True,
            "use_instaloader": False,     # Avoid 30-min 429 waits
            "interactive_login_fallback": True,
            "manual_login_wait_seconds": 120,
        }
        if len(urls) == 1:
            self.thread = LinkGrabberThread(urls[0], options)
            try:
                self.creator = _extract_creator_from_url(urls[0], _detect_platform_key(urls[0]))
            except Exception as e:
                self.log_area.append(f" Failed to extract creator: {str(e)[:100]}")
                self.creator = "unknown"
        else:
            self.thread = BulkLinkGrabberThread(urls, options)
            self.creator = "bulk"

        self.thread.progress.connect(self.on_progress_log)
        self.thread.progress_percent.connect(self.on_progress_percent)
        self.thread.link_found.connect(self.on_link_found)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

        self.log_area.append(" Started grabbing links...")

    def cancel_grab(self):
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.log_area.append(" Cancelling process...")
            self.thread = None
        self.start_btn.setEnabled(True)
        self.creator_results = {}
        self.save_btn.setEnabled(bool(self.links))
        self.copy_btn.setEnabled(bool(self.links))
        self.download_btn.setEnabled(bool(self.links))

    def save_to_folder(self):
        if not self.creator_results:
            QMessageBox.warning(self, "Error", "No creator data available to save yet.")
            return

        saved_details = []
        total_links = 0

        try:
            for creator_name, entries in self.creator_results.items():
                if not entries:
                    continue
                safe_creator = creator_name or "unknown"
                creator_folder = _create_creator_folder(safe_creator)
                filepath = _save_links_to_file(safe_creator, entries, creator_folder)
                saved_details.append((safe_creator, filepath, len(entries)))
                total_links += len(entries)

            if not saved_details:
                QMessageBox.warning(self, "Error", "No links to save.")
                return

            self.log_area.append(f" Saved {total_links} links across {len(saved_details)} creator folder(s).")

            summary_lines = [
                f" @{_safe_filename(name)}  {count} links\n  {path}"
                for name, path, count in saved_details
            ]
            QMessageBox.information(
                self,
                "Saved",
                f"Saved {total_links} links across {len(saved_details)} creator(s).\n\n" + "\n".join(summary_lines)
            )
        except Exception as e:
            self.log_area.append(f" Failed to save files: {str(e)[:100]}")
            QMessageBox.warning(self, "Error", f"Failed to save files: {str(e)[:100]}")

    def clear_interface(self):
        self.url_input.clear()
        self.link_list.clear()
        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.links.clear()
        self.creator = "unknown"
        self.save_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.thread = None

    def show_help(self):
        """Show comprehensive help dialog"""
        help_text = """

            Link Grabber - User Guide & Troubleshooting             



   PROXY SETUP GUIDE


The app supports ALL proxy formats automatically:

1 No Authentication:
   209.101.203.79:59100

2 Standard Format (user:pass@ip:port):
   username:password@209.101.203.79:59100

3 Provider Format (ip:port:user:pass):
   209.101.203.79:59100:username:password

 All formats are automatically detected and converted!

HOW TO USE:
 Enter proxy in ANY format above
 Click " Validate" to test connection
 Green  = Working, Red  = Failed
 Only validated proxies are used during extraction

WHY USE PROXIES:
 Bypass IP blocks and rate limits
 Access geo-restricted content
 Prevent detection during bulk operations
 Max 2 proxies supported


   yt-dlp INSTALLATION (Optional - App Has Built-in)


The app includes yt-dlp, but you can install your own for updates:

DETECTION PRIORITY:
1. Bundled yt-dlp.exe (in app) - Most reliable 
2. System yt-dlp (in PATH) - If you installed
3. Custom locations (C:\\yt-dlp, AppData, etc.)

RECOMMENDED INSTALL (for updates):
1. Download: https://github.com/yt-dlp/yt-dlp/releases/latest
2. Install to system PATH OR save to: C:\\yt-dlp\\yt-dlp.exe
3. Restart app

VERIFICATION:
 Open Command Prompt
 Run: yt-dlp --version
 Should show version number


   COOKIE TROUBLESHOOTING


If link grabbing fails:

 SOLUTIONS:
1. Update cookies (they expire!)
2. Use "Use Browser (Chrome)" option
3. Try different proxy
4. Check if account is private
5. Verify you're logged into the platform

COOKIE FORMATS:
 Netscape format (recommended)
 Export using "Get cookies.txt" Chrome extension
 Place in cookies/ folder or use Browser mode


   BEST PRACTICES


 Always validate proxies before use
 Update cookies regularly (weekly)
 Use "Fetch All Videos" for complete extraction
 For private accounts, ensure cookies are fresh
 Check logs for detailed error messages


   COMMON ERRORS & FIXES


ERROR: "Proxy connection failed"
FIX: Check proxy format, verify credentials, try HTTP instead of HTTPS

ERROR: "No links found"
FIX: Update cookies, check account privacy, try proxy, verify URL

ERROR: "Proxy timeout"
FIX: Proxy too slow, try different proxy or increase timeout

ERROR: "Authentication failed"
FIX: Check proxy username/password, verify format


  Need more help? Check the logs for detailed error messages!         

        """

        # Create scrollable message box
        msg = QMessageBox(self)
        msg.setWindowTitle(" Link Grabber Help & Guide")
        msg.setText("Comprehensive Guide for Link Grabber")
        msg.setDetailedText(help_text)
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)

        # Make it bigger and scrollable
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #2C2F33;
                color: #F5F6F5;
            }
            QTextEdit {
                background-color: #23272A;
                color: #F5F6F5;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                min-width: 700px;
                min-height: 500px;
            }
            QPushButton {
                background-color: #1ABC9C;
                color: white;
                padding: 8px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
        """)

        msg.exec_()

    def _show_first_time_setup(self):
        """Show first-time setup dialog for platform login."""
        if not self.auth_manager:
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("First Time Setup")
        msg.setText(
            "Welcome to Link Grabber!\n\n"
            "You need to log in to social media platforms once.\n"
            "A browser will open - please log in to:\n\n"
            "1. YouTube/Google\n"
            "2. Instagram\n"
            "3. TikTok\n"
            "4. Twitter/X\n"
            "5. Facebook\n\n"
            "After logging in to all, close the browser tabs."
        )
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

        if msg.exec_() == QMessageBox.Ok:
            self._run_browser_login()

    def _run_browser_login(self):
        """Launch Chromium browser for user platform login."""
        if not self.auth_manager:
            self.log_area.append("Chromium auth manager not available.")
            return
        if self.browser_login_worker and self.browser_login_worker.isRunning():
            self.log_area.append("Browser login is already running.")
            return

        self.log_area.append("Opening browser for login. Please log in to all platforms.")
        self.log_area.append("Close browser tabs when done.")
        self.relogin_btn.setEnabled(False)

        self.browser_login_worker = _BrowserLoginWorker(self.auth_manager)
        self.browser_login_worker.status_signal.connect(self._on_browser_login_status)
        self.browser_login_worker.finished_signal.connect(self._on_browser_login_finished)
        self.browser_login_worker.start()

    def _on_browser_login_status(self, platform: str, status: str):
        self.log_area.append(f"[Auth] {platform}: {status}")

    def _on_browser_login_finished(self, success: bool, platform_status: dict = None):
        self.log_area.append("Browser login finished." if success else "Browser login ended without new session.")

        # Display per-platform detection results with clear indicators
        if platform_status:
            detected = []
            missing = []
            for p in ["youtube", "tiktok", "instagram", "twitter", "facebook"]:
                if platform_status.get(p):
                    detected.append(p.title())
                else:
                    missing.append(p.title())
            if detected:
                self.log_area.append(
                    f" Platforms detected ({len(detected)}): {', '.join(detected)}"
                )
            if missing:
                self.log_area.append(
                    f" Not detected ({len(missing)}): {', '.join(missing)}"
                )
            if not detected:
                self.log_area.append(" No sessions detected. Try Re-login again.")

        self.relogin_btn.setEnabled(bool(self.auth_manager))
        # Use platform_status directly for immediate indicator update,
        # in case auth_state.json write is still in progress.
        self._refresh_auth_status_indicators(live_status=platform_status)
        self._refresh_cookie_validity()

    def _refresh_auth_status_indicators(self, live_status: dict = None):
        if not hasattr(self, "platform_status_label"):
            return
        if not self.auth_manager:
            self.platform_status_label.setText("Chromium auth unavailable")
            self.platform_status_label.setStyleSheet("color: #888; font-size: 12px;")
            if hasattr(self, "relogin_btn"):
                self.relogin_btn.setEnabled(False)
            return

        # Use live_status from login callback when available for immediate
        # feedback; fall back to reading persisted auth_state.json.
        if live_status:
            status = {k: bool(v) for k, v in live_status.items()}
        else:
            status = self._read_cached_platform_status()

        # Check cooldown state (lightweight file read, no Playwright)
        cooldowns = {}
        try:
            from .browser_auth import ChromiumAuthManager
            if self.auth_manager:
                cooldowns = self.auth_manager.get_all_cooldowns()
        except Exception:
            pass

        order = ["youtube", "tiktok", "instagram", "twitter", "facebook"]
        parts = []
        ok_count = 0
        for key in order:
            if key in cooldowns:
                parts.append(f"[COOL] {key.title()}")
            elif bool(status.get(key, False)):
                ok_count += 1
                parts.append(f"[OK] {key.title()}")
            else:
                parts.append(f"[WARN] {key.title()}")

        self.platform_status_label.setText("  ".join(parts))
        color = "#2ECC71" if ok_count >= 3 else "#F39C12"
        self.platform_status_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _read_cached_platform_status(self):
        """Return platform status from config/auth_state.json without launching browser."""
        status = {
            "youtube": False,
            "tiktok": False,
            "instagram": False,
            "twitter": False,
            "facebook": False,
        }
        try:
            state_file = self.auth_hub.auth_state_file
            if not state_file.exists():
                return status
            raw = json.loads(state_file.read_text(encoding="utf-8"))
            platforms = raw.get("cookies", {}).get("platforms", []) or []
            for p in platforms:
                key = str(p).strip().lower()
                if key in status:
                    status[key] = True
        except Exception:
            pass
        return status

    def _refresh_cookie_validity(self):
        """Check per-platform cookie files and display validity status."""
        try:
            from modules.video_downloader.core import _validate_cookie_file
            from modules.shared.session_authority import get_session_authority
        except ImportError:
            return

        order = ["youtube", "tiktok", "instagram", "twitter", "facebook"]
        parts = []
        authority = None
        try:
            authority = get_session_authority()
        except Exception:
            authority = None
        for platform in order:
            cookie_file = self.cookies_dir / f"{platform}.txt"
            if not cookie_file.exists():
                parts.append(f"\u274c {platform.title()}")
                continue
            result = _validate_cookie_file(str(cookie_file))
            strict_auth = False
            try:
                if authority is not None:
                    strict_auth = bool(authority._cookie_file_has_auth(cookie_file, platform))
            except Exception:
                strict_auth = False
            total_cookies = max(int(result.get("total_cookies", 0) or 0), 1)
            expired_cookies = int(result.get("expired_cookies", 0) or 0)
            expired_ratio = expired_cookies / total_cookies
            if not result.get("valid"):
                parts.append(f"\u274c {platform.title()}")
            elif strict_auth and result.get("fresh", True) and expired_ratio <= 0.5:
                parts.append(f"\u2705 {platform.title()}")
            elif not result.get("fresh", True):
                age = result.get("age_days", 0)
                parts.append(f"\u26a0 {platform.title()} ({age}d)")
            elif strict_auth:
                parts.append(f"\u26a0 {platform.title()}")
            else:
                parts.append(f"\u26a0 {platform.title()}")

        if hasattr(self, "cookie_validity_label"):
            self.cookie_validity_label.setText("Cookies: " + "  ".join(parts))

    def on_progress_log(self, msg):
        try:
            from modules.shared.progress_filter import filter_for_gui
            filtered = filter_for_gui(msg)
            if filtered is None:
                return
            msg = filtered
        except ImportError:
            pass
        self.log_area.append(self._repair_log_text(msg))
        self.log_area.ensureCursorVisible()

    def on_progress_percent(self, val):
        self.progress_bar.setValue(val)

    def on_link_found(self, link, text):
        self.link_list.addItem(text)
        self.links.append({'url': link})

    def on_finished(self, success, message, links):
        thread_ref = self.thread
        self.log_area.append(message)
        self.start_btn.setEnabled(True)

        creator_map = {}
        if success and thread_ref:
            if isinstance(thread_ref, LinkGrabberThread):
                creator_name = getattr(thread_ref, "creator_name", self.creator) or "unknown"
                creator_map[creator_name] = links or []
            elif isinstance(thread_ref, BulkLinkGrabberThread):
                for creator_name, data in thread_ref.creator_data.items():
                    creator_links = data.get('links') if isinstance(data, dict) else None
                    if creator_links:
                        creator_map[creator_name] = creator_links

        self.creator_results = creator_map

        if success and links:
            cleaned_links = self._update_shared_links(links)
        else:
            cleaned_links = self._update_shared_links([])

        can_save = success and bool(self.creator_results)
        can_copy = success and bool(cleaned_links)
        self.save_btn.setEnabled(can_save)
        self.copy_btn.setEnabled(can_copy)
        self.download_btn.setEnabled(can_copy)

        self.thread = None

        if success:
            QMessageBox.information(self, "Completed", f"{message}\n\nClick 'Save to Folder' or 'Download Links'.")

    def show_context_menu(self, position):
        if not self.link_list.selectedItems():
            return
        menu = QMenu()
        copy_action = QAction("Copy Selected Links", self)
        copy_action.triggered.connect(self.copy_selected_links)
        menu.addAction(copy_action)
        menu.exec_(self.link_list.mapToGlobal(position))

    def copy_selected_links(self):
        selected = [item.text() for item in self.link_list.selectedItems()]
        if selected:
            pyperclip.copy('\n'.join(selected))
            self.log_area.append(f" Copied {len(selected)} selected links to clipboard!")
            self.download_btn.setEnabled(True)

    def copy_all_links(self):
        if self.links:
            urls = [link['url'] for link in self.links]
            pyperclip.copy('\n'.join(urls))
            self.log_area.append(f" Copied {len(urls)} links to clipboard!")
            self.download_btn.setEnabled(True)

    def _collect_all_links(self):
        """Combine creator results into a single list of link dicts"""
        aggregated = []
        if self.creator_results:
            for data in self.creator_results.values():
                if isinstance(data, list):
                    aggregated.extend(data)

        if not aggregated and self.links:
            for entry in self.links:
                if isinstance(entry, dict):
                    url = entry.get('url', '')
                    if url:
                        aggregated.append({'url': url})
                elif isinstance(entry, str) and entry.strip():
                    aggregated.append({'url': entry.strip()})

        return aggregated

    def _update_shared_links(self, entries):
        """Update shared link list (keeps same list object for other modules)"""
        if self.links is None:
            self.links = []
        else:
            self.links.clear()

        cleaned = []
        seen = set()

        for entry in entries or []:
            if isinstance(entry, dict):
                url = entry.get('url', '')
            elif isinstance(entry, str):
                url = entry
            else:
                url = str(entry)

            url = (url or '').strip()
            if not url or url in seen:
                continue

            seen.add(url)
            clean_entry = {'url': url}
            # Preserve _meta from extraction for downstream consumers
            if isinstance(entry, dict) and '_meta' in entry:
                clean_entry['_meta'] = entry['_meta']
            cleaned.append(clean_entry)

        self.links.extend(cleaned)
        return cleaned

    # ========== COOKIE MANAGEMENT METHODS ==========
    def run_auto_detect_cookies(self):
        """
        Manually trigger Workflow 1 (Smart Browser Cookie Extraction).
        Uses a QThread so all GUI updates are thread-safe via Qt signals.
        """
        self.auto_detect_btn.setEnabled(False)
        self.auto_detect_btn.setText("Detecting...")
        self.cookie_status.setText("Running Workflow 1 – smart browser detection...")
        self.cookie_status.setStyleSheet("color: #F39C12; font-size: 11px;")

        self._auto_detect_worker = _AutoDetectWorker(self.cookies_dir)
        self._auto_detect_worker.log_msg.connect(self.log_area.append)
        self._auto_detect_worker.status_ok.connect(
            lambda t: (
                self.cookie_status.setText(t),
                self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 11px;"),
            )
        )
        self._auto_detect_worker.status_err.connect(
            lambda t: (
                self.cookie_status.setText(t),
                self.cookie_status.setStyleSheet("color: #E74C3C; font-size: 11px;"),
            )
        )
        self._auto_detect_worker.finished_signal.connect(
            lambda: (
                self.auto_detect_btn.setEnabled(True),
                self.auto_detect_btn.setText("Auto-Detect Cookies from Browser"),
            )
        )
        self._auto_detect_worker.start()

    def upload_cookie_file(self):
        """Upload cookie file from disk"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Cookie File", "", "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    cookies = f.read()
                self.cookie_text.setPlainText(cookies)
                self.log_area.append(f" Cookie file loaded: {Path(file_path).name}")
                self.detect_cookie_platforms(cookies)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load cookie file: {str(e)}")

    def detect_cookie_platforms(self, cookies):
        """Detect which platforms are in the cookie file"""
        cookies_lower = cookies.lower()
        platforms = []
        if 'youtube.com' in cookies_lower or 'google.com' in cookies_lower:
            platforms.append("YouTube")
        if 'instagram.com' in cookies_lower:
            platforms.append("Instagram")
        if 'tiktok.com' in cookies_lower:
            platforms.append("TikTok")
        if 'facebook.com' in cookies_lower:
            platforms.append("Facebook")
        if 'twitter.com' in cookies_lower or 'x.com' in cookies_lower:
            platforms.append("Twitter")

        if platforms:
            self.cookie_status.setText(f" Detected: {', '.join(platforms)}")
            self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 11px;")
        else:
            self.cookie_status.setText("No known platforms detected")
            self.cookie_status.setStyleSheet("color: #E74C3C; font-size: 11px;")
        self._refresh_cookie_validity()

    def save_cookies(self):
        """Save cookies as master chrome_cookies.txt file with comprehensive validation"""
        cookies = self.cookie_text.toPlainText().strip()
        if not cookies:
            QMessageBox.warning(self, "Error", "No cookies to save!")
            return

        # === STEP 1: Comprehensive Validation ===
        self.log_area.append(" Validating cookies...")
        validator = EnhancedCookieValidator()
        validation_result = validator.validate(cookies)

        # Show validation results
        if not validation_result.is_valid:
            # Validation FAILED - show detailed error
            error_details = validation_result.get_summary()
            self.log_area.append(f" Cookie validation failed!\n{error_details}")

            # Show error dialog with detailed message
            QMessageBox.critical(
                self, " Cookie Validation Failed",
                f"{error_details}\n"
                f"Please fix the errors and try again.\n\n"
                f"TIP: Use 'Get cookies.txt' Chrome extension to export cookies in correct format."
            )
            return

        # Validation SUCCESSFUL - but check for warnings
        if validation_result.warnings:
            warning_msg = " Cookies are valid but have some warnings:\n\n"
            for i, warning in enumerate(validation_result.warnings, 1):
                warning_msg += f"{i}. {warning}\n"
            warning_msg += "\n Do you want to save anyway?"

            reply = QMessageBox.question(
                self, " Validation Warnings",
                warning_msg,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.No:
                self.log_area.append(" Cookie save cancelled by user")
                return

        # Log validation success
        self.log_area.append(f" Validation passed: {validation_result.cookie_count} cookies, "
                           f"{len(validation_result.platforms_detected)} platforms")

        # === STEP 2: Backup Existing Cookies ===
        cookie_file = self.cookies_dir / "chrome_cookies.txt"
        backup_created = False

        if cookie_file.exists():
            try:
                # Create backup with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = self.cookies_dir / f"chrome_cookies_{timestamp}.txt.bak"

                shutil.copy2(cookie_file, backup_file)
                backup_created = True
                self.log_area.append(f" Backup created: {backup_file.name}")

                # Keep only last 5 backups to save space
                self._cleanup_old_backups()

            except Exception as e:
                # Backup failed - ask user if they want to continue
                reply = QMessageBox.warning(
                    self, " Backup Failed",
                    f"Failed to create backup: {str(e)}\n\n"
                    f"Do you want to save anyway (existing cookies will be overwritten)?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply == QMessageBox.No:
                    self.log_area.append(" Save cancelled - backup failed")
                    return

        # === STEP 3: Save New Cookies ===
        try:
            with open(cookie_file, 'w', encoding='utf-8') as f:
                f.write(cookies)

            self.log_area.append(f" Cookies saved to: cookies/chrome_cookies.txt")
            try:
                self.auth_hub.write_auth_state(
                    {
                        "cookies": {
                            "master_file": str(cookie_file),
                            "cookie_count": int(getattr(validation_result, "cookie_count", 0) or 0),
                            "platforms": sorted(
                                list(getattr(validation_result, "platforms_detected", []) or [])
                            ),
                        }
                    }
                )
            except Exception:
                pass

            # Update UI status
            self.detect_cookie_platforms(cookies)

            # === STEP 4: Show Detailed Success Message ===
            success_msg = validation_result.get_summary()
            success_msg += "\n\n"
            success_msg += f" Saved to: cookies/chrome_cookies.txt\n"

            if backup_created:
                success_msg += f" Previous cookies backed up\n"

            success_msg += f"\n These cookies will be used automatically for ALL link extraction operations."

            QMessageBox.information(self, " Cookies Saved Successfully", success_msg)
            self._refresh_cookie_validity()

        except Exception as e:
            # Save failed
            self.log_area.append(f" Failed to save cookies: {str(e)}")
            QMessageBox.critical(
                self, " Save Failed",
                f"Failed to save cookies:\n{str(e)}\n\n"
                f"Check file permissions and try again."
            )

    def _cleanup_old_backups(self):
        """Keep only last 5 cookie backups"""
        try:
            backup_files = sorted(
                self.cookies_dir.glob("chrome_cookies_*.txt.bak"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            # Remove old backups (keep only 5 most recent)
            for old_backup in backup_files[5:]:
                old_backup.unlink()
                self.log_area.append(f" Removed old backup: {old_backup.name}")

        except Exception as e:
            # Cleanup failure is not critical, just log it
            self.log_area.append(f" Backup cleanup warning: {str(e)}")

    def validate_cookies(self, cookies):
        """Validate Netscape cookie format"""
        if not cookies:
            return False
        lines = cookies.strip().split('\n')
        has_header = any('Netscape' in line for line in lines[:3])
        valid_lines = sum(1 for line in lines if not line.startswith('#') and line.strip() and len(line.split('\t')) >= 7)
        return has_header or valid_lines > 0

    def clear_cookies(self):
        """Clear cookie text area"""
        self.cookie_text.clear()
        self.cookie_status.setText("No cookies loaded - Using browser cookies or public access")
        self.cookie_status.setStyleSheet("color: #888; font-size: 11px;")
        self.log_area.append(" Cookie text area cleared")
        self._refresh_cookie_validity()


