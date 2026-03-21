"""
modules/creator_profiles/download_engine.py
Tiered downloader + optional post-processing for creator profiles.

Link grabbing: uses Playwright browser engine (same as Link Grabber module).
Downloading: uses method3-style approach from VideoDownloaderThread (same as Video Downloader module).
Never reads links.txt files Ã¢â‚¬â€ always visits profile fresh via browser.
"""

import json
import logging
import os
import random
import shutil
import subprocess
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yt_dlp
from PyQt5.QtCore import QThread, pyqtSignal

from .config_manager import CreatorConfig
from modules.config.paths import find_ytdlp_executable
from modules.config.paths import get_cookies_dir
from modules.shared.auth_network_hub import AuthNetworkHub
from modules.shared.pacing import PacingManager
from modules.video_downloader.core import VideoDownloaderThread

# ── Approach Toggle ──────────────────────────────────────────────────────────
# True = IXBrowser (Approach 2), False = Playwright (Approach 1 — existing)
ENABLE_IXBROWSER_FALLBACK = True


_SCOPED_LIBRARY_LOG_MARKERS = (
    "modules/link_grabber/",
    "modules\\link_grabber\\",
)


def _is_scoped_library_record(record: logging.LogRecord, thread_id: int) -> bool:
    if getattr(record, "thread", None) != thread_id:
        return False
    path = str(getattr(record, "pathname", "") or "").replace("\\", "/").lower()
    return any(marker.replace("\\", "/").lower() in path for marker in _SCOPED_LIBRARY_LOG_MARKERS)


class _ScopedLibraryLogSuppressor(logging.Filter):
    def __init__(self, thread_id: int):
        super().__init__()
        self.thread_id = thread_id

    def filter(self, record: logging.LogRecord) -> bool:
        return not _is_scoped_library_record(record, self.thread_id)


class _ScopedLibraryLogRelay(logging.Handler):
    def __init__(self, worker: "CreatorDownloadWorker", thread_id: int):
        super().__init__(level=logging.WARNING)
        self.worker = worker
        self.thread_id = thread_id

    # yt-dlp messages that are known platform issues — not actionable by the user.
    _SUPPRESS_PATTERNS = (
        "marked as broken, and will probably not work",
        "Unable to extract data; please report this issue",
        "Confirm you are on the latest version using yt-dlp -U",
    )

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.WARNING:
            return
        if not _is_scoped_library_record(record, self.thread_id):
            return
        try:
            message = re.sub(r"\s+", " ", str(record.getMessage() or "").strip())
        except Exception:
            message = ""
        if not message:
            return
        # Suppress known yt-dlp platform-level broken-extractor noise
        if any(p in message for p in self._SUPPRESS_PATTERNS):
            return
        stage = "ExtractorError" if record.levelno >= logging.ERROR else "ExtractorWarn"
        self.worker._terminal_log(stage, message)


# Ã¢â€â‚¬Ã¢â€â‚¬ User Agent Pool Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def _get_random_user_agent() -> str:
    """Get random user agent Ã¢â‚¬â€ same pool as Link Grabber and Video Downloader."""
    try:
        from modules.shared.user_agents import get_random_user_agent
        return get_random_user_agent()
    except Exception:
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        return random.choice(agents)


# Ã¢â€â‚¬Ã¢â€â‚¬ Helpers Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def _safe_id_from_url(url: str) -> str:
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
    # Fallback: clean the URL but keep enough to be unique
    return u.split('?')[0].rstrip("/").split('/')[-1]


_GENERIC_TITLE_PHRASES = {
    "instagram post",
    "instagram reel",
    "youtube video",
    "youtube short",
    "tiktok video",
    "facebook video",
    "facebook reel",
    "video",
    "post",
    "reel",
    "short",
    "untitled",
}

_GENERIC_TITLE_WORDS = {
    "facebook", "instagram", "tiktok", "youtube",
    "video", "post", "short", "shorts", "reel", "reels",
    "viral", "fyp",
}


def _clean_video_title_candidate(value: str, *, strip_tags: bool = True) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    text = Path(text).stem
    text = re.sub(r'^[\d.,]+[KkMm]?_views_[\d.,]+[KkMm]?_reactions?_', '', text)
    text = text.replace("_", " ")
    text = re.sub(r'[\\/*?:"<>|]+', "", text)
    text = re.sub(r"\s+", " ", text).strip(" .-_")

    if strip_tags:
        tokens = text.split()
        no_tags = [tok for tok in tokens if not tok.startswith("#")]
        if no_tags and len(" ".join(no_tags).strip()) >= 5:
            text = " ".join(no_tags)

    return re.sub(r"\s+", " ", text).strip(" .-_")[:100]


def _is_meaningful_video_title(title: str, creator_name: str = "", source_id: str = "") -> bool:
    cleaned = _clean_video_title_candidate(title)
    if len(cleaned) < 6:
        return False

    lowered = cleaned.lower().strip()
    if lowered in _GENERIC_TITLE_PHRASES:
        return False

    normalized_title = re.sub(r'[^a-z0-9]+', '', lowered)
    normalized_creator = re.sub(r'[^a-z0-9]+', '', str(creator_name or "").lower())
    normalized_source_id = re.sub(r'[^a-z0-9]+', '', str(source_id or "").lower())

    if normalized_creator and normalized_title == normalized_creator:
        return False
    if normalized_source_id and normalized_title == normalized_source_id:
        return False

    tokens = [tok for tok in re.split(r"\s+", lowered) if tok]
    meaningful_tokens = [tok for tok in tokens if tok not in _GENERIC_TITLE_WORDS and not tok.startswith("#")]
    if not meaningful_tokens:
        return False

    hashtag_tokens = [tok for tok in tokens if tok.startswith("#")]
    if hashtag_tokens and len(hashtag_tokens) >= len(tokens):
        return False

    return True


def _build_preferred_download_name(
    *,
    raw_filename: str,
    provided_title: str,
    creator_name: str,
    source_url: str,
    extension: str,
) -> str:
    source_id = _safe_id_from_url(source_url)
    title_candidate = _clean_video_title_candidate(provided_title)
    raw_candidate = _clean_video_title_candidate(raw_filename)

    if _is_meaningful_video_title(title_candidate, creator_name, source_id):
        stem = title_candidate
    elif _is_meaningful_video_title(raw_candidate, creator_name, source_id):
        stem = raw_candidate
    else:
        stem = f"{creator_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return f"{stem}{extension}"


def _normalize_youtube_download_url(url: str) -> str:
    """Use the more compatible watch URL for YouTube Shorts downloads."""
    raw = (url or "").strip()
    if not raw:
        return ""
    match = re.search(
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{6,})",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return raw
    return f"https://www.youtube.com/watch?v={match.group(1)}"


def _infer_youtube_ix_view(yt_content_type: str, urls: List[str]) -> str:
    """Pick the best YouTube IXBrowser tab based on preference and observed links."""
    pref = str(yt_content_type or "all").strip().lower()
    if pref in {"shorts", "long"}:
        return pref

    shorts_count = 0
    long_count = 0
    for url in urls or []:
        u = str(url or "").strip().lower()
        if not u:
            continue
        if "/shorts/" in u:
            shorts_count += 1
        elif "watch?v=" in u:
            long_count += 1

    if shorts_count and shorts_count >= long_count:
        return "shorts"
    if long_count:
        return "long"
    return "all"


def _ffmpeg_path() -> str:
    """Return a working ffmpeg path, validating each candidate before use.

    On the second PC, the bundled ffmpeg.exe may be missing companion DLLs
    (e.g. avcodec-62.dll) and will crash with error 0xc0000142. We test each
    candidate with -version and skip any broken ones.
    """
    try:
        from modules.video_editor.utils import check_ffmpeg, get_ffmpeg_path

        if check_ffmpeg():
            return get_ffmpeg_path()
    except Exception:
        pass

    # Last resort: let subprocess resolve it at call site
    return "ffmpeg"


def _detect_platform(url: str) -> str:
    u = (url or "").lower()
    if "tiktok.com" in u:
        return "tiktok"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "instagram.com" in u:
        return "instagram"
    if "facebook.com" in u or "fb.com" in u:
        return "facebook"
    return "other"


def _facebook_backfill_sources(url: str) -> List[Tuple[str, str]]:
    """Return ordered Facebook profile/tab sources for reel/video discovery."""
    raw = (url or "").strip()
    if not raw:
        return []
    low = raw.lower().rstrip("/")

    # Already a direct video-like URL or explicit reels/videos tab.
    if any(token in low for token in ("/reel/", "/reels", "/videos", "/watch/", "/share/v/")):
        return [("direct", raw)]

    def _dedupe(sources: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        deduped: List[Tuple[str, str]] = []
        seen: set = set()
        for label, candidate in sources:
            candidate = (candidate or "").strip()
            if not candidate:
                continue
            key = candidate.rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append((label, candidate))
        return deduped

    def _set_profile_query_tab(source_url: str, tab_name: str) -> str:
        parsed = urlparse(source_url)
        query_items = [
            (k, v)
            for k, v in parse_qsl(parsed.query or "", keep_blank_values=True)
            if k.lower() != "sk"
        ]
        query_items.append(("sk", tab_name))
        return urlunparse(parsed._replace(query=urlencode(query_items)))

    # profile.php style prefers reels tab query.
    if "facebook.com/profile.php" in low:
        return _dedupe([
            ("reels", _set_profile_query_tab(raw, "reels_tab")),
            ("videos", _set_profile_query_tab(raw, "videos")),
            ("profile", raw),
        ])

    # Username/profile style -> force reels tab URL.
    base = raw.rstrip("/")
    return _dedupe([
        ("reels", base + "/reels"),
        ("videos", base + "/videos"),
        ("profile", raw),
    ])


def _instagram_backfill_url(url: str) -> str:
    """Return a stronger Instagram source URL for reel discovery."""
    raw = (url or "").strip()
    if not raw:
        return raw
    low = raw.lower().rstrip("/")

    # Already direct media URL.
    if any(token in low for token in ("/reel/", "/reels/", "/p/", "/tv/")):
        return raw

    # Profile-like URL -> force reels tab.
    return raw.rstrip("/") + "/reels/"


def _is_profile_listing_url(platform_key: str, url: str) -> bool:
    """Return True when the source URL represents a creator listing, not a direct post."""
    raw = (url or "").strip()
    low = raw.lower()
    if not raw:
        return False

    if platform_key == "facebook":
        return (
            ("facebook.com" in low or "fb.com" in low)
            and not any(token in low for token in ("/reel/", "/watch/", "/share/v/"))
        )

    if platform_key == "instagram":
        return (
            "instagram.com" in low
            and not any(token in low for token in ("/reel/", "/reels/", "/p/", "/tv/"))
        )

    if platform_key == "youtube":
        parsed = urlparse(raw)
        path = (parsed.path or "").lower()
        return (
            ("youtube.com" in low or "youtu.be" in low)
            and bool(path.strip("/"))
            and "watch?v=" not in low
            and "/watch" not in path
            and "/shorts/" not in path
            and "/playlist" not in path
            and "/live/" not in path
        )

    if platform_key == "tiktok":
        return (
            "tiktok.com" in low
            and "/@" in low
            and not any(token in low for token in ("/video/", "/photo/"))
        )

    return False


# â"€â"€ Intelligent Link Grabbing handled via modules.link_grabber.core â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€


# Ã¢â€â‚¬Ã¢â€â‚¬ Video Download (method3-style: UA rotation + Chrome 120 headers) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

# Smart format: prefer mp4+m4a merge, fallback to best available
_SMART_FORMAT = (
    "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
    "/bestvideo+bestaudio"
    "/best[ext=mp4]"
    "/best"
)

# Chrome 120 http_headers dict for yt-dlp
_CHROME120_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
}


def _validate_cookie_file(cookie_path: str) -> bool:
    """Basic Netscape cookie-file validation."""
    try:
        p = Path(cookie_path)
        if not p.exists() or not p.is_file() or p.stat().st_size < 10:
            return False
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7 and parts[5] and len(parts[6]) >= 1:
                    return True
        return False
    except Exception:
        return False


def _cookie_has_sessionid(cookie_path: str) -> bool:
    """Instagram auth cookies should include sessionid."""
    try:
        with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7 and parts[5].lower() == "sessionid" and parts[6]:
                    return True
    except Exception:
        pass
    return False


def _normalize_cookie_candidates(
    primary_cookie: Optional[str],
    cookie_candidates: Optional[List[str]],
) -> List[str]:
    """Build a de-duplicated list of usable cookie files."""
    merged: List[str] = []
    if primary_cookie:
        merged.append(primary_cookie)
    if cookie_candidates:
        merged.extend(cookie_candidates)

    out: List[str] = []
    seen = set()
    for candidate in merged:
        try:
            p = str(candidate or "").strip()
            if not p:
                continue
            key = str(Path(p).resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            if _validate_cookie_file(p):
                out.append(p)
        except Exception:
            continue
    return out


def _validate_instagram_cookie(cookie_path: str) -> bool:
    """Prefer strict Instagram validation; fallback to sessionid check."""
    if not _validate_cookie_file(cookie_path):
        return False
    try:
        from modules.video_downloader.instagram_helper import InstagramCookieValidator

        validator = InstagramCookieValidator()
        validation = validator.validate_cookie_file(cookie_path)
        if bool(validation.get("is_valid")):
            return True
    except Exception:
        pass
    return _cookie_has_sessionid(cookie_path)


def download_video(
    url: str,
    output_folder: Path,
    ffmpeg: str = "ffmpeg",
    progress_cb: Callable[[str], None] = None,
    proxy_url: str = None,
    cookiefile: str = None,
    cookie_candidates: Optional[List[str]] = None,
    cancel_event: threading.Event = None,
    error_out: Optional[List[str]] = None,
) -> Optional[Path]:
    """
    Platform-aware video download with API + CLI fallback.
    """
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    video_exts = {
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".mpeg", ".mpg"
    }

    before_files = {str(p) for p in output_folder.rglob("*") if p.is_file()}
    result_path: List[Optional[Path]] = [None]
    cancelled = [False]

    platform = _detect_platform(url)
    ytdlp_bin = find_ytdlp_executable()
    last_error = [""]
    if error_out is not None:
        try:
            error_out[:] = [""]
        except Exception:
            pass

    def _set_error(msg: str):
        text = str(msg or "").strip()
        if not text:
            return
        clean = " ".join(text.split())
        last_error[0] = clean[:300]
        if error_out is not None:
            try:
                error_out[:] = [last_error[0]]
            except Exception:
                pass

    def _hook(d):
        if cancel_event and cancel_event.is_set():
            cancelled[0] = True
            raise yt_dlp.utils.DownloadError("Cancelled")
        if d.get("status") == "finished":
            fp = d.get("filename") or d.get("info_dict", {}).get("_filename", "")
            if fp:
                result_path[0] = Path(fp)
        if progress_cb and d.get("_percent_str"):
            progress_cb(f"    {d['_percent_str'].strip()}")

    def _pick_fresh_video() -> Optional[Path]:
        try:
            # First, check if the hook already gave us the exact path
            if result_path[0] and result_path[0].exists():
                return result_path[0]

            fresh = [
                p for p in output_folder.rglob("*")
                if p.is_file() and str(p) not in before_files and p.suffix.lower() in video_exts
            ]
            if len(fresh) > 1:
                # YT-DLP often preserves original timestamps (from e.g. 2021). 
                # Instead of mtime, pick the largest file, which is usually the merged video.
                # DO NOT delete other files, as they might be concurrent downloads.
                fresh.sort(key=lambda p: p.stat().st_size, reverse=True)
                return fresh[0]
            return fresh[0] if fresh else None
        except Exception:
            return None

    def _ffmpeg_ok() -> bool:
        if not ffmpeg or ffmpeg == "ffmpeg":
            return bool(shutil.which("ffmpeg"))
        return Path(ffmpeg).exists()

    ffmpeg_available = _ffmpeg_ok()
    cookie_pool = _normalize_cookie_candidates(cookiefile, cookie_candidates)

    def _base_opts(fmt: str, cookie: str = None, proxy: str = None, extractor_args: dict = None) -> dict:
        user_agent = _get_random_user_agent()
        headers = dict(_CHROME120_HEADERS)
        headers["User-Agent"] = user_agent
        opts = {
            "outtmpl": str(output_folder / "%(title).80s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
            "noplaylist": True,
            "continuedl": True,
            "nocheckcertificate": True,
            "restrictfilenames": True,
            "socket_timeout": 60,
            "retries": 3,
            "fragment_retries": 3,
            "http_headers": headers,
            "progress_hooks": [_hook],
        }
        if fmt:
            opts["format"] = fmt
        if cookie and _validate_cookie_file(cookie):
            opts["cookiefile"] = cookie
        if proxy:
            opts["proxy"] = proxy
        if extractor_args:
            opts["extractor_args"] = extractor_args
        if ffmpeg_available and ffmpeg and ffmpeg != "ffmpeg":
            opts["ffmpeg_location"] = str(Path(ffmpeg).parent)
            opts["merge_output_format"] = "mp4"
        return opts

    def _try_opts(opts: dict):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            if cancel_event and cancel_event.is_set():
                cancelled[0] = True
            err = str(e)
            _set_error(err)
            return False, err
        if result_path[0] and result_path[0].exists():
            return True, ""
        fp = _pick_fresh_video()
        if fp:
            result_path[0] = fp
            return True, ""
        err = "No media file created"
        _set_error(err)
        return False, err

    def _try_cli(fmt: str, cookie: str = None, proxy: str = None, player_client: str = None):
        if not ytdlp_bin:
            return False, "yt-dlp executable not found"
        if cancel_event and cancel_event.is_set():
            cancelled[0] = True
            return False, "Cancelled"

        cmd = [
            ytdlp_bin,
            "-o", str(output_folder / "%(title).80s.%(ext)s"),
            "--no-warnings",
            "--no-playlist",
            "--continue",
            "--restrict-filenames",
            "--retries", "3",
            "--fragment-retries", "3",
            "--socket-timeout", "60",
            "--user-agent", _get_random_user_agent(),
            "--no-check-certificate",
        ]
        if fmt:
            cmd.extend(["-f", fmt])
        if cookie and _validate_cookie_file(cookie):
            cmd.extend(["--cookies", cookie])
        if proxy:
            cmd.extend(["--proxy", proxy])
        if player_client:
            cmd.extend(["--extractor-args", f"youtube:player_client={player_client}"])
        if ffmpeg_available and ffmpeg and ffmpeg != "ffmpeg":
            cmd.extend(["--ffmpeg-location", str(Path(ffmpeg).parent), "--merge-output-format", "mp4"])
        for k, v in _CHROME120_HEADERS.items():
            cmd.extend(["--add-header", f"{k}:{v}"])
        cmd.append(url)

        try:
            run = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=420,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            err = "yt-dlp CLI timeout"
            _set_error(err)
            return False, err
        except Exception as e:
            err = str(e)
            _set_error(err)
            return False, err

        if run.returncode == 0:
            if result_path[0] and result_path[0].exists():
                return True, ""
            fp = _pick_fresh_video()
            if fp:
                result_path[0] = fp
                return True, ""
            err = "CLI completed but no media file created"
            _set_error(err)
            return False, err

        err = (run.stderr or run.stdout or "").strip()
        _set_error(err)
        return False, err

    def _attempt_download(
        fmt: str,
        cookie: str = None,
        proxy: str = None,
        extractor_args: dict = None,
        player_client: str = None,
        force_cli: bool = False,
    ):
        if force_cli:
            return _try_cli(fmt, cookie, proxy, player_client)

        ok, err = _try_opts(_base_opts(fmt, cookie, proxy, extractor_args))
        if ok:
            return True, ""

        err_l = (err or "").lower()
        should_try_cli = bool(ytdlp_bin) and (
            platform in ("youtube", "instagram")
            or "failed to extract any player response" in err_l
            or "empty media response" in err_l
            or "no video formats found" in err_l
        )
        if not should_try_cli:
            return False, err

        ok_cli, err_cli = _try_cli(fmt, cookie, proxy, player_client)
        if ok_cli:
            return True, ""
        return False, (err_cli or err)

    if platform == "youtube":
        is_shorts = "/shorts/" in url.lower()
        web_cookies = list(cookie_pool)

        if is_shorts:
            client_cookie_pairs = [
                ("android_vr", None),
                ("ios", None),
                *[("web", c) for c in web_cookies],
                ("android", None),
                ("web", None),
            ]
        else:
            client_cookie_pairs = [
                *[("web", c) for c in web_cookies],
                ("android_vr", None),
                ("ios", None),
                ("android", None),
                ("web", None),
            ]

        seen_cc = set()
        unique_pairs = []
        for client, ck in client_cookie_pairs:
            key = (client, ck or "")
            if key in seen_cc:
                continue
            seen_cc.add(key)
            unique_pairs.append((client, ck))

        smart_fmt = _SMART_FORMAT if ffmpeg_available else "best[ext=mp4]/best"
        formats_to_try = [smart_fmt, "bestvideo+bestaudio/best", "best[ext=mp4]/best", "best"]

        for strategy_label, use_proxy in [("direct", False), ("proxy", bool(proxy_url))]:
            if strategy_label == "proxy" and not use_proxy:
                continue
            if cancelled[0]:
                break

            active_proxy = proxy_url if use_proxy else None

            for client, ck in unique_pairs:
                if cancelled[0]:
                    break

                extractor_args = {"youtube": {"player_client": [client]}}
                for fmt in formats_to_try:
                    if cancelled[0]:
                        break
                    if progress_cb:
                        ck_label = Path(ck).name if ck else "no-cookie"
                        progress_cb(f"  [YT] {strategy_label} | {client} / {ck_label}")

                    ok, err = _attempt_download(
                        fmt=fmt,
                        cookie=ck,
                        proxy=active_proxy,
                        extractor_args=extractor_args,
                        player_client=client,
                    )
                    if ok:
                        return result_path[0] or _pick_fresh_video()

                    err_low = (err or "").lower()
                    if "requested format is not available" in err_low:
                        continue
                    if any(x in err_low for x in (
                        "failed to extract any player response",
                        "no video formats found",
                    )):
                        if progress_cb:
                            progress_cb(f"  [YT] {client}: player blocked, trying next client")
                        break
                    if any(x in err_low for x in ("sign in", "login required", "private")):
                        _set_error("YouTube login/cookies required for this video")
                        return None
                    break

        if progress_cb and last_error[0]:
            progress_cb(f"  [YT] Final error: {last_error[0]}")
        return _pick_fresh_video()

    if platform == "instagram":
        ig_valid_cookies = [c for c in cookie_pool if _validate_instagram_cookie(c)]
        if not ig_valid_cookies:
            ig_valid_cookies = [c for c in cookie_pool if _cookie_has_sessionid(c)]
        if progress_cb:
            progress_cb(f"  [IG] Cookies available: {len(cookie_pool)} | usable: {len(ig_valid_cookies)}")

        smart_fmt = _SMART_FORMAT if ffmpeg_available else "best[ext=mp4]/best"
        attempt_list = []
        for ck in ig_valid_cookies:
            attempt_list.append((smart_fmt, ck, proxy_url, "with-cookie"))
            attempt_list.append((smart_fmt, ck, None, "with-cookie/no-proxy"))
            attempt_list.append(("best", ck, None, "best/with-cookie"))
        attempt_list.append((smart_fmt, None, proxy_url, "no-cookie"))
        attempt_list.append(("best[ext=mp4]/best", None, None, "mp4/no-cookie"))
        attempt_list.append(("best", None, None, "best/no-cookie"))

        seen_ig = set()
        unique_ig = []
        for fmt, ck, px, label in attempt_list:
            key = (fmt, ck or "", px or "")
            if key in seen_ig:
                continue
            seen_ig.add(key)
            unique_ig.append((fmt, ck, px, label))

        for fmt, ck, px, label in unique_ig:
            if cancelled[0]:
                break
            if progress_cb:
                ck_label = Path(ck).name if ck else "no-cookie"
                progress_cb(f"  [IG] {label} | {ck_label}")

            ok, err = _attempt_download(
                fmt=fmt,
                cookie=ck,
                proxy=px,
                extractor_args=None,
            )
            if ok:
                return result_path[0] or _pick_fresh_video()

            err_low = (err or "").lower()
            if any(x in err_low for x in ("empty media response", "login", "private")):
                if progress_cb:
                    progress_cb("  [IG] Auth required or blocked, trying next attempt")
                continue

        if progress_cb and last_error[0]:
            progress_cb(f"  [IG] Final error: {last_error[0]}")
        return _pick_fresh_video()

    # Facebook serves pre-muxed streams — bestvideo+bestaudio often fails.
    # Use a wider ladder that tries pre-muxed HD/SD before the smart merge format.
    if platform == "facebook":
        smart_fmt = _SMART_FORMAT if ffmpeg_available else "best[ext=mp4]/best"
        format_candidates = [
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best",
            "hd/sd/best[ext=mp4]/best",
            smart_fmt,
            "best[ext=mp4]/best",
            "best",
        ]
    else:
        smart_fmt = _SMART_FORMAT if ffmpeg_available else "best[ext=mp4]/best"
        format_candidates = [smart_fmt, "best[ext=mp4]/best", "best"]

    cookie_choices = list(cookie_pool)
    cookie_choices.append(None)

    attempt_plan = []
    for fmt in format_candidates:
        for ck in cookie_choices:
            attempt_plan.append((fmt, proxy_url, ck, "primary"))
        if proxy_url:
            for ck in cookie_choices:
                attempt_plan.append((fmt, None, ck, "no-proxy"))

    seen_attempts = set()
    unique_attempts = []
    for fmt, px, ck, label in attempt_plan:
        key = (fmt, px or "", ck or "")
        if key in seen_attempts:
            continue
        seen_attempts.add(key)
        unique_attempts.append((fmt, px, ck, label))

    for idx, (fmt, px, ck, label) in enumerate(unique_attempts, start=1):
        if cancelled[0]:
            break
        if progress_cb:
            ck_label = Path(ck).name if ck else "no-cookie"
            progress_cb(f"  Attempt {idx}/{len(unique_attempts)} [{label}] | {ck_label}")

        ok, _err = _attempt_download(fmt=fmt, cookie=ck, proxy=px)
        if ok:
            return result_path[0] or _pick_fresh_video()

    if cancelled[0]:
        _set_error("Cancelled")
        return None
    if progress_cb and last_error[0]:
        progress_cb(f"  Final error: {last_error[0]}")
    return _pick_fresh_video()


# FFprobe / Split
def _ffprobe_path(ffmpeg: str) -> str:
    if ffmpeg and ffmpeg != "ffmpeg":
        p = Path(ffmpeg)
        probe_name = "ffprobe.exe" if p.suffix.lower() == ".exe" else "ffprobe"
        sibling = p.with_name(probe_name)
        if sibling.exists():
            return str(sibling)
    return shutil.which("ffprobe") or "ffprobe"


def _probe_duration_seconds(input_path: Path, ffmpeg: str = "ffmpeg") -> float:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        ffprobe = _ffprobe_path(ffmpeg)
        probe_cmds = [
            [
                ffprobe, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ],
            [
                ffprobe, "-v", "error",
                "-show_entries", "stream=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ],
        ]
        for cmd in probe_cmds:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=flags,
            )
            if r.returncode != 0:
                continue
            for raw in (r.stdout or "").splitlines():
                try:
                    sec = float((raw or "").strip())
                except Exception:
                    continue
                if sec > 0:
                    return sec
    except Exception:
        pass
    try:
        r = subprocess.run(
            [ffmpeg, "-i", str(input_path)],
            capture_output=True, text=True, timeout=30,
            creationflags=flags,
        )
        text = (r.stderr or "") + "\n" + (r.stdout or "")
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 0.0


def _probe_duration_with_retry(
    input_path: Path,
    ffmpeg: str = "ffmpeg",
    delays: Tuple[float, ...] = (0.0, 0.12, 0.30, 0.65, 1.10),
) -> float:
    last = 0.0
    for idx, delay in enumerate(delays):
        if idx > 0 and delay > 0:
            time.sleep(delay)
        last = _probe_duration_seconds(input_path, ffmpeg)
        if last > 0:
            return last
    return last


def _can_decode_media(input_path: Path, ffmpeg: str = "ffmpeg") -> bool:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(input_path),
                "-t",
                "0.20",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=45,
            creationflags=flags,
        )
        return result.returncode == 0
    except Exception:
        return False


def split_video(
    input_path: Path,
    output_folder: Path,
    segment_sec: float,
    ffmpeg: str = "ffmpeg",
    progress_cb: Callable[[str], None] = None,
) -> List[Path]:
    input_path = Path(input_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    try:
        segment_sec = float(segment_sec)
    except Exception:
        segment_sec = 0.0
    if segment_sec <= 0:
        return []

    stem = input_path.stem
    input_ext = input_path.suffix.lower()
    out_ext = input_ext if input_ext in {".mp4", ".m4v", ".mov"} else ".mp4"

    duration = _probe_duration_seconds(input_path, ffmpeg)
    if duration <= 0:
        return []

    for stale in output_folder.glob(f"{stem}_part*{out_ext}"):
        try:
            stale.unlink()
        except Exception:
            pass

    parts: List[Path] = []
    start = 0.0
    idx = 1
    epsilon = 0.02
    min_tail_sec = 0.35
    min_valid_part_sec = 0.20

    while start < duration - epsilon and idx <= 2000:
        remaining = duration - start
        if remaining <= min_tail_sec:
            break
        chunk = min(segment_sec, remaining)
        out_path = output_folder / f"{stem}_part{idx:03d}{out_ext}"

        if progress_cb:
            progress_cb(f"    Split part {idx}: {start:.2f}s -> {start + chunk:.2f}s")

        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-i", str(input_path),
            "-ss", f"{start:.3f}", "-t", f"{chunk:.3f}",
            "-map", "0:v:0", "-map", "0:a?",
            "-fflags", "+genpts",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-fps_mode", "cfr",
            "-af", "aresample=async=1:first_pts=0",
            "-c:a", "aac", "-b:a", "160k",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            str(out_path), "-y",
        ]

        def _run_safe(command: List[str]) -> Tuple[int, str]:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
            try:
                stdout, stderr = p.communicate(timeout=1800)
                text = ((stderr or b"") + b"\n" + (stdout or b"")).decode(errors="ignore")
                return p.returncode, re.sub(r"\s+", " ", text).strip()
            except Exception:
                p.kill()
                p.wait()
                return -1, "ffmpeg process timed out or was terminated"

        try:
            rc, err_text = _run_safe(cmd)
            if rc != 0:
                cmd2 = [
                    ffmpeg, "-hide_banner", "-loglevel", "error",
                    "-i", str(input_path),
                    "-ss", f"{start:.3f}", "-t", f"{chunk:.3f}",
                    "-fflags", "+genpts",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-pix_fmt", "yuv420p", "-fps_mode", "cfr",
                    "-af", "aresample=async=1:first_pts=0",
                    "-c:a", "aac", "-b:a", "128k",
                    "-avoid_negative_ts", "make_zero",
                    str(out_path), "-y",
                ]
                rc2, err_text2 = _run_safe(cmd2)
                if rc2 != 0:
                    if progress_cb:
                        progress_cb(f"    Split: ffmpeg failed for part {idx} (rc={rc2})")
                        preview = (err_text2 or err_text)[:180]
                        if preview:
                            progress_cb(f"    Split: {preview}")
                    break

            if out_path.exists() and out_path.stat().st_size > 0:
                actual = _probe_duration_with_retry(out_path, ffmpeg)
                if actual >= min_valid_part_sec:
                    parts.append(out_path)
                else:
                    if _can_decode_media(out_path, ffmpeg):
                        if progress_cb:
                            progress_cb(
                                f"    Split: keeping {out_path.name} after decode fallback "
                                "(duration probe lagged)"
                            )
                        parts.append(out_path)
                    else:
                        if progress_cb:
                            progress_cb(
                                f"    Split: invalid part {idx} "
                                f"(size={out_path.stat().st_size} bytes, duration={actual:.2f}s)"
                            )
                        try:
                            out_path.unlink()
                        except Exception:
                            pass
                        break
            else:
                if progress_cb:
                    progress_cb(f"    Split: no output created for part {idx}")
                break
        except Exception as exc:
            if progress_cb:
                progress_cb(f"    Split: exception on part {idx}: {exc}")
            break

        start += chunk
        idx += 1

    return parts


def apply_preset(
    input_path: Path,
    output_folder: Path,
    preset_name: str,
    ffmpeg: str = "ffmpeg",
) -> Optional[Path]:
    target_w, target_h = 1080, 1920
    for d in ["presets/system", "presets/user", "presets/imported"]:
        p = Path(d)
        if not p.exists():
            continue
        for f in p.glob("*.json"):
            if preset_name.lower() in f.stem.lower():
                try:
                    with open(f, encoding="utf-8") as fh:
                        data = json.load(fh)
                    exp = data.get("export_settings", {})
                    target_w = int(exp.get("width", target_w))
                    target_h = int(exp.get("height", target_h))
                except Exception:
                    pass
                break

    input_path = Path(input_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    out = output_folder / f"{input_path.stem}_edited{input_path.suffix or '.mp4'}"
    vf = (
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h}"
    )
    cmd = [ffmpeg, "-i", str(input_path), "-vf", vf, "-c:a", "copy", str(out), "-y"]
    
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
        p.communicate(timeout=600)
        if p.returncode == 0 and out.exists():
            return out
    except Exception:
        if 'p' in locals():
            p.kill()
            p.wait()
        pass
    return None


# Ã¢â€â‚¬Ã¢â€â‚¬ Main Worker Thread Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class CreatorDownloadWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    paused   = pyqtSignal()
    download_speed = pyqtSignal(str)
    eta = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    login_required = pyqtSignal(str)   # emitted when IXBrowser profile not logged in

    def __init__(self, creator_folder: Path, creator_url: str, parent=None):
        super().__init__(parent)
        self.creator_folder = Path(creator_folder)
        self.creator_url = (creator_url or "").strip()
        self.config = CreatorConfig(creator_folder)
        self.auth_hub = AuthNetworkHub()
        self.proxies = self.auth_hub.get_proxy_pool()
        self._proxy_index = 0
        self.ffmpeg = _ffmpeg_path()

        self._stop = False
        self._pause_flag = False
        self._resume_event = threading.Event()
        self._resume_event.set()          # not paused initially
        self._cancel_event = threading.Event()   # for yt-dlp cancel
        self._active_downloader: Optional[VideoDownloaderThread] = None
        self._cookie_sync_info: Dict[str, str] = {}
        self._last_download_error: str = ""
        self._current_auth_ticket: Dict = {}
        self._runtime_readiness: Dict = {}
        self._attempt_summary: List[Dict] = []

        # Overall progress tracking for GUI progress bar
        self._n_target = 0           # total videos to download
        self._n_completed = 0        # videos fully downloaded so far
        try:
            self.progress.connect(self._mirror_progress_to_terminal)
        except Exception:
            pass

    # Ã¢â€â‚¬Ã¢â€â‚¬ Pause / Resume / Stop Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def pause(self):
        """Request pause after current video download finishes."""
        self._pause_flag = True
        self._resume_event.clear()

    def resume(self):
        """Resume from paused state."""
        self._pause_flag = False
        self._resume_event.set()

    def stop(self):
        """Hard stop Ã¢â‚¬â€ cancel current download and exit."""
        self._stop = True
        self._cancel_event.set()
        try:
            if self._active_downloader and self._active_downloader.isRunning():
                self._active_downloader.cancel()
        except Exception:
            pass
        self._resume_event.set()   # unblock if waiting

    def _check_pause(self):
        """Block here if paused. Returns True if we should stop."""
        if self._pause_flag:
            self.progress.emit("Paused Ã¢â‚¬â€ waiting for Resume...")
            self.paused.emit()
            self._resume_event.wait()   # blocks until resume() is called
        return self._stop

    def _on_single_video_percent(self, video_pct: int):
        """Convert per-video % into overall % and emit to GUI."""
        if self._n_target <= 0:
            return
        # Overall = (completed_videos + current_video_fraction) / total * 100
        overall = int(((self._n_completed + video_pct / 100.0) / self._n_target) * 100)
        self.progress_percent.emit(max(0, min(100, overall)))

    def _terminal_log(self, stage: str, message: str) -> None:
        """Mirror runtime details to the terminal for analysis/debugging."""
        text = str(message or "").strip()
        if not text:
            return
        creator_name = getattr(getattr(self, "creator_folder", None), "name", "?")
        creator_display = creator_name if str(creator_name).startswith("@") else f"@{creator_name}"
        print(f"[CreatorProfile][{creator_display}][{stage}] {text}", flush=True)

    def _mirror_progress_to_terminal(self, message: str) -> None:
        self._terminal_log("Progress", message)

    def _install_scoped_log_bridge(self) -> None:
        root_logger = logging.getLogger()
        thread_id = threading.get_ident()
        suppressor = _ScopedLibraryLogSuppressor(thread_id)
        relay = _ScopedLibraryLogRelay(self, thread_id)
        attached_handlers = []
        for handler in list(root_logger.handlers):
            if handler is relay:
                continue
            try:
                handler.addFilter(suppressor)
                attached_handlers.append(handler)
            except Exception:
                continue
        root_logger.addHandler(relay)
        self._scoped_log_bridge = (root_logger, relay, suppressor, attached_handlers)

    def _remove_scoped_log_bridge(self) -> None:
        bridge = getattr(self, "_scoped_log_bridge", None)
        if not bridge:
            return
        root_logger, relay, suppressor, attached_handlers = bridge
        try:
            root_logger.removeHandler(relay)
        except Exception:
            pass
        try:
            relay.close()
        except Exception:
            pass
        for handler in attached_handlers:
            try:
                handler.removeFilter(suppressor)
            except Exception:
                pass
        self._scoped_log_bridge = None

    #Ã¢â€â‚¬Ã¢â€â‚¬ Proxy helpers Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def _active_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        return self.proxies[self._proxy_index]

    def _rotate_proxy(self):
        if len(self.proxies) > 1:
            self._proxy_index = (self._proxy_index + 1) % len(self.proxies)
            self.progress.emit(f"  Proxy switched to {self._proxy_index + 1}/{len(self.proxies)}")

    # â"€â"€ Cookie sync (Chromium profile -> shared cookies/) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

    def _maybe_sync_profile_cookies(self, platform_key: str, force: bool = False) -> Optional[str]:
        """
        Export fresh Netscape cookies from the persistent browser profile
        via SessionAuthority.  This ensures downstream downloaders get
        the freshest possible auth from the managed browser session.

        When force=True, always re-exports (used at download-phase start
        so that cookies captured during link grabbing are available).
        If the profile is busy (e.g. just closing from link grab), waits
        briefly before retrying once.
        """
        platform_key = (platform_key or "").strip().lower()
        if platform_key not in {"instagram", "tiktok", "youtube", "facebook", "twitter"}:
            return None

        # If we already synced recently in this run, avoid repeating unless forced.
        if not force and platform_key in self._cookie_sync_info:
            return self._cookie_sync_info.get(platform_key) or None

        try:
            from modules.shared.session_authority import AuthFallbackChain
            chain = AuthFallbackChain()

            # If profile is busy (link grabbing just finished), wait briefly
            if force and chain._sa.is_profile_busy():
                self.progress.emit(f"  Managed profile busy, waiting for release...")
                for _ in range(6):  # up to 3 seconds
                    time.sleep(0.5)
                    if not chain._sa.is_profile_busy():
                        break

            creator_name = getattr(self, 'creator_folder', None)
            creator_name = creator_name.name if creator_name else ""
            best_cookie, source_id = chain.resolve_cookie(
                platform_key, creator=creator_name,
            )
            if best_cookie:
                self._cookie_sync_info[platform_key] = best_cookie
                dest_name = Path(best_cookie).name
                self.progress.emit(f"  Cookie sync: {platform_key} -> {dest_name}")
                return best_cookie

            return None
        except Exception as e:
            self.progress.emit(f"  Cookie sync failed for {platform_key}: {str(e)[:100]}")
            return None

    def _export_ix_platform_cookies(self, platform_key: str) -> Optional[str]:
        """Best-effort IXBrowser cookie export for auth fallback chaining."""
        try:
            from .ix_link_grabber import get_ix_session
            ix = get_ix_session()
            if not ix.ensure_session(progress_cb=self.progress.emit):
                return None
            if not ix.check_login(platform_key, progress_cb=self.progress.emit):
                return None
            return ix.export_platform_cookies(platform_key, progress_cb=self.progress.emit)
        except Exception as exc:
            self._terminal_log("IX", f"cookie export failed for {platform_key}: {exc}")
            return None

    def _resolve_auth_ticket(self, platform_key: str, creator_hint: str = "") -> Dict:
        """Build a single shared auth ticket for link grabbing and downloading."""
        try:
            from modules.shared.session_authority import (
                AuthFallbackChain,
                normalize_creator_key,
            )
            creator_name = creator_hint or self.creator_folder.name
            creator_key = normalize_creator_key(
                creator_name,
                platform=platform_key,
                creator_url=self.creator_url,
            )
            ticket = AuthFallbackChain().resolve_ticket(
                platform=platform_key,
                creator=creator_name,
                creator_url=self.creator_url,
                ix_cookie_provider=self._export_ix_platform_cookies,
                progress_callback=self.progress.emit,
            )
            ticket_dict = ticket.to_dict()
            ticket_dict["creator_key"] = creator_key
            return ticket_dict
        except Exception as exc:
            self._terminal_log("Auth", f"resolve_auth_ticket failed: {exc}")
            return {
                "creator_key": str(self.creator_folder.name).lstrip("@").lower(),
                "platform": platform_key,
                "source_id": "",
                "source_kind": "none",
                "cookie_path": None,
                "validated_at": 0.0,
                "auth_strength": "none",
                "candidate_paths": [],
                "can_use_public_fallback": platform_key in {"youtube", "facebook", "instagram", "tiktok"},
            }

    def _record_attempt(
        self,
        *,
        stage: str,
        method_id: str,
        auth_source: str = "",
        result: str = "failed",
        failure_type: str = "",
        links_added: int = 0,
        retry_used: bool = False,
        detail: str = "",
    ) -> None:
        """Append a structured attempt record for later debugging/UI summaries."""
        self._attempt_summary.append(
            {
                "stage": str(stage or ""),
                "method_id": str(method_id or ""),
                "auth_source": str(auth_source or ""),
                "result": str(result or ""),
                "failure_type": str(failure_type or ""),
                "links_added": int(links_added or 0),
                "retry_used": bool(retry_used),
                "detail": str(detail or ""),
            }
        )

    # ── Delete-before-download cleanup ──────────────────────────────────────

    _MEDIA_EXTENSIONS = frozenset({
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv",
        ".m4v", ".mpeg", ".mpg", ".ts", ".3gp",
    })
    _IMAGE_EXTENSIONS = frozenset({
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
    })
    _MIN_MEDIA_SIZE = 10_000
    _TEMP_SKIP_NAMES = frozenset({"history.json"})

    def _scan_media_folder(self, folder: Path) -> List[Path]:
        """Return newest valid media files from a folder tree."""
        found: List[Path] = []
        if not folder.exists():
            return found
        try:
            for item in folder.rglob("*"):
                if not item.is_file():
                    continue
                if item.name in self._TEMP_SKIP_NAMES:
                    continue
                if item.suffix.lower() not in self._MEDIA_EXTENSIONS:
                    continue
                try:
                    if item.stat().st_size < self._MIN_MEDIA_SIZE:
                        continue
                except OSError:
                    continue
                found.append(item)
        except Exception:
            return []
        found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return found

    def _delete_existing_media(self) -> None:
        """Delete existing media files in the creator folder (once per run).

        Only cleans the top-level creator folder.
        Deletes old top-level video files plus non-essential image files.
        Preserves nested folders, configs, text/json files, and image assets
        whose names suggest they are important branding/profile files
        (for example: logo*, *logo*, avatar*).
        """
        folder = self.creator_folder
        if not folder.is_dir():
            return

        self.progress.emit("[Cleanup] Checking top-level media...")
        self._terminal_log("Cleanup", f"scanning top-level folder: {folder}")

        def _should_keep_asset(path: Path) -> bool:
            stem = path.stem.lower()
            name = path.name.lower()
            return (
                "logo" in stem
                or "avatar" in stem
                or name.startswith("logo.")
                or name.startswith("avatar.")
            )

        top_level_names: List[str] = []
        found: List[Path] = []
        kept_assets: List[str] = []
        try:
            for item in folder.iterdir():
                if not item.is_file():
                    continue
                top_level_names.append(item.name)
                if item.name in self._TEMP_SKIP_NAMES:
                    continue
                suffix = item.suffix.lower()
                if suffix in self._MEDIA_EXTENSIONS:
                    if _should_keep_asset(item):
                        kept_assets.append(item.name)
                    else:
                        found.append(item)
                    continue
                if suffix in self._IMAGE_EXTENSIONS:
                    if _should_keep_asset(item):
                        kept_assets.append(item.name)
                    else:
                        found.append(item)
                    continue
                if _should_keep_asset(item):
                    kept_assets.append(item.name)
                    continue
        except Exception as exc:
            self.progress.emit("[Cleanup] Failed to scan old media.")
            self._terminal_log("Cleanup", f"scan failed: {exc}")
            return

        self._terminal_log(
            "Cleanup",
            f"top-level files={len(top_level_names)} delete_candidates={len(found)} keep_assets={len(kept_assets)}",
        )
        for name in top_level_names:
            self._terminal_log("Cleanup", f"top-level file: {name}")
        for name in kept_assets:
            self._terminal_log("Cleanup", f"preserved asset: {name}")
        for fp in found:
            self._terminal_log("Cleanup", f"delete candidate: {fp.name}")

        if not found:
            self.progress.emit("[Cleanup] Nothing to remove.")
            self._terminal_log("Cleanup", "no top-level media needed deletion")
            return

        deleted = 0
        failed = 0
        for fp in found:
            try:
                fp.unlink()
                deleted += 1
                self._terminal_log("Cleanup", f"deleted: {fp.name}")
            except Exception as exc:
                failed += 1
                self._terminal_log("Cleanup", f"FAILED {fp.name}: {exc}")

        if failed:
            self.progress.emit(f"[Cleanup] Removed {deleted} old file(s), {failed} could not be removed.")
        else:
            self.progress.emit(f"[Cleanup] Removed {deleted} old file(s).")

    def _pick_fresh_video_from_folder(self, before_files: set) -> Optional[Path]:
        video_exts = {
            ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".mpeg", ".mpg"
        }
        try:
            fresh = [
                p for p in self.creator_folder.iterdir()
                if p.is_file() and p.suffix.lower() in video_exts and p.name not in before_files
            ]
            if fresh:
                fresh.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return fresh[0]
        except Exception:
            pass
        try:
            all_videos = [
                p for p in self.creator_folder.iterdir()
                if p.is_file() and p.suffix.lower() in video_exts
            ]
            if all_videos:
                all_videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return all_videos[0]
        except Exception:
            pass
        return None

    def _download_single_via_video_downloader(self, url: str, provided_title: str = None) -> Tuple[Optional[Path], str]:
        """
        Reuse Video Downloader module's proven platform-specific strategy for one URL.
        Returns (downloaded_file_path, error_message).
        """
        # Use a temporary folder for downloading to prevent yt-dlp from overwriting 
        # identical titles before we can safely rename them.
        temp_dl_dir = self.creator_folder / ".temp_profile_dl"
        try:
            shutil.rmtree(temp_dl_dir)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        os.makedirs(temp_dl_dir, exist_ok=True)

        def _run_once(opts: Dict) -> Tuple[bool, str, Optional[Path]]:
            result = {"ok": False, "msg": "", "verified_path": None}

            downloader = VideoDownloaderThread(
                urls=[url],
                save_path=str(temp_dl_dir),  # Download to temp!
                options=opts,
                bulk_mode_data=None,
            )
            self._active_downloader = downloader
            def _filter_relay(m):
                self._terminal_log("Downloader", m)
                try:
                    from modules.shared.progress_filter import filter_for_gui
                    filtered = filter_for_gui(m)
                    if filtered is None:
                        return
                    m = filtered
                except ImportError:
                    pass
                self.progress.emit(f"  {m}")
            downloader.progress.connect(_filter_relay)
            downloader.download_speed.connect(self.download_speed.emit)
            downloader.eta.connect(self.eta.emit)
            downloader.progress_percent.connect(self._on_single_video_percent)

            def _on_finished(ok: bool, msg: str):
                result["ok"] = bool(ok) and int(getattr(downloader, "success_count", 0) or 0) > 0
                result["msg"] = str(msg or "").strip()

            downloader.finished.connect(_on_finished)
            downloader.start()

            while downloader.isRunning():
                if self._stop:
                    try:
                        downloader.cancel()
                    except Exception:
                        pass
                    downloader.wait(1500)
                    self._active_downloader = None
                    return False, "Cancelled", None
                time.sleep(0.15)

            downloader.wait(1500)
            self._active_downloader = None

            if not result["ok"] and int(getattr(downloader, "success_count", 0) or 0) > 0:
                result["ok"] = True

            try:
                verified_path = getattr(downloader, "last_verified_output", None) or None
                if verified_path:
                    result["verified_path"] = Path(str(verified_path))
            except Exception:
                result["verified_path"] = None

            reason = result["msg"]
            if not result["ok"] and not reason:
                try:
                    failed_urls = list(getattr(downloader, "failed_urls", []) or [])
                    if failed_urls and isinstance(failed_urls[0], (list, tuple)) and len(failed_urls[0]) >= 2:
                        reason = str(failed_urls[0][1] or "").strip()
                except Exception:
                    pass
            return result["ok"], (reason or ""), result["verified_path"]

        # Use exact options the GUI manual VideoDownloader uses
        creator_name = ""
        try:
            creator_name = self.config.data.get('creator_name') or self.creator_folder.name
        except Exception:
            creator_name = self.creator_folder.name
        current_auth_ticket = dict(getattr(self, "_current_auth_ticket", {}) or {})
        runtime_readiness = dict(getattr(self, "_runtime_readiness", {}) or {})
        robust_opts: Dict = {
            "quality": "HD", # Use exact same string as VideoDownloader dropsdown for YouTube formats
            "skip_recent_window": False,
            "force_all_methods": True,
            "max_retries": 3,
            "rate_limit_delay": 5.0,
            "rate_limit_profile": {"youtube_rate_limit_backoff": 8.0},
            "platform_retry_policy": {
                "auth_refresh_first": True,
                "respect_auth_ticket": True,
            },
            "_creator_hint": creator_name,
            "_expected_media_kind": "video",
            "auth_ticket": current_auth_ticket,
            "cookie_candidates": list(
                current_auth_ticket.get("candidate_paths") or []
            ),
            "cookie_file": current_auth_ticket.get("cookie_path"),
            "strict_auth_ticket": bool(current_auth_ticket),
            "runtime_readiness": runtime_readiness,
        }
        
        ok, reason, verified_path = _run_once(robust_opts)
        self._terminal_log("Downloader", f"_run_once result: ok={ok}, reason='{reason}'")

        temp_media = []
        if verified_path:
            try:
                if verified_path.exists():
                    temp_media = [verified_path]
                    self._terminal_log("Downloader", f"using verified output path: {verified_path.name}")
            except Exception:
                temp_media = []
        if not temp_media:
            temp_media = self._scan_media_folder(temp_dl_dir)
        if ok and not temp_media:
            ok = False
            reason = reason or "Downloader reported success but no output video was found in temp folder"
            self._terminal_log("Downloader", f"normalized success-without-file to failure: {reason}")

        if temp_media:
            fp = temp_media[0]

            if fp:
                # We found the downloaded file in the temp directory!
                # Now safely move it to the creator folder, renaming if title already exists 
                # (e.g., "Video_by_ashkan (1).mp4") so we never overwrite the user's previous videos.
                # ENHANCED: Use provided title if current filename is generic or very short
                safe_name = fp.name
                # Strip Facebook engagement metrics from filename
                # e.g. "7.3K_views_75_reactions_Title..." → "Title..."
                _engagement_re = re.compile(
                    r'^[\d.,]+[KkMm]?_views_[\d.,]+[KkMm]?_reactions?_',
                )
                _stem = Path(safe_name).stem
                _cleaned_stem = _engagement_re.sub('', _stem)
                if _cleaned_stem and _cleaned_stem != _stem:
                    safe_name = _cleaned_stem + Path(safe_name).suffix

                generic_keywords = [
                    "facebook", "instagram", "tiktok", "youtube", "video",
                    "post", "short", "reel"
                ]
                stem_low = fp.stem.lower()
                # If the filename is short (e.g. shortcode DVJGZnWCESp) or contains generic platform names
                is_generic = len(fp.stem) < 15 or any(kw in stem_low for kw in generic_keywords)

                if is_generic:
                    creator_name = self.creator_folder.name.lstrip('@')
                    if provided_title and provided_title.strip():
                        # Use provided title
                        clean_title = re.sub(r'[\\/*?:"<>|]', "", provided_title)
                        clean_title = clean_title.strip()[:100]
                        if clean_title and len(clean_title) > 5:
                            if creator_name.lower() not in clean_title.lower() and len(clean_title) < 60:
                                safe_name = f"{creator_name}_{clean_title}{fp.suffix}"
                            else:
                                safe_name = f"{clean_title}{fp.suffix}"
                    else:
                        # No title available (common for Instagram) — use creator_name + timestamp
                        from datetime import datetime as _dt
                        _ts = _dt.now().strftime("%Y%m%d_%H%M%S")
                        safe_name = f"{creator_name}_{_ts}{fp.suffix}"
                
                safe_name = _build_preferred_download_name(
                    raw_filename=safe_name,
                    provided_title=provided_title or "",
                    creator_name=self.creator_folder.name.lstrip('@'),
                    source_url=url,
                    extension=fp.suffix,
                )
                target_path = self.creator_folder / safe_name
                counter = 1
                while target_path.exists():
                    # If we renamed but there's a collision, add a counter to our new name
                    target_path = self.creator_folder / f"{Path(safe_name).stem} ({counter}){Path(safe_name).suffix}"
                    counter += 1
                
                shutil.move(str(fp), str(target_path))
                
                # Clean up temp folder safely
                try: shutil.rmtree(temp_dl_dir)
                except Exception: pass
                    
                return target_path, ""
                
        try:
            shutil.rmtree(temp_dl_dir)
        except Exception:
            pass

        if reason == "Cancelled":
            return None, reason
            
        self._last_download_error = reason
        return None, (reason or "All downloader methods failed")

    # Ã¢â€â‚¬Ã¢â€â‚¬ Thread entry Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def run(self):
        result = {
            "success": False,
            "downloaded": 0,
            "failed": 0,
            "target": 0,
            "tier_used": None,
            "error": None,
            "status_code": "failed",
            "failure_type": "",
            "stage_failed": "",
            "auth_source_used": "",
            "links_found": 0,
            "download_attempts": 0,
            "anonymous_fallback_used": False,
            "attempt_summary": [],
            "runtime_readiness": {},
        }
        self._install_scoped_log_bridge()
        try:
            self._execute(result)
        except Exception as e:
            import traceback
            result["error"] = str(e)
            self.progress.emit(f"Error: {e}")
            self._terminal_log("Error", f"ERROR in _execute: {e}")
            traceback.print_exc()
            self.config.update_last_activity("failed", "Error", 0)
            self.config.save()
        finally:
            self._remove_scoped_log_bridge()
        # Store result as attribute so queue manager can read it directly
        # (avoids cross-thread signal delivery issues)
        self._result = result
        self.finished.emit(result)

    def _execute(self, result: dict):
        # Ã¢â€â‚¬Ã¢â€â‚¬ Load settings Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        creator_url = self.creator_url
        n_target = self.config.n_videos
        self._n_target = n_target
        self._n_completed = 0
        result["target"] = n_target
        dup_ctrl = self.config.duplication_control
        use_popular_fallback = self.config.popular_fallback
        randomize_links = self.config.randomize_links
        yt_content_type = self.config.yt_content_type
        keep_original = self.config.keep_original_after_edit
        delete_before_dl = self.config.delete_before_download

        if not creator_url:
            self.progress.emit("No creator URL found. Please set the URL in Edit settings.")
            result["error"] = "No creator URL configured"
            self.config.update_last_activity("failed", "No URL", 0)
            self.config.save()
            return

        platform_key = _detect_platform(creator_url)
        self._attempt_summary = []
        try:
            from modules.shared.runtime_readiness import get_runtime_readiness
            self._runtime_readiness = get_runtime_readiness(platform_key)
        except Exception as exc:
            self._runtime_readiness = {
                "ready": False,
                "platform": platform_key,
                "issues": [f"runtime readiness failed: {exc}"],
                "warnings": [],
            }
        result["runtime_readiness"] = dict(self._runtime_readiness or {})
        self._terminal_log(
            "Run",
            (
                f"starting platform={platform_key.upper()} target={n_target} "
                f"duplication_control={dup_ctrl} delete_before_download={delete_before_dl} "
                f"popular_fallback={use_popular_fallback} randomize_links={randomize_links}"
            ),
        )
        self.progress.emit(f"Platform: {platform_key.upper()} | Target: {n_target} videos")
        for warning in self._runtime_readiness.get("warnings", []) or []:
            self.progress.emit(f"Runtime: {warning}")
        if not self._runtime_readiness.get("ready", False):
            runtime_error = "; ".join(self._runtime_readiness.get("issues", []) or [])
            result["error"] = runtime_error or "Runtime readiness failed"
            result["status_code"] = "failed_auth" if "Playwright" in runtime_error else "runtime_unavailable"
            result["failure_type"] = "runtime_missing"
            result["stage_failed"] = "runtime_readiness"
            self._record_attempt(
                stage="runtime_readiness",
                method_id="get_runtime_readiness",
                auth_source="",
                result="failed",
                failure_type="runtime_missing",
                detail=result["error"],
            )
            self.progress.emit(f"Runtime readiness failed: {result['error']}")
            self.config.update_last_activity("failed", "Runtime", 0)
            self.config.save()
            return

        self._current_auth_ticket = self._resolve_auth_ticket(platform_key)
        result["auth_source_used"] = (
            self._current_auth_ticket.get("source_kind")
            or self._current_auth_ticket.get("source_id")
            or ""
        )
        result["anonymous_fallback_used"] = (
            self._current_auth_ticket.get("auth_strength") != "authenticated"
        )
        self.progress.emit(
            "Auth ticket: "
            f"{self._current_auth_ticket.get('source_kind') or 'none'}"
        )
        self._record_attempt(
            stage="auth_ticket",
            method_id="resolve_auth_ticket",
            auth_source=result["auth_source_used"],
            result=(
                "success"
                if self._current_auth_ticket.get("auth_strength") == "authenticated"
                else "fallback"
            ),
            failure_type=(
                ""
                if self._current_auth_ticket.get("auth_strength") == "authenticated"
                else "public_only"
            ),
            detail=str(self._current_auth_ticket.get("cookie_path") or ""),
        )
        self.progress_percent.emit(0)

        # ── Delete-before-download cleanup (once per creator run) ─────────
        if delete_before_dl:
            self._terminal_log("Run", "Delete B4 DL is ON -> cleaning top-level media before selection")
            self._delete_existing_media()

        # Sync cookies from Chromium managed profile for auth-heavy platforms.
        # Force=True because link grabbing may have just finished and we need
        # the freshest possible cookies from the managed browser session.
        synced_cookie = None
        if platform_key in {"instagram", "tiktok", "youtube", "facebook", "twitter"}:
            synced_cookie = self._maybe_sync_profile_cookies(platform_key, force=True)
            if synced_cookie:
                self.progress.emit(f"  Auth: Synced managed profile cookies for {platform_key}")

        downloads: List[Path] = []
        failed_downloads: int = 0
        tier_used = None
        session_ids: set = set()
        attempted_ids: set = set()
        last_error_message = ""
        _pacer = PacingManager(batch_size=10)
        try:
            self.progress.emit(
                f"Pacing profile: {_pacer.user_plan.upper()} ({_pacer.delay_multiplier:.1f}x delays)"
            )
        except Exception:
            pass

        from .selection_policy import normalise_entry, select_videos, _is_supported_video_url

        raw_downloaded_ids: frozenset = frozenset(
            self.config.data.get("downloaded_ids", [])
        ) if dup_ctrl else frozenset()
        self._terminal_log(
            "Selection",
            (
                f"skip_downloaded_active={bool(dup_ctrl)} "
                f"remembered_downloaded_ids={len(raw_downloaded_ids)}"
            ),
        )

        def _key(vid: Dict) -> str:
            return (vid.get("id") or vid.get("url") or "").strip()

        def _entry_id(entry: Dict) -> str:
            url = (entry.get("url") or "").strip()
            return (entry.get("id") or _safe_id_from_url(url) or url).strip()

        def _is_already_downloaded(entry: Dict) -> bool:
            if not dup_ctrl:
                return False
            entry_id = _entry_id(entry)
            return bool(entry_id and entry_id in raw_downloaded_ids)

        def _count_usable_entries(entries: List[Dict]) -> int:
            usable = 0
            for entry in entries or []:
                if not isinstance(entry, dict):
                    continue
                url = (entry.get("url") or "").strip()
                if not url:
                    continue
                if not _is_supported_video_url(url, platform_key):
                    continue
                if _is_already_downloaded(entry):
                    continue
                entry_key = _key(entry) or url
                if entry_key in attempted_ids or entry_key in session_ids:
                    continue
                usable += 1
            return usable

        def _selected_ready_count() -> int:
            return len(selected or [])

        download_queue: List[Dict] = []
        queued_ids: set = set()
        ix_direct_retry_candidates: List[Dict] = []

        def _queue_entries(
            entries: List[Dict],
            label: str,
            supported_only: bool = False,
            skip_downloaded: bool = False,
        ) -> int:
            added = 0
            for entry in entries or []:
                if not isinstance(entry, dict):
                    continue
                url = (entry.get("url") or "").strip()
                if not url:
                    continue
                if supported_only and not _is_supported_video_url(url, platform_key):
                    continue
                if skip_downloaded and _is_already_downloaded(entry):
                    continue
                entry_key = _key(entry) or url
                if entry_key in queued_ids or entry_key in attempted_ids or entry_key in session_ids:
                    continue
                entry_copy = dict(entry)
                if not entry_copy.get("id"):
                    entry_copy["id"] = _safe_id_from_url(url)
                entry_copy["platform"] = platform_key
                entry_copy["creator"] = entry_copy.get("creator") or self.creator_folder.name
                entry_copy["_download_tier"] = entry_copy.get("_download_tier") or label
                download_queue.append(entry_copy)
                queued_ids.add(entry_key)
                added += 1
            return added

        def _download_entries(
            entries: List[Dict],
            label: str,
            allow_ix_retry: bool = False,
            retry_entries: bool = False,
            collect_retry_candidates: Optional[List[Dict]] = None,
        ):
            nonlocal tier_used, last_error_message, failed_downloads
            for vid in entries:
                # Check pause between videos
                if self._check_pause():
                    return
                if len(downloads) >= n_target:
                    return

                url = vid.get("url", "")
                if not url:
                    vid_id = vid.get("id", "?")
                    self._terminal_log("Download", f"skipping entry with no URL (id={vid_id})")
                    continue
                entry_key = _key(vid)
                if not entry_key:
                    entry_key = url.strip()
                if not retry_entries and entry_key in attempted_ids:
                    continue

                entry_label = vid.get("_download_tier") or label
                self.progress.emit(f"{entry_label} download ({len(downloads)+1}/{n_target}): {url[:80]}")
                title = vid.get("title")
                download_url = (
                    _normalize_youtube_download_url(url)
                    if platform_key == "youtube"
                    else url
                )
                result["download_attempts"] = int(result.get("download_attempts", 0) or 0) + 1
                
                self._terminal_log("Download", f"attempting: {url[:80]}")
                if download_url != url:
                    self._terminal_log(
                        "Download",
                        f"normalized youtube url for downloader: {download_url[:80]}",
                    )
                
                # IX session refresh is reserved for the explicit IX fallback stage.
                if allow_ix_retry:
                    try:
                        from modules.creator_profiles.ix_link_grabber import get_ix_session
                        ix_session = get_ix_session()
                        if ix_session.ensure_session(progress_cb=self.progress.emit):
                            self._maybe_sync_profile_cookies(platform_key, force=True)
                            refreshed_ticket = self._resolve_auth_ticket(
                                platform_key,
                                creator_hint=vid.get("creator", self.creator_folder.name),
                            )
                            if refreshed_ticket:
                                self._current_auth_ticket = refreshed_ticket
                                result["auth_source_used"] = (
                                    refreshed_ticket.get("source_kind")
                                    or refreshed_ticket.get("source_id")
                                    or result.get("auth_source_used", "")
                                )
                    except ImportError:
                        pass

                fp, dl_error = self._download_single_via_video_downloader(download_url, title)

                # Active Retry Strategy against Bot Blocks
                if not fp and allow_ix_retry:
                    err_l = (dl_error or "").lower()
                    if any(x in err_l for x in ("sign in", "login", "private", "extract", "empty", "forbidden", "403")):
                        self.progress.emit(f"  [IX Retry] Bot block detected. Refreshing IXBrowser session...")
                        try:
                            from modules.creator_profiles.ix_link_grabber import get_ix_session
                            ix_session = get_ix_session()
                            if ix_session.ensure_session(progress_cb=self.progress.emit):
                                # Ask IXBrowser to literally navigate to the site to refresh cookies
                                ix_session.check_login(platform_key, progress_cb=self.progress.emit)
                                ix_session.maximize_browser(progress_cb=self.progress.emit)
                                self._maybe_sync_profile_cookies(platform_key, force=True)
                                self.progress.emit(f"  [IX Retry] Retrying download with fresh cookies...")
                                time.sleep(2.0) # brief pause
                                fp, dl_error = self._download_single_via_video_downloader(download_url, title)
                        except Exception as e:
                            self.progress.emit(f"  [IX Retry] Failed to refresh session: {e}")

                attempted_ids.add(entry_key)
                if not fp:
                    failed_downloads += 1
                    err = (dl_error or "download failed").strip()
                    last_error_message = err
                    attempt_failure_type = ""
                    result["stage_failed"] = result.get("stage_failed") or "download"
                    if not result.get("failure_type"):
                        try:
                            from modules.shared.failure_classifier import classify_failure
                            attempt_failure_type = classify_failure(err, platform_key).name.lower()
                            result["failure_type"] = attempt_failure_type
                        except Exception:
                            result["failure_type"] = "download_failed"
                    if not attempt_failure_type:
                        attempt_failure_type = str(result.get("failure_type") or "download_failed")
                    self._record_attempt(
                        stage="download",
                        method_id=str(entry_label or label).strip().lower().replace(" ", "_"),
                        auth_source=result.get("auth_source_used", ""),
                        result="failed",
                        failure_type=attempt_failure_type,
                        retry_used=bool(allow_ix_retry or retry_entries),
                        detail=url[:240],
                    )
                    if collect_retry_candidates is not None:
                        retry_copy = dict(vid)
                        retry_copy["_download_tier"] = "IX Direct Retry"
                        collect_retry_candidates.append(retry_copy)
                    msg = f"  Failed ({failed_downloads}): {url[:60]} | {err[:120]}"
                    self.progress.emit(msg)
                    print(f"[CreatorProfile] {msg}")
                    # Failure pacing: avoid burst retries against the same platform.
                    if len(downloads) < n_target:
                        wait_s = _pacer.pace_after_failure()
                        self.progress.emit(f"Cooldown: {wait_s:.1f}s before next attempt...")
                    continue

                downloads.append(fp)
                self._n_completed = len(downloads)
                self.progress_percent.emit(int((self._n_completed / self._n_target) * 100))
                msg_success = f"[CreatorProfile] Successfully downloaded to: {fp.absolute()}"
                print(msg_success)
                vid_id = vid.get("id") or _safe_id_from_url(url)
                if vid_id:
                    self.config.add_downloaded_id(vid_id)
                    self.config.save()  # persist immediately so concurrent workers see this ID
                self.config.add_url_to_history(
                    url, platform=platform_key,
                    creator=vid.get("creator", self.creator_folder.name),
                )
                session_ids.add(_key(vid))
                tier_used = entry_label
                self.config.append_activity_event(
                    "download_completed",
                    {"video_id": vid_id, "title": vid.get("title", ""), "tier": entry_label},
                )
                self._record_attempt(
                    stage="download",
                    method_id=str(entry_label or label).strip().lower().replace(" ", "_"),
                    auth_source=result.get("auth_source_used", ""),
                    result="success",
                    links_added=1,
                    retry_used=bool(allow_ix_retry or retry_entries),
                    detail=url[:240],
                )
                self.progress.emit(f"Progress: {len(downloads)}/{n_target}")

                # Pacing: 2-4s between operations + batch cooldown every ~10
                if len(downloads) < n_target:
                    _pacer.pace_operation()

        if self._check_pause():
            return

        latest_entries = []
        creator_name = ""
        annotated: List[Dict] = []
        selected: List[Dict] = []
        debug_log: List[Dict] = []
        ix_annotated: List[Dict] = []
        late_history_candidates: List[Dict] = []

        def _entry_pool_key(ent: Dict) -> str:
            url_value = (ent.get("url") or "").strip()
            entry_id = (ent.get("id") or _safe_id_from_url(url_value)).strip()
            if entry_id:
                return f"id:{entry_id.lower()}"
            return f"url:{url_value.lower()}"

        def _merge_latest_entries(new_entries: List[Dict], source_label: str) -> int:
            nonlocal latest_entries
            seen_keys = {
                _entry_pool_key(e)
                for e in latest_entries
                if isinstance(e, dict) and e.get("url")
            }
            added = 0
            for entry in new_entries or []:
                if not isinstance(entry, dict):
                    continue
                if not entry.get("url"):
                    continue
                pool_key = _entry_pool_key(entry)
                if pool_key in seen_keys:
                    continue
                seen_keys.add(pool_key)
                latest_entries.append(entry)
                added += 1
            self._terminal_log(
                "LinkGrab",
                f"{source_label}: merged {added} new link(s), pool now {len(latest_entries)}",
            )
            return added

        def _refresh_selection_state(stage_label: str) -> int:
            nonlocal annotated, selected, debug_log
            for entry in latest_entries:
                if not isinstance(entry, dict):
                    continue
                if not entry.get("id"):
                    entry["id"] = _safe_id_from_url(entry.get("url", ""))
                entry["platform"] = platform_key
                entry["creator"] = creator_name or self.creator_folder.name

            annotated = [
                normalise_entry(entry)
                for entry in latest_entries
                if isinstance(entry, dict) and entry.get("url")
            ]
            dropped = len(latest_entries) - len(annotated)
            if dropped > 0:
                self._terminal_log(
                    "Selection",
                    f"{stage_label}: dropped {dropped}/{len(latest_entries)} entries (missing URL or invalid)",
                )
                self.progress.emit(f"Warning: {dropped} link(s) dropped (missing URL)")

            selected, debug_log = select_videos(
                entries=annotated,
                n_videos=n_target,
                skip_downloaded=dup_ctrl,
                popular_enabled=use_popular_fallback,
                random_enabled=randomize_links,
                already_downloaded=raw_downloaded_ids,
                platform=platform_key,
                yt_content_type=yt_content_type,
            )
            selected = [
                entry for entry in selected
                if (_key(entry) not in session_ids and _key(entry) not in attempted_ids)
            ]
            usable_count = _count_usable_entries(annotated)
            selected_count = len(selected)
            self._terminal_log(
                "Selection",
                (
                    f"{stage_label}: annotated={len(annotated)} "
                    f"selected={selected_count}/{n_target} usable={usable_count}/{n_target}"
                ),
            )
            return selected_count

        legacy_page_batch = max(10, n_target * 2)
        legacy_first_pass_fetch_count = max(8, n_target + 4)
        if dup_ctrl:
            legacy_first_pass_fetch_count += max(2, n_target)
        if use_popular_fallback or randomize_links:
            legacy_first_pass_fetch_count += 2
        legacy_first_pass_scroll_attempts = 3
        legacy_max_rounds = 5

        try:
            from modules.link_grabber.core import extract_links_intelligent
            from modules.config.paths import get_cookies_dir
        except Exception as e:
            extract_links_intelligent = None
            get_cookies_dir = None
            msg = f"Link grabber import failed: {e}"
            self.progress.emit(msg)
            self._terminal_log("LinkGrab", msg)
            last_error_message = msg

        def _run_legacy_extract(
            source_url: str,
            fetch_count: int,
            stage_label: str,
            browser_max_scroll_attempts: Optional[int] = None,
        ) -> int:
            nonlocal creator_name, last_error_message, legacy_page_batch
            if extract_links_intelligent is None or get_cookies_dir is None:
                return 0

            grab_opts = {
                "max_videos": fetch_count,
                "force_all_methods": False,
                "respect_global_exhaustive_mode": False,
                "fast_mode": False,
                "managed_profile_only": True,
                "interactive_login_fallback": False,
                "yt_content_type": yt_content_type,
                "auth_ticket": dict(self._current_auth_ticket or {}),
                "include_meta": True,
            }
            source_lower = (source_url or "").lower()
            if _is_profile_listing_url(platform_key, source_url):
                # Creator-profile listings across platforms can under-fill on the
                # first successful method. Keep scanning until the pool is truly
                # exhausted instead of trusting one weak profile pass.
                grab_opts["force_all_methods"] = True
            if browser_max_scroll_attempts is not None:
                grab_opts["browser_max_scroll_attempts"] = browser_max_scroll_attempts

            if stage_label == "Legacy" and browser_max_scroll_attempts is not None:
                request_detail = f"running page-driven first-pass scan (buffer={fetch_count})"
            elif fetch_count > 0:
                request_detail = f"requesting up to {fetch_count} links"
            else:
                request_detail = "running page-driven first-pass scan"
            if browser_max_scroll_attempts is not None:
                request_detail = (
                    f"{request_detail} "
                    f"(scroll rounds={browser_max_scroll_attempts})"
                )
            self._terminal_log("LinkGrab", f"{stage_label}: {request_detail} from {source_url}")

            try:
                extracted_data = extract_links_intelligent(
                    url=source_url,
                    platform_key=platform_key,
                    options=grab_opts,
                    cookies_dir=get_cookies_dir(),
                    progress_callback=self.progress.emit,
                )
                extracted_entries = extracted_data[0] if isinstance(extracted_data, tuple) else extracted_data
                extracted_creator_name = (
                    extracted_data[1]
                    if isinstance(extracted_data, tuple) and len(extracted_data) > 1
                    else ""
                )
                extracted_meta = (
                    extracted_data[2]
                    if isinstance(extracted_data, tuple)
                    and len(extracted_data) > 2
                    and isinstance(extracted_data[2], dict)
                    else {}
                )
                if extracted_meta:
                    self._attempt_summary.extend(extracted_meta.get("attempt_reports", []) or [])
                    refreshed_ticket = extracted_meta.get("auth_ticket") or {}
                    if refreshed_ticket:
                        self._current_auth_ticket = dict(refreshed_ticket)
                        result["auth_source_used"] = (
                            self._current_auth_ticket.get("source_kind")
                            or self._current_auth_ticket.get("source_id")
                            or result.get("auth_source_used", "")
                        )
                        result["anonymous_fallback_used"] = (
                            self._current_auth_ticket.get("auth_strength") != "authenticated"
                        )
                    if not extracted_entries:
                        result["stage_failed"] = extracted_meta.get("stage_failed") or result.get("stage_failed", "")
                        result["failure_type"] = extracted_meta.get("failure_type") or result.get("failure_type", "")
                if extracted_creator_name:
                    creator_name = extracted_creator_name
                added = _merge_latest_entries(extracted_entries, stage_label)
                result["links_found"] = len(latest_entries)
                if added > 0:
                    legacy_page_batch = max(legacy_page_batch, added)
                selected_count = _refresh_selection_state(stage_label)
                usable_count = _count_usable_entries(annotated)
                self._terminal_log(
                    "LinkGrab",
                    (
                        f"{stage_label}: extracted={len(extracted_entries or [])} "
                        f"added={added} pool={len(latest_entries)} "
                        f"selected={selected_count}/{n_target} usable={usable_count}/{n_target}"
                    ),
                )
                return selected_count
            except Exception as e:
                msg = f"{stage_label} failed: {e}"
                self.progress.emit(msg)
                self._terminal_log("LinkGrab", msg)
                last_error_message = msg
                return _selected_ready_count()

        def _expand_legacy_pool(source_url: str, stage_label: str, start_round: int, total_rounds: int) -> int:
            total_added = 0
            stale_rounds = 0
            for round_idx in range(start_round, total_rounds):
                if self._check_pause():
                    return total_added
                if _selected_ready_count() >= n_target:
                    break
                fetch_count = max(
                    len(latest_entries) + legacy_page_batch,
                    legacy_page_batch * (round_idx + 1),
                )
                self.progress.emit(
                    f"{stage_label}: expanding link pool to {fetch_count} candidate link(s)..."
                )
                prev_pool_size = len(latest_entries)
                _run_legacy_extract(
                    source_url=source_url,
                    fetch_count=fetch_count,
                    stage_label=f"{stage_label} R{round_idx + 1}",
                )
                added_now = max(0, len(latest_entries) - prev_pool_size)
                total_added += added_now
                if _selected_ready_count() >= n_target:
                    break
                if added_now <= 0:
                    stale_rounds += 1
                    if stale_rounds >= 2:
                        break
                else:
                    stale_rounds = 0
            return total_added

        # ── Approach 1: Playwright + Intelligent Link Grabber (Primary) ─────────
        self.progress.emit("Fetching latest videos from profile using robust Link Grabber...")

        if extract_links_intelligent is not None and get_cookies_dir is not None:
            _run_legacy_extract(
                source_url=creator_url,
                fetch_count=legacy_first_pass_fetch_count,
                stage_label="Legacy",
                browser_max_scroll_attempts=legacy_first_pass_scroll_attempts,
            )
            if _selected_ready_count() < n_target:
                _expand_legacy_pool(
                    source_url=creator_url,
                    stage_label="Legacy",
                    start_round=1,
                    total_rounds=legacy_max_rounds,
                )

        # ── Approach 2: IXBrowser Fallback ───────────────────────────────────────
        if False and ENABLE_IXBROWSER_FALLBACK and not latest_entries:  # legacy IX hook kept disabled; fallback runs after legacy queue
            self.progress.emit("[IX] Primary grabber found 0 links. Falling back to IXBrowser approach...")
            print(f"[CreatorProfile] IXBrowser fallback for {creator_url} on {platform_key}")

            try:
                from .ix_link_grabber import get_ix_session

                ix = get_ix_session()

                # Step 1: Ensure IXBrowser session is open
                if not ix.ensure_session(progress_cb=self.progress.emit):
                    result["error"] = "IXBrowser session failed — is IXBrowser running?"
                    self.progress.emit(result["error"])
                    self.config.update_last_activity("failed", "IX Error", 0)
                    self.config.save()
                    return

                # Step 2: Check login for this platform (Note: Homepage navigation is skipped now)
                if not ix.check_login(platform_key, progress_cb=self.progress.emit):
                    msg = (
                        f"Not logged in to {platform_key.upper()} in IXBrowser! "
                        f"Please login in the 'onesoul' profile first."
                    )
                    self.progress.emit(f"[IX] {msg}")
                    self.login_required.emit(platform_key)
                    result["error"] = msg
                    self.config.update_last_activity("failed", "Login Required", 0)
                    self.config.save()
                    return

                # Step 3: Maximize browser for better visibility and loading
                ix.maximize_browser(progress_cb=self.progress.emit)

                # Step 4: Extract links directly from creator profile
                fetch_count = n_target * 2 if use_popular_fallback else n_target + 5
                latest_entries, ix_creator_name = ix.extract_links(
                    creator_url=creator_url,
                    platform_key=platform_key,
                    max_videos=fetch_count,
                    yt_content_type=yt_content_type,
                    progress_cb=self.progress.emit,
                )
                if ix_creator_name:
                    creator_name = ix_creator_name
                    
                print(f"[CreatorProfile] IX extracted {len(latest_entries)} links for '{creator_name}'")

                # Step 5: Minimize browser after extraction is done
                ix.minimize_browser(progress_cb=self.progress.emit)

            except Exception as e:
                msg = f"IXBrowser extraction failed: {e}"
                self.progress.emit(msg)
                print(f"[CreatorProfile] Error: {msg}")
                import traceback
                traceback.print_exc()
                last_error_message = msg
            try:
                from modules.link_grabber.core import extract_links_intelligent
                from modules.config.paths import get_cookies_dir

                grab_opts = {
                    "max_videos": n_target * 2 if use_popular_fallback else n_target + 5,
                    "force_all_methods": True,
                    "fast_mode": False,
                    # CreatorProfile pipeline should use ONLY app-managed auth/session.
                    # Do not scan/launch local Chrome/Edge user profiles.
                    "managed_profile_only": True,
                    "interactive_login_fallback": False,
                    "yt_content_type": yt_content_type,
                }

                print(f"[CreatorProfile] Starting intelligent link grab for {creator_url} on {platform_key}")

                extracted_data = extract_links_intelligent(
                    url=creator_url,
                    platform_key=platform_key,
                    cookies_dir=get_cookies_dir(),
                    options=grab_opts,
                    progress_callback=self.progress.emit,
                )

                latest_entries = extracted_data[0] if isinstance(extracted_data, tuple) else extracted_data
                creator_name = extracted_data[1] if isinstance(extracted_data, tuple) and len(extracted_data) > 1 else ""
                print(f"[CreatorProfile] Found {len(latest_entries)} links for creator '{creator_name}'")

            except Exception as e:
                msg = f"Failed to extract links intelligently: {e}"
                self.progress.emit(msg)
                print(f"[CreatorProfile] Error: {msg}")
                latest_entries = []
                last_error_message = msg

        # ── Links-extracted continue rule ─────────────────────────────
        # [NoPopupPolicy] If extraction returned ANY links, clear any
        # cooldown that was recorded during this session so:
        #   a) selection + download proceeds (not aborted)
        #   b) no browser popup is triggered by cooldown/challenge
        #   c) future runs are not blocked by a transient challenge
        if latest_entries:
            try:
                from modules.link_grabber.browser_auth import ChromiumAuthManager

                _auth = ChromiumAuthManager()
                _cd_reason = _auth.is_in_cooldown(platform_key)
                if _cd_reason:
                    _auth.clear_cooldown(platform_key)
                    logging.info(
                        "[ContinueRule][NoPopupPolicy] Cleared cooldown for %s "
                        "— %d links already extracted (reason was: %s)",
                        platform_key, len(latest_entries), _cd_reason,
                    )
                    if platform_key == "tiktok":
                        logging.info(
                            "[TikTokPath] Cooldown cleared — proceeding with "
                            "%d links, no browser popup", len(latest_entries),
                        )
                    self.progress.emit(
                        f"Continuing: {len(latest_entries)} links extracted."
                    )
            except ImportError:
                pass
            except Exception as _cr_err:
                logging.debug("[ContinueRule] check failed: %s", _cr_err)

        # ── Annotate: enrich entries with normalised fields ────────────
        from .selection_policy import normalise_entry, select_videos, _is_supported_video_url

        for e in latest_entries:
            if not isinstance(e, dict):
                continue
            if not e.get("id"):
                e["id"] = _safe_id_from_url(e.get("url", ""))
            e["platform"] = platform_key
            e["creator"] = creator_name or self.creator_folder.name

        annotated = [normalise_entry(e) for e in latest_entries if isinstance(e, dict) and e.get("url")]
        dropped = len(latest_entries) - len(annotated)
        if dropped > 0:
            self._terminal_log(
                "Selection",
                f"dropped {dropped}/{len(latest_entries)} entries (missing URL or invalid)",
            )
            self.progress.emit(f"Warning: {dropped} link(s) dropped (missing URL)")
        self._terminal_log("Selection", f"annotated entries ready: {len(annotated)}")

        # ── Select: apply user preference logic BEFORE downloader ─────
        raw_downloaded_ids = frozenset(self.config.data.get("downloaded_ids", []))
        effective_skip_downloaded = bool(dup_ctrl)
        already_downloaded: frozenset = raw_downloaded_ids

        selected, debug_log = select_videos(
            entries=annotated,
            n_videos=n_target,
            skip_downloaded=effective_skip_downloaded,
            popular_enabled=use_popular_fallback,
            random_enabled=randomize_links,
            already_downloaded=already_downloaded,
            platform=platform_key,
            yt_content_type=yt_content_type,
        )

        # Social backfill (Facebook/Instagram): if usable unique links are still
        # short after the primary pool, expand from the reels/videos tab too.
        if (
            platform_key in {"facebook", "instagram"}
            and _selected_ready_count() < n_target
        ):
            if platform_key == "facebook":
                backfill_sources = _facebook_backfill_sources(creator_url)
            else:
                backfill_sources = [("reels", _instagram_backfill_url(creator_url))]

            need_more = max(1, n_target - _selected_ready_count())
            self.progress.emit(
                f"{platform_key.title()} backfill: need {need_more} more matching link(s)."
            )

            for backfill_kind, backfill_url in backfill_sources:
                if _selected_ready_count() >= n_target:
                    break
                if not backfill_url:
                    continue
                stage_label = f"{platform_key.title()} backfill {backfill_kind}".strip()
                backfill_added = _expand_legacy_pool(
                    source_url=backfill_url,
                    stage_label=stage_label,
                    start_round=0,
                    total_rounds=3,
                )
                debug_log.append({
                    "action": f"{platform_key}_backfill",
                    "kind": backfill_kind,
                    "added": backfill_added,
                    "backfill_url": backfill_url[:120],
                })

        # Remove session-already-attempted duplicates
        selected = [
            e for e in selected
            if (_key(e) not in session_ids and _key(e) not in attempted_ids)
        ]

        for d in debug_log:
            self._terminal_log("SelectionDebug", json.dumps(d, ensure_ascii=False))

        self._terminal_log(
            "Selection",
            f"selected={len(selected)}/{n_target} from annotated={len(annotated)}",
        )

        # ── Fallback 1: Duplicate fallback ────────────────────────────
        # When skip_downloaded removed all candidates, pick a random
        # duplicate so repeated runs cycle through different videos.
        if False and not selected and annotated and effective_skip_downloaded:
            supported_annotated = [
                e for e in annotated
                if _is_supported_video_url(e.get("url", ""), platform_key)
            ]
            logging.info(
                "[SelectionFallback] skip_downloaded emptied selection "
                "(%d annotated, %d supported) — picking random duplicate",
                len(annotated), len(supported_annotated),
            )
            # Filter out session-attempted, then pick randomly
            eligible = [
                e for e in supported_annotated
                if _key(e) not in session_ids and _key(e) not in attempted_ids
            ]
            if eligible:
                candidate = random.choice(eligible)
                candidate["_selection_reason"] = "duplicate_fallback"
                selected = [candidate]
                debug_log.append({"action": "duplicate_fallback", "url": candidate.get("url", "")[:80]})
                self.progress.emit("All videos already downloaded — re-downloading random as fallback.")
                self._terminal_log("SelectionFallback", f"picked duplicate: {candidate.get('url', '')[:80]}")

        # ── Fallback 2: History fallback ──────────────────────────────
        # When extraction returned 0 links OR only unsupported links,
        # try up to 3 random URLs from persisted download history.
        history_candidates: List[Dict] = []
        annotated_has_supported = any(
            _is_supported_video_url(e.get("url", ""), platform_key) for e in annotated
        ) if annotated else False
        if False and not selected and (not annotated or not annotated_has_supported):  # history now runs after legacy + IX stages
            url_history = self.config.get_url_history()
            if url_history:
                # Filter to same platform, exclude session-attempted
                platform_history = [
                    h for h in url_history
                    if h.get("platform", "").lower() == platform_key
                    and h.get("url", "").strip() not in attempted_ids
                    and h.get("url", "").strip() not in session_ids
                ]
                if platform_history:
                    history_candidates = [
                        {
                            "url": h["url"],
                            "id": _safe_id_from_url(h["url"]),
                            "platform": platform_key,
                            "creator": h.get("creator", self.creator_folder.name),
                            "_selection_reason": "history_fallback",
                            "_download_tier": "History",
                        }
                        for h in platform_history
                    ]
                    random.shuffle(history_candidates)
                    sample_count = min(3, len(history_candidates), n_target)
                    history_sample = history_candidates[:sample_count]
                    selected = []
                    for h in history_sample:
                        selected.append(dict(h))
                    debug_log.append({
                        "action": "history_fallback",
                        "count": len(selected),
                        "history_pool": len(platform_history),
                    })
                    self.progress.emit(
                        f"No fresh links — trying {len(selected)} from download history."
                    )
                    logging.info(
                        "[HistoryFallback] Extraction returned 0 links. "
                        "Picked %d from %d history entries for %s",
                        len(selected), len(platform_history), platform_key,
                    )

        if selected:
            self.progress.emit(f"Selected {len(selected)} videos. Preparing downloads...")
            # Stagger between link-grab phase and download phase to reduce rush.
            pre_download_wait = _pacer.scale_delay(random.uniform(1.5, 3.5))
            time.sleep(pre_download_wait)
            self.progress.emit(
                f"Selected {len(selected)} videos. Starting downloads (after {pre_download_wait:.1f}s)..."
            )

        # ── Download: final pre-filtered URLs only ────────────────────
        selected_count = _queue_entries(selected, "Selected", skip_downloaded=dup_ctrl)
        backup_count = _queue_entries(
            annotated,
            "Backup",
            supported_only=True,
            skip_downloaded=dup_ctrl,
        )
        if history_candidates:
            backup_count += _queue_entries(
                history_candidates,
                "History",
                skip_downloaded=dup_ctrl,
            )

        self._terminal_log(
            "Queue",
            (
                f"selected_count={selected_count} backup_count={backup_count} "
                f"queued_total={len(download_queue)} downloads_done={len(downloads)}/{n_target}"
            ),
        )

        if not selected_count and download_queue:
            self.progress.emit(f"No primary selection available. Trying {len(download_queue)} backup link(s).")
        elif backup_count:
            self.progress.emit(
                f"Download queue ready: {selected_count} selected + {backup_count} backup link(s)."
            )

        _download_entries(
            download_queue,
            "Selected",
            allow_ix_retry=False,
            collect_retry_candidates=ix_direct_retry_candidates,
        )

        # IXBrowser is a fallback stage only. We try it after the legacy
        # link-grabbing + downloading queue has already been attempted.
        if ENABLE_IXBROWSER_FALLBACK and len(downloads) < n_target:
            remaining_needed = max(1, n_target - len(downloads))
            self._terminal_log(
                "IX",
                f"entering fallback because legacy delivered {len(downloads)}/{n_target}; remaining_needed={remaining_needed}",
            )
            self.progress.emit(
                f"[IX] Legacy flow delivered {len(downloads)}/{n_target}. Trying IXBrowser fallback..."
            )

            ix_entries: List[Dict] = []
            ix_creator_name = creator_name or self.creator_folder.name
            ix = None
            ix_error_message = ""

            try:
                from .ix_link_grabber import get_ix_session

                ix = get_ix_session()
                if not ix.ensure_session(progress_cb=self.progress.emit):
                    raise RuntimeError("IXBrowser session failed")
                if not ix.check_login(platform_key, progress_cb=self.progress.emit):
                    self.login_required.emit(platform_key)
                    raise RuntimeError(
                        f"Not logged in to {platform_key.upper()} in IXBrowser"
                    )
                result["auth_source_used"] = "ix_browser"

                ix.maximize_browser(progress_cb=self.progress.emit)

                if (
                    platform_key == "youtube"
                    and ix_direct_retry_candidates
                    and len(downloads) < n_target
                ):
                    same_url_retry_count = min(len(ix_direct_retry_candidates), remaining_needed)
                    self._terminal_log(
                        "IX",
                        f"retrying same selected/backup urls before fresh extraction: {same_url_retry_count}",
                    )
                    self.progress.emit(
                        f"[IX] Retrying {same_url_retry_count} previously selected link(s) with IXBrowser session..."
                    )
                    _download_entries(
                        ix_direct_retry_candidates[:same_url_retry_count],
                        "IX Direct Retry",
                        allow_ix_retry=True,
                        retry_entries=True,
                    )

                if len(downloads) < n_target:
                    fetch_count = (
                        remaining_needed * 2 if use_popular_fallback else remaining_needed + 5
                    )
                    ix_youtube_view = _infer_youtube_ix_view(
                        yt_content_type,
                        [
                            *(e.get("url", "") for e in selected if isinstance(e, dict)),
                            *(e.get("url", "") for e in annotated if isinstance(e, dict)),
                            *(e.get("url", "") for e in latest_entries if isinstance(e, dict)),
                        ],
                    )
                    if platform_key == "youtube":
                        self._terminal_log("IX", f"youtube view selected: {ix_youtube_view}")
                    ix_entries, extracted_ix_creator_name = ix.extract_links(
                        creator_url=creator_url,
                        platform_key=platform_key,
                        max_videos=fetch_count,
                        yt_content_type=ix_youtube_view,
                        progress_cb=self.progress.emit,
                    )
                    if extracted_ix_creator_name:
                        ix_creator_name = extracted_ix_creator_name
                    self._terminal_log("IX", f"extracted {len(ix_entries)} links for '{ix_creator_name}'")
                else:
                    self.progress.emit("[IX] Same-link retry succeeded. Skipping fresh IX link grabbing.")
            except Exception as e:
                ix_error = f"IXBrowser fallback failed: {e}"
                ix_error_message = str(e)
                self.progress.emit(ix_error)
                self._terminal_log("IX", f"error: {ix_error}")
                last_error_message = ix_error
                ix_entries = []
            finally:
                if ix:
                    try:
                        ix.minimize_browser(progress_cb=self.progress.emit)
                    except Exception:
                        pass

            for e in ix_entries:
                if not isinstance(e, dict):
                    continue
                if not e.get("id"):
                    e["id"] = _safe_id_from_url(e.get("url", ""))
                e["platform"] = platform_key
                e["creator"] = ix_creator_name or self.creator_folder.name

            ix_annotated = [
                normalise_entry(e)
                for e in ix_entries
                if isinstance(e, dict) and e.get("url")
            ]
            ix_selected, ix_debug_log = select_videos(
                entries=ix_annotated,
                n_videos=remaining_needed,
                skip_downloaded=effective_skip_downloaded,
                popular_enabled=use_popular_fallback,
                random_enabled=randomize_links,
                already_downloaded=already_downloaded,
                platform=platform_key,
                yt_content_type=yt_content_type,
            )
            ix_selected = [
                e for e in ix_selected
                if (_key(e) not in session_ids and _key(e) not in attempted_ids)
            ]

            if False and not ix_selected and ix_annotated and effective_skip_downloaded:
                ix_supported = [
                    e for e in ix_annotated
                    if _is_supported_video_url(e.get("url", ""), platform_key)
                ]
                ix_eligible = [
                    e for e in ix_supported
                    if _key(e) not in session_ids and _key(e) not in attempted_ids
                ]
                if ix_eligible:
                    candidate = random.choice(ix_eligible)
                    candidate["_selection_reason"] = "duplicate_fallback"
                    ix_selected = [candidate]
                    ix_debug_log.append({
                        "action": "ix_duplicate_fallback",
                        "url": candidate.get("url", "")[:80],
                    })
                    self.progress.emit("[IX] Using random duplicate because fresh IX links were exhausted.")

            for d in ix_debug_log:
                self._terminal_log("SelectionDebugIX", json.dumps(d, ensure_ascii=False))

            ix_queue_start = len(download_queue)
            ix_selected_count = _queue_entries(
                ix_selected,
                "IX Selected",
                skip_downloaded=dup_ctrl,
            )
            ix_backup_count = _queue_entries(
                ix_annotated,
                "IX Backup",
                supported_only=True,
                skip_downloaded=dup_ctrl,
            )
            self._terminal_log(
                "IX",
                f"selected_count={ix_selected_count} backup_count={ix_backup_count} extracted={len(ix_annotated)}",
            )
            self._record_attempt(
                stage="ix_extraction",
                method_id="ix_browser",
                auth_source="ix_browser",
                result="success" if ix_selected_count or ix_backup_count else "failed",
                failure_type="" if ix_selected_count or ix_backup_count else (ix_error_message or "no_links"),
                links_added=len(ix_annotated),
                retry_used=False,
                detail=creator_url[:240],
            )
            if ix_selected_count or ix_backup_count:
                self.progress.emit(
                    f"[IX] Queue ready: {ix_selected_count} selected + {ix_backup_count} backup link(s)."
                )
                _download_entries(
                    download_queue[ix_queue_start:],
                    "IX",
                    allow_ix_retry=True,
                )
            else:
                self.progress.emit("[IX] Fallback did not add any usable links.")

        # ── Instaloader Fallback (Instagram only) ─────────────────────────────
        # yt-dlp's instagram:user extractor is officially broken.
        # instaloader is the purpose-built library for Instagram profile scraping.
        if platform_key == "instagram" and len(downloads) < n_target:
            remaining_needed = max(1, n_target - len(downloads))
            self._terminal_log(
                "Instaloader",
                f"entering fallback because total delivered={len(downloads)}/{n_target}; remaining_needed={remaining_needed}",
            )
            try:
                from .instaloader_grabber import grab_instagram_links_instaloader, is_session_available
                if is_session_available():
                    il_raw = grab_instagram_links_instaloader(
                        profile_url=creator_url,
                        max_videos=remaining_needed + 5,
                        progress_cb=self.progress.emit,
                    )
                    if il_raw:
                        for e in il_raw:
                            if not e.get("id"):
                                e["id"] = _safe_id_from_url(e.get("url", ""))
                            e.setdefault("platform", platform_key)
                            e.setdefault("creator", creator_name or self.creator_folder.name)
                        il_annotated = [
                            normalise_entry(e)
                            for e in il_raw
                            if isinstance(e, dict) and e.get("url")
                        ]
                        il_selected, il_debug = select_videos(
                            entries=il_annotated,
                            n_videos=remaining_needed,
                            skip_downloaded=effective_skip_downloaded,
                            popular_enabled=use_popular_fallback,
                            random_enabled=randomize_links,
                            already_downloaded=already_downloaded,
                            platform=platform_key,
                            yt_content_type=yt_content_type,
                        )
                        il_selected = [
                            e for e in il_selected
                            if (_key(e) not in session_ids and _key(e) not in attempted_ids)
                        ]
                        for d in il_debug:
                            self._terminal_log("SelectionDebugIL", json.dumps(d, ensure_ascii=False))
                        self._terminal_log(
                            "Instaloader",
                            f"selected_count={len(il_selected)} extracted={len(il_annotated)}",
                        )
                        il_queue_start = len(download_queue)
                        _queue_entries(il_selected, "Instaloader Selected", skip_downloaded=dup_ctrl)
                        _queue_entries(il_annotated, "Instaloader Backup", supported_only=True, skip_downloaded=dup_ctrl)
                        if len(download_queue) > il_queue_start:
                            _download_entries(download_queue[il_queue_start:], "Instaloader", allow_ix_retry=False)
                    else:
                        self._terminal_log("Instaloader", "no video links extracted")
                else:
                    self._terminal_log("Instaloader", "no session file — skipping (run: python -m instaloader --login=username)")
            except Exception as _il_exc:
                self._terminal_log("Instaloader", f"fallback error: {_il_exc}")

        if (
            len(downloads) < n_target
            and not latest_entries
            and not ix_annotated
            and not (
                platform_key == "instagram"
                and str(result.get("failure_type") or "") in {"auth_missing", "auth_expired", "auth_wall"}
            )
            and (self._current_auth_ticket or {}).get("can_use_public_fallback")
            and extract_links_intelligent is not None
            and get_cookies_dir is not None
        ):
            remaining_needed = max(1, n_target - len(downloads))
            self.progress.emit("[Public] Auth paths exhausted. Trying limited public fallback...")
            try:
                public_data = extract_links_intelligent(
                    url=creator_url,
                    platform_key=platform_key,
                    cookies_dir=get_cookies_dir(),
                    options={
                        "max_videos": remaining_needed + 5,
                        "force_all_methods": False,
                        "respect_global_exhaustive_mode": False,
                        "fast_mode": False,
                        "managed_profile_only": True,
                        "public_fallback_only": True,
                        "interactive_login_fallback": False,
                        "yt_content_type": yt_content_type,
                        "auth_ticket": dict(self._current_auth_ticket or {}),
                        "include_meta": True,
                    },
                    progress_callback=self.progress.emit,
                )
                public_entries = public_data[0] if isinstance(public_data, tuple) else public_data
                public_meta = (
                    public_data[2]
                    if isinstance(public_data, tuple)
                    and len(public_data) > 2
                    and isinstance(public_data[2], dict)
                    else {}
                )
                self._attempt_summary.extend(public_meta.get("attempt_reports", []) or [])
                self._record_attempt(
                    stage="public_fallback",
                    method_id="extract_links_intelligent",
                    auth_source="public",
                    result="success" if public_entries else "failed",
                    failure_type="" if public_entries else str(public_meta.get("failure_type") or "no_links"),
                    links_added=len(public_entries or []),
                    retry_used=False,
                    detail=creator_url[:240],
                )
                if public_entries:
                    result["anonymous_fallback_used"] = True
                    for entry in public_entries:
                        if not isinstance(entry, dict):
                            continue
                        if not entry.get("id"):
                            entry["id"] = _safe_id_from_url(entry.get("url", ""))
                        entry["platform"] = platform_key
                        entry["creator"] = entry.get("creator") or creator_name or self.creator_folder.name
                    public_annotated = [
                        normalise_entry(e)
                        for e in public_entries
                        if isinstance(e, dict) and e.get("url")
                    ]
                    public_selected, public_debug = select_videos(
                        entries=public_annotated,
                        n_videos=remaining_needed,
                        skip_downloaded=effective_skip_downloaded,
                        popular_enabled=use_popular_fallback,
                        random_enabled=randomize_links,
                        already_downloaded=already_downloaded,
                        platform=platform_key,
                        yt_content_type=yt_content_type,
                    )
                    public_selected = [
                        e for e in public_selected
                        if (_key(e) not in session_ids and _key(e) not in attempted_ids)
                    ]
                    for d in public_debug:
                        self._terminal_log("SelectionDebugPublic", json.dumps(d, ensure_ascii=False))
                    public_queue_start = len(download_queue)
                    public_added = _queue_entries(
                        public_selected,
                        "Public Selected",
                        skip_downloaded=dup_ctrl,
                    )
                    public_added += _queue_entries(
                        public_annotated,
                        "Public Backup",
                        supported_only=True,
                        skip_downloaded=dup_ctrl,
                    )
                    if public_added:
                        _download_entries(
                            download_queue[public_queue_start:],
                            "Public",
                            allow_ix_retry=False,
                        )
            except Exception as exc:
                self._terminal_log("PublicFallback", f"failed: {exc}")

        # History stays the last fallback, only after both legacy and IX paths.
        if len(downloads) < n_target:
            remaining_needed = max(1, n_target - len(downloads))
            self._terminal_log(
                "History",
                f"entering fallback because total delivered={len(downloads)}/{n_target}; remaining_needed={remaining_needed}",
            )
            late_history_candidates: List[Dict] = []
            url_history = self.config.get_url_history()
            if url_history:
                platform_history = []
                for h in url_history:
                    history_url = (h.get("url") or "").strip()
                    history_key = (_safe_id_from_url(history_url) or history_url).strip()
                    if not history_url:
                        continue
                    if h.get("platform", "").lower() != platform_key:
                        continue
                    if history_key in attempted_ids or history_key in session_ids:
                        continue
                    platform_history.append(h)

                if platform_history:
                    late_history_candidates = [
                        {
                            "url": h["url"],
                            "id": _safe_id_from_url(h["url"]),
                            "platform": platform_key,
                            "creator": h.get("creator", self.creator_folder.name),
                            "_selection_reason": "history_fallback",
                            "_download_tier": "History",
                        }
                        for h in platform_history
                    ]
                    random.shuffle(late_history_candidates)
                    late_history_candidates = late_history_candidates[
                        : min(3, len(late_history_candidates), remaining_needed)
                    ]
                    self.progress.emit(
                        f"[History] Old + IX flow still short. Trying {len(late_history_candidates)} from download history."
                    )
                    logging.info(
                        "[HistoryFallback] Picking %d from %d history entries for %s",
                        len(late_history_candidates),
                        len(platform_history),
                        platform_key,
                    )

            if late_history_candidates:
                history_queue_start = len(download_queue)
                history_added = _queue_entries(
                    late_history_candidates,
                    "History",
                    skip_downloaded=dup_ctrl,
                )
                if history_added:
                    _download_entries(
                        download_queue[history_queue_start:],
                        "History",
                        allow_ix_retry=False,
                    )

        # â"€â"€ Post-processing (edit + watermark) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
        if dup_ctrl and len(downloads) < n_target:
            duplicate_candidates: List[Dict] = []
            duplicate_seen: set = set()

            def _append_duplicate_candidates(entries: List[Dict], label: str) -> None:
                for entry in entries or []:
                    if not isinstance(entry, dict):
                        continue
                    url = (entry.get("url") or "").strip()
                    if not url:
                        continue
                    if not _is_supported_video_url(url, platform_key):
                        continue
                    if not _is_already_downloaded(entry):
                        continue
                    entry_key = _key(entry) or url
                    if entry_key in attempted_ids or entry_key in session_ids or entry_key in duplicate_seen:
                        continue
                    duplicate_seen.add(entry_key)
                    entry_copy = dict(entry)
                    entry_copy["_download_tier"] = entry_copy.get("_download_tier") or label
                    duplicate_candidates.append(entry_copy)

            _append_duplicate_candidates(annotated, "Duplicate")
            _append_duplicate_candidates(ix_annotated, "IX Duplicate")
            _append_duplicate_candidates(late_history_candidates, "History Duplicate")

            if duplicate_candidates:
                random.shuffle(duplicate_candidates)
                duplicate_queue_start = len(download_queue)
                duplicate_added = _queue_entries(
                    duplicate_candidates,
                    "Duplicate",
                    supported_only=True,
                    skip_downloaded=False,
                )
                if duplicate_added:
                    self.progress.emit(
                        f"[Duplicate] Unique links exhausted. Re-trying {duplicate_added} previously downloaded link(s)."
                    )
                    _download_entries(
                        download_queue[duplicate_queue_start:],
                        "Duplicate",
                        allow_ix_retry=False,
                    )

        if downloads and not self._stop:
            self._terminal_log(
                "Post",
                f"download phase complete ({len(downloads)} videos). Starting post-processing...",
            )

            # Validate ffmpeg BEFORE starting any editing — re-resolve if broken
            from modules.video_editor.utils import check_ffmpeg, get_ffmpeg_path
            ffmpeg_ok = False
            try:
                subprocess.run(
                    [self.ffmpeg, "-version"],
                    capture_output=True, timeout=5,
                )
                ffmpeg_ok = True
            except Exception:
                pass

            if not ffmpeg_ok:
                self.progress.emit(f"Bundled ffmpeg failed ({self.ffmpeg}), searching for alternative...")
                print(f"[CreatorProfile] Bundled ffmpeg failed ({self.ffmpeg}), re-resolving...")
                if check_ffmpeg():
                    self.ffmpeg = get_ffmpeg_path()
                    ffmpeg_ok = True
                    self.progress.emit(f"Found working ffmpeg: {self.ffmpeg}")
                    print(f"[CreatorProfile] Re-resolved ffmpeg to: {self.ffmpeg}")

            if not ffmpeg_ok:
                self.progress.emit("ERROR: ffmpeg not found! Editing/watermark/split SKIPPED")
                self.progress.emit("FIX: Copy ffmpeg folder to C:\\ffmpeg (with bin\\ffmpeg.exe + DLLs)")
                print(f"[CreatorProfile] CRITICAL: No working ffmpeg found - skipping all post-processing")
            else:
                self.progress.emit(f"ffmpeg OK: {self.ffmpeg}")

            from .watermark_engine import apply_watermark_inplace

            wm_enabled = self.config.watermark_enabled
            wm_text_cfg = self.config.watermark_text
            wm_logo_cfg = self.config.watermark_logo
            wm_avatar_cfg = self.config.watermark_avatar
            split_edit_cfg = self.config.split_edit_settings

            def _apply_wm(fp: Path, preserve_source: bool = False) -> Path:
                if not wm_enabled:
                    return fp
                if not ffmpeg_ok:
                    self.progress.emit(f"  SKIP watermark for {fp.name} (ffmpeg unavailable)")
                    return fp
                result_path = apply_watermark_inplace(
                    video_path=fp,
                    creator_folder=self.creator_folder,
                    wm_text_cfg=wm_text_cfg,
                    wm_logo_cfg=wm_logo_cfg,
                    wm_avatar_cfg=wm_avatar_cfg,
                    keep_original=preserve_source,
                    ffmpeg=self.ffmpeg,
                    progress_cb=self.progress.emit,
                )
                if not result_path:
                    self.progress.emit(f"  WARNING: watermark failed for {fp.name} - kept original")
                    return fp
                return result_path

            mode = self.config.editing_mode
            if mode == "split_edit" and ffmpeg_ok:
                from .config_manager import summarize_split_edit_settings
                from .split_edit_engine import apply_split_edit_to_clip

                self.progress.emit(f"Editing: splitting into {self.config.split_duration}s segments...")
                self.progress.emit(
                    f"Editing: split+edit ({summarize_split_edit_settings(split_edit_cfg)})..."
                )
                for fp in downloads:
                    if self._stop:
                        break
                    parts = split_video(
                        fp,
                        self.creator_folder,
                        self.config.split_duration,
                        self.ffmpeg,
                        self.progress.emit,
                    )
                    if not parts:
                        self.progress.emit(f"  WARNING: split failed for {fp.name} - kept original")
                    for part in parts:
                        if self._stop:
                            break
                        edited_part = apply_split_edit_to_clip(
                            part,
                            self.creator_folder,
                            split_edit_cfg,
                            self.ffmpeg,
                            self.progress.emit,
                        )
                        final_part = edited_part or part
                        if edited_part and edited_part != part and part.exists():
                            try:
                                part.unlink()
                            except Exception:
                                pass
                        if wm_enabled:
                            final_part = _apply_wm(final_part, preserve_source=False)
                        self.config.append_activity_event(
                            "split_edit_part_finalized",
                            {
                                "source": fp.name,
                                "part": final_part.name if final_part else part.name,
                                "edited": bool(edited_part),
                            },
                        )
                    self.config.append_activity_event(
                        "output_finalized",
                        {"mode": "split_edit", "source": fp.name, "parts": len(parts)},
                    )
                    if parts and not keep_original and fp.exists():
                        try:
                            fp.unlink()
                            self.progress.emit(f"Removed original: {fp.name}")
                        except Exception:
                            pass
            elif mode == "split_edit" and not ffmpeg_ok:
                self.progress.emit("SKIP split+edit: ffmpeg not available")

            elif mode == "split" and ffmpeg_ok:
                self.progress.emit(f"Editing: splitting into {self.config.split_duration}s segments...")
                for fp in downloads:
                    if self._stop:
                        break
                    parts = split_video(
                        fp,
                        self.creator_folder,
                        self.config.split_duration,
                        self.ffmpeg,
                        self.progress.emit,
                    )
                    if not parts:
                        self.progress.emit(f"  WARNING: split failed for {fp.name} - kept original")
                    for part in parts:
                        if self._stop:
                            break
                        _apply_wm(part, preserve_source=False)
                    self.config.append_activity_event(
                        "output_finalized",
                        {"mode": "split", "source": fp.name, "parts": len(parts)},
                    )
                    if parts and not keep_original and fp.exists():
                        try:
                            fp.unlink()
                            self.progress.emit(f"Removed original: {fp.name}")
                        except Exception:
                            pass
            elif mode == "split" and not ffmpeg_ok:
                self.progress.emit("SKIP split: ffmpeg not available")

            elif mode == "preset" and self.config.preset_name and ffmpeg_ok:
                self.progress.emit(f"Editing: applying preset '{self.config.preset_name}'...")
                for fp in downloads:
                    if self._stop:
                        break
                    out = apply_preset(fp, self.creator_folder, self.config.preset_name, self.ffmpeg)
                    if not out:
                        self.progress.emit(f"  WARNING: preset failed for {fp.name} - kept original")
                    if out:
                        _apply_wm(out, preserve_source=False)
                    self.config.append_activity_event(
                        "output_finalized",
                        {"mode": "preset", "source": fp.name, "output": out.name if out else ""},
                    )
                    if out and not keep_original and fp.exists():
                        try:
                            fp.unlink()
                            self.progress.emit(f"Removed original: {fp.name}")
                        except Exception:
                            pass
            elif mode == "preset" and not ffmpeg_ok:
                self.progress.emit("SKIP preset: ffmpeg not available")

            else:
                for fp in downloads:
                    if self._stop:
                        break
                    _apply_wm(fp, preserve_source=keep_original)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Finalize Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        count = len(downloads)
        status_code = "success" if count >= n_target else ("partial_download" if count > 0 else "failed")
        activity_status = "success" if count >= n_target else ("partial" if count > 0 else "failed")
        if not result.get("failure_type") and last_error_message:
            try:
                from modules.shared.failure_classifier import classify_failure
                result["failure_type"] = classify_failure(last_error_message, platform_key).name.lower()
            except Exception:
                result["failure_type"] = "download_failed"
        if status_code == "failed":
            if result.get("stage_failed") == "runtime_readiness":
                status_code = "runtime_unavailable"
            elif result.get("failure_type") in {"auth_expired", "auth_missing", "auth_wall"}:
                status_code = "failed_auth"
            elif int(result.get("links_found", 0) or 0) == 0:
                status_code = "link_grab_failed"
            else:
                status_code = "download_failed"
        result["status_code"] = status_code
        self.config.update_last_activity(activity_status, tier_used or "N/A", count)
        self.config.save()

        if count == 0 and not result.get("error"):
            result["error"] = last_error_message or "No videos were downloaded"
            self._terminal_log("Run", f"fail reason: {result['error']}")
        elif 0 < count < n_target and not result.get("error"):
            result["error"] = last_error_message or f"Only {count}/{n_target} downloaded"
            self._terminal_log("Run", f"partial: {result['error']}")

        result["success"] = status_code == "success"
        result["downloaded"] = count
        result["failed"] = failed_downloads
        result["target"] = n_target
        result["tier_used"] = tier_used
        result["links_found"] = max(int(result.get("links_found", 0) or 0), len(latest_entries))
        result["attempt_summary"] = list(self._attempt_summary or [])
        summary_parts = [f"Done: {count}/{n_target}"]
        if failed_downloads:
            summary_parts.append(f"Failed: {failed_downloads}")
        summary_parts.append(f"Tier: {tier_used or 'N/A'}")
        summary_parts.append(f"Status: {status_code}")
        self.progress.emit(" | ".join(summary_parts))

        # Concise run summary for debugging / reliability checks.
        try:
            proxy_count = len(self.proxies or [])
            cookie_line = ""
            if self._cookie_sync_info:
                cookie_line = " | cookies_synced=" + ",".join(sorted(self._cookie_sync_info.keys()))
            err_line = ""
            if not result.get("success") and self._last_download_error:
                err_line = f" | last_error={str(self._last_download_error)[:120]}"
            self.progress.emit(
                f"Summary: platform={platform_key} target={n_target} downloaded={count} proxies={proxy_count}{cookie_line}{err_line}"
            )
        except Exception:
            pass
