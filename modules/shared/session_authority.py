"""
SessionAuthority - Unified browser session / auth authority for the entire app.

This module is the SINGLE source of truth for:
  - Is platform X authenticated?
  - Get a fresh cookie file for platform X
  - What browser executable and UA string should be used?
  - Where is the persistent browser profile stored?
  - Is the persistent browser profile currently in use?

All other modules should go through this authority for auth decisions.
Cookie files are treated as interoperability artifacts exported from the
persistent browser profile, NOT as the primary source of truth.

Architecture:
  persistent browser profile (Playwright)
          |
          v
  SessionAuthority  <--- consumers ask here
     |          |          |
     v          v          v
  fresh export  fallback   profile busy?
  ({platform}.txt)         -> last-known-good fallback
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth cookie markers per platform (used for export validation)
# ---------------------------------------------------------------------------
_AUTH_COOKIE_MARKERS: Dict[str, List[Tuple[str, Sequence[str]]]] = {
    "youtube": [
        ("SID", ("google.com",)),
        ("HSID", ("google.com",)),
        ("SSID", ("google.com",)),
    ],
    "instagram": [("sessionid", ("instagram.com",))],
    "tiktok": [
        ("sessionid_ss", ("tiktok.com",)),
        ("sid_tt", ("tiktok.com",)),
        ("sessionid", ("tiktok.com",)),
    ],
    "twitter": [
        ("auth_token", ("x.com", "twitter.com")),
        ("ct0", ("x.com", "twitter.com")),
    ],
    "facebook": [
        ("c_user", ("facebook.com",)),
        ("xs", ("facebook.com",)),
    ],
}

# ---------------------------------------------------------------------------
# Singleton plumbing
# ---------------------------------------------------------------------------
_instance: Optional["SessionAuthority"] = None
_instance_lock = threading.Lock()


def get_session_authority() -> SessionAuthority:
    """Get or create the singleton SessionAuthority instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SessionAuthority()
    return _instance


# ---------------------------------------------------------------------------
# Supported platforms
# ---------------------------------------------------------------------------
PLATFORMS = ("youtube", "instagram", "tiktok", "twitter", "facebook")


# ---------------------------------------------------------------------------
# SessionAuthority
# ---------------------------------------------------------------------------
class SessionAuthority:
    """
    Central authority for browser session, login status, and cookie management.

    Responsibilities:
      - Own the persistent browser profile path
      - Resolve the browser executable and derive a matching User-Agent
      - Determine per-platform login status (with time-based caching)
      - Export fresh Netscape cookies from the profile on demand
      - Provide a single ``get_best_cookie_file(platform)`` that all
        consumers should call instead of doing their own file scanning
      - Invalidate caches after login / logout events
    """

    def __init__(self) -> None:
        from modules.config.paths import get_data_dir, get_cookies_dir, get_application_root

        self._data_dir = get_data_dir()
        self._app_root = get_application_root()
        self._profile_dir = self._data_dir / "browser_profile"
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        self._cookies_dir = get_cookies_dir()

        # Session lock file inside profile dir
        self._session_lock_path = self._profile_dir / ".session_lock"

        # Browser engine
        self._chrome_exe: Optional[str] = None
        self._chrome_version: Optional[str] = None
        self._user_agent: Optional[str] = None
        self._resolve_browser_engine()

        # Strict auth cache (export-grade cookies for yt-dlp)
        self._login_status_cache: Dict[str, bool] = {}
        self._login_status_age: float = 0
        self._status_cache_ttl: float = 300  # 5 minutes

        # Browser session cache (broader indicators for GUI / Re-login)
        self._session_status_cache: Dict[str, bool] = {}
        self._session_status_age: float = 0

        # Cookie export rate-limit
        self._last_export: Dict[str, float] = {}
        self._export_min_interval: float = 30  # seconds

        # Concurrency
        self._lock = threading.Lock()

        # Legacy profile migration (one-time, on first init)
        self._migrate_legacy_profile()

        logger.info(
            "[SessionAuthority] Initialized. profile=%s  chrome=%s  version=%s  ua=%s",
            self._profile_dir,
            self._chrome_exe or "<playwright-default>",
            self._chrome_version or "unknown",
            (self._user_agent or "fallback")[:60],
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def profile_dir(self) -> Path:
        return self._profile_dir

    @property
    def chrome_executable(self) -> Optional[str]:
        return self._chrome_exe

    @property
    def chrome_version(self) -> Optional[str]:
        return self._chrome_version

    @property
    def user_agent(self) -> str:
        """Consistent User-Agent matching the actual Chrome version."""
        return self._user_agent or self._fallback_ua()

    # ------------------------------------------------------------------
    # Browser engine resolution
    # ------------------------------------------------------------------
    def _resolve_browser_engine(self) -> None:
        """Detect system Chrome, determine version, build matching UA."""
        from modules.shared.browser_utils import get_chromium_executable_path

        exe = get_chromium_executable_path()
        self._chrome_exe = exe

        if not exe:
            self._user_agent = self._fallback_ua()
            logger.info("[SessionAuthority] No Chrome found; using Playwright default + fallback UA")
            return

        # Detect actual Chrome version
        version = self._detect_chrome_version(exe)
        if version:
            self._chrome_version = version
            self._user_agent = (
                f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{self._chrome_version} Safari/537.36"
            )
            logger.info(
                "[SessionAuthority] Detected Chrome %s at %s",
                self._chrome_version,
                exe,
            )
            return

        self._user_agent = self._fallback_ua()
        logger.info("[SessionAuthority] Using fallback UA (Chrome exe: %s)", exe)

    @staticmethod
    def _detect_chrome_version(exe_path: str) -> Optional[str]:
        """
        Detect Chrome version from the executable path.

        Strategy (Windows):
          1. Look for version-numbered sibling directories
             (e.g. C:/Program Files/Google/Chrome/Application/145.0.7632.117/)
          2. Check Windows registry (HKCU\\Software\\Google\\Chrome\\BLBeacon)
          3. Try --version flag (works on Linux/Mac)
        """
        version_pattern = re.compile(r"^(\d+\.\d+\.\d+\.\d+)$")

        # Strategy 1: Version directory next to chrome.exe
        try:
            app_dir = Path(exe_path).parent
            for item in app_dir.iterdir():
                if item.is_dir() and version_pattern.match(item.name):
                    return item.name
        except Exception:
            pass

        # Strategy 2: Windows registry
        if os.name == "nt":
            try:
                import winreg
                for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    try:
                        key = winreg.OpenKey(hive, r"Software\Google\Chrome\BLBeacon")
                        val, _ = winreg.QueryValueEx(key, "version")
                        winreg.CloseKey(key)
                        if val and version_pattern.match(str(val)):
                            return str(val)
                    except Exception:
                        continue
            except Exception:
                pass

        # Strategy 3: --version CLI (Linux/Mac)
        try:
            result = subprocess.run(
                [exe_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                match = re.search(r"(\d+\.\d+\.\d+\.\d+)", result.stdout)
                if match:
                    return match.group(1)
        except Exception:
            pass

        return None

    @staticmethod
    def _fallback_ua() -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        )

    # ------------------------------------------------------------------
    # Profile state
    # ------------------------------------------------------------------
    # Files that do NOT indicate a real initialized profile
    _PROFILE_JUNK_NAMES = frozenset({
        ".session_lock", "SingletonLock", "SingletonSocket", "SingletonCookie",
        ".singleton_test", "lockfile", "parent.lock",
    })

    def is_profile_initialized(self) -> bool:
        """True if the persistent browser profile has been used at least once.

        Ignores lock files and other junk artifacts that don't represent
        real Chromium profile data.
        """
        if not self._profile_dir.exists():
            return False
        try:
            for item in self._profile_dir.iterdir():
                if item.name not in self._PROFILE_JUNK_NAMES:
                    return True
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Profile busy detection
    # ------------------------------------------------------------------
    def is_profile_busy(self) -> bool:
        """
        Check if the persistent browser profile is currently in use by
        another Playwright context (same or different process).

        Detection strategy:
          1. Check our own .session_lock file (JSON with pid + timestamp)
          2. Check Chromium's SingletonLock file
          3. If the owning PID is dead, treat the lock as stale
        """
        # Check our session lock
        if self._session_lock_path.exists():
            try:
                data = json.loads(self._session_lock_path.read_text(encoding="utf-8"))
                pid = data.get("pid")
                ts = data.get("timestamp", 0)
                purpose = data.get("purpose", "unknown")

                if pid and self._is_pid_alive(pid):
                    age = time.time() - ts
                    logger.info(
                        "[SessionAuthority] Profile is BUSY (pid=%s, purpose=%s, age=%.0fs)",
                        pid, purpose, age,
                    )
                    return True

                # PID is dead -> stale lock, clean up
                logger.info(
                    "[SessionAuthority] Cleaning stale session lock (pid=%s was dead)", pid
                )
                self._session_lock_path.unlink(missing_ok=True)
            except Exception:
                pass

        # Check Chromium's own SingletonLock
        singleton_lock = self._profile_dir / "SingletonLock"
        if singleton_lock.exists():
            try:
                # On Windows, if we can rename/delete SingletonLock, it's stale
                # If not, Chromium is holding it
                test_path = self._profile_dir / ".singleton_test"
                singleton_lock.rename(test_path)
                test_path.rename(singleton_lock)
                # If rename succeeded, lock is stale
                logger.debug("[SessionAuthority] SingletonLock exists but is stale (rename succeeded)")
            except (OSError, PermissionError):
                logger.info("[SessionAuthority] Profile is BUSY (Chromium SingletonLock is held)")
                return True

        return False

    def write_session_lock(self, purpose: str) -> None:
        """Write a session lock file. Call before launching a persistent context."""
        try:
            self._session_lock_path.write_text(
                json.dumps({
                    "pid": os.getpid(),
                    "timestamp": time.time(),
                    "purpose": purpose,
                }, indent=2),
                encoding="utf-8",
            )
            logger.info("[SessionAuthority] Session lock written (purpose=%s, pid=%s)", purpose, os.getpid())
        except Exception as exc:
            logger.warning("[SessionAuthority] Failed to write session lock: %s", exc)

    def clear_session_lock(self) -> None:
        """Remove the session lock file. Call after closing a persistent context."""
        try:
            self._session_lock_path.unlink(missing_ok=True)
            logger.info("[SessionAuthority] Session lock cleared")
        except Exception as exc:
            logger.warning("[SessionAuthority] Failed to clear session lock: %s", exc)

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """Check if a process with the given PID is still running."""
        if not pid or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError, SystemError):
            return False

    # ------------------------------------------------------------------
    # Legacy profile migration
    # ------------------------------------------------------------------
    def _migrate_legacy_profile(self) -> None:
        """
        One-time migration: if a legacy browser profile exists at a
        different location, move it to the canonical path.

        Known legacy locations:
          - app_root/data_files/browser_profile/
        """
        if self.is_profile_initialized():
            return  # Current profile already has content, no migration needed

        legacy_candidates = [
            self._app_root / "data_files" / "browser_profile",
        ]

        for legacy_path in legacy_candidates:
            try:
                if not legacy_path.exists() or not legacy_path.is_dir():
                    continue
                # Check for real profile content (not just lock/junk files)
                has_real_content = any(
                    item.name not in self._PROFILE_JUNK_NAMES
                    for item in legacy_path.iterdir()
                )
                if not has_real_content:
                    continue

                logger.info(
                    "[SessionAuthority] Found legacy profile at %s - migrating to %s",
                    legacy_path, self._profile_dir,
                )
                # Copy contents (not move, to be safe)
                for item in legacy_path.iterdir():
                    dest = self._profile_dir / item.name
                    if dest.exists():
                        continue
                    if item.is_dir():
                        shutil.copytree(str(item), str(dest), dirs_exist_ok=True)
                    else:
                        shutil.copy2(str(item), str(dest))

                logger.info("[SessionAuthority] Legacy profile migrated successfully")
                return
            except Exception as exc:
                logger.warning("[SessionAuthority] Legacy profile migration failed from %s: %s", legacy_path, exc)

    # ------------------------------------------------------------------
    # Cookie export validation
    # ------------------------------------------------------------------
    @staticmethod
    def _cookie_file_has_auth(file_path: Path, platform: str) -> bool:
        """
        Check if a Netscape cookie file contains real auth cookies for a platform.
        Returns True if at least one auth marker is present.
        """
        markers = _AUTH_COOKIE_MARKERS.get(platform, [])
        if not markers:
            return False

        try:
            if not file_path.exists() or file_path.stat().st_size < 10:
                return False

            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for cookie_name, domain_tokens in markers:
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        domain_field = parts[0].lower()
                        name_field = parts[5].strip()
                        if name_field == cookie_name:
                            if any(token in domain_field for token in domain_tokens):
                                if platform == "tiktok":
                                    logger.debug(
                                        "[TikTokAuth] Cookie file %s has auth marker: %s",
                                        file_path.name, cookie_name,
                                    )
                                return True

            if platform == "tiktok":
                # Log cookie names present to aid debugging stricter markers
                cookie_names_in_file = set()
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7 and "tiktok" in parts[0].lower():
                        cookie_names_in_file.add(parts[5].strip())
                logger.info(
                    "[TikTokAuth] Cookie file %s: no auth marker matched. "
                    "TikTok cookies present: %s",
                    file_path.name,
                    sorted(cookie_names_in_file)[:15] if cookie_names_in_file else "none",
                )
        except Exception:
            pass
        return False

    def _safe_to_overwrite_cookie_file(self, platform: str, new_file: Path) -> bool:
        """
        Determine if it's safe to overwrite the canonical cookie file.

        Rule: NEVER overwrite an existing file that has valid auth cookies
        with a new file that does NOT have auth cookies.  This prevents
        a stale/empty profile export from wiping out a known-good cookie file.
        """
        canonical = self._cookies_dir / f"{platform}.txt"

        # No existing file -> always safe to write
        if not canonical.exists() or canonical.stat().st_size < 10:
            return True

        # New file has auth -> safe to overwrite
        if self._cookie_file_has_auth(new_file, platform):
            return True

        # New file has NO auth, existing DOES have auth -> NOT safe
        if self._cookie_file_has_auth(canonical, platform):
            logger.info(
                "[SessionAuthority] BLOCKED overwrite of %s: existing file has auth cookies, "
                "new export does not. Keeping existing file.",
                canonical.name,
            )
            return False

        # Both have no auth -> safe to overwrite
        return True

    # ------------------------------------------------------------------
    # Login status
    # ------------------------------------------------------------------
    def get_login_status(self, force_refresh: bool = False) -> Dict[str, bool]:
        """STRICT AUTH LAYER: which platforms have export-grade auth cookies?

        Returns True only when the profile has strong auth markers
        (sessionid, SID, c_user, etc.) trusted for cookie export to
        yt-dlp / instaloader.

        For GUI / Re-login decisions, use get_session_status() instead.

        Uses a time-based cache (default 5 min) to avoid launching
        Playwright on every call.
        """
        now = time.time()
        if (
            not force_refresh
            and self._login_status_cache
            and (now - self._login_status_age) < self._status_cache_ttl
        ):
            return dict(self._login_status_cache)

        if not self.is_profile_initialized():
            return {p: False for p in PLATFORMS}

        # If profile is busy, don't try to launch another context
        if self.is_profile_busy():
            logger.info(
                "[SessionAuthority] Profile busy - returning cached/metadata login status"
            )
            if self._login_status_cache:
                return dict(self._login_status_cache)
            return self._read_persisted_login_status()

        try:
            from modules.link_grabber.browser_auth import ChromiumAuthManager

            auth = ChromiumAuthManager(profile_dir=self._profile_dir)
            status = auth.get_login_status()
            auth.close_all()

            self._login_status_cache = status
            self._login_status_age = now

            logged_in = sorted(k for k, v in status.items() if v)
            logger.info(
                "[SessionAuthority] Login status refreshed. Logged in: %s",
                logged_in or "none",
            )
            return dict(status)
        except Exception as exc:
            logger.error("[SessionAuthority] Login status check failed: %s", exc)
            if self._login_status_cache:
                return dict(self._login_status_cache)
            return self._read_persisted_login_status()

    def _read_persisted_login_status(self) -> Dict[str, bool]:
        """
        Read login status from the persisted auth_state.json metadata file.
        This is a last-resort fallback when the profile is busy or Playwright fails.
        """
        result = {p: False for p in PLATFORMS}
        try:
            from modules.shared.auth_network_hub import AuthNetworkHub
            hub = AuthNetworkHub()
            if hub.auth_state_file.exists():
                data = json.loads(hub.auth_state_file.read_text(encoding="utf-8"))
                platforms = data.get("cookies", {}).get("platforms", [])
                for p in platforms:
                    if p in result:
                        result[p] = True
                logger.info(
                    "[SessionAuthority] Using persisted metadata for login status: %s",
                    sorted(p for p, v in result.items() if v) or "none",
                )
        except Exception:
            pass
        return result

    def is_platform_logged_in(self, platform: str) -> bool:
        """Quick strict-auth check for a single platform."""
        return self.get_login_status().get(platform.lower().strip(), False)

    def get_session_status(self, force_refresh: bool = False) -> Dict[str, bool]:
        """BROWSER SESSION LAYER: which platforms have a browser session?

        Returns True when the managed browser has broader session evidence
        (passport_csrf_token, ds_user_id, twid, c_user, etc.) — enough
        to treat the user as "logged in" for GUI display and Re-login
        decisions, but NOT strong enough for cookie export trust.

        For downloader / cookie export decisions, use get_login_status().
        """
        now = time.time()
        if (
            not force_refresh
            and self._session_status_cache
            and (now - self._session_status_age) < self._status_cache_ttl
        ):
            return dict(self._session_status_cache)

        if not self.is_profile_initialized():
            return {p: False for p in PLATFORMS}

        if self.is_profile_busy():
            if self._session_status_cache:
                return dict(self._session_status_cache)
            return self._read_persisted_login_status()

        try:
            from modules.link_grabber.browser_auth import ChromiumAuthManager

            auth = ChromiumAuthManager(profile_dir=self._profile_dir)
            status = auth.get_session_status()
            auth.close_all()

            self._session_status_cache = status
            self._session_status_age = now

            sessions = sorted(k for k, v in status.items() if v)
            logger.info(
                "[SessionAuthority] Session status refreshed. Sessions: %s",
                sessions or "none",
            )
            return dict(status)
        except Exception as exc:
            logger.error("[SessionAuthority] Session status check failed: %s", exc)
            if self._session_status_cache:
                return dict(self._session_status_cache)
            return self._read_persisted_login_status()

    # ------------------------------------------------------------------
    # Cookie export
    # ------------------------------------------------------------------
    def ensure_fresh_cookies(self, platform: str) -> Optional[str]:
        """
        Export fresh Netscape cookies from the persistent browser profile.

        This is the PREFERRED way for downstream consumers (yt-dlp, etc.)
        to obtain cookies.  Returns the path to the fresh cookie file,
        or None if the profile has no auth for this platform.

        Rate-limited to avoid excessive Playwright launches.
        If the profile is busy, falls back to the last-known-good cookie file.
        """
        platform = platform.lower().strip()
        if platform not in PLATFORMS:
            return None

        now = time.time()
        last = self._last_export.get(platform, 0)
        canonical = self._cookies_dir / f"{platform}.txt"

        # Rate limit: reuse recently exported file, but only if it has auth
        if (now - last) < self._export_min_interval:
            if canonical.exists() and canonical.stat().st_size > 10:
                if self._cookie_file_has_auth(canonical, platform):
                    logger.info(
                        "[SessionAuthority] Reusing recently exported cookies for %s (age %.0fs)",
                        platform, now - last,
                    )
                    return str(canonical)
                logger.debug(
                    "[SessionAuthority] Rate-limited file for %s exists but lacks auth; re-exporting",
                    platform,
                )

        if not self.is_profile_initialized():
            logger.info("[SessionAuthority] Profile not initialized; cannot export for %s", platform)
            return self._last_known_good_cookie(platform)

        # If profile is busy, fall back to existing cookie file
        if self.is_profile_busy():
            logger.info(
                "[SessionAuthority] Profile busy; deferring export for %s. Using last-known-good.",
                platform,
            )
            return self._last_known_good_cookie(platform)

        with self._lock:
            try:
                from modules.link_grabber.browser_auth import ChromiumAuthManager

                auth = ChromiumAuthManager(profile_dir=self._profile_dir)
                result = auth.extract_cookies_for_platform(platform)
                auth.close_all()

                self._last_export[platform] = time.time()

                if result:
                    # Prefer canonical file, but ONLY if it has real auth
                    if canonical.exists() and canonical.stat().st_size > 10:
                        if self._cookie_file_has_auth(canonical, platform):
                            logger.info(
                                "[SessionAuthority] Fresh cookies exported for %s -> %s (auth=True)",
                                platform, canonical.name,
                            )
                            return str(canonical)
                        logger.info(
                            "[SessionAuthority] Fresh export wrote %s but file lacks auth markers for %s; "
                            "not returning as authenticated cookie",
                            canonical.name, platform,
                        )
                    # Check if the staging file itself has auth
                    result_path = Path(result)
                    if result_path.exists() and self._cookie_file_has_auth(result_path, platform):
                        return result

                logger.info("[SessionAuthority] No authenticated cookies in profile for %s", platform)
                return self._last_known_good_cookie(platform)
            except Exception as exc:
                logger.error("[SessionAuthority] Cookie export failed for %s: %s", platform, exc)
                return self._last_known_good_cookie(platform)

    def _last_known_good_cookie(self, platform: str) -> Optional[str]:
        """
        Return the existing canonical cookie file ONLY if it has valid auth cookies.
        This is the fallback when fresh export is not possible.
        Returns None if no file with real auth markers exists.
        """
        candidates = [
            self._cookies_dir / f"{platform}.txt",
            self._cookies_dir / "browser_cookies" / f"{platform}_chromium_profile.txt",
        ]

        for cookie_file in candidates:
            if not cookie_file.exists() or cookie_file.stat().st_size < 10:
                continue
            if self._cookie_file_has_auth(cookie_file, platform):
                logger.info(
                    "[SessionAuthority] Last-known-good cookie for %s: %s (has_auth=True)",
                    platform, cookie_file.name,
                )
                return str(cookie_file)
            logger.debug(
                "[SessionAuthority] Skipping %s for %s (no auth markers)",
                cookie_file.name, platform,
            )

        logger.info(
            "[SessionAuthority] No authenticated last-known-good cookie for %s", platform
        )
        return None

    def get_best_cookie_file(
        self, platform: str, source_folder: Optional[str] = None
    ) -> Optional[str]:
        """
        Get the best available cookie file for a platform.

        Decision order:
          1. Fresh export from persistent browser profile
          2. Existing per-platform cookie file (from prior export or user import)
          3. Generic / legacy cookie files

        This should be called instead of AuthNetworkHub.pick_cookie_file()
        whenever profile-first auth is desired.
        """
        platform = platform.lower().strip()

        # Step 1: Fresh export from profile
        fresh = self.ensure_fresh_cookies(platform)
        if fresh:
            logger.info(
                "[SessionAuthority] Best cookie for %s: fresh profile export (%s)",
                platform,
                Path(fresh).name,
            )
            return fresh

        # Step 2: Fall back to file scan via AuthNetworkHub
        from modules.shared.auth_network_hub import AuthNetworkHub

        hub = AuthNetworkHub()
        fallback = hub.pick_cookie_file(platform, source_folder)
        if fallback:
            fallback_path = Path(fallback)
            # Validate: don't return unauthenticated files for platforms
            # where we have auth markers defined
            if platform in _AUTH_COOKIE_MARKERS:
                if self._cookie_file_has_auth(fallback_path, platform):
                    logger.info(
                        "[SessionAuthority] Best cookie for %s: fallback file (%s, auth=True)",
                        platform, fallback_path.name,
                    )
                    return fallback
                logger.info(
                    "[SessionAuthority] Rejecting fallback %s for %s: file exists but lacks auth markers",
                    fallback_path.name, platform,
                )
                return None
            # Platform has no auth markers defined — accept the file as-is
            logger.info(
                "[SessionAuthority] Best cookie for %s: fallback file (%s, no markers defined)",
                platform, fallback_path.name,
            )
            return fallback

        logger.info("[SessionAuthority] No cookie file available for %s", platform)
        return None

    # ------------------------------------------------------------------
    # Browser session recovery (live-context cookie refresh)
    # ------------------------------------------------------------------
    def force_browser_cookie_refresh(self, platform: str) -> Optional[str]:
        """
        BROWSER SESSION RECOVERY — genuinely different from ensure_fresh_cookies().

        ensure_fresh_cookies():
          Opens headless context -> reads cookies from profile DB -> exports.
          No navigation. Tokens may be stale/expired in the DB.

        force_browser_cookie_refresh():
          Opens headless context -> navigates to platform home URL ->
          browser auto-authenticates -> platform rotates/refreshes tokens ->
          reads cookies from the LIVE NAVIGATED CONTEXT via context.cookies() ->
          writes Netscape file from those live cookies.

        Critical: Does NOT call extract_cookies_for_platform() which would
        open a SEPARATE context and lose the refreshed live state.
        Instead, reads context.cookies() from the SAME navigated context,
        filters by domain, and writes via auth._write_netscape_cookies().
        """
        with self._lock:
            home_urls = {
                "youtube": "https://www.youtube.com",
                "tiktok": "https://www.tiktok.com",
                "instagram": "https://www.instagram.com",
                "facebook": "https://www.facebook.com",
                "twitter": "https://x.com",
            }
            home_url = home_urls.get(platform)
            if not home_url:
                return None
            if self.is_profile_busy():
                return None

            auth = None
            context = None
            try:
                from modules.link_grabber.browser_auth import ChromiumAuthManager

                auth = ChromiumAuthManager(profile_dir=self._profile_dir)
                context = auth.launch_headless_context()  # can raise
                if context is None:
                    return None

                page = context.new_page()
                page.goto(home_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)

                live_cookies = context.cookies()
                page.close()

                if not auth._has_platform_cookies(live_cookies, platform):
                    return None

                domain_tokens = auth._platform_domain_tokens.get(platform, ())
                filtered = [
                    c for c in live_cookies
                    if any(t in c.get("domain", "").lower() for t in domain_tokens)
                ]

                out_dir = self._cookies_dir / "browser_cookies"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"{platform}_chromium_profile.txt"
                auth._write_netscape_cookies(filtered, out_path, platform)
                auth._safe_write_canonical(filtered, platform, out_path)

                canonical = self._cookies_dir / f"{platform}.txt"
                if canonical.exists() and self._cookie_file_has_auth(canonical, platform):
                    self._last_export[platform] = time.time()
                    return str(canonical)
                if out_path.exists() and self._cookie_file_has_auth(out_path, platform):
                    self._last_export[platform] = time.time()
                    return str(out_path)
                return None
            except Exception as e:
                logger.warning(
                    "[SessionAuthority] force_browser_cookie_refresh(%s) failed: %s",
                    platform, e,
                )
                return None
            finally:
                if context is not None:
                    try:
                        auth._close_context(context)
                    except Exception:
                        pass
                if auth is not None:
                    try:
                        auth.close_all()
                    except Exception:
                        pass

    # ------------------------------------------------------------------
    # Cache invalidation
    # ------------------------------------------------------------------
    def invalidate_cache(self) -> None:
        """
        Invalidate all cached state.  Call after login, logout, or
        profile reset events.
        """
        self._login_status_cache.clear()
        self._login_status_age = 0
        self._session_status_cache.clear()
        self._session_status_age = 0
        self._last_export.clear()
        logger.info("[SessionAuthority] All caches invalidated")

    # ------------------------------------------------------------------
    # Auth state persistence (metadata for GUI display)
    # ------------------------------------------------------------------
    def persist_auth_state(self, platform_status: Dict[str, bool], source: str) -> None:
        """
        Write login status metadata so the GUI can display it without
        launching Playwright.  This is metadata only, not the source of truth.
        """
        try:
            from modules.shared.auth_network_hub import AuthNetworkHub

            hub = AuthNetworkHub()
            logged_in = sorted(k for k, v in platform_status.items() if v)
            hub.write_auth_state({
                "cookies": {
                    "platforms": logged_in,
                    "source": source,
                },
            })
            logger.info(
                "[SessionAuthority] Auth state persisted (source=%s, platforms=%s)",
                source,
                logged_in,
            )
        except Exception as exc:
            logger.warning("[SessionAuthority] Failed to persist auth state: %s", exc)

    # ------------------------------------------------------------------
    # Login-complete notification (called after Re-login / manual fallback)
    # ------------------------------------------------------------------
    def notify_login_complete(
        self,
        platform: str,
        source: str = "unknown",
        detected_status: Optional[Dict[str, bool]] = None,
    ) -> None:
        """
        Notify SessionAuthority that a login event just completed.

        This should be called by any flow that logs in to a platform
        (Re-login, auto_login, manual fallback, etc.) to ensure:
          1. Caches are invalidated
          2. Fresh cookies are exported from the persistent profile
          3. Auth metadata is updated for GUI display
          4. The session lock is cleared

        Args:
            platform: The platform that was logged in (or "all")
            source: Description of the login source (e.g., "relogin", "auto_login")
            detected_status: If provided, use this instead of launching a
                separate headless browser to re-check login status.
                Callers that already have fresh cookie data (e.g.
                ``open_login_browser``) should pass it here.
        """
        logger.info(
            "[SessionAuthority] Login complete notification: platform=%s source=%s",
            platform, source,
        )

        # 1. Clear session lock (the login browser should be closed by now)
        self.clear_session_lock()

        # 2. Invalidate all caches
        self.invalidate_cache()

        # 3. Refresh login status and export cookies
        try:
            if detected_status is not None:
                # detected_status comes from has_platform_session() (BROAD).
                # Seed the SESSION cache (browser-session layer) — NOT the
                # strict auth cache, which must be populated from
                # _has_platform_cookies() only.
                session_status = detected_status
                self._session_status_cache = dict(session_status)
                self._session_status_age = time.time()

                # Populate strict auth cache separately so downstream
                # cookie export decisions use the correct layer.
                strict_status = self.get_login_status(force_refresh=True)
            else:
                strict_status = self.get_login_status(force_refresh=True)
                session_status = strict_status  # best-effort when no broad data

            # Export cookies for platforms that have strict auth
            for p, has_auth in strict_status.items():
                if has_auth:
                    self.ensure_fresh_cookies(p)

            # Persist metadata for GUI (uses session layer — the broader check)
            self.persist_auth_state(session_status, source)

            strict_list = sorted(k for k, v in strict_status.items() if v)
            session_list = sorted(k for k, v in session_status.items() if v)
            logger.info(
                "[SessionAuthority] Post-login state: "
                "strict_auth=%s  browser_session=%s",
                strict_list, session_list,
            )
        except Exception as exc:
            logger.error("[SessionAuthority] Post-login sync failed: %s", exc)


# ---------------------------------------------------------------------------
# AuthFallbackChain — production-grade cookie source chain
# ---------------------------------------------------------------------------

# Source IDs (stable, never shown to GUI)
AUTH_SRC_MANAGED = "managed_profile"
AUTH_SRC_GUI_COOKIE = "gui_user_cookie"
AUTH_SRC_LAST_KNOWN = "last_known_good"
AUTH_SRC_BROWSER_REFRESH = "browser_refresh_recovery"

_SOURCE_MEMORY_FILE = "auth_source_memory.json"
_SOURCE_MEMORY_MAX_AGE = 7 * 86400  # 7 days


class AuthFallbackChain:
    """Four-source auth chain with strict validation and source memory.

    Priority:
      1. managed_profile    — fresh export from persistent browser profile
      2. gui_user_cookie    — user-provided cookie file in cookies/ dir
      3. last_known_good    — prior canonical cookie with valid auth markers
      4. browser_refresh    — live navigation refresh (if profile not busy)

    Each source is strictly validated with platform-specific auth markers
    before being accepted.  The chain never overwrites authenticated
    canonical cookies with weaker/unauthenticated files.

    Source memory persists the most recent successful source per
    creator+platform so the preferred source is tried first next run.
    """

    def __init__(self) -> None:
        from modules.config.paths import get_data_dir, get_cookies_dir

        self._sa = get_session_authority()
        self._cookies_dir = get_cookies_dir()
        self._data_dir = get_data_dir()
        self._memory_file = self._data_dir / _SOURCE_MEMORY_FILE
        self._memory: Dict = self._load_memory()

    # ------------------------------------------------------------------
    # Source memory (per creator+platform)
    # ------------------------------------------------------------------
    def _load_memory(self) -> Dict:
        try:
            if self._memory_file.exists():
                return json.loads(self._memory_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_memory(self) -> None:
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._memory_file.write_text(
                json.dumps(self._memory, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug("[AuthSourceMemory] save failed: %s", exc)

    def get_preferred_source(self, creator: str, platform: str) -> Optional[str]:
        """Return the preferred auth source for a creator+platform, or None."""
        key = f"{creator}|{platform}".lower()
        entry = self._memory.get(key)
        if not entry:
            return None
        age = time.time() - entry.get("ts", 0)
        if age > _SOURCE_MEMORY_MAX_AGE:
            return None
        return entry.get("source")

    def record_success(self, creator: str, platform: str, source: str) -> None:
        """Record that a source worked for a creator+platform."""
        key = f"{creator}|{platform}".lower()
        self._memory[key] = {"source": source, "ts": time.time()}
        self._save_memory()
        logger.info(
            "[AuthSourceMemory] recorded best_source=%s for %s",
            source, key,
        )

    # ------------------------------------------------------------------
    # Core chain
    # ------------------------------------------------------------------
    def resolve_cookie(
        self,
        platform: str,
        creator: str = "",
    ) -> Tuple[Optional[str], str]:
        """Walk the fallback chain and return (cookie_path, source_id).

        Returns (None, "") if no authenticated cookie could be found.
        Logs every step with [AuthSource] / [AuthFallback] tags.
        """
        platform = platform.lower().strip()

        # Build ordered source list (preferred source first if known)
        sources = [
            AUTH_SRC_MANAGED,
            AUTH_SRC_GUI_COOKIE,
            AUTH_SRC_LAST_KNOWN,
            AUTH_SRC_BROWSER_REFRESH,
        ]
        preferred = self.get_preferred_source(creator, platform) if creator else None
        if preferred and preferred in sources:
            sources.remove(preferred)
            sources.insert(0, preferred)
            logger.info(
                "[AuthSource] preferred=%s for %s|%s (from memory)",
                preferred, creator, platform,
            )

        prev_source = None
        for src in sources:
            cookie_path = self._try_source(platform, src)
            if cookie_path:
                if prev_source:
                    logger.info(
                        "[AuthFallback] from=%s to=%s reason=prev_source_failed platform=%s",
                        prev_source, src, platform,
                    )
                logger.info(
                    "[AuthSource] selected=%s cookie=%s platform=%s",
                    src, Path(cookie_path).name, platform,
                )
                return cookie_path, src
            prev_source = src

        logger.warning(
            "[AuthSource] ALL sources exhausted for %s — no authenticated cookie",
            platform,
        )
        return None, ""

    def _try_source(self, platform: str, source: str) -> Optional[str]:
        """Try a single source, return validated cookie path or None."""
        try:
            if source == AUTH_SRC_MANAGED:
                return self._try_managed(platform)
            elif source == AUTH_SRC_GUI_COOKIE:
                return self._try_gui_cookie(platform)
            elif source == AUTH_SRC_LAST_KNOWN:
                return self._try_last_known(platform)
            elif source == AUTH_SRC_BROWSER_REFRESH:
                return self._try_browser_refresh(platform)
        except Exception as exc:
            logger.debug("[AuthSource] %s failed for %s: %s", source, platform, exc)
        return None

    def _try_managed(self, platform: str) -> Optional[str]:
        """Source 1: Fresh export from managed browser profile."""
        # Check cooldown — if managed profile is in cooldown, skip silently
        try:
            from modules.link_grabber.browser_auth import ChromiumAuthManager
            auth = ChromiumAuthManager()
            cooldown_reason = auth.is_in_cooldown(platform)
            if cooldown_reason:
                logger.info(
                    "[AuthSource] managed_profile SKIPPED for %s — cooldown: %s",
                    platform, cooldown_reason,
                )
                return None
        except Exception:
            pass

        cookie_path = self._sa.ensure_fresh_cookies(platform)
        if cookie_path and self._validate(cookie_path, platform):
            return cookie_path
        return None

    def _try_gui_cookie(self, platform: str) -> Optional[str]:
        """Source 2: User-provided cookie file in cookies/ directory.

        Looks for platform-specific files that the user manually placed
        (e.g., instagram.txt, facebook.txt) and validates auth markers.
        Does NOT scan local browser profiles.
        """
        candidates = [
            self._cookies_dir / f"{platform}.txt",
            self._cookies_dir / "browser_cookies" / f"{platform}_chromium_profile.txt",
        ]
        for c in candidates:
            if c.exists() and c.stat().st_size > 10:
                if self._validate(str(c), platform):
                    return str(c)
        return None

    def _try_last_known(self, platform: str) -> Optional[str]:
        """Source 3: Last-known-good canonical cookie file."""
        cookie_path = self._sa._last_known_good_cookie(platform)
        if cookie_path and self._validate(cookie_path, platform):
            return cookie_path
        return None

    def _try_browser_refresh(self, platform: str) -> Optional[str]:
        """Source 4: Live browser navigation refresh (only if profile not busy)."""
        if self._sa.is_profile_busy():
            logger.info(
                "[AuthSource] browser_refresh SKIPPED for %s — profile busy",
                platform,
            )
            return None
        cookie_path = self._sa.force_browser_cookie_refresh(platform)
        if cookie_path and self._validate(cookie_path, platform):
            return cookie_path
        return None

    def _validate(self, cookie_path: str, platform: str) -> bool:
        """Strict validation: cookie file must have platform auth markers."""
        p = Path(cookie_path)
        if not p.exists() or p.stat().st_size < 10:
            return False
        return self._sa._cookie_file_has_auth(p, platform)
