"""
Workflow 1 - Smart Browser Cookie Extractor

Bypasses the SQLite file lock that occurs when Chrome/Edge is running
by copying the Cookies DB to a temp location and decrypting with
Windows DPAPI + AES-256-GCM (Chromium v80+).

Supported browsers  : Chrome, Edge (Chromium-based)
Supported platforms : Windows
Fallback            : Direct browser_cookie3 extraction (if DB copy fails)
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# DPAPI helpers (no win32crypt dependency – pure ctypes)
# ---------------------------------------------------------------------------

class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_decrypt(data: bytes) -> Optional[bytes]:
    """Decrypt a DPAPI blob using ctypes (works without pywin32)."""
    try:
        buf = ctypes.create_string_buffer(data, len(data))
        blob_in = _DataBlob(ctypes.sizeof(buf), buf)
        blob_out = _DataBlob()
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None, None, None, None, 0,
            ctypes.byref(blob_out),
        )
        if not ok:
            return None
        result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return result
    except Exception:
        return None


# ---------------------------------------------------------------------------
# AES-GCM decryption helpers (try pycryptodome, then cryptography)
# ---------------------------------------------------------------------------

def _aes_gcm_decrypt(key: bytes, iv: bytes, ciphertext_with_tag: bytes) -> str:
    """Decrypt AES-256-GCM ciphertext.  Tag is the last 16 bytes."""
    tag = ciphertext_with_tag[-16:]
    ciphertext = ciphertext_with_tag[:-16]
    # Try pycryptodome first
    try:
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8", errors="replace")
    except ImportError:
        pass
    # Try cryptography package
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(iv, ciphertext_with_tag, None).decode("utf-8", errors="replace")
    except Exception:
        pass
    return ""


def _decrypt_cookie_value(encrypted_value: bytes, aes_key: Optional[bytes]) -> str:
    """Decrypt a single Chrome/Edge cookie encrypted_value field."""
    if not encrypted_value:
        return ""
    prefix = encrypted_value[:3]
    if prefix in (b"v10", b"v11", b"v20"):
        # AES-256-GCM (Chrome 80+)
        if not aes_key:
            return ""
        iv = encrypted_value[3:15]
        return _aes_gcm_decrypt(aes_key, iv, encrypted_value[15:])
    # Legacy DPAPI-encrypted value (Chrome < 80 or Windows fallback)
    decrypted = _dpapi_decrypt(encrypted_value)
    return decrypted.decode("utf-8", errors="replace") if decrypted else ""


# ---------------------------------------------------------------------------
# Browser profile discovery
# ---------------------------------------------------------------------------

_BROWSER_PROFILES: Dict[str, Path] = {
    "chrome": Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data",
    "edge":   Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data",
    "brave":  Path(os.environ.get("LOCALAPPDATA", "")) / "BraveSoftware" / "Brave-Browser" / "User Data",
}


def _get_aes_key(user_data_dir: Path) -> Optional[bytes]:
    """Read and DPAPI-decrypt the AES master key from Chrome's Local State."""
    local_state_path = user_data_dir / "Local State"
    if not local_state_path.exists():
        return None
    try:
        with open(str(local_state_path), "r", encoding="utf-8") as f:
            local_state = json.load(f)
        b64_key = local_state.get("os_crypt", {}).get("encrypted_key", "")
        if not b64_key:
            return None
        encrypted_key = base64.b64decode(b64_key)
        # Strip "DPAPI" prefix (5 bytes)
        if encrypted_key[:5] == b"DPAPI":
            encrypted_key = encrypted_key[5:]
        return _dpapi_decrypt(encrypted_key)
    except Exception:
        return None


def _list_profiles(user_data_dir: Path) -> List[str]:
    """Return all profile folder names that contain a Cookies DB."""
    profiles: List[str] = []
    if not user_data_dir.exists():
        return profiles
    for candidate in ["Default", "Profile 1", "Profile 2", "Profile 3"]:
        db = user_data_dir / candidate / "Network" / "Cookies"
        if not db.exists():
            # Older Chrome path (no Network sub-folder)
            db = user_data_dir / candidate / "Cookies"
        if db.exists():
            profiles.append(candidate)
    return profiles or ["Default"]


# ---------------------------------------------------------------------------
# Domain filters
# ---------------------------------------------------------------------------

_PLATFORM_DOMAINS: Dict[str, List[str]] = {
    "instagram": ["instagram.com"],
    "facebook":  ["facebook.com"],
    "tiktok":    ["tiktok.com"],
    "youtube":   ["youtube.com", "google.com"],
    "twitter":   ["twitter.com", "x.com"],
}


def _domain_matches(host_key: str, platform_key: str) -> bool:
    domains = _PLATFORM_DOMAINS.get(platform_key, [])
    if not domains:
        return True  # no filter → accept all
    hk = (host_key or "").lower().lstrip(".")
    return any(d in hk for d in domains)


# ---------------------------------------------------------------------------
# Chrome timestamp → Unix timestamp
# ---------------------------------------------------------------------------

def _chrome_ts_to_unix(chrome_ts: int) -> int:
    """Chrome stores timestamps as microseconds since 1601-01-01."""
    if not chrome_ts or chrome_ts <= 0:
        return 0
    return max(0, (chrome_ts - 11_644_473_600_000_000) // 1_000_000)


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def _read_cookies_from_db(
    db_path: Path,
    aes_key: Optional[bytes],
    platform_key: str,
) -> List[Dict]:
    """Copy DB to temp, query it, decrypt values. Returns list of cookie dicts."""
    if not db_path.exists():
        return []

    temp_db: Optional[str] = None
    try:
        # Copy while Chrome may have it locked
        fd, temp_db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        shutil.copy2(str(db_path), temp_db)
        time.sleep(0.05)  # tiny pause so OS flushes the copy

        conn = sqlite3.connect(f"file:{temp_db}?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT host_key, name, encrypted_value, path, expires_utc, is_secure "
            "FROM cookies"
        )
        rows = cur.fetchall()
        conn.close()

        cookies: List[Dict] = []
        for row in rows:
            host_key = row["host_key"] or ""
            if not _domain_matches(host_key, platform_key):
                continue
            value = _decrypt_cookie_value(bytes(row["encrypted_value"] or b""), aes_key)
            if not value:
                continue
            cookies.append({
                "host_key":   host_key,
                "name":       row["name"] or "",
                "value":      value,
                "path":       row["path"] or "/",
                "expires_ts": _chrome_ts_to_unix(row["expires_utc"] or 0),
                "is_secure":  bool(row["is_secure"]),
            })
        return cookies

    except Exception as exc:
        logging.debug(f"browser_extractor: DB read error: {exc}")
        return []
    finally:
        if temp_db:
            try:
                os.unlink(temp_db)
            except Exception:
                pass


def _cookies_to_netscape(cookies: List[Dict], source_label: str, out_path: Path) -> bool:
    """Write cookie list as Netscape HTTP Cookie File."""
    if not cookies:
        return False
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(out_path), "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(f"# Source: {source_label}\n\n")
            for c in cookies:
                flag = "TRUE" if c["host_key"].startswith(".") else "FALSE"
                secure = "TRUE" if c["is_secure"] else "FALSE"
                f.write(
                    f"{c['host_key']}\t{flag}\t{c['path']}\t"
                    f"{secure}\t{c['expires_ts']}\t{c['name']}\t{c['value']}\n"
                )
        return True
    except Exception as exc:
        logging.debug(f"browser_extractor: write error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_cookies_db_copy(
    platform_key: str,
    preferred_browser: Optional[str] = None,
    save_to: Optional[Path] = None,
) -> Optional[str]:
    """
    Extract browser cookies by copying the locked SQLite DB.

    Args:
        platform_key    : 'instagram', 'facebook', 'tiktok', 'youtube', etc.
        preferred_browser: 'chrome', 'edge', 'brave' or None (tries all)
        save_to         : If given, also save a copy to this Path (e.g. cookies/chrome_cookies.txt)

    Returns:
        Path to a temporary Netscape cookie file, or None on failure.
    """
    browsers_to_try: List[Tuple[str, Path]] = []

    if preferred_browser:
        pb = preferred_browser.lower()
        if pb in _BROWSER_PROFILES:
            browsers_to_try = [(pb, _BROWSER_PROFILES[pb])]
    if not browsers_to_try:
        # Try Chrome first, then Edge, then Brave
        browsers_to_try = list(_BROWSER_PROFILES.items())

    for browser_name, user_data_dir in browsers_to_try:
        if not user_data_dir.exists():
            continue
        aes_key = _get_aes_key(user_data_dir)
        profiles = _list_profiles(user_data_dir)

        for profile in profiles:
            # Prefer the Network sub-folder (Chrome 96+)
            db_path = user_data_dir / profile / "Network" / "Cookies"
            if not db_path.exists():
                db_path = user_data_dir / profile / "Cookies"
            if not db_path.exists():
                continue

            cookies = _read_cookies_from_db(db_path, aes_key, platform_key)
            if not cookies:
                continue

            # Write temp Netscape file
            fd, tmp_path = tempfile.mkstemp(suffix=".txt")
            os.close(fd)
            source_label = f"{browser_name}:{profile} (DB copy)"
            if _cookies_to_netscape(cookies, source_label, Path(tmp_path)):
                logging.info(
                    f"browser_extractor: extracted {len(cookies)} cookies "
                    f"from {browser_name}:{profile} for {platform_key}"
                )
                # Optionally persist to a shared location
                if save_to:
                    try:
                        shutil.copy2(tmp_path, str(save_to))
                        logging.info(f"browser_extractor: saved cookies → {save_to}")
                    except Exception:
                        pass
                return tmp_path
            else:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    return None


def extract_all_platforms_to_master(save_path: Path) -> bool:
    """
    Extract cookies for all supported platforms from Chrome and save
    as a single chrome_cookies.txt master file.

    Useful for a one-time 'Refresh Cookies' button in the GUI.
    Returns True if any cookies were written.
    """
    all_cookies: List[Dict] = []
    platforms = list(_PLATFORM_DOMAINS.keys())

    browsers_to_try = list(_BROWSER_PROFILES.items())
    for browser_name, user_data_dir in browsers_to_try:
        if not user_data_dir.exists():
            continue
        aes_key = _get_aes_key(user_data_dir)
        profiles = _list_profiles(user_data_dir)
        for profile in profiles:
            db_path = user_data_dir / profile / "Network" / "Cookies"
            if not db_path.exists():
                db_path = user_data_dir / profile / "Cookies"
            if not db_path.exists():
                continue
            # Read for all platforms at once (no domain filter)
            raw = _read_cookies_from_db(db_path, aes_key, "")  # "" = no filter
            all_cookies.extend(raw)
            if raw:
                logging.info(
                    f"browser_extractor: master extract from {browser_name}:{profile} → {len(raw)} cookies"
                )

    if not all_cookies:
        return False

    # Deduplicate by (host_key, name)
    seen: set = set()
    deduped: List[Dict] = []
    for c in all_cookies:
        key = (c["host_key"], c["name"])
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    return _cookies_to_netscape(deduped, "all-platforms master extract", save_path)
