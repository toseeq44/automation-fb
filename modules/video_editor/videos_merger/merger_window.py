"""
modules/video_editor/videos_merger/merger_window.py
Main video merger window with tabs for simple and bulk merging
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QSplitter
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from .simple_merge_tab import SimpleMergeTab
from .bulk_folder_tab import BulkFolderTab
from .progress_widget import ProgressWidget
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class VideoMergerWindow(QDialog):
    """Main video merger window"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_processor = None

        self.init_ui()
        self.setWindowTitle("🎬 Video Merger")
        self.resize(1200, 900)

    def init_ui(self):
        """Initialize UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("🎬 Video Merger")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Help button
        help_btn = QPushButton("❓ Help")
        help_btn.clicked.connect(self.show_help)
        header_layout.addWidget(help_btn)

        main_layout.addLayout(header_layout)

        # Splitter for tabs and progress
        splitter = QSplitter(Qt.Vertical)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Arial", 10))

        # Tab 1: Simple Merge
        self.simple_tab = SimpleMergeTab()
        self.simple_tab.merge_started.connect(self._on_merge_started)
        self.simple_tab.merge_completed.connect(self._on_merge_completed)
        self.tabs.addTab(self.simple_tab, "📹 Simple Merge")

        # Tab 2: Bulk Folder Merge
        self.bulk_tab = BulkFolderTab()
        self.bulk_tab.merge_started.connect(self._on_merge_started)
        self.bulk_tab.merge_completed.connect(self._on_merge_completed)
        self.tabs.addTab(self.bulk_tab, "📁 Bulk Folder Merge")

        splitter.addWidget(self.tabs)

        # Progress widget
        self.progress_widget = ProgressWidget()
        self.progress_widget.pause_clicked.connect(self._on_pause)
        self.progress_widget.resume_clicked.connect(self._on_resume)
        self.progress_widget.cancel_clicked.connect(self._on_cancel)

        splitter.addWidget(self.progress_widget)

        # Set splitter sizes (70% tabs, 30% progress)
        splitter.setSizes([700, 300])

        main_layout.addWidget(splitter, 1)

        # Bottom buttons
        button_layout = QHBoxLayout()

        reset_btn = QPushButton("🔄 Reset")
        reset_btn.clicked.connect(self.reset_all)
        button_layout.addWidget(reset_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # Apply stylesheet
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #ccc;
                background-color: white;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #d0e0f0;
            }
        """)

    def _on_merge_started(self, processor):
        """Handle merge started"""
        self.current_processor = processor

        # Connect processor signals to progress widget
        processor.progress_updated.connect(self.progress_widget.update_progress)
        processor.batch_progress_updated.connect(self.progress_widget.update_batch_progress)
        processor.log_message.connect(self.progress_widget.log)

        # Start progress widget
        self.progress_widget.start_processing()
        self.progress_widget.reset()

        logger.info("Merge started")

    def _on_merge_completed(self, success: bool, results: dict):
        """Handle merge completed"""
        self.progress_widget.stop_processing()

        if success:
            output_files = results.get('output_files', [results.get('output_path')])
            self.progress_widget.set_completed(output_files)
        elif results.get('cancelled'):
            self.progress_widget.set_cancelled()
        else:
            error = results.get('error', 'Unknown error')
            self.progress_widget.set_failed(error)

        self.current_processor = None
        logger.info(f"Merge completed: success={success}")

    def _on_pause(self):
        """Pause processing"""
        if self.current_processor:
            self.current_processor.pause()
            self.progress_widget.set_paused(True)
            logger.info("Merge paused")

    def _on_resume(self):
        """Resume processing"""
        if self.current_processor:
            self.current_processor.resume()
            self.progress_widget.set_paused(False)
            logger.info("Merge resumed")

    def _on_cancel(self):
        """Cancel processing"""
        if self.current_processor:
            self.current_processor.cancel()
            logger.info("Merge cancelled")

    def reset_all(self):
        """Reset all tabs"""
        self.simple_tab.reset()
        self.progress_widget.reset()
        logger.info("Reset all")

    def show_help(self):
        """Show help dialog"""
        from PyQt5.QtWidgets import QMessageBox

        help_text = """
🎬 Video Merger - Help

📹 SIMPLE MERGE:
• Add 2 or more videos to merge them into one
• Use bulk trim to cut start/end from all videos
• Apply crop, zoom, flip to all videos
• Choose transitions between clips
• Select output quality and format

📁 BULK FOLDER MERGE:
• Add 2 or more folders containing videos
• Videos are merged round-robin style:
  - One video from each folder per batch
  - Creates multiple merged videos
  - Skips batches with only 1 video
• All settings apply to every merge

⏸️ PAUSE/RESUME:
• Click Pause to temporarily stop processing
• Click Resume to continue from where you left off

🗑️ AUTO-DELETE:
• Enable to automatically delete source videos
  after successful merge
• Use with caution!

📊 PREVIEW BATCHES:
• (Bulk mode only) Preview how videos will be batched
  before starting the merge
        """

        QMessageBox.information(self, "Help", help_text)

    def closeEvent(self, event):
        """Handle window close"""
        # Check if processing
        if self.current_processor and self.current_processor.is_running():
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "Processing in Progress",
                "Merging is in progress. Are you sure you want to close?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.No:
                event.ignore()
                return
            else:
                # Cancel processing
                self.current_processor.cancel()

        event.accept()
