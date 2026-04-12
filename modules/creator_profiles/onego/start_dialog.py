"""
OneGo Start Dialog
Asks user for mode (Downloading+Uploading / Uploading only)
and IX API credentials, with prefill from shared storage.
"""

import logging
from typing import Optional, Dict, Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

log = logging.getLogger(__name__)

_BG = "#0d1117"
_BG_INPUT = "#0a0e1a"
_CYAN = "#00d4ff"
_GREEN = "#43B581"
_BORDER = "rgba(0,212,255,0.2)"

MODE_DOWNLOAD_UPLOAD = "download_upload"
MODE_UPLOAD_ONLY = "upload_only"
ACTIVITY_DISABLED = "disabled"
ACTIVITY_ENABLED = "enabled"


def _load_ix_prefill() -> Dict[str, str]:
    """Load saved IX credentials from shared auto_uploader storage."""
    result: Dict[str, str] = {}
    try:
        from modules.auto_uploader.config.settings_manager import SettingsManager
        sm = SettingsManager()
        creds = sm.get_credentials("ix") or {}
        result["api_url"] = creds.get("api_url", "")
        result["email"] = creds.get("email", "")
        result["profile_hint"] = creds.get("profile_hint", "")
    except Exception as exc:
        log.debug("Could not load IX settings: %s", exc)

    try:
        from modules.auto_uploader.auth.credential_manager import CredentialManager
        cm = CredentialManager()
        stored = cm.load_credentials("approach:ix") or {}
        if not result.get("email") and stored.get("email"):
            result["email"] = stored["email"]
        result["password"] = stored.get("password", "")
    except Exception as exc:
        log.debug("Could not load IX credentials: %s", exc)

    return result


def _save_ix_credentials(api_url: str, email: str, password: str, profile_hint: str) -> None:
    """Persist IX credentials back to shared auto_uploader storage."""
    try:
        from modules.auto_uploader.config.settings_manager import SettingsManager
        sm = SettingsManager()
        payload = {"api_url": api_url, "email": email}
        if profile_hint:
            payload["profile_hint"] = profile_hint
        sm.update_credentials("ix", payload)
    except Exception as exc:
        log.warning("Could not save IX settings: %s", exc)

    if password:
        try:
            from modules.auto_uploader.auth.credential_manager import CredentialManager
            cm = CredentialManager()
            cm.save_credentials("approach:ix", {"email": email, "password": password})
        except Exception as exc:
            log.warning("Could not save IX credentials: %s", exc)


class OneGoStartDialog(QDialog):
    """Dialog to configure and launch a OneGo run."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OneGo — Start")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"""
            QDialog {{
                background:{_BG};
                color:white;
            }}
            QLabel {{
                color:white;
                font-size:12px;
                font-weight:bold;
                background:transparent;
                border:none;
            }}
        """)

        self._result_data: Optional[Dict[str, Any]] = None
        self._build()
        self._prefill()

    def _build(self):
        vbox = QVBoxLayout(self)
        vbox.setSpacing(12)

        # Title
        title = QLabel("OneGo Workflow")
        title.setStyleSheet(f"color:{_CYAN}; font-size:16px; font-weight:bold;")
        title.setAlignment(Qt.AlignCenter)
        vbox.addWidget(title)

        # Mode selector
        form = QFormLayout()
        form.setSpacing(8)

        self.mode_cb = QComboBox()
        self.mode_cb.addItem("Downloading + Uploading", MODE_DOWNLOAD_UPLOAD)
        self.mode_cb.addItem("Uploading Only", MODE_UPLOAD_ONLY)
        self.mode_cb.setStyleSheet(self._input_ss())
        self.mode_cb.setFixedHeight(32)
        form.addRow("Mode:", self.mode_cb)

        self.activity_cb = QComboBox()
        self.activity_cb.addItem("Just Uploading", ACTIVITY_DISABLED)
        self.activity_cb.addItem("Uploading + Activity", ACTIVITY_ENABLED)
        self.activity_cb.setStyleSheet(self._input_ss())
        self.activity_cb.setFixedHeight(32)
        form.addRow("Profile Activity:", self.activity_cb)

        # IX API fields
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("http://127.0.0.1:53200")
        self.api_url_input.setStyleSheet(self._input_ss())
        self.api_url_input.setFixedHeight(32)
        form.addRow("IX API URL:", self.api_url_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your@email.com")
        self.email_input.setStyleSheet(self._input_ss())
        self.email_input.setFixedHeight(32)
        form.addRow("IX Email:", self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("IX password")
        self.password_input.setStyleSheet(self._input_ss())
        self.password_input.setFixedHeight(32)
        form.addRow("IX Password:", self.password_input)

        self.profile_hint_input = QLineEdit()
        self.profile_hint_input.setPlaceholderText("(optional) profile name hint")
        self.profile_hint_input.setStyleSheet(self._input_ss())
        self.profile_hint_input.setFixedHeight(32)
        form.addRow("Profile Hint:", self.profile_hint_input)

        vbox.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(self._btn_ss("#E74C3C"))
        cancel_btn.setFixedHeight(36)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        start_btn = QPushButton("Start OneGo")
        start_btn.setStyleSheet(self._btn_ss(_GREEN))
        start_btn.setFixedHeight(36)
        start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(start_btn)

        vbox.addLayout(btn_row)

    def _prefill(self):
        saved = _load_ix_prefill()
        self._original = dict(saved)  # track originals for dirty-check
        if saved.get("api_url"):
            self.api_url_input.setText(saved["api_url"])
        if saved.get("email"):
            self.email_input.setText(saved["email"])
        if saved.get("password"):
            self.password_input.setText(saved["password"])
        if saved.get("profile_hint"):
            self.profile_hint_input.setText(saved["profile_hint"])

    def _on_start(self):
        api_url = self.api_url_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        profile_hint = self.profile_hint_input.text().strip()

        if not api_url:
            api_url = "http://127.0.0.1:53200"

        # Only persist if user actually changed a field
        orig = getattr(self, "_original", {})
        orig_api = orig.get("api_url") or "http://127.0.0.1:53200"
        orig_email = orig.get("email") or ""
        orig_pw = orig.get("password") or ""
        orig_hint = orig.get("profile_hint") or ""

        changed = (
            api_url != orig_api
            or email != orig_email
            or password != orig_pw
            or profile_hint != orig_hint
        )
        if changed:
            # If password blank/unchanged, keep the stored password
            save_pw = password if password and password != orig_pw else orig_pw
            _save_ix_credentials(api_url, email, save_pw, profile_hint)

        # Pass effective password to workflow (typed or stored)
        effective_pw = password if password else orig_pw

        mode = self.mode_cb.currentData()
        self._result_data = {
            "mode": mode,
            "activity_mode": self.activity_cb.currentData(),
            "api_url": api_url,
            "email": email,
            "password": effective_pw,
            "profile_hint": profile_hint,
        }
        self.accept()

    def get_result(self) -> Optional[Dict[str, Any]]:
        return self._result_data

    @staticmethod
    def _input_ss() -> str:
        return (
            f"background:{_BG_INPUT}; color:white;"
            f" border:1px solid {_BORDER}; border-radius:4px; padding:5px 7px;"
            " font-size:12px;"
        )

    @staticmethod
    def _btn_ss(fg: str) -> str:
        return (
            f"QPushButton {{"
            f"  color:{fg}; background:#161b22;"
            f"  border:1px solid {fg}; border-radius:5px;"
            f"  padding:6px 18px; font-weight:bold; font-size:13px;"
            f"}}"
            f"QPushButton:hover {{ background:#1c2128; }}"
            f"QPushButton:pressed {{ background:rgba(255,255,255,0.12); }}"
        )
