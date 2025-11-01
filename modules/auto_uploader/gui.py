"""
modules/auto_uploader/gui.py
Facebook Auto Uploader GUI - SIMPLIFIED VERSION
"""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QMessageBox, QProgressBar,
    QDialog, QLineEdit, QComboBox, QFormLayout, QDialogButtonBox,
    QFileDialog, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from pathlib import Path
import inspect
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

    def __init__(self, settings_manager):
        super().__init__()
        self.uploader = None
        self.settings_manager = settings_manager

    def run(self):
        logger = logging.getLogger()
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
            self.log_signal.emit("Initializing Facebook Auto Uploader...")

            try:
                # Use the settings manager from the main thread
                self.uploader = FacebookAutoUploader()
            except ImportError as e:
                self.log_signal.emit(f"\n❌ DEPENDENCY ERROR:\n{str(e)}\n")
                self.log_signal.emit("\nRequired packages:")
                self.log_signal.emit("  • selenium")
                self.log_signal.emit("  • webdriver-manager")
                self.log_signal.emit("  • pyautogui (Windows)")
                self.log_signal.emit("  • pygetwindow (Windows)")
                self.log_signal.emit("\nInstall with:")
                self.log_signal.emit("  pip install selenium webdriver-manager pyautogui pygetwindow")
                self.finished_signal.emit(False)
                return
            except Exception as e:
                self.log_signal.emit(f"\n❌ INITIALIZATION ERROR:\n{str(e)}\n")
                import traceback
                self.log_signal.emit(traceback.format_exc())
                self.finished_signal.emit(False)
                return

            # Add GUI logging handler
            gui_handler = GUIHandler(self.log_signal)
            gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(gui_handler)

            try:
                if self.isInterruptionRequested():
                    self.finished_signal.emit(False)
                    return

                success = self.uploader.run()
            finally:
                logger.removeHandler(gui_handler)

            self.finished_signal.emit(success)

        except Exception as e:
            self.log_signal.emit(f"\n❌ RUNTIME ERROR:\n{str(e)}\n")
            import traceback
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit(False)


class AutoUploaderPage(QWidget):
    """Facebook Auto Uploader GUI Page - SIMPLIFIED"""

    def __init__(self, back_callback=None):
        super().__init__()
        self.back_callback = back_callback
        self.uploader_thread = None
        self.settings_manager = None
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

        self.setup_btn = QPushButton("⚙️ Reset & Configure Settings")
        self.setup_btn.setStyleSheet("""
            QPushButton {
                background-color: #9B59B6;
                color: #F5F6F5;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8E44AD;
            }
        """)
        self.setup_btn.clicked.connect(self.re_run_setup)
        btn_layout.addWidget(self.setup_btn)

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

    def _collect_setup_data(self, base_dir: Path, current_config: Dict[str, Any]) -> Dict[str, Any]:
        """Collect setup data using GUI dialog or fallback collector."""
        dialog_cls = globals().get("SetupDialog")
        if dialog_cls and inspect.isclass(dialog_cls):
            try:
                dialog = dialog_cls(base_dir, self)
            except Exception as exc:
                logging.exception("Failed to initialise setup dialog", exc_info=True)
                raise RuntimeError("Could not open the setup dialog") from exc

            try:
                result = dialog.exec_()
            except Exception as exc:
                logging.exception("Setup dialog crashed", exc_info=True)
                dialog.deleteLater()
                raise RuntimeError("Setup dialog encountered an unexpected error") from exc

            try:
                payload = dialog.get_setup_data() if result == QDialog.Accepted else None
            finally:
                dialog.deleteLater()

            if payload:
                return payload
            raise RuntimeError("Setup was cancelled by user")

        if InitialSetupUI is not None:
            try:
                ui = InitialSetupUI(base_dir)
                return ui.collect(current_config)
            except Exception as exc:
                logging.exception("CLI setup collector failed", exc_info=True)
                raise RuntimeError("Could not collect automation settings") from exc

        raise RuntimeError("Interactive setup UI is not available")

    def _create_settings_manager(self, base_dir: Path, settings_path: Path):
        """Create SettingsManager instance with proper error handling."""
        if SettingsManager is None:
            raise RuntimeError("Settings manager module is unavailable")

        def collector(current_config: Dict[str, Any]) -> Dict[str, Any]:
            return self._collect_setup_data(base_dir, current_config)

        try:
            return SettingsManager(
                settings_path,
                base_dir,
                interactive_collector=collector,
            )
        except Exception as exc:
            logging.exception("Failed to initialise SettingsManager", exc_info=True)
            raise

    def re_run_setup(self):
        """Re-run the setup wizard safely - forces dialog to open"""
        if SettingsManager is None:
            QMessageBox.warning(
                self,
                "Module Not Available",
                "The configuration module could not be loaded."
            )
            return

        if self.uploader_thread and self.uploader_thread.isRunning():
            QMessageBox.warning(
                self,
                "Uploader Running",
                "Please stop the uploader before re-running setup."
            )
            return

        base_dir = Path(__file__).resolve().parent
        settings_path = base_dir / 'data' / 'settings.json'

        try:
            # Reset setup_completed flag to force dialog to open
            if load_config and save_config:
                config = load_config(settings_path)
                config.setdefault("automation", {})["setup_completed"] = False
                save_config(settings_path, config)

            # Create a NEW settings manager which will now trigger dialog
            new_settings_manager = self._create_settings_manager(base_dir, settings_path)

            # Only update if setup was successful
            if new_settings_manager:
                # Clean up old thread if it exists (shouldn't be running but just in case)
                if self.uploader_thread:
                    try:
                        self.uploader_thread.deleteLater()
                    except Exception:
                        pass
                    self.uploader_thread = None

                # Update settings manager
                self.settings_manager = new_settings_manager

                # Reset UI to fresh state
                self.status_text.setText("Ready")
                self.status_text.setStyleSheet("font-size: 14px; color: #43B581;")
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                self.progress_bar.setVisible(False)

                # Clear log output for fresh start
                self.log_output.clear()
                self.log_output.append("="*60)
                self.log_output.append("Settings Updated Successfully!")
                self.log_output.append("="*60)
                self.log_output.append("Ready to start upload with new settings.")

                QMessageBox.information(
                    self,
                    "Setup Updated",
                    "Settings have been updated successfully!\n\n"
                    "You can now start the uploader with new settings."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Setup Failed",
                    "Could not update settings. Please try again."
                )
                
        except RuntimeError as exc:
            message = str(exc) or "Setup was cancelled."
            self.log_output.append(f"[!] {message}")
            QMessageBox.information(self, "Setup Cancelled", message)
        except Exception as exc:
            logging.exception("Failed to re-run setup", exc_info=True)
            QMessageBox.critical(
                self,
                "Setup Error",
                f"Failed to update settings: {exc}"
            )

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
            # Reset UI state
            self.status_text.setText("Failed")
            self.status_text.setStyleSheet("font-size: 14px; color: #E74C3C;")
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

        # Start uploader thread with proper cleanup
        try:
            self.uploader_thread = UploaderThread(self.settings_manager)
            self.uploader_thread.log_signal.connect(self.append_log)
            self.uploader_thread.finished_signal.connect(self.upload_finished)
            self.uploader_thread.start()
        except Exception as e:
            logging.error(f"Failed to start uploader thread: {e}")
            self.upload_finished(False)
            QMessageBox.critical(
                self,
                "Thread Error",
                f"Failed to start upload process: {e}"
            )

    def stop_upload(self):
        """Stop upload process safely"""
        if not self.uploader_thread:
            return

        if self.uploader_thread.isRunning():
            self.log_output.append("\n[!] Stopping uploader...")
            try:
                self.uploader_thread.requestInterruption()
            except AttributeError:
                # Older Qt versions may not support requestInterruption; ignore.
                pass

            if not self.uploader_thread.wait(5000):
                self.log_output.append("[!] Force stopping uploader...")
                self.uploader_thread.terminate()
                self.uploader_thread.wait()

        self.upload_finished(False)

    def append_log(self, message: str):
        """Append message to log"""
        self.log_output.append(message)
        # Auto-scroll to bottom
        cursor = self.log_output.textCursor()
        cursor.movePosition(cursor.End)
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def upload_finished(self, success: bool):
        """Handle upload completion with proper cleanup."""
        if self.uploader_thread:
            try:
                if self.uploader_thread.isRunning():
                    try:
                        self.uploader_thread.requestInterruption()
                    except AttributeError:
                        pass
                    self.uploader_thread.wait(1000)
                self.uploader_thread.deleteLater()
            except Exception as exc:
                logging.debug("Error while cleaning up uploader thread: %s", exc)
            finally:
                self.uploader_thread = None

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
