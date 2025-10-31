"""
modules/auto_uploader/gui.py
Facebook Auto Uploader GUI
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from pathlib import Path
import logging

try:
    from .core import FacebookAutoUploader
    from .configuration import SettingsManager
    from .ui_configurator import InitialSetupUI
except ImportError:
    FacebookAutoUploader = None
    SettingsManager = None
    InitialSetupUI = None


class UploaderThread(QThread):
    """Background thread for running uploader"""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.uploader = None

    def run(self):
        try:
            # Setup logging to emit to GUI
            class GUIHandler(logging.Handler):
                def __init__(self, signal):
                    super().__init__()
                    self.signal = signal

                def emit(self, record):
                    msg = self.format(record)
                    self.signal.emit(msg)

            # Initialize uploader
            self.uploader = FacebookAutoUploader()

            # Add GUI logging handler
            gui_handler = GUIHandler(self.log_signal)
            gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logging.getLogger().addHandler(gui_handler)

            # Run uploader
            success = self.uploader.run()
            self.finished_signal.emit(success)

        except Exception as e:
            self.log_signal.emit(f"ERROR: {str(e)}")
            self.finished_signal.emit(False)


class AutoUploaderPage(QWidget):
    """Facebook Auto Uploader GUI Page"""

    def __init__(self, back_callback=None):
        super().__init__()
        self.back_callback = back_callback
        self.uploader_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        self.setStyleSheet("background-color: #23272A; color: #F5F6F5;")

        # Title
        title = QLabel("☁️ Facebook Auto Uploader")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1ABC9C;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Description
        desc = QLabel("Upload videos to Facebook pages using anti-detect browsers")
        desc.setStyleSheet("font-size: 14px; color: #B9BBBE;")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        # Status section
        status_layout = QHBoxLayout()

        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        status_layout.addWidget(status_label)

        self.status_text = QLabel("Ready")
        self.status_text.setStyleSheet("font-size: 14px; color: #43B581;")
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()

        layout.addLayout(status_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #1ABC9C;
                border-radius: 5px;
                text-align: center;
                background-color: #2C2F33;
                color: #F5F6F5;
            }
            QProgressBar::chunk {
                background-color: #1ABC9C;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Log output
        log_label = QLabel("Log Output:")
        log_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(log_label)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border: 2px solid #1ABC9C;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.log_output)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.start_btn = QPushButton("🚀 Start Upload")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #1ABC9C;
                color: #F5F6F5;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
            QPushButton:pressed {
                background-color: #128C7E;
            }
            QPushButton:disabled {
                background-color: #7F8C8D;
            }
        """)
        self.start_btn.clicked.connect(self.start_upload)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: #F5F6F5;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
            QPushButton:disabled {
                background-color: #7F8C8D;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_upload)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        self.clear_log_btn = QPushButton("🗑 Clear Log")
        self.clear_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #7F8C8D;
                color: #F5F6F5;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #95A5A6;
            }
        """)
        self.clear_log_btn.clicked.connect(lambda: self.log_output.clear())
        btn_layout.addWidget(self.clear_log_btn)

        back_btn = QPushButton("⬅ Back")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: #F5F6F5;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
        """)
        back_btn.clicked.connect(self.back_callback if self.back_callback else lambda: None)
        btn_layout.addWidget(back_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def start_upload(self):
        """Start upload process"""
        if FacebookAutoUploader is None or SettingsManager is None or InitialSetupUI is None:
            QMessageBox.warning(
                self,
                "Module Not Available",
                "The auto uploader module could not be loaded."
            )
            return

        base_dir = Path(__file__).resolve().parent
        settings_path = base_dir / 'data' / 'settings.json'

        try:
            SettingsManager(
                settings_path,
                base_dir,
                interactive_collector=lambda cfg: InitialSetupUI(base_dir, parent=self).collect(cfg),
            )
        except RuntimeError as exc:
            message = str(exc) or "Initial setup was cancelled."
            self.log_output.append(f"[!] {message}")
            QMessageBox.information(self, "Setup Cancelled", message)
            return
        except Exception as exc:  # pragma: no cover - defensive guard
            logging.exception("Failed to complete initial setup", exc_info=True)
            QMessageBox.critical(
                self,
                "Setup Failed",
                f"Could not complete the initial setup: {exc}",
            )
            return

        self.log_output.append("="*60)
        self.log_output.append("Starting Facebook Auto Uploader...")
        self.log_output.append("="*60)

        self.status_text.setText("Running...")
        self.status_text.setStyleSheet("font-size: 14px; color: #F39C12;")

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        # Start uploader thread
        self.uploader_thread = UploaderThread()
        self.uploader_thread.log_signal.connect(self.append_log)
        self.uploader_thread.finished_signal.connect(self.upload_finished)
        self.uploader_thread.start()

    def stop_upload(self):
        """Stop upload process"""
        if self.uploader_thread and self.uploader_thread.isRunning():
            self.log_output.append("\n[!] Stopping uploader...")
            self.uploader_thread.terminate()
            self.uploader_thread.wait()
            self.upload_finished(False)

    def append_log(self, message: str):
        """Append message to log"""
        self.log_output.append(message)
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def upload_finished(self, success: bool):
        """Handle upload completion"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)

        if success:
            self.status_text.setText("Completed Successfully")
            self.status_text.setStyleSheet("font-size: 14px; color: #43B581;")
            self.log_output.append("\n" + "="*60)
            self.log_output.append("✓ Upload process completed successfully!")
            self.log_output.append("="*60)
        else:
            self.status_text.setText("Failed/Stopped")
            self.status_text.setStyleSheet("font-size: 14px; color: #E74C3C;")
            self.log_output.append("\n" + "="*60)
            self.log_output.append("✗ Upload process failed or was stopped")
            self.log_output.append("="*60)