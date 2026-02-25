"""
Workflow 2 - Credential Store
==============================
Securely saves and retrieves per-platform login credentials using
Windows Credential Manager (via the `keyring` library) with a DPAPI
fallback to a local encrypted JSON file.

Supports: Instagram, Facebook, TikTok, YouTube, Twitter
Supports 2FA: TOTP secret (Google Authenticator) + manual SMS/email flow

Usage
-----
    store = CredentialStore()
    store.save('instagram', 'myuser', 'mypassword', totp_secret='BASE32SECRET')
    creds = store.load('instagram')
    # creds = {'username': ..., 'password': ..., 'totp_secret': ...}
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Keyring service name
# ─────────────────────────────────────────────────────────────────────────────

_SERVICE = "automation_downloader"
_FALLBACK_FILE = Path(os.environ.get("APPDATA", "")) / ".automation_creds.json"


# ─────────────────────────────────────────────────────────────────────────────
# DPAPI helpers for fallback file encryption (no external deps)
# ─────────────────────────────────────────────────────────────────────────────

def _dpapi_encrypt(data: bytes) -> Optional[bytes]:
    try:
        import ctypes, ctypes.wintypes

        class _Blob(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_char))]

        buf      = ctypes.create_string_buffer(data, len(data))
        blob_in  = _Blob(ctypes.sizeof(buf), buf)
        blob_out = _Blob()
        ok = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0,
            ctypes.byref(blob_out),
        )
        if not ok:
            return None
        result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return result
    except Exception:
        return None


def _dpapi_decrypt(data: bytes) -> Optional[bytes]:
    try:
        import ctypes, ctypes.wintypes

        class _Blob(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_char))]

        buf      = ctypes.create_string_buffer(data, len(data))
        blob_in  = _Blob(ctypes.sizeof(buf), buf)
        blob_out = _Blob()
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0,
            ctypes.byref(blob_out),
        )
        if not ok:
            return None
        result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return result
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TOTP generation (Google Authenticator style)
# ─────────────────────────────────────────────────────────────────────────────

def generate_totp(secret: str) -> Optional[str]:
    """Generate a current TOTP code from a base32 secret key."""
    try:
        import hmac, hashlib, struct, time as _time
        key  = base64.b32decode(secret.strip().upper().replace(" ", ""), casefold=True)
        ts   = int(_time.time()) // 30
        msg  = struct.pack(">Q", ts)
        h    = hmac.new(key, msg, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        code   = struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF
        return str(code % 1_000_000).zfill(6)
    except Exception as e:
        logging.debug(f"TOTP error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CredentialStore
# ─────────────────────────────────────────────────────────────────────────────

class CredentialStore:
    """
    Stores per-platform credentials.
    Primary storage  : Windows Credential Manager (keyring)
    Fallback storage : APPDATA/.automation_creds.json (DPAPI-encrypted)
    """

    SUPPORTED_PLATFORMS = {"instagram", "facebook", "tiktok", "youtube", "twitter"}

    def __init__(self):
        self._keyring_ok = self._check_keyring()

    # ── internal ──────────────────────────────────────────────────────────────

    def _check_keyring(self) -> bool:
        try:
            import keyring
            keyring.get_password(_SERVICE, "__test__")
            return True
        except Exception:
            return False

    def _key(self, platform: str) -> str:
        return f"{_SERVICE}_{platform}"

    # ── keyring methods ───────────────────────────────────────────────────────

    def _kr_save(self, platform: str, payload: dict) -> bool:
        try:
            import keyring
            keyring.set_password(_SERVICE, platform, json.dumps(payload))
            return True
        except Exception as e:
            logging.debug(f"keyring save failed: {e}")
            return False

    def _kr_load(self, platform: str) -> Optional[dict]:
        try:
            import keyring
            raw = keyring.get_password(_SERVICE, platform)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def _kr_delete(self, platform: str) -> bool:
        try:
            import keyring
            keyring.delete_password(_SERVICE, platform)
            return True
        except Exception:
            return False

    # ── fallback file methods ─────────────────────────────────────────────────

    def _file_load_all(self) -> Dict[str, str]:
        if not _FALLBACK_FILE.exists():
            return {}
        try:
            raw = _FALLBACK_FILE.read_bytes()
            decrypted = _dpapi_decrypt(raw)
            if decrypted:
                return json.loads(decrypted.decode("utf-8"))
            # Unencrypted fallback (old format)
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _file_save_all(self, data: Dict[str, str]) -> bool:
        try:
            _FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
            raw = json.dumps(data).encode("utf-8")
            encrypted = _dpapi_encrypt(raw)
            _FALLBACK_FILE.write_bytes(encrypted if encrypted else raw)
            return True
        except Exception as e:
            logging.debug(f"fallback file save failed: {e}")
            return False

    def _file_save(self, platform: str, payload: dict) -> bool:
        all_data = self._file_load_all()
        all_data[platform] = json.dumps(payload)
        return self._file_save_all(all_data)

    def _file_load(self, platform: str) -> Optional[dict]:
        all_data = self._file_load_all()
        raw = all_data.get(platform)
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return None

    def _file_delete(self, platform: str) -> bool:
        all_data = self._file_load_all()
        if platform in all_data:
            del all_data[platform]
            return self._file_save_all(all_data)
        return True

    # ── Public API ────────────────────────────────────────────────────────────

    def save(
        self,
        platform: str,
        username: str,
        password: str,
        totp_secret: str = "",
    ) -> bool:
        """Save credentials for a platform."""
        platform = platform.lower()
        payload = {
            "username":    username,
            "password":    password,
            "totp_secret": totp_secret,
        }
        if self._keyring_ok:
            ok = self._kr_save(platform, payload)
            if ok:
                logging.info(f"CredentialStore: saved {platform} to keyring")
                return True
        ok = self._file_save(platform, payload)
        if ok:
            logging.info(f"CredentialStore: saved {platform} to fallback file")
        return ok

    def load(self, platform: str) -> Optional[Dict[str, str]]:
        """Load credentials for a platform. Returns dict or None."""
        platform = platform.lower()
        if self._keyring_ok:
            creds = self._kr_load(platform)
            if creds:
                return creds
        return self._file_load(platform)

    def has_credentials(self, platform: str) -> bool:
        return self.load(platform.lower()) is not None

    def delete(self, platform: str) -> bool:
        platform = platform.lower()
        ok = True
        if self._keyring_ok:
            ok = self._kr_delete(platform)
        ok = self._file_delete(platform) and ok
        return ok

    def get_totp_code(self, platform: str) -> Optional[str]:
        """Generate current TOTP code if secret is stored."""
        creds = self.load(platform)
        if creds and creds.get("totp_secret"):
            return generate_totp(creds["totp_secret"])
        return None

    def list_platforms(self) -> list:
        """Return list of platforms with stored credentials."""
        stored = []
        for p in self.SUPPORTED_PLATFORMS:
            if self.has_credentials(p):
                stored.append(p)
        return stored
