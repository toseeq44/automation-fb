"""Main PyQt5 page for the modular Facebook auto uploader."""

import logging
from datetime import datetime
from typing import Callable, Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)

from ..auth.credential_manager import CredentialManager
from ..config.settings_manager import SettingsManager
from ..core.orchestrator import UploadOrchestrator
from .approach_dialog import ApproachDialog


class UploadWorker(QThread):
    """Background worker that executes the orchestration flow."""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, orchestrator: UploadOrchestrator, automation_mode: str):
        super().__init__()
        self._orchestrator = orchestrator
        self._automation_mode = automation_mode

    def run(self) -> None:
        try:
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] Starting workflow ({self._automation_mode})")
            success = self._orchestrator.run(mode=self._automation_mode)
            self.finished_signal.emit(bool(success))
        except Exception as exc:  # pragma: no cover - runtime safeguard
            logging.exception("Upload workflow crashed", exc_info=True)
            self.log_signal.emit(f"[ERROR] {exc}")
            self.finished_signal.emit(False)


class AutoUploaderPage(QWidget):
    """Modern replacement for the legacy AutoUploaderPage."""

    def __init__(self, back_callback: Optional[Callable[[], None]] = None, parent: Optional[QWidget] = None):
        # Backward compatibility: legacy code passed the callback as the first
        # positional argument instead of a QWidget parent.
        if parent is None and isinstance(back_callback, QWidget):
            parent = back_callback
            back_callback = None

        super().__init__(parent)

        self.back_callback = back_callback
        self.settings = SettingsManager()
        self.credentials = CredentialManager()
        self.orchestrator = UploadOrchestrator(settings=self.settings, credentials=self.credentials)

        self.worker: Optional[UploadWorker] = None
        self.current_mode = self.settings.get_automation_mode()

        self._build_ui()
        self._append_log(f"Current approach: {self.current_mode}")

    # ------------------------------------------------------------------ #
    # UI construction                                                    #
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        self.setObjectName("autoUploaderRoot")
        self.setStyleSheet(
            """
            QWidget#autoUploaderRoot {
                background-color: #23272A;
                color: #F5F6F5;
            }
            QLabel#titleLabel {
                font-size: 24px;
                font-weight: bold;
                color: #1ABC9C;
            }
            QLabel {
                font-size: 14px;
            }
            QPushButton {
                background-color: #3498DB;
                color: #F5F6F5;
                border: none;
                padding: 10px 18px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #4B6584;
                color: #CED6E0;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
            QTextEdit {
                background-color: #2C2F33;
                color: #F5F6F5;
                border-radius: 4px;
            }
            """
        )

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(24, 24, 24, 24)
        outer_layout.setSpacing(16)

        title = QLabel("Facebook Auto Uploader")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        outer_layout.addWidget(title)

        subtitle = QLabel("Manage uploads using modular automation approaches.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #B9BBBE;")
        outer_layout.addWidget(subtitle)

        status_layout = QHBoxLayout()
        status_layout.setSpacing(10)

        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        status_layout.addWidget(status_label)

        self.status_value = QLabel("Ready")
        self.status_value.setStyleSheet("font-size: 14px; color: #43B581;")
        status_layout.addWidget(self.status_value)
        status_layout.addStretch()

        outer_layout.addLayout(status_layout)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        self.approach_button = QPushButton("Approaches...")
        self.approach_button.clicked.connect(self._open_approach_dialog)
        button_row.addWidget(self.approach_button)

        self.start_button = QPushButton("Start Upload")
        self.start_button.clicked.connect(self.start_upload)
        button_row.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_upload)
        self.stop_button.setEnabled(False)
        button_row.addWidget(self.stop_button)

        button_row.addStretch()
        outer_layout.addLayout(button_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        outer_layout.addWidget(self.progress_bar)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(260)
        outer_layout.addWidget(self.log_output)

        outer_layout.addStretch()

    # ------------------------------------------------------------------ #
    # Workflow management                                                #
    # ------------------------------------------------------------------ #
    def _open_approach_dialog(self, force: bool = False) -> None:
        if self.worker and self.worker.isRunning() and not force:
            QMessageBox.information(self, "Workflow running", "Stop the current upload before changing approach.")
            return

        dialog = ApproachDialog(self.settings, self.credentials, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.current_mode = self.settings.get_automation_mode()
            self._append_log(f"Approach selected: {self.current_mode}")
        elif force:
            QMessageBox.warning(
                self,
                "Setup Incomplete",
                "An automation approach is required before the uploader can start.",
            )

    def start_upload(self) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Upload running", "The upload workflow is already running.")
            return

        if not self.settings.is_setup_completed():
            self._open_approach_dialog(force=True)
            if not self.settings.is_setup_completed():
                return

        self.current_mode = self.settings.get_automation_mode()
        self.status_value.setText("Running...")
        self.status_value.setStyleSheet("font-size: 14px; color: #F39C12;")

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indeterminate

        self.worker = UploadWorker(self.orchestrator, self.current_mode)
        self.worker.log_signal.connect(self._append_log)
        self.worker.finished_signal.connect(self._upload_finished)
        self.worker.start()

    def stop_upload(self) -> None:
        if not self.worker or not self.worker.isRunning():
            return

        self._append_log("Stopping upload...")
        self.worker.requestInterruption()
        self.worker.quit()
        self.worker.wait(2000)
        self._upload_finished(False)

    def _upload_finished(self, success: bool) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)

        if success:
            self.status_value.setText("Completed Successfully")
            self.status_value.setStyleSheet("font-size: 14px; color: #43B581;")
            self._append_log("Upload process completed successfully.")
        else:
            self.status_value.setText("Stopped / Failed")
            self.status_value.setStyleSheet("font-size: 14px; color: #E74C3C;")
            self._append_log("Upload process stopped or failed.")

        if self.worker:
            self.worker.finished_signal.disconnect()
            self.worker.log_signal.disconnect()
            self.worker = None

    # ------------------------------------------------------------------ #
    # Logging helper                                                     #
    # ------------------------------------------------------------------ #
    def _append_log(self, message: str) -> None:
        stamped = message if message.startswith("[") else f"[{datetime.now():%H:%M:%S}] {message}"
        self.log_output.append(stamped)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
