import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QProgressBar, QComboBox, QCheckBox, QFileDialog, QMessageBox,
    QListWidget, QGroupBox, QLineEdit, QMenu, QListWidgetItem 
)
from PyQt5.QtGui import QClipboard
from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets
from pathlib import Path
from datetime import datetime
from .core import VideoDownloaderThread

class VideoDownloaderPage(QWidget):
    def __init__(self, back_callback=None, links=None):
        super().__init__()
        self.back_callback = back_callback
        self.downloader_thread = None
        self.links = links if links is not None else []
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

        # Enhanced link list with copy/cut/paste support
        link_label = QLabel("📋 Links from Link Grabber (right-click to copy/cut):")
        link_label.setStyleSheet("color: #1ABC9C; font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(link_label)

        self.link_list = QListWidget()
        self.link_list.setSelectionMode(QListWidget.ExtendedSelection)  # Allow multiple selection
        self.link_list.setEditTriggers(QListWidget.DoubleClicked | QListWidget.EditKeyPressed)
        self.link_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.link_list.itemClicked.connect(self.select_link)
        self.link_list.customContextMenuRequested.connect(self.show_context_menu)
        self.link_list.setStyleSheet("""
            QListWidget {
                background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;
                border-radius: 8px; padding: 10px; font-size: 14px;
            }
            QListWidget::item:selected { background-color: #1ABC9C; color: #F5F6F5; }
            QListWidget::item:hover { background-color: #3A3D41; }
        """)
        layout.addWidget(self.link_list)

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
        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet("""
            QPushButton { background-color: #1ABC9C; color: #F5F6F5; border: none;
                         padding: 10px 20px; border-radius: 8px; font-size: 16px; font-weight: bold; }
            QPushButton:hover { background-color: #16A085; }
            QPushButton:pressed { background-color: #128C7E; }
        """)
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

    def show_context_menu(self, pos):
        item = self.link_list.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057; }
            QMenu::item:selected { background-color: #1ABC9C; }
        """)

        # Enhanced context menu
        edit_act = menu.addAction("✏️ Edit")
        copy_act = menu.addAction("📋 Copy")
        copy_all_act = menu.addAction("📋 Copy All Selected")
        cut_act = menu.addAction("✂️ Cut")
        paste_act = menu.addAction("📌 Paste to URL Input")
        menu.addSeparator()
        delete_act = menu.addAction("🗑️ Delete")
        delete_all_act = menu.addAction("🗑️ Delete All Selected")
        menu.addSeparator()
        select_all_act = menu.addAction("☑️ Select All")

        action = menu.exec_(self.link_list.mapToGlobal(pos))

        if action == edit_act:
            self.link_list.editItem(item)

        elif action == copy_act:
            # Copy single item
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(item.text())
            self.log_message(f"📋 Copied: {item.text()[:50]}...")

        elif action == copy_all_act:
            # Copy all selected items
            selected_items = self.link_list.selectedItems()
            if selected_items:
                urls = '\n'.join([item.text() for item in selected_items])
                clipboard = QtWidgets.QApplication.clipboard()
                clipboard.setText(urls)
                self.log_message(f"📋 Copied {len(selected_items)} links to clipboard")
            else:
                self.log_message("⚠️ No links selected")

        elif action == cut_act:
            # Cut single item
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(item.text())
            row = self.link_list.row(item)
            self.link_list.takeItem(row)
            if row < len(self.links):
                del self.links[row]
            self.log_message(f"✂️ Cut: {item.text()[:50]}...")

        elif action == paste_act:
            # Paste to URL input field
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard_text = clipboard.text()
            if clipboard_text:
                current_text = self.url_input.toPlainText()
                if current_text:
                    self.url_input.setPlainText(current_text + '\n' + clipboard_text)
                else:
                    self.url_input.setPlainText(clipboard_text)
                self.log_message("📌 Pasted to URL input field")
            else:
                self.log_message("⚠️ Clipboard is empty")

        elif action == delete_act:
            # Delete single item
            row = self.link_list.row(item)
            self.link_list.takeItem(row)
            if row < len(self.links):
                del self.links[row]
            self.log_message(f"🗑️ Deleted: {item.text()[:50]}...")

        elif action == delete_all_act:
            # Delete all selected items
            selected_items = self.link_list.selectedItems()
            if selected_items:
                for item in selected_items:
                    row = self.link_list.row(item)
                    self.link_list.takeItem(row)
                    if row < len(self.links):
                        del self.links[row]
                self.log_message(f"🗑️ Deleted {len(selected_items)} links")
            else:
                self.log_message("⚠️ No links selected")

        elif action == select_all_act:
            self.link_list.selectAll()
            self.log_message(f"☑️ Selected all {self.link_list.count()} links")

    def clear_all(self):
        reply = QMessageBox.question(self, "Clear All?", "Clear URLs, logs, and links list?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.url_input.clear()
            self.log_text.clear()
            self.progress_bar.setValue(0)
            self.speed_label.setText("Speed: --")
            self.eta_label.setText("ETA: --")
            self.link_list.clear()
            self.links = []
            self.log_message("🗑️ Cleared everything")

    def update_links(self, links):
        """Update link list - make all items editable"""
        self.links = links if links else []
        self.link_list.clear()
        
        for link in self.links:
            # Handle both string and dict
            if isinstance(link, str):
                url = link
            elif isinstance(link, dict):
                url = link.get('url', '')
            else:
                url = str(link)

            if url:
                item = QListWidgetItem(url)
                # Make item FULLY editable
                item.setFlags(
                    Qt.ItemIsSelectable | 
                    Qt.ItemIsEditable | 
                    Qt.ItemIsEnabled | 
                    Qt.ItemIsDragEnabled
                )
                self.link_list.addItem(item)
        
        # Drag and drop enabled
        self.link_list.setDragEnabled(True)
        self.link_list.setDragDropMode(QListWidget.InternalMove)
                
        if self.links:
            self.log_message(f"📋 Loaded {len(self.links)} link(s) from Link Grabber")

    def select_link(self, item):
        self.url_input.setPlainText(item.text())

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.path_input.text())
        if folder:
            self.path_input.setText(folder)
            self.log_message(f"📁 Save location: {folder}")

    def start_download(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Download in progress. Wait or cancel.")
            return

        raw_urls = self.url_input.toPlainText().strip()
        if not raw_urls:
            if self.links:
                raw_urls = '\n'.join([link.get('url', str(link)) if isinstance(link, dict) else str(link) for link in self.links])
                self.url_input.setPlainText(raw_urls)
            else:
                QMessageBox.warning(self, "Error", "Paste at least one URL or grab links first.")
                return

        urls = [u.strip() for u in raw_urls.replace(',', '\n').splitlines() if u.strip() and u.startswith(('http://', 'https://'))]
        if not urls:
            QMessageBox.warning(self, "Error", "No valid URLs found.")
            return

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
            'thumbnail': self.thumbnail_check.isChecked()
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

        self.downloader_thread = VideoDownloaderThread(urls, save_path, options)
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