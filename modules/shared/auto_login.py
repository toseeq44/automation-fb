"""
Workflow 2 - Automated Login
==============================
Uses Playwright with stealth techniques to log in to a platform when
no cookies are available or when they have expired.

Flow:
  1. Load stored credentials (CredentialStore)
  2. Launch Playwright Chromium with anti-detection flags
  3. Navigate to platform login page
  4. Type credentials with human-like random delays
  5. Handle 2FA: TOTP auto-generate OR SMS/email prompt to user
  6. Wait for successful login (check for known post-login elements)
  7. Export cookies → Netscape format → save to chrome_cookies.txt
  8. Return cookie file path for immediate use

Debug callback at every step for GUI visibility.
"""

from __future__ import annotations

import logging
import os
import random
import tempfile
import time
from pathlib import Path
from typing import Callable, List, Optional

from .credential_store import CredentialStore

DebugCb = Optional[Callable[[str], None]]


def _dbg(cb: DebugCb, msg: str) -> None:
    logging.debug(msg)
    if cb:
        cb(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Platform login configs
# ─────────────────────────────────────────────────────────────────────────────

_PLATFORM_LOGIN: dict = {
    "instagram": {
        "url":            "https://www.instagram.com/accounts/login/",
        "user_selector":  'input[name="username"]',
        "pass_selector":  'input[name="password"]',
        "submit_selector":'button[type="submit"]',
        "success_check":  'a[href="/"]',          # Home icon appears after login
        "domain":         ".instagram.com",
    },
    "facebook": {
        "url":            "https://www.facebook.com/login/",
        "user_selector":  '#email',
        "pass_selector":  '#pass',
        "submit_selector":'button[name="login"]',
        "success_check":  '[aria-label="Facebook"]',
        "domain":         ".facebook.com",
    },
    "tiktok": {
        "url":            "https://www.tiktok.com/login/phone-or-email/email",
        "user_selector":  'input[name="username"]',
        "pass_selector":  'input[type="password"]',
        "submit_selector":'button[data-e2e="login-button"]',
        "success_check":  '[data-e2e="profile-icon"]',
        "domain":         ".tiktok.com",
    },
    "youtube": {
        "url":            "https://accounts.google.com/signin",
        "user_selector":  'input[type="email"]',
        "pass_selector":  'input[type="password"]',
        "submit_selector":'#identifierNext',
        "success_check":  'a[href*="youtube.com"]',
        "domain":         ".google.com",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Human-like typing
# ─────────────────────────────────────────────────────────────────────────────

def _human_type(page, selector: str, text: str, cb: DebugCb = None) -> None:
    """Type text character by character with random delays."""
    el = page.locator(selector).first
    el.click()
    time.sleep(random.uniform(0.3, 0.7))
    for char in text:
        el.type(char)
        time.sleep(random.uniform(0.05, 0.18))
    _dbg(cb, f"[WF2]   Typed into {selector[:30]}...")


# ─────────────────────────────────────────────────────────────────────────────
# Cookie export → Netscape format
# ─────────────────────────────────────────────────────────────────────────────

def _playwright_cookies_to_netscape(
    pw_cookies: List[dict],
    platform_key: str,
    save_to: Optional[Path] = None,
    cb: DebugCb = None,
) -> Optional[str]:
    """Convert Playwright cookies to Netscape format file."""
    domain_filter = {
        "instagram": "instagram.com",
        "facebook":  "facebook.com",
        "tiktok":    "tiktok.com",
        "youtube":   "google.com",
        "twitter":   "twitter.com",
    }.get(platform_key, "")

    filtered = [
        c for c in pw_cookies
        if not domain_filter or domain_filter in (c.get("domain") or "")
    ]

    if not filtered:
        _dbg(cb, f"[WF2] No {platform_key} cookies in browser session")
        return None

    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(f"# Source: Workflow 2 auto-login ({platform_key})\n\n")
            for c in filtered:
                domain  = c.get("domain", "")
                flag    = "TRUE"  if domain.startswith(".") else "FALSE"
                path    = c.get("path", "/")
                secure  = "TRUE"  if c.get("secure") else "FALSE"
                expires = str(int(c.get("expires", 0) or 0))
                name    = c.get("name", "")
                value   = c.get("value", "")
                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")

        _dbg(cb, f"[WF2]   {len(filtered)} cookies written")

        if save_to:
            import shutil
            save_to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp, str(save_to))
            _dbg(cb, f"[WF2]   Saved → {save_to.name}")

        return tmp
    except Exception as e:
        _dbg(cb, f"[WF2]   Cookie write error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 2FA handling
# ─────────────────────────────────────────────────────────────────────────────

def _handle_2fa(
    page,
    platform_key: str,
    credential_store: CredentialStore,
    totp_callback: Optional[Callable[[], str]] = None,
    cb: DebugCb = None,
) -> bool:
    """
    Detect and handle 2FA:
    - TOTP auto-generate from stored secret
    - SMS/email: call totp_callback() to prompt user for code
    Returns True if handled successfully.
    """
    time.sleep(2)

    # Check for TOTP/2FA input field
    two_fa_selectors = [
        'input[name="verificationCode"]',
        'input[autocomplete="one-time-code"]',
        'input[name="code"]',
        '#approvals_code',
    ]

    for sel in two_fa_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                _dbg(cb, f"[WF2] 2FA input detected ({sel})")

                # Try TOTP auto-generate
                code = credential_store.get_totp_code(platform_key)
                if not code and totp_callback:
                    _dbg(cb, "[WF2] Requesting 2FA code from user...")
                    code = totp_callback()

                if code:
                    _human_type(page, sel, code, cb)
                    # Submit
                    for submit_sel in ['button[type="submit"]', '#checkpointSubmitButton']:
                        try:
                            page.locator(submit_sel).first.click()
                            break
                        except Exception:
                            pass
                    time.sleep(3)
                    _dbg(cb, "[WF2] 2FA code submitted")
                    return True
                else:
                    _dbg(cb, "[WF2] No 2FA code available – login may fail")
                    return False
        except Exception:
            continue

    return True  # No 2FA needed


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def auto_login_and_get_cookies(
    platform_key: str,
    save_to: Optional[Path] = None,
    totp_callback: Optional[Callable[[], str]] = None,
    cb: DebugCb = None,
) -> Optional[str]:
    """
    Workflow 2 main entry point.

    1. Load credentials from CredentialStore
    2. Launch Playwright stealth browser
    3. Login with human-like typing
    4. Handle 2FA (TOTP auto or manual callback)
    5. Export cookies → save to save_to → return path

    Returns path to Netscape cookie file, or None on failure.
    """
    _dbg(cb, "=" * 48)
    _dbg(cb, f"[WF2] Auto-login for: {platform_key}")
    _dbg(cb, "=" * 48)

    config = _PLATFORM_LOGIN.get(platform_key.lower())
    if not config:
        _dbg(cb, f"[WF2] Platform not supported for auto-login: {platform_key}")
        return None

    # ── Load credentials ─────────────────────────────────────────────────────
    store = CredentialStore()
    creds = store.load(platform_key)
    if not creds:
        _dbg(cb, f"[WF2] No credentials stored for {platform_key}")
        _dbg(cb, "[WF2] Save credentials via Settings → Saved Logins first")
        return None

    username = creds.get("username", "")
    password = creds.get("password", "")
    if not username or not password:
        _dbg(cb, "[WF2] Credentials incomplete (username or password missing)")
        return None

    _dbg(cb, f"[WF2] Credentials loaded for: {username}")

    # ── Playwright launch ────────────────────────────────────────────────────
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _dbg(cb, "[WF2] Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None

    try:
        with sync_playwright() as pw:
            _dbg(cb, "[WF2] Launching stealth Chromium browser...")

            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-web-security",
                f"--window-size={random.choice([1366, 1440, 1920])},{random.choice([768, 900, 1080])}",
            ]

            # Use bundled Chromium from bin/ if available
            from pathlib import Path as _Path
            bin_dir = _Path(__file__).parent.parent.parent / "bin"
            chromium_candidates = [
                bin_dir / "chromium" / "chromium.exe",
                bin_dir / "chromium.exe",
            ]
            exe_path = next((str(p) for p in chromium_candidates if p.exists()), None)

            browser = pw.chromium.launch(
                headless=False,        # Visible – less suspicious for login
                args=launch_args,
                executable_path=exe_path,
                slow_mo=random.randint(30, 80),
            )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    f"Chrome/{random.randint(120, 130)}.0.0.0 Safari/537.36"
                ),
                viewport={"width": random.choice([1366, 1440]), "height": random.choice([768, 900])},
                locale="en-US",
            )

            # Mask navigator.webdriver
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3, 4, 5] });
                window.chrome = { runtime: {} };
            """)

            page = context.new_page()
            _dbg(cb, f"[WF2] Navigating to login page: {config['url']}")
            page.goto(config["url"], timeout=30000, wait_until="domcontentloaded")
            time.sleep(random.uniform(1.5, 3.0))

            # ── Type username ───────────────────────────────────────────────
            _dbg(cb, "[WF2] Entering username...")
            try:
                _human_type(page, config["user_selector"], username, cb)
            except Exception as e:
                _dbg(cb, f"[WF2] Username field error: {e}")
                browser.close()
                return None

            time.sleep(random.uniform(0.5, 1.2))

            # ── Type password ───────────────────────────────────────────────
            _dbg(cb, "[WF2] Entering password...")
            try:
                _human_type(page, config["pass_selector"], password, cb)
            except Exception as e:
                _dbg(cb, f"[WF2] Password field error: {e}")
                browser.close()
                return None

            time.sleep(random.uniform(0.8, 1.5))

            # ── Submit ──────────────────────────────────────────────────────
            _dbg(cb, "[WF2] Submitting login form...")
            try:
                page.locator(config["submit_selector"]).first.click()
            except Exception as e:
                _dbg(cb, f"[WF2] Submit click error: {e}")
                browser.close()
                return None

            time.sleep(random.uniform(3.0, 5.0))

            # ── 2FA ─────────────────────────────────────────────────────────
            _handle_2fa(page, platform_key, store, totp_callback, cb)

            # ── Verify login ─────────────────────────────────────────────────
            _dbg(cb, "[WF2] Verifying login success...")
            current_url = page.url
            _dbg(cb, f"[WF2] Current URL: {current_url}")

            login_keywords = ["login", "signin", "accounts/login"]
            if any(kw in current_url.lower() for kw in login_keywords):
                _dbg(cb, "[WF2] Still on login page – login may have failed (wrong credentials / CAPTCHA)")
                browser.close()
                return None

            _dbg(cb, "[WF2] Login appears successful!")
            time.sleep(2)

            # ── Extract cookies ──────────────────────────────────────────────
            _dbg(cb, "[WF2] Extracting cookies from browser session...")
            pw_cookies = context.cookies()
            _dbg(cb, f"[WF2] Total cookies in session: {len(pw_cookies)}")

            browser.close()

            result = _playwright_cookies_to_netscape(pw_cookies, platform_key, save_to, cb)
            if result:
                _dbg(cb, f"[WF2] ✓ Cookie file ready: {Path(result).name}")
            else:
                _dbg(cb, "[WF2] ✗ No cookies extracted")
            return result

    except Exception as e:
        _dbg(cb, f"[WF2] Auto-login error: {e}")
        return None
