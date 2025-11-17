"""
Move Progress Dialog
Shows progress and logs when moving videos based on folder mappings
"""

from pathlib import Path
from typing import List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QGroupBox, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor

from .video_mover import VideoMover, MappingMoveResult, MoveResult
from .folder_mapping_manager import FolderMappingManager


class MoveWorkerThread(QThread):
    """Worker thread for moving videos"""

    progress = pyqtSignal(int, int)  # current, total
    log_message = pyqtSignal(str, str)  # message, level (info/success/warning/error)
    mapping_processed = pyqtSignal(object)  # MappingMoveResult
    finished = pyqtSignal(list)  # List of all MappingMoveResult

    def __init__(self, mapping_manager: FolderMappingManager, sort_by: str = "oldest"):
        super().__init__()
        self.mapping_manager = mapping_manager
        self.sort_by = sort_by
        self.is_cancelled = False

    def run(self):
        """Run the move operation"""
        try:
            video_mover = VideoMover(self.mapping_manager)
            active_mappings = self.mapping_manager.get_active_mappings()

            self.log_message.emit(
                f"Starting move operation for {len(active_mappings)} active mapping(s)...",
                "info"
            )

            results = []
            total = len(active_mappings)

            for i, mapping in enumerate(active_mappings):
                if self.is_cancelled:
                    self.log_message.emit("Operation cancelled by user.", "warning")
                    break

                self.progress.emit(i, total)
                self.log_message.emit(f"\n{'='*60}", "info")
                self.log_message.emit(
                    f"Processing mapping {i+1}/{total}:",
                    "info"
                )
                self.log_message.emit(f"  Source: {mapping.source_folder}", "info")
                self.log_message.emit(f"  Destination: {mapping.destination_folder}", "info")

                # Process the mapping
                result = video_mover.process_mapping(mapping, sort_by=self.sort_by)
                results.append(result)

                # Log the result
                self.log_result(result)
                self.mapping_processed.emit(result)

            self.progress.emit(total, total)

            # Summary
            self.log_message.emit(f"\n{'='*60}", "info")
            self.log_message.emit("SUMMARY", "info")
            self.log_message.emit(f"{'='*60}", "info")

            summary = video_mover.get_move_summary(results)
            self.log_message.emit(f"Total mappings processed: {summary['mappings_processed']}", "info")
            self.log_message.emit(f"Mappings successful: {summary['mappings_successful']}", "success")
            self.log_message.emit(f"Mappings skipped: {summary['mappings_skipped']}", "warning")
            self.log_message.emit(f"Mappings failed: {summary['mappings_failed']}", "error")
            self.log_message.emit(f"\nTotal videos moved: {summary['total_videos_moved']}", "success")
            self.log_message.emit(f"Total videos failed: {summary['total_videos_failed']}", "error")

            if summary['total_videos_moved'] > 0:
                self.log_message.emit(f"\n✅ Move operation completed successfully!", "success")
            else:
                self.log_message.emit(f"\n⚠️ No videos were moved.", "warning")

            self.finished.emit(results)

        except Exception as e:
            self.log_message.emit(f"\n❌ Error during move operation: {str(e)}", "error")
            self.finished.emit([])

    def log_result(self, result: MappingMoveResult):
        """Log the result of a mapping move operation"""
        if result.status == MoveResult.SUCCESS or result.videos_moved > 0:
            self.log_message.emit(f"  ✅ {result.message}", "success")
            if result.operations:
                for op in result.operations:
                    if op.result == MoveResult.SUCCESS:
                        file_name = Path(op.source_file).name
                        self.log_message.emit(f"    • Moved: {file_name}", "success")
                    elif op.result == MoveResult.ERROR:
                        self.log_message.emit(f"    • Failed: {op.error_message}", "error")

        elif result.status == MoveResult.SKIPPED_LIMIT_REACHED:
            self.log_message.emit(f"  ⏭️ {result.message}", "warning")

        elif result.status == MoveResult.SKIPPED_NOT_EMPTY:
            self.log_message.emit(f"  ⏭️ {result.message}", "warning")

        elif result.status == MoveResult.SKIPPED_NO_VIDEOS:
            self.log_message.emit(f"  ℹ️ {result.message}", "info")

        elif result.status == MoveResult.SKIPPED_DISABLED:
            self.log_message.emit(f"  ⏭️ {result.message}", "warning")

        elif result.status == MoveResult.ERROR:
            self.log_message.emit(f"  ❌ {result.message}", "error")

        else:
            self.log_message.emit(f"  ℹ️ {result.message}", "info")

    def cancel(self):
        """Cancel the operation"""
        self.is_cancelled = True


class MoveProgressDialog(QDialog):
    """Dialog showing progress of video move operations"""

    def __init__(self, parent=None, mapping_manager: FolderMappingManager = None, sort_by: str = "oldest"):
        super().__init__(parent)
        self.mapping_manager = mapping_manager or FolderMappingManager()
        self.sort_by = sort_by
        self.worker_thread = None
        self.is_complete = False

        self.setWindowTitle("Moving Videos - Progress")
        self.setMinimumSize(800, 600)
        self.setModal(True)

        # Style
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
            }
            QProgressBar {
                border: 2px solid #00d4ff;
                border-radius: 5px;
                background-color: #16213e;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #00d4ff;
                border-radius: 3px;
            }
            QTextEdit {
                background-color: #0a0a0a;
                color: #ffffff;
                border: 2px solid #00d4ff;
                border-radius: 5px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                padding: 5px;
            }
            QPushButton {
                background-color: #00d4ff;
                color: #000000;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #00a8cc;
            }
            QPushButton:pressed {
                background-color: #0088aa;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
            QPushButton#cancelBtn {
                background-color: #e74c3c;
            }
            QPushButton#cancelBtn:hover {
                background-color: #c0392b;
            }
            QGroupBox {
                border: 2px solid #00d4ff;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #00d4ff;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        self.init_ui()
        self.start_move_operation()

    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Header
        header_label = QLabel("Moving Videos")
        header_label.setFont(QFont("Arial", 16, QFont.Bold))
        header_label.setStyleSheet("color: #00d4ff; padding: 10px;")
        layout.addWidget(header_label)

        # Progress bar
        progress_layout = QVBoxLayout()
        self.status_label = QLabel("Initializing...")
        progress_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        layout.addLayout(progress_layout)

        # Log area
        log_group = QGroupBox("Operation Log")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Statistics
        stats_group = self.create_stats_group()
        layout.addWidget(stats_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("⏸️ Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.cancel_operation)
        button_layout.addWidget(self.cancel_btn)

        self.close_btn = QPushButton("✅ Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setEnabled(False)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_stats_group(self) -> QGroupBox:
        """Create statistics group box"""
        stats_group = QGroupBox("Statistics")
        stats_layout = QHBoxLayout()

        self.processed_label = QLabel("Processed: 0")
        self.moved_label = QLabel("Moved: 0")
        self.skipped_label = QLabel("Skipped: 0")
        self.failed_label = QLabel("Failed: 0")

        for label in [self.processed_label, self.moved_label, self.skipped_label, self.failed_label]:
            label.setStyleSheet("color: #ffffff; font-size: 11px;")
            stats_layout.addWidget(label)

        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)

        return stats_group

    def start_move_operation(self):
        """Start the move operation in a separate thread"""
        self.worker_thread = MoveWorkerThread(self.mapping_manager, self.sort_by)
        self.worker_thread.progress.connect(self.on_progress)
        self.worker_thread.log_message.connect(self.add_log_message)
        self.worker_thread.mapping_processed.connect(self.on_mapping_processed)
        self.worker_thread.finished.connect(self.on_operation_finished)
        self.worker_thread.start()

    def on_progress(self, current: int, total: int):
        """Update progress bar"""
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
            self.status_label.setText(f"Processing mapping {current}/{total}...")
        else:
            self.progress_bar.setValue(0)

    def add_log_message(self, message: str, level: str = "info"):
        """Add a message to the log"""
        # Color based on level
        color_map = {
            "info": "#ffffff",
            "success": "#00ff00",
            "warning": "#ffaa00",
            "error": "#ff0000"
        }

        color = color_map.get(level, "#ffffff")
        formatted_message = f'<span style="color: {color};">{message}</span>'

        self.log_text.append(formatted_message)

        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def on_mapping_processed(self, result: MappingMoveResult):
        """Update statistics when a mapping is processed"""
        # This is handled by the log_result in worker thread
        pass

    def on_operation_finished(self, results: List[MappingMoveResult]):
        """Handle operation completion"""
        self.is_complete = True
        self.status_label.setText("Operation completed!")
        self.progress_bar.setValue(100)

        # Update final statistics
        total_processed = len(results)
        total_moved = sum(r.videos_moved for r in results)
        total_skipped = sum(r.videos_skipped for r in results)
        total_failed = sum(r.videos_failed for r in results)

        self.processed_label.setText(f"Processed: {total_processed}")
        self.moved_label.setText(f"Moved: {total_moved}")
        self.skipped_label.setText(f"Skipped: {total_skipped}")
        self.failed_label.setText(f"Failed: {total_failed}")

        # Enable close button
        self.close_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def cancel_operation(self):
        """Cancel the ongoing operation"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.add_log_message("\nCancelling operation...", "warning")
            self.worker_thread.cancel()
            self.worker_thread.wait()  # Wait for thread to finish
            self.status_label.setText("Operation cancelled")
            self.close_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.worker_thread and self.worker_thread.isRunning() and not self.is_complete:
            self.cancel_operation()
        event.accept()
