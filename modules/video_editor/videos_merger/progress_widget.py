"""
modules/video_editor/videos_merger/progress_widget.py
Progress display widget for merge operations
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QTextEdit, QGroupBox, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class ProgressWidget(QWidget):
    """Widget for displaying merge progress"""

    # Signals
    pause_clicked = pyqtSignal()
    resume_clicked = pyqtSignal()
    cancel_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.is_paused = False
        self.is_processing = False

        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # Progress group
        progress_group = QGroupBox("Progress")
        progress_group.setFont(QFont("Arial", 10, QFont.Bold))
        progress_layout = QVBoxLayout()

        # Current operation label
        self.operation_label = QLabel("Ready")
        self.operation_label.setStyleSheet("font-size: 10pt; font-weight: bold;")
        progress_layout.addWidget(self.operation_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedHeight(25)
        progress_layout.addWidget(self.progress_bar)

        # Status info row
        status_layout = QHBoxLayout()

        # Current batch info (for bulk merge)
        self.batch_label = QLabel("")
        self.batch_label.setStyleSheet("color: #666; font-size: 9pt;")
        status_layout.addWidget(self.batch_label, 1)

        # Time remaining
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #666; font-size: 9pt;")
        self.time_label.setAlignment(Qt.AlignRight)
        status_layout.addWidget(self.time_label)

        progress_layout.addLayout(status_layout)

        # Completed files label
        self.completed_label = QLabel("")
        self.completed_label.setStyleSheet("color: #008800; font-size: 9pt; font-weight: bold;")
        progress_layout.addWidget(self.completed_label)

        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)

        # Log group (collapsible)
        log_group = QGroupBox("Log")
        log_group.setFont(QFont("Arial", 10, QFont.Bold))
        log_group.setCheckable(True)
        log_group.setChecked(False)  # Collapsed by default
        log_layout = QVBoxLayout()

        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: 'Courier New', monospace;
                font-size: 8pt;
                border: 1px solid #555;
            }
        """)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # Control buttons
        button_layout = QHBoxLayout()

        self.pause_resume_btn = QPushButton("⏸️ Pause")
        self.pause_resume_btn.setFixedHeight(35)
        self.pause_resume_btn.clicked.connect(self._on_pause_resume)
        self.pause_resume_btn.setEnabled(False)
        button_layout.addWidget(self.pause_resume_btn)

        self.cancel_btn = QPushButton("⏹️ Cancel")
        self.cancel_btn.setFixedHeight(35)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        button_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # Apply dark theme styling
        self.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;
                color: #e0e0e0;
            }
            QGroupBox {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #00bcd4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 5px 10px;
                color: #00bcd4;
            }
            QGroupBox::indicator {
                width: 16px;
                height: 16px;
            }
            QLabel {
                color: #e0e0e0;
                background-color: transparent;
            }
            QProgressBar {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                text-align: center;
                color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #0066cc;
            }
            QPushButton:pressed {
                background-color: #202020;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #666666;
            }
        """)

    def _on_pause_resume(self):
        """Pause/Resume button clicked"""
        if self.is_paused:
            self.resume_clicked.emit()
        else:
            self.pause_clicked.emit()

    def _on_cancel(self):
        """Cancel button clicked"""
        self.cancel_clicked.emit()

    def start_processing(self):
        """Start processing mode"""
        self.is_processing = True
        self.is_paused = False
        self.pause_resume_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.pause_resume_btn.setText("⏸️ Pause")
        self.progress_bar.setValue(0)
        self.operation_label.setText("Starting...")
        self.log("Processing started")

    def stop_processing(self):
        """Stop processing mode"""
        self.is_processing = False
        self.is_paused = False
        self.pause_resume_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.pause_resume_btn.setText("⏸️ Pause")

    def set_paused(self, paused: bool):
        """Set paused state"""
        self.is_paused = paused
        if paused:
            self.pause_resume_btn.setText("▶️ Resume")
            self.operation_label.setText("⏸️ Paused")
            self.log("Processing paused")
        else:
            self.pause_resume_btn.setText("⏸️ Pause")
            self.log("Processing resumed")

    def update_progress(self, status: str, percentage: float):
        """
        Update progress display

        Args:
            status: Status message
            percentage: Progress percentage (0-100)
        """
        self.operation_label.setText(status)
        self.progress_bar.setValue(int(percentage))

    def update_batch_progress(self, current: int, total: int, status: str, percentage: float):
        """
        Update batch progress

        Args:
            current: Current batch number
            total: Total batches
            status: Status message
            percentage: Progress percentage (0-100)
        """
        self.operation_label.setText(status)
        self.batch_label.setText(f"Batch: {current}/{total}")
        self.progress_bar.setValue(int(percentage))

    def set_completed(self, output_files):
        """
        Set completed state

        Args:
            output_files: List of output file paths
        """
        self.progress_bar.setValue(100)
        self.operation_label.setText("✅ Completed!")

        if output_files:
            if len(output_files) == 1:
                self.completed_label.setText(f"✅ Completed: {output_files[0]}")
            else:
                self.completed_label.setText(f"✅ Completed: {len(output_files)} files")

        self.log("Processing completed successfully")

    def set_failed(self, error_msg: str = None):
        """
        Set failed state

        Args:
            error_msg: Error message
        """
        self.operation_label.setText("❌ Failed")
        self.operation_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: red;")

        if error_msg:
            self.log(f"Error: {error_msg}")

    def set_cancelled(self):
        """Set cancelled state"""
        self.operation_label.setText("⏹️ Cancelled")
        self.log("Processing cancelled by user")

    def log(self, message: str):
        """
        Add log message

        Args:
            message: Log message
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        logger.info(message)

    def clear_log(self):
        """Clear log"""
        self.log_text.clear()

    def reset(self):
        """Reset widget to initial state"""
        self.progress_bar.setValue(0)
        self.operation_label.setText("Ready")
        self.operation_label.setStyleSheet("font-size: 10pt; font-weight: bold;")
        self.batch_label.setText("")
        self.time_label.setText("")
        self.completed_label.setText("")
        self.is_processing = False
        self.is_paused = False
        self.pause_resume_btn.setText("⏸️ Pause")
        self.pause_resume_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
