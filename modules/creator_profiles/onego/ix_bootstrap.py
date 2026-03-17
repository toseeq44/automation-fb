"""
IX Browser bootstrap — detect, launch, login, wait for API.

Reuses DesktopAppLauncher from auto_uploader for exe detection and process launch.
Keeps OneGo independent from the old upload engine.
"""

from __future__ import annotations

import logging
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

log = logging.getLogger(__name__)


class BootstrapResult:
    """Outcome of an IX bootstrap attempt."""

    __slots__ = ("success", "reason")

    def __init__(self, success: bool, reason: Optional[str] = None):
        self.success = success
        self.reason = reason  # None on success; SkipReason value on failure


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _parse_host_port(api_url: str) -> Tuple[str, int]:
    try:
        parsed = urlparse(api_url)
        return parsed.hostname or "127.0.0.1", parsed.port or 53200
    except Exception:
        return "127.0.0.1", 53200


def _ping_api(host: str, port: int, timeout: float = 3.0) -> bool:
    """Quick TCP check whether IX API port is reachable."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def bootstrap_ix(
    api_url: str,
    email: str = "",
    password: str = "",
    progress_cb=None,
    timeout: int = 60,
) -> BootstrapResult:
    """Ensure IX Browser API is reachable before profile listing.

    Steps
    -----
    1. Ping *api_url* host:port.
    2. If unreachable → find ixBrowser exe (common paths + registry), launch,
       wait up to 20 s for API.
    3. If still unreachable and credentials present → run IX login helper,
       wait for API again.
    4. Return ``BootstrapResult(success=True)`` or a failure with reason.

    Parameters
    ----------
    api_url : str
        IX API base URL (e.g. ``http://127.0.0.1:53200``).
    email, password : str
        IX account credentials for auto-login fallback.
    progress_cb : callable, optional
        ``progress_cb(msg: str)`` — status messages for the UI.
    timeout : int
        Max total seconds to wait for API availability.
    """

    def _emit(msg: str):
        if progress_cb:
            progress_cb(f"OneGo: {msg}")
        log.info("[OneGo-Bootstrap] %s", msg)

    host, port = _parse_host_port(api_url)

    # ── Step 1: quick ping ────────────────────────────────────────────────
    _emit(f"Checking IX API at {host}:{port}...")
    if _ping_api(host, port):
        _emit("IX API is reachable.")
        return BootstrapResult(success=True)

    # ── Step 2: attempt auto-launch ───────────────────────────────────────
    _emit("IX API unreachable — attempting to launch ixBrowser...")
    try:
        from modules.auto_uploader.approaches.ixbrowser.desktop_launcher import (
            DesktopAppLauncher,
        )
    except ImportError:
        _emit("Desktop launcher module not available.")
        return BootstrapResult(success=False, reason="api_unreachable")

    launcher = DesktopAppLauncher(
        host=host, port=port, email=email, password=password,
    )

    exe_path = launcher.find_executable()
    if not exe_path:
        _emit("ixBrowser executable not found on this machine.")
        return BootstrapResult(success=False, reason="ix_exe_not_found")

    if not launcher.launch_application(exe_path):
        _emit("Failed to start ixBrowser process.")
        return BootstrapResult(success=False, reason="ix_exe_not_found")

    # Wait for initial API availability (up to 20 s)
    _emit("ixBrowser launched — waiting for API...")
    initial_wait = min(20, timeout)
    if launcher.wait_for_api(timeout=initial_wait, check_interval=2):
        _emit("IX API is now reachable.")
        return BootstrapResult(success=True)

    # ── Step 3: auto-login fallback ───────────────────────────────────────
    if not (email and password):
        _emit("No credentials for auto-login — API still unreachable.")
        return BootstrapResult(success=False, reason="api_unreachable")

    _emit("API not ready after launch — attempting IX auto-login...")
    try:
        from modules.auto_uploader.approaches.ixbrowser.ix_login_helper import (
            IXBrowserLoginHelper,
        )

        login_helper = IXBrowserLoginHelper(email, password)
        if not login_helper.perform_login():
            _emit("IX auto-login failed.")
            return BootstrapResult(success=False, reason="ix_login_failed")

        _emit("Login sequence completed — waiting for API...")
        remaining = max(timeout - initial_wait, 30)
        if launcher.wait_for_api(timeout=remaining, check_interval=7):
            _emit("IX API is now reachable after login.")
            return BootstrapResult(success=True)

        _emit("API still unreachable after login.")
        return BootstrapResult(success=False, reason="ix_login_failed")

    except ImportError:
        _emit("IX login helper module not available.")
        return BootstrapResult(success=False, reason="ix_login_failed")
    except Exception as exc:
        _emit(f"IX login error: {exc}")
        return BootstrapResult(success=False, reason="ix_login_failed")
