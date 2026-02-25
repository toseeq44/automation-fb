"""
Persistent Chromium auth/session manager for Link Grabber.
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple, Union
from urllib.parse import urljoin, urlparse

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

    def __init__(self, profile_dir: Optional[Union[str, Path]] = None):
        app_root = Path(__file__).resolve().parents[2]
        default_profile = app_root / "data_files" / BROWSER_AUTH_CONFIG.get(
            "profile_dir_name", "browser_profile"
        )
        self.profile_dir = Path(profile_dir) if profile_dir else default_profile
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self.platforms: Dict[str, str] = {
            "youtube": "https://accounts.google.com/signin",
            "instagram": "https://www.instagram.com/accounts/login/",
            "tiktok": "https://www.tiktok.com/login",
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
                ("msToken", ("tiktok.com",)),
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

    def is_setup_complete(self) -> bool:
        if not self.profile_dir.exists():
            return False
        if not any(self.profile_dir.iterdir()):
            return False
        status = self.get_login_status()
        logged_in_count = sum(1 for v in status.values() if v)
        return logged_in_count >= 3

    def get_login_status(self) -> Dict[str, bool]:
        status = {platform: False for platform in self.platforms}
        if sync_playwright is None or not any(self.profile_dir.iterdir()):
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

    def open_login_browser(
        self, callback: Optional[Callable[[str, str], None]] = None
    ) -> bool:
        if sync_playwright is None:
            if callback:
                detail = _PLAYWRIGHT_IMPORT_ERROR or "unknown reason"
                callback("system", f"Playwright not installed | {detail}")
            return False

        playwright, context = self._start_persistent_context(headless=False)
        if context is None:
            if callback:
                callback("system", "Failed to launch Chromium")
            if playwright:
                playwright.stop()
            return False

        try:
            self._install_stealth(context)
            tabs = []
            if context.pages:
                tabs.append(context.pages[0])
            while len(tabs) < len(self.platforms):
                tabs.append(context.new_page())

            for (platform, login_url), page in zip(self.platforms.items(), tabs):
                try:
                    page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
                    if callback:
                        callback(platform, "opened")
                except Exception as exc:
                    if callback:
                        callback(platform, f"failed: {str(exc)[:120]}")

            if callback:
                callback("system", "Log in, then close all browser tabs")

            while True:
                try:
                    open_pages = [p for p in context.pages if not p.is_closed()]
                    if not open_pages:
                        break
                except Exception:
                    break
                time.sleep(1.0)
        except Exception:
            logging.exception("Interactive login browser flow failed")
        finally:
            try:
                self._close_started_context(playwright, context)
            except Exception:
                pass  # EPIPE / broken pipe when browser already closed - harmless

        final_status = self.get_login_status()
        if callback:
            for platform, ok in final_status.items():
                callback(platform, "ok" if ok else "missing")
        return any(final_status.values())

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
                return ""

            out_dir = self.profile_dir.parent / "browser_cookies"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{platform_key}_chromium_profile.txt"

            with out_path.open("w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Exported from persistent Chromium profile\n\n")
                for cookie in filtered:
                    domain = str(cookie.get("domain", "")).strip()
                    if not domain:
                        continue
                    include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
                    path = str(cookie.get("path", "/") or "/")
                    secure = "TRUE" if bool(cookie.get("secure", False)) else "FALSE"
                    expires = int(cookie.get("expires", 0) or 0)
                    name = str(cookie.get("name", "")).strip()
                    value = str(cookie.get("value", "")).strip()
                    if not name:
                        continue
                    f.write(
                        f"{domain}\t{include_subdomains}\t{path}\t{secure}\t"
                        f"{expires}\t{name}\t{value}\n"
                    )

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
            return entries
        except Exception:
            logging.exception("Chromium browser extraction failed")
            return []
        finally:
            if context is not None:
                self._close_context(context)

    def attempt_silent_relogin(self, platform_key: str) -> bool:
        platform_key = (platform_key or "").lower().strip()
        login_url = self.platforms.get(platform_key)
        if not login_url:
            return False

        context = None
        try:
            context = self.launch_headless_context()
            page = context.new_page()
            page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2.0)

            current_url = page.url.lower()
            if not self._looks_like_login_page(current_url, platform_key):
                return True
            if self._challenge_detected(page):
                return False

            submitted = page.evaluate(
                """
                () => {
                    const submitBtn = document.querySelector(
                        'button[type="submit"], input[type="submit"], [role="button"][data-testid*="login"]'
                    );
                    if (submitBtn) {
                        submitBtn.click();
                        return true;
                    }
                    const form = document.querySelector('form');
                    if (form) {
                        form.submit();
                        return true;
                    }
                    return false;
                }
                """
            )
            if not submitted:
                return False

            time.sleep(4.0)
            if self._challenge_detected(page):
                return False
            return not self._looks_like_login_page(page.url.lower(), platform_key)
        except Exception:
            logging.exception("Silent relogin failed for %s", platform_key)
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

    def _start_persistent_context(self, headless: bool):
        if sync_playwright is None:
            return None, None

        try:
            playwright = sync_playwright().start()
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=headless,
                viewport={
                    "width": int(BROWSER_AUTH_CONFIG.get("viewport_width", 1920)),
                    "height": int(BROWSER_AUTH_CONFIG.get("viewport_height", 1080)),
                },
                locale=str(BROWSER_AUTH_CONFIG.get("locale", "en-US")),
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            return playwright, context
        except Exception:
            logging.exception("Failed launching persistent Chromium context")
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

    def _close_context(self, context):
        playwright = self._active_contexts.pop(id(context), None)
        self._close_started_context(playwright, context)

    def _install_stealth(self, context):
        try:
            context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                """
            )
        except Exception:
            pass

    def _has_platform_cookies(self, cookies: List[dict], platform_key: str) -> bool:
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
                    return True
        return False

    def _cookie_domain_matches_platform(self, domain: str, platform_key: str) -> bool:
        domain_lower = str(domain or "").lower()
        tokens = self._platform_domain_tokens.get(platform_key, ())
        return any(token in domain_lower for token in tokens)

    def _build_target_urls(self, url: str, platform_key: str) -> List[str]:
        raw = (url or "").strip().rstrip("/")
        if not raw:
            return []

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

        max_scroll_attempts = int(BROWSER_AUTH_CONFIG.get("max_scroll_attempts", 100))
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

    def _challenge_detected(self, page) -> bool:
        try:
            html = (page.content() or "").lower()
        except Exception:
            return True
        challenge_tokens = (
            "captcha",
            "two-factor",
            "2fa",
            "verification code",
            "security check",
        )
        return any(token in html for token in challenge_tokens)
