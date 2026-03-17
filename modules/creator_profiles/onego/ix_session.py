"""
IX Browser session manager for OneGo.
Opens profiles, attaches Selenium, extracts bookmarks.
"""

from __future__ import annotations

import logging
import platform
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .ix_api import IXBrowserClient, IXAPIError, IXProfile, IXSession

log = logging.getLogger(__name__)


def _bring_profile_visible(driver) -> bool:
    """Maximize browser and bring to foreground. Best-effort, never crashes."""
    # 1. Selenium maximize + focus
    try:
        driver.maximize_window()
        driver.switch_to.window(driver.current_window_handle)
        driver.execute_script("window.focus();")
        log.info("[OneGo-IX] Selenium maximize/focus applied")
    except Exception:
        pass

    title = ""
    try:
        title = driver.title or ""
    except Exception:
        title = ""

    # 2. Try existing Windows window manager helpers (same behavior family as auto_uploader)
    if platform.system().lower() == "windows":
        try:
            from modules.auto_uploader.approaches.ixbrowser.window_manager import (
                bring_window_to_front_windows,
                maximize_window_windows,
            )
            if title:
                maximize_window_windows(title)
                bring_window_to_front_windows(title, partial_match=True)
                log.info("[OneGo-IX] Windows helper maximize/foreground applied")
        except Exception:
            pass

    # 3. Win32 SetForegroundWindow + SW_MAXIMIZE via ctypes (no subprocess)
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        SW_MAXIMIZE = 3
        if not title:
            return True  # nothing to match

        def _callback(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if title[:30].lower() in buf.value.lower():
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.ShowWindow(hwnd, SW_MAXIMIZE)
                user32.SetForegroundWindow(hwnd)
                log.info("[OneGo-IX] Win32 foreground set for '%s'", buf.value[:60])
                return False  # stop enumeration
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(_callback), 0)
    except Exception:
        pass  # non-Windows or ctypes unavailable

    return True


# JS to extract all bookmarks via chrome.bookmarks API
_BOOKMARK_SCRIPT = """
return new Promise((resolve) => {
    chrome.bookmarks.getTree((tree) => {
        let bookmarks = [];
        function walk(nodes) {
            nodes.forEach(node => {
                if (node.url) {
                    bookmarks.push({ title: node.title, url: node.url });
                }
                if (node.children) {
                    walk(node.children);
                }
            });
        }
        walk(tree);
        resolve(bookmarks);
    });
});
"""


@dataclass
class Bookmark:
    title: str
    url: str


@dataclass
class ProfileSession:
    """Holds state for one open IX profile."""
    profile: IXProfile
    ix_session: IXSession
    bookmarks: List[Bookmark] = field(default_factory=list)
    driver: Any = None  # selenium WebDriver, set after attach


class IXSessionManager:
    """
    Manages opening IX profiles, attaching Selenium, and extracting bookmarks.
    """

    def __init__(self, client: IXBrowserClient):
        self.client = client

    def open_and_attach(self, profile: IXProfile) -> Optional[ProfileSession]:
        """Open profile, attach Selenium driver, return ProfileSession or None on failure.

        Sets self.last_failure_reason (str) on failure for the caller to inspect.
        """
        self.last_failure_reason = None
        ix_sess: Optional[IXSession] = None
        for attempt in range(1, 4):
            try:
                ix_sess = self.client.open_profile(profile.profile_id)
                break
            except IXAPIError as exc:
                is_kernel_missing = getattr(exc, "code", None) == 2013
                if is_kernel_missing and attempt < 3:
                    wait_s = 2 * attempt
                    log.warning(
                        "[OneGo-IX] Kernel missing while opening '%s' (attempt %d/3). "
                        "Waiting %ss and retrying...",
                        profile.profile_name,
                        attempt,
                        wait_s,
                    )
                    try:
                        self.client.close_profile(profile.profile_id)
                    except Exception:
                        pass
                    time.sleep(wait_s)
                    continue

                log.error("[OneGo-IX] Failed to open profile '%s': %s", profile.profile_name, exc)
                self.last_failure_reason = (
                    "kernel_missing" if is_kernel_missing else "profile_open_failed"
                )
                return None

        if not ix_sess:
            self.last_failure_reason = "profile_open_failed"
            return None

        debug_addr = ix_sess.debugging_address
        if not debug_addr:
            log.error("[OneGo-IX] No debugging address for profile '%s'", profile.profile_name)
            self.client.close_profile(profile.profile_id)
            self.last_failure_reason = "profile_open_failed"
            return None

        driver, attach_hint = self._attach_selenium(debug_addr, ix_sess.webdriver_path)
        if not driver:
            log.error("[OneGo-IX] Selenium attach failed for '%s' at %s",
                      profile.profile_name, debug_addr)
            self.client.close_profile(profile.profile_id)
            self.last_failure_reason = attach_hint or "selenium_attach_failed"
            return None

        ps = ProfileSession(profile=profile, ix_session=ix_sess, driver=driver)
        return ps

    def extract_bookmarks(self, ps: ProfileSession, facebook_only: bool = True) -> List[Bookmark]:
        """Extract bookmarks from a profile session. Filters to Facebook by default."""
        driver = ps.driver
        if not driver:
            return []

        try:
            # Open new tab and go to chrome://bookmarks
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            driver.get("chrome://bookmarks/")
            time.sleep(2)

            raw = driver.execute_script(_BOOKMARK_SCRIPT)
            all_bm = [Bookmark(title=b.get("title", ""), url=b.get("url", "")) for b in (raw or [])]
            log.info("[OneGo-IX] Retrieved %d total bookmark(s) from '%s'",
                     len(all_bm), ps.profile.profile_name)

            if facebook_only:
                filtered = [b for b in all_bm if "facebook.com" in b.url.lower()]
                log.info("[OneGo-IX] Filtered to %d Facebook bookmark(s)", len(filtered))
                ps.bookmarks = filtered
                return filtered

            ps.bookmarks = all_bm
            return all_bm
        except Exception as exc:
            log.error("[OneGo-IX] Bookmark extraction failed for '%s': %s",
                      ps.profile.profile_name, exc)
            return []

    def close(self, ps: ProfileSession) -> None:
        """Close Selenium driver and IX profile."""
        try:
            if ps.driver:
                ps.driver.quit()
                ps.driver = None
        except Exception:
            pass
        try:
            self.client.close_profile(ps.ix_session.profile_id)
        except Exception:
            pass

    @staticmethod
    def _attach_selenium(
        debug_address: str, webdriver_path: str = None
    ) -> Tuple[Any, Optional[str]]:
        """Attach Selenium to a running Chrome instance via debugging address.

        Returns (driver, None) on success or (None, failure_hint) on failure.
        failure_hint is one of: "driver_mismatch", "selenium_attach_failed".
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            opts = Options()
            opts.add_experimental_option("debuggerAddress", debug_address)

            if webdriver_path:
                log.info("[OneGo-IX] Using webdriver at: %s", webdriver_path)
                service = Service(executable_path=webdriver_path)
                driver = webdriver.Chrome(service=service, options=opts)
            else:
                driver = webdriver.Chrome(options=opts)

            log.info("[OneGo-IX] Selenium attached to %s", debug_address)
            return driver, None
        except Exception as exc:
            msg = str(exc).lower()
            # Detect ChromeDriver / Chrome version mismatch
            if "only supports chrome version" in msg or (
                "chrome version" in msg and "current browser version" in msg
            ) or "this version of chromedriver" in msg:
                log.error("[OneGo-IX] Driver/browser version mismatch: %s", exc)
                return None, "driver_mismatch"
            log.error("[OneGo-IX] Selenium attach error: %s", exc)
            return None, "selenium_attach_failed"
