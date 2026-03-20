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
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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
        self._profile_dir = self._sa.profile_dir
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

    def _is_lock_stale(self, lock_data: Dict) -> bool:
        """Check if a lock is stale (process dead or too old)."""
        pid = lock_data.get("pid", 0)
        ts = lock_data.get("timestamp", 0)

        # Too old
        if time.time() - ts > _STALE_LOCK_SECONDS:
            logger.info(
                "[ManagedCDP] Lock is stale (age=%.0fs > %ds)",
                time.time() - ts, _STALE_LOCK_SECONDS,
            )
            return True

        # Process is dead
        if pid and not self._is_pid_alive(pid):
            logger.info("[ManagedCDP] Lock is stale (pid=%d is dead)", pid)
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
          1. We have a valid (non-stale) lock file, AND
          2. The CDP port is accepting connections.
        """
        lock = self._read_lock()
        if not lock:
            return False
        if self._is_lock_stale(lock):
            self._clear_lock()
            return False
        return self._is_port_open(lock.get("port", self._cdp_port))

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
            "--headless=new",  # [NoPopupPolicy] NEVER open visible window
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
            logger.error("[ManagedCDP] Chrome launch failed: %s", exc)
            self._kill_process()
            return False, f"launch_error: {exc}"

    # ------------------------------------------------------------------
    # Core: attach_selenium
    # ------------------------------------------------------------------
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

            options = Options()
            options.add_experimental_option(
                "debuggerAddress", f"localhost:{self._cdp_port}"
            )
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(30)
            logger.info("[ManagedCDP] Selenium attached to port %d", self._cdp_port)
            return driver
        except Exception as exc:
            logger.warning("[ManagedCDP] Selenium attach failed: %s", exc)
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
            logger.warning("[ManagedCDP] Playwright CDP attach failed: %s", exc)
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

        driver.get(url)
        time.sleep(4)

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
    except Exception as exc:
        logger.debug("[ManagedCDP] extract failed: %s", exc)
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
