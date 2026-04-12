"""
Managed Chrome CDP Session Manager.

Provides a single, process-locked Chrome instance with --remote-debugging-port
that all automation modules can attach to.  Avoids conflicting Chrome launches
by coordinating with SessionAuthority's profile-busy detection.

Feature flag: MANAGED_CDP_ATTACH_FIRST (default OFF).
When OFF, nothing in this module is activated and all existing behaviour
remains unchanged.  When ON, Link Grabber and Downloader attempt a CDP
attach to the managed Chrome before falling back to normal methods.

Architecture:
  1. ensure_running() launches Chrome with --remote-debugging-port=<port>
     using the managed browser profile (same as Re-login).
  2. Consumers call attach_selenium() or attach_playwright_cdp() to get
     a driver/page connected to the running instance.
  3. graceful_close() terminates Chrome and releases the process lock.
  4. Single-process lock (pid + timestamp) prevents two Chrome processes
     from using the same profile directory simultaneously.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import sys
from urllib.parse import urlparse

if sys.platform == "win32":
    try:
        import win32gui
        import win32process
        import win32con
    except ImportError:
        pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------
MANAGED_CDP_ATTACH_FIRST = True

# Default CDP port for the managed Chrome instance
_DEFAULT_CDP_PORT = 9250  # Avoids conflict with user Chrome on 9222-9229

# Stale lock threshold (seconds) — locks older than this are auto-cleaned
_STALE_LOCK_SECONDS = 600  # 10 minutes

# Chrome startup timeout
_CHROME_STARTUP_TIMEOUT = 20  # seconds

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_instance: Optional["ManagedChromeSessionManager"] = None
_instance_lock = threading.Lock()


def get_managed_chrome_session() -> ManagedChromeSessionManager:
    """Get or create the singleton ManagedChromeSessionManager."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ManagedChromeSessionManager()
    return _instance


# ---------------------------------------------------------------------------
# ManagedChromeSessionManager
# ---------------------------------------------------------------------------
class ManagedChromeSessionManager:
    """
    Manages a single Chrome process with --remote-debugging-port for
    automated CDP attach from Link Grabber and Downloader modules.

    Thread-safe.  Uses a file-based process lock to prevent conflicts
    with Re-login and other profile consumers.
    """

    def __init__(self) -> None:
        from modules.config.paths import get_data_dir
        from modules.shared.session_authority import get_session_authority

        self._sa = get_session_authority()
        self._data_dir = get_data_dir()
        self._profile_dir = str(Path(self._sa.profile_dir).resolve())
        self._cdp_lock_path = self._data_dir / ".managed_cdp_lock"
        self._cdp_port = _DEFAULT_CDP_PORT
        self._chrome_process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

        logger.info(
            "[ManagedCDP] Initialized. profile=%s  port=%d  flag=%s",
            self._profile_dir,
            self._cdp_port,
            "ON" if MANAGED_CDP_ATTACH_FIRST else "OFF",
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def cdp_port(self) -> int:
        return self._cdp_port

    @property
    def is_flag_enabled(self) -> bool:
        return MANAGED_CDP_ATTACH_FIRST

    # ------------------------------------------------------------------
    # Process lock (file-based, pid + timestamp)
    # ------------------------------------------------------------------
    def _write_lock(self, pid: int, purpose: str = "managed_cdp") -> None:
        """Write the CDP process lock file."""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._cdp_lock_path.write_text(
                json.dumps({
                    "pid": pid,
                    "port": self._cdp_port,
                    "timestamp": time.time(),
                    "purpose": purpose,
                }, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("[ManagedCDP] Failed to write lock: %s", exc)

    def _read_lock(self) -> Optional[Dict]:
        """Read the CDP process lock file, return data or None."""
        try:
            if self._cdp_lock_path.exists():
                return json.loads(
                    self._cdp_lock_path.read_text(encoding="utf-8")
                )
        except Exception:
            pass
        return None

    def _clear_lock(self) -> None:
        """Remove the CDP process lock file."""
        try:
            self._cdp_lock_path.unlink(missing_ok=True)
            logger.info("[ManagedCDP] Lock cleared")
        except Exception as exc:
            logger.warning("[ManagedCDP] Failed to clear lock: %s", exc)

    def _find_listener_pid(self, port: int = 0) -> int:
        """Best-effort resolve of the process currently listening on ``port``."""
        port = int(port or self._cdp_port)
        try:
            import psutil

            for conn in psutil.net_connections(kind="tcp"):
                try:
                    laddr = conn.laddr
                    local_port = getattr(laddr, "port", None)
                    status = str(getattr(conn, "status", "") or "").upper()
                    if local_port != port or status != "LISTEN":
                        continue
                    pid = int(conn.pid or 0)
                    if pid > 0:
                        return pid
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("[ManagedCDP] Failed to resolve listener pid: %s", exc)
        return 0

    def _adopt_running_instance(self, port: int = 0) -> bool:
        """Adopt an already-running managed Chrome when the port is live."""
        port = int(port or self._cdp_port)
        if not self._is_port_open(port):
            return False

        pid = self._find_listener_pid(port)
        purpose = "managed_cdp_adopted"
        lock = self._read_lock() or {}
        current_pid = int(lock.get("pid", 0) or 0)
        current_port = int(lock.get("port", port) or port)
        current_purpose = str(lock.get("purpose") or purpose)

        if current_pid != pid or current_port != port:
            self._write_lock(pid, purpose)
            logger.info(
                "[ManagedCDP] Adopted existing Chrome on port %d (pid=%s)",
                port,
                pid or "?",
            )
        else:
            self._write_lock(pid or current_pid, current_purpose)
        return True

    def _is_lock_stale(self, lock_data: Dict) -> bool:
        """Check if a lock is stale (process dead or too old)."""
        pid = lock_data.get("pid", 0)
        port = int(lock_data.get("port", self._cdp_port) or self._cdp_port)
        ts = lock_data.get("timestamp", 0)

        # As long as the listener is still alive, keep the session.
        if self._is_port_open(port):
            return False

        if pid and self._is_pid_alive(pid):
            return False

        # Process is dead and CDP port is closed.
        if pid:
            logger.info(
                "[ManagedCDP] Lock is stale (pid=%d is dead and port=%d is closed)",
                pid,
                port,
            )
            return True

        # No pid information left and the port is closed: treat as stale only
        # after the grace window so an in-flight launch is not broken.
        if time.time() - ts > _STALE_LOCK_SECONDS:
            logger.info(
                "[ManagedCDP] Lock is stale (inactive age=%.0fs > %ds)",
                time.time() - ts, _STALE_LOCK_SECONDS,
            )
            return True

        return False

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        if not pid or pid <= 0:
            return False
        if os.name == "nt":
            # On Windows, os.kill(pid, 0) can raise asynchronous KeyboardInterrupt
            # in some runtimes; use WinAPI process query instead.
            try:
                import ctypes
                from ctypes import wintypes

                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                STILL_ACTIVE = 259

                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)
                )
                if not handle:
                    return False
                try:
                    exit_code = wintypes.DWORD()
                    if not kernel32.GetExitCodeProcess(
                        wintypes.HANDLE(handle), ctypes.byref(exit_code)
                    ):
                        return False
                    return int(exit_code.value) == STILL_ACTIVE
                finally:
                    kernel32.CloseHandle(wintypes.HANDLE(handle))
            except Exception:
                return False

        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError, SystemError):
            return False

    # ------------------------------------------------------------------
    # Port check
    # ------------------------------------------------------------------
    def _is_port_open(self, port: int = 0, timeout: float = 0.5) -> bool:
        """Check if a TCP port is accepting connections on localhost."""
        port = port or self._cdp_port
        sock = None
        try:
            # connect_ex avoids exception-heavy socket.create_connection() paths
            # and behaves more predictably under repeated short timeout probes.
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            return sock.connect_ex(("127.0.0.1", int(port))) == 0
        except (OSError, ValueError, OverflowError):
            return False
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Core: is_running
    # ------------------------------------------------------------------
    def is_running(self) -> bool:
        """Check if the managed Chrome instance is currently running.

        Returns True only when:
          1. A valid managed lock exists and the CDP port is alive, OR
          2. The CDP port is already alive and can be adopted.
        """
        lock = self._read_lock()
        if lock:
            if self._is_lock_stale(lock):
                if self._adopt_running_instance(lock.get("port", self._cdp_port)):
                    return True
                self._clear_lock()
                return False

            port = int(lock.get("port", self._cdp_port) or self._cdp_port)
            if self._is_port_open(port):
                # Refresh the heartbeat so long sessions are not misclassified
                # as stale later.
                self._write_lock(
                    int(lock.get("pid", 0) or self._find_listener_pid(port)),
                    str(lock.get("purpose") or "managed_cdp"),
                )
                return True

        return self._adopt_running_instance(self._cdp_port)

    # ------------------------------------------------------------------
    # Core: ensure_running
    # ------------------------------------------------------------------
    def ensure_running(self) -> Tuple[bool, str]:
        """Ensure the managed Chrome instance is running with CDP enabled.

        Returns:
            (success, message) — success is True if Chrome is running
            and the CDP port is accepting connections.

        Conflict rules:
          - If SessionAuthority says profile is busy (Re-login in progress),
            returns (False, "profile_busy") without launching.
          - If our own managed Chrome is already running, returns (True, "already_running").
          - Otherwise, launches a new Chrome process.
        """
        if not MANAGED_CDP_ATTACH_FIRST:
            return False, "feature_disabled"

        with self._lock:
            # Already running?
            if self.is_running():
                return True, "already_running"

            # Profile busy (Re-login or other Playwright context)?
            if self._sa.is_profile_busy():
                logger.info(
                    "[ManagedCDP] Cannot launch — profile is busy (Re-login?)"
                )
                return False, "profile_busy"

            # Find Chrome executable
            chrome_exe = self._sa.chrome_executable
            if not chrome_exe:
                from modules.shared.browser_utils import get_chromium_executable_path
                chrome_exe = get_chromium_executable_path()
            if not chrome_exe or not Path(chrome_exe).exists():
                logger.warning("[ManagedCDP] Chrome not found")
                return False, "chrome_not_found"

            # Launch Chrome
            return self._launch_chrome(chrome_exe)

    def _launch_chrome(self, chrome_exe: str) -> Tuple[bool, str]:
        """Launch Chrome with --remote-debugging-port and managed profile.

        [NoPopupPolicy] Chrome is ALWAYS launched headless to prevent
        visible browser windows from appearing during automation.
        Only manual Re-login (open_login_browser) should show a window.
        """
        args = [
            chrome_exe,
            f"--remote-debugging-port={self._cdp_port}",
            f"--user-data-dir={self._profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-client-side-phishing-detection",
            "--disable-default-apps",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-sync",
            "--disable-gpu",
            "--metrics-recording-only",
            "--no-service-autorun",
        ]

        try:
            # Write SessionAuthority lock so other modules know profile is in use
            self._sa.write_session_lock("managed_cdp")

            self._chrome_process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            pid = self._chrome_process.pid
            self._write_lock(pid, "managed_cdp")

            logger.info(
                "[ManagedCDP] Chrome launched (pid=%d, port=%d)",
                pid, self._cdp_port,
            )

            # Wait for CDP port to become available
            deadline = time.time() + _CHROME_STARTUP_TIMEOUT
            while time.time() < deadline:
                if self._is_port_open():
                    logger.info(
                        "[ManagedCDP] CDP port %d is open (waited %.1fs)",
                        self._cdp_port,
                        _CHROME_STARTUP_TIMEOUT - (deadline - time.time()),
                    )
                    return True, "launched"
                time.sleep(0.5)

            # Timeout — port never opened
            logger.warning(
                "[ManagedCDP] CDP port %d did not open within %ds",
                self._cdp_port, _CHROME_STARTUP_TIMEOUT,
            )
            self._kill_process()
            return False, "port_timeout"

        except Exception as exc:
            logger.error("[ManagedCDP] Chrome launch failed: %s", exc, exc_info=True)
            self._kill_process()
            return False, f"launch_error: {exc}"

    # ------------------------------------------------------------------
    # Core: attach_selenium
    # ------------------------------------------------------------------
    def _read_cdp_browser_version(self) -> Optional[str]:
        """Read the managed Chrome browser version from the local CDP endpoint."""
        if not self._is_port_open():
            return None

        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{self._cdp_port}/json/version",
                timeout=2,
            ) as response:
                payload = json.loads(response.read().decode("utf-8", "ignore"))
            browser = str(payload.get("Browser") or "").strip()
            if "/" in browser:
                return browser.split("/", 1)[1].strip() or None
        except (OSError, ValueError, urllib.error.URLError) as exc:
            logger.debug("[ManagedCDP] Failed to read CDP version: %s", exc)
        return None

    @staticmethod
    def _version_key(value: str) -> Tuple[int, ...]:
        parts = []
        for piece in str(value).split("."):
            try:
                parts.append(int(piece))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    def _find_cached_chromedriver(self, browser_major: str = "") -> Optional[str]:
        """Find the best cached Selenium chromedriver, preferring browser major."""
        cache_root = Path.home() / ".cache" / "selenium" / "chromedriver" / "win64"
        if not cache_root.exists():
            return None

        preferred = []
        others = []
        for version_dir in cache_root.iterdir():
            if not version_dir.is_dir():
                continue
            driver_path = version_dir / "chromedriver.exe"
            if not driver_path.exists():
                continue
            version = version_dir.name
            bucket = preferred if browser_major and version.startswith(f"{browser_major}.") else others
            bucket.append((self._version_key(version), str(driver_path)))

        for candidates in (preferred, others):
            if candidates:
                candidates.sort(reverse=True)
                return candidates[0][1]
        return None

    def _resolve_selenium_driver_path(self, chrome_exe: str) -> Optional[str]:
        """Resolve a ChromeDriver compatible with the managed system Chrome.

        Selenium Manager is used first, but with the IXBrowser chromedriver PATH
        entry filtered out so it cannot shadow the correct driver. If that still
        fails, we fall back to the Selenium cache.
        """
        browser_version = self._read_cdp_browser_version() or ""
        browser_major = browser_version.split(".", 1)[0] if browser_version else ""
        original_path = os.environ.get("PATH", "")
        cleaned_parts = [
            part
            for part in original_path.split(os.pathsep)
            if "ixbrowser-resources\\chrome" not in part.lower()
        ]
        cleaned_path = os.pathsep.join(cleaned_parts)

        try:
            from selenium.webdriver.common.selenium_manager import SeleniumManager

            os.environ["PATH"] = cleaned_path
            result = SeleniumManager().binary_paths(
                ["--browser", "chrome", "--browser-path", chrome_exe]
            )
            driver_path = str(result.get("driver_path") or "").strip()
            if driver_path and Path(driver_path).exists():
                logger.info(
                    "[ManagedCDP] Resolved ChromeDriver %s for Chrome %s",
                    driver_path,
                    browser_version or "unknown",
                )
                return driver_path
        except Exception as exc:
            logger.warning("[ManagedCDP] ChromeDriver resolve failed: %s", exc)
        finally:
            os.environ["PATH"] = original_path

        cached_driver = self._find_cached_chromedriver(browser_major)
        if cached_driver:
            logger.info(
                "[ManagedCDP] Using cached ChromeDriver %s for Chrome %s",
                cached_driver,
                browser_version or "unknown",
            )
            return cached_driver

        logger.warning(
            "[ManagedCDP] No compatible ChromeDriver found for Chrome %s",
            browser_version or "unknown",
        )
        return None

    def attach_selenium(self):
        """Attach Selenium WebDriver to the managed Chrome via CDP.

        Returns:
            selenium.webdriver.Chrome instance, or None on failure.

        IMPORTANT: Callers must NOT call driver.quit() — that would close
        the user's Chrome window.  Instead call driver.service.stop() when
        done, or just let the driver go out of scope.
        """
        if not self.is_running():
            return None

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            options = Options()
            options.add_experimental_option(
                "debuggerAddress", f"localhost:{self._cdp_port}"
            )
            chrome_exe = self._sa.chrome_executable
            if not chrome_exe:
                from modules.shared.browser_utils import get_chromium_executable_path

                chrome_exe = get_chromium_executable_path()
            if not chrome_exe or not Path(chrome_exe).exists():
                logger.warning("[ManagedCDP] Cannot attach Selenium: Chrome not found")
                return None

            driver_path = self._resolve_selenium_driver_path(chrome_exe)
            if not driver_path:
                return None

            service = Service(executable_path=driver_path)
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(30)
            logger.info(
                "[ManagedCDP] Selenium attached to port %d with %s",
                self._cdp_port,
                driver_path,
            )
            return driver
        except Exception as exc:
            logger.error("[ManagedCDP] Selenium attach failed: %s", exc, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Core: attach_playwright_cdp
    # ------------------------------------------------------------------
    def attach_playwright_cdp(self, playwright_instance=None):
        """Attach Playwright to the managed Chrome via CDP.

        Args:
            playwright_instance: An existing sync_playwright() context.
                If None, caller must provide one.

        Returns:
            (browser, context) tuple, or (None, None) on failure.

        Caller is responsible for closing the browser connection when done
        (browser.close()), but this does NOT close the actual Chrome process.
        """
        if not self.is_running():
            return None, None

        try:
            if playwright_instance is None:
                from playwright.sync_api import sync_playwright
                # Caller should manage the playwright lifecycle
                logger.warning(
                    "[ManagedCDP] No playwright_instance provided — "
                    "caller must manage sync_playwright context"
                )
                return None, None

            browser = playwright_instance.chromium.connect_over_cdp(
                f"http://localhost:{self._cdp_port}"
            )
            contexts = browser.contexts
            context = contexts[0] if contexts else browser.new_context()
            logger.info(
                "[ManagedCDP] Playwright CDP attached (contexts=%d)",
                len(contexts),
            )
            return browser, context
        except Exception as exc:
            logger.error("[ManagedCDP] Playwright CDP attach failed: %s", exc, exc_info=True)
            return None, None

    # ------------------------------------------------------------------
    # Core: graceful_close
    # ------------------------------------------------------------------
    def graceful_close(self) -> bool:
        """Gracefully close the managed Chrome instance.

        Returns True if Chrome was running and was successfully terminated.
        """
        with self._lock:
            was_running = self.is_running()

            # Kill our tracked process
            self._kill_process()

            # Also kill by PID from lock file (in case process was restarted)
            lock = self._read_lock()
            if lock:
                pid = lock.get("pid", 0)
                if pid and int(pid) != os.getpid() and self._is_pid_alive(pid):
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        logger.info("[ManagedCDP] Sent SIGTERM to pid=%d", pid)
                    except Exception:
                        pass

            # Clean up locks
            self._clear_lock()
            self._sa.clear_session_lock()

            if was_running:
                logger.info("[ManagedCDP] Chrome closed gracefully")
            return was_running

    def _get_hwnd_for_pid(self, target_pid: int) -> Optional[int]:
        """Find the main window handle (HWND) for a given PID."""
        if sys.platform != "win32" or "win32gui" not in sys.modules:
            return None

        import psutil
        try:
            parent = psutil.Process(target_pid)
            children = parent.children(recursive=True)
            valid_pids = {target_pid} | {c.pid for c in children}
        except psutil.NoSuchProcess:
            return None

        found_hwnd = []
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in valid_pids:
                    # Chrome typically uses this class name for its main window
                    if win32gui.GetClassName(hwnd) == "Chrome_WidgetWin_1":
                        windows.append(hwnd)
            return True

        try:
            win32gui.EnumWindows(callback, found_hwnd)
        except Exception as e:
            logger.debug(f"[ManagedCDP] Error finding HWND: {e}")

        if found_hwnd:
            return found_hwnd[0]

        # Fallback: Find ANY window ending in " - Google Chrome"
        fallback_hwnds = []
        def fallback_cb(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                text = win32gui.GetWindowText(hwnd)
                if text and text.endswith(" - Google Chrome"):
                    windows.append(hwnd)
            return True
            
        try:
            win32gui.EnumWindows(fallback_cb, fallback_hwnds)
        except Exception:
            pass
            
        if fallback_hwnds:
            return fallback_hwnds[0]
            
        return None

    def minimize_window(self) -> None:
        """Minimize the active Chrome window if running on Windows."""
        if sys.platform != "win32" or "win32gui" not in sys.modules:
            return

        lock = self._read_lock()
        pid = lock.get("pid", 0) if lock else 0
        if not pid and self._chrome_process:
            pid = self._chrome_process.pid

        if not pid:
            return

        hwnd = self._get_hwnd_for_pid(pid)
        if hwnd:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                logger.info(f"[ManagedCDP] Minimized window for pid={pid}")
            except Exception as e:
                logger.debug(f"[ManagedCDP] Failed to minimize window: {e}")

    def maximize_window(self) -> None:
        """Restore and maximize the active Chrome window if running on Windows."""
        if sys.platform != "win32" or "win32gui" not in sys.modules:
            return

        lock = self._read_lock()
        pid = lock.get("pid", 0) if lock else 0
        if not pid and self._chrome_process:
            pid = self._chrome_process.pid

        if not pid:
            return

        hwnd = self._get_hwnd_for_pid(pid)
        if hwnd:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                logger.info(f"[ManagedCDP] Restored window for pid={pid}")
            except Exception as e:
                logger.debug(f"[ManagedCDP] Failed to restore window: {e}")

    def release_lock(self) -> None:
        """Release the process lock without killing Chrome.

        Use this when Chrome was closed externally (e.g., user closed it)
        and we just need to clean up our lock files.
        """
        self._clear_lock()
        self._sa.clear_session_lock()
        self._chrome_process = None
        logger.info("[ManagedCDP] Lock released (external close)")

    # ------------------------------------------------------------------
    # Internal: kill process
    # ------------------------------------------------------------------
    def _kill_process(self) -> None:
        """Kill the tracked Chrome subprocess if it exists."""
        if self._chrome_process is not None:
            try:
                self._chrome_process.terminate()
                try:
                    self._chrome_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._chrome_process.kill()
                logger.info("[ManagedCDP] Chrome process terminated")
            except Exception as exc:
                logger.warning("[ManagedCDP] Kill failed: %s", exc)
            finally:
                self._chrome_process = None


# ---------------------------------------------------------------------------
# Convenience: extract links via managed CDP
# ---------------------------------------------------------------------------
def extract_links_via_managed_cdp(
    url: str,
    platform_key: str,
    max_videos: int = 0,
    progress_callback=None,
    expected_count: int = 0,
) -> list:
    """Attempt link extraction by attaching to the managed Chrome via CDP.

    This is the "attach-first" path that runs BEFORE the normal method chain
    when MANAGED_CDP_ATTACH_FIRST is True.

    Returns a list of entry dicts, or [] if managed Chrome isn't running
    or extraction fails.
    """
    if not MANAGED_CDP_ATTACH_FIRST:
        return []

    def _normalize_browser_url(raw_url: str) -> str:
        parsed = urlparse((raw_url or "").strip())
        host = (parsed.netloc or "").lower().replace("www.", "").replace("m.", "")
        path = (parsed.path or "").rstrip("/").lower()
        if host and path:
            return f"{host}{path}"
        return ((raw_url or "").split("?", 1)[0].split("#", 1)[0]).rstrip("/").lower()

    def _same_target_url(target_url: str, current_url: str) -> bool:
        target_norm = _normalize_browser_url(target_url)
        current_norm = _normalize_browser_url(current_url)
        return bool(target_norm and current_norm and target_norm == current_norm)

    def _detect_blocked_state(target_url: str, current_url: str) -> Tuple[bool, str]:
        current_norm = _normalize_browser_url(current_url)
        target_norm = _normalize_browser_url(target_url)
        lower_url = (current_url or "").lower()

        if current_norm and target_norm and current_norm != target_norm:
            return True, f"url_mismatch:{current_url}"

        redirect_terms = (
            "accounts/login",
            "/login",
            "/challenge",
            "/checkpoint",
            "/consent",
            "/suspended",
        )
        if any(term in lower_url for term in redirect_terms):
            return True, f"redirect:{current_url}"

        block_terms = [
            "log in",
            "sign up",
            "open app",
            "use app",
            "challenge_required",
            "checkpoint required",
            "confirm it's you",
            "unusual activity",
            "try again later",
        ]
        platform_specific_terms = {
            "instagram": [
                "see instagram photos and videos",
                "continue as",
                "instagram login",
            ],
            "tiktok": [
                "login to tiktok",
                "open tiktok",
            ],
            "facebook": [
                "log into facebook",
                "login to facebook",
            ],
        }
        terms = block_terms + platform_specific_terms.get((platform_key or "").lower(), [])

        try:
            title_text = (driver.title or "").strip().lower()
        except Exception:
            title_text = ""
        if any(term in title_text for term in terms):
            return True, f"title_block:{title_text[:120]}"

        try:
            page_text = (driver.page_source or "").lower()
        except Exception:
            page_text = ""
        page_block_terms = [
            "challenge_required",
            "checkpoint required",
            "confirm it's you",
            "unusual activity",
            "try again later",
            "accounts/login",
            "login_and_signup_page",
            "see instagram photos and videos",
        ]
        if page_text and any(term in page_text for term in page_block_terms):
            return True, "page_block"

        try:
            from selenium.webdriver.common.by import By

            dialogs = driver.find_elements(By.CSS_SELECTOR, "[role='dialog']")
            for dialog in dialogs[:3]:
                dialog_text = (dialog.text or "").strip().lower()
                if dialog_text and any(term in dialog_text for term in terms):
                    return True, f"dialog_block:{dialog_text[:120]}"
        except Exception:
            pass

        return False, ""

    mgr = get_managed_chrome_session()
    if not mgr.is_running():
        # [NoPopupPolicy] NEVER auto-launch Chrome from background automation.
        # Attach-only: if managed Chrome is not already running, silently
        # fall back to the normal extraction chain.
        logger.info(
            "[ManagedCDP-Fallback] Managed Chrome not running — "
            "skipping CDP attach, falling back to normal methods"
        )
        return []

    driver = mgr.attach_selenium()
    if driver is None:
        return []

    try:
        if progress_callback:
            progress_callback("Scanning (managed session)...")

        current_url = driver.current_url or ""
        target_base_url = url.split('?')[0].rstrip('/')
        current_base_url = current_url.split('?')[0].rstrip('/')

        # Smart URL check to prevent duplicate pasting/reloading
        if current_base_url != target_base_url:
            if progress_callback:
                progress_callback(f"Writing URL to navigate: {url}")
            
            # --- Native typing block ---
            import sys
            typed = False
            if sys.platform == "win32":
                try:
                    import win32gui
                    import win32con
                    import pyautogui
                    mgr.maximize_window()
                    time.sleep(0.5)
                    pyautogui.hotkey('ctrl', 'l')
                    time.sleep(0.3)
                    import random
                    for char in url:
                        pyautogui.typewrite(char)
                        # Randomize typing speed per character natively
                        time.sleep(random.uniform(0.04, 0.13))
                    time.sleep(0.2)
                    pyautogui.press('enter')
                    typed = True
                except ImportError:
                    pass
            
            if not typed:
                driver.get(url)
            # ---------------------------
            
            time.sleep(3)

            # Verification: If PyAutoGUI typed into the void instead of Chrome, force driver.get!
            post_nav_url = driver.current_url or ""
            if _normalize_browser_url(post_nav_url) != _normalize_browser_url(url):
                if progress_callback:
                    progress_callback("PyAutoGUI missed address bar. Forcing native driver.get()...")
                logger.info("[ManagedCDP] PyAutoGUI failed to navigate. Forcing driver.get(url)")
                driver.get(url)
                time.sleep(4)
                post_nav_url = driver.current_url or ""

            blocked, reason = _detect_blocked_state(url, post_nav_url)
            if blocked:
                msg = f"Managed session blocked after URL write ({reason})"
                logger.info("[ManagedCDP] %s", msg)
                if progress_callback:
                    progress_callback(msg)
                return []
        else:
            if progress_callback:
                progress_callback("Continuing from active profile view (target already open)")

        # Reuse existing link extraction logic
        from modules.link_grabber.core import _extract_links_from_selenium_driver

        entries = _extract_links_from_selenium_driver(
            driver,
            platform_key=platform_key,
            max_videos=max_videos,
            expected_count=expected_count,
            progress_callback=progress_callback,
        )

        if entries and progress_callback:
            progress_callback(f"Found {len(entries)} links (managed session)")
            return entries

        current_url = driver.current_url or ""
        blocked, reason = _detect_blocked_state(url, current_url)
        if blocked:
            msg = f"Managed session blocked after extraction ({reason})"
            logger.info("[ManagedCDP] %s", msg)
            if progress_callback:
                progress_callback(msg)
            return []

        if not _same_target_url(url, current_url):
            msg = f"Managed session URL mismatch after extraction: {current_url or '<empty>'}"
            logger.info("[ManagedCDP] %s", msg)
            if progress_callback:
                progress_callback(msg)
            return []

        if progress_callback:
            progress_callback("Managed session returned 0 links; refreshing target page...")

        try:
            driver.refresh()
        except Exception as refresh_exc:
            logger.debug("[ManagedCDP] refresh failed: %s", refresh_exc)
            if progress_callback:
                progress_callback("Managed session refresh failed; skipping managed method")
            return []

        time.sleep(4)

        refreshed_url = driver.current_url or ""
        blocked, reason = _detect_blocked_state(url, refreshed_url)
        if blocked:
            msg = f"Managed session blocked after refresh ({reason})"
            logger.info("[ManagedCDP] %s", msg)
            if progress_callback:
                progress_callback(msg)
            return []

        if not _same_target_url(url, refreshed_url):
            msg = f"Managed session URL changed after refresh: {refreshed_url or '<empty>'}"
            logger.info("[ManagedCDP] %s", msg)
            if progress_callback:
                progress_callback(msg)
            return []

        if progress_callback:
            progress_callback("Managed session target verified after refresh; retrying extraction...")

        retry_entries = _extract_links_from_selenium_driver(
            driver,
            platform_key=platform_key,
            max_videos=max_videos,
            expected_count=expected_count,
            progress_callback=progress_callback,
        )

        if retry_entries and progress_callback:
            progress_callback(f"Found {len(retry_entries)} links (managed session retry)")

        if not retry_entries and progress_callback:
            progress_callback("Managed session retry returned 0 links; falling back to next method")

        return retry_entries

    except Exception as exc:
        logger.error("[ManagedCDP] extract failed: %s", exc, exc_info=True)
        return []
    finally:
        # Disconnect ChromeDriver WITHOUT closing Chrome
        try:
            if driver and driver.service:
                driver.service.stop()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Integration helper: >=10-links continue rule
# ---------------------------------------------------------------------------
def should_continue_despite_challenge(
    entries_count: int,
    platform: str,
    challenge_signal: str = "",
) -> bool:
    """When managed CDP is active, continue if we have >= 10 links
    even if a challenge/cooldown was detected.

    This prevents aborting a productive session due to transient
    challenge pages that appear after successful extraction.
    """
    if not MANAGED_CDP_ATTACH_FIRST:
        return False
    if entries_count >= 10:
        logger.info(
            "[ManagedCDP] Continue despite challenge: %d links extracted "
            "(platform=%s, signal=%s)",
            entries_count, platform, challenge_signal[:60],
        )
        return True
    return False
