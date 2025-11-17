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
from .folder_mapping_manager import FolderMappingManager
from .folder_mapping_dialog import FolderMappingDialog
from .move_progress_dialog import MoveProgressDialog

class VideoDownloaderPage(QWidget):
    def __init__(self, back_callback=None, links=None):
        super().__init__()
        self.back_callback = back_callback
        self.downloader_thread = None
        self.links = links if links is not None else []
        self.bulk_mode_data = None  # Stores bulk mode info
        self.mapping_manager = FolderMappingManager()  # Initialize folder mapping manager
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

        # ========== SINGLE MODE INPUT ==========
        single_mode_label = QLabel("🔸 SINGLE MODE - Manual URLs (for Link Grabber & direct paste)")
        single_mode_label.setStyleSheet("color: #1ABC9C; font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(single_mode_label)

        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("Paste video URLs here (one per line or comma-separated)\n\nThis field is for SINGLE MODE:\n• Direct URL paste\n• Link Grabber integration\n• Simple downloads to Desktop/Toseeq Downloads\n• No tracking, no extra files")
        self.url_input.setStyleSheet("""
            QTextEdit {
                background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;
                padding: 10px; border-radius: 8px; font-size: 16px;
            }
            QTextEdit:focus { border: 2px solid #1ABC9C; }
        """)
        self.url_input.setMinimumHeight(100)
        layout.addWidget(self.url_input)

        # Separator
        separator = QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        separator.setStyleSheet("color: #4B5057; margin: 10px 0px;")
        layout.addWidget(separator)

        # ========== BULK MODE INPUT ==========
        bulk_mode_label = QLabel("🔹 BULK MODE - Creator Folders (load folder structure below)")
        bulk_mode_label.setStyleSheet("color: #1ABC9C; font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(bulk_mode_label)

        # Folder structure button
        load_folder_btn = QPushButton("📂 Load Folder Structure (Bulk Mode)")
        load_folder_btn.setStyleSheet("""
            QPushButton { background-color: #E67E22; color: #F5F6F5; border: none;
                         padding: 10px 20px; border-radius: 6px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background-color: #D35400; }
            QPushButton:pressed { background-color: #BA4A00; }
        """)
        load_folder_btn.clicked.connect(self.browse_and_load_folder_structure)
        layout.addWidget(load_folder_btn)

        self.link_text = QTextEdit()
        self.link_text.setPlaceholderText("Creator links will appear here after loading folder structure\n\nThis field is for BULK MODE:\n• Load creator folders with *_links.txt files\n• Automatic history tracking (history.json)\n• Smart 24h skip\n• Per-creator downloads\n\n⚠️ Do NOT manually paste URLs here - use Single Mode field above")
        self.link_text.setReadOnly(True)  # Make read-only to prevent confusion
        self.link_text.setStyleSheet("""
            QTextEdit {
                background-color: #34495E; color: #F5F6F5; border: 2px solid #4B5057;
                border-radius: 8px; padding: 10px; font-size: 14px;
            }
            QTextEdit:focus { border: 2px solid #E67E22; }
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
        self.instagram_help_btn = QPushButton("📸 Instagram Help")
        button_style = """
            QPushButton { background-color: #1ABC9C; color: #F5F6F5; border: none;
                         padding: 10px 20px; border-radius: 8px; font-size: 16px; font-weight: bold; }
            QPushButton:hover { background-color: #16A085; }
            QPushButton:pressed { background-color: #128C7E; }
            QPushButton:disabled { background-color: #4B5057; color: #888; }
        """
        instagram_btn_style = """
            QPushButton { background-color: #E1306C; color: #F5F6F5; border: none;
                         padding: 10px 20px; border-radius: 8px; font-size: 16px; font-weight: bold; }
            QPushButton:hover { background-color: #C13584; }
            QPushButton:pressed { background-color: #A02D6F; }
        """
        for btn in [self.back_btn, self.start_btn, self.cancel_btn, self.clear_btn]:
            btn.setStyleSheet(button_style)
        self.instagram_help_btn.setStyleSheet(instagram_btn_style)
        self.cancel_btn.setVisible(False)
        btn_row.addWidget(self.back_btn)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.instagram_help_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ========== FOLDER MAPPING BUTTONS ==========
        mapping_row = QHBoxLayout()
        mapping_row.setSpacing(10)

        # Folder Mapping Configuration Button
        self.mapping_config_btn = QPushButton("📁 Configure Folder Mapping")
        mapping_config_btn_style = """
            QPushButton { background-color: #9B59B6; color: #F5F6F5; border: none;
                         padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background-color: #8E44AD; }
            QPushButton:pressed { background-color: #7D3C98; }
        """
        self.mapping_config_btn.setStyleSheet(mapping_config_btn_style)
        self.mapping_config_btn.clicked.connect(self.open_folder_mapping_dialog)
        self.mapping_config_btn.setToolTip("Configure folder mappings to move videos from Links Grabber to Creators Data folders")
        mapping_row.addWidget(self.mapping_config_btn)

        # Move Videos Button
        self.move_videos_btn = QPushButton("➡️ Move Videos to Creator Data")
        move_videos_btn_style = """
            QPushButton { background-color: #3498DB; color: #F5F6F5; border: none;
                         padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background-color: #2E86C1; }
            QPushButton:pressed { background-color: #2874A6; }
            QPushButton:disabled { background-color: #4B5057; color: #888; }
        """
        self.move_videos_btn.setStyleSheet(move_videos_btn_style)
        self.move_videos_btn.clicked.connect(self.move_videos_to_creator_data)
        self.move_videos_btn.setToolTip("Move videos based on configured folder mappings")
        mapping_row.addWidget(self.move_videos_btn)

        # Mapping Status Label
        self.mapping_status_label = QLabel()
        self.mapping_status_label.setStyleSheet("color: #3498DB; font-size: 12px; font-weight: bold;")
        self.update_mapping_status_label()
        mapping_row.addWidget(self.mapping_status_label)

        mapping_row.addStretch()
        layout.addLayout(mapping_row)

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
        self.instagram_help_btn.clicked.connect(self.show_instagram_help)

        self.log_message("✓ Video Downloader ready")
        self.log_message("💡 Supports YouTube, TikTok, Instagram, and more")
        self.update_links(self.links)

    # Removed old load_txt_file and drag/drop methods
    # Single Mode: Users paste URLs directly in url_input
    # Bulk Mode: Users load folder structure which populates link_text (read-only)

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

            # Initialize history manager FIRST (will create history.json if not exists)
            self.log_message("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.log_message("📊 Checking download history...")

            history_mgr = None
            try:
                history_mgr = HistoryManager(folder_path)
                history_file = folder_path / "history.json"

                # Ensure history.json exists (create if needed)
                history_mgr.ensure_exists()

                if history_file.exists():
                    all_history = history_mgr.get_all_creators()

                    if all_history:
                        # Has existing history data
                        self.log_message(f"✅ Found history.json with {len(all_history)} creator(s)")

                        # Show recent downloads
                        recent_creators = []
                        for creator, info in all_history.items():
                            if history_mgr.should_skip_creator(creator, window_hours=24):
                                last_time = info.get('last_download', 'Unknown')
                                try:
                                    from datetime import datetime
                                    dt = datetime.fromisoformat(last_time)
                                    last_time = dt.strftime('%Y-%m-%d %H:%M')
                                except:
                                    pass
                                recent_creators.append(f"{creator} ({last_time})")

                        if recent_creators:
                            self.log_message(f"⏸️ Recently downloaded (will skip by default):")
                            for rc in recent_creators[:5]:  # Show first 5
                                self.log_message(f"   • {rc}")
                            if len(recent_creators) > 5:
                                self.log_message(f"   ... and {len(recent_creators) - 5} more")
                    else:
                        # New history.json (just created)
                        self.log_message(f"📝 Created new history.json for tracking")

            except Exception as e:
                self.log_message(f"⚠️ History tracking unavailable: {str(e)[:50]}")
                history_mgr = None

            self.log_message("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.log_message("🔍 Scanning creator folders...")

            # Find creator folders and their links
            creator_data = {}  # {creator_name: {'links': [], 'folder': Path, 'links_file': Path}}
            skipped_creators = []  # Track which will be skipped

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
                    # Check if this creator should be skipped (24h window)
                    will_skip = False
                    if history_mgr and history_mgr.should_skip_creator(creator_name, window_hours=24):
                        will_skip = True
                        skipped_creators.append(creator_name)

                    creator_data[creator_name] = {
                        'links': all_links,
                        'folder': item,
                        'links_file': links_files[0],  # Primary links file
                        'will_skip_24h': will_skip  # Mark for UI
                    }

                    # Log with skip indicator
                    skip_marker = "⏸️ [WILL SKIP]" if will_skip else "✅"
                    self.log_message(f"{skip_marker} {creator_name}: {len(all_links)} links")

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

            # Summary
            total_creators = len(creator_data)
            active_creators = total_creators - len(skipped_creators)
            total_links = sum(len(d['links']) for d in creator_data.values())

            self.log_message("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.log_message(f"📊 Summary:")
            self.log_message(f"   Total creators: {total_creators}")
            self.log_message(f"   Will process: {active_creators}")
            self.log_message(f"   Will skip (24h): {len(skipped_creators)}")
            self.log_message(f"   Total links: {total_links}")
            self.log_message("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            # Show enhanced bulk preview dialog
            dialog = BulkPreviewDialog(self, creator_data, history_mgr)

            if dialog.exec_() == QDialog.Accepted:
                selected_links = dialog.get_selected_links()
                selected_creators = dialog.get_selected_creators()

                if selected_links:
                    # Add to BULK MODE link text area (read-only but we can set programmatically)
                    self.link_text.setReadOnly(False)  # Temporarily allow changes
                    self.link_text.setPlainText('\n'.join(selected_links))
                    self.link_text.setReadOnly(True)  # Re-lock
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
        """Update URL input with links from Link Grabber (SINGLE MODE)"""
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
            # Send to SINGLE MODE field (url_input)
            self.url_input.setPlainText('\n'.join(link_texts))
            self.log_message(f"📋 Loaded {len(link_texts)} link(s) from Link Grabber → SINGLE MODE")
            self.log_message(f"💡 Links loaded in Single Mode field - will download to Desktop/Toseeq Downloads")

    def show_instagram_help(self):
        """Show detailed Instagram cookie setup instructions"""
        from .instagram_helper import get_instagram_cookie_instructions, InstagramCookieValidator
        from pathlib import Path

        # Get instructions
        instructions = get_instagram_cookie_instructions()

        # Check current cookie status
        cookie_locations = [
            Path(__file__).parent.parent.parent / "cookies" / "instagram.txt",
            Path.home() / "Desktop" / "toseeq-cookies.txt",
        ]

        status_msg = "\n📊 CURRENT COOKIE STATUS:\n" + "="*60 + "\n"
        cookie_found = False

        for cookie_path in cookie_locations:
            if cookie_path.exists():
                cookie_found = True
                status_msg += f"\n📁 Found: {cookie_path}\n"
                validator = InstagramCookieValidator()
                result = validator.validate_cookie_file(str(cookie_path))

                if result['is_valid']:
                    status_msg += "✅ Status: VALID - Ready to use!\n"
                else:
                    status_msg += "❌ Status: INVALID\n"
                    for error in result['errors'][:2]:
                        status_msg += f"   • {error}\n"
                    if result['is_expired']:
                        status_msg += "   💡 Fix: Re-export cookies (expired)\n"
                    elif not result['has_sessionid']:
                        status_msg += "   💡 Fix: Login to Instagram before exporting\n"
                break

        if not cookie_found:
            status_msg += "❌ No Instagram cookies found\n"
            status_msg += "📍 Checked locations:\n"
            for loc in cookie_locations:
                status_msg += f"   • {loc}\n"

        status_msg += "\n" + "="*60 + "\n"

        # Show dialog
        dialog = QMessageBox(self)
        dialog.setWindowTitle("📸 Instagram Cookie Setup Guide")
        dialog.setIcon(QMessageBox.Information)
        dialog.setText("Instagram requires authentication to download videos.")
        dialog.setDetailedText(instructions + "\n\n" + status_msg)
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.exec_()

        # Also log to console
        self.log_message("="*60)
        self.log_message("📸 INSTAGRAM COOKIE SETUP GUIDE")
        self.log_message("="*60)
        for line in instructions.split('\n')[:25]:  # First 25 lines
            self.log_message(line)
        self.log_message("="*60)
        self.log_message("📖 Click 'Show Details' in dialog for full guide")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.path_input.text())
        if folder:
            self.path_input.setText(folder)
            self.log_message(f"📁 Save location: {folder}")

    def start_download(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Download in progress. Wait or cancel.")
            return

        # ========== CLEAN MODE DETECTION ==========
        url_input_text = self.url_input.toPlainText().strip()
        link_text_text = self.link_text.toPlainText().strip()

        # Determine mode based on which field has content
        raw_urls = None
        detected_mode = None

        if url_input_text:
            # SINGLE MODE: url_input has content
            raw_urls = url_input_text
            detected_mode = "single"
            self.bulk_mode_data = None  # Clear bulk mode data
            self.log_message("🔸 Detected: SINGLE MODE (using URL input field)")

        elif link_text_text and self.bulk_mode_data and self.bulk_mode_data.get('enabled'):
            # BULK MODE: link_text has content AND bulk_mode_data exists
            raw_urls = link_text_text
            detected_mode = "bulk"
            self.log_message("🔹 Detected: BULK MODE (using folder structure)")

        else:
            # No valid input
            QMessageBox.warning(
                self,
                "No Input",
                "Please either:\n\n"
                "🔸 Paste URLs in Single Mode field (top), OR\n"
                "🔹 Load folder structure for Bulk Mode (bottom)"
            )
            return

        # Extract URLs
        urls = extract_urls(raw_urls)
        if not urls:
            QMessageBox.warning(self, "Error", "No valid URLs found.")
            return

        self.log_message(f"📊 Found {len(urls)} valid URL(s)")

        # ========== SAVE PATH LOGIC ==========
        if detected_mode == "single":
            # SINGLE MODE: Force Desktop/Toseeq Downloads
            save_path = str(Path.home() / "Desktop" / "Toseeq Downloads")
            self.log_message(f"📁 Single Mode → Saving to: {save_path}")

        else:
            # BULK MODE: Use selected folder path
            save_path = self.path_input.text().strip()
            if not save_path:
                QMessageBox.warning(self, "Error", "Bulk mode requires save folder path.")
                return
            self.log_message(f"📁 Bulk Mode → Saving to: {save_path}")

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

    # ========== FOLDER MAPPING METHODS ==========

    def update_mapping_status_label(self):
        """Update the mapping status label with current statistics"""
        try:
            stats = self.mapping_manager.get_stats()
            active = stats.get('active_mappings', 0)
            total = stats.get('total_mappings', 0)

            if total == 0:
                self.mapping_status_label.setText("📊 No mappings configured")
                self.move_videos_btn.setEnabled(False)
            else:
                self.mapping_status_label.setText(f"📊 Mappings: {active}/{total} active")
                self.move_videos_btn.setEnabled(active > 0)
        except Exception as e:
            self.mapping_status_label.setText("📊 Mappings: Error")
            self.move_videos_btn.setEnabled(False)

    def open_folder_mapping_dialog(self):
        """Open the folder mapping configuration dialog"""
        try:
            dialog = FolderMappingDialog(self, self.mapping_manager)

            # Connect signal to update status when mappings change
            dialog.mappings_updated.connect(self.update_mapping_status_label)

            if dialog.exec_() == QDialog.Accepted:
                self.update_mapping_status_label()
                self.log_message("✅ Folder mappings saved successfully")
            else:
                # Even on cancel, reload to reflect any changes made before cancel
                self.mapping_manager.load()
                self.update_mapping_status_label()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open folder mapping dialog:\n{str(e)}"
            )
            self.log_message(f"❌ Error opening folder mapping dialog: {str(e)}")

    def move_videos_to_creator_data(self):
        """Move videos based on configured folder mappings"""
        try:
            # Check if there are active mappings
            active_mappings = self.mapping_manager.get_active_mappings()

            if not active_mappings:
                QMessageBox.warning(
                    self,
                    "No Active Mappings",
                    "No active folder mappings found.\n\n"
                    "Please configure folder mappings first using the 'Configure Folder Mapping' button."
                )
                return

            # Ask user for sort preference
            reply = QMessageBox.question(
                self,
                "Move Videos",
                f"Ready to move videos from {len(active_mappings)} active mapping(s).\n\n"
                "Sort videos by:",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Cancel:
                return

            # Yes = oldest first, No = newest first
            sort_by = "oldest" if reply == QMessageBox.Yes else "newest"

            # Show progress dialog
            progress_dialog = MoveProgressDialog(
                self,
                self.mapping_manager,
                sort_by=sort_by
            )

            self.log_message(f"🚀 Starting video move operation ({sort_by} first)...")

            if progress_dialog.exec_() == QDialog.Accepted:
                # Update status after move
                self.update_mapping_status_label()
                self.log_message("✅ Video move operation completed")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to move videos:\n{str(e)}"
            )
            self.log_message(f"❌ Error moving videos: {str(e)}")
