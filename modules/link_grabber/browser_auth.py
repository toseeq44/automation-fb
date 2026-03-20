"""
Persistent Chromium auth/session manager for Link Grabber.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple, Union
from urllib.parse import urljoin, urlparse

from ..shared.browser_utils import delete_browser_profile, get_chromium_executable_path
from ..config.paths import get_data_dir, get_cookies_dir


def _get_session_user_agent() -> str:
    """Get the UA from SessionAuthority (consistent with actual Chrome version)."""
    try:
        from ..shared.session_authority import get_session_authority
        return get_session_authority().user_agent
    except Exception:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        )

try:
    from playwright.sync_api import BrowserContext, sync_playwright
    _PLAYWRIGHT_IMPORT_ERROR = None
except Exception as _e:  # pragma: no cover - runtime dependency
    import sys as _sys
    _PLAYWRIGHT_IMPORT_ERROR = f"Python: {_sys.executable} | Error: {_e}"
    BrowserContext = object  # type: ignore[assignment]
    sync_playwright = None

try:
    from .config import BROWSER_AUTH_CONFIG
except Exception:
    BROWSER_AUTH_CONFIG = {
        "profile_dir_name": "browser_profile",
        "headless_during_grab": True,
        "viewport_width": 1920,
        "viewport_height": 1080,
        "locale": "en-US",
        "scroll_delay_min": 1.5,
        "scroll_delay_max": 3.0,
        "max_scroll_attempts": 100,
        "stagnant_limit": 5,
    }


class ChromiumAuthManager:
    """Manage a persistent Playwright Chromium profile for multi-platform auth."""
    
    _launch_lock = threading.Lock()

    def __init__(self, profile_dir: Optional[Union[str, Path]] = None):
        if profile_dir:
            self.profile_dir = Path(profile_dir)
        else:
            # Persistent EXE-safe location
            self.profile_dir = get_data_dir() / BROWSER_AUTH_CONFIG.get("profile_dir_name", "browser_profile")
            
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self.platforms: Dict[str, str] = {
            "youtube": "https://accounts.google.com/signin",
            "instagram": "https://www.instagram.com/accounts/login/",
            "tiktok": "https://www.tiktok.com/login/phone-or-email/email",
            "twitter": "https://x.com/i/flow/login",
            "facebook": "https://www.facebook.com/login",
        }

        self._cookie_markers: Dict[str, Sequence[Tuple[str, Sequence[str]]]] = {
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

        self._platform_domain_tokens: Dict[str, Sequence[str]] = {
            "youtube": ("youtube.com", "google.com", "youtu.be"),
            "instagram": ("instagram.com",),
            "tiktok": ("tiktok.com",),
            "twitter": ("x.com", "twitter.com"),
            "facebook": ("facebook.com", "fb.com"),
        }

        self._active_contexts: Dict[int, object] = {}

        # Cooldown state: prevent re-opening login for platforms that hit
        # challenges / rate-limits.  Persisted to JSON so it survives restarts.
        self._cooldown_file = get_data_dir() / "login_cooldowns.json"
        self._cooldown_duration = timedelta(hours=1)

    # ── Cooldown tracking ──────────────────────────────────────────────────

    _DEFAULT_COOLDOWN_MINUTES = 60

    def _load_cooldowns(self) -> Dict[str, dict]:
        try:
            if self._cooldown_file.exists():
                return json.loads(
                    self._cooldown_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_cooldowns(self, data: Dict[str, dict]) -> None:
        try:
            self._cooldown_file.parent.mkdir(parents=True, exist_ok=True)
            self._cooldown_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logging.debug("Failed to save cooldown state", exc_info=True)

    def record_cooldown(
        self,
        platform_key: str,
        reason: str,
        minutes: int = _DEFAULT_COOLDOWN_MINUTES,
    ) -> None:
        """Record that a platform hit a challenge/rate-limit.

        Prevents duplicate re-recording while a cooldown is already active.
        """
        active_reason = self.is_in_cooldown(platform_key)
        if active_reason:
            logging.info(
                "[CooldownDecision] %s SKIPPED duplicate record — "
                "already in cooldown (existing reason: %s, new reason: %s)",
                platform_key, active_reason, reason,
            )
            return

        now = datetime.now()
        data = self._load_cooldowns()
        data[platform_key] = {
            "reason": reason,
            "recorded": now.isoformat(),
            "cooldown_until": (now + timedelta(minutes=minutes)).isoformat(),
        }
        self._save_cooldowns(data)
        logging.warning(
            "[Cooldown] %s in cooldown for %d min: %s",
            platform_key, minutes, reason,
        )

    def is_in_cooldown(self, platform_key: str) -> Optional[str]:
        """Return cooldown reason if platform is in cooldown, else None."""
        data = self._load_cooldowns()
        entry = data.get(platform_key)
        if not entry:
            return None
        try:
            until = datetime.fromisoformat(entry["cooldown_until"])
            if datetime.now() < until:
                return entry.get("reason", "unknown")
        except Exception:
            pass
        # Expired — clean up
        data.pop(platform_key, None)
        self._save_cooldowns(data)
        return None

    def clear_cooldown(self, platform_key: str) -> None:
        """Manually clear cooldown for a platform (e.g. after successful login)."""
        data = self._load_cooldowns()
        if platform_key in data:
            data.pop(platform_key)
            self._save_cooldowns(data)
            logging.info("[Cooldown] Cleared cooldown for %s", platform_key)

    def get_all_cooldowns(self) -> Dict[str, str]:
        """Return {platform: reason} for all currently active cooldowns."""
        data = self._load_cooldowns()
        active = {}
        now = datetime.now()
        for platform, entry in data.items():
            try:
                until = datetime.fromisoformat(entry["cooldown_until"])
                if now < until:
                    remaining = int((until - now).total_seconds() / 60)
                    active[platform] = (
                        f"{entry.get('reason', 'unknown')} "
                        f"({remaining}min remaining)"
                    )
            except Exception:
                pass
        return active

    # Lock/junk file names that do NOT indicate a real Chromium profile.
    # Must stay consistent with SessionAuthority._PROFILE_JUNK_NAMES.
    _PROFILE_JUNK_NAMES = frozenset({
        ".session_lock", "SingletonLock", "SingletonSocket", "SingletonCookie",
        ".singleton_test", "lockfile", "parent.lock",
    })

    def _has_real_profile_content(self) -> bool:
        """True if profile_dir contains at least one non-junk file/directory."""
        if not self.profile_dir.exists():
            return False
        try:
            return any(
                item.name not in self._PROFILE_JUNK_NAMES
                for item in self.profile_dir.iterdir()
            )
        except Exception:
            return False

    def is_setup_complete(self) -> bool:
        """Check if the persistent profile exists and has real content (not just lock files)."""
        return self._has_real_profile_content()

    def get_login_status(self) -> Dict[str, bool]:
        """Strict auth layer: checks for export-grade auth cookies.

        Use this when you need to know if cookies can be trusted for
        yt-dlp / instaloader / other downloaders.  Returns True only
        when the profile has strong auth markers (sessionid, c_user, etc.).

        For GUI / Re-login decisions, use get_session_status() instead.
        """
        status = {platform: False for platform in self.platforms}
        if sync_playwright is None or not self._has_real_profile_content():
            return status

        playwright, context = self._start_persistent_context(headless=True)
        if context is None:
            if playwright:
                playwright.stop()
            return status

        try:
            cookies = context.cookies()
            for platform in self.platforms:
                status[platform] = self._has_platform_cookies(cookies, platform)
        except Exception:
            logging.exception("Failed reading Chromium profile cookies")
        finally:
            self._close_started_context(playwright, context)

        return status

    def get_session_status(self) -> Dict[str, bool]:
        """Browser session layer: checks for broader session indicators.

        Use this for GUI status display and Re-login tab decisions.
        Returns True when the managed browser has any evidence of a
        logged-in session (broad indicators like passport_csrf_token,
        ds_user_id, etc.) — NOT strong enough for cookie export trust.

        For downloader / cookie export decisions, use get_login_status().
        """
        status = {platform: False for platform in self.platforms}
        if sync_playwright is None or not self._has_real_profile_content():
            return status

        playwright, context = self._start_persistent_context(headless=True)
        if context is None:
            if playwright:
                playwright.stop()
            return status

        try:
            cookies = context.cookies()
            for platform in self.platforms:
                status[platform] = self.has_platform_session(cookies, platform)
        except Exception:
            logging.exception("Failed reading Chromium profile cookies")
        finally:
            self._close_started_context(playwright, context)

        return status

    # ── Home pages for session-preserving Re-login ──────────────────────
    # When Re-login opens platforms, use HOME pages (not login pages) so
    # existing sessions are preserved and platforms don't see repeated
    # forced login attempts.  The user can navigate to login from here
    # only if they're actually logged out.
    _HOME_URLS: Dict[str, str] = {
        "youtube": "https://www.youtube.com/",
        "instagram": "https://www.instagram.com/",
        "tiktok": "https://www.tiktok.com/",
        "twitter": "https://x.com/home",
        "facebook": "https://www.facebook.com/",
    }

    def open_login_browser(
        self,
        callback: Optional[Callable[[str, str], None]] = None,
        force_refresh: bool = False,
        target_platform: Optional[str] = None,
        open_even_if_logged_in: bool = False,
    ) -> bool:
        """
        Launch the user's REAL system Chrome for interactive login.

        Architecture (v2 — real-Chrome):
          Interactive login now uses the user's actual Chrome browser
          launched as a normal process — NO Playwright, NO CDP, NO
          automation control during the interactive session.  This
          makes the browser indistinguishable from a real user session.

          After the user closes Chrome, Playwright is used headless-only
          for cookie reading and status detection.

        Flow:
          1. Find system Chrome executable
          2. Launch it with --user-data-dir=<our shared profile>
          3. Open home pages (not login pages) for platforms that need login
          4. User logs in manually in a fully trusted browser
          5. User closes Chrome
          6. Playwright headless reads cookies for status + export
        """
        import subprocess
        import os

        self._last_login_status = {}

        # ── Close managed CDP Chrome if running (avoid profile conflict) ──
        try:
            from modules.shared.managed_chrome_session import (
                MANAGED_CDP_ATTACH_FIRST,
                get_managed_chrome_session,
            )
            if MANAGED_CDP_ATTACH_FIRST:
                mgr = get_managed_chrome_session()
                if mgr.is_running():
                    logging.info(
                        "[ReLogin] Closing managed CDP Chrome before launching Re-login browser"
                    )
                    mgr.graceful_close()
                    if callback:
                        callback("system", "Closed automated session to open login browser.")
        except ImportError:
            pass
        except Exception as _cdp_close_err:
            logging.debug("[ReLogin] managed CDP close failed: %s", _cdp_close_err)

        if force_refresh:
            logging.info("Force refresh requested: resetting Chromium profile")
            self.reset_profile()

        # ── Find system Chrome ────────────────────────────────────────────
        chrome_exe = get_chromium_executable_path()
        if not chrome_exe or not Path(chrome_exe).exists():
            if callback:
                callback("system", "Chrome not found. Please install Google Chrome.")
            return False

        # Skip bundled Playwright Chromium — we need the real browser
        if "chromium" in Path(chrome_exe).name.lower() and "bin" in chrome_exe.lower():
            # This is the bundled Chromium, not real Chrome
            # Still usable but less trusted by platforms
            logging.warning("[ReLogin] Using bundled Chromium — real Chrome preferred")

        # ── Check existing sessions via headless Playwright ───────────────
        pre_status: Dict[str, bool] = {p: False for p in self.platforms}
        if sync_playwright is not None and self._has_real_profile_content():
            try:
                pw_pre, ctx_pre = self._start_persistent_context(headless=True)
                if ctx_pre is not None:
                    try:
                        pre_cookies = ctx_pre.cookies()
                        for platform in self.platforms:
                            pre_status[platform] = self.has_platform_session(
                                pre_cookies, platform)
                    except Exception:
                        pass
                    finally:
                        self._close_started_context(pw_pre, ctx_pre)
            except Exception:
                pass

        # Report already-logged-in platforms
        for platform, ok in pre_status.items():
            if ok and callback:
                callback(platform, "ok (session exists)")

        # ── Determine which platforms need login ──────────────────────────
        if target_platform:
            scope = {target_platform.lower()}
        else:
            scope = set(self.platforms.keys())

        need_login = {p for p in scope if not pre_status.get(p)}

        # ── Skip platforms in cooldown (challenge / rate-limit) ────────────
        cooled = {}
        for p in list(need_login):
            reason = self.is_in_cooldown(p)
            if reason:
                cooled[p] = reason
                need_login.discard(p)
                if callback:
                    callback(p, f"COOLDOWN: {reason}")

        if not need_login:
            # Manual Re-login button should still be able to open the managed
            # browser, even when broad session detection says "already logged in"
            # or all missing platforms are in cooldown.
            if open_even_if_logged_in:
                if cooled:
                    need_login = set(cooled.keys())
                    # Clear cooldowns so the manual Re-login isn't blocked
                    for p in need_login:
                        self.clear_cooldown(p)
                        logging.info(
                            "[ReLogin] Manual override: cleared cooldown for %s", p,
                        )
                    if callback:
                        callback(
                            "system",
                            "Manual Re-login override: opening managed browser (cooldowns cleared).",
                        )
                else:
                    fallback_platform = sorted(scope)[0] if scope else "instagram"
                    need_login = {fallback_platform}
                    if callback:
                        callback(
                            "system",
                            f"All sessions look active. Opening managed browser for manual check ({fallback_platform}).",
                        )
            else:
                if callback:
                    callback("system",
                             "All platforms already logged in. "
                             "No browser needed.")
                # Still run post-login sync to refresh cookies/GUI
                self._last_login_status = dict(pre_status)
                self._post_login_sync(pre_status, callback)
                return True

        # ── Build Chrome launch command ───────────────────────────────────
        # Open HOME pages, not login pages.  If the user is already logged
        # in, the home page preserves the session.  If not, the platform
        # will redirect to its own login flow naturally — without our app
        # forcing them into a specific login URL that triggers rate-limits.
        urls_to_open = []
        for platform in need_login:
            home = self._HOME_URLS.get(platform)
            if home:
                urls_to_open.append(home)

        cmd = [
            chrome_exe,
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        cmd.extend(urls_to_open)

        if callback:
            platform_list = ", ".join(sorted(need_login))
            callback("system",
                     f"Opening real Chrome for: {platform_list}. "
                     "Log in to any platforms needed, then CLOSE the browser.")

        # ── Write session lock & launch Chrome ────────────────────────────
        try:
            from ..shared.session_authority import get_session_authority
            get_session_authority().write_session_lock("interactive_relogin")
        except Exception:
            pass

        try:
            logging.info(
                "[ReLogin] Launching real Chrome: %s (profile=%s, urls=%d)",
                Path(chrome_exe).name, self.profile_dir, len(urls_to_open),
            )
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )

            if callback:
                for platform in need_login:
                    callback(platform, "opened (real Chrome)")

            # ── Wait for the user to close Chrome ─────────────────────────
            # Poll the process — when Chrome exits, the user is done.
            while proc.poll() is None:
                time.sleep(1.0)

            logging.info("[ReLogin] Chrome closed (exit code %s)", proc.returncode)
            if callback:
                callback("system", "Browser closed. Detecting login status...")

        except FileNotFoundError:
            if callback:
                callback("system", f"Failed to launch Chrome: {chrome_exe}")
            self._clear_session_lock_safe()
            return False
        except Exception as exc:
            logging.exception("Failed to launch Chrome for Re-login")
            if callback:
                callback("system", f"Chrome launch error: {str(exc)[:120]}")
            self._clear_session_lock_safe()
            return False

        # ── Post-login: Headless status detection & cookie export ─────────
        # Small delay to let Chrome fully release the profile lock
        time.sleep(1.5)

        final_status: Dict[str, bool] = {p: False for p in self.platforms}

        if sync_playwright is not None:
            try:
                pw_post, ctx_post = self._start_persistent_context(headless=True)
                if ctx_post is not None:
                    try:
                        post_cookies = ctx_post.cookies()
                        for platform in self.platforms:
                            final_status[platform] = self.has_platform_session(
                                post_cookies, platform)

                        # ── Probe failed platforms for challenge state ─────
                        # The app cannot observe what happened inside real
                        # Chrome.  But after Chrome closes, if a platform the
                        # user tried to log into is STILL not logged in, we
                        # do a lightweight headless probe to see if the
                        # platform is in a challenge / rate-limit state.
                        # If so, record cooldown so next Re-login skips it.
                        failed = {p for p in need_login
                                  if not final_status.get(p)}
                        if failed:
                            self._probe_challenge_after_relogin(
                                ctx_post, failed, callback)
                    except Exception:
                        logging.exception("Failed to read post-login cookies")
                    finally:
                        self._close_started_context(pw_post, ctx_post)
            except Exception:
                logging.exception("Post-login headless check failed")
        else:
            if callback:
                callback("system",
                         "Playwright not available for status check. "
                         "Cookie export will happen on next backend operation.")

        # ── Clear cooldowns for platforms that are now logged in ─────────
        for platform, ok in final_status.items():
            if ok:
                self.clear_cooldown(platform)

        self._last_login_status = dict(final_status)
        self._post_login_sync(final_status, callback)
        return any(final_status.values())

    def _post_login_sync(
        self,
        final_status: Dict[str, bool],
        callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Shared post-login logic: report status, export cookies, notify SA."""
        if callback:
            for platform, ok in final_status.items():
                callback(platform, "ok" if ok else "missing")

        # Always notify SessionAuthority so auth_state.json reflects
        # the real login status — including full logout (all False).
        try:
            from ..shared.session_authority import get_session_authority
            sa = get_session_authority()
            sa.notify_login_complete(
                "all", source="relogin",
                detected_status=final_status,
            )
        except Exception:
            logging.exception(
                "notify_login_complete failed; falling back to manual sync"
            )
            if any(final_status.values()):
                try:
                    self.extract_cookies_for_all_platforms()
                except Exception:
                    pass

        if not any(final_status.values()):
            self._clear_session_lock_safe()

    def _probe_challenge_after_relogin(
        self,
        context,
        failed_platforms: Set[str],
        callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """After interactive Re-login, probe failed platforms for challenge state.

        The app cannot observe what happens inside the real Chrome window.
        But after Chrome closes, for each platform the user tried to log into
        that is STILL not logged in, we open a headless page on the platform's
        home URL and run _challenge_detected().  If a challenge / rate-limit
        page is found, we record a cooldown.  If the platform just appears
        logged-out (no challenge), we do NOT record a cooldown — the user
        may simply have not completed login for that platform.
        """
        for platform in failed_platforms:
            home_url = self._HOME_URLS.get(platform)
            if not home_url:
                continue
            try:
                page = context.new_page()
                page.goto(
                    home_url,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                time.sleep(2.0)

                _signal = self._challenge_detected(page, platform_key=platform)
                if _signal:
                    reason = f"Challenge after Re-login: {_signal}"
                    if self._should_record_cooldown(platform, _signal, page.url):
                        logging.warning(
                            "[CooldownDecision] %s: recording cooldown post-Re-login — signal=%s",
                            platform, _signal,
                        )
                        self.record_cooldown(platform, reason)
                    else:
                        logging.info(
                            "[CooldownDecision] %s: skipping cooldown post-Re-login "
                            "(weak signal) — signal=%s",
                            platform, _signal,
                        )
                    if callback:
                        callback(
                            platform,
                            f"COOLDOWN recorded: {reason}" if self.is_in_cooldown(platform)
                            else f"Challenge seen but cooldown skipped: {_signal}",
                        )
                else:
                    logging.info(
                        "[ReLogin] %s: no challenge detected (user may not "
                        "have completed login)", platform,
                    )

                page.close()
            except Exception:
                logging.debug(
                    "Challenge probe failed for %s (non-fatal)",
                    platform, exc_info=True,
                )

    def _write_netscape_cookies(self, cookies: list, target_path: Path, platform: str) -> None:
        """Write a list of Playwright cookies to a Netscape cookie file."""
        with target_path.open("w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(f"# Exported from persistent Chromium profile ({platform})\n\n")
            for cookie in cookies:
                domain = str(cookie.get("domain", "")).strip()
                if not domain:
                    continue
                include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
                path = str(cookie.get("path", "/") or "/")
                secure = "TRUE" if bool(cookie.get("secure", False)) else "FALSE"
                expires = int(cookie.get("expires", 0) or 0)
                if expires <= 0:
                    expires = int(time.time()) + (365 * 24 * 60 * 60)
                name = str(cookie.get("name", "")).strip()
                value = str(cookie.get("value", "")).strip()
                if not name:
                    continue
                f.write(
                    f"{domain}\t{include_subdomains}\t{path}\t{secure}\t"
                    f"{expires}\t{name}\t{value}\n"
                )

    def _export_has_auth_cookies(self, cookies: list, platform_key: str) -> bool:
        """Check if a set of Playwright cookies contains auth markers for a platform."""
        return self._has_platform_cookies(cookies, platform_key)

    def _safe_write_canonical(self, cookies: list, platform_key: str, staging_path: Path) -> None:
        """
        Write cookies to the canonical platform file, but only if the new
        cookies contain real auth markers OR the existing file has none.

        This prevents a stale/empty profile export from wiping out
        a known-good cookie file.
        """
        canonical_path = get_cookies_dir() / f"{platform_key}.txt"
        has_auth = self._export_has_auth_cookies(cookies, platform_key)

        if has_auth:
            # New export has auth -> always write
            self._write_netscape_cookies(cookies, canonical_path, platform_key)
            logging.info(
                "[CookieGuard] Wrote %s (export has auth cookies)", canonical_path.name
            )
            return

        # New export has NO auth cookies - check existing file
        if canonical_path.exists() and canonical_path.stat().st_size > 10:
            try:
                from modules.shared.session_authority import _AUTH_COOKIE_MARKERS
                markers = _AUTH_COOKIE_MARKERS.get(platform_key, [])
                content = canonical_path.read_text(encoding="utf-8", errors="ignore")
                for cookie_name, _ in markers:
                    if cookie_name in content:
                        logging.info(
                            "[CookieGuard] BLOCKED overwrite of %s: existing file has "
                            "auth cookie '%s', new export does not",
                            canonical_path.name, cookie_name,
                        )
                        return
            except Exception:
                pass

        # Both have no auth, or existing doesn't exist -> write
        self._write_netscape_cookies(cookies, canonical_path, platform_key)
        logging.info("[CookieGuard] Wrote %s (no auth in either old or new)", canonical_path.name)

    def extract_cookies_for_all_platforms(self) -> Dict[str, str]:
        """Export Netscape cookies for all platforms in a single headless pass."""
        results = {}
        context = None
        try:
            context = self.launch_headless_context()
            all_cookies = context.cookies()

            out_dir = get_cookies_dir() / "browser_cookies"
            out_dir.mkdir(parents=True, exist_ok=True)

            for platform in self.platforms:
                filtered = [
                    c for c in all_cookies
                    if self._cookie_domain_matches_platform(c.get("domain", ""), platform)
                ]
                if not filtered:
                    continue

                # Path 1: browser_cookies subdirectory (always written - staging area)
                out_path = out_dir / f"{platform}_chromium_profile.txt"
                self._write_netscape_cookies(filtered, out_path, platform)

                # Path 2: Canonical platform file (overwrite-protected)
                self._safe_write_canonical(filtered, platform, out_path)

                results[platform] = str(out_path)
                logging.info(
                    "Synced cookies for %s -> %s (auth=%s)",
                    platform, out_path.name,
                    self._export_has_auth_cookies(filtered, platform),
                )

        except Exception:
            logging.exception("Failed bulk cookie extraction")
        finally:
            if context is not None:
                self._close_context(context)
        return results

    def launch_headless_context(self) -> BrowserContext:
        if sync_playwright is None:
            raise RuntimeError("Playwright is not installed")

        playwright, context = self._start_persistent_context(headless=True)
        if context is None:
            if playwright:
                playwright.stop()
            raise RuntimeError("Failed to launch headless Chromium context")

        self._active_contexts[id(context)] = playwright
        self._install_stealth(context)
        return context  # type: ignore[return-value]

    def extract_cookies_for_platform(self, platform_key: str) -> str:
        platform_key = (platform_key or "").lower().strip()
        if platform_key not in self.platforms:
            return ""

        context = None
        try:
            context = self.launch_headless_context()
            cookies = context.cookies()
            filtered = [
                c
                for c in cookies
                if self._cookie_domain_matches_platform(c.get("domain", ""), platform_key)
            ]
            if not filtered:
                logging.info("[CookieExport] No cookies found in profile for %s", platform_key)
                return ""

            out_dir = get_cookies_dir() / "browser_cookies"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{platform_key}_chromium_profile.txt"

            # Always write to staging area (browser_cookies/)
            self._write_netscape_cookies(filtered, out_path, platform_key)

            # Write to canonical path with overwrite protection
            self._safe_write_canonical(filtered, platform_key, out_path)

            return str(out_path)
        except Exception:
            logging.exception("Failed exporting cookies for %s", platform_key)
            return ""
        finally:
            if context is not None:
                self._close_context(context)

    def grab_links_via_browser(
        self,
        url: str,
        platform_key: str,
        content_filter: str,
        max_items: int = 0,
        max_scroll_attempts_override: Optional[int] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[dict]:
        platform_key = (platform_key or "").lower().strip()
        if platform_key not in self.platforms:
            return []

        context = None
        try:
            context = self.launch_headless_context()
            page = context.new_page()

            target_urls = self._build_target_urls(url=url, platform_key=platform_key)
            if progress_callback:
                progress_callback(f"Chromium: scraping {len(target_urls)} page(s)")

            ordered_links: List[str] = []
            seen: Set[str] = set()

            for target in target_urls:
                for href in self._collect_links_on_page(
                    page=page,
                    target_url=target,
                    platform_key=platform_key,
                    max_items=max_items,
                    max_scroll_attempts_override=max_scroll_attempts_override,
                    progress_callback=progress_callback,
                ):
                    if href in seen:
                        continue
                    seen.add(href)
                    ordered_links.append(href)
                    if max_items > 0 and len(ordered_links) >= max_items:
                        break
                if max_items > 0 and len(ordered_links) >= max_items:
                    break

            entries = []
            for index, href in enumerate(ordered_links):
                pseudo_date = f"{99999999 - index:08d}"
                entries.append({"url": href, "title": "", "date": pseudo_date})

            entries.sort(key=lambda x: x.get("date", "00000000"), reverse=True)

            # Piggyback cookie export while the context is already open.
            # This saves a separate headless launch for downstream yt-dlp.
            if entries and context is not None:
                try:
                    all_cookies = context.cookies()
                    plat_cookies = [
                        c for c in all_cookies
                        if self._cookie_domain_matches_platform(
                            c.get("domain", ""), platform_key)
                    ]
                    if plat_cookies:
                        out_dir = get_cookies_dir() / "browser_cookies"
                        out_dir.mkdir(parents=True, exist_ok=True)
                        out_path = out_dir / f"{platform_key}_chromium_profile.txt"
                        self._write_netscape_cookies(plat_cookies, out_path, platform_key)
                        self._safe_write_canonical(plat_cookies, platform_key, out_path)
                        logging.info(
                            "[ChromiumAuth] Piggyback cookie export for %s (%d cookies)",
                            platform_key, len(plat_cookies),
                        )
                except Exception:
                    logging.debug("Piggyback cookie export failed (non-fatal)")

            return entries
        except Exception:
            logging.exception("Chromium browser extraction failed")
            return []
        finally:
            if context is not None:
                self._close_context(context)

    def attempt_silent_relogin(self, platform_key: str) -> bool:
        """Check if the managed profile still has a valid session.

        Uses cookie-based detection only — no page navigation, no form
        interaction.  This avoids false positives from public home pages
        that load without login (TikTok, Facebook, Twitter/X all serve
        their home page to logged-out visitors).

        Consistent with get_login_status(): both use the same cookie
        checks on the same profile, so they cannot disagree.
        """
        platform_key = (platform_key or "").lower().strip()
        if platform_key not in self.platforms:
            return False

        context = None
        try:
            context = self.launch_headless_context()
            cookies = context.cookies()
            has_session = self.has_platform_session(cookies, platform_key)

            if has_session:
                logging.info(
                    "[SilentRelogin] %s session valid (cookies confirmed)",
                    platform_key,
                )
                self.clear_cooldown(platform_key)
                return True

            logging.info(
                "[SilentRelogin] %s no valid session (cookies missing)",
                platform_key,
            )
            return False
        except Exception:
            logging.exception("Silent relogin check failed for %s", platform_key)
            return False
        finally:
            if context is not None:
                self._close_context(context)

    def reset_profile(self):
        try:
            if self.profile_dir.exists():
                shutil.rmtree(self.profile_dir, ignore_errors=True)
            self.profile_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            logging.exception("Failed resetting browser profile folder")

    @staticmethod
    def _clear_session_lock_safe():
        """Clear session lock without raising. Used on launch failure paths."""
        try:
            from ..shared.session_authority import get_session_authority
            get_session_authority().clear_session_lock()
        except Exception:
            pass

    def _start_persistent_context(self, headless: bool, retry_on_crash: bool = True):
        # Prevent concurrent launches on the same profile
        with self._launch_lock:
            return self._locked_start_persistent_context(headless, retry_on_crash)

    def _locked_start_persistent_context(self, headless: bool, retry_on_crash: bool = True):
        if sync_playwright is None:
            return None, None

        # Write session lock so other flows know the profile is busy
        purpose = "headless_export" if headless else "interactive_login"
        try:
            from ..shared.session_authority import get_session_authority
            get_session_authority().write_session_lock(purpose)
        except Exception:
            pass

        playwright = None
        launch_args = None
        try:
            playwright = sync_playwright().start()

            # For headless exports/recovery, prefer Playwright bundled Chromium.
            # System Chrome in headless+persistent mode is less stable on some
            # Windows builds and can throw Browser.getWindowForTarget.
            exe_path = get_chromium_executable_path()

            # Use SessionAuthority UA for consistency with actual Chrome version.
            consistent_ua = _get_session_user_agent()

            launch_args = {
                "user_data_dir": str(self.profile_dir),
                "headless": headless,
                "ignore_default_args": ["--enable-automation"],
                "user_agent": consistent_ua,
                "viewport": {
                    "width": int(BROWSER_AUTH_CONFIG.get("viewport_width", 1920)),
                    "height": int(BROWSER_AUTH_CONFIG.get("viewport_height", 1080)),
                },
                "locale": str(BROWSER_AUTH_CONFIG.get("locale", "en-US")),
                "args": [
                    "--disable-blink-features=AutomationControlled",
                ],
            }

            if exe_path and not headless:
                launch_args["executable_path"] = exe_path
                if "bin" not in exe_path.lower():
                    logging.info("[ChromiumAuthManager] Using System Chrome: %s", exe_path)
                else:
                    logging.info("[ChromiumAuthManager] Using Bundled Chromium: %s", exe_path)
            elif exe_path and headless:
                # System Chrome + headless crashes with Browser.getWindowForTarget
                # on some Windows builds, so use Playwright bundled Chromium.
                # BUT keep the same User-Agent as the headed login session so
                # Instagram doesn't detect a browser switch and force-logout.
                logging.info(
                    "[ChromiumAuthManager] Headless launch: Playwright bundled Chromium "
                    "with consistent UA to preserve session"
                )
            else:
                logging.warning("[ChromiumAuthManager] No browser found, using Playwright default.")

            logging.info(
                "[ChromiumAuthManager] Launching persistent context: profile=%s headless=%s ua=%s",
                self.profile_dir, headless, consistent_ua[:60],
            )
            context = playwright.chromium.launch_persistent_context(**launch_args)
            return playwright, context
        except Exception as e:
            logging.error(f"Chromium launch failed: {e}")
            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    pass

            # Retry ONCE with fallback args (remove executable_path + UA override).
            # This handles system-Chrome headless failures like:
            # "Protocol error (Browser.getWindowForTarget): Browser window not found".
            if retry_on_crash and launch_args:
                logging.warning(
                    "[ChromiumAuthManager] Retrying launch once with fallback browser args..."
                )
                time.sleep(1.0)
                fallback_args = dict(launch_args)
                if "executable_path" in fallback_args:
                    del fallback_args["executable_path"]
                    logging.info(
                        "[ChromiumAuthManager] Fallback: removed executable_path "
                        "(using Playwright bundled Chromium)."
                    )
                # Avoid UA mismatch if fallback browser major version differs.
                fallback_args.pop("user_agent", None)
                try:
                    playwright = sync_playwright().start()
                    context = playwright.chromium.launch_persistent_context(**fallback_args)
                    logging.info("[ChromiumAuthManager] Fallback launch succeeded.")
                    return playwright, context
                except Exception as e2:
                    logging.error(f"Fallback launch failed: {e2}")
                    if playwright:
                        try:
                            playwright.stop()
                        except Exception:
                            pass

                    logging.error(
                        "Chromium launch failed twice. Preserving profile to keep saved sessions. "
                        "User can force-reset via Re-login if needed."
                    )
                    self._clear_session_lock_safe()
                    return None, None

            self._clear_session_lock_safe()
            return None, None

    def _close_started_context(self, playwright, context):
        try:
            if context is not None:
                context.close()
        except Exception:
            pass
        try:
            if playwright is not None:
                playwright.stop()
        except Exception:
            pass
        # Clear session lock so other flows know the profile is free
        try:
            from ..shared.session_authority import get_session_authority
            get_session_authority().clear_session_lock()
        except Exception:
            pass

    def _close_context(self, context):
        playwright = self._active_contexts.pop(id(context), None)
        self._close_started_context(playwright, context)

    def close_all(self):
        """Close all remaining active contexts and stop their Playwright instances.
        Call this when done using the auth manager to release browser profile locks."""
        for ctx_id in list(self._active_contexts.keys()):
            try:
                # We don't have a direct ref to context object by id,
                # but we can stop the playwright instance to force cleanup.
                pw = self._active_contexts.pop(ctx_id, None)
                if pw is not None:
                    try:
                        pw.stop()
                    except Exception:
                        pass
            except Exception:
                pass

    def _install_stealth(self, context):
        """Minimal stealth: only hide the webdriver flag that Playwright sets.

        No other browser properties are overridden.  Faking additional
        values creates detectable inconsistencies with a real Chrome
        profile and triggers verification on social media platforms.
        """
        try:
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
        except Exception:
            pass

    # Broader session indicators — cookies that show the user has interacted
    # with the platform beyond a first-time anonymous visit.  These are NOT
    # strong enough for downloader/export trust, but they ARE strong enough
    # to say "this user has a session in this browser — do not force them
    # to the login page again".
    _session_indicators: Dict[str, Sequence[Tuple[str, Sequence[str]]]] = {
        "youtube": [
            # Google login sets these alongside SID/HSID
            ("SAPISID", ("google.com",)),
            ("APISID", ("google.com",)),
            ("__Secure-1PSID", ("google.com",)),
            ("LOGIN_INFO", ("youtube.com",)),
        ],
        "instagram": [
            ("ds_user_id", ("instagram.com",)),
            ("csrftoken", ("instagram.com",)),
        ],
        "tiktok": [
            ("passport_csrf_token", ("tiktok.com",)),
            ("passport_auth_status", ("tiktok.com",)),
            ("cmpl_token", ("tiktok.com",)),
            ("uid_tt", ("tiktok.com",)),
            ("sid_guard", ("tiktok.com",)),
        ],
        "twitter": [
            ("twid", ("x.com", "twitter.com")),
            ("auth_multi", ("x.com", "twitter.com")),
        ],
        # Facebook: datr/sb/fr are visitor cookies set without login.
        # Require account-level cookies that only appear after real login.
        "facebook": [
            ("c_user", ("facebook.com",)),   # logged-in user ID
            ("xs", ("facebook.com",)),       # session secret
            ("presence", ("facebook.com",)), # online-presence indicator (logged-in)
        ],
    }

    def has_platform_session(self, cookies: List[dict], platform_key: str) -> bool:
        """BROWSER SESSION LAYER: does the managed browser have a session?

        Checks strict auth markers first, then broader session indicators
        (passport_csrf_token, ds_user_id, twid, c_user, etc.).

        Use for: GUI status, Re-login tab decisions, attempt_silent_relogin.
        Do NOT use for: downloader cookie export trust (use _has_platform_cookies).
        """
        # First check strict markers (if those pass, session definitely exists)
        if self._has_platform_cookies(cookies, platform_key):
            return True

        # Then check broader session indicators
        indicators = self._session_indicators.get(platform_key, ())
        for cookie_name, allowed_domains in indicators:
            for cookie in cookies:
                name = str(cookie.get("name", "")).strip()
                domain = str(cookie.get("domain", "")).lower()
                if name == cookie_name and any(
                    token in domain for token in allowed_domains
                ):
                    logging.debug(
                        "[SessionDetect] %s session detected via broader indicator: %s (domain=%s)",
                        platform_key, cookie_name, domain,
                    )
                    return True

        return False

    def _has_platform_cookies(self, cookies: List[dict], platform_key: str) -> bool:
        """STRICT AUTH LAYER: does the profile have export-grade auth cookies?

        Checks for strong auth markers (sessionid, SID, c_user, auth_token, etc.).
        These are trusted enough for Netscape cookie export to yt-dlp / instaloader.

        Use for: cookie export validation, downloader auth decisions.
        For GUI / Re-login decisions, use has_platform_session() instead.
        """
        markers = self._cookie_markers.get(platform_key, ())
        if not markers:
            return False

        for cookie_name, allowed_domains in markers:
            for cookie in cookies:
                name = str(cookie.get("name", "")).strip()
                domain = str(cookie.get("domain", "")).lower()
                if name != cookie_name:
                    continue
                if any(token in domain for token in allowed_domains):
                    if platform_key == "tiktok":
                        logging.debug(
                            "[TikTokAuth] Matched auth marker: %s (domain=%s)",
                            cookie_name, domain,
                        )
                    return True

        if platform_key == "tiktok":
            # Log which TikTok cookies ARE present to aid debugging
            tiktok_cookies = [
                c.get("name") for c in cookies
                if "tiktok" in str(c.get("domain", "")).lower()
            ]
            logging.info(
                "[TikTokAuth] No auth marker matched. TikTok cookies present: %s",
                sorted(set(tiktok_cookies))[:15] if tiktok_cookies else "none",
            )
        return False

    def _cookie_domain_matches_platform(self, domain: str, platform_key: str) -> bool:
        domain_lower = str(domain or "").lower()
        tokens = self._platform_domain_tokens.get(platform_key, ())
        return any(token in domain_lower for token in tokens)

    def _build_target_urls(self, url: str, platform_key: str) -> List[str]:
        raw = (url or "").strip().rstrip("/")
        if not raw:
            return []

        if platform_key == "youtube":
            # Respect the caller's chosen YouTube profile view. The higher-level
            # extractor already decides whether we should hit homepage, /videos,
            # or /shorts. If we need more later, extract_links_intelligent()
            # performs the broader tab fallback explicitly.
            return [raw]

        try:
            from .content_filter import ContentFilter

            return ContentFilter().get_profile_url_for_content(raw, platform_key)
        except Exception:
            if platform_key == "youtube":
                return [f"{raw}/videos", f"{raw}/shorts"]
            if platform_key == "instagram":
                return [f"{raw}/reels/"]
            if platform_key == "twitter":
                return [f"{raw}/media"]
            if platform_key == "facebook":
                return [f"{raw}/videos/", f"{raw}/reels/"]
            return [raw]

    def _collect_links_on_page(
        self,
        page,
        target_url: str,
        platform_key: str,
        max_items: int,
        max_scroll_attempts_override: Optional[int] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[str]:
        selector_map = {
            "youtube": 'a[href*="/watch?v="], a[href*="/shorts/"]',
            "tiktok": 'a[href*="/video/"]',
            "instagram": 'a[href*="/reel/"]',
            "twitter": 'a[href*="/status/"]',
            "facebook": 'a[href*="/reel/"], a[href*="/videos/"], a[href*="/watch/"]',
        }
        selector = selector_map.get(platform_key, "a")

        if max_scroll_attempts_override is None:
            max_scroll_attempts = int(BROWSER_AUTH_CONFIG.get("max_scroll_attempts", 100))
        else:
            max_scroll_attempts = max(1, int(max_scroll_attempts_override))
        stagnant_limit = int(BROWSER_AUTH_CONFIG.get("stagnant_limit", 5))
        sleep_seconds = float(BROWSER_AUTH_CONFIG.get("scroll_delay_min", 1.8))

        page.goto(target_url, wait_until="domcontentloaded", timeout=70000)
        time.sleep(2.0)

        ordered_links: List[str] = []
        seen: Set[str] = set()
        stagnant_rounds = 0

        for scroll_index in range(max_scroll_attempts):
            extracted = self._extract_visible_links(page, selector, platform_key)
            before = len(seen)
            for href in extracted:
                normalized = self._normalize_extracted_url(href, page.url)
                if not normalized:
                    continue
                if normalized in seen:
                    continue
                seen.add(normalized)
                ordered_links.append(normalized)
                if max_items > 0 and len(ordered_links) >= max_items:
                    break

            if max_items > 0 and len(ordered_links) >= max_items:
                break

            # Stop if we get redirected to a login wall
            if self._looks_like_login_page(page.url, platform_key):
                if progress_callback:
                    progress_callback(f"  Hit login redirect on {platform_key}. Stopping scroll. Retained {len(ordered_links)} links.")
                break

            # Stop if a login overlay / captcha appears
            _challenge_signal = self._challenge_detected(page, platform_key=platform_key)
            if _challenge_signal:
                if progress_callback:
                    progress_callback(f"  Hit login overlay/challenge on {platform_key}. Stopping scroll. Retained {len(ordered_links)} links.")
                # Only persist cooldown when challenge is strong enough and
                # we could not extract links. If links are already flowing,
                # this was likely a transient UI element, not a hard block.
                if len(ordered_links) == 0:
                    if self._should_record_cooldown(platform_key, _challenge_signal, page.url):
                        logging.warning(
                            "[CooldownDecision] %s: recording cooldown — "
                            "signal=%s, links_extracted=0",
                            platform_key, _challenge_signal,
                        )
                        self.record_cooldown(
                            platform_key,
                            f"Challenge detected: {_challenge_signal}",
                        )
                    else:
                        logging.info(
                            "[CooldownDecision] %s: challenge signal seen but skipped cooldown "
                            "(weak signal) — signal=%s, links_extracted=0",
                            platform_key, _challenge_signal,
                        )
                else:
                    logging.info(
                        "[CooldownDecision] %s: challenge detected but NOT recording "
                        "cooldown — signal=%s, links_extracted=%d (links flowing)",
                        platform_key, _challenge_signal, len(ordered_links),
                    )
                break

            if len(seen) == before:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
            if stagnant_rounds >= stagnant_limit:
                break

            if progress_callback and scroll_index % 8 == 0:
                progress_callback(f"Chromium: {platform_key} found {len(ordered_links)} links")

            page.evaluate("window.scrollBy(0, document.body.scrollHeight * 0.9)")
            time.sleep(sleep_seconds)

        return ordered_links

    def _extract_visible_links(self, page, selector: str, platform_key: str) -> List[str]:
        if platform_key == "twitter":
            return page.evaluate(
                """
                () => {
                    const links = [];
                    const anchors = document.querySelectorAll('a[href*="/status/"]');
                    for (const a of anchors) {
                        const article = a.closest('article');
                        if (!article) continue;
                        const hasVideo = article.querySelector('video,[data-testid="videoPlayer"]');
                        if (!hasVideo) continue;
                        const href = a.href || a.getAttribute('href');
                        if (href) links.push(href);
                    }
                    return links;
                }
                """
            ) or []

        return page.eval_on_selector_all(
            selector,
            "els => els.map(el => el.href || el.getAttribute('href')).filter(Boolean)",
        ) or []

    def _normalize_extracted_url(self, href: str, base_url: str) -> str:
        raw = str(href or "").strip()
        if not raw:
            return ""
        abs_url = urljoin(base_url, raw)
        parsed = urlparse(abs_url)
        if not parsed.scheme or not parsed.netloc:
            return ""

        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query and "watch?v=" in abs_url:
            # Keep YouTube video ids.
            normalized = f"{normalized}?{parsed.query}"
        return normalized.rstrip("/")

    def _looks_like_login_page(self, current_url: str, platform_key: str) -> bool:
        u = (current_url or "").lower()
        hints = {
            "youtube": ("accounts.google.com", "/signin"),
            "instagram": ("instagram.com/accounts/login",),
            "tiktok": ("tiktok.com/login",),
            "twitter": ("x.com/i/flow/login", "twitter.com/i/flow/login"),
            "facebook": ("facebook.com/login",),
        }
        return any(token in u for token in hints.get(platform_key, ()))

    def _challenge_detected(self, page, platform_key: Optional[str] = None) -> str:
        """Check for interactive challenges that block automated browsing.

        Returns a descriptive string if challenge detected (truthy), or
        empty string if no challenge (falsy).  Callers can use the return
        value directly in if-statements and also log the exact signal.

        Instagram detection is intentionally conservative:
          - URL: only /challenge/ path
          - Selector: form[action*='/challenge/'], input[name='security_code']
          - Text: only 'suspicious login attempt' (no generic 'challenge' token)
        """
        try:
            url = (page.url or "").lower()
        except Exception:
            return "page_url_unreadable"

        pk = (platform_key or "").lower().strip()

        # URL-based: platform-specific challenge/checkpoint pages.
        challenge_url_map = {
            "instagram": (
                "/challenge/",
                "/accounts/suspended",
            ),
            "facebook": (
                "checkpoint",
                "/arkose",
                "/captcha",
                "/security/",
                "/two_step",
            ),
            "tiktok": (
                "tiktok.com/login",
                "/captcha",
                "/verify",
                "/challenge",
            ),
            "twitter": (
                "/account/access",
                "/i/flow/login",
                "/challenge",
                "/captcha",
            ),
        }
        challenge_url_tokens = challenge_url_map.get(pk) or (
            "checkpoint",
            "/captcha",
            "/arkose",
        )
        for token in challenge_url_tokens:
            if token in url:
                signal = f"url:{token} in {url[:120]}"
                logging.info("[ChallengeDetect] %s: %s", pk, signal)
                return signal

        # Visible UI element check (more reliable than searching full HTML)
        try:
            selector_map = {
                "instagram": [
                    "form[action*='/challenge/']",
                    "input[name='security_code']",
                ],
                "facebook": [
                    "iframe[src*='arkose']",
                    "iframe[src*='captcha']",
                    "[data-testid='two_step_verification']",
                    "input[name='approvals_code']",
                ],
                "tiktok": [
                    "iframe[src*='captcha']",
                    "iframe[src*='recaptcha']",
                    "div[class*='captcha']",
                ],
                "twitter": [
                    "iframe[src*='captcha']",
                    "iframe[src*='recaptcha']",
                    "input[name='text'][autocomplete='one-time-code']",
                ],
            }
            selectors = selector_map.get(pk) or [
                "iframe[src*='captcha']",
                "iframe[src*='recaptcha']",
                "iframe[src*='arkose']",
            ]
            for sel in selectors:
                if page.locator(sel).count() > 0:
                    signal = f"selector:{sel}"
                    logging.info("[ChallengeDetect] %s: %s", pk, signal)
                    return signal
        except Exception:
            pass

        # Text-based: use platform-specific phrases to avoid false positives.
        # Instagram is INTENTIONALLY limited to 'suspicious login attempt' only.
        # 'challenge_required' and '/challenge/' are NOT checked in body text
        # for Instagram because embedded JSON/scripts can contain these tokens
        # even on valid pages without an actual user-facing challenge.
        try:
            body_text = page.inner_text("body", timeout=3000).lower()
            phrase_map = {
                "tiktok": (
                    "maximum number of attempts",
                    "too many attempts",
                    "try again later",
                    "temporarily blocked",
                ),
                "facebook": (
                    "arkose",
                    "matchkey",
                    "security check",
                    "checkpoint",
                ),
                "instagram": (
                    "suspicious login attempt",
                ),
                "twitter": (
                    "verify your identity",
                    "unusual login attempt",
                    "confirm your phone number",
                ),
            }
            # Fallback set when platform is unknown
            phrases = phrase_map.get(pk) or (
                "maximum number of attempts",
                "temporarily blocked",
                "security check",
            )
            for phrase in phrases:
                if phrase in body_text:
                    signal = f"text:'{phrase}'"
                    logging.info("[ChallengeDetect] %s: %s", pk, signal)
                    return signal
        except Exception:
            pass

        logging.debug("[ChallengeDetect] %s: no challenge signal on %s", pk, url[:80])
        return ""

    def _should_record_cooldown(
        self,
        platform_key: str,
        challenge_signal: str,
        current_url: str = "",
    ) -> bool:
        """Decide whether challenge signal is strong enough to persist cooldown.

        Instagram is stricter to avoid false positives from weak text-only hints.
        """
        pk = (platform_key or "").lower().strip()
        sig = (challenge_signal or "").lower()
        url = (current_url or "").lower()

        if pk == "instagram":
            strong_instagram_signals = (
                "url:/challenge/",
                "url:/accounts/suspended",
                "selector:form[action*='/challenge/']",
                "selector:input[name='security_code']",
            )
            if any(token in sig for token in strong_instagram_signals):
                return True
            # URL guard in case signal text is transformed upstream.
            return "/challenge/" in url

        return bool(sig)
