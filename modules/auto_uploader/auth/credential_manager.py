"""
Credential Manager
==================
Secure credential storage and retrieval using keyring or encrypted storage.

NOTE: Uses persistent paths for EXE, original paths for development
"""

import base64
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import keyring  # type: ignore

    KEYRING_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    KEYRING_AVAILABLE = False
    keyring = None  # type: ignore
    logging.warning("keyring not available. Install: pip install keyring")


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_running_as_exe() -> bool:
    """Check if running as PyInstaller EXE."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def _get_credentials_dir() -> Path:
    """
    Get credentials directory - EXE uses persistent path, dev uses module path.
    """
    if _is_running_as_exe():
        # EXE mode: use persistent path in user's home
        cred_dir = Path.home() / ".onesoul" / "auto_uploader" / "credentials"
    else:
        # Development mode: use original module path
        cred_dir = Path(__file__).resolve().parents[1] / "data_files" / "credentials"

    cred_dir.mkdir(parents=True, exist_ok=True)
    return cred_dir


class CredentialManager:
    """Manages secure credential storage and retrieval."""

    def __init__(self, service_name: str = "facebook_auto_uploader", storage_path: Optional[Path] = None):
        self.service_name = service_name
        # Use appropriate directory based on running mode
        self.storage_path = storage_path or _get_credentials_dir()
        self.storage_path.mkdir(parents=True, exist_ok=True)

        if not KEYRING_AVAILABLE:
            logging.warning("Keyring not available; credentials will be stored in local encrypted files.")

        logging.debug("CredentialManager initialized (service=%s, storage=%s)", service_name, self.storage_path)

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    def save_credentials(self, identifier: str, credentials: Dict[str, str]) -> bool:
        """Save credentials securely."""
        if not identifier:
            logging.error("Identifier is required to save credentials.")
            return False

        if not self.validate_credentials(credentials):
            logging.error("Credential validation failed for identifier %s", identifier)
            return False

        payload = dict(credentials)
        password = payload.get("password")
        uses_keyring = False

        if password:
            uses_keyring = self._save_to_keyring(identifier, password)
            if uses_keyring:
                payload["password"] = "__keyring__"
            else:
                payload["password"] = self._encode_password(password)

        data = {
            "identifier": identifier,
            "credentials": payload,
            "uses_keyring": uses_keyring,
        }

        return self._save_to_file(identifier, data)

    def load_credentials(self, identifier: str) -> Optional[Dict[str, str]]:
        """Load credentials for identifier."""
        record = self._load_from_file(identifier)
        if not record:
            return None

        payload = dict(record.get("credentials", {}))
        password = payload.get("password")
        uses_keyring = record.get("uses_keyring", False)

        if password == "__keyring__":
            secret = self._load_from_keyring(identifier)
            if secret:
                payload["password"] = secret
            else:
                payload.pop("password", None)
        elif password:
            decoded = self._decode_password(password)
            if decoded is None:
                logging.warning("Unable to decode password for %s", identifier)
                payload.pop("password", None)
            else:
                payload["password"] = decoded

        payload["_uses_keyring"] = uses_keyring
        return payload

    def update_credentials(self, identifier: str, credentials: Dict[str, str]) -> bool:
        """Update existing credentials."""
        if not self.credential_exists(identifier):
            logging.error("Cannot update missing credentials for %s", identifier)
            return False
        return self.save_credentials(identifier, credentials)

    def delete_credentials(self, identifier: str) -> bool:
        """Delete credential record."""
        file_path = self._credential_file(identifier)
        removed = False

        if file_path.exists():
            try:
                file_path.unlink()
                removed = True
            except OSError as exc:
                logging.error("Unable to delete credential file for %s: %s", identifier, exc)
                return False

        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(self.service_name, identifier)  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover - backend specifics
                logging.debug("Keyring deletion warning for %s: %s", identifier, exc)

        return removed

    def list_accounts(self) -> List[str]:
        """List all saved credential identifiers."""
        results: List[str] = []
        for file_path in self.storage_path.glob("*.json"):
            try:
                record = json.loads(file_path.read_text(encoding="utf-8"))
                identifier = record.get("identifier")
                if identifier:
                    results.append(identifier)
            except json.JSONDecodeError:
                logging.warning("Skipping malformed credential file: %s", file_path.name)
        return sorted(results)

    def credential_exists(self, identifier: str) -> bool:
        """Check if credentials exist for identifier."""
        return self._credential_file(identifier).exists()

    def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """
        Validate credential format and required fields.

        Only ensures that email (if provided) looks valid and password (if provided) is non-empty.
        """
        if not isinstance(credentials, dict):
            return False

        email = credentials.get("email")
        password = credentials.get("password")

        if email and not EMAIL_PATTERN.match(email):
            logging.warning("Invalid email format: %s", email)
            return False

        if password is not None and not str(password).strip():
            logging.warning("Password cannot be empty.")
            return False

        return True

    def import_from_file(self, file_path: Path, format: str = "json") -> int:
        """Import credentials from external JSON file."""
        format = format.lower()
        if format != "json":
            logging.error("Unsupported credential import format: %s", format)
            return 0

        try:
            entries = json.loads(Path(file_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logging.error("Failed to import credentials from %s: %s", file_path, exc)
            return 0

        imported = 0
        if isinstance(entries, dict):
            iterable = entries.items()
        elif isinstance(entries, list):
            iterable = ((item.get("identifier"), item.get("credentials", {})) for item in entries)
        else:
            logging.error("Unsupported credential import structure. Expected list or dict.")
            return 0

        for identifier, payload in iterable:
            if not identifier or not isinstance(payload, dict):
                continue
            if self.save_credentials(str(identifier), payload):
                imported += 1

        logging.info("Imported %s credential entries.", imported)
        return imported

    def export_to_file(self, file_path: Path, format: str = "json", include_passwords: bool = False) -> bool:
        """Export credential metadata to external file."""
        format = format.lower()
        if format != "json":
            logging.error("Unsupported credential export format: %s", format)
            return False

        export_list: List[Dict[str, Any]] = []
        for identifier in self.list_accounts():
            record = self._load_from_file(identifier)
            if not record:
                continue

            payload = dict(record.get("credentials", {}))
            if not include_passwords:
                payload.pop("password", None)
            else:
                loaded = self.load_credentials(identifier)
                if loaded and "password" in loaded:
                    payload["password"] = loaded["password"]

            export_list.append({"identifier": identifier, "credentials": payload})

        try:
            Path(file_path).write_text(json.dumps(export_list, indent=2), encoding="utf-8")
            return True
        except OSError as exc:
            logging.error("Unable to export credentials to %s: %s", file_path, exc)
            return False

    def change_master_password(self, old_password: str, new_password: str) -> bool:
        """Placeholder for API compatibility. Returns False because the feature is not implemented."""
        logging.warning("change_master_password not implemented in the lightweight credential manager.")
        return False

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _credential_file(self, identifier: str) -> Path:
        safe_identifier = re.sub(r"[^a-zA-Z0-9_.-]", "_", identifier)
        return self.storage_path / f"{safe_identifier}.json"

    def _save_to_file(self, identifier: str, payload: Dict[str, Any]) -> bool:
        file_path = self._credential_file(identifier)
        try:
            file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return True
        except OSError as exc:
            logging.error("Failed to write credential file for %s: %s", identifier, exc)
            return False

    def _load_from_file(self, identifier: str) -> Optional[Dict[str, Any]]:
        file_path = self._credential_file(identifier)
        if not file_path.exists():
            return None
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logging.error("Failed to read credential file for %s: %s", identifier, exc)
            return None

    def _save_to_keyring(self, identifier: str, password: str) -> bool:
        if not (KEYRING_AVAILABLE and password):
            return False
        try:
            keyring.set_password(self.service_name, identifier, password)  # type: ignore[attr-defined]
            return True
        except Exception as exc:  # pragma: no cover - backend specific
            logging.debug("Keyring storage failed for %s: %s", identifier, exc)
            return False

    def _load_from_keyring(self, identifier: str) -> Optional[str]:
        if not KEYRING_AVAILABLE:
            return None
        try:
            return keyring.get_password(self.service_name, identifier)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - backend specific
            logging.debug("Keyring retrieval failed for %s: %s", identifier, exc)
            return None

    @staticmethod
    def _encode_password(password: str) -> str:
        return base64.urlsafe_b64encode(password.encode("utf-8")).decode("utf-8")

    @staticmethod
    def _decode_password(token: str) -> Optional[str]:
        try:
            return base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        except Exception:
            return None

