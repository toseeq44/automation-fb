"""
Workflow 1 - Smart Browser Cookie Extractor
============================================

Full decision chain:
  1. Detect which browsers are CURRENTLY RUNNING (tasklist)
  2. If running → copy locked SQLite DB to temp → AES-256-GCM + DPAPI decrypt
  3. If no browser running → try to read DB directly (no lock when closed)
  4. If cookies missing/expired → check Windows registry for default browser
                                  → launch it → wait for session load → copy DB
  5. Save result to cookies/chrome_cookies.txt for future runs
  6. Debug callback at EVERY step so GUI shows exactly what is happening

Platform   : Windows (DPAPI/AES-256-GCM), graceful skip on Linux/Mac
Encryption : pycryptodome (Crypto.Cipher.AES) OR cryptography package
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import http.client
import json
import logging
import os
import shutil
import socket
import sqlite3
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Type alias for debug callback
# ─────────────────────────────────────────────────────────────────────────────
DebugCb = Optional[Callable[[str], None]]


def _dbg(cb: DebugCb, msg: str) -> None:
    logging.debug(msg)
    if cb:
        cb(msg)


# ─────────────────────────────────────────────────────────────────────────────
# DPAPI (pure ctypes – no pywin32 / win32crypt needed)
# ─────────────────────────────────────────────────────────────────────────────

class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_decrypt(data: bytes) -> Optional[bytes]:
    """Decrypt a Windows DPAPI blob using pure ctypes."""
    try:
        buf = ctypes.create_string_buffer(data, len(data))
        blob_in  = _DataBlob(ctypes.sizeof(buf), buf)
        blob_out = _DataBlob()
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
# AES-256-GCM (Chrome v80+ cookie encryption)
# ─────────────────────────────────────────────────────────────────────────────

def _aes_gcm_decrypt(key: bytes, iv: bytes, ciphertext_with_tag: bytes) -> str:
    """Decrypt AES-256-GCM. Tag = last 16 bytes."""
    tag        = ciphertext_with_tag[-16:]
    ciphertext = ciphertext_with_tag[:-16]
    # Try pycryptodome first
    try:
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8", errors="replace")
    except ImportError:
        pass
    except Exception:
        # Decryption error (wrong key, corrupted data, v20 app-bound, etc.) — try next lib
        pass
    # Try cryptography package
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(iv, ciphertext_with_tag, None).decode("utf-8", errors="replace")
    except Exception:
        pass
    return ""


def _decrypt_value(encrypted_value: bytes, aes_key: Optional[bytes]) -> str:
    """Decrypt a single Chrome cookie encrypted_value field."""
    if not encrypted_value:
        return ""
    prefix = encrypted_value[:3]
    if prefix in (b"v10", b"v11", b"v20"):
        if not aes_key:
            return ""
        iv = encrypted_value[3:15]
        return _aes_gcm_decrypt(aes_key, iv, encrypted_value[15:])
    # Legacy DPAPI
    decrypted = _dpapi_decrypt(encrypted_value)
    return decrypted.decode("utf-8", errors="replace") if decrypted else ""


# ─────────────────────────────────────────────────────────────────────────────
# Browser profile paths
# ─────────────────────────────────────────────────────────────────────────────

_LAPPDATA = os.environ.get("LOCALAPPDATA", "")
_APPDATA   = os.environ.get("APPDATA", "")

# (browser_key, user_data_dir, exe_candidates)
_BROWSER_DEFS: List[Tuple[str, Path, List[Path]]] = [
    (
        "chrome",
        Path(_LAPPDATA) / "Google" / "Chrome" / "User Data",
        [
            Path(os.environ.get("PROGRAMFILES",    "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
            Path(_LAPPDATA) / "Google/Chrome/Application/chrome.exe",
        ],
    ),
    (
        "edge",
        Path(_LAPPDATA) / "Microsoft" / "Edge" / "User Data",
        [
            Path(os.environ.get("PROGRAMFILES",    "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        ],
    ),
    (
        "brave",
        Path(_LAPPDATA) / "BraveSoftware" / "Brave-Browser" / "User Data",
        [
            Path(os.environ.get("PROGRAMFILES",    "")) / "BraveSoftware/Brave-Browser/Application/brave.exe",
            Path(_LAPPDATA) / "BraveSoftware/Brave-Browser/Application/brave.exe",
        ],
    ),
]

# Process names that signal a Chromium browser is running
_PROCESS_MAP: Dict[str, str] = {
    "chrome.exe":  "chrome",
    "msedge.exe":  "edge",
    "brave.exe":   "brave",
}

# Domain tokens per platform
_PLATFORM_DOMAINS: Dict[str, List[str]] = {
    "instagram": ["instagram.com"],
    "facebook":  ["facebook.com"],
    "tiktok":    ["tiktok.com"],
    "youtube":   ["youtube.com", "google.com"],
    "twitter":   ["twitter.com", "x.com"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: AES key from Local State
# ─────────────────────────────────────────────────────────────────────────────

def _get_aes_key(user_data_dir: Path, cb: DebugCb = None) -> Optional[bytes]:
    local_state_path = user_data_dir / "Local State"
    if not local_state_path.exists():
        _dbg(cb, f"[WF1] Local State not found: {local_state_path}")
        return None
    try:
        with open(str(local_state_path), "r", encoding="utf-8") as f:
            local_state = json.load(f)
        b64_key = local_state.get("os_crypt", {}).get("encrypted_key", "")
        if not b64_key:
            _dbg(cb, "[WF1] No encrypted_key in Local State")
            return None
        encrypted_key = base64.b64decode(b64_key)
        if encrypted_key[:5] == b"DPAPI":
            encrypted_key = encrypted_key[5:]
        key = _dpapi_decrypt(encrypted_key)
        if key:
            _dbg(cb, f"[WF1] AES key decrypted OK ({len(key)} bytes)")
        else:
            _dbg(cb, "[WF1] DPAPI key decryption failed")
        return key
    except Exception as e:
        _dbg(cb, f"[WF1] AES key error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Profile list
# ─────────────────────────────────────────────────────────────────────────────

def _list_profiles(user_data_dir: Path) -> List[str]:
    profiles: List[str] = []
    for candidate in ["Default", "Profile 1", "Profile 2", "Profile 3"]:
        db = user_data_dir / candidate / "Network" / "Cookies"
        if not db.exists():
            db = user_data_dir / candidate / "Cookies"
        if db.exists():
            profiles.append(candidate)
    return profiles or ["Default"]


# ─────────────────────────────────────────────────────────────────────────────
# Helper: domain filter
# ─────────────────────────────────────────────────────────────────────────────

def _domain_ok(host_key: str, platform_key: str) -> bool:
    domains = _PLATFORM_DOMAINS.get(platform_key, [])
    if not domains:
        return True
    hk = (host_key or "").lower().lstrip(".")
    return any(d in hk for d in domains)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Chrome timestamp → Unix
# ─────────────────────────────────────────────────────────────────────────────

def _chrome_ts(ts: int) -> int:
    if not ts or ts <= 0:
        return 0
    return max(0, (ts - 11_644_473_600_000_000) // 1_000_000)


# ─────────────────────────────────────────────────────────────────────────────
# Core DB read (copy-then-read, bypasses lock)
# ─────────────────────────────────────────────────────────────────────────────

def _read_db(db_path: Path, aes_key: Optional[bytes], platform_key: str,
             cb: DebugCb = None) -> List[Dict]:
    if not db_path.exists():
        _dbg(cb, f"[WF1]   DB not found: {db_path}")
        return []

    _dbg(cb, f"[WF1]   Copying DB: {db_path.name} ...")
    temp_db: Optional[str] = None
    try:
        fd, temp_db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        shutil.copy2(str(db_path), temp_db)
        _dbg(cb, f"[WF1]   DB copy OK ({os.path.getsize(temp_db):,} bytes)")

        # NOTE: Do NOT use sqlite3 URI mode here.
        # URI format breaks when the path contains spaces (e.g. "toseeq ur rehman").
        # Since temp_db is already a copy we own, plain connect is safe.
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        cur.execute(
            "SELECT host_key, name, encrypted_value, path, expires_utc, is_secure "
            "FROM cookies"
        )
        rows = cur.fetchall()
        conn.close()
        _dbg(cb, f"[WF1]   Total rows in DB: {len(rows)}")

        cookies: List[Dict] = []
        skipped_domain = 0
        skipped_decrypt = 0
        for row in rows:
            host_key = row["host_key"] or ""
            if not _domain_ok(host_key, platform_key):
                skipped_domain += 1
                continue
            value = _decrypt_value(bytes(row["encrypted_value"] or b""), aes_key)
            if not value:
                skipped_decrypt += 1
                continue
            cookies.append({
                "host_key":   host_key,
                "name":       row["name"] or "",
                "value":      value,
                "path":       row["path"] or "/",
                "expires_ts": _chrome_ts(row["expires_utc"] or 0),
                "is_secure":  bool(row["is_secure"]),
            })

        if skipped_decrypt > 0 and not cookies:
            _dbg(cb, f"[WF1]   WARNING: {skipped_decrypt} cookies failed decryption (AES key wrong/missing or Chrome v20 App-Bound?)")
        _dbg(cb, f"[WF1]   Decrypted {len(cookies)} {platform_key} cookies (skipped: {skipped_domain} domain, {skipped_decrypt} decrypt)")
        return cookies

    except Exception as exc:
        _dbg(cb, f"[WF1]   DB read error: {exc}")
        return []
    finally:
        if temp_db:
            try:
                os.unlink(temp_db)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Write Netscape cookie file
# ─────────────────────────────────────────────────────────────────────────────

def _write_netscape(cookies: List[Dict], label: str,
                    save_to: Optional[Path] = None, cb: DebugCb = None) -> Optional[str]:
    if not cookies:
        return None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(f"# Source: {label}\n\n")
            for c in cookies:
                flag   = "TRUE"  if c["host_key"].startswith(".") else "FALSE"
                secure = "TRUE"  if c["is_secure"] else "FALSE"
                f.write(
                    f"{c['host_key']}\t{flag}\t{c['path']}\t"
                    f"{secure}\t{c['expires_ts']}\t{c['name']}\t{c['value']}\n"
                )
        _dbg(cb, f"[WF1]   Temp cookie file written: {Path(tmp).name}")

        if save_to:
            try:
                save_to.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(tmp, str(save_to))
                _dbg(cb, f"[WF1]   Saved → {save_to.name}")
            except Exception as e:
                _dbg(cb, f"[WF1]   Save warning: {e}")

        return tmp
    except Exception as exc:
        _dbg(cb, f"[WF1]   Write error: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Detect running browsers
# ─────────────────────────────────────────────────────────────────────────────

def detect_running_browsers(cb: DebugCb = None) -> List[str]:
    """Return list of browser keys (e.g. ['chrome', 'edge']) that are running."""
    found: List[str] = []
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        output_lower = result.stdout.lower()
        for proc, browser_key in _PROCESS_MAP.items():
            if proc in output_lower:
                found.append(browser_key)
    except Exception as e:
        _dbg(cb, f"[WF1] tasklist error: {e}")

    if found:
        _dbg(cb, f"[WF1] Running browsers: {found}")
    else:
        _dbg(cb, "[WF1] No browser currently running")
    return found


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Get default/last-used browser from Windows registry
# ─────────────────────────────────────────────────────────────────────────────

def get_default_browser_windows(cb: DebugCb = None) -> Optional[str]:
    """Read Windows registry to find the default (last used) browser."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice",
        )
        prog_id, _ = winreg.QueryValueEx(key, "ProgId")
        winreg.CloseKey(key)
        p = prog_id.lower()
        if   "chrome" in p:             browser = "chrome"
        elif "edge"   in p or "msedge" in p: browser = "edge"
        elif "brave"  in p:             browser = "brave"
        elif "firefox" in p:            browser = "firefox"
        else:                           browser = None
        _dbg(cb, f"[WF1] Registry default browser: {browser or prog_id}")
        return browser
    except Exception:
        pass

    # Fallback: first installed browser
    for key, user_data, _ in _BROWSER_DEFS:
        if user_data.exists():
            _dbg(cb, f"[WF1] Fallback: first installed browser = {key}")
            return key
    _dbg(cb, "[WF1] No default browser found in registry")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Find browser executable
# ─────────────────────────────────────────────────────────────────────────────

def _find_exe(browser_key: str) -> Optional[Path]:
    for key, _, exes in _BROWSER_DEFS:
        if key == browser_key:
            for exe in exes:
                if exe.exists():
                    return exe
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Launch browser, wait for session load, extract cookies
# ─────────────────────────────────────────────────────────────────────────────

def _launch_and_extract(
    browser_key: str,
    platform_key: str,
    save_to: Optional[Path],
    cb: DebugCb = None,
) -> Optional[str]:
    """
    Open a browser in the background (minimized, no first-run prompts),
    wait for the session to load, copy the DB, decrypt, return cookie file.
    """
    exe = _find_exe(browser_key)
    if not exe:
        _dbg(cb, f"[WF1] {browser_key} executable not found – cannot launch")
        return None

    _dbg(cb, f"[WF1] Launching {browser_key} (minimized) to load session...")
    try:
        subprocess.Popen(
            [str(exe), "--no-first-run", "--no-default-browser-check",
             "--start-minimized", "--window-position=-32000,-32000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except Exception as e:
        _dbg(cb, f"[WF1] Launch failed: {e}")
        return None

    _dbg(cb, "[WF1] Waiting 5s for browser session to load...")
    time.sleep(5)

    result = _extract_from_browser(browser_key, platform_key, save_to, cb)
    if result:
        _dbg(cb, f"[WF1] Successfully extracted cookies after launching {browser_key}")
    else:
        _dbg(cb, f"[WF1] No cookies found even after launching {browser_key}")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Core: extract from one browser (copy DB → decrypt)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_from_browser(
    browser_key: str,
    platform_key: str,
    save_to: Optional[Path],
    cb: DebugCb = None,
) -> Optional[str]:
    user_data_dir: Optional[Path] = None
    for key, ud, _ in _BROWSER_DEFS:
        if key == browser_key:
            user_data_dir = ud
            break
    if not user_data_dir or not user_data_dir.exists():
        _dbg(cb, f"[WF1]   {browser_key} user data dir not found")
        return None

    aes_key  = _get_aes_key(user_data_dir, cb)
    profiles = _list_profiles(user_data_dir)
    _dbg(cb, f"[WF1]   Profiles found: {profiles}")

    for profile in profiles:
        _dbg(cb, f"[WF1]   Trying profile: {profile}")
        db_path = user_data_dir / profile / "Network" / "Cookies"
        if not db_path.exists():
            db_path = user_data_dir / profile / "Cookies"
        if not db_path.exists():
            _dbg(cb, f"[WF1]   No Cookies DB in {profile}")
            continue

        cookies = _read_db(db_path, aes_key, platform_key, cb)
        if not cookies:
            _dbg(cb, f"[WF1]   No {platform_key} cookies in {profile}")
            continue

        label = f"{browser_key}:{profile}"
        result = _write_netscape(cookies, label, save_to, cb)
        if result:
            return result

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Phase 0 — Chrome DevTools Protocol (CDP)
# Works for Chrome 127+ App-Bound Encrypted (v20) cookies.
# Requires Chrome to be running with --remote-debugging-port=PORT
# OR we relaunch Chrome with that flag (restore-last-session keeps all tabs).
# ─────────────────────────────────────────────────────────────────────────────

_CDP_PORTS = [9222, 9223, 9224, 9229]


def _ws_send_recv(ws_url: str, method: str, params: Optional[dict] = None,
                  timeout: float = 8.0) -> Optional[dict]:
    """
    Minimal stdlib WebSocket client for a single CDP request.
    Connects to ws_url, sends one JSON command, returns the matching response.
    """
    params = params or {}
    # Parse ws://host:port/path
    url = ws_url.replace("ws://", "").replace("wss://", "")
    if "/" in url:
        host_port, path = url.split("/", 1)
        path = "/" + path
    else:
        host_port, path = url, "/"
    host, port_str = (host_port.split(":", 1) + ["80"])[:2]
    port = int(port_str)

    try:
        sock = socket.create_connection((host, port), timeout=3)
    except (ConnectionRefusedError, OSError):
        return None

    # HTTP Upgrade handshake
    key = base64.b64encode(os.urandom(16)).decode()
    handshake = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode()
    sock.sendall(handshake)

    # Read response headers
    resp = b""
    try:
        while b"\r\n\r\n" not in resp:
            chunk = sock.recv(4096)
            if not chunk:
                break
            resp += chunk
    except Exception:
        sock.close()
        return None

    if b"101" not in resp:
        sock.close()
        return None

    # Send CDP command as masked text frame
    cmd_bytes = json.dumps({"id": 1, "method": method, "params": params}).encode()
    mask = os.urandom(4)
    n = len(cmd_bytes)
    if n < 126:
        hdr = bytearray([0x81, 0x80 | n])
    elif n < 65536:
        hdr = bytearray([0x81, 0xFE]) + bytearray(struct.pack(">H", n))
    else:
        hdr = bytearray([0x81, 0xFF]) + bytearray(struct.pack(">Q", n))
    hdr.extend(mask)
    sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(cmd_bytes)))

    # Read response frames until we find id=1 result
    sock.settimeout(timeout)
    buf = b""
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk

            # Parse all complete frames from buf
            pos = 0
            while pos < len(buf):
                if pos + 2 > len(buf):
                    break
                b0, b1 = buf[pos], buf[pos + 1]
                masked = bool(b1 & 0x80)
                length = b1 & 0x7F
                offset = pos + 2
                if length == 126:
                    if offset + 2 > len(buf):
                        break
                    length = struct.unpack(">H", buf[offset:offset + 2])[0]
                    offset += 2
                elif length == 127:
                    if offset + 8 > len(buf):
                        break
                    length = struct.unpack(">Q", buf[offset:offset + 8])[0]
                    offset += 8
                mk = b""
                if masked:
                    if offset + 4 > len(buf):
                        break
                    mk = buf[offset:offset + 4]
                    offset += 4
                if offset + length > len(buf):
                    break
                payload = buf[offset:offset + length]
                if masked:
                    payload = bytes(b ^ mk[i % 4] for i, b in enumerate(payload))
                pos = offset + length
                try:
                    msg = json.loads(payload.decode("utf-8", errors="replace"))
                    if msg.get("id") == 1 and "result" in msg:
                        sock.close()
                        return msg
                except Exception:
                    pass
            buf = buf[pos:]
    except Exception:
        pass
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return None


def _cdp_get_cookies(port: int, platform_key: str, cb: DebugCb = None) -> List[Dict]:
    """Extract cookies from Chrome/Edge via CDP on the given port."""
    try:
        conn = http.client.HTTPConnection("localhost", port, timeout=2)
        conn.request("GET", "/json/list")
        resp = conn.getresponse()
        if resp.status != 200:
            return []
        targets = json.loads(resp.read().decode())
    except Exception:
        return []

    # Prefer a page target; fall back to /json/version browser target
    ws_url = ""
    for t in (targets or []):
        if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
            ws_url = t["webSocketDebuggerUrl"]
            break
    if not ws_url:
        try:
            conn2 = http.client.HTTPConnection("localhost", port, timeout=2)
            conn2.request("GET", "/json/version")
            resp2 = conn2.getresponse()
            v = json.loads(resp2.read().decode())
            ws_url = v.get("webSocketDebuggerUrl", "")
        except Exception:
            pass
    if not ws_url:
        _dbg(cb, f"[WF1] CDP port {port}: no WebSocket URL")
        return []

    _dbg(cb, f"[WF1] CDP port {port}: connecting to {ws_url[:60]}...")
    result = _ws_send_recv(ws_url, "Network.getAllCookies", timeout=8.0)
    if not result:
        _dbg(cb, f"[WF1] CDP port {port}: no response to getAllCookies")
        return []

    raw = result.get("result", {}).get("cookies", [])
    cookies: List[Dict] = []
    for c in raw:
        domain = c.get("domain", "")
        if not _domain_ok(domain, platform_key):
            continue
        exp = c.get("expires", -1)
        cookies.append({
            "host_key":   domain,
            "name":       c.get("name", ""),
            "value":      c.get("value", ""),
            "path":       c.get("path", "/"),
            "expires_ts": int(exp) if exp and exp > 0 else 0,
            "is_secure":  bool(c.get("secure", False)),
        })
    _dbg(cb, f"[WF1] CDP port {port}: {len(cookies)} {platform_key or 'any'} cookies")
    return cookies


def _extract_via_cdp(
    platform_key: str,
    save_to: Optional[Path],
    cb: DebugCb = None,
) -> Optional[str]:
    """Phase 0: Extract cookies via Chrome DevTools Protocol (CDP)."""
    _dbg(cb, "[WF1] PHASE 0: Checking for Chrome with remote debugging...")
    for port in _CDP_PORTS:
        try:
            # Quick check: is anything listening on this port?
            s = socket.create_connection(("localhost", port), timeout=0.5)
            s.close()
        except (ConnectionRefusedError, OSError, socket.timeout):
            continue

        _dbg(cb, f"[WF1] Found service on port {port} – trying CDP...")
        cookies = _cdp_get_cookies(port, platform_key, cb)
        if cookies:
            _dbg(cb, f"[WF1] ✓ CDP: {len(cookies)} cookies from port {port}")
            return _write_netscape(cookies, f"cdp:localhost:{port}", save_to, cb)
        _dbg(cb, f"[WF1] CDP port {port}: no matching cookies")
    return None


def _relaunch_chrome_with_cdp(
    browser_key: str,
    platform_key: str,
    save_to: Optional[Path],
    cb: DebugCb = None,
) -> Optional[str]:
    """
    Close Chrome and relaunch with --remote-debugging-port=9222
    + --restore-last-session so all tabs come back.
    Used as last-resort when Chrome v20 App-Bound blocks all other methods.
    """
    exe = _find_exe(browser_key)
    if not exe:
        _dbg(cb, f"[WF1] {browser_key} exe not found – cannot relaunch")
        return None

    _dbg(cb, f"[WF1] Relaunching {browser_key} with CDP debug port (will restore all tabs)...")

    # Close existing Chrome instance gracefully
    proc_name = {"chrome": "chrome.exe", "edge": "msedge.exe", "brave": "brave.exe"}.get(browser_key)
    if proc_name:
        try:
            subprocess.run(["taskkill", "/F", "/IM", proc_name], capture_output=True, timeout=10)
            _dbg(cb, f"[WF1] Closed {proc_name}")
            time.sleep(2)
        except Exception as e:
            _dbg(cb, f"[WF1] Could not close {proc_name}: {e}")

    # Launch with CDP debug port + restore session
    try:
        subprocess.Popen(
            [str(exe),
             "--remote-debugging-port=9222",
             "--restore-last-session",
             "--no-first-run",
             "--no-default-browser-check"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        _dbg(cb, f"[WF1] Relaunch failed: {e}")
        return None

    _dbg(cb, "[WF1] Waiting for Chrome to start with CDP debug port...")
    for attempt in range(12):
        time.sleep(2)
        try:
            s = socket.create_connection(("localhost", 9222), timeout=1)
            s.close()
            _dbg(cb, "[WF1] CDP port 9222 is now open!")
            time.sleep(2)  # Let session fully load
            result = _extract_via_cdp(platform_key, save_to, cb)
            if result:
                return result
        except (ConnectionRefusedError, OSError):
            _dbg(cb, f"[WF1] Still waiting... ({attempt + 1}/12)")

    _dbg(cb, "[WF1] CDP debug port did not open in time")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1.5 — browser_cookie3 (handles locked DB + some Chrome v20 cookies)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_via_browser_cookie3(
    browser_key: str,
    platform_key: str,
    save_to: Optional[Path],
    cb: DebugCb = None,
) -> Optional[str]:
    """
    Use browser_cookie3 library to extract cookies.
    It handles the locked Chrome SQLite DB via Windows Shadow Copy (VSS),
    and may return v10/v11 session cookies even when Chrome 127+ is running.
    """
    try:
        import browser_cookie3  # type: ignore
    except ImportError:
        _dbg(cb, "[WF1]   browser_cookie3 not installed – skipping")
        return None

    _dbg(cb, f"[WF1]   browser_cookie3: trying {browser_key}...")

    # Map our key to browser_cookie3 function
    bc3_fn = getattr(browser_cookie3, browser_key, None)
    if bc3_fn is None:
        _dbg(cb, f"[WF1]   browser_cookie3 has no handler for {browser_key}")
        return None

    domains = _PLATFORM_DOMAINS.get(platform_key, [])
    domain_filter = domains[0] if domains else None

    try:
        if domain_filter:
            jar = bc3_fn(domain_name=domain_filter)
        else:
            jar = bc3_fn()

        cookies: List[Dict] = []
        for c in jar:
            cookies.append({
                "host_key":   c.domain or "",
                "name":       c.name or "",
                "value":      c.value or "",
                "path":       c.path or "/",
                "expires_ts": int(c.expires) if c.expires else 0,
                "is_secure":  bool(c.secure),
            })

        if not cookies:
            _dbg(cb, f"[WF1]   browser_cookie3: no {platform_key or 'any'} cookies in {browser_key}")
            return None

        _dbg(cb, f"[WF1]   browser_cookie3: {len(cookies)} cookies from {browser_key}")
        return _write_netscape(cookies, f"bc3:{browser_key}", save_to, cb)

    except Exception as exc:
        # browser_cookie3 may raise BrowserCookieError for Chrome v20 App-Bound
        _dbg(cb, f"[WF1]   browser_cookie3 error: {exc}")
        return None


def _bc3_all_cookies(browser_key: str, cb: DebugCb = None) -> List[Dict]:
    """Return ALL cookies from a browser via browser_cookie3 (no domain filter)."""
    try:
        import browser_cookie3  # type: ignore
    except ImportError:
        return []
    bc3_fn = getattr(browser_cookie3, browser_key, None)
    if not bc3_fn:
        return []
    try:
        jar = bc3_fn()
        result = []
        for c in jar:
            result.append({
                "host_key":   c.domain or "",
                "name":       c.name or "",
                "value":      c.value or "",
                "path":       c.path or "/",
                "expires_ts": int(c.expires) if c.expires else 0,
                "is_secure":  bool(c.secure),
            })
        return result
    except Exception as exc:
        _dbg(cb, f"[WF1]   bc3 all-cookies error ({browser_key}): {exc}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Validate existing cookie file (skip re-extraction if still valid)
# ─────────────────────────────────────────────────────────────────────────────

# Session cookies that prove a logged-in state for each platform
_KEY_COOKIES_BY_PLATFORM: Dict[str, List[str]] = {
    "instagram": ["sessionid"],
    "facebook":  ["c_user", "xs"],
    "youtube":   ["LOGIN_INFO", "SID", "HSID", "__Secure-1PSID"],
    "tiktok":    ["sessionid", "tt-target-idc"],
    "twitter":   ["auth_token", "ct0"],
}


def _validate_existing_cookies(save_path: Path, cb: DebugCb = None) -> bool:
    """
    Return True if the existing cookie file has at least one platform's
    key session cookies that are present and not expired.
    """
    if not save_path.exists() or save_path.stat().st_size < 100:
        _dbg(cb, "[WF1] No existing cookie file (or empty)")
        return False

    try:
        now = int(time.time())
        cookies_by_platform: Dict[str, set] = {}

        with open(str(save_path), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                host_key  = parts[0]
                expires_s = parts[4]
                name      = parts[5]

                # Skip expired (0 = session cookie → keep)
                try:
                    exp = int(expires_s)
                    if exp > 0 and exp < now:
                        continue
                except (ValueError, TypeError):
                    pass

                for platform, domains in _PLATFORM_DOMAINS.items():
                    if any(d in host_key for d in domains):
                        cookies_by_platform.setdefault(platform, set()).add(name)

        found_valid = False
        for platform, key_names in _KEY_COOKIES_BY_PLATFORM.items():
            present = cookies_by_platform.get(platform, set())
            matched = [k for k in key_names if k in present]
            if matched:
                _dbg(cb, f"[WF1] Cookie check ✓ {platform}: {matched}")
                found_valid = True
            else:
                _dbg(cb, f"[WF1] Cookie check ✗ {platform}: need one of {key_names}")

        return found_valid

    except Exception as exc:
        _dbg(cb, f"[WF1] Cookie validation error: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Detect all Chrome user-data-dir paths from running process cmdlines
# ─────────────────────────────────────────────────────────────────────────────

def _detect_chrome_user_data_dirs(cb: DebugCb = None) -> List[Path]:
    """
    Parse cmdlines of ALL running chrome.exe processes to find each
    --user-data-dir argument.  Falls back to the standard Chrome user data dir.
    This handles multiple Chrome instances (e.g. regular + work profile).
    """
    import re as _re
    dirs: List[Path] = []
    default_ud = Path(_LAPPDATA) / "Google" / "Chrome" / "User Data"

    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='chrome.exe'",
             "get", "CommandLine", "/FORMAT:CSV"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "--user-data-dir=" not in line:
                continue
            m = _re.search(r'--user-data-dir=(?:"([^"]+)"|(\S+))', line)
            if m:
                ud = Path(m.group(1) or m.group(2))
                if ud.exists() and ud not in dirs:
                    dirs.append(ud)
                    _dbg(cb, f"[WF1] Chrome instance user-data-dir: {ud.name}")
    except Exception as exc:
        _dbg(cb, f"[WF1] WMIC cmdline scan error: {exc}")

    # Always include the standard Chrome dir as final candidate
    if default_ud.exists() and default_ud not in dirs:
        dirs.append(default_ud)

    return dirs


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def extract_cookies_smart(
    platform_key: str,
    save_to: Optional[Path] = None,
    preferred_browser: Optional[str] = None,
    cb: DebugCb = None,
) -> Optional[str]:
    """
    Workflow 1 full decision chain:

      1. Detect running browsers → try those first (copy locked DB)
      2. No running browser with cookies → read closed DB directly (no lock)
      3. Still nothing → open default/last-used browser from registry → wait → copy DB
      4. Save to save_to (usually cookies/chrome_cookies.txt)

    Returns path to temp Netscape cookie file, or None.
    """
    _dbg(cb, "=" * 48)
    _dbg(cb, f"[WF1] Smart cookie extraction for: {platform_key}")
    _dbg(cb, "=" * 48)

    # ── Build ordered browser list ──────────────────────────────────────────
    order: List[str] = []
    if preferred_browser and preferred_browser.lower() in {k for k, _, _ in _BROWSER_DEFS}:
        order.append(preferred_browser.lower())
    for key, _, _ in _BROWSER_DEFS:
        if key not in order:
            order.append(key)

    # ── PHASE 0: CDP (Chrome DevTools Protocol) ───────────────────────────────
    # Works for Chrome 127+ App-Bound Encryption (v20) when Chrome was launched
    # with --remote-debugging-port.  Zero-overhead check if no port is open.
    result = _extract_via_cdp(platform_key, save_to, cb)
    if result:
        _dbg(cb, "[WF1] ✓ Cookies extracted via CDP")
        return result

    # ── PHASE 1: running browsers ────────────────────────────────────────────
    _dbg(cb, "[WF1] PHASE 1: Checking running browsers...")
    running = detect_running_browsers(cb)
    running_in_order = [b for b in order if b in running]

    for browser_key in running_in_order:
        _dbg(cb, f"[WF1] Trying running browser: {browser_key}")
        result = _extract_from_browser(browser_key, platform_key, save_to, cb)
        if result:
            _dbg(cb, f"[WF1] ✓ Cookies extracted from running {browser_key}")
            return result
        _dbg(cb, f"[WF1] {browser_key}: no {platform_key} cookies via DB copy (Chrome 127+ v20 App-Bound?)")

    # ── PHASE 1.5: browser_cookie3 (handles locked DB + some v20 cases) ─────
    _dbg(cb, "[WF1] PHASE 1.5: Trying browser_cookie3 library...")
    bc3_browsers = running_in_order if running_in_order else order[:2]
    for browser_key in bc3_browsers:
        result = _extract_via_browser_cookie3(browser_key, platform_key, save_to, cb)
        if result:
            _dbg(cb, f"[WF1] ✓ Cookies extracted via browser_cookie3 from {browser_key}")
            return result

    # ── PHASE 2: closed browsers (no lock – read directly) ──────────────────
    _dbg(cb, "[WF1] PHASE 2: Trying closed browsers (no file lock)...")
    not_running = [b for b in order if b not in running]

    for browser_key in not_running:
        _dbg(cb, f"[WF1] Trying closed browser: {browser_key}")
        result = _extract_from_browser(browser_key, platform_key, save_to, cb)
        if result:
            _dbg(cb, f"[WF1] ✓ Cookies extracted from closed {browser_key}")
            return result
        _dbg(cb, f"[WF1] {browser_key}: no cookies found")

    # ── PHASE 3: no browser has cookies → launch default browser ────────────
    _dbg(cb, "[WF1] PHASE 3: No cookies found. Checking registry for default browser...")
    default_browser = get_default_browser_windows(cb)

    if default_browser:
        if default_browser in running:
            _dbg(cb, f"[WF1] {default_browser} already tried (was running). Skipping re-launch.")
        else:
            _dbg(cb, f"[WF1] Launching default browser ({default_browser}) to refresh session...")
            result = _launch_and_extract(default_browser, platform_key, save_to, cb)
            if result:
                return result
    else:
        _dbg(cb, "[WF1] No default browser detected – cannot auto-launch")

    # ── PHASE 3b: CDP relaunch (v20 App-Bound last resort) ───────────────────
    # Chrome 127+ App-Bound Encryption cannot be bypassed any other way.
    # Kill the running Chrome and relaunch with --remote-debugging-port=9222
    # and --restore-last-session so ALL tabs come back automatically.
    #
    # Priority: Chrome running > any other running browser > registry default.
    # We do NOT blindly use get_default_browser_windows() here — it reads the
    # Windows registry which may return Edge even when Chrome is running.
    if "chrome" in running:
        cdp_browser = "chrome"
    elif running:
        cdp_browser = running[0]
    elif default_browser:
        cdp_browser = default_browser
    else:
        cdp_browser = None

    if cdp_browser:
        _dbg(cb, f"[WF1] PHASE 3b: Chrome v20 workaround – relaunching {cdp_browser} with CDP...")
        _dbg(cb, "[WF1] Chrome will restart. All your tabs will be restored automatically.")
        result = _relaunch_chrome_with_cdp(cdp_browser, platform_key, save_to, cb)
        if result:
            _dbg(cb, "[WF1] ✓ Cookies extracted via CDP relaunch")
            return result

    _dbg(cb, "[WF1] ✗ All phases exhausted – no cookies obtained")
    _dbg(cb, "[WF1] TIP: Chrome 127+ uses App-Bound Encryption (v20) that blocks external extraction.")
    _dbg(cb, "[WF1] TIP: Upload your cookies manually using a browser extension (Cookie-Editor, EditThisCookie).")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: extract_cookies_db_copy (backward-compat alias)
# ─────────────────────────────────────────────────────────────────────────────

def extract_cookies_db_copy(
    platform_key: str,
    preferred_browser: Optional[str] = None,
    save_to: Optional[Path] = None,
    debug_cb: DebugCb = None,
) -> Optional[str]:
    """Backward-compatible alias for extract_cookies_smart."""
    return extract_cookies_smart(
        platform_key=platform_key,
        save_to=save_to,
        preferred_browser=preferred_browser,
        cb=debug_cb,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Master extract: all platforms at once → single chrome_cookies.txt
# ─────────────────────────────────────────────────────────────────────────────

def extract_all_platforms_to_master(save_path: Path, cb: DebugCb = None) -> bool:
    """
    Extract cookies for ALL platforms from the best available browser
    and save as a single master chrome_cookies.txt.

    Priority:
      0. Skip entirely if existing cookie file already has valid session cookies.
      1. CDP on already-running Chrome with debug port (zero-overhead check).
      2. DB copy from all running Chrome user-data-dirs (DPAPI+AES v10/v11).
      3. browser_cookie3 fallback.
      4. CDP relaunch: kill running Chrome → relaunch with --remote-debugging-port
         (handles Chrome 127+ v20 App-Bound Encryption — restores all tabs).
    """
    _dbg(cb, "[WF1] ══════════════════════════════════")
    _dbg(cb, "[WF1] Master cookie extraction: START")
    _dbg(cb, "[WF1] ══════════════════════════════════")

    # ── Pre-check: validate existing cookies ─────────────────────────────────
    _dbg(cb, f"[WF1] Checking existing cookies: {save_path.name} ...")
    if _validate_existing_cookies(save_path, cb):
        _dbg(cb, "[WF1] ✓ Existing cookies are valid — skipping re-extraction")
        return True
    _dbg(cb, "[WF1] Existing cookies missing/expired/invalid — starting extraction...")

    running = detect_running_browsers(cb)
    all_cookies: List[Dict] = []

    # ── Phase 0: CDP (Chrome DevTools Protocol) ───────────────────────────────
    # Handles Chrome 127+ App-Bound Encryption (v20).
    # Zero-overhead if no debug port is open.
    _dbg(cb, "[WF1] PHASE 0: Checking for Chrome DevTools Protocol (CDP)...")
    for port in _CDP_PORTS:
        try:
            s = socket.create_connection(("localhost", port), timeout=0.5)
            s.close()
        except (ConnectionRefusedError, OSError, socket.timeout):
            continue
        _dbg(cb, f"[WF1] CDP port {port} is open — extracting ALL cookies...")
        cdp_cookies = _cdp_get_cookies(port, "", cb)  # "" = no platform filter
        if cdp_cookies:
            _dbg(cb, f"[WF1] CDP: {len(cdp_cookies)} total cookies")
            all_cookies.extend(cdp_cookies)
            break

    if all_cookies:
        seen: set = set()
        deduped = [c for c in all_cookies
                   if (k := (c["host_key"], c["name"])) not in seen and not seen.add(k)]
        _dbg(cb, f"[WF1] Master (CDP): {len(deduped)} unique cookies")
        result = _write_netscape(deduped, "master-cdp", save_path, cb)
        return bool(result)

    # ── Phase 1+: DB copy (DPAPI+AES — works for v10/v11, not v20) ───────────
    _dbg(cb, "[WF1] PHASE 1: DB copy from running browsers...")

    def _collect_from_ud(user_data_dir: Path, label: str) -> None:
        if not user_data_dir.exists():
            return
        aes_key  = _get_aes_key(user_data_dir, cb)
        profiles = _list_profiles(user_data_dir)
        for profile in profiles:
            db_path = user_data_dir / profile / "Network" / "Cookies"
            if not db_path.exists():
                db_path = user_data_dir / profile / "Cookies"
            if not db_path.exists():
                continue
            cookies = _read_db(db_path, aes_key, "", cb)
            all_cookies.extend(cookies)
            _dbg(cb, f"[WF1] {label}:{profile} → {len(cookies)} cookies")

    seen_browsers: set = set()

    # For Chrome: detect all running instances (multiple user-data-dirs)
    if "chrome" in running:
        chrome_ud_dirs = _detect_chrome_user_data_dirs(cb)
        _dbg(cb, f"[WF1] Chrome: {len(chrome_ud_dirs)} user-data-dir(s) found")
        for ud in chrome_ud_dirs:
            _collect_from_ud(ud, f"chrome({ud.parent.name})")
        seen_browsers.add("chrome")

    # Other running browsers (Edge, Brave) — standard path
    for browser_key in running:
        if browser_key in seen_browsers:
            continue
        seen_browsers.add(browser_key)
        user_data_dir = next((ud for k, ud, _ in _BROWSER_DEFS if k == browser_key), None)
        if user_data_dir:
            _collect_from_ud(user_data_dir, browser_key)

    # If nothing running, try all installed browsers
    if not running:
        for browser_key, user_data_dir, _ in _BROWSER_DEFS:
            if browser_key not in seen_browsers:
                seen_browsers.add(browser_key)
                _collect_from_ud(user_data_dir, browser_key)

    if not all_cookies:
        _dbg(cb, "[WF1] DB copy: 0 cookies (Chrome 127+ v20 App-Bound Encryption?)")
        _dbg(cb, "[WF1] PHASE 1.5: Trying browser_cookie3 library...")
        seen_bc3: set = set()
        for browser_key in (running or [k for k, _, _ in _BROWSER_DEFS]):
            if browser_key in seen_bc3:
                continue
            seen_bc3.add(browser_key)
            bc3_cookies = _bc3_all_cookies(browser_key, cb)
            if bc3_cookies:
                _dbg(cb, f"[WF1] browser_cookie3 {browser_key}: {len(bc3_cookies)} cookies")
                all_cookies.extend(bc3_cookies)

    if not all_cookies:
        # ── Phase 3b: CDP relaunch (v20 App-Bound last resort) ────────────────
        # Kill the running Chrome, relaunch with --remote-debugging-port=9222
        # and --restore-last-session so ALL tabs come back.
        #
        # Priority: Chrome running > other running browser > registry default.
        # We do NOT use get_default_browser_windows() here — that reads the
        # Windows registry which may return Edge even when Chrome is running.
        _dbg(cb, "[WF1] PHASE 3b: Attempting CDP relaunch for Chrome v20 workaround...")

        if "chrome" in running:
            cdp_browser = "chrome"
        elif running:
            cdp_browser = running[0]
        else:
            # Nothing running — fall back to registry default
            cdp_browser = get_default_browser_windows(cb)

        if cdp_browser:
            _dbg(cb, f"[WF1] CDP relaunch target: {cdp_browser}")
            _dbg(cb, "[WF1] Chrome will restart and restore all tabs automatically...")
            cdp_result = _relaunch_chrome_with_cdp(cdp_browser, "", save_path, cb)
            if cdp_result:
                _dbg(cb, f"[WF1] ✓ Master (Phase 3b CDP): cookies saved → {save_path.name}")
                return True
            _dbg(cb, "[WF1] Phase 3b CDP relaunch yielded no cookies")
        else:
            _dbg(cb, "[WF1] Phase 3b skipped: no running or default browser detected")

    if not all_cookies:
        _dbg(cb, "[WF1] ✗ Master extract: no cookies found in any browser")
        _dbg(cb, "[WF1] TIP: Open Chrome with your platforms logged in, then click Auto-Detect again.")
        _dbg(cb, "[WF1] TIP: Or export cookies manually via Cookie-Editor / EditThisCookie extension.")
        return False

    # Deduplicate
    seen2: set = set()
    deduped2: List[Dict] = []
    for c in all_cookies:
        k = (c["host_key"], c["name"])
        if k not in seen2:
            seen2.add(k)
            deduped2.append(c)

    _dbg(cb, f"[WF1] Master: {len(deduped2)} unique cookies total")
    result = _write_netscape(deduped2, "master-all-platforms", save_path, cb)
    return bool(result)
