"""
modules/creator_profiles/instaloader_grabber.py

Instagram profile link grabber using the `instaloader` library.

Why this exists:
    yt-dlp's `instagram:user` extractor has been officially marked as broken
    and cannot reliably fetch video lists from Instagram profiles.
    `instaloader` is the purpose-built Python library for this task and
    remains the most stable option for authenticated Instagram scraping.

Session setup (one-time, by user):
    Run from the app's virtual environment terminal:
        python -m instaloader --login=your_instagram_username
    This creates a session file. The app reads that file on every run
    — no re-login needed until the session expires.

Session file location (checked in order):
    1. {app}/cookies/instagram_instaloader_session   ← preferred
    2. Instaloader default (~/.config/instaloader/session-{username})
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional


# ── helpers ──────────────────────────────────────────────────────────────────

def _progress(msg: str, cb: Optional[Callable]) -> None:
    if cb:
        cb(msg)


def _cookies_dir() -> Optional[Path]:
    try:
        from modules.config.paths import get_cookies_dir
        return get_cookies_dir()
    except Exception:
        return None


def _find_session_file() -> Optional[Path]:
    """
    Locate an existing instaloader session file.
    Returns the Path if found, None otherwise.
    """
    # 1. App-specific path
    cd = _cookies_dir()
    if cd:
        p = cd / "instagram_instaloader_session"
        if p.exists() and p.stat().st_size > 0:
            return p

    # 2. Instaloader default locations
    home = Path.home()
    for candidate in [
        home / ".config" / "instaloader" / "session-*",
        home / "instaloader-session*",
    ]:
        matches = list(home.glob(str(candidate.relative_to(home))))
        if matches:
            return matches[0]

    return None


def _extract_username(profile_url: str) -> Optional[str]:
    """Extract @username from an Instagram profile URL."""
    url = (profile_url or "").strip().rstrip("/")
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)/?$", url)
    return m.group(1) if m else None


# ── public API ────────────────────────────────────────────────────────────────

def grab_instagram_links_instaloader(
    profile_url: str,
    max_videos: int = 20,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> List[Dict]:
    """
    Fetch video post URLs from an Instagram profile using instaloader.

    Returns a list of entry dicts compatible with download_engine's pipeline:
        {"url": "https://www.instagram.com/p/{shortcode}/",
         "id": shortcode, "platform": "instagram", "creator": username, "title": "..."}

    Returns [] on any error so the calling code can fall through gracefully.
    """
    try:
        import instaloader
    except ImportError:
        _progress("[Instaloader] Not installed — skipping", progress_cb)
        return []

    session_file = _find_session_file()
    if not session_file:
        _progress(
            "[Instaloader] No session file found. "
            "Run: python -m instaloader --login=your_instagram_username "
            "then copy the session file to cookies/instagram_instaloader_session",
            progress_cb,
        )
        return []

    username = _extract_username(profile_url)
    if not username:
        _progress(f"[Instaloader] Cannot parse username from URL: {profile_url}", progress_cb)
        return []

    _progress(f"[Instaloader] Loading session from {session_file.name}...", progress_cb)

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
        quiet=True,
        sleep=True,           # instaloader's built-in rate limiting
        max_connection_attempts=2,
    )

    # Load existing session — never re-login to avoid triggering Multi-Session alerts
    try:
        L.load_session_from_file(username=None, filename=str(session_file))
        _progress("[Instaloader] Session loaded.", progress_cb)
    except Exception as exc:
        _progress(f"[Instaloader] Failed to load session: {exc}", progress_cb)
        return []

    try:
        _progress(f"[Instaloader] Fetching profile: @{username}...", progress_cb)
        profile = instaloader.Profile.from_username(L.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        _progress(f"[Instaloader] Profile @{username} does not exist or is private.", progress_cb)
        return []
    except Exception as exc:
        _progress(f"[Instaloader] Profile fetch error: {exc}", progress_cb)
        return []

    _progress(
        f"[Instaloader] @{username} — {profile.mediacount} total posts. Scanning for videos...",
        progress_cb,
    )

    entries: List[Dict] = []
    scanned = 0
    # Scan up to 3× target to find enough video posts (profile may have many images)
    scan_limit = max(max_videos * 3, 60)

    try:
        for post in profile.get_posts():
            scanned += 1
            if scanned > scan_limit:
                break

            if not post.is_video:
                continue

            shortcode = post.shortcode
            url = f"https://www.instagram.com/reel/{shortcode}/"
            caption = (post.caption or "")[:100].strip().replace("\n", " ")

            entries.append({
                "url": url,
                "id": shortcode,
                "platform": "instagram",
                "creator": username,
                "title": caption or shortcode,
                "thumbnail": "",
            })

            _progress(
                f"[Instaloader] Found video {len(entries)}/{max_videos}: {caption[:50] or shortcode}",
                progress_cb,
            )

            if len(entries) >= max_videos + 5:   # buffer for deduplication
                break

            # Small courtesy delay between post metadata fetches
            time.sleep(0.5)

    except Exception as exc:
        _progress(f"[Instaloader] Error while iterating posts: {exc}", progress_cb)

    _progress(
        f"[Instaloader] Extracted {len(entries)} video post(s) from @{username} "
        f"(scanned {scanned} total posts)",
        progress_cb,
    )
    return entries


def is_session_available() -> bool:
    """Quick check — is an instaloader session file present?"""
    return _find_session_file() is not None


def get_session_setup_instructions() -> str:
    cd = _cookies_dir()
    dest = str(cd / "instagram_instaloader_session") if cd else "cookies/instagram_instaloader_session"
    return (
        "Instagram instaloader session setup:\n"
        "  1. Open terminal in the app folder\n"
        "  2. Run: python -m instaloader --login=your_instagram_username\n"
        "  3. Copy the created session file to:\n"
        f"     {dest}\n"
        "  4. No re-login needed — session persists."
    )
