"""Credential management utilities for the automation bot."""

from __future__ import annotations

import logging
from typing import Dict

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    KEYRING_AVAILABLE = False
    keyring = None


class AuthHandler:
    """Stores and retrieves credentials securely when possible."""

    def __init__(self, service_name: str = "facebook_auto_uploader"):
        self.service_name = service_name

    def save_credentials(self, identifier: str, payload: Dict[str, str]):
        if KEYRING_AVAILABLE and "password" in payload:
            try:
                keyring.set_password(self.service_name, identifier, payload["password"])
                payload = {**payload}
                payload["password"] = "__keyring__"
            except Exception as exc:  # pragma: no cover - depends on environment
                logging.warning("Failed to store password in keyring: %s", exc)

        return payload

    def read_password(self, identifier: str, payload: Dict[str, str]) -> Dict[str, str]:
        if payload.get("password") == "__keyring__" and KEYRING_AVAILABLE:
            try:
                stored = keyring.get_password(self.service_name, identifier)
                if stored:
                    payload = {**payload}
                    payload["password"] = stored
            except Exception as exc:  # pragma: no cover
                logging.warning("Unable to fetch password from keyring: %s", exc)
        return payload

