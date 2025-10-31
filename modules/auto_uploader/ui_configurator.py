"""Configuration UI helpers for the Facebook automation bot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from .utils import expand_path

try:  # pragma: no cover - GUI imports are optional at runtime
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )

    PYQT_AVAILABLE = True
except Exception:  # pragma: no cover - allow CLI fallback
    QApplication = None  # type: ignore
    PYQT_AVAILABLE = False


MODE_OPTIONS = [
    ("GoLogin", "gologin"),
    ("IX Browser", "ix"),
    ("VPN", "vpn"),
    ("Free Automation", "free_automation"),
]


if PYQT_AVAILABLE:  # pragma: no cover - GUI code exercised via manual testing

    class SetupWizardDialog(QDialog):
        """PyQt dialog that collects initial configuration data."""

        def __init__(self, base_dir: Path, current_config: Dict, parent=None):
            super().__init__(parent)
            self.base_dir = Path(base_dir)
            self.current_config = current_config
            self._result: Dict | None = None

            self.setWindowTitle("Facebook Auto Uploader - Initial Setup")
            self.setModal(True)
            self.resize(520, 420)

            self._build_ui()
            self._load_defaults()

        # ------------------------------------------------------------------
        # UI construction helpers
        # ------------------------------------------------------------------
        def _build_ui(self):
            layout = QVBoxLayout(self)
            layout.setSpacing(12)

            title = QLabel("Welcome! Let's prepare your automation setup.")
            title.setWordWrap(True)
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-size: 16px; font-weight: 600;")
            layout.addWidget(title)

            # Mode selection
            mode_layout = QVBoxLayout()
            mode_label = QLabel("Select automation mode")
            mode_label.setStyleSheet("font-weight: 600;")
            mode_layout.addWidget(mode_label)

            self.mode_combo = QComboBox()
            for label, value in MODE_OPTIONS:
                self.mode_combo.addItem(label, value)
            self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
            mode_layout.addWidget(self.mode_combo)

            layout.addLayout(mode_layout)

            # Content folders section
            folders_label = QLabel("Content folders")
            folders_label.setStyleSheet("font-weight: 600;")
            layout.addWidget(folders_label)

            folders_widget = QWidget()
            folders_form = QFormLayout(folders_widget)
            folders_form.setLabelAlignment(Qt.AlignLeft)

            self.creators_edit = QLineEdit()
            self.creators_browse = QPushButton("Browse…")
            self.creators_browse.clicked.connect(lambda: self._browse_directory(self.creators_edit))

            creators_row = QHBoxLayout()
            creators_row.addWidget(self.creators_edit)
            creators_row.addWidget(self.creators_browse)
            folders_form.addRow("Creators folder", creators_row)

            self.shortcuts_edit = QLineEdit()
            self.shortcuts_browse = QPushButton("Browse…")
            self.shortcuts_browse.clicked.connect(lambda: self._browse_directory(self.shortcuts_edit))

            shortcuts_row = QHBoxLayout()
            shortcuts_row.addWidget(self.shortcuts_edit)
            shortcuts_row.addWidget(self.shortcuts_browse)
            folders_form.addRow("Creator shortcuts", shortcuts_row)

            layout.addWidget(folders_widget)

            # Credentials stack
            creds_label = QLabel("Mode details")
            creds_label.setStyleSheet("font-weight: 600;")
            layout.addWidget(creds_label)

            self.stack = QStackedWidget()
            layout.addWidget(self.stack)

            self.browser_forms: Dict[str, Dict[str, QLineEdit]] = {}
            self.vpn_form: Dict[str, QLineEdit] | None = None

            self.stack.addWidget(self._create_free_form())
            self.stack.addWidget(self._create_browser_form("gologin"))
            self.stack.addWidget(self._create_browser_form("ix"))
            self.stack.addWidget(self._create_vpn_form())

            # Buttons
            buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def _create_free_form(self) -> QWidget:
            widget = QWidget()
            v_layout = QVBoxLayout(widget)
            label = QLabel(
                "Free automation mode uses your local shortcuts."
                "\nEnsure each login folder contains creator shortcuts and login data."
            )
            label.setWordWrap(True)
            v_layout.addWidget(label)
            v_layout.addStretch()
            return widget

        def _create_browser_form(self, key: str) -> QWidget:
            widget = QWidget()
            form = QFormLayout(widget)

            api_key = QLineEdit()
            form.addRow("API Key (optional)", api_key)

            email = QLineEdit()
            form.addRow("Account email", email)

            password = QLineEdit()
            password.setEchoMode(QLineEdit.Password)
            form.addRow("Account password", password)

            self.browser_forms[key] = {
                "api_key": api_key,
                "email": email,
                "password": password,
            }

            return widget

        def _create_vpn_form(self) -> QWidget:
            widget = QWidget()
            form = QFormLayout(widget)

            username = QLineEdit()
            form.addRow("VPN username", username)

            password = QLineEdit()
            password.setEchoMode(QLineEdit.Password)
            form.addRow("VPN password", password)

            location = QLineEdit()
            form.addRow("Preferred city/country", location)

            self.vpn_form = {
                "username": username,
                "password": password,
                "location": location,
            }

            return widget

        # ------------------------------------------------------------------
        # Event handlers
        # ------------------------------------------------------------------
        def _on_mode_changed(self, index: int):
            # Stack order: free, gologin, ix, vpn
            self.stack.setCurrentIndex(index)

        def _browse_directory(self, line_edit: QLineEdit):
            start_dir = line_edit.text() or str(self.base_dir)
            selected = QFileDialog.getExistingDirectory(self, "Select folder", start_dir)
            if selected:
                line_edit.setText(selected)

        # ------------------------------------------------------------------
        # Data helpers
        # ------------------------------------------------------------------
        def _load_defaults(self):
            automation_cfg = self.current_config.get("automation", {})
            default_mode = automation_cfg.get("mode", "free_automation")
            for idx, (_, value) in enumerate(MODE_OPTIONS):
                if value == default_mode:
                    self.mode_combo.setCurrentIndex(idx)
                    break

            paths_cfg = automation_cfg.get("paths", {})
            creators_default = paths_cfg.get("creators_root") or str((self.base_dir / "creators").resolve())
            shortcuts_default = paths_cfg.get("shortcuts_root") or str((self.base_dir / "creator_shortcuts").resolve())
            history_default = paths_cfg.get("history_file") or str((self.base_dir / "data" / "history.json").resolve())

            self.creators_edit.setText(creators_default)
            self.shortcuts_edit.setText(shortcuts_default)
            self._history_path = history_default

            creds_cfg = automation_cfg.get("credentials", {})
            for key, fields in self.browser_forms.items():
                existing = creds_cfg.get(key, {})
                fields["api_key"].setText(existing.get("api_key", ""))
                fields["email"].setText(existing.get("email", ""))
                fields["password"].setText(existing.get("password", ""))

            if self.vpn_form:
                existing_vpn = creds_cfg.get("vpn", {})
                self.vpn_form["username"].setText(existing_vpn.get("username", ""))
                self.vpn_form["password"].setText(existing_vpn.get("password", ""))
                self.vpn_form["location"].setText(existing_vpn.get("location", ""))

        def accept(self):  # noqa: D401 - Qt specific signature
            mode = self.mode_combo.currentData()

            creators_value = self.creators_edit.text().strip()
            shortcuts_value = self.shortcuts_edit.text().strip()
            if not creators_value or not shortcuts_value:
                QMessageBox.warning(self, "Missing folders", "Please provide both creators and shortcut folders.")
                return

            creators_path = expand_path(creators_value, self.base_dir / "creators")
            shortcuts_path = expand_path(shortcuts_value, self.base_dir / "creator_shortcuts")

            payload: Dict = {
                "automation": {
                    "mode": mode,
                    "setup_completed": True,
                    "paths": {
                        "creators_root": str(creators_path),
                        "shortcuts_root": str(shortcuts_path),
                        "history_file": self._history_path,
                    },
                }
            }

            if mode in {"gologin", "ix"}:
                fields = self.browser_forms[mode]
                api_key = fields["api_key"].text().strip()
                email = fields["email"].text().strip()
                password = fields["password"].text().strip()

                if not api_key and (not email or not password):
                    QMessageBox.warning(
                        self,
                        "Missing credentials",
                        "Provide an API key or an email/password combination for the selected service.",
                    )
                    return

                payload["automation"]["credentials"] = {
                    mode: {
                        "api_key": api_key,
                        "email": email,
                        "password": password,
                    }
                }

            elif mode == "vpn" and self.vpn_form:
                username = self.vpn_form["username"].text().strip()
                password = self.vpn_form["password"].text().strip()
                location = self.vpn_form["location"].text().strip()

                if not username or not password:
                    QMessageBox.warning(self, "Missing VPN credentials", "Enter VPN username and password.")
                    return

                payload["automation"]["credentials"] = {
                    "vpn": {
                        "username": username,
                        "password": password,
                        "location": location,
                    }
                }

            self._result = payload
            super().accept()

        def get_payload(self) -> Dict | None:
            return self._result

else:  # pragma: no cover - fallback when PyQt is unavailable

    class SetupWizardDialog:  # type: ignore[misc]
        def __init__(self, *_, **__):
            raise RuntimeError("PyQt5 is required for the GUI setup wizard.")


class CLIInitialSetup:
    """Command line fallback configuration wizard."""

    MODES = {str(idx + 1): (label, value) for idx, (label, value) in enumerate(MODE_OPTIONS)}

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def collect(self, current_config: Dict) -> Dict:
        logging.info("Starting CLI configuration wizard for Facebook Auto Uploader")
        automation_cfg = current_config.get("automation", {})
        mode_choice = self._ask_mode(automation_cfg.get("mode", "free_automation"))

        updated = {
            "automation": {
                "mode": mode_choice,
                "setup_completed": True,
                "paths": {},
            }
        }

        if mode_choice == "free_automation":
            updated["automation"]["paths"].update(self._collect_free_paths(automation_cfg.get("paths", {})))
        elif mode_choice in {"gologin", "ix"}:
            updated["automation"]["credentials"] = self._collect_browser_credentials(
                mode_choice, automation_cfg.get("credentials", {})
            )
        elif mode_choice == "vpn":
            updated["automation"]["credentials"] = self._collect_vpn_credentials(automation_cfg.get("credentials", {}))

        logging.info("CLI configuration captured")
        return updated

    # ------------------------------------------------------------------
    def _ask_mode(self, default_mode: str) -> str:
        print("\nSelect automation mode:")
        for key, (label, _) in self.MODES.items():
            print(f"  {key}. {label}")

        default_key = next((key for key, (_, value) in self.MODES.items() if value == default_mode), "4")
        selection = input(f"Enter choice [{default_key}]: ").strip() or default_key
        return self.MODES.get(selection, self.MODES[default_key])[1]

    def _collect_free_paths(self, existing_paths: Dict) -> Dict:
        creators_default = existing_paths.get("creators_root") or str((self.base_dir / "creators").resolve())
        shortcuts_default = existing_paths.get("shortcuts_root") or str((self.base_dir / "creator_shortcuts").resolve())

        creators_root = input(f"Creators folder path [{creators_default}]: ").strip() or creators_default
        shortcuts_root = input(f"Creator shortcuts folder path [{shortcuts_default}]: ").strip() or shortcuts_default

        creators_path = expand_path(creators_root, self.base_dir / "creators")
        shortcuts_path = expand_path(shortcuts_root, self.base_dir / "creator_shortcuts")

        return {
            "creators_root": str(creators_path),
            "shortcuts_root": str(shortcuts_path),
        }

    def _collect_browser_credentials(self, mode: str, existing_credentials: Dict) -> Dict:
        print("\nProvide access information for the browser automation service.")
        print("You can leave fields blank to keep existing values.")

        api_key = input("API Key (optional): ").strip() or existing_credentials.get(mode, {}).get("api_key", "")
        email = input("Account email: ").strip() or existing_credentials.get(mode, {}).get("email", "")
        password = input("Account password: ").strip() or existing_credentials.get(mode, {}).get("password", "")

        return {
            mode: {
                "api_key": api_key,
                "email": email,
                "password": password,
            }
        }

    def _collect_vpn_credentials(self, existing_credentials: Dict) -> Dict:
        print("\nEnter VPN credentials and preferred location.")
        vpn_cfg = existing_credentials.get("vpn", {})

        username = input("VPN username: ").strip() or vpn_cfg.get("username", "")
        password = input("VPN password: ").strip() or vpn_cfg.get("password", "")
        location = input("Preferred city/country: ").strip() or vpn_cfg.get("location", "")

        return {
            "vpn": {
                "username": username,
                "password": password,
                "location": location,
            }
        }


class InitialSetupUI:
    """Facade that chooses GUI or CLI setup flows."""

    def __init__(self, base_dir: Path, parent=None):
        self.base_dir = Path(base_dir)
        self.parent = parent

    def collect(self, current_config: Dict) -> Dict:
        if PYQT_AVAILABLE and QApplication is not None:
            app = QApplication.instance()
            if app is not None:
                dialog = SetupWizardDialog(self.base_dir, current_config, parent=self.parent)
                result = dialog.exec_()
                if result == QDialog.Accepted:
                    payload = dialog.get_payload() or {}
                    if payload:
                        logging.info("Initial setup captured via GUI wizard")
                        return payload
                raise RuntimeError("Initial setup wizard was cancelled by the user")

        logging.info("GUI setup unavailable; falling back to CLI wizard")
        cli = CLIInitialSetup(self.base_dir)
        return cli.collect(current_config)

