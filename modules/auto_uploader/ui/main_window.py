"""Main PyQt5 page for the modular Facebook auto uploader."""

import logging
import sys
from datetime import datetime
from typing import Callable, Optional
from io import StringIO

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


class LogCapture(logging.Handler):
    """Custom logging handler that captures logs and emits them via Qt signal."""

    def __init__(self, log_signal: pyqtSignal):
        super().__init__()
        self.log_signal = log_signal
        # Don't format here - let records pass through with full info
        self.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        # Ensure this handler captures everything
        self.setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit log record via Qt signal."""
        try:
            msg = self.format(record)
            self.log_signal.emit(msg)
        except Exception:
            self.handleError(record)


class UploadWorker(QThread):
    """Background worker that executes the orchestration flow."""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, orchestrator: UploadOrchestrator, automation_mode: str):
        super().__init__()
        self._orchestrator = orchestrator
        self._automation_mode = automation_mode
        self._log_handler = None

    def run(self) -> None:
        """Execute the upload workflow with proper logging capture."""
        try:
            # Step 1: Setup logging
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 📋 STEP 1/7: Setting up logging system...")

            # Setup log handler
            self._log_handler = LogCapture(self.log_signal)
            self._log_handler.setLevel(logging.DEBUG)

            # Get root logger and set it to DEBUG
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)  # ← Important: Set root logger to DEBUG
            logger.addHandler(self._log_handler)

            # Emit diagnostic info
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] ✅ Logging configured successfully")
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 📊 Root logger level: {logger.level} (DEBUG={logging.DEBUG})")
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 📊 Handler count: {len(logger.handlers)}")
            self.log_signal.emit("")

            # Step 2: Start workflow
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 📋 STEP 2/7: Initializing upload orchestrator...")
            logging.info("="*70)
            logging.info("🚀 UPLOAD ORCHESTRATOR - INITIALIZING")
            logging.info(f"   Mode: {self._automation_mode.upper()}")
            logging.info("="*70)
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] ✅ Orchestrator initialized")
            self.log_signal.emit("")

            # Step 3: Run orchestrator
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 📋 STEP 3/7: Running upload workflow...")

            # Add blank line and start logging from orchestrator
            self.log_signal.emit("")

            logging.info("="*70)
            logging.info("🚀 UPLOAD ORCHESTRATOR - RUNNING WORKFLOW")
            logging.info("="*70)
            logging.info("📌 IMPORTANT: Calling orchestrator.run() with mode: %s", self._automation_mode)
            logging.info("📌 This should show desktop search, browser launch, etc. below:")
            logging.info("")

            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 🔄 About to call orchestrator.run()...")
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] Mode: {self._automation_mode}")

            # CRITICAL: Call the orchestrator
            success = self._orchestrator.run(mode=self._automation_mode)

            # Log the result
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] ✅ orchestrator.run() COMPLETED with result: {success}")
            logging.info("")
            logging.info("📌 orchestrator.run() returned: %s", success)

            # Step 4: Check results
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 📋 STEP 4/7: Checking workflow results...")
            logging.info("="*70)
            if success:
                logging.info("✅ WORKFLOW - COMPLETED SUCCESSFULLY")
            else:
                logging.error("❌ WORKFLOW - FAILED")
            logging.info("="*70)

            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] ✅ Results processed")
            self.log_signal.emit("")

            # Step 5: Cleanup handler
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 📋 STEP 5/7: Cleaning up logging...")
            if self._log_handler:
                logger.removeHandler(self._log_handler)
                self._log_handler.close()
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] ✅ Logging cleaned up")
            self.log_signal.emit("")

            # Step 6: Final message
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 📋 STEP 6/7: Generating final status...")
            self.log_signal.emit("")
            if success:
                self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] ✅✅✅ WORKFLOW COMPLETED SUCCESSFULLY ✅✅✅")
            else:
                self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] ❌ WORKFLOW FAILED - Check logs above for errors")

            self.log_signal.emit("")
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 📋 STEP 7/7: Emitting finished signal...")

            # Step 7: Emit signal
            self.finished_signal.emit(bool(success))
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] ✅ Finished signal emitted. Thread ending.")

        except Exception as exc:  # pragma: no cover - runtime safeguard
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] ❌ EXCEPTION OCCURRED: {type(exc).__name__}")
            self.log_signal.emit(f"[{datetime.now():%H:%M:%S}] 💥 Error details: {str(exc)}")
            logging.exception("💥 Upload workflow crashed", exc_info=True)

            try:
                if self._log_handler:
                    logger = logging.getLogger()
                    logger.removeHandler(self._log_handler)
                    self._log_handler.close()
            except:
                pass

            self.finished_signal.emit(False)

        finally:
            # Final cleanup
            try:
                if self._log_handler:
                    logger = logging.getLogger()
                    logger.removeHandler(self._log_handler)
                    self._log_handler.close()
            except:
                pass


class AutoUploaderPage(QWidget):

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

        # Back button
        self.back_button = QPushButton("◀ Back")
        self.back_button.setMaximumWidth(100)
        self.back_button.setStyleSheet("""
            QPushButton {
                background-color: #95A5A6;
            }
            QPushButton:hover {
                background-color: #7F8C8D;
            }
        """)
        self.back_button.clicked.connect(self._go_back)
        button_row.addWidget(self.back_button)

        button_row.addSpacing(20)

        self.approach_button = QPushButton("⚙️ Approaches...")
        self.approach_button.clicked.connect(self._open_approach_dialog)
        button_row.addWidget(self.approach_button)

        self.start_button = QPushButton("▶️ Start Upload")
        self.start_button.clicked.connect(self.start_upload)
        button_row.addWidget(self.start_button)

        self.stop_button = QPushButton("⏹️ Stop")
        self.stop_button.clicked.connect(self.stop_upload)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
            QPushButton:disabled {
                background-color: #4B6584;
            }
        """)
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
    # Navigation                                                         #
    # ------------------------------------------------------------------ #
    def _go_back(self) -> None:
        """Go back to previous page."""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(
                self,
                "Upload Running",
                "Cannot go back while upload is running. Please stop the upload first."
            )
            return

        self.log_output.clear()
        self._append_log("Going back to main menu...")

        if self.back_callback:
            self.back_callback()

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
        """Start the upload workflow in a separate thread."""
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Upload running", "The upload workflow is already running.")
            return

        # Check if setup is completed
        if not self.settings.is_setup_completed():
            self._append_log("⚠️  Setup not completed. Opening Approaches dialog...")
            self._open_approach_dialog(force=True)
            if not self.settings.is_setup_completed():
                self._append_log("❌ Setup cancelled.")
                return

        # Get current automation mode
        self.current_mode = self.settings.get_automation_mode()
        self._append_log(f"✅ Setup completed. Automation mode: {self.current_mode.upper()}")
        self._append_log("")

        # Update UI state
        self.status_value.setText("Running...")
        self.status_value.setStyleSheet("font-size: 14px; color: #F39C12;")

        self.start_button.setEnabled(False)
        self.approach_button.setEnabled(False)
        self.back_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indeterminate

        # Create and start worker thread
        self.worker = UploadWorker(self.orchestrator, self.current_mode)
        self.worker.log_signal.connect(self._append_log)
        self.worker.finished_signal.connect(self._upload_finished)
        self.worker.start()

    def stop_upload(self) -> None:
        """Stop the running upload workflow."""
        if not self.worker or not self.worker.isRunning():
            self._append_log("❌ No workflow currently running")
            return

        self._append_log("")
        self._append_log(f"[{datetime.now():%H:%M:%S}] 🛑 STOPPING WORKFLOW...")
        self._append_log(f"[{datetime.now():%H:%M:%S}] Requesting thread interruption...")

        # Request interruption
        self.worker.requestInterruption()
        self.worker.quit()

        # Wait for thread to finish (max 5 seconds)
        self._append_log(f"[{datetime.now():%H:%M:%S}] Waiting for thread to finish (max 5 seconds)...")
        if self.worker.wait(5000):
            self._append_log(f"[{datetime.now():%H:%M:%S}] ✅ Thread stopped cleanly")
        else:
            self._append_log(f"[{datetime.now():%H:%M:%S}] ⚠️  Thread did not stop within timeout")
            self._append_log(f"[{datetime.now():%H:%M:%S}] Forcing thread termination...")
            self.worker.terminate()
            self.worker.wait(1000)
            self._append_log(f"[{datetime.now():%H:%M:%S}] ✅ Thread forcefully terminated")

        self._upload_finished(False)

    def _upload_finished(self, success: bool) -> None:
        """Handle upload workflow completion."""
        self._append_log("")
        self._append_log(f"[{datetime.now():%H:%M:%S}] 🧹 Cleaning up worker thread...")

        # Disconnect signals
        try:
            if self.worker:
                self.worker.finished_signal.disconnect()
                self.worker.log_signal.disconnect()
                self._append_log(f"[{datetime.now():%H:%M:%S}] ✅ Signals disconnected")

                # Wait for thread to fully finish
                if self.worker.isRunning():
                    self._append_log(f"[{datetime.now():%H:%M:%S}] Thread still running, waiting...")
                    self.worker.wait(2000)

                self.worker = None
                self._append_log(f"[{datetime.now():%H:%M:%S}] ✅ Worker cleaned up completely")
        except Exception as e:
            self._append_log(f"[{datetime.now():%H:%M:%S}] ⚠️  Error during cleanup: {e}")

        # Re-enable buttons
        self._append_log(f"[{datetime.now():%H:%M:%S}] 🔘 Re-enabling UI buttons...")
        self.start_button.setEnabled(True)
        self.approach_button.setEnabled(True)
        self.back_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self._append_log(f"[{datetime.now():%H:%M:%S}] ✅ Buttons re-enabled")

        # Update status
        self._append_log("")
        self._append_log("=" * 70)
        if success:
            self.status_value.setText("✅ Completed Successfully")
            self.status_value.setStyleSheet("font-size: 14px; color: #43B581;")
            self._append_log(f"[{datetime.now():%H:%M:%S}] ✅✅✅ WORKFLOW COMPLETED SUCCESSFULLY ✅✅✅")
        else:
            self.status_value.setText("❌ Stopped / Failed")
            self.status_value.setStyleSheet("font-size: 14px; color: #E74C3C;")
            self._append_log(f"[{datetime.now():%H:%M:%S}] ❌ WORKFLOW FAILED OR STOPPED")

        self._append_log("=" * 70)
        self._append_log(f"[{datetime.now():%H:%M:%S}] Ready for next upload")

    # ------------------------------------------------------------------ #
    # Logging helper                                                     #
    # ------------------------------------------------------------------ #
    def _append_log(self, message: str) -> None:
        stamped = message if message.startswith("[") else f"[{datetime.now():%H:%M:%S}] {message}"
        self.log_output.append(stamped)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
