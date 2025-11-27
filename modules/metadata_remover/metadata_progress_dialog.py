"""
modules/metadata_remover/metadata_progress_dialog.py
Metadata Progress Dialog - Shows real-time progress during batch metadata removal
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QTextEdit, QFrame, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QTextCursor

from modules.logging.logger import get_logger
from modules.metadata_remover.metadata_processor import MetadataBatchWorker, MetadataBatchProcessor

logger = get_logger(__name__)


class MetadataProgressDialog(QDialog):
    """
    Progress dialog for batch metadata removal
    Shows real-time progress, logs, and statistics
    """

    def __init__(self, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config = config
        self.worker: Optional[MetadataBatchWorker] = None
        self.batch_processor = MetadataBatchProcessor()

        self.start_time = None
        self.is_processing = False
        self.is_in_place = config.get('mapping', {}).same_as_source if config.get('mapping') else False

        self.init_ui()
        self.apply_theme()

        # Start processing after dialog shows
        QTimer.singleShot(500, self.start_processing)

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Metadata Removal Progress")
        self.setMinimumSize(800, 650)
        self.resize(900, 700)
        self.setModal(True)

        # Prevent closing during processing
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        header = self.create_header()
        main_layout.addWidget(header)

        # Progress section
        progress_group = self.create_progress_group()
        main_layout.addWidget(progress_group)

        # Statistics
        stats_group = self.create_stats_group()
        main_layout.addWidget(stats_group)

        # Log output
        log_group = self.create_log_group()
        main_layout.addWidget(log_group, 1)

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        button_layout.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        button_layout.addWidget(self.cancel_btn)

        button_layout.addStretch()

        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        button_layout.addWidget(self.open_folder_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def create_header(self) -> QFrame:
        """Create header section"""
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)

        # Title
        title_text = "Removing Metadata (In-Place)" if self.is_in_place else "Removing Metadata"
        title = QLabel(title_text)
        title.setFont(QFont('Segoe UI', 16, QFont.Bold))
        layout.addWidget(title)

        layout.addStretch()

        # Timer
        self.timer_label = QLabel("Elapsed: 00:00:00")
        self.timer_label.setObjectName("timer_label")
        layout.addWidget(self.timer_label)

        # Setup timer for elapsed time
        self.elapsed_timer = QTimer()
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)

        return header

    def create_progress_group(self) -> QGroupBox:
        """Create progress section"""
        group = QGroupBox("Progress")
        layout = QVBoxLayout()

        # Main progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% (%v/%m)")
        layout.addWidget(self.progress_bar)

        # Current file label
        self.current_file_label = QLabel("Preparing...")
        self.current_file_label.setWordWrap(True)
        layout.addWidget(self.current_file_label)

        # Estimated time
        self.eta_label = QLabel("Estimated time remaining: Calculating...")
        layout.addWidget(self.eta_label)

        group.setLayout(layout)
        return group

    def create_stats_group(self) -> QGroupBox:
        """Create statistics section"""
        group = QGroupBox("Statistics")
        layout = QHBoxLayout()

        # Completed
        completed_frame = self.create_stat_frame("Completed", "0", "completed")
        layout.addWidget(completed_frame)

        # Pending
        pending_frame = self.create_stat_frame("Pending", "0", "pending")
        layout.addWidget(pending_frame)

        # Failed
        failed_frame = self.create_stat_frame("Failed", "0", "failed")
        layout.addWidget(failed_frame)

        # Replaced (for in-place mode)
        if self.is_in_place:
            replaced_frame = self.create_stat_frame("Replaced", "0", "replaced")
            layout.addWidget(replaced_frame)

        group.setLayout(layout)
        return group

    def create_stat_frame(self, label: str, value: str, name: str) -> QFrame:
        """Create a single stat frame"""
        frame = QFrame()
        frame.setObjectName(f"stat_{name}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)

        value_label = QLabel(value)
        value_label.setObjectName(f"stat_value_{name}")
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setFont(QFont('Segoe UI', 24, QFont.Bold))
        layout.addWidget(value_label)

        text_label = QLabel(label)
        text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(text_label)

        return frame

    def create_log_group(self) -> QGroupBox:
        """Create log output section"""
        group = QGroupBox("Processing Log")
        layout = QVBoxLayout()

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont('Consolas', 10))
        self.log_output.setMinimumHeight(200)
        layout.addWidget(self.log_output)

        group.setLayout(layout)
        return group

    def apply_theme(self):
        """Apply dark theme"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #e0e0e0;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
                background-color: #242424;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                color: #9c27b0;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                text-align: center;
                background-color: #2a2a2a;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #9c27b0;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353535;
            }
            QPushButton:pressed {
                background-color: #202020;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #666666;
            }
            QTextEdit {
                background-color: #0f0f0f;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 10px;
            }
            QFrame#header {
                background-color: #0f0f0f;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel#timer_label {
                color: #9c27b0;
                font-weight: bold;
                font-size: 14px;
            }
            QFrame[objectName^="stat_"] {
                background-color: #2a2a2a;
                border-radius: 8px;
            }
            QLabel[objectName="stat_value_completed"] {
                color: #4caf50;
            }
            QLabel[objectName="stat_value_pending"] {
                color: #ff9800;
            }
            QLabel[objectName="stat_value_failed"] {
                color: #f44336;
            }
            QLabel[objectName="stat_value_replaced"] {
                color: #9c27b0;
            }
        """)

    def start_processing(self):
        """Start the batch processing"""
        self.is_processing = True
        self.start_time = datetime.now()
        self.elapsed_timer.start(1000)

        total = self.config.get('total_count', 0)
        self.progress_bar.setMaximum(total)

        # Log start
        mode_str = "in-place replacement" if self.is_in_place else "to destination"
        self.log_message(f"Starting metadata removal ({mode_str}) for {total} videos", "info")

        # Create and connect worker
        self.worker = self.batch_processor.start_processing(self.config)

        # Connect signals
        self.worker.progress.connect(self.on_progress)
        self.worker.video_started.connect(self.on_video_started)
        self.worker.video_completed.connect(self.on_video_completed)
        self.worker.log_message.connect(self.log_message)
        self.worker.processing_finished.connect(self.on_processing_finished)

    def on_progress(self, current: int, total: int):
        """Handle progress update"""
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"%p% ({current}/{total})")

        # Update pending count
        pending = total - current
        self.update_stat("pending", str(pending))

        # Calculate ETA
        if current > 0 and self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            avg_time = elapsed / current
            remaining = (total - current) * avg_time

            if remaining < 60:
                eta_text = f"{int(remaining)} seconds"
            elif remaining < 3600:
                eta_text = f"{int(remaining / 60)} minutes"
            else:
                eta_text = f"{remaining / 3600:.1f} hours"

            self.eta_label.setText(f"Estimated time remaining: {eta_text}")

    def on_video_started(self, video_path: str, current: int, total: int):
        """Handle video started"""
        filename = os.path.basename(video_path)
        self.current_file_label.setText(f"Processing: {filename}")

    def on_video_completed(self, result: dict):
        """Handle video completed"""
        status = result.get('status', 'unknown')

        # Update stats
        if status == 'success':
            completed = int(self.get_stat_value("completed") or "0") + 1
            self.update_stat("completed", str(completed))

            if result.get('in_place') and self.is_in_place:
                replaced = int(self.get_stat_value("replaced") or "0") + 1
                self.update_stat("replaced", str(replaced))

        elif status == 'failed':
            failed = int(self.get_stat_value("failed") or "0") + 1
            self.update_stat("failed", str(failed))

    def on_processing_finished(self, summary: dict):
        """Handle processing finished"""
        self.is_processing = False
        self.elapsed_timer.stop()

        # Update UI
        self.current_file_label.setText("Processing complete!")
        self.eta_label.setText("")
        self.progress_bar.setValue(self.progress_bar.maximum())

        # Update buttons
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(True)

        # Allow closing
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)
        self.show()

        # Log summary
        self.log_message("=" * 50, "info")
        self.log_message("METADATA REMOVAL COMPLETE", "success")
        self.log_message(f"Total: {summary['total']}", "info")
        self.log_message(f"Successful: {summary['successful']}", "success")
        self.log_message(f"Failed: {summary['failed']}", "error" if summary['failed'] > 0 else "info")
        if summary.get('in_place_replaced', 0) > 0:
            self.log_message(f"Replaced in-place: {summary['in_place_replaced']}", "info")
        if summary['cancelled'] > 0:
            self.log_message(f"Cancelled: {summary['cancelled']}", "warning")
        self.log_message(f"Total time: {summary['total_time']:.1f}s", "info")
        self.log_message("=" * 50, "info")

        # Show completion message
        if summary['was_cancelled']:
            QMessageBox.information(
                self, "Processing Cancelled",
                f"Processing was cancelled.\n\n"
                f"Completed: {summary['successful']}\n"
                f"Cancelled: {summary['cancelled']}"
            )
        elif summary['failed'] > 0:
            QMessageBox.warning(
                self, "Processing Complete",
                f"Processing complete with errors.\n\n"
                f"Successful: {summary['successful']}\n"
                f"Failed: {summary['failed']}"
            )
        else:
            msg = f"All videos processed successfully!\n\nTotal: {summary['successful']} videos"
            if self.is_in_place:
                msg += f"\nReplaced in-place: {summary.get('in_place_replaced', summary['successful'])}"
            QMessageBox.information(
                self, "Processing Complete",
                msg
            )

    def log_message(self, message: str, level: str = "info"):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Color based on level
        colors = {
            "info": "#e0e0e0",
            "success": "#4caf50",
            "warning": "#ff9800",
            "error": "#f44336"
        }
        color = colors.get(level, "#e0e0e0")

        # Format message
        html = f'<span style="color: #666666;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'

        self.log_output.append(html)

        # Auto-scroll to bottom
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_output.setTextCursor(cursor)

    def update_stat(self, name: str, value: str):
        """Update a stat value"""
        label = self.findChild(QLabel, f"stat_value_{name}")
        if label:
            label.setText(value)

    def get_stat_value(self, name: str) -> str:
        """Get a stat value"""
        label = self.findChild(QLabel, f"stat_value_{name}")
        return label.text() if label else "0"

    def update_elapsed_time(self):
        """Update elapsed time display"""
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.timer_label.setText(f"Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def toggle_pause(self):
        """Toggle pause/resume"""
        if self.batch_processor.is_running():
            if self.pause_btn.text() == "Pause":
                self.batch_processor.pause()
                self.pause_btn.setText("Resume")
                self.current_file_label.setText("Processing paused...")
            else:
                self.batch_processor.resume()
                self.pause_btn.setText("Pause")

    def cancel_processing(self):
        """Cancel processing"""
        reply = QMessageBox.question(
            self, "Cancel Processing",
            "Are you sure you want to cancel?\n"
            "Videos already processed will be kept.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.batch_processor.cancel()
            self.cancel_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)

    def open_output_folder(self):
        """Open output folder in file manager"""
        if self.config.get('mapping'):
            mapping = self.config['mapping']
            # Use source folder for in-place, destination for different folders
            folder = mapping.source_folder if mapping.same_as_source else mapping.destination_folder

            if os.path.exists(folder):
                import subprocess
                import sys

                if sys.platform == 'win32':
                    os.startfile(folder)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', folder])
                else:
                    subprocess.run(['xdg-open', folder])

    def closeEvent(self, event):
        """Handle close event"""
        if self.is_processing:
            reply = QMessageBox.question(
                self, "Processing in Progress",
                "Processing is still in progress.\n"
                "Do you want to cancel and close?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.batch_processor.cancel()
                self.batch_processor.wait_for_completion(5000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
