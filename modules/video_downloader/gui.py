import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QProgressBar, QComboBox, QCheckBox, QFileDialog, QMessageBox,
    QListWidget, QGroupBox, QLineEdit, QMenu, QListWidgetItem, QDialog,
    QDialogButtonBox, QSpinBox
)
from PyQt5.QtGui import QClipboard, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt, QUrl
from PyQt5 import QtWidgets
from pathlib import Path
from datetime import datetime
from .core import VideoDownloaderThread
from .url_utils import extract_urls
from .bulk_preview_dialog import BulkPreviewDialog
from .history_manager import HistoryManager

class VideoDownloaderPage(QWidget):
    def __init__(self, back_callback=None, links=None):
        super().__init__()
        self.back_callback = back_callback
        self.downloader_thread = None
        self.links = links if links is not None else []
        self.bulk_mode_data = None  # Stores bulk mode info
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

        self.title = QLabel("⬇️ Video Downloader")
        self.title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1ABC9C; margin-bottom: 15px;")
        layout.addWidget(self.title)

        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("Paste video URL(s) (multiple lines or comma-separated)")
        self.url_input.setStyleSheet("""
            QTextEdit {
                background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;
                padding: 10px; border-radius: 8px; font-size: 16px;
            }
            QTextEdit:focus { border: 2px solid #1ABC9C; }
        """)
        self.url_input.setMinimumHeight(80)
        layout.addWidget(self.url_input)

        # Editable link text area with drag-and-drop support + Load buttons
        link_label = QLabel("📋 Links (editable - cut/paste/drag-drop .txt files here):")
        link_label.setStyleSheet("color: #1ABC9C; font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(link_label)

        # Buttons for loading links
        load_buttons_layout = QHBoxLayout()
        load_txt_btn = QPushButton("📄 Load .txt File")
        load_folder_btn = QPushButton("📂 Load Folder Structure")
        load_btn_style = """
            QPushButton { background-color: #1ABC9C; color: #F5F6F5; border: none;
                         padding: 8px 15px; border-radius: 6px; font-size: 13px; font-weight: bold; }
            QPushButton:hover { background-color: #16A085; }
            QPushButton:pressed { background-color: #128C7E; }
        """
        load_txt_btn.setStyleSheet(load_btn_style)
        load_folder_btn.setStyleSheet(load_btn_style)
        load_txt_btn.clicked.connect(self.load_txt_file)
        load_folder_btn.clicked.connect(self.browse_and_load_folder_structure)
        load_buttons_layout.addWidget(load_txt_btn)
        load_buttons_layout.addWidget(load_folder_btn)
        load_buttons_layout.addStretch()
        layout.addLayout(load_buttons_layout)

        self.link_text = QTextEdit()
        self.link_text.setPlaceholderText("Links will appear here (editable - you can cut/paste/drag-drop)\n\nQuick Actions:\n• Click '📄 Load .txt File' to select a single .txt file\n• Click '📂 Load Folder Structure' to load creator folders")
        self.link_text.setAcceptDrops(True)
        self.link_text.dragEnterEvent = self.link_text_drag_enter
        self.link_text.dropEvent = self.link_text_drop
        self.link_text.setStyleSheet("""
            QTextEdit {
                background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;
                border-radius: 8px; padding: 10px; font-size: 14px;
            }
            QTextEdit:focus { border: 2px solid #1ABC9C; }
        """)
        self.link_text.setMinimumHeight(120)
        layout.addWidget(self.link_text)

        settings_group = QGroupBox("Download Settings")
        settings_group.setStyleSheet("""
            QGroupBox { color: #1ABC9C; border: 2px solid #4B5057; border-radius: 8px;
                        margin-top: 12px; padding-top: 15px; background-color: #2C2F33;
                        font-weight: bold; font-size: 14px; }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 8px; }
        """)
        settings_layout = QVBoxLayout()

        path_layout = QHBoxLayout()
        path_label = QLabel("📁 Save to:")
        path_label.setStyleSheet("color: #F5F6F5; font-size: 16px;")
        self.path_input = QLineEdit()
        self.path_input.setText(str(Path.home() / "Desktop" / "Toseeq Downloads"))
        self.path_input.setStyleSheet("""
            QLineEdit { background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;
                        padding: 10px; border-radius: 8px; font-size: 16px; }
            QLineEdit:focus { border: 2px solid #1ABC9C; }
        """)
        browse_btn = QPushButton("📁 Browse")
        button_style_browse = """
            QPushButton { background-color: #1ABC9C; color: #F5F6F5; border: none;
                         padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background-color: #16A085; }
            QPushButton:pressed { background-color: #128C7E; }
        """
        browse_btn.setStyleSheet(button_style_browse)
        browse_btn.clicked.connect(self.browse_folder)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        settings_layout.addLayout(path_layout)

        quality_layout = QHBoxLayout()
        quality_label = QLabel("🎥 Quality:")
        quality_label.setStyleSheet("color: #F5F6F5; font-size: 16px;")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "Mobile (480p, small size)",
            "HD (1080p, balanced)",
            "4K (maximum quality)",
            "Best",
            "Medium (720p)",
            "Low (480p)"
        ])
        self.quality_combo.setCurrentIndex(1)  # Default to HD
        self.quality_combo.setStyleSheet("""
            QComboBox { background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;
                        padding: 8px; border-radius: 8px; font-size: 16px; }
            QComboBox:focus { border: 2px solid #1ABC9C; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background-color: #2C2F33; color: #F5F6F5;
                                         selection-background-color: #1ABC9C; }
        """)
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)
        settings_layout.addLayout(quality_layout)

        # Custom bitrate control
        bitrate_layout = QHBoxLayout()
        bitrate_label = QLabel("📊 Bitrate (kbps):")
        bitrate_label.setStyleSheet("color: #F5F6F5; font-size: 16px;")
        self.bitrate_input = QLineEdit()
        self.bitrate_input.setPlaceholderText("Leave empty for auto (optional)")
        self.bitrate_input.setStyleSheet("""
            QLineEdit { background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;
                        padding: 8px; border-radius: 8px; font-size: 16px; }
            QLineEdit:focus { border: 2px solid #1ABC9C; }
        """)
        bitrate_layout.addWidget(bitrate_label)
        bitrate_layout.addWidget(self.bitrate_input)
        settings_layout.addLayout(bitrate_layout)

        # Max retries control
        retry_layout = QHBoxLayout()
        retry_label = QLabel("🔄 Max Retries:")
        retry_label.setStyleSheet("color: #F5F6F5; font-size: 16px;")
        self.retry_spinbox = QComboBox()
        self.retry_spinbox.addItems(["1", "3", "5", "10"])
        self.retry_spinbox.setCurrentIndex(1)  # Default to 3
        self.retry_spinbox.setStyleSheet("""
            QComboBox { background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;
                        padding: 8px; border-radius: 8px; font-size: 16px; }
            QComboBox:focus { border: 2px solid #1ABC9C; }
        """)
        retry_layout.addWidget(retry_label)
        retry_layout.addWidget(self.retry_spinbox)
        retry_layout.addStretch()
        settings_layout.addLayout(retry_layout)

        options_layout = QHBoxLayout()
        self.playlist_check = QCheckBox("📑 Playlist")
        self.subtitle_check = QCheckBox("📝 Subtitles")
        self.thumbnail_check = QCheckBox("🖼️ Thumbnail")
        for cb in [self.playlist_check, self.subtitle_check, self.thumbnail_check]:
            cb.setStyleSheet("""
                QCheckBox { color: #F5F6F5; font-size: 16px; font-weight: bold;
                            background-color: #2C2F33; padding: 8px; border-radius: 5px; }
                QCheckBox::indicator { width: 24px; height: 24px; background-color: #2C2F33;
                                      border: 2px solid #4B5057; border-radius: 4px; }
                QCheckBox::indicator:checked { background-color: #1ABC9C; border: 2px solid #1ABC9C; }
            """)
        options_layout.addWidget(self.playlist_check)
        options_layout.addWidget(self.subtitle_check)
        options_layout.addWidget(self.thumbnail_check)
        options_layout.addStretch()
        settings_layout.addLayout(options_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.back_btn = QPushButton("⬅ Back")
        self.start_btn = QPushButton("⬇ Start")
        self.cancel_btn = QPushButton("❌ Cancel")
        self.clear_btn = QPushButton("🗑️ Clear")
        button_style = """
            QPushButton { background-color: #1ABC9C; color: #F5F6F5; border: none;
                         padding: 10px 20px; border-radius: 8px; font-size: 16px; font-weight: bold; }
            QPushButton:hover { background-color: #16A085; }
            QPushButton:pressed { background-color: #128C7E; }
            QPushButton:disabled { background-color: #4B5057; color: #888; }
        """
        for btn in [self.back_btn, self.start_btn, self.cancel_btn, self.clear_btn]:
            btn.setStyleSheet(button_style)
        self.cancel_btn.setVisible(False)
        btn_row.addWidget(self.back_btn)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #2C2F33; border: 2px solid #4B5057;
                          border-radius: 8px; text-align: center; color: #F5F6F5; font-size: 14px; }
            QProgressBar::chunk { background-color: #1ABC9C; border-radius: 6px; }
        """)
        layout.addWidget(self.progress_bar)

        info_layout = QHBoxLayout()
        self.speed_label = QLabel("Speed: --")
        self.eta_label = QLabel("ETA: --")
        for label in [self.speed_label, self.eta_label]:
            label.setStyleSheet("color: #F5F6F5; font-size: 14px;")
            label.setVisible(False)
        info_layout.addWidget(self.speed_label)
        info_layout.addWidget(self.eta_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit { background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;
                        border-radius: 8px; padding: 10px; font-size: 14px; }
        """)
        layout.addWidget(self.log_text)

        self.setLayout(layout)

        self.back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        self.start_btn.clicked.connect(self.start_download)
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.clear_btn.clicked.connect(self.clear_all)

        self.log_message("✓ Video Downloader ready")
        self.log_message("💡 Supports YouTube, TikTok, Instagram, and more")
        self.update_links(self.links)

    def load_txt_file(self):
        """Load links from a single .txt file"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select .txt File with Links",
                str(Path.home() / "Desktop"),
                "Text Files (*.txt);;All Files (*.*)"
            )

            if not file_path:
                return

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    links = [line.strip() for line in content.splitlines() if line.strip() and line.strip().startswith('http')]

                    if links:
                        # Replace or append?
                        current_text = self.link_text.toPlainText().strip()
                        if current_text:
                            reply = QMessageBox.question(
                                self,
                                "Add or Replace?",
                                f"Found {len(links)} links.\n\nAdd to existing links or replace all?",
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.Yes
                            )
                            if reply == QMessageBox.Yes:
                                # Append
                                self.link_text.setPlainText(current_text + '\n' + '\n'.join(links))
                            else:
                                # Replace
                                self.link_text.setPlainText('\n'.join(links))
                        else:
                            # No existing text, just set
                            self.link_text.setPlainText('\n'.join(links))

                        self.log_message(f"✅ Loaded {len(links)} links from: {Path(file_path).name}")
                    else:
                        QMessageBox.warning(self, "No Links Found", f"No valid HTTP(S) links found in:\n{Path(file_path).name}")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not read file:\n{str(e)[:200]}")
                self.log_message(f"⚠️ Error reading file: {str(e)[:100]}")

        except Exception as e:
            self.log_message(f"⚠️ Error: {str(e)[:100]}")

    def link_text_drag_enter(self, event: QDragEnterEvent):
        """Handle drag enter for file drops"""
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def link_text_drop(self, event: QDropEvent):
        """Handle file drops - read .txt files and add links"""
        try:
            if event.mimeData().hasUrls():
                urls = event.mimeData().urls()
                links_added = 0

                for url in urls:
                    file_path = url.toLocalFile()
                    if file_path.endswith('.txt'):
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                # Add to existing text
                                current_text = self.link_text.toPlainText()
                                if current_text:
                                    self.link_text.setPlainText(current_text + '\n' + content)
                                else:
                                    self.link_text.setPlainText(content)
                                links_added += 1
                                self.log_message(f"📂 Loaded links from: {Path(file_path).name}")
                        except Exception as e:
                            self.log_message(f"⚠️ Could not read {Path(file_path).name}: {str(e)[:50]}")

                if links_added > 0:
                    self.log_message(f"✅ Loaded {links_added} file(s)")
                    event.acceptProposedAction()
            elif event.mimeData().hasText():
                # Handle text drops
                text = event.mimeData().text()
                current_text = self.link_text.toPlainText()
                if current_text:
                    self.link_text.setPlainText(current_text + '\n' + text)
                else:
                    self.link_text.setPlainText(text)
                event.acceptProposedAction()
        except Exception as e:
            self.log_message(f"⚠️ Drop error: {str(e)[:100]}")

    def browse_and_load_folder_structure(self):
        """Enhanced folder structure loading with creator detection and history"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder Structure (with creator subfolders)",
            str(Path.home() / "Desktop")
        )

        if not folder:
            return

        try:
            folder_path = Path(folder)

            # Initialize history manager
            try:
                history_mgr = HistoryManager(folder_path)
            except Exception:
                history_mgr = None

            # Find creator folders and their links
            creator_data = {}  # {creator_name: {'links': [], 'folder': Path, 'links_file': Path}}

            # Scan for creator subfolders (any folder with *_links.txt)
            for item in folder_path.iterdir():
                if not item.is_dir():
                    continue

                # Look for *_links.txt files in this folder
                links_files = list(item.glob('*_links.txt'))
                if not links_files:
                    # Also check for any .txt file
                    links_files = list(item.glob('*.txt'))
                    # Filter out hidden/system files
                    links_files = [f for f in links_files if not f.name.startswith('.')]

                if not links_files:
                    continue

                creator_name = item.name
                all_links = []

                # Read all link files for this creator
                for links_file in links_files:
                    try:
                        with open(links_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            links = [
                                line.strip()
                                for line in content.splitlines()
                                if line.strip() and
                                   not line.strip().startswith('#') and
                                   ('http://' in line or 'https://' in line)
                            ]
                            all_links.extend(links)
                    except Exception as e:
                        self.log_message(f"⚠️ Error reading {links_file.name}: {str(e)[:50]}")

                if all_links:
                    creator_data[creator_name] = {
                        'links': all_links,
                        'folder': item,
                        'links_file': links_files[0]  # Primary links file
                    }
                    self.log_message(f"📂 {creator_name}: {len(all_links)} links")

            if not creator_data:
                QMessageBox.warning(
                    self,
                    "No Creators Found",
                    f"No creator folders with *_links.txt found in:\n{folder}\n\n"
                    f"Expected structure:\n"
                    f"  CreatorName/\n"
                    f"    CreatorName_links.txt"
                )
                return

            # Show enhanced bulk preview dialog
            dialog = BulkPreviewDialog(self, creator_data, history_mgr)

            if dialog.exec_() == QDialog.Accepted:
                selected_links = dialog.get_selected_links()
                selected_creators = dialog.get_selected_creators()

                if selected_links:
                    # Add to link text area
                    self.link_text.setPlainText('\n'.join(selected_links))
                    self.log_message(f"✅ Loaded {len(selected_links)} links from {len(selected_creators)} creator(s)")

                    # Set save path to parent folder
                    self.path_input.setText(str(folder_path))
                    self.log_message(f"📁 Save location: {folder_path}")

                    # Store creator data for later use
                    self.bulk_mode_data = {
                        'enabled': True,
                        'creators': selected_creators,
                        'history_manager': history_mgr
                    }
                else:
                    QMessageBox.information(
                        self,
                        "No Links Selected",
                        "No links were selected for download."
                    )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process folder:\n{str(e)[:200]}")
            self.log_message(f"❌ Folder processing error: {str(e)[:100]}")


    def clear_all(self):
        reply = QMessageBox.question(self, "Clear All?", "Clear URLs, logs, and links?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.url_input.clear()
            self.log_text.clear()
            self.progress_bar.setValue(0)
            self.speed_label.setText("Speed: --")
            self.eta_label.setText("ETA: --")
            self.link_text.clear()
            self.links = []
            self.bulk_mode_data = None  # Clear bulk mode
            self.log_message("🗑️ Cleared everything")

    def update_links(self, links):
        """Update link text area with links from link grabber"""
        self.links = links if links else []

        # Convert links to text
        link_texts = []
        for link in self.links:
            # Handle both string and dict
            if isinstance(link, str):
                url = link
            elif isinstance(link, dict):
                url = link.get('url', '')
            else:
                url = str(link)

            if url:
                link_texts.append(url)

        if link_texts:
            self.link_text.setPlainText('\n'.join(link_texts))
            self.log_message(f"📋 Loaded {len(link_texts)} link(s) from Link Grabber")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.path_input.text())
        if folder:
            self.path_input.setText(folder)
            self.log_message(f"📁 Save location: {folder}")

    def start_download(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Download in progress. Wait or cancel.")
            return

        # Check URL input first
        raw_urls = self.url_input.toPlainText().strip()

        # If URL input is manually entered (not from bulk mode), clear bulk mode
        if raw_urls and not (self.bulk_mode_data and self.bulk_mode_data.get('enabled')):
            # User entered URLs manually - this is single mode
            self.bulk_mode_data = None

        # If URL input is empty, check link text area
        if not raw_urls:
            link_text = self.link_text.toPlainText().strip()
            if link_text:
                raw_urls = link_text
                self.url_input.setPlainText(raw_urls)
            elif self.links:
                # Fallback to self.links
                raw_urls = '\n'.join([link.get('url', str(link)) if isinstance(link, dict) else str(link) for link in self.links])
                self.url_input.setPlainText(raw_urls)
            else:
                QMessageBox.warning(self, "Error", "Paste at least one URL or grab links first.")
                return

        urls = extract_urls(raw_urls)
        if not urls:
            QMessageBox.warning(self, "Error", "No valid URLs found.")
            return

        # Replace input with cleaned list so the user sees what will be downloaded
        self.url_input.setPlainText('\n'.join(urls))

        save_path = self.path_input.text().strip()
        if not save_path:
            QMessageBox.warning(self, "Error", "Select save folder.")
            return

        if not os.path.exists(save_path):
            reply = QMessageBox.question(self, "Create?", f"Folder not found:\n{save_path}\n\nCreate it?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                try:
                    os.makedirs(save_path, exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Cannot create folder: {str(e)[:100]}")
                    return
            else:
                return

        # Enhanced quality mapping
        quality_map = {
            0: 'Mobile',
            1: 'HD',
            2: '4K',
            3: 'Best',
            4: 'Medium',
            5: 'Low'
        }
        quality = quality_map.get(self.quality_combo.currentIndex(), 'HD')

        # Get custom bitrate if specified
        custom_bitrate = None
        bitrate_text = self.bitrate_input.text().strip()
        if bitrate_text.isdigit():
            custom_bitrate = int(bitrate_text)

        # Get max retries
        max_retries = int(self.retry_spinbox.currentText())

        options = {
            'quality': quality,
            'bitrate': custom_bitrate,
            'max_retries': max_retries,
            'playlist': self.playlist_check.isChecked(),
            'subtitles': self.subtitle_check.isChecked(),
            'thumbnail': self.thumbnail_check.isChecked(),
            'skip_recent_window': False,
        }

        self.start_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setValue(0)
        self.speed_label.setVisible(True)
        self.eta_label.setVisible(True)

        self.log_message("="*60)
        self.log_message(f"🔗 URLs: {len(urls)}")
        self.log_message(f"📁 Save: {save_path}")
        self.log_message(f"🎥 Quality: {quality}")
        if custom_bitrate:
            self.log_message(f"📊 Bitrate: {custom_bitrate} kbps")
        self.log_message(f"🔄 Max Retries: {max_retries}")
        self.log_message(f"✅ Auto-resume: ON")
        self.log_message(f"🔍 Duplicate detection: ON")
        if options['playlist']:
            self.log_message("📑 Playlist mode: ON")
        if options['subtitles']:
            self.log_message("📝 Subtitles: ON")
        if options['thumbnail']:
            self.log_message("🖼️ Thumbnails: ON")
        self.log_message("="*60)

        # Pass bulk mode data if available
        self.downloader_thread = VideoDownloaderThread(
            urls,
            save_path,
            options,
            bulk_mode_data=self.bulk_mode_data
        )
        self.downloader_thread.progress.connect(self.log_message)
        self.downloader_thread.progress_percent.connect(self.progress_bar.setValue)
        self.downloader_thread.download_speed.connect(lambda s: self.speed_label.setText(f"Speed: {s}"))
        self.downloader_thread.eta.connect(lambda e: self.eta_label.setText(f"ETA: {e}"))
        self.downloader_thread.video_complete.connect(lambda f: self.log_message(f"✅ Saved: {f}"))
        self.downloader_thread.finished.connect(self.download_finished)
        self.downloader_thread.start()

    def cancel_download(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.cancel()
            self.log_message("⚠️ Cancelling download...")

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.ensureCursorVisible()

    def download_finished(self, success, message):
        self.log_message(message)
        self.log_message("=" * 60)
        self.start_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.speed_label.setVisible(False)
        self.eta_label.setVisible(False)
        self.progress_bar.setValue(100 if success else 0)

        folder = self.path_input.text().strip()

        # Show notification popup (NO AUTO-OPEN FOLDER)
        if success:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("✅ Download Complete!")
            msg_box.setText(message)
            msg_box.setInformativeText(f"📁 Location: {folder}")

            # Add button to open folder manually (optional)
            open_folder_btn = msg_box.addButton("Open Folder", QMessageBox.ActionRole)
            msg_box.addButton("Close", QMessageBox.AcceptRole)

            msg_box.exec_()

            # Only open if user clicks "Open Folder"
            if msg_box.clickedButton() == open_folder_btn:
                if folder and os.path.isdir(folder):
                    import subprocess
                    import platform

                    # Cross-platform folder opening
                    if platform.system() == 'Windows':
                        subprocess.Popen(['explorer', folder])
                    elif platform.system() == 'Darwin':  # macOS
                        subprocess.Popen(['open', folder])
                    else:  # Linux
                        subprocess.Popen(['xdg-open', folder])
        else:
            QMessageBox.critical(self, "❌ Download Failed", message)
