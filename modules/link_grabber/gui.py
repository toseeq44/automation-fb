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
    QProgressBar, QTextEdit, QSpinBox, QMessageBox, QListWidget, QMenu, QAction, QCheckBox
)
from PyQt5.QtCore import Qt
from pathlib import Path
import pyperclip
from .core import LinkGrabberThread, BulkLinkGrabberThread, _extract_creator_from_url, _detect_platform_key, _safe_filename

class LinkGrabberPage(QWidget):
    def __init__(self, go_back_callback=None, shared_links=None):
        super().__init__()
        self.thread = None
        self.go_back_callback = go_back_callback
        self.links = shared_links if shared_links is not None else []  # Use shared links
        self.creator = "unknown"
        self.init_ui()

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

        self.back_btn = QPushButton("⬅ Back")
        self.start_btn = QPushButton("🎯 Start")
        self.cancel_btn = QPushButton("❌ Cancel")
        self.save_btn = QPushButton("💾 Save")
        self.copy_btn = QPushButton("📋 Copy All")
        self.clear_btn = QPushButton("🧹 Clear")
        self.download_btn = QPushButton("⬇ Download Links")  # New button to switch to downloader

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
        self.back_btn.setStyleSheet(button_style)
        self.start_btn.setStyleSheet(button_style)
        self.cancel_btn.setStyleSheet(button_style)
        self.save_btn.setStyleSheet(button_style)
        self.copy_btn.setStyleSheet(button_style)
        self.clear_btn.setStyleSheet(button_style)
        self.download_btn.setStyleSheet(button_style)

        self.back_btn.setEnabled(bool(self.go_back_callback))
        self.save_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.download_btn.setEnabled(False)

        btn_row.addWidget(self.back_btn)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.copy_btn)
        btn_row.addWidget(self.clear_btn)
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

        self.back_btn.clicked.connect(self.go_back)
        self.start_btn.clicked.connect(self.start_grabbing)
        self.cancel_btn.clicked.connect(self.cancel_grab)
        self.save_btn.clicked.connect(self.save_to_folder)
        self.copy_btn.clicked.connect(self.copy_all_links)
        self.clear_btn.clicked.connect(self.clear_interface)
        self.download_btn.clicked.connect(self.start_download_page)

        # Populate link list if shared links exist
        for link in self.links:
            self.link_list.addItem(link['url'])
            self.save_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)
            self.download_btn.setEnabled(True)

    def go_back(self):
        if self.go_back_callback:
            self.go_back_callback()
        else:
            QMessageBox.warning(self, "Error", "No back navigation available.")

    def start_download_page(self):
        if self.go_back_callback:
            self.go_back_callback()  # Return to menu to select downloader
        else:
            QMessageBox.warning(self, "Error", "Download page navigation not available.")

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
        self.save_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.start_btn.setEnabled(False)

        max_videos = 0 if self.all_videos_check.isChecked() else self.limit_spin.value()
        options = {"max_videos": max_videos}
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
        self.thread.save_triggered.connect(self.on_save_triggered)
        self.thread.start()

        self.log_area.append("🚀 Started grabbing links...")

    def cancel_grab(self):
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.log_area.append("⚠️ Cancelling process...")
            self.thread = None
        self.start_btn.setEnabled(True)
        self.save_btn.setEnabled(bool(self.links))
        self.copy_btn.setEnabled(bool(self.links))
        self.download_btn.setEnabled(bool(self.links))

    def save_to_folder(self):
        if not self.links:
            QMessageBox.warning(self, "Error", "No links to save.")
            return
        try:
            desktop = Path.home() / "Desktop" / "Toseeq Links Grabber"
            desktop.mkdir(parents=True, exist_ok=True)
            filename = _safe_filename(self.creator) + ".txt" if self.creator != "bulk" else "bulk_links.txt"
            filepath = desktop / filename
            with open(filepath, "w", encoding="utf-8") as f:
                for link in self.links:
                    f.write(f"{link['url']}\n")
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
        self.download_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.thread = None

    def on_progress_log(self, msg):
        self.log_area.append(msg)
        self.log_area.ensureCursorVisible()

    def on_progress_percent(self, val):
        self.progress_bar.setValue(val)

    def on_link_found(self, link, text):
        self.link_list.addItem(text)
        self.links.append({'url': link})

    def on_finished(self, success, message, links):
        self.log_area.append(message)
        self.start_btn.setEnabled(True)
        self.save_btn.setEnabled(success and bool(links))
        self.copy_btn.setEnabled(success and bool(links))
        self.download_btn.setEnabled(success and bool(links))
        self.thread = None
        if success:
            QMessageBox.information(self, "Completed", f"{message}\n\nClick 'Save to Folder' or 'Download Links'.")

    def on_save_triggered(self, path, links):
        self.log_area.append(f"✅ File saved to: {path}")
        QMessageBox.information(self, "Saved", f"Saved {len(links)} links to {path}")

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