"""
modules/link_grabber/gui.py
INTELLIGENT LINK GRABBER GUI - Simplified & Modern

Features:
- 🍪 Cookie Management (Upload, Paste, Save to root/cookies folder)
- 🧠 Shows intelligence/learning status
- 📅 Displays dates with links
- 🎯 Simple, clean interface
- 📊 Important information only
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QTextEdit, QSpinBox, QMessageBox, QListWidget, QMenu,
    QAction, QCheckBox, QGroupBox, QComboBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from pathlib import Path
import pyperclip
from .core import LinkGrabberThread, BulkLinkGrabberThread, _extract_creator_from_url, _detect_platform_key, _safe_filename


class LinkGrabberPage(QWidget):
    def __init__(self, go_back_callback=None, shared_links=None):
        super().__init__()
        self.thread = None
        self.go_back_callback = go_back_callback
        self.links = shared_links if shared_links is not None else []
        self.creator = "unknown"

        # Root cookies folder
        self.cookies_dir = Path(__file__).parent.parent.parent / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Dark theme
        self.setStyleSheet("""
            QWidget {
                background-color: #23272A;
                color: #F5F6F5;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                border: 2px solid #4B5057;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        # ========== TITLE ==========
        title = QLabel("🧠 Intelligent Link Grabber")
        title.setStyleSheet("""
            font-size: 26px;
            font-weight: bold;
            color: #1ABC9C;
            margin-bottom: 10px;
        """)
        main_layout.addWidget(title)

        # ========== URL INPUT SECTION ==========
        url_group = QGroupBox("📋 URL Input")
        url_layout = QVBoxLayout()

        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            "Enter URL(s) here...\n\n"
            "Single URL: One creator's channel/profile\n"
            "Multiple URLs: One per line for bulk extraction\n\n"
            "Supported: YouTube, Instagram, TikTok, Facebook, Twitter"
        )
        self.url_input.setMaximumHeight(100)
        self.url_input.setStyleSheet("""
            QTextEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: 2px solid #1ABC9C;
            }
        """)
        url_layout.addWidget(self.url_input)

        url_group.setLayout(url_layout)
        main_layout.addWidget(url_group)

        # ========== COOKIE SECTION ==========
        cookie_group = QGroupBox("🍪 Cookies (Optional - For Private/Unlisted Content)")
        cookie_layout = QVBoxLayout()

        # Platform selector
        platform_row = QHBoxLayout()
        platform_label = QLabel("Platform:")
        platform_label.setStyleSheet("font-size: 14px;")
        self.platform_combo = QComboBox()
        self.platform_combo.addItems([
            "Auto-Detect",
            "youtube",
            "instagram",
            "tiktok",
            "facebook",
            "twitter"
        ])
        self.platform_combo.setStyleSheet("""
            QComboBox {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                padding: 8px;
                border-radius: 5px;
                font-size: 14px;
            }
            QComboBox:hover {
                border: 2px solid #1ABC9C;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2C2F33;
                color: #F5F6F5;
                selection-background-color: #1ABC9C;
            }
        """)
        platform_row.addWidget(platform_label)
        platform_row.addWidget(self.platform_combo)
        platform_row.addStretch()
        cookie_layout.addLayout(platform_row)

        # Cookie text area
        self.cookie_text = QTextEdit()
        self.cookie_text.setPlaceholderText(
            "Paste cookies here (Netscape format)...\n\n"
            "Example:\n"
            "# Netscape HTTP Cookie File\n"
            ".youtube.com\tTRUE\t/\tTRUE\t1735689600\tSSID\tvalue123\n"
            ".youtube.com\tTRUE\t/\tTRUE\t1735689600\tHSID\tvalue456\n\n"
            "How to get cookies:\n"
            "1. Install 'Get cookies.txt LOCALLY' browser extension\n"
            "2. Go to YouTube/Instagram/TikTok and login\n"
            "3. Click extension → Export → Copy\n"
            "4. Paste here and click 'Save Cookies'"
        )
        self.cookie_text.setMaximumHeight(120)
        self.cookie_text.setStyleSheet("""
            QTextEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        cookie_layout.addWidget(self.cookie_text)

        # Cookie buttons
        cookie_btn_row = QHBoxLayout()

        self.upload_cookie_btn = QPushButton("📤 Upload File")
        self.save_cookie_btn = QPushButton("💾 Save Cookies")
        self.clear_cookie_btn = QPushButton("🧹 Clear")

        for btn in [self.upload_cookie_btn, self.save_cookie_btn, self.clear_cookie_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1ABC9C;
                    color: #F5F6F5;
                    border: none;
                    padding: 8px 15px;
                    border-radius: 5px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #16A085;
                }
                QPushButton:pressed {
                    background-color: #128C7E;
                }
            """)

        cookie_btn_row.addWidget(self.upload_cookie_btn)
        cookie_btn_row.addWidget(self.save_cookie_btn)
        cookie_btn_row.addWidget(self.clear_cookie_btn)
        cookie_btn_row.addStretch()
        cookie_layout.addLayout(cookie_btn_row)

        # Cookie status
        self.cookie_status = QLabel("Status: No cookies loaded")
        self.cookie_status.setStyleSheet("color: #888; font-size: 12px; margin-top: 5px;")
        cookie_layout.addWidget(self.cookie_status)

        cookie_group.setLayout(cookie_layout)
        main_layout.addWidget(cookie_group)

        # ========== OPTIONS ==========
        options_row = QHBoxLayout()

        self.all_videos_check = QCheckBox("Fetch All Videos")
        self.all_videos_check.setChecked(True)
        self.all_videos_check.setStyleSheet("""
            QCheckBox {
                color: #F5F6F5;
                font-size: 14px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
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
        self.limit_label.setStyleSheet("color: #F5F6F5; font-size: 14px;")
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 1000)
        self.limit_spin.setValue(0)
        self.limit_spin.setEnabled(False)
        self.limit_spin.setStyleSheet("""
            QSpinBox {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                padding: 6px;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        options_row.addWidget(self.limit_label)
        options_row.addWidget(self.limit_spin)
        options_row.addStretch()

        main_layout.addLayout(options_row)

        # ========== ACTION BUTTONS ==========
        btn_row = QHBoxLayout()

        self.back_btn = QPushButton("⬅ Back")
        self.start_btn = QPushButton("🎯 Start Extraction")
        self.cancel_btn = QPushButton("❌ Cancel")
        self.save_btn = QPushButton("💾 Save")
        self.copy_btn = QPushButton("📋 Copy All")
        self.clear_btn = QPushButton("🧹 Clear")

        button_style = """
            QPushButton {
                background-color: #1ABC9C;
                color: #F5F6F5;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 15px;
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

        for btn in [self.back_btn, self.start_btn, self.cancel_btn,
                    self.save_btn, self.copy_btn, self.clear_btn]:
            btn.setStyleSheet(button_style)

        self.back_btn.setEnabled(bool(self.go_back_callback))
        self.save_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)

        btn_row.addWidget(self.back_btn)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.copy_btn)
        btn_row.addWidget(self.clear_btn)
        main_layout.addLayout(btn_row)

        # ========== EXTRACTION STATUS ==========
        status_group = QGroupBox("📊 Extraction Status")
        status_layout = QVBoxLayout()

        self.status_display = QLabel(
            "Creator: -\n"
            "Platform: -\n"
            "Method: Waiting...\n"
            "Links Found: 0\n"
            "Status: Ready"
        )
        self.status_display.setStyleSheet("""
            font-size: 13px;
            color: #1ABC9C;
            background-color: #2C2F33;
            padding: 10px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
        """)
        status_layout.addWidget(self.status_display)

        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        # ========== PROGRESS BAR ==========
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2C2F33;
                border: 2px solid #4B5057;
                border-radius: 8px;
                text-align: center;
                color: #F5F6F5;
                font-size: 14px;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #1ABC9C;
                border-radius: 6px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # ========== EXTRACTED LINKS ==========
        links_header = QHBoxLayout()
        links_label = QLabel("📝 Extracted Links (with Dates)")
        links_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1ABC9C;")
        links_header.addWidget(links_label)
        links_header.addStretch()
        main_layout.addLayout(links_header)

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
                font-size: 13px;
                font-family: 'Courier New', monospace;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #1ABC9C;
                color: #F5F6F5;
            }
            QListWidget::item:hover {
                background-color: #3A3F44;
            }
        """)
        main_layout.addWidget(self.link_list)

        # ========== LOG AREA ==========
        log_label = QLabel("📋 Extraction Log")
        log_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1ABC9C; margin-top: 10px;")
        main_layout.addWidget(log_label)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(150)
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
                font-family: 'Courier New', monospace;
            }
        """)
        main_layout.addWidget(self.log_area)

        self.setLayout(main_layout)

        # ========== CONNECT SIGNALS ==========
        self.back_btn.clicked.connect(self.go_back)
        self.start_btn.clicked.connect(self.start_grabbing)
        self.cancel_btn.clicked.connect(self.cancel_grab)
        self.save_btn.clicked.connect(self.save_to_folder)
        self.copy_btn.clicked.connect(self.copy_all_links)
        self.clear_btn.clicked.connect(self.clear_interface)

        # Cookie signals
        self.upload_cookie_btn.clicked.connect(self.upload_cookie_file)
        self.save_cookie_btn.clicked.connect(self.save_cookies)
        self.clear_cookie_btn.clicked.connect(self.clear_cookies)
        self.platform_combo.currentTextChanged.connect(self.check_existing_cookies)

        # Populate existing links
        for link in self.links:
            self.link_list.addItem(link['url'])
            self.save_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)

    # ========== NAVIGATION ==========
    def go_back(self):
        if self.go_back_callback:
            self.go_back_callback()
        else:
            QMessageBox.warning(self, "Error", "No back navigation available.")

    def toggle_limit_spin(self, state):
        self.limit_spin.setEnabled(state != Qt.Checked)

    # ========== COOKIE MANAGEMENT ==========
    def upload_cookie_file(self):
        """Upload cookie file from disk"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cookie File",
            "",
            "Text Files (*.txt);;All Files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    cookies = f.read()

                self.cookie_text.setPlainText(cookies)
                self.log_area.append(f"✅ Cookie file loaded: {Path(file_path).name}")

                # Auto-detect platform
                self.auto_detect_platform_from_cookies(cookies)

            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load cookie file: {str(e)}")

    def auto_detect_platform_from_cookies(self, cookies):
        """Auto-detect platform from cookie domains"""
        cookies_lower = cookies.lower()

        if 'youtube.com' in cookies_lower or 'google.com' in cookies_lower:
            self.platform_combo.setCurrentText("youtube")
            self.cookie_status.setText("Status: 🎯 Detected YouTube cookies")
            self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 12px;")
        elif 'instagram.com' in cookies_lower:
            self.platform_combo.setCurrentText("instagram")
            self.cookie_status.setText("Status: 🎯 Detected Instagram cookies")
            self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 12px;")
        elif 'tiktok.com' in cookies_lower:
            self.platform_combo.setCurrentText("tiktok")
            self.cookie_status.setText("Status: 🎯 Detected TikTok cookies")
            self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 12px;")
        elif 'facebook.com' in cookies_lower:
            self.platform_combo.setCurrentText("facebook")
            self.cookie_status.setText("Status: 🎯 Detected Facebook cookies")
            self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 12px;")
        elif 'twitter.com' in cookies_lower or 'x.com' in cookies_lower:
            self.platform_combo.setCurrentText("twitter")
            self.cookie_status.setText("Status: 🎯 Detected Twitter cookies")
            self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 12px;")
        else:
            self.cookie_status.setText("Status: ⚠️ Unknown platform")
            self.cookie_status.setStyleSheet("color: #E74C3C; font-size: 12px;")

    def save_cookies(self):
        """Save cookies to root cookies folder"""
        cookies = self.cookie_text.toPlainText().strip()

        if not cookies:
            QMessageBox.warning(self, "Error", "No cookies to save!")
            return

        # Validate cookie format
        if not self.validate_cookies(cookies):
            QMessageBox.warning(
                self,
                "Invalid Format",
                "Cookies must be in Netscape format!\n\n"
                "Expected format:\n"
                "# Netscape HTTP Cookie File\n"
                ".domain.com  TRUE  /  TRUE  expiry  name  value"
            )
            return

        platform = self.platform_combo.currentText().lower()

        if platform == "auto-detect":
            # Try to detect from cookies
            self.auto_detect_platform_from_cookies(cookies)
            platform = self.platform_combo.currentText().lower()

            if platform == "auto-detect":
                QMessageBox.warning(self, "Error", "Please select a platform manually!")
                return

        # Save to root cookies folder: cookies/{platform}.txt
        cookie_file = self.cookies_dir / f"{platform}.txt"

        try:
            with open(cookie_file, 'w', encoding='utf-8') as f:
                f.write(cookies)

            self.cookie_status.setText(f"Status: ✅ Saved to cookies/{platform}.txt")
            self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 12px; font-weight: bold;")
            self.log_area.append(f"✅ Cookies saved to: cookies/{platform}.txt")

            QMessageBox.information(
                self,
                "Success",
                f"Cookies saved successfully!\n\n"
                f"File: cookies/{platform}.txt\n"
                f"Platform: {platform.title()}\n\n"
                f"These cookies will be used automatically when extracting from {platform.title()}."
            )

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save cookies: {str(e)}")

    def validate_cookies(self, cookies):
        """Validate Netscape cookie format"""
        if not cookies:
            return False

        lines = cookies.strip().split('\n')

        # Check if it has Netscape header or at least one valid cookie line
        has_header = any('Netscape' in line for line in lines[:3])

        # Check for valid cookie lines (7 tab-separated fields)
        valid_lines = 0
        for line in lines:
            if line.startswith('#') or not line.strip():
                continue

            parts = line.split('\t')
            if len(parts) >= 7:
                valid_lines += 1

        return has_header or valid_lines > 0

    def clear_cookies(self):
        """Clear cookie text area"""
        self.cookie_text.clear()
        self.cookie_status.setText("Status: No cookies loaded")
        self.cookie_status.setStyleSheet("color: #888; font-size: 12px;")
        self.log_area.append("🧹 Cookie text area cleared")

    def check_existing_cookies(self, platform_text):
        """Check if cookies already exist for selected platform"""
        if platform_text == "Auto-Detect":
            return

        platform = platform_text.lower()
        cookie_file = self.cookies_dir / f"{platform}.txt"

        if cookie_file.exists():
            try:
                file_size = cookie_file.stat().st_size
                self.cookie_status.setText(
                    f"Status: ✅ Found existing cookies ({file_size} bytes)"
                )
                self.cookie_status.setStyleSheet("color: #1ABC9C; font-size: 12px;")

                # Ask if user wants to load them
                reply = QMessageBox.question(
                    self,
                    "Existing Cookies Found",
                    f"Found existing {platform.title()} cookies ({file_size} bytes).\n\n"
                    f"Do you want to load them?",
                    QMessageBox.Yes | QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    with open(cookie_file, 'r', encoding='utf-8') as f:
                        existing_cookies = f.read()
                    self.cookie_text.setPlainText(existing_cookies)
                    self.log_area.append(f"✅ Loaded existing {platform.title()} cookies")

            except Exception as e:
                self.cookie_status.setText("Status: ⚠️ Error reading cookie file")
                self.cookie_status.setStyleSheet("color: #E74C3C; font-size: 12px;")
        else:
            self.cookie_status.setText(f"Status: No {platform} cookies found")
            self.cookie_status.setStyleSheet("color: #888; font-size: 12px;")

    # ========== EXTRACTION ==========
    def start_grabbing(self):
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "Error", "Process already running. Please wait or cancel.")
            return

        url_text = self.url_input.toPlainText().strip()
        if not url_text:
            QMessageBox.warning(self, "Error", "Please enter at least one URL.")
            return

        urls = [url.strip() for url in url_text.split('\n') if url.strip()]

        self.link_list.clear()
        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.links.clear()
        self.save_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.start_btn.setEnabled(False)

        max_videos = 0 if self.all_videos_check.isChecked() else self.limit_spin.value()
        options = {"max_videos": max_videos}

        if len(urls) == 1:
            self.thread = LinkGrabberThread(urls[0], options)
            try:
                platform = _detect_platform_key(urls[0])
                self.creator = _extract_creator_from_url(urls[0], platform)
                self.update_status(f"@{self.creator}", platform.upper(), "Initializing...", 0, "Starting...")
            except Exception as e:
                self.log_area.append(f"⚠️ Failed to extract creator: {str(e)[:100]}")
                self.creator = "unknown"
        else:
            self.thread = BulkLinkGrabberThread(urls, options)
            self.creator = "bulk"
            self.update_status("Multiple Creators", "BULK MODE", "Initializing...", 0, "Starting...")

        self.thread.progress.connect(self.on_progress_log)
        self.thread.progress_percent.connect(self.on_progress_percent)
        self.thread.link_found.connect(self.on_link_found)
        self.thread.finished.connect(self.on_finished)
        self.thread.save_triggered.connect(self.on_save_triggered)
        self.thread.start()

        self.log_area.append("🚀 Started intelligent link grabbing...")
        self.log_area.append("🧠 Learning system active - tracking performance...")

    def update_status(self, creator, platform, method, links_count, status):
        """Update status display"""
        self.status_display.setText(
            f"Creator: {creator}\n"
            f"Platform: {platform}\n"
            f"Method: {method}\n"
            f"Links Found: {links_count}\n"
            f"Status: {status}"
        )

    def cancel_grab(self):
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.log_area.append("⚠️ Cancelling process...")
            self.thread = None
        self.start_btn.setEnabled(True)
        self.save_btn.setEnabled(bool(self.links))
        self.copy_btn.setEnabled(bool(self.links))

    def save_to_folder(self):
        if not self.links:
            QMessageBox.warning(self, "Error", "No links to save.")
            return

        try:
            desktop = Path.home() / "Desktop" / "Toseeq Links Grabber"
            desktop.mkdir(parents=True, exist_ok=True)
            filename = _safe_filename(self.creator) + "_links.txt" if self.creator != "bulk" else "bulk_links.txt"
            filepath = desktop / filename

            with open(filepath, "w", encoding="utf-8") as f:
                for link in self.links:
                    url = link['url']
                    date = link.get('date', '')
                    if date and date != '00000000':
                        from .core import _parse_upload_date
                        date_str = _parse_upload_date(date)
                        f.write(f"{url}  # {date_str}\n")
                    else:
                        f.write(f"{url}\n")

            self.log_area.append(f"✅ File saved to: {filepath}")
            QMessageBox.information(self, "Saved", f"Saved {len(self.links)} links to {filepath}")

        except Exception as e:
            self.log_area.append(f"❌ Failed to save file: {str(e)[:100]}")
            QMessageBox.warning(self, "Error", f"Failed to save file: {str(e)[:100]}")

    def clear_interface(self):
        self.url_input.clear()
        self.link_list.clear()
        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.links.clear()
        self.creator = "unknown"
        self.save_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        self.update_status("-", "-", "Waiting...", 0, "Ready")
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.thread = None

    def on_progress_log(self, msg):
        self.log_area.append(msg)
        self.log_area.ensureCursorVisible()

        # Update status display based on log messages
        if "Platform:" in msg:
            platform = msg.split(":")[1].strip()
            self.update_status(f"@{self.creator}", platform, "Detecting...", len(self.links), "Analyzing...")
        elif "Best method:" in msg or "Trying:" in msg:
            method = msg.split(":")[-1].strip() if ":" in msg else msg
            self.update_status(f"@{self.creator}", "-", method[:40], len(self.links), "Extracting...")
        elif "Success!" in msg or "Complete" in msg:
            self.update_status(f"@{self.creator}", "-", "Completed", len(self.links), "✅ Done!")

    def on_progress_percent(self, val):
        self.progress_bar.setValue(val)

    def on_link_found(self, link, text):
        self.link_list.addItem(text)
        self.links.append({'url': link, 'date': ''})
        self.update_status(f"@{self.creator}", "-", "Extracting...", len(self.links), "In Progress...")

    def on_finished(self, success, message, links):
        self.log_area.append(message)
        self.start_btn.setEnabled(True)
        self.save_btn.setEnabled(success and bool(links))
        self.copy_btn.setEnabled(success and bool(links))
        self.thread = None

        if success:
            self.update_status(f"@{self.creator}", "-", "Completed", len(links), "✅ Success!")
            QMessageBox.information(
                self,
                "Completed",
                f"{message}\n\n"
                f"Links have been auto-saved to creator folder.\n"
                f"You can also click 'Copy All' to copy links to clipboard."
            )

    def on_save_triggered(self, path, links):
        self.log_area.append(f"💾 Auto-saved to: {path}")

    def show_context_menu(self, position):
        if not self.link_list.selectedItems():
            return

        menu = QMenu()
        copy_action = QAction("Copy Selected Links", self)
        copy_action.triggered.connect(self.copy_selected_links)
        menu.addAction(copy_action)
        menu.exec_(self.link_list.mapToGlobal(position))

    def copy_selected_links(self):
        selected = [item.text().split("  (")[0] for item in self.link_list.selectedItems()]  # Remove date part
        if selected:
            pyperclip.copy('\n'.join(selected))
            self.log_area.append(f"✅ Copied {len(selected)} selected links to clipboard!")

    def copy_all_links(self):
        if self.links:
            urls = [link['url'] for link in self.links]
            pyperclip.copy('\n'.join(urls))
            self.log_area.append(f"✅ Copied {len(urls)} links to clipboard!")
            QMessageBox.information(self, "Copied", f"Copied {len(urls)} links to clipboard!")
