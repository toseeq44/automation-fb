"""
Move Progress Dialog
Shows progress and logs when moving videos based on folder mappings
Enhanced Professional Version with Beautiful UI
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

        self.setWindowTitle("🚀 Moving Videos - Progress")

        # Add window controls (minimize, maximize, close buttons)
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinMaxButtonsHint |
            Qt.WindowCloseButtonHint
        )

        # Responsive sizing
        self.resize(950, 700)  # Default size
        self.setMinimumSize(700, 500)  # Minimum size for usability

        # Make dialog resizable
        self.setSizeGripEnabled(True)
        self.setModal(True)

        # Enhanced Professional Style
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QLabel#headerLabel {
                color: #00d4ff;
                font-size: 20px;
                font-weight: bold;
                padding: 15px;
            }
            QLabel#statusLabel {
                color: #00ff88;
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
            }
            QProgressBar {
                border: none;
                border-radius: 10px;
                background-color: #1e1e2e;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                min-height: 25px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00d4ff, stop:0.5 #00ff88, stop:1 #ffd700);
                border-radius: 10px;
            }
            QTextEdit {
                background-color: #0f0f1e;
                color: #e0e0e0;
                border: 2px solid #3a3a4a;
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', 'Monaco', monospace;
                font-size: 12px;
                padding: 10px;
                line-height: 1.4;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00d4ff, stop:1 #00a8cc);
                color: #000000;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 13px;
                min-height: 36px;
                min-width: 120px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00f0ff, stop:1 #00c8ee);
            }
            QPushButton:pressed {
                background: #0088aa;
            }
            QPushButton:disabled {
                background: #3a3a4a;
                color: #707070;
            }
            QPushButton#cancelBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e74c3c, stop:1 #c0392b);
                color: white;
            }
            QPushButton#cancelBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff5c4c, stop:1 #d0493b);
            }
            QGroupBox {
                border: 2px solid #3a3a4a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 18px;
                background-color: rgba(30, 30, 46, 0.5);
                font-weight: bold;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #00d4ff;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #1e1e2e;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #00d4ff;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #00f0ff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.init_ui()
        self.start_move_operation()

    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout()
        layout.setSpacing(18)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_label = QLabel("🚀 Moving Videos")
        header_label.setObjectName("headerLabel")
        layout.addWidget(header_label)

        # Status label with icon
        self.status_label = QLabel("⏳ Initializing operation...")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        # Progress bar with better styling
        progress_group = QGroupBox("📊 Progress")
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% Complete")
        progress_layout.addWidget(self.progress_bar)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Log area with enhanced styling
        log_group = QGroupBox("📝 Operation Log")
        log_layout = QVBoxLayout()
        log_layout.setSpacing(5)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(250)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Statistics with enhanced design
        stats_group = self.create_stats_group()
        layout.addWidget(stats_group)

        # Buttons with better layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch()

        self.cancel_btn = QPushButton("⏸️ Cancel Operation")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setToolTip("Cancel the ongoing move operation")
        self.cancel_btn.clicked.connect(self.cancel_operation)
        button_layout.addWidget(self.cancel_btn)

        self.close_btn = QPushButton("✅ Close Window")
        self.close_btn.setToolTip("Close this dialog")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setEnabled(False)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_stats_group(self) -> QGroupBox:
        """Create statistics group box"""
        stats_group = QGroupBox("📈 Live Statistics")
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(25)

        # Create styled stat labels with colors
        self.processed_label = self.create_stat_label("Processed", "0", "#00d4ff")
        self.moved_label = self.create_stat_label("Moved", "0", "#00ff88")
        self.skipped_label = self.create_stat_label("Skipped", "0", "#ffaa00")
        self.failed_label = self.create_stat_label("Failed", "0", "#ff6b6b")

        stats_layout.addWidget(self.processed_label)
        stats_layout.addWidget(self.moved_label)
        stats_layout.addWidget(self.skipped_label)
        stats_layout.addWidget(self.failed_label)
        stats_layout.addStretch()

        stats_group.setLayout(stats_layout)
        return stats_group

    def create_stat_label(self, title: str, value: str, color: str) -> QLabel:
        """Create a styled statistic label"""
        label = QLabel(f"<b>{title}:</b> <span style='color: {color}; font-size: 16px;'>{value}</span>")
        label.setStyleSheet(
            f"padding: 8px; background-color: rgba(0, 0, 0, 0.2); "
            f"border-radius: 6px; border-left: 3px solid {color};"
        )
        return label

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
            self.status_label.setText(f"⚙️ Processing mapping {current}/{total}...")
        else:
            self.progress_bar.setValue(0)
            self.status_label.setText("⏳ Initializing...")

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
        self.status_label.setText("✅ Operation completed successfully!")
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("✅ Completed - 100%")

        # Update final statistics with styled labels
        total_processed = len(results)
        total_moved = sum(r.videos_moved for r in results)
        total_skipped = sum(r.videos_skipped for r in results)
        total_failed = sum(r.videos_failed for r in results)

        self.processed_label.setText(
            f"<b>Processed:</b> <span style='color: #00d4ff; font-size: 16px;'>{total_processed}</span>"
        )
        self.moved_label.setText(
            f"<b>Moved:</b> <span style='color: #00ff88; font-size: 16px;'>{total_moved}</span>"
        )
        self.skipped_label.setText(
            f"<b>Skipped:</b> <span style='color: #ffaa00; font-size: 16px;'>{total_skipped}</span>"
        )
        self.failed_label.setText(
            f"<b>Failed:</b> <span style='color: #ff6b6b; font-size: 16px;'>{total_failed}</span>"
        )

        # Enable close button
        self.close_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def cancel_operation(self):
        """Cancel the ongoing operation"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.add_log_message("\n⏸️ Cancelling operation...", "warning")
            self.worker_thread.cancel()
            self.worker_thread.wait()  # Wait for thread to finish
            self.status_label.setText("⏸️ Operation cancelled by user")
            self.progress_bar.setFormat("⏸️ Cancelled - %p%")
            self.close_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.worker_thread and self.worker_thread.isRunning() and not self.is_complete:
            self.cancel_operation()
        event.accept()
