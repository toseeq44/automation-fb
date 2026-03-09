"""
modules/creator_profiles/ix_link_grabber.py
IXBrowser-based link extraction for Creator Profiles (Approach 2).

Uses IXBrowser's anti-detect Chrome engine + Selenium to grab video links
from creator profiles. Designed as a singleton session that stays open for
the entire app lifecycle (multiple runs reuse the same profile).

Reuses:
  - modules.auto_uploader.approaches.ixbrowser.api_client  (REST API)
  - Selenium attach pattern from browser_launcher.py
"""

from __future__ import annotations

import logging
import platform
import random
import re
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Windows-specific imports for window management ───────────────────────────
if platform.system() == "Windows":
    try:
        import win32gui
        import win32con
        _HAS_WIN32 = True
    except ImportError:
        _HAS_WIN32 = False
else:
    _HAS_WIN32 = False

# ── Selenium imports ─────────────────────────────────────────────────────────
try:
    from selenium.webdriver import Chrome
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import WebDriverException
    _HAS_SELENIUM = True
except ImportError:
    _HAS_SELENIUM = False
    Chrome = None
    Options = None
    Service = None
    WebDriverException = Exception

# ── Constants ────────────────────────────────────────────────────────────────

IX_API_BASE = "http://127.0.0.1:53200"
IX_API_KEY = ""
PROFILE_IDENT = "onesoul"

# Per-platform: URL to navigate for login check + patterns indicating NOT logged in
PLATFORM_LOGIN_CHECKS: Dict[str, dict] = {
    "instagram": {
        "url": "https://www.instagram.com/",
        "fail_patterns": ["/accounts/login", "/challenge/"],
    },
    "facebook": {
        "url": "https://www.facebook.com/",
        "fail_patterns": ["/login", "login_attempt", "checkpoint"],
    },
    "tiktok": {
        "url": "https://www.tiktok.com/",
        "fail_patterns": ["/login"],
    },
    "youtube": {
        "url": "https://www.youtube.com/",
        "fail_patterns": ["accounts.google.com/ServiceLogin", "accounts.google.com/v3/signin"],
    },
}

# Per-platform: CSS selector for video links + optional tab path to append
PLATFORM_SELECTORS: Dict[str, dict] = {
    "tiktok": {
        "video_link": 'a[href*="/video/"]',
        "video_tab": None,  # default profile page shows videos
    },
    "instagram": {
        "video_link": 'a[href*="/reel/"]',
        "video_tab": "/reels/",
    },
    "facebook": {
        "video_link": 'a[href*="/videos/"]',
        "video_tab": "/videos/",
    },
    "youtube": {
        "video_link": 'a#video-title-link, a[href*="/watch?v="]',
        "video_tab": "/videos",
    },
}

# Max scrolls with no new links before we stop
_MAX_STALE_SCROLLS = 5


def _log(msg: str, progress_cb: Optional[Callable] = None):
    """Print to terminal AND optionally emit to GUI progress."""
    print(msg)
    logger.info(msg)
    if progress_cb:
        progress_cb(msg)


# ═════════════════════════════════════════════════════════════════════════════
# IXSessionManager — singleton managing one IXBrowser profile
# ═════════════════════════════════════════════════════════════════════════════

class IXSessionManager:
    """Manages a single IXBrowser 'onesoul' profile + Selenium WebDriver.

    Lifecycle:
      ensure_session() → check_login() → extract_links() ... → close_session()

    The session stays open between multiple creator runs.  Only close_session()
    or app exit should shut it down.
    """

    _instance: Optional["IXSessionManager"] = None

    def __init__(self):
        self._api = None
        self._profile_info = None
        self._session = None  # IXProfileSession
        self._driver: Optional[Chrome] = None
        self._is_open: bool = False
        self._lock = threading.Lock()
        self._login_verified: Dict[str, bool] = {}

    # ── Session lifecycle ────────────────────────────────────────────────

    def ensure_session(self, progress_cb: Optional[Callable] = None) -> bool:
        """Open 'onesoul' profile and attach Selenium.  Reuses if already open.

        Full flow (same as autouploader):
          1. Check if IXBrowser API is reachable
          2. If not → auto-launch IXBrowser app + auto-login if needed
          3. Find 'onesoul' profile via API
          4. Open profile (visible window)
          5. Attach Selenium via Chrome DevTools Protocol
        """
        with self._lock:
            # Reuse existing session if driver is alive
            if self._is_open and self._driver:
                try:
                    _ = self._driver.current_url  # health check
                    _log("[IX-Session] Reusing existing session", progress_cb)
                    return True
                except Exception:
                    _log("[IX-Session] Previous session dead, re-opening...", progress_cb)
                    self._is_open = False
                    self._driver = None

            if not _HAS_SELENIUM:
                _log("[IX-Session] ERROR: Selenium not installed! pip install selenium", progress_cb)
                return False

            try:
                # ── Step 1: Ensure IXBrowser app is running (auto-launch + auto-login)
                _log("[IX-Session] Step 1: Ensuring IXBrowser is running...", progress_cb)

                # Quick socket check first — avoid heavy launcher if API is already up
                import socket
                api_ready = False
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    api_ready = sock.connect_ex(("127.0.0.1", 53200)) == 0
                    sock.close()
                except Exception:
                    pass

                if api_ready:
                    _log("[IX-Session] Step 1: IXBrowser API already available!", progress_cb)
                else:
                    # API not reachable → use DesktopAppLauncher to start IX + auto-login
                    _log("[IX-Session] API not reachable, launching IXBrowser...", progress_cb)
                    ix_email, ix_password = self._load_ix_credentials()
                    from modules.auto_uploader.approaches.ixbrowser.desktop_launcher import DesktopAppLauncher

                    launcher = DesktopAppLauncher(
                        host="127.0.0.1",
                        port=53200,
                        email=ix_email,
                        password=ix_password,
                    )

                    if not launcher.ensure_running(timeout=60):
                        _log(
                            "[IX-Session] ERROR: Could not start IXBrowser! "
                            "Please install IXBrowser or start it manually.",
                            progress_cb,
                        )
                        return False

                    _log("[IX-Session] Step 1: IXBrowser launched and ready!", progress_cb)

                # ── Step 2: Connect our API client
                from modules.auto_uploader.approaches.ixbrowser.api_client import (
                    IXBrowserAPI,
                    IXBrowserAPIError,
                )

                _log(f"[IX-Session] Step 2: Connecting to API at {IX_API_BASE}", progress_cb)
                self._api = IXBrowserAPI(base_url=IX_API_BASE, api_key=IX_API_KEY)

                # ── Step 3: Find "onesoul" profile
                _log(f"[IX-Session] Step 3: Searching for profile '{PROFILE_IDENT}'", progress_cb)
                self._profile_info = self._api.find_profile(PROFILE_IDENT)
                if not self._profile_info:
                    _log(
                        f"[IX-Session] ERROR: Profile '{PROFILE_IDENT}' not found! "
                        f"Create a profile named '{PROFILE_IDENT}' in IXBrowser first.",
                        progress_cb,
                    )
                    return False
                _log(
                    f"[IX-Session] Found: '{self._profile_info.profile_name}' "
                    f"(ID: {self._profile_info.profile_id})",
                    progress_cb,
                )

                # ── Step 4: Open profile (visible — user can see browser window)
                _log(
                    f"[IX-Session] Step 4: Checking if profile '{self._profile_info.profile_name}' is already running...",
                    progress_cb,
                )

                debugging_addr = None
                webdriver_path = None

                # Check if it's already active in the raw data from find_profile
                raw_info = self._profile_info.raw or {}
                if raw_info.get("status") in (1, "1", "running", "active") or raw_info.get("profile_status") in (1, "1", "running", "active"):
                    _log("[IX-Session] Profile appears to be already running! Attempting to extract debug port...", progress_cb)
                    debugging_addr = raw_info.get("debugging_address") or raw_info.get("debugPort") or raw_info.get("debug_port")
                    if debugging_addr and str(debugging_addr).isdigit():
                        debugging_addr = f"127.0.0.1:{debugging_addr}"

                if debugging_addr:
                    _log(f"[IX-Session] Profile is already running at {debugging_addr}, bypassing open...", progress_cb)
                else:
                    _log("[IX-Session] Step 4: Opening profile normally...", progress_cb)
                    debugging_addr, webdriver_path = self._open_profile_with_kernel_fix(
                        progress_cb
                    )

                # Wait for Chrome engine to start
                _log("[IX-Session] Step 5: Waiting 3s for browser startup...", progress_cb)
                time.sleep(3)

                # ── Step 6: Attach Selenium via Chrome DevTools Protocol
                if not debugging_addr:
                    _log(
                        "[IX-Session] Step 4d: API open failed. Searching for manually opened Chrome debug port...",
                        progress_cb,
                    )
                    debugging_addr = self._find_running_debug_port()
                
                if not debugging_addr:
                    _log(
                        "[IX-Session] ERROR: No debugging address from IXBrowser! "
                        "Profile may already be open or API returned empty data. "
                        "Try closing the profile in IXBrowser and running again.",
                        progress_cb,
                    )
                    return False

                _log(
                    f"[IX-Session] Step 6: Attaching Selenium (debuggerAddress={debugging_addr})",
                    progress_cb,
                )
                chrome_options = Options()
                chrome_options.add_experimental_option("debuggerAddress", debugging_addr)

                if webdriver_path:
                    _log(f"[IX-Session] Using chromedriver: {webdriver_path}", progress_cb)
                    self._driver = Chrome(
                        service=Service(webdriver_path), options=chrome_options
                    )
                else:
                    _log("[IX-Session] No chromedriver path, using system default", progress_cb)
                    self._driver = Chrome(options=chrome_options)

                # Verify connection
                current = self._driver.current_url
                _log(
                    f"[IX-Session] Step 7: Selenium attached! Current URL: {current}",
                    progress_cb,
                )

                self._is_open = True
                return True

            except Exception as e:
                _log(f"[IX-Session] ERROR: {e}", progress_cb)
                import traceback
                traceback.print_exc()
                return False

    @staticmethod
    def _load_ix_credentials() -> tuple:
        """Load IXBrowser login credentials from ix_config.json."""
        import json
        config_path = (
            Path(__file__).resolve().parents[1]
            / "auto_uploader" / "approaches" / "ixbrowser" / "ix_config.json"
        )
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            email = cfg.get("email", "")
            password = cfg.get("password", "")
            if email:
                print(f"[IX-Session] Loaded IX credentials from {config_path}")
            return email, password
        except Exception as e:
            print(f"[IX-Session] Could not load ix_config.json: {e}")
            return "", ""

    # ── Profile opener with auto-fix ────────────────────────────────────

    def _open_profile_with_kernel_fix(
        self, progress_cb: Optional[Callable] = None
    ) -> tuple:
        """Open profile via official lib with automatic error recovery.

        Strategy:
          1. Try normal open_profile()
          2. If fails (kernel error, crash, timeout) → try open_profile_with_random_fingerprint()
             which regenerates fingerprint config and bypasses corrupted stored fingerprint
          3. If official lib not installed → fall back to REST API

        Returns (debugging_addr, webdriver_path) tuple.
        """
        try:
            from ixbrowser_local_api import IXBrowserClient
            from ixbrowser_local_api.entities import Fingerprint
        except ImportError:
            _log("[IX-Session] Official library not installed, using REST API", progress_cb)
            return self._open_profile_rest_fallback(progress_cb)

        client = IXBrowserClient(target="127.0.0.1", port=53200)
        pid_int = int(self._profile_info.profile_id)

        # Attempt 1: normal open_profile
        _log("[IX-Session] Step 4a: Opening profile (normal)...", progress_cb)
        open_result = client.open_profile(
            profile_id=pid_int,
            load_extensions=True,
            load_profile_info_page=False,
            cookies_backup=False,
        )

        if open_result is not None:
            addr = open_result.get("debugging_address")
            wdriver = open_result.get("webdriver")
            _log(f"[IX-Session] Profile opened! debug_addr={addr}", progress_cb)
            return addr, wdriver

        # Normal open failed
        err_code = client.code
        err_msg = client.message or ""
        _log(
            f"[IX-Session] Normal open failed (code={err_code}): {err_msg}",
            progress_cb,
        )

        # Attempt 2: open_profile_with_random_fingerprint
        # This regenerates fingerprint config, bypassing corrupted stored fingerprint
        # or kernel version issues that cause Chrome to crash
        _log(
            "[IX-Session] Step 4b: Retrying with random fingerprint (auto-fix)...",
            progress_cb,
        )

        fp = Fingerprint()
        fp.kernel_version = 0  # automatch — picks best available kernel

        open_result = client.open_profile_with_random_fingerprint(
            profile_id=pid_int,
            load_extensions=True,
            load_profile_info_page=False,
            fingerprint_config=fp,
        )

        if open_result is not None:
            addr = open_result.get("debugging_address")
            wdriver = open_result.get("webdriver")
            _log(
                f"[IX-Session] SUCCESS with random fingerprint! debug_addr={addr}",
                progress_cb,
            )
            return addr, wdriver

        err_code2 = client.code
        err_msg2 = client.message or ""
        _log(
            f"[IX-Session] Random fingerprint also failed (code={err_code2}): {err_msg2}",
            progress_cb,
        )

        # Attempt 3: Try REST API fallback directly
        _log("[IX-Session] Step 4c: Attempting REST API fallback...", progress_cb)
        addr, wdriver = self._open_profile_rest_fallback(progress_cb)
        if addr:
            _log(f"[IX-Session] SUCCESS with REST API fallback! debug_addr={addr}", progress_cb)
            return addr, wdriver

        return None, None

    def _open_profile_rest_fallback(
        self, progress_cb: Optional[Callable] = None
    ) -> tuple:
        """Fallback: open profile using our REST API client."""
        _log("[IX-Session] Using REST API to open profile...", progress_cb)
        try:
            session = self._api.open_profile(self._profile_info.profile_id)
            return session.debugging_address, session.webdriver_url
        except Exception as e:
            _log(f"[IX-Session] REST API open failed: {e}", progress_cb)
            return None, None

    def _find_running_debug_port(self) -> Optional[str]:
        """Attempt to find port of manually opened IXBrowser by scanning open localhost ports."""
        import subprocess, urllib.request, json
        try:
            out = subprocess.check_output('netstat -ano', shell=True).decode(errors='ignore')
            port_to_pid = {}
            for line in out.splitlines():
                if 'LISTENING' in line and '127.0.0.1:' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        addr = parts[1]
                        pid = parts[-1]
                        port = addr.split(':')[-1]
                        if port.isdigit() and pid.isdigit():
                            port_to_pid[int(port)] = pid
            
            # Usually remote debugging ports are > 9000
            candidate_ports = [p for p in port_to_pid.keys() if 9000 < p < 60000]
            
            for p in candidate_ports:
                try:
                    req = urllib.request.Request(f"http://127.0.0.1:{p}/json/version", timeout=0.2)
                    with urllib.request.urlopen(req) as response:
                        data = json.loads(response.read().decode())
                        # Check if it's a Chromium browser exposing devtools
                        if "Browser" in data and ("Chrome/" in data["Browser"] or "HeadlessChrome" in data["Browser"]):
                            # Verify the process belongs to IXBrowser to avoid hijacking normal Chrome
                            pid = port_to_pid[p]
                            try:
                                cmd_out = subprocess.check_output(f'wmic process where processid={pid} get commandline', shell=True).decode(errors='ignore').lower()
                                if 'ixbrowser' in cmd_out or 'onesoul' in cmd_out or 'profile' in cmd_out:
                                    return f"127.0.0.1:{p}"
                            except Exception:
                                # If wmic fails but it's chrome, we can risk returning it, but safer to skip or return. 
                                # Since usually only dev tools use this, we'll return it.
                                return f"127.0.0.1:{p}"
                except Exception:
                    continue
        except Exception:
            pass
        return None

    # ── Login check ──────────────────────────────────────────────────────

    def check_login(self, platform_key: str, progress_cb: Optional[Callable] = None) -> bool:
        """Navigate to platform and verify user is logged in.

        Returns False if not logged in — caller should show popup to user.
        """
        # Skip re-check if already verified this session
        if self._login_verified.get(platform_key):
            _log(f"[IX-Login] Already verified for {platform_key}", progress_cb)
            return True

        check = PLATFORM_LOGIN_CHECKS.get(platform_key)
        if not check:
            _log(f"[IX-Login] No login check for '{platform_key}', assuming OK", progress_cb)
            return True

        if not self._driver:
            _log("[IX-Login] ERROR: No Selenium driver!", progress_cb)
            return False

        try:
            _log(f"[IX-Login] Navigating to {check['url']}...", progress_cb)
            self._driver.get(check["url"])
            time.sleep(4)  # wait for page load + any redirects

            current = self._driver.current_url.lower()
            _log(f"[IX-Login] Current URL: {current}", progress_cb)

            for pattern in check["fail_patterns"]:
                if pattern.lower() in current:
                    _log(
                        f"[IX-Login] NOT LOGGED IN to {platform_key} "
                        f"(URL contains '{pattern}')",
                        progress_cb,
                    )
                    return False

            _log(f"[IX-Login] CONFIRMED logged in to {platform_key}", progress_cb)
            self._login_verified[platform_key] = True
            return True

        except Exception as e:
            _log(f"[IX-Login] Error checking login: {e}", progress_cb)
            return False

    # ── Link extraction ──────────────────────────────────────────────────

    def extract_links(
        self,
        creator_url: str,
        platform_key: str,
        max_videos: int = 20,
        progress_cb: Optional[Callable] = None,
    ) -> Tuple[List[dict], str]:
        """Scroll creator profile and extract video links via Selenium.

        Returns same format as extract_links_intelligent():
            (list_of_dicts[{url, id, title}], creator_name_str)
        """
        if not self._driver:
            _log("[IX-Links] ERROR: No Selenium driver!", progress_cb)
            return [], ""

        sel = PLATFORM_SELECTORS.get(platform_key, {})
        css_selector = sel.get("video_link")
        video_tab = sel.get("video_tab")

        if not css_selector:
            _log(f"[IX-Links] No selectors configured for '{platform_key}'", progress_cb)
            return [], ""

        # Build target URL: append video tab if needed
        target_url = creator_url.rstrip("/")
        if video_tab and not target_url.endswith(video_tab.rstrip("/")):
            target_url = target_url + video_tab

        _log(f"[IX-Links] Navigating to {target_url}", progress_cb)
        self._driver.get(target_url)
        time.sleep(random.uniform(3.0, 5.0))

        # Extract creator name from page title
        creator_name = ""
        try:
            raw_title = self._driver.title or ""
            # Common patterns: "Username - Platform", "Username (@handle)"
            for sep in [" - ", " | ", " (@", " •"]:
                if sep in raw_title:
                    creator_name = raw_title.split(sep)[0].strip()
                    break
            if not creator_name:
                creator_name = raw_title.strip()
            # Sanity check
            if len(creator_name) > 60:
                creator_name = creator_name[:60]
        except Exception:
            pass

        _log(f"[IX-Links] Page loaded. Creator: '{creator_name}'", progress_cb)

        # Scroll and collect links
        collected = self._scroll_and_collect(
            css_selector, max_videos, platform_key, progress_cb
        )

        # Deduplicate and assign IDs
        seen_urls = set()
        result: List[dict] = []
        for entry in collected:
            url = (entry.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            vid_id = _safe_id_from_url(url)
            result.append({
                "url": url,
                "id": vid_id,
                "title": (entry.get("title") or "").strip(),
            })

        _log(f"[IX-Links] Extraction complete: {len(result)} unique links", progress_cb)
        return result, creator_name

    def _scroll_and_collect(
        self,
        css_selector: str,
        max_videos: int,
        platform_key: str,
        progress_cb: Optional[Callable] = None,
    ) -> List[dict]:
        """Scroll page repeatedly, collecting video link elements."""
        all_links: List[dict] = []
        seen_hrefs: set = set()
        stale_count = 0
        scroll_num = 0

        while len(all_links) < max_videos and stale_count < _MAX_STALE_SCROLLS:
            scroll_num += 1

            # Extract links via JavaScript
            try:
                js_code = f"""
                    var links = document.querySelectorAll('{css_selector}');
                    var results = [];
                    links.forEach(function(a) {{
                        results.push({{
                            href: a.href || '',
                            title: a.getAttribute('title') || a.innerText || ''
                        }});
                    }});
                    return results;
                """
                raw = self._driver.execute_script(js_code)
            except Exception as e:
                _log(f"[IX-Links] JS extraction error on scroll {scroll_num}: {e}", progress_cb)
                break

            new_count = 0
            for item in (raw or []):
                href = (item.get("href") or "").strip()
                if not href or href in seen_hrefs:
                    continue
                # Basic URL validation
                if not href.startswith("http"):
                    continue
                seen_hrefs.add(href)
                all_links.append({
                    "url": href,
                    "title": (item.get("title") or "").strip()[:200],
                })
                new_count += 1

            if new_count > 0:
                stale_count = 0
                _log(
                    f"[IX-Links] Scroll {scroll_num}: +{new_count} new links (total: {len(all_links)})",
                    progress_cb,
                )
            else:
                stale_count += 1
                _log(
                    f"[IX-Links] Scroll {scroll_num}: no new links (stale: {stale_count}/{_MAX_STALE_SCROLLS})",
                    progress_cb,
                )

            if len(all_links) >= max_videos:
                break

            # Scroll down
            try:
                self._driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception:
                break
            time.sleep(random.uniform(1.5, 2.5))

        return all_links[:max_videos]

    # ── Window management ────────────────────────────────────────────────

    def minimize_browser(self, progress_cb: Optional[Callable] = None):
        """Minimize IXBrowser parent window + the browser window."""
        if not _HAS_WIN32:
            _log("[IX-Window] Win32 not available, cannot minimize", progress_cb)
            return

        try:
            # Minimize IXBrowser app window
            def _find_ix_windows(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if "ixBrowser" in title:
                        windows.append(hwnd)
                return True

            windows = []
            win32gui.EnumWindows(_find_ix_windows, windows)
            for hwnd in windows:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

            _log(f"[IX-Window] Minimized {len(windows)} IXBrowser window(s)", progress_cb)
        except Exception as e:
            _log(f"[IX-Window] Minimize error: {e}", progress_cb)

        # Also minimize the Chrome browser window via Selenium
        if self._driver:
            try:
                self._driver.minimize_window()
                _log("[IX-Window] Browser window minimized", progress_cb)
            except Exception:
                pass

    # ── Cleanup ──────────────────────────────────────────────────────────

    def close_session(self, progress_cb: Optional[Callable] = None):
        """Close Selenium driver + IXBrowser profile. Call on app exit."""
        with self._lock:
            _log("[IX-Session] Closing session...", progress_cb)

            if self._driver:
                try:
                    self._driver.quit()
                    _log("[IX-Session] Selenium driver closed", progress_cb)
                except Exception as e:
                    _log(f"[IX-Session] Driver close error: {e}", progress_cb)
                self._driver = None

            if self._api and self._profile_info:
                try:
                    self._api.close_profile(self._profile_info.profile_id)
                    _log("[IX-Session] IXBrowser profile closed", progress_cb)
                except Exception as e:
                    _log(f"[IX-Session] Profile close error: {e}", progress_cb)

            self._is_open = False
            self._session = None
            self._login_verified.clear()
            _log("[IX-Session] Session fully closed", progress_cb)

    def is_alive(self) -> bool:
        """Check if the Selenium driver is still responsive."""
        if not self._is_open or not self._driver:
            return False
        try:
            _ = self._driver.current_url
            return True
        except Exception:
            return False


# ═════════════════════════════════════════════════════════════════════════════
# Module-level singleton accessor
# ═════════════════════════════════════════════════════════════════════════════

def get_ix_session() -> IXSessionManager:
    """Return the global IXSessionManager singleton."""
    if IXSessionManager._instance is None:
        IXSessionManager._instance = IXSessionManager()
    return IXSessionManager._instance


# ═════════════════════════════════════════════════════════════════════════════
# Helper — extract video ID from URL (same logic as download_engine)
# ═════════════════════════════════════════════════════════════════════════════

def _safe_id_from_url(url: str) -> str:
    """Extract a video ID from common platform URL patterns."""
    u = (url or "").strip()
    if not u:
        return ""
    patterns = [
        r"v=([A-Za-z0-9_-]{6,})",
        r"youtu\.be/([A-Za-z0-9_-]{6,})",
        r"/video/(\d+)",
        r"/watch/\?v=(\d+)",
        r"/reel/([A-Za-z0-9_-]+)",
        r"/p/([A-Za-z0-9_-]+)",
        r"facebook\.com/[^/]+/videos/(\d+)",
        r"facebook\.com/watch/\?v=(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, u, re.IGNORECASE)
        if m:
            return m.group(1)
    return u.split("?")[0].rstrip("/").split("/")[-1]
