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
    QGroupBox, QComboBox, QFileDialog
)
from PyQt5.QtCore import Qt
from pathlib import Path
import pyperclip
import shutil
from datetime import datetime
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

class LinkGrabberPage(QWidget):
    def __init__(self, go_back_callback=None, shared_links=None, download_callback=None):
        super().__init__()
        self.thread = None
        self.go_back_callback = go_back_callback
        self.download_callback = download_callback
        self.links = shared_links if shared_links is not None else []  # Use shared links
        self.creator = "unknown"
        self.creator_results = {}

        # Root cookies folder
        self.cookies_dir = Path(__file__).parent.parent.parent / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

        self.init_ui()

    def closeEvent(self, event):
        """Properly cleanup thread on close to prevent crash"""
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.thread.wait(2000)  # Wait max 2 seconds
            self.thread.quit()
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

        self.title = QLabel("🔗 Fast Link Grabber")
        self.title.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #1ABC9C;
            margin-bottom: 15px;
        """)
        layout.addWidget(self.title)

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
        cookie_group = QGroupBox("🍪 Cookies (Optional - For Private Content)")
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

        # Cookie source selector
        source_row = QHBoxLayout()
        source_label = QLabel("Cookie Source:")
        self.cookie_source_combo = QComboBox()
        self.cookie_source_combo.addItems(["Upload File", "Use Browser (Chrome)", "Use Browser (Firefox)", "Use Browser (Edge)"])
        self.cookie_source_combo.setStyleSheet("""
            QComboBox {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                padding: 5px;
                border-radius: 5px;
            }
        """)
        source_row.addWidget(source_label)
        source_row.addWidget(self.cookie_source_combo)
        source_row.addStretch()
        cookie_layout.addLayout(source_row)

        # Cookie text area (only for Upload File mode)
        self.cookie_text = QTextEdit()
        self.cookie_text.setPlaceholderText(
            "Paste Chrome cookies here (Netscape format)...\n"
            "TIP: Use 'Get cookies.txt' Chrome extension to export\n"
            "Example: .youtube.com\tTRUE\t/\tTRUE\t1234567890\tSSID\tvalue123"
        )
        self.cookie_text.setMaximumHeight(80)
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

        # Cookie buttons
        cookie_btn_row = QHBoxLayout()
        self.upload_cookie_btn = QPushButton("📤 Upload Cookie File")
        self.save_cookie_btn = QPushButton("💾 Save")
        self.clear_cookie_btn = QPushButton("🧹 Clear")

        for btn in [self.upload_cookie_btn, self.save_cookie_btn, self.clear_cookie_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1ABC9C;
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 5px;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #16A085; }
            """)

        cookie_btn_row.addWidget(self.upload_cookie_btn)
        cookie_btn_row.addWidget(self.save_cookie_btn)
        cookie_btn_row.addWidget(self.clear_cookie_btn)
        cookie_btn_row.addStretch()
        cookie_layout.addLayout(cookie_btn_row)

        # Cookie status
        self.cookie_status = QLabel("💡 No cookies loaded - Using browser cookies or public access")
        self.cookie_status.setStyleSheet("color: #888; font-size: 11px;")
        cookie_layout.addWidget(self.cookie_status)

        cookie_group.setLayout(cookie_layout)
        layout.addWidget(cookie_group)

        # Connect cookie signals
        self.upload_cookie_btn.clicked.connect(self.upload_cookie_file)
        self.save_cookie_btn.clicked.connect(self.save_cookies)
        self.clear_cookie_btn.clicked.connect(self.clear_cookies)
        self.cookie_source_combo.currentTextChanged.connect(self.on_cookie_source_changed)

        # Set initial state - enable all buttons for "Upload File" mode
        self.cookie_text.setEnabled(True)
        self.upload_cookie_btn.setEnabled(True)
        self.save_cookie_btn.setEnabled(True)
        self.clear_cookie_btn.setEnabled(True)

        # ===== PROXY SECTION (2026 Upgrade) =====
        proxy_group = QGroupBox("🌐 Proxy Settings (Optional - Max 2 Proxies)")
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
        self.validate_proxy1_btn = QPushButton("✓ Validate")
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
        self.proxy1_status = QLabel("⚪ Not validated")
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
        self.validate_proxy2_btn = QPushButton("✓ Validate")
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
        self.proxy2_status = QLabel("⚪ Not validated")
        self.proxy2_status.setStyleSheet("color: #888; font-size: 11px;")

        proxy2_row.addWidget(proxy2_label)
        proxy2_row.addWidget(self.proxy2_input, 3)
        proxy2_row.addWidget(self.validate_proxy2_btn)
        proxy2_row.addWidget(self.proxy2_status, 1)
        proxy_layout.addLayout(proxy2_row)

        # Proxy info/tip
        proxy_tip = QLabel("💡 Proxies help bypass IP blocks and rate limits. Leave empty to use direct connection.")
        proxy_tip.setStyleSheet("color: #888; font-size: 11px; font-style: italic;")
        proxy_layout.addWidget(proxy_tip)

        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)

        # Connect proxy validation signals
        self.validate_proxy1_btn.clicked.connect(lambda: self.validate_proxy(1))
        self.validate_proxy2_btn.clicked.connect(lambda: self.validate_proxy(2))

        # Store validated proxies
        self.validated_proxies = []

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

        self.start_btn = QPushButton("🎯 Start")
        self.cancel_btn = QPushButton("❌ Cancel")
        self.save_btn = QPushButton("💾 Save")
        self.copy_btn = QPushButton("📋 Copy All")
        self.clear_btn = QPushButton("🧹 Clear")
        self.download_btn = QPushButton("⬇ Download Links")  # New button to switch to downloader
        self.help_btn = QPushButton("❓ Help")  # New help button

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

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
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
            self.log_area.append(f"🚀 Sent {len(cleaned)} link(s) to Video Downloader (Single Mode).")
        else:
            QMessageBox.information(
                self,
                "Links Ready",
                f"Prepared {len(cleaned)} link(s). Switch to the Video Downloader module to continue."
            )
            self.log_area.append("ℹ️ Links ready for downloader - open the Video Downloader module to continue.")

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
            status_label.setText("⚪ Not validated")
            status_label.setStyleSheet("color: #888; font-size: 11px;")
            return

        # Show validating message
        status_label.setText("🔄 Validating...")
        status_label.setStyleSheet("color: #FFA500; font-size: 11px;")
        self.log_area.append(f"🔄 Validating Proxy {proxy_num}: {proxy}")

        # Validate proxy
        result = _validate_proxy(proxy, timeout=10)

        if result['working']:
            # Proxy is working
            status_label.setText(f"✅ Working ({result['response_time']}s)")
            status_label.setStyleSheet("color: #1ABC9C; font-size: 11px;")
            self.log_area.append(f"✅ Proxy {proxy_num} validated: {result['ip']} ({result['response_time']}s)")

            # Add to validated list
            if proxy not in self.validated_proxies:
                self.validated_proxies.append(proxy)

        else:
            # Proxy failed - Show detailed error
            error_msg = result.get('error', 'Unknown error')

            # Truncate error for status label (max 30 chars)
            short_error = error_msg[:30] + "..." if len(error_msg) > 30 else error_msg
            status_label.setText(f"❌ {short_error}")
            status_label.setStyleSheet("color: #E74C3C; font-size: 10px;")
            status_label.setToolTip(error_msg)  # Full error in tooltip

            # Show full error in log
            self.log_area.append(f"❌ Proxy {proxy_num} validation failed")
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

        # Get cookie source
        cookie_source = self.cookie_source_combo.currentText()
        browser = None
        if cookie_source != "Upload File":
            # Extract browser name (e.g., "Use Browser (Chrome)" -> "chrome")
            browser = cookie_source.split("(")[1].split(")")[0].lower()

        # Collect proxies (if provided)
        proxies = []
        proxy1 = self.proxy1_input.text().strip()
        proxy2 = self.proxy2_input.text().strip()

        if proxy1 and proxy1 in self.validated_proxies:
            proxies.append(proxy1)
        if proxy2 and proxy2 in self.validated_proxies:
            proxies.append(proxy2)

        if proxies:
            self.log_area.append(f"🌐 Using {len(proxies)} validated proxy(ies)")

        options = {
            "max_videos": max_videos,
            "cookie_browser": browser,  # None for file, "chrome"/"firefox"/"edge" for browser
            "proxies": proxies,  # List of validated proxies
            "use_enhancements": True  # Enable enhanced extraction methods
        }
        if len(urls) == 1:
            self.thread = LinkGrabberThread(urls[0], options)
            try:
                self.creator = _extract_creator_from_url(urls[0], _detect_platform_key(urls[0]))
            except Exception as e:
                self.log_area.append(f"⚠️ Failed to extract creator: {str(e)[:100]}")
                self.creator = "unknown"
        else:
            self.thread = BulkLinkGrabberThread(urls, options)
            self.creator = "bulk"

        self.thread.progress.connect(self.on_progress_log)
        self.thread.progress_percent.connect(self.on_progress_percent)
        self.thread.link_found.connect(self.on_link_found)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

        self.log_area.append("🚀 Started grabbing links...")

    def cancel_grab(self):
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.log_area.append("⚠️ Cancelling process...")
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

            self.log_area.append(f"✅ Saved {total_links} links across {len(saved_details)} creator folder(s).")

            summary_lines = [
                f"• @{_safe_filename(name)} → {count} links\n  {path}"
                for name, path, count in saved_details
            ]
            QMessageBox.information(
                self,
                "Saved",
                f"Saved {total_links} links across {len(saved_details)} creator(s).\n\n" + "\n".join(summary_lines)
            )
        except Exception as e:
            self.log_area.append(f"❌ Failed to save files: {str(e)[:100]}")
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
╔══════════════════════════════════════════════════════════════════════╗
║           📖 Link Grabber - User Guide & Troubleshooting             ║
╚══════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🌐 PROXY SETUP GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The app supports ALL proxy formats automatically:

1️⃣ No Authentication:
   209.101.203.79:59100

2️⃣ Standard Format (user:pass@ip:port):
   username:password@209.101.203.79:59100

3️⃣ Provider Format (ip:port:user:pass):
   209.101.203.79:59100:username:password

✨ All formats are automatically detected and converted!

HOW TO USE:
• Enter proxy in ANY format above
• Click "✓ Validate" to test connection
• Green ✅ = Working, Red ❌ = Failed
• Only validated proxies are used during extraction

WHY USE PROXIES:
• Bypass IP blocks and rate limits
• Access geo-restricted content
• Prevent detection during bulk operations
• Max 2 proxies supported

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🔧 yt-dlp INSTALLATION (Optional - App Has Built-in)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The app includes yt-dlp, but you can install your own for updates:

DETECTION PRIORITY:
1. Bundled yt-dlp.exe (in app) - Most reliable ✓
2. System yt-dlp (in PATH) - If you installed
3. Custom locations (C:\\yt-dlp, AppData, etc.)

RECOMMENDED INSTALL (for updates):
1. Download: https://github.com/yt-dlp/yt-dlp/releases/latest
2. Install to system PATH OR save to: C:\\yt-dlp\\yt-dlp.exe
3. Restart app

VERIFICATION:
• Open Command Prompt
• Run: yt-dlp --version
• Should show version number

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🍪 COOKIE TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If link grabbing fails:

✅ SOLUTIONS:
1. Update cookies (they expire!)
2. Use "Use Browser (Chrome)" option
3. Try different proxy
4. Check if account is private
5. Verify you're logged into the platform

COOKIE FORMATS:
• Netscape format (recommended)
• Export using "Get cookies.txt" Chrome extension
• Place in cookies/ folder or use Browser mode

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🎯 BEST PRACTICES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Always validate proxies before use
• Update cookies regularly (weekly)
• Use "Fetch All Videos" for complete extraction
• For private accounts, ensure cookies are fresh
• Check logs for detailed error messages

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ❓ COMMON ERRORS & FIXES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ERROR: "Proxy connection failed"
FIX: Check proxy format, verify credentials, try HTTP instead of HTTPS

ERROR: "No links found"
FIX: Update cookies, check account privacy, try proxy, verify URL

ERROR: "Proxy timeout"
FIX: Proxy too slow, try different proxy or increase timeout

ERROR: "Authentication failed"
FIX: Check proxy username/password, verify format

╔══════════════════════════════════════════════════════════════════════╗
║  Need more help? Check the logs for detailed error messages!         ║
╚══════════════════════════════════════════════════════════════════════╝
        """

        # Create scrollable message box
        msg = QMessageBox(self)
        msg.setWindowTitle("📖 Link Grabber Help & Guide")
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

    def on_progress_log(self, msg):
        self.log_area.append(msg)
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
            self.log_area.append(f"✅ Copied {len(selected)} selected links to clipboard!")
            self.download_btn.setEnabled(True)

    def copy_all_links(self):
        if self.links:
            urls = [link['url'] for link in self.links]
            pyperclip.copy('\n'.join(urls))
            self.log_area.append(f"✅ Copied {len(urls)} links to clipboard!")
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
            cleaned.append({'url': url})

        self.links.extend(cleaned)
        return cleaned

    # ========== COOKIE MANAGEMENT METHODS ==========
    def on_cookie_source_changed(self, source):
        """Handle cookie source selection change"""
        if source == "Upload File":
            self.cookie_text.setEnabled(True)
            self.upload_cookie_btn.setEnabled(True)
            self.save_cookie_btn.setEnabled(True)
            self.clear_cookie_btn.setEnabled(True)
            self.cookie_status.setText("💡 Upload your Chrome cookie file (Netscape format)")
        else:
            # Browser mode - disable file upload controls
            self.cookie_text.setEnabled(False)
            self.upload_cookie_btn.setEnabled(False)
            self.save_cookie_btn.setEnabled(False)
            self.clear_cookie_btn.setEnabled(False)
            browser = source.split("(")[1].split(")")[0]  # Extract browser name
            self.cookie_status.setText(f"✅ Will use cookies directly from {browser} browser")
            self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 11px;")

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
                self.log_area.append(f"✅ Cookie file loaded: {Path(file_path).name}")
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
            self.cookie_status.setText(f"✅ Detected: {', '.join(platforms)}")
            self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 11px;")
        else:
            self.cookie_status.setText("⚠️ No known platforms detected")
            self.cookie_status.setStyleSheet("color: #E74C3C; font-size: 11px;")

    def save_cookies(self):
        """Save cookies as master chrome_cookies.txt file with comprehensive validation"""
        cookies = self.cookie_text.toPlainText().strip()
        if not cookies:
            QMessageBox.warning(self, "Error", "No cookies to save!")
            return

        # === STEP 1: Comprehensive Validation ===
        self.log_area.append("🔍 Validating cookies...")
        validator = EnhancedCookieValidator()
        validation_result = validator.validate(cookies)

        # Show validation results
        if not validation_result.is_valid:
            # Validation FAILED - show detailed error
            error_details = validation_result.get_summary()
            self.log_area.append(f"❌ Cookie validation failed!\n{error_details}")

            # Show error dialog with detailed message
            QMessageBox.critical(
                self, "❌ Cookie Validation Failed",
                f"{error_details}\n"
                f"Please fix the errors and try again.\n\n"
                f"TIP: Use 'Get cookies.txt' Chrome extension to export cookies in correct format."
            )
            return

        # Validation SUCCESSFUL - but check for warnings
        if validation_result.warnings:
            warning_msg = "⚠️ Cookies are valid but have some warnings:\n\n"
            for i, warning in enumerate(validation_result.warnings, 1):
                warning_msg += f"{i}. {warning}\n"
            warning_msg += "\n✅ Do you want to save anyway?"

            reply = QMessageBox.question(
                self, "⚠️ Validation Warnings",
                warning_msg,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.No:
                self.log_area.append("❌ Cookie save cancelled by user")
                return

        # Log validation success
        self.log_area.append(f"✅ Validation passed: {validation_result.cookie_count} cookies, "
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
                self.log_area.append(f"💾 Backup created: {backup_file.name}")

                # Keep only last 5 backups to save space
                self._cleanup_old_backups()

            except Exception as e:
                # Backup failed - ask user if they want to continue
                reply = QMessageBox.warning(
                    self, "⚠️ Backup Failed",
                    f"Failed to create backup: {str(e)}\n\n"
                    f"Do you want to save anyway (existing cookies will be overwritten)?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply == QMessageBox.No:
                    self.log_area.append("❌ Save cancelled - backup failed")
                    return

        # === STEP 3: Save New Cookies ===
        try:
            with open(cookie_file, 'w', encoding='utf-8') as f:
                f.write(cookies)

            self.log_area.append(f"✅ Cookies saved to: cookies/chrome_cookies.txt")

            # Update UI status
            self.detect_cookie_platforms(cookies)

            # === STEP 4: Show Detailed Success Message ===
            success_msg = validation_result.get_summary()
            success_msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            success_msg += f"📁 Saved to: cookies/chrome_cookies.txt\n"

            if backup_created:
                success_msg += f"💾 Previous cookies backed up\n"

            success_msg += f"\n✅ These cookies will be used automatically for ALL link extraction operations."

            QMessageBox.information(self, "✅ Cookies Saved Successfully", success_msg)

        except Exception as e:
            # Save failed
            self.log_area.append(f"❌ Failed to save cookies: {str(e)}")
            QMessageBox.critical(
                self, "❌ Save Failed",
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
                self.log_area.append(f"🗑️ Removed old backup: {old_backup.name}")

        except Exception as e:
            # Cleanup failure is not critical, just log it
            self.log_area.append(f"⚠️ Backup cleanup warning: {str(e)}")

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
        self.cookie_status.setText("💡 No cookies loaded - Using browser cookies or public access")
        self.cookie_status.setStyleSheet("color: #888; font-size: 11px;")
        self.log_area.append("🧹 Cookie text area cleared")
