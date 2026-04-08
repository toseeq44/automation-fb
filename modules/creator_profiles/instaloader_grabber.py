"""
Instagram profile link grabber using the `instaloader` library.

This module prefers a cached Instaloader session file when available, but it
can also bootstrap that session from a validated Instagram Netscape cookie
file. That lets Creator Profiles reuse the same manual / managed / IX cookie
sources that the rest of the auth pipeline already resolves.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional


def _progress(msg: str, cb: Optional[Callable]) -> None:
    if cb:
        cb(msg)


def _cookies_dir() -> Optional[Path]:
    try:
        from modules.config.paths import get_cookies_dir

        return get_cookies_dir()
    except Exception:
        return None


def _preferred_session_file() -> Optional[Path]:
    cd = _cookies_dir()
    if not cd:
        return None
    return cd / "instagram_instaloader_session"


def _find_session_file() -> Optional[Path]:
    """Locate an existing Instaloader session file."""
    cd = _cookies_dir()
    if cd:
        for candidate in (
            cd / "instagram_instaloader_session",
            cd / "instaloader" / "instagram_instaloader_session",
        ):
            if candidate.exists() and candidate.stat().st_size > 0:
                return candidate

    home = Path.home()
    for candidate in (
        home / ".config" / "instaloader" / "session-*",
        home / "instaloader-session*",
    ):
        matches = list(home.glob(str(candidate.relative_to(home))))
        if matches:
            return matches[0]

    return None


def _extract_username(profile_url: str) -> Optional[str]:
    """Extract @username from an Instagram profile URL."""
    url = (profile_url or "").strip().rstrip("/")
    match = re.search(r"instagram\.com/([A-Za-z0-9._]+)/?$", url)
    return match.group(1) if match else None


def _iter_cookie_candidates(
    primary_cookie: Optional[str] = None,
    cookie_candidates: Optional[Iterable[str]] = None,
) -> List[Path]:
    ordered: List[Path] = []
    seen = set()

    default_candidates: List[Path] = []
    cd = _cookies_dir()
    if cd:
        default_candidates = [
            cd / "manual" / "instagram.txt",
            cd / "instagram.txt",
            cd / "browser_cookies" / "instagram_chromium_profile.txt",
            cd / "browser_cookies" / "instagram_ixbrowser_profile.txt",
            cd / "chrome_cookies.txt",
        ]

    for raw in [primary_cookie, *(cookie_candidates or []), *default_candidates]:
        try:
            if not raw:
                continue
            candidate = Path(str(raw).strip())
            key = str(candidate.resolve()).lower() if candidate.exists() else str(candidate).lower()
            if key in seen or not candidate.exists() or candidate.stat().st_size < 10:
                continue
            seen.add(key)
            ordered.append(candidate)
        except Exception:
            continue
    return ordered


def _load_instagram_cookies(cookie_file: Path) -> List[Dict]:
    cookies: List[Dict] = []
    try:
        with cookie_file.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                domain = str(parts[0] or "").strip()
                if "instagram.com" not in domain.lower():
                    continue
                expires_raw = str(parts[4] or "0").strip()
                try:
                    expires = int(expires_raw)
                except Exception:
                    expires = None
                cookies.append(
                    {
                        "domain": domain,
                        "path": str(parts[2] or "/").strip() or "/",
                        "secure": str(parts[3] or "").strip().upper() == "TRUE",
                        "expires": expires if expires and expires > 0 else None,
                        "name": str(parts[5] or "").strip(),
                        "value": str(parts[6] or "").strip(),
                    }
                )
    except Exception:
        return []
    return [cookie for cookie in cookies if cookie.get("name")]


def _cookie_debug_path(cookie_file: Path) -> str:
    try:
        return str(cookie_file.resolve())
    except Exception:
        return str(cookie_file)


def _inspect_cookie_candidate(cookie_file: Path) -> Dict[str, object]:
    info: Dict[str, object] = {
        "path": cookie_file,
        "usable": False,
        "reason": "",
        "ig_cookie_count": 0,
        "sample_names": [],
    }
    try:
        if not cookie_file.exists():
            info["reason"] = "missing file"
            return info
        if cookie_file.stat().st_size < 10:
            info["reason"] = "file too small"
            return info
    except Exception as exc:
        info["reason"] = f"stat failed: {str(exc)[:80]}"
        return info

    cookies = _load_instagram_cookies(cookie_file)
    info["ig_cookie_count"] = len(cookies)
    sample_names = sorted(
        {
            str(cookie.get("name") or "").strip()
            for cookie in cookies
            if str(cookie.get("name") or "").strip()
        }
    )
    info["sample_names"] = sample_names[:6]

    if not cookies:
        info["reason"] = "no instagram cookie rows"
        return info

    session_cookie = next(
        (cookie for cookie in cookies if str(cookie.get("name") or "").strip() == "sessionid"),
        None,
    )
    if not session_cookie:
        found = ", ".join(info["sample_names"]) or "none"
        info["reason"] = f"missing sessionid (found: {found})"
        return info

    session_value = str(session_cookie.get("value") or "").strip()
    if not session_value:
        info["reason"] = "sessionid empty"
        return info

    expires = session_cookie.get("expires")
    try:
        if expires and int(expires) <= int(time.time()):
            info["reason"] = "sessionid expired"
            return info
    except Exception:
        pass

    info["usable"] = True
    info["reason"] = "sessionid ready"
    return info


def _save_loader_session(loader, progress_cb: Optional[Callable]) -> None:
    session_file = _preferred_session_file()
    if not session_file:
        return

    try:
        session_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            loader.save_session_to_file(filename=str(session_file))
        except TypeError:
            loader.save_session_to_file(str(session_file))
        _progress(f"[Instaloader] Session cached -> {session_file.name}", progress_cb)
    except Exception as exc:
        _progress(f"[Instaloader] Session cache skipped: {exc}", progress_cb)


def _apply_cookie_file_session(loader, cookie_file: Path, progress_cb: Optional[Callable]) -> bool:
    cookies = _load_instagram_cookies(cookie_file)
    if not cookies:
        _progress(f"[Instaloader] No Instagram cookies found in {cookie_file.name}", progress_cb)
        return False

    csrf_token = ""
    try:
        loader.context._session.headers.update({"User-Agent": "Mozilla/5.0"})
    except Exception:
        pass

    try:
        for cookie in cookies:
            if cookie.get("name") == "csrftoken":
                csrf_token = str(cookie.get("value") or "")
            loader.context._session.cookies.set(
                cookie.get("name", ""),
                cookie.get("value", ""),
                domain=cookie.get("domain"),
                path=cookie.get("path", "/") or "/",
                secure=bool(cookie.get("secure", False)),
                expires=cookie.get("expires"),
            )
        if csrf_token:
            loader.context._session.headers.update({"X-CSRFToken": csrf_token})
        loader.context._session.headers.setdefault("X-IG-App-ID", "936619743392459")
        loader.context._session.headers.setdefault("Referer", "https://www.instagram.com/")
    except Exception as exc:
        _progress(f"[Instaloader] Failed applying cookie bridge: {exc}", progress_cb)
        return False

    try:
        username = loader.test_login()
    except Exception as exc:
        _progress(f"[Instaloader] Cookie login probe failed: {exc}", progress_cb)
        return False

    if not username:
        _progress(f"[Instaloader] Cookie login failed for {cookie_file.name}", progress_cb)
        return False

    try:
        loader.context.username = username
    except Exception:
        pass

    _progress(f"[Instaloader] Cookie login OK as @{username}", progress_cb)
    _save_loader_session(loader, progress_cb)
    return True


def _authenticate_loader(
    loader,
    *,
    progress_cb: Optional[Callable],
    cookie_file: Optional[str] = None,
    cookie_candidates: Optional[Iterable[str]] = None,
) -> bool:
    session_file = _find_session_file()
    if session_file:
        _progress(f"[Instaloader] Loading session from {session_file.name}...", progress_cb)
        try:
            loader.load_session_from_file(username=None, filename=str(session_file))
            _progress("[Instaloader] Session loaded.", progress_cb)
            return True
        except Exception as exc:
            _progress(f"[Instaloader] Session load failed: {exc}", progress_cb)
            _progress("[Instaloader] Falling back to cookie bridge candidates...", progress_cb)

    candidate_files = _iter_cookie_candidates(
        primary_cookie=cookie_file,
        cookie_candidates=cookie_candidates,
    )
    usable_cookie_files: List[Path] = []

    if candidate_files:
        _progress(f"[Instaloader] Inspecting {len(candidate_files)} cookie candidate(s)...", progress_cb)
    else:
        _progress("[Instaloader] No cookie bridge candidates were supplied.", progress_cb)

    for candidate in candidate_files:
        info = _inspect_cookie_candidate(candidate)
        if info.get("usable"):
            usable_cookie_files.append(candidate)
            _progress(
                f"[Instaloader] Candidate OK: {_cookie_debug_path(candidate)} "
                f"({int(info.get('ig_cookie_count') or 0)} IG cookies)",
                progress_cb,
            )
        else:
            _progress(
                f"[Instaloader] Candidate reject: {_cookie_debug_path(candidate)} "
                f"-> {info.get('reason') or 'unknown'}",
                progress_cb,
            )

    if not usable_cookie_files:
        _progress(
            "[Instaloader] No cached session or usable Instagram cookie file found.",
            progress_cb,
        )
        return False

    for candidate in usable_cookie_files:
        _progress(
            f"[Instaloader] Trying cookie bridge: {_cookie_debug_path(candidate)}",
            progress_cb,
        )
        if _apply_cookie_file_session(loader, candidate, progress_cb):
            return True

    _progress("[Instaloader] Cookie bridge could not establish a session.", progress_cb)
    return False


def grab_instagram_links_instaloader(
    profile_url: str,
    max_videos: int = 20,
    progress_cb: Optional[Callable[[str], None]] = None,
    cookie_file: Optional[str] = None,
    cookie_candidates: Optional[Iterable[str]] = None,
) -> List[Dict]:
    """
    Fetch video post URLs from an Instagram profile using Instaloader.

    Returns a list of entry dicts compatible with download_engine's pipeline:
        {"url": "https://www.instagram.com/p/{shortcode}/",
         "id": shortcode, "platform": "instagram", "creator": username, "title": "..."}

    Returns [] on any error so the calling code can fall through gracefully.
    """
    try:
        import instaloader
    except ImportError:
        _progress("[Instaloader] Not installed - skipping", progress_cb)
        return []

    username = _extract_username(profile_url)
    if not username:
        _progress(f"[Instaloader] Cannot parse username from URL: {profile_url}", progress_cb)
        return []

    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
        quiet=True,
        sleep=True,
        max_connection_attempts=2,
    )

    if not _authenticate_loader(
        loader,
        progress_cb=progress_cb,
        cookie_file=cookie_file,
        cookie_candidates=cookie_candidates,
    ):
        return []

    try:
        _progress(f"[Instaloader] Fetching profile: @{username}...", progress_cb)
        profile = instaloader.Profile.from_username(loader.context, username)
    except instaloader.exceptions.ProfileNotExistsException:
        _progress(f"[Instaloader] Profile @{username} does not exist or is private.", progress_cb)
        return []
    except Exception as exc:
        _progress(f"[Instaloader] Profile fetch error: {exc}", progress_cb)
        return []

    _progress(
        f"[Instaloader] @{username} - {profile.mediacount} total posts. Scanning for videos...",
        progress_cb,
    )

    entries: List[Dict] = []
    scanned = 0
    scan_limit = max(max_videos * 3, 60)

    try:
        for post in profile.get_posts():
            scanned += 1
            if scanned > scan_limit:
                break

            if not post.is_video:
                continue

            shortcode = post.shortcode
            caption = (post.caption or "")[:100].strip().replace("\n", " ")
            entries.append(
                {
                    "url": f"https://www.instagram.com/reel/{shortcode}/",
                    "id": shortcode,
                    "platform": "instagram",
                    "creator": username,
                    "title": caption or shortcode,
                    "thumbnail": "",
                }
            )

            _progress(
                f"[Instaloader] Found video {len(entries)}/{max_videos}: {caption[:50] or shortcode}",
                progress_cb,
            )

            if len(entries) >= max_videos + 5:
                break

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
    """Quick check - is an Instaloader session file present?"""
    return _find_session_file() is not None


def get_session_setup_instructions() -> str:
    session_file = _preferred_session_file()
    dest = str(session_file) if session_file else "cookies/instagram_instaloader_session"
    return (
        "Instagram Instaloader session setup:\n"
        "  1. Open terminal in the app folder\n"
        "  2. Run: python -m instaloader --login=your_instagram_username\n"
        "  3. Copy the created session file to:\n"
        f"     {dest}\n"
        "  4. Or save a valid Instagram cookie file and the app will bootstrap the session automatically."
    )
