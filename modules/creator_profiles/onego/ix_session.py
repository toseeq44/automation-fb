"""
IX Browser session manager for OneGo.
Opens profiles, attaches Selenium, extracts bookmarks.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .ix_api import IXBrowserClient, IXAPIError, IXProfile, IXSession

log = logging.getLogger(__name__)

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
        """Open profile, attach Selenium driver, return ProfileSession or None on failure."""
        try:
            ix_sess = self.client.open_profile(profile.profile_id)
        except IXAPIError as exc:
            log.error("[OneGo-IX] Failed to open profile '%s': %s", profile.profile_name, exc)
            return None

        debug_addr = ix_sess.debugging_address
        if not debug_addr:
            log.error("[OneGo-IX] No debugging address for profile '%s'", profile.profile_name)
            self.client.close_profile(profile.profile_id)
            return None

        driver = self._attach_selenium(debug_addr)
        if not driver:
            log.error("[OneGo-IX] Selenium attach failed for '%s' at %s",
                      profile.profile_name, debug_addr)
            self.client.close_profile(profile.profile_id)
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
    def _attach_selenium(debug_address: str):
        """Attach Selenium to a running Chrome instance via debugging address."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            opts = Options()
            opts.add_experimental_option("debuggerAddress", debug_address)
            driver = webdriver.Chrome(options=opts)
            log.info("[OneGo-IX] Selenium attached to %s", debug_address)
            return driver
        except Exception as exc:
            log.error("[OneGo-IX] Selenium attach error: %s", exc)
            return None
