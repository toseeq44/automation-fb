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
import inspect
import logging

try:  # pragma: no cover - import side effects exercised at runtime
    from .core import FacebookAutoUploader
    from .configuration import SettingsManager
    from .ui_configurator import InitialSetupUI
except ImportError:
    FacebookAutoUploader = None
    SettingsManager = None
    InitialSetupUI = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .configuration import SettingsManager
except ImportError:  # pragma: no cover - compatibility guard
    SettingsManager = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .ui_configurator import InitialSetupUI
except ImportError:  # pragma: no cover - compatibility guard
    InitialSetupUI = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .utils import load_config, merge_dicts, save_config
except ImportError:  # pragma: no cover - compatibility guard
    load_config = None
    merge_dicts = None
    save_config = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .configuration import SettingsManager
except ImportError:  # pragma: no cover - compatibility guard
    SettingsManager = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .ui_configurator import InitialSetupUI
except ImportError:  # pragma: no cover - compatibility guard
    InitialSetupUI = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .utils import load_config, merge_dicts, save_config
except ImportError:  # pragma: no cover - compatibility guard
    load_config = None
    merge_dicts = None
    save_config = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .configuration import SettingsManager
except ImportError:  # pragma: no cover - compatibility guard
    SettingsManager = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .ui_configurator import InitialSetupUI
except ImportError:  # pragma: no cover - compatibility guard
    InitialSetupUI = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .utils import load_config, merge_dicts, save_config
except ImportError:  # pragma: no cover - compatibility guard
    load_config = None
    merge_dicts = None
    save_config = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .configuration import SettingsManager
except ImportError:  # pragma: no cover - compatibility guard
    SettingsManager = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .ui_configurator import InitialSetupUI
except ImportError:  # pragma: no cover - compatibility guard
    InitialSetupUI = None

try:  # pragma: no cover - import side effects exercised at runtime
    from .utils import load_config, merge_dicts, save_config
except ImportError:  # pragma: no cover - compatibility guard
    load_config = None
    merge_dicts = None
    save_config = None


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
            self.log_signal.emit("Initializing Facebook Auto Uploader...")

            try:
                # Use parent directory (auto_uploader) as base, not _legacy folder
                base_dir = Path(__file__).parent.parent
                self.uploader = FacebookAutoUploader(base_dir=base_dir)
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
            logging.getLogger().addHandler(gui_handler)

            # Run uploader
            success = self.uploader.run()
            self.finished_signal.emit(success)

        except Exception as e:
            self.log_signal.emit(f"\n❌ RUNTIME ERROR:\n{str(e)}\n")
            import traceback
            self.log_signal.emit(traceback.format_exc())
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

        # Approaches button (NEW - select automation approach)
        self.approaches_btn = QPushButton("⚙️ Approaches")
        self.approaches_btn.setStyleSheet("""
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
        self.approaches_btn.clicked.connect(self.show_approach_selector)
        btn_layout.addWidget(self.approaches_btn)

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

        # Use parent directory (auto_uploader) as base, not _legacy folder
        base_dir = Path(__file__).resolve().parent.parent
        settings_path = base_dir / 'data_files' / 'settings.json'  # ✓ FIXED PATH

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

    def show_approach_selector(self):
        """Show dialog to select automation approach"""
        from PyQt5.QtWidgets import QDialog, QRadioButton, QButtonGroup, QDialogButtonBox

        # Load current approach from settings
        current_approach = self.get_current_approach()

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Automation Approach")
        dialog.setModal(True)
        dialog.setStyleSheet("background-color: #2C2F33; color: #F5F6F5;")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QLabel("⚙️ Choose Automation Approach")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1ABC9C;")
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel("Select which approach the bot should use for automation:")
        desc_label.setStyleSheet("font-size: 13px; color: #B9BBBE; margin-bottom: 10px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Radio buttons
        button_group = QButtonGroup(dialog)

        # Legacy approach
        legacy_radio = QRadioButton("🔧 Legacy Approach (Original Code)")
        legacy_radio.setStyleSheet("""
            QRadioButton {
                font-size: 14px;
                color: #F5F6F5;
                spacing: 10px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        legacy_desc = QLabel("   Uses the original automation code. Stable and tested.")
        legacy_desc.setStyleSheet("font-size: 12px; color: #95A5A6; margin-left: 30px;")
        legacy_desc.setWordWrap(True)

        button_group.addButton(legacy_radio, 0)
        layout.addWidget(legacy_radio)
        layout.addWidget(legacy_desc)

        # Intelligent approach
        intelligent_radio = QRadioButton("🤖 Intelligent Approach (AI-Powered)")
        intelligent_radio.setStyleSheet("""
            QRadioButton {
                font-size: 14px;
                color: #F5F6F5;
                spacing: 10px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        intelligent_desc = QLabel("   Uses new modular code with:\n   • Image recognition for UI detection\n   • Human-like mouse movements with bezier curves\n   • Circular idle animations for trust-building\n   • Intelligent login/logout with autofill handling")
        intelligent_desc.setStyleSheet("font-size: 12px; color: #95A5A6; margin-left: 30px;")
        intelligent_desc.setWordWrap(True)

        button_group.addButton(intelligent_radio, 1)
        layout.addWidget(intelligent_radio)
        layout.addWidget(intelligent_desc)

        # Set current selection
        if current_approach == "intelligent":
            intelligent_radio.setChecked(True)
        else:
            legacy_radio.setChecked(True)

        # Current selection indicator
        current_label = QLabel(f"Current: {current_approach.upper()}")
        current_label.setStyleSheet("font-size: 12px; color: #43B581; margin-top: 10px;")
        layout.addWidget(current_label)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.setStyleSheet("""
            QPushButton {
                background-color: #1ABC9C;
                color: #F5F6F5;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #16A085;
            }
        """)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.setLayout(layout)

        # Show dialog and get result
        if dialog.exec_() == QDialog.Accepted:
            selected_id = button_group.checkedId()
            new_approach = "intelligent" if selected_id == 1 else "legacy"

            # Save to settings
            if self.save_approach(new_approach):
                self.log_output.append(f"\n✓ Approach changed to: {new_approach.upper()}")
                QMessageBox.information(
                    self,
                    "Approach Updated",
                    f"Automation approach set to: {new_approach.upper()}\n\nThis will take effect on next upload."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Save Failed",
                    "Could not save approach to settings.json"
                )

    def get_current_approach(self):
        """Get current approach from settings.json"""
        try:
            if load_config:
                config = load_config()
                return config.get('automation', {}).get('approach', 'legacy')
            return 'legacy'
        except Exception as e:
            logging.error(f"Error loading approach: {e}")
            return 'legacy'

    def save_approach(self, approach):
        """Save approach to settings.json"""
        try:
            if load_config and save_config:
                config = load_config()
                if 'automation' not in config:
                    config['automation'] = {}
                config['automation']['approach'] = approach
                save_config(config)
                logging.info(f"Approach saved: {approach}")
                return True
            return False
        except Exception as e:
            logging.error(f"Error saving approach: {e}")
            return False
            self.log_output.append("\n" + "="*60)
            self.log_output.append("✗ Upload process failed or was stopped")
            self.log_output.append("="*60)

    # ------------------------------------------------------------------
    # settings helpers
    # ------------------------------------------------------------------
    def _initialise_settings_manager(
        self,
        manager_cls,
        settings_path: Path,
        base_dir: Path,
        collector,
    ):
        """Create a SettingsManager instance with broad compatibility."""

        try:
            return manager_cls(settings_path, base_dir)
        except TypeError as exc:
            logging.debug("SettingsManager two-argument init failed: %s", exc)

            signature = None
            try:
                signature = inspect.signature(manager_cls.__init__)
            except (TypeError, ValueError):  # pragma: no cover - defensive guard
                pass

            if signature and "interactive_collector" in signature.parameters:
                logging.debug("Retrying SettingsManager init with interactive collector")
                return manager_cls(settings_path, base_dir, collector)

            raise

    def _ensure_settings_setup(
        self,
        settings_manager,
        collector,
        settings_path: Path,
    ):
        """Make sure the configuration wizard has completed."""

        ensure_setup = getattr(settings_manager, "ensure_setup", None)
        if callable(ensure_setup):
            try:
                ensure_setup(interactive_collector=collector)
                return
            except TypeError as exc:
                logging.debug(
                    "ensure_setup rejected 'interactive_collector'; retrying without kwargs: %s",
                    exc,
                )
                try:
                    ensure_setup()
                    # Fall through to manual collector application so GUI data is still captured.
                except Exception as inner_exc:  # pragma: no cover - defensive guard
                    logging.debug("ensure_setup() call without kwargs failed: %s", inner_exc)

        self._apply_collector_payload(settings_manager, collector, settings_path)

    def _apply_collector_payload(self, settings_manager, collector, settings_path: Path):
        """Fallback path that applies the GUI payload manually for legacy managers."""

        if collector is None:
            return

        if load_config is None or merge_dicts is None or save_config is None:
            raise RuntimeError(
                "The setup wizard is unavailable because configuration utilities could not be loaded."
            )

        current_config = {}

        # Try common attributes exposed by historical SettingsManager implementations.
        for attr in ("config", "_config"):
            try:
                candidate = getattr(settings_manager, attr)
                if callable(candidate):  # pragma: no cover - defensive guard
                    candidate = candidate()
                if isinstance(candidate, dict):
                    current_config = candidate
                    break
            except Exception:  # pragma: no cover - defensive guard
                continue
        else:
            current_config = load_config(settings_path)

        payload = collector(current_config)
        if not payload:
            raise RuntimeError("Initial setup wizard was cancelled by the user")

        merged = merge_dicts(current_config, payload)

        if hasattr(settings_manager, "_config"):
            try:
                settings_manager._config = merged
            except Exception:  # pragma: no cover - defensive guard
                pass

        saved = False
        saver = getattr(settings_manager, "save", None)
        if callable(saver):
            try:
                saver()
                saved = True
            except TypeError:
                try:
                    saver(merged)
                    saved = True
                except Exception:  # pragma: no cover - defensive guard
                    pass

        if not saved:
            save_config(settings_path, merged)

        # Attempt to rebuild derived attributes if helpers are present.
        builder = getattr(settings_manager, "_build_paths", None)
        if callable(builder):
            try:
                settings_manager.paths = builder()
            except Exception:  # pragma: no cover - defensive guard
                pass

