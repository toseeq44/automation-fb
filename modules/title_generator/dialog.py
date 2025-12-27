"""
Title Generator Main Dialog
User interface for video title generation
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFileDialog, QProgressBar,
                             QTextEdit, QCheckBox, QMessageBox, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from pathlib import Path
from modules.logging.logger import get_logger
from .api_manager import APIKeyManager
from .scanner import VideoScanner
from .generator import TitleGenerator
from .renamer import VideoRenamer

logger = get_logger(__name__)


class ProcessingThread(QThread):
    """Background thread for video processing"""

    progress_update = pyqtSignal(int, int, str)  # (current, total, message)
    processing_complete = pyqtSignal(dict)  # statistics

    def __init__(self, videos, generator, renamer):
        super().__init__()
        self.videos = videos
        self.generator = generator
        self.renamer = renamer
        self._stop_requested = False

    def run(self):
        """Process all videos"""
        total = len(self.videos)

        for index, video_info in enumerate(self.videos):
            if self._stop_requested:
                break

            # Update progress
            filename = video_info['filename']
            self.progress_update.emit(index + 1, total, f"Processing: {filename}")

            try:
                # Generate title
                new_title = self.generator.generate_title(video_info)

                # Rename file
                success, new_path, error = self.renamer.rename_video(
                    video_info['path'],
                    new_title
                )

                if success:
                    message = f"✅ {filename} → {Path(new_path).name}"
                else:
                    message = f"❌ {filename}: {error}"

                self.progress_update.emit(index + 1, total, message)

            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                self.progress_update.emit(
                    index + 1, total,
                    f"❌ {filename}: {str(e)}"
                )

        # Send completion signal with statistics
        stats = self.renamer.get_statistics()
        self.processing_complete.emit(stats)

    def stop(self):
        """Request stop"""
        self._stop_requested = True


class TitleGeneratorDialog(QDialog):
    """Main dialog for title generation"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_manager = APIKeyManager()
        self.scanner = VideoScanner()
        self.generator = TitleGenerator()
        self.renamer = VideoRenamer()

        self.videos = []
        self.processing_thread = None

        self.setup_ui()

    def setup_ui(self):
        """Setup UI components"""
        self.setWindowTitle("🪄 Title Generator")
        self.setMinimumSize(700, 600)
        self.setModal(True)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Title
        title = QLabel("AI-Powered Video Title Generator")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Folder selection group
        folder_group = QGroupBox("Folder Selection")
        folder_layout = QVBoxLayout()

        folder_select_layout = QHBoxLayout()
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setWordWrap(True)
        folder_select_layout.addWidget(self.folder_label)

        browse_btn = QPushButton("📁 Browse")
        browse_btn.clicked.connect(self.browse_folder)
        folder_select_layout.addWidget(browse_btn)

        folder_layout.addLayout(folder_select_layout)

        # Recursive option
        self.recursive_checkbox = QCheckBox("Scan nested folders (subfolders)")
        self.recursive_checkbox.setChecked(True)
        folder_layout.addWidget(self.recursive_checkbox)

        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # Video count label
        self.video_count_label = QLabel("Videos found: 0")
        layout.addWidget(self.video_count_label)

        # Progress section
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Log text area
        log_group = QGroupBox("Processing Log")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        self.start_btn = QPushButton("🚀 Start Processing")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def browse_folder(self):
        """Browse for folder"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder Containing Videos",
            str(Path.home())
        )

        if folder:
            self.folder_label.setText(folder)
            self.scan_videos(folder)

    def scan_videos(self, folder_path: str):
        """Scan folder for videos"""
        self.log_text.append(f"📂 Scanning: {folder_path}")

        recursive = self.recursive_checkbox.isChecked()
        self.videos = self.scanner.scan_folder(folder_path, recursive=recursive)

        # Update UI
        count = len(self.videos)
        self.video_count_label.setText(f"Videos found: {count}")

        if count > 0:
            self.start_btn.setEnabled(True)
            self.log_text.append(f"✅ Found {count} videos")

            # Show statistics
            stats = self.scanner.get_statistics()
            self.log_text.append(
                f"   Total size: {stats['total_size_mb']} MB\n"
                f"   Folders: {stats['folders']}"
            )
        else:
            self.start_btn.setEnabled(False)
            self.log_text.append("❌ No videos found")

    def start_processing(self):
        """Start title generation process"""
        if not self.videos:
            QMessageBox.warning(self, "No Videos", "Please select a folder with videos")
            return

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Confirm Processing",
            f"Generate titles for {len(self.videos)} videos?\n\n"
            "This will rename the files in-place.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Disable buttons during processing
        self.start_btn.setEnabled(False)
        self.close_btn.setEnabled(False)

        # Clear log
        self.log_text.clear()
        self.log_text.append("🚀 Starting title generation...\n")

        # Start processing thread
        self.processing_thread = ProcessingThread(
            self.videos,
            self.generator,
            self.renamer
        )
        self.processing_thread.progress_update.connect(self.on_progress_update)
        self.processing_thread.processing_complete.connect(self.on_processing_complete)
        self.processing_thread.start()

    def on_progress_update(self, current: int, total: int, message: str):
        """Handle progress update"""
        # Update progress bar
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)

        # Update status
        self.status_label.setText(f"Processing {current}/{total}")

        # Add to log
        self.log_text.append(message)

        # Scroll to bottom
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def on_processing_complete(self, stats: dict):
        """Handle processing completion"""
        # Update UI
        self.progress_bar.setValue(100)
        self.status_label.setText("✅ Processing complete!")

        # Show summary
        self.log_text.append(f"\n{'='*50}")
        self.log_text.append("Summary:")
        self.log_text.append(f"  Total videos: {stats['total']}")
        self.log_text.append(f"  ✅ Successful: {stats['successful']}")
        self.log_text.append(f"  ❌ Failed: {stats['failed']}")
        self.log_text.append(f"  Success rate: {stats['success_rate']}%")
        self.log_text.append(f"{'='*50}")

        # Re-enable buttons
        self.close_btn.setEnabled(True)

        # Show completion message
        QMessageBox.information(
            self,
            "Processing Complete",
            f"✅ Title generation complete!\n\n"
            f"Successful: {stats['successful']}/{stats['total']}\n"
            f"Failed: {stats['failed']}/{stats['total']}\n\n"
            f"Videos renamed based on content analysis."
        )

    def closeEvent(self, event):
        """Handle dialog close"""
        # Stop processing thread if running
        if self.processing_thread and self.processing_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Processing in Progress",
                "Processing is still running. Stop and close?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.processing_thread.stop()
                self.processing_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
