"""Combined workflow page for grabbing links and downloading videos."""
from datetime import datetime
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QSpinBox,
    QComboBox,
    QMessageBox,
    QProgressBar,
)

from modules.link_grabber.core import (
    BulkLinkGrabberThread,
    _create_creator_folder,
    _normalize_url,
)
from modules.video_downloader.core import VideoDownloaderThread


class CombinedWorkflowPage(QWidget):
    """Single click workflow that grabs links and downloads videos."""

    def __init__(self, go_back_callback=None, shared_links=None):
        super().__init__()
        self.go_back_callback = go_back_callback
        self.links = shared_links if shared_links is not None else []
        self.grabber_thread: Optional[BulkLinkGrabberThread] = None
        self.downloader_thread: Optional[VideoDownloaderThread] = None
        self.creator_queue: List[Dict[str, object]] = []
        self.current_download_index = -1
        self.total_downloads = 0
        self.completed_downloads = 0
        self.cancel_requested = False
        self.workflow_active = False
        self.selected_quality = "HD"
        self.download_errors: List[str] = []
        self._last_creator_data: Dict[str, dict] = {}
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(
            """
            QWidget {
                background-color: #23272A;
                color: #F5F6F5;
                font-family: Arial, sans-serif;
            }
            QTextEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #4B5057;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: 2px solid #1ABC9C;
            }
            QLabel {
                color: #F5F6F5;
            }
            """
        )

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("🚀 Link Grabber + Video Downloader")
        title.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #1ABC9C; margin-bottom: 5px;"
        )
        layout.addWidget(title)

        subtitle = QLabel(
            "Paste creator/profile URLs. Bot will grab links & download videos automatically."
        )
        subtitle.setStyleSheet("font-size: 14px; color: #F5F6F5; margin-bottom: 10px;")
        layout.addWidget(subtitle)

        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            "Enter one or more creator/profile URLs (comma or new line separated)"
        )
        self.url_input.setMinimumHeight(80)
        layout.addWidget(self.url_input)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(12)

        grab_label = QLabel("🔗 Links to grab:")
        grab_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        controls_row.addWidget(grab_label)

        self.grab_limit_spin = QSpinBox()
        self.grab_limit_spin.setRange(0, 500)
        self.grab_limit_spin.setValue(0)
        self.grab_limit_spin.setToolTip("0 = grab all available links")
        self.grab_limit_spin.setStyleSheet(
            "QSpinBox { background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;"
            " padding: 6px; border-radius: 6px; font-size: 14px; }"
        )
        controls_row.addWidget(self.grab_limit_spin)

        download_label = QLabel("📥 Videos to download:")
        download_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        controls_row.addWidget(download_label)

        self.download_limit_spin = QSpinBox()
        self.download_limit_spin.setRange(0, 500)
        self.download_limit_spin.setValue(0)
        self.download_limit_spin.setToolTip("0 = download all grabbed links")
        self.download_limit_spin.setStyleSheet(
            "QSpinBox { background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;"
            " padding: 6px; border-radius: 6px; font-size: 14px; }"
        )
        controls_row.addWidget(self.download_limit_spin)

        quality_label = QLabel("🎥 Quality:")
        quality_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        controls_row.addWidget(quality_label)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(
            [
                "Mobile (480p, small)",
                "HD (1080p)",
                "4K (max)",
                "Best Available",
                "Medium (720p)",
                "Low (360p)",
            ]
        )
        self.quality_combo.setCurrentIndex(1)
        self.quality_combo.setStyleSheet(
            "QComboBox { background-color: #2C2F33; color: #F5F6F5; border: 2px solid #4B5057;"
            " padding: 6px; border-radius: 6px; font-size: 14px; }"
            "QComboBox QAbstractItemView { background-color: #2C2F33; color: #F5F6F5;"
            " selection-background-color: #1ABC9C; }"
        )
        controls_row.addWidget(self.quality_combo)
        controls_row.addStretch()
        layout.addLayout(controls_row)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_style = (
            "QPushButton { background-color: #1ABC9C; color: #F5F6F5; border: none;"
            " padding: 10px 18px; border-radius: 8px; font-size: 15px; font-weight: bold; }"
            "QPushButton:hover { background-color: #16A085; }"
            "QPushButton:pressed { background-color: #128C7E; }"
            "QPushButton:disabled { background-color: #4B5057; color: #888; }"
        )

        self.back_btn = QPushButton("⬅ Back")
        self.start_btn = QPushButton("🚀 Start Bot")
        self.cancel_btn = QPushButton("❌ Cancel")

        for btn in (self.back_btn, self.start_btn, self.cancel_btn):
            btn.setStyleSheet(button_style)

        self.cancel_btn.setVisible(False)
        self.back_btn.setEnabled(bool(self.go_back_callback))

        self.back_btn.clicked.connect(self.handle_back)
        self.start_btn.clicked.connect(self.start_workflow)
        self.cancel_btn.clicked.connect(self.cancel_workflow)

        button_row.addWidget(self.back_btn)
        button_row.addWidget(self.start_btn)
        button_row.addWidget(self.cancel_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #2C2F33; border: 2px solid #4B5057; border-radius: 8px;"
            " text-align: center; color: #F5F6F5; height: 24px; }"
            "QProgressBar::chunk { background-color: #1ABC9C; border-radius: 8px; }"
        )
        layout.addWidget(self.progress_bar)

        info_row = QHBoxLayout()
        self.speed_label = QLabel("Speed: --")
        self.eta_label = QLabel("ETA: --")
        info_row.addWidget(self.speed_label)
        info_row.addWidget(self.eta_label)
        info_row.addStretch()
        layout.addLayout(info_row)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(240)
        layout.addWidget(self.log_area)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("font-size: 13px; color: #F5F6F5;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    # -----------------------------
    # UI helpers
    # -----------------------------
    def log_message(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        self.log_area.ensureCursorVisible()

    def handle_back(self):
        if self.workflow_active:
            QMessageBox.warning(
                self,
                "Busy",
                "Workflow is running. Cancel it before going back.",
            )
            return
        if self.go_back_callback:
            self.go_back_callback()

    def set_status(self, message: str, success: bool | None = None):
        color = "#F5F6F5"
        if success is True:
            color = "#1ABC9C"
        elif success is False:
            color = "#E74C3C"
        self.status_label.setStyleSheet(f"font-size: 13px; color: {color};")
        self.status_label.setText(message)

    # -----------------------------
    # Workflow control
    # -----------------------------
    def start_workflow(self):
        if self.workflow_active:
            QMessageBox.information(self, "Running", "Workflow already running.")
            return

        raw_urls = self.url_input.toPlainText().strip()
        if not raw_urls:
            QMessageBox.warning(self, "Input Required", "At least one URL is required.")
            return

        urls = [
            u.strip()
            for u in raw_urls.replace(",", "\n").splitlines()
            if u.strip().startswith(("http://", "https://"))
        ]
        if not urls:
            QMessageBox.warning(self, "Invalid", "Please enter valid http/https URLs.")
            return

        self.cancel_requested = False
        self.workflow_active = True
        self.download_errors.clear()
        self._last_creator_data = {}
        self.progress_bar.setValue(0)
        self.speed_label.setText("Speed: --")
        self.eta_label.setText("ETA: --")
        self.log_area.clear()

        self.start_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.back_btn.setEnabled(False)

        grab_limit = self.grab_limit_spin.value()
        download_limit = self.download_limit_spin.value()
        self.selected_quality = self.quality_combo.currentText()

        self.log_message(
            f"🚀 Starting bot | URLs: {len(urls)} | Grab limit: {grab_limit or 'ALL'} | "
            f"Download limit: {download_limit or 'ALL'}"
        )
        self.set_status("Grabbing links...", None)

        options = {"max_videos": grab_limit if grab_limit > 0 else 0}

        self.grabber_thread = BulkLinkGrabberThread(urls, options)
        self.grabber_thread.progress.connect(
            lambda msg: self.log_message(f"[Grabber] {msg}")
        )
        self.grabber_thread.progress_percent.connect(self.progress_bar.setValue)
        self.grabber_thread.finished.connect(self.on_grabber_finished)
        self.grabber_thread.start()

    def cancel_workflow(self):
        self.cancel_requested = True
        if self.grabber_thread and self.grabber_thread.isRunning():
            self.grabber_thread.cancel()
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.cancel()
        self.log_message("⚠️ Cancel requested. Waiting for safe stop...")
        self.set_status("Cancelling...", None)

    def on_grabber_finished(self, success: bool, message: str, links: List[dict]):
        thread = self.grabber_thread
        if thread and hasattr(thread, "creator_data"):
            self._last_creator_data = getattr(thread, "creator_data", {})
        self.grabber_thread = None
        self.log_message(f"[Grabber] {message}")
        if not success or not links:
            if success and not links:
                self.set_status("No links found.", False)
            else:
                self.set_status("Link grabber failed.", False)
            self.finish_workflow(False)
            return
        if self.cancel_requested:
            self.set_status("Cancelled after grabbing.", False)
            self.finish_workflow(False)
            return

        self.log_message(f"[Grabber] Total links fetched: {len(links)}")
        self.update_shared_links(links)

        self.prepare_download_queue()

    def update_shared_links(self, new_links: List[dict]):
        if self.links is None:
            return
        existing = set()
        for link in self.links:
            if isinstance(link, dict):
                url = link.get("url", "")
            else:
                url = str(link)
            existing.add(_normalize_url(url))
        for item in new_links:
            url = item.get("url")
            if not url:
                continue
            normalized = _normalize_url(url)
            if normalized not in existing:
                self.links.append({"url": url})
                existing.add(normalized)

    def prepare_download_queue(self):
        if self.cancel_requested:
            self.set_status("Cancelled before download.", False)
            self.finish_workflow(False)
            return

        creator_data = self._last_creator_data or {}

        if not creator_data:
            self.set_status("No creator data available.", False)
            self.finish_workflow(False)
            return

        self._last_creator_data = creator_data

        download_limit = self.download_limit_spin.value()
        remaining = download_limit if download_limit > 0 else None

        self.creator_queue = []
        total_selected = 0

        for creator, data in creator_data.items():
            links = data.get("links", [])
            selected_urls: List[str] = []
            for entry in links:
                if remaining is not None and remaining <= 0:
                    break
                url = entry.get("url") if isinstance(entry, dict) else None
                if not url:
                    continue
                selected_urls.append(url)
                total_selected += 1
                if remaining is not None:
                    remaining -= 1
            if selected_urls:
                folder_path = _create_creator_folder(creator)
                self.creator_queue.append(
                    {
                        "creator": creator,
                        "folder": str(folder_path),
                        "urls": selected_urls,
                    }
                )
            if remaining is not None and remaining <= 0:
                break

        self.total_downloads = total_selected
        self.completed_downloads = 0

        if not self.creator_queue or self.total_downloads == 0:
            self.set_status("No videos selected for download.", False)
            self.finish_workflow(False)
            return

        self.log_message(
            f"[Bot] Prepared {self.total_downloads} download(s) across {len(self.creator_queue)} creator(s)."
        )
        self.set_status("Downloading videos...", None)
        self.start_next_download()

    def start_next_download(self):
        if self.cancel_requested:
            self.set_status("Cancelled by user.", False)
            self.finish_workflow(False)
            return

        self.current_download_index += 1
        if self.current_download_index >= len(self.creator_queue):
            self.finish_workflow(True)
            return

        entry = self.creator_queue[self.current_download_index]
        creator = entry["creator"]
        urls = entry["urls"]
        folder = entry["folder"]

        self.log_message(
            f"[Download] 🎯 @{creator} | Videos: {len(urls)} | Folder: {folder}"
        )

        options = {
            "quality": self.selected_quality,
            "bitrate": None,
            "max_retries": 3,
            "playlist": False,
            "subtitles": False,
            "thumbnail": False,
        }

        self.downloader_thread = VideoDownloaderThread(urls, folder, options)
        self.downloader_thread.progress.connect(
            lambda msg: self.log_message(f"[Download] {msg}")
        )
        self.downloader_thread.progress_percent.connect(self.progress_bar.setValue)
        self.downloader_thread.download_speed.connect(
            lambda s: self.speed_label.setText(f"Speed: {s}")
        )
        self.downloader_thread.eta.connect(
            lambda e: self.eta_label.setText(f"ETA: {e}")
        )
        self.downloader_thread.video_complete.connect(self.on_video_complete)
        self.downloader_thread.finished.connect(self.on_download_finished)
        self.downloader_thread.start()

    def on_video_complete(self, file_path: str):
        self.completed_downloads += 1
        self.log_message(f"[Download] ✅ Saved: {file_path}")
        if self.total_downloads:
            percent = int((self.completed_downloads / self.total_downloads) * 100)
            if percent > self.progress_bar.value():
                self.progress_bar.setValue(percent)

    def on_download_finished(self, success: bool, message: str):
        if not success:
            self.download_errors.append(message)
        self.log_message(f"[Download] {message}")
        self.downloader_thread = None
        if self.cancel_requested:
            self.set_status("Cancelled by user.", False)
            self.finish_workflow(False)
            return
        self.start_next_download()

    def finish_workflow(self, success: bool):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.wait(100)
        self.workflow_active = False
        self.cancel_requested = False
        self.current_download_index = -1
        self.creator_queue = []

        self.start_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.back_btn.setEnabled(True)

        if success:
            summary = (
                f"Completed {self.completed_downloads} downloads."
                if self.completed_downloads
                else "Links grabbed only."
            )
            self.set_status(summary, True)
            self.log_message(f"[Bot] ✅ {summary}")
            self.progress_bar.setValue(100)
        else:
            error_msg = (
                self.download_errors[-1]
                if self.download_errors
                else "Workflow stopped."
            )
            self.set_status(error_msg, False)
            self.log_message(f"[Bot] ❌ {error_msg}")

        self.speed_label.setText("Speed: --")
        self.eta_label.setText("ETA: --")

