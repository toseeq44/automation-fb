"""Approach selection dialog for the modular auto uploader."""

import logging
from pathlib import Path
from typing import Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..auth.credential_manager import CredentialManager
from ..config.settings_manager import SettingsManager


class ApproachDialog(QDialog):
    """Dialog that lets the user choose an automation approach and capture credentials."""

    APPROACHES = [
        ("free_automation", "Free Automation"),
        ("gologin", "GoLogin"),
        ("ix", "IX Browser"),
        ("nstbrowser", "NSTbrowser"),
        ("vpn", "VPN"),
    ]

    def __init__(
        self,
        settings_manager: SettingsManager,
        credential_manager: CredentialManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Select Automation Approach")
        self.setModal(True)
        self.setMinimumWidth(480)

        self._settings = settings_manager
        self._credentials = credential_manager
        self._input_fields: Dict[str, Dict[str, QLineEdit]] = {}
        self._optional_fields: Dict[str, set[str]] = {
            "ix": {"api_url", "profile_id", "profile_name"},
            "nstbrowser": {"base_url"},
        }
        self._free_fields: Dict[str, QLineEdit] = {}
        self._free_labels: Dict[str, str] = {
            "creators_root": "Creators Folder",
            "shortcuts_root": "Creator Shortcuts Folder",
        }

        self._build_ui()
        self._load_existing_selection()

    # ------------------------------------------------------------------ #
    # UI building                                                        #
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        subtitle = QLabel(
            "Choose how the bot should control accounts. You can change this option later using the Approaches button."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._approach_combo = QComboBox()
        for value, label in self.APPROACHES:
            self._approach_combo.addItem(label, value)
        self._approach_combo.currentIndexChanged.connect(self._on_approach_changed)
        layout.addWidget(self._approach_combo)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        # Free automation configuration
        free_widget = QWidget()
        free_layout = QVBoxLayout(free_widget)
        free_layout.setSpacing(10)
        free_description = QLabel(
            "Select the folders that contain creator videos and shortcut definitions for the free automation workflow."
        )
        free_description.setWordWrap(True)
        free_layout.addWidget(free_description)

        free_form = QFormLayout()
        free_form.setSpacing(8)
        free_form.setLabelAlignment(Qt.AlignLeft)

        for key, label in self._free_labels.items():
            line_edit = self._build_path_row(free_form, label)
            self._free_fields[key] = line_edit

        free_layout.addLayout(free_form)
        free_layout.addStretch()
        self._stack.addWidget(free_widget)

        mode_field_map = {
            "gologin": {
                "api_key": ("API Key", False, ""),
                "email": ("Account Email", False, ""),
                "password": ("Account Password", True, ""),
            },
            "ix": {
                "api_url": ("Local API URL", False, "http://127.0.0.1:53200/v2"),
                "profile_id": ("Profile ID (optional)", False, ""),
                "profile_name": ("Profile Name (optional)", False, ""),
                "email": ("Account Email", False, ""),
                "password": ("Account Password", True, ""),
            },
            "nstbrowser": {
                "base_url": ("API URL (optional)", False, "http://127.0.0.1:8848"),
                "api_key": ("API Key", False, ""),
                "email": ("Account Email", False, ""),
                "password": ("Account Password", True, ""),
            },
        }

        for mode in ("gologin", "ix", "nstbrowser"):
            widget, fields = self._build_account_form(mode_field_map[mode])
            self._input_fields[mode] = fields
            self._stack.addWidget(widget)

        # VPN credentials
        vpn_widget, vpn_fields = self._build_account_form(
            {
                "username": ("VPN Username", False, ""),
                "password": ("VPN Password", True, ""),
                "location": ("Preferred Location", False, ""),
            }
        )
        self._input_fields["vpn"] = vpn_fields
        self._stack.addWidget(vpn_widget)

        self._button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        self._button_box.accepted.connect(self._persist_selection)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

    def _build_account_form(
        self,
        field_map: Dict[str, tuple[str, bool, str]],
    ) -> tuple[QWidget, Dict[str, QLineEdit]]:
        widget = QWidget()
        form_layout = QFormLayout(widget)
        form_layout.setSpacing(8)
        form_layout.setLabelAlignment(Qt.AlignLeft)

        fields: Dict[str, QLineEdit] = {}
        for key, descriptor in field_map.items():
            if len(descriptor) == 2:
                label, is_secret = descriptor
                placeholder = ""
            else:
                label, is_secret, placeholder = descriptor[:3]
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(placeholder or label)
            if is_secret:
                line_edit.setEchoMode(QLineEdit.Password)
            form_layout.addRow(QLabel(label), line_edit)
            fields[key] = line_edit

        return widget, fields

    def _build_path_row(self, form_layout: QFormLayout, label: str) -> QLineEdit:
        container = QWidget()
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        line_edit = QLineEdit()
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(lambda _, target=line_edit: self._browse_folder(target))

        row_layout.addWidget(line_edit)
        row_layout.addWidget(browse_btn)
        form_layout.addRow(QLabel(label), container)
        return line_edit

    # ------------------------------------------------------------------ #
    # Data handling                                                      #
    # ------------------------------------------------------------------ #
    def _load_existing_selection(self) -> None:
        current_mode = self._settings.get_automation_mode()
        index = next((i for i, (value, _) in enumerate(self.APPROACHES) if value == current_mode), 0)
        self._approach_combo.setCurrentIndex(index)
        self._on_approach_changed(index)

        paths = self._settings.get_automation_paths() or {}
        if isinstance(paths, dict):
            for key, widget in self._free_fields.items():
                widget.setText(paths.get(key, ""))

        for mode, fields in self._input_fields.items():
            stored = self._settings.get_credentials(mode) or {}
            for key, widget in fields.items():
                if key != "password":
                    widget.setText(stored.get(key, ""))

            # Load password from credential manager (if available)
            if "password" in fields:
                secret = self._credentials.load_credentials(f"approach:{mode}")
                if secret and "password" in secret:
                    fields["password"].setText(secret["password"])

    def _on_approach_changed(self, index: int) -> None:
        # 0 -> free, 1 -> gologin, 2 -> ix, 3 -> nstbrowser, 4 -> vpn
        self._stack.setCurrentIndex(index)

    def _persist_selection(self) -> None:
        mode = self._approach_combo.currentData()
        if mode is None:
            logging.error("No automation mode selected.")
            return

        if not self._validate_mode_payload(mode):
            return

        self._settings.set_automation_mode(mode)
        self._settings.mark_setup_completed()

        logging.info("Automation approach set to %s", mode)
        self.accept()

    def _validate_mode_payload(self, mode: str) -> bool:
        if mode == "free_automation":
            paths: Dict[str, str] = {}
            for key, widget in self._free_fields.items():
                text = widget.text().strip()
                if not text:
                    widget.setFocus()
                    human_label = self._free_labels.get(key, key.replace("_", " ").title())
                    QMessageBox.warning(
                        self,
                        "Missing Information",
                        f"{human_label} is required for Free Automation.",
                    )
                    logging.warning("Field '%s' is required for mode '%s'", key, mode)
                    return False
                paths[key] = text

            existing_paths = self._settings.get_automation_paths()
            history_file = ""
            if isinstance(existing_paths, dict):
                history_file = existing_paths.get("history_file", "")

            self._settings.update_automation_paths(
                creators_root=paths["creators_root"],
                shortcuts_root=paths["shortcuts_root"],
                history_file=history_file,
            )
            self._settings.update_credentials(mode, {})
            return True

        fields = self._input_fields.get(mode, {})
        payload: Dict[str, str] = {}
        optional_keys = self._optional_fields.get(mode, set())
        for key, widget in fields.items():
            text = widget.text().strip()
            if not text and key not in optional_keys and key != "password":
                widget.setFocus()
                human_label = widget.placeholderText() or key.replace("_", " ").title()
                QMessageBox.warning(self, "Missing Information", f"{human_label} is required for {mode.title()}.")
                logging.warning("Field '%s' is required for mode '%s'", key, mode)
                return False
            if text:
                payload[key] = text

        # Persist credentials (password handled via credential manager)
        password = payload.pop("password", "")
        if password:
            if not self._credentials.save_credentials(f"approach:{mode}", {"password": password}):
                QMessageBox.critical(
                    self,
                    "Credential Error",
                    "Unable to store the password securely. Please check your keyring configuration.",
                )
                return False
        else:
            self._credentials.delete_credentials(f"approach:{mode}")

        self._settings.update_credentials(mode, payload)
        return True

    def _browse_folder(self, target: QLineEdit) -> None:
        start_dir = target.text() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "Select Folder", start_dir)
        if directory:
            target.setText(directory)
