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
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

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
USE_IXBROWSER_APPROACH = False  # Set True to test IXBrowser approach


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


def _facebook_backfill_url(url: str) -> str:
    """Return a stronger Facebook source URL for reel/video discovery."""
    raw = (url or "").strip()
    if not raw:
        return raw
    low = raw.lower().rstrip("/")

    # Already a direct video-like URL or explicit reels/videos tab.
    if any(token in low for token in ("/reel/", "/reels", "/videos", "/watch/", "/share/v/")):
        return raw

    # profile.php style prefers reels tab query.
    if "facebook.com/profile.php" in low:
        if "sk=reels_tab" in low:
            return raw
        connector = "&" if "?" in raw else "?"
        return f"{raw}{connector}sk=reels_tab"

    # Username/profile style -> force reels tab URL.
    return raw.rstrip("/") + "/reels"


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

    before_files = {p.name for p in output_folder.iterdir() if p.is_file()}
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
            fresh = [
                p for p in output_folder.iterdir()
                if p.is_file() and p.name not in before_files and p.suffix.lower() in video_exts
            ]
            if len(fresh) > 1:
                fresh.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                for extra in fresh[1:]:
                    try:
                        extra.unlink()
                    except Exception:
                        pass
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
            "outtmpl": str(output_folder / "%(title)s.%(ext)s"),
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
            "-o", str(output_folder / "%(title)s.%(ext)s"),
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
    try:
        cmd = [
            _ffprobe_path(ffmpeg), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            sec = float((r.stdout or "").strip())
            if sec > 0:
                return sec
    except Exception:
        pass
    try:
        r = subprocess.run(
            [ffmpeg, "-i", str(input_path)],
            capture_output=True, text=True, timeout=30,
        )
        text = (r.stderr or "") + "\n" + (r.stdout or "")
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 0.0


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
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if r.returncode != 0:
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
                r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=1800)
                if r2.returncode != 0:
                    break

            if out_path.exists() and out_path.stat().st_size > 0:
                actual = _probe_duration_seconds(out_path, ffmpeg)
                if actual >= min_valid_part_sec:
                    parts.append(out_path)
                else:
                    try:
                        out_path.unlink()
                    except Exception:
                        pass
                    break
            else:
                break
        except Exception:
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
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode == 0 and out.exists():
            return out
    except Exception:
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

        # Overall progress tracking for GUI progress bar
        self._n_target = 0           # total videos to download
        self._n_completed = 0        # videos fully downloaded so far

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

    # ── Delete-before-download cleanup ──────────────────────────────────────

    _MEDIA_EXTENSIONS = frozenset({
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv",
        ".m4v", ".mpeg", ".mpg", ".ts", ".3gp",
    })

    def _delete_existing_media(self) -> None:
        """Delete existing media files in the creator folder (once per run).

        Only deletes top-level files matching known video extensions.
        Preserves config, metadata, text files, images, and subdirectories.
        """
        folder = self.creator_folder
        if not folder.is_dir():
            return

        self.progress.emit("[Cleanup] delete_before_download enabled - scanning folder...")
        print(f"[CreatorProfile] delete_before_download: scanning {folder}")

        found: List[Path] = []
        for item in folder.iterdir():
            if item.is_file() and item.suffix.lower() in self._MEDIA_EXTENSIONS:
                found.append(item)

        if not found:
            self.progress.emit("[Cleanup] No existing media files found.")
            return

        self.progress.emit(f"[Cleanup] Found {len(found)} media file(s) to delete.")
        deleted = 0
        for fp in found:
            try:
                fp.unlink()
                deleted += 1
                self.progress.emit(f"[Cleanup] Deleted: {fp.name}")
                print(f"[CreatorProfile] delete_before_download: deleted {fp.name}")
            except Exception as exc:
                self.progress.emit(f"[Cleanup] Failed to delete {fp.name}: {exc}")
                print(f"[CreatorProfile] delete_before_download: FAILED {fp.name}: {exc}")

        self.progress.emit(f"[Cleanup] Cleanup complete: {deleted}/{len(found)} files deleted.")

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
        os.makedirs(temp_dl_dir, exist_ok=True)
        # Clean any old temp files
        for old_temp in temp_dl_dir.iterdir():
            if old_temp.is_file():
                try: old_temp.unlink()
                except Exception: pass

        def _run_once(opts: Dict) -> Tuple[bool, str]:
            result = {"ok": False, "msg": ""}

            downloader = VideoDownloaderThread(
                urls=[url],
                save_path=str(temp_dl_dir),  # Download to temp!
                options=opts,
                bulk_mode_data=None,
            )
            self._active_downloader = downloader
            def _filter_relay(m):
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
                    return False, "Cancelled"
                time.sleep(0.15)

            downloader.wait(1500)
            self._active_downloader = None

            if not result["ok"] and int(getattr(downloader, "success_count", 0) or 0) > 0:
                result["ok"] = True

            reason = result["msg"]
            if not result["ok"] and not reason:
                try:
                    failed_urls = list(getattr(downloader, "failed_urls", []) or [])
                    if failed_urls and isinstance(failed_urls[0], (list, tuple)) and len(failed_urls[0]) >= 2:
                        reason = str(failed_urls[0][1] or "").strip()
                except Exception:
                    pass
            return result["ok"], (reason or "")

        # Use exact options the GUI manual VideoDownloader uses
        creator_name = ""
        try:
            creator_name = self.config.data.get('creator_name') or self.creator_folder.name
        except Exception:
            creator_name = self.creator_folder.name
        robust_opts: Dict = {
            "quality": "HD", # Use exact same string as VideoDownloader dropsdown for YouTube formats
            "skip_recent_window": False,
            "force_all_methods": True,
            "max_retries": 1,
            "rate_limit_delay": 2.5,
            "_creator_hint": creator_name,
        }
        ok, reason = _run_once(robust_opts)
        print(f"[CreatorProfile] _run_once result: ok={ok}, reason='{reason}'")

        if ok:
            # Look for the file in the temp output folder
            fp = None
            if temp_dl_dir.exists():
                for child in temp_dl_dir.iterdir():
                    if child.is_file() and child.name not in ["history.json"]:
                        fp = child
                        break
            
            if fp:
                # We found the downloaded file in the temp directory!
                # Now safely move it to the creator folder, renaming if title already exists 
                # (e.g., "Video_by_ashkan (1).mp4") so we never overwrite the user's previous videos.
                # ENHANCED: Use provided title if current filename is generic or very short
                safe_name = fp.name
                if provided_title and provided_title.strip():
                    generic_keywords = [
                        "facebook", "instagram", "tiktok", "youtube", "video", 
                        "post", "short", "reel"
                    ]
                    stem_low = fp.stem.lower()
                    # If the filename is short (e.g. 1234567.mp4) or contains generic platform names
                    is_generic = len(fp.stem) < 15 or any(kw in stem_low for kw in generic_keywords)
                    
                    if is_generic:
                        # Sanitize provided title for filesystem
                        clean_title = re.sub(r'[\\/*?:"<>|]', "", provided_title)
                        clean_title = clean_title.strip()[:100]
                        if clean_title and len(clean_title) > 5:
                            # Prepend creator name if not already present to ensure clarity
                            creator_name = self.creator_folder.name.lstrip('@')
                            if creator_name.lower() not in clean_title.lower() and len(clean_title) < 60:
                                safe_name = f"{creator_name}_{clean_title}{fp.suffix}"
                            else:
                                safe_name = f"{clean_title}{fp.suffix}"
                
                target_path = self.creator_folder / safe_name
                counter = 1
                while target_path.exists():
                    # If we renamed but there's a collision, add a counter to our new name
                    target_path = self.creator_folder / f"{Path(safe_name).stem} ({counter}){Path(safe_name).suffix}"
                    counter += 1
                
                import shutil
                shutil.move(str(fp), str(target_path))
                
                # Clean up temp folder safely
                try: shutil.rmtree(temp_dl_dir)
                except Exception: pass
                    
                return target_path, ""
                
            # Cleanup if no file found
            try: shutil.rmtree(temp_dl_dir)
            except Exception: pass
            
            return None, "Downloader reported success but no output file was found in temp folder"
            
        if reason == "Cancelled":
            return None, reason
            
        self._last_download_error = reason
        return None, (reason or "All downloader methods failed")

    # Ã¢â€â‚¬Ã¢â€â‚¬ Thread entry Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    def run(self):
        result = {"success": False, "downloaded": 0, "target": 0, "tier_used": None, "error": None}
        try:
            self._execute(result)
        except Exception as e:
            import traceback
            result["error"] = str(e)
            self.progress.emit(f"Error: {e}")
            print(f"[CreatorProfile] ERROR in _execute: {e}")
            traceback.print_exc()
            self.config.update_last_activity("failed", "Error", 0)
            self.config.save()
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
        keep_original = self.config.keep_original_after_edit
        delete_before_dl = self.config.delete_before_download

        if not creator_url:
            self.progress.emit("No creator URL found. Please set the URL in Edit settings.")
            result["error"] = "No creator URL configured"
            self.config.update_last_activity("failed", "No URL", 0)
            self.config.save()
            return

        platform_key = _detect_platform(creator_url)
        print(f"\n[CreatorProfile] >>> Processing @{self.creator_folder.name} on {platform_key.upper()}")
        self.progress.emit(f"Platform: {platform_key.upper()} | Target: {n_target} videos")
        self.progress_percent.emit(0)

        # ── Delete-before-download cleanup (once per creator run) ─────────
        if delete_before_dl:
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

        def _key(vid: Dict) -> str:
            return (vid.get("id") or vid.get("url") or "").strip()

        def _download_entries(entries: List[Dict], label: str):
            nonlocal tier_used, last_error_message
            for vid in entries:
                # Check pause between videos
                if self._check_pause():
                    return
                if len(downloads) >= n_target:
                    return

                url = vid.get("url", "")
                if not url:
                    continue
                entry_key = _key(vid)
                if not entry_key:
                    entry_key = url.strip()
                if entry_key in attempted_ids:
                    continue

                self.progress.emit(f"Downloading ({len(downloads)+1}/{n_target}): {url[:80]}")
                title = vid.get("title")
                
                # VideoDownloaderThread finds cookies internally via AuthNetworkHub
                print(f"[CreatorProfile] Attempting download: {url[:80]}")
                fp, dl_error = self._download_single_via_video_downloader(url, title)

                attempted_ids.add(entry_key)
                if not fp:
                    err = (dl_error or "download failed").strip()
                    last_error_message = err
                    msg = f"  Failed: {url[:60]} | {err[:120]}"
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
                self.config.add_url_to_history(
                    url, platform=platform_key,
                    creator=vid.get("creator", self.creator_folder.name),
                )
                session_ids.add(_key(vid))
                tier_used = label
                self.config.append_activity_event(
                    "download_completed",
                    {"video_id": vid_id, "title": vid.get("title", ""), "tier": label},
                )
                self.progress.emit(f"Progress: {len(downloads)}/{n_target}")

                # Pacing: 2-4s between operations + batch cooldown every ~10
                if len(downloads) < n_target:
                    _pacer.pace_operation()

        # ── Fetching links ────────────────────────────────────────────────────────
        if self._check_pause():
            return

        latest_entries = []
        creator_name = ""

        if USE_IXBROWSER_APPROACH:
            # ── Approach 2: IXBrowser + Selenium ─────────────────────────────
            self.progress.emit("[IX] Using IXBrowser approach for link grabbing...")
            print(f"[CreatorProfile] IXBrowser approach for {creator_url} on {platform_key}")

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

                # Step 2: Check login for this platform
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

                # Step 3: Minimize browser — further work is background
                ix.minimize_browser(progress_cb=self.progress.emit)

                # Step 4: Extract links
                fetch_count = n_target * 2 if use_popular_fallback else n_target + 5
                latest_entries, creator_name = ix.extract_links(
                    creator_url=creator_url,
                    platform_key=platform_key,
                    max_videos=fetch_count,
                    progress_cb=self.progress.emit,
                )
                print(f"[CreatorProfile] IX extracted {len(latest_entries)} links for '{creator_name}'")

            except Exception as e:
                msg = f"IXBrowser extraction failed: {e}"
                self.progress.emit(msg)
                print(f"[CreatorProfile] Error: {msg}")
                import traceback
                traceback.print_exc()
                latest_entries = []

        else:
            # ── Approach 1: Playwright + Intelligent Link Grabber (existing) ─
            self.progress.emit("Fetching latest videos from profile using robust Link Grabber...")

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
        print(f"[CreatorProfile] Annotated {len(annotated)} entries for selection")

        # ── Select: apply user preference logic BEFORE downloader ─────
        already_downloaded: frozenset = frozenset(
            self.config.data.get("downloaded_ids", [])
        ) if dup_ctrl else frozenset()

        selected, debug_log = select_videos(
            entries=annotated,
            n_videos=n_target,
            skip_downloaded=dup_ctrl,
            popular_enabled=use_popular_fallback,
            random_enabled=randomize_links,
            already_downloaded=already_downloaded,
            platform=platform_key,
        )

        # Social backfill (Facebook/Instagram): if selection is short after
        # filtering/dedup, grab a broader reel/video pool and re-run selection.
        if (
            platform_key in {"facebook", "instagram"}
            and not USE_IXBROWSER_APPROACH
            and len(selected) < n_target
        ):
            need_more = n_target - len(selected)
            try:
                from modules.link_grabber.core import extract_links_intelligent
                from modules.config.paths import get_cookies_dir

                if platform_key == "facebook":
                    backfill_url = _facebook_backfill_url(creator_url)
                else:
                    backfill_url = _instagram_backfill_url(creator_url)
                backfill_max = max(40, n_target * 8)

                # Mandatory pre-backfill cooldown to avoid burst behavior.
                # Base: 30-70s, plan-aware scaling via PacingManager.
                backfill_wait = _pacer.scale_delay(random.uniform(30.0, 70.0))
                self.progress.emit(
                    f"{platform_key.title()} backfill cooldown: {backfill_wait:.1f}s before retry..."
                )
                wait_until = time.time() + backfill_wait
                while time.time() < wait_until:
                    if self._check_pause():
                        return
                    step = min(1.0, max(0.0, wait_until - time.time()))
                    if step > 0:
                        time.sleep(step)

                self.progress.emit(
                    f"{platform_key.title()} backfill: need {need_more} more, scanning broader pool..."
                )

                backfill_opts = {
                    "max_videos": backfill_max,
                    "force_all_methods": True,
                    "fast_mode": False,
                    "managed_profile_only": True,
                    "interactive_login_fallback": False,
                }

                extra_data = extract_links_intelligent(
                    url=backfill_url,
                    platform_key=platform_key,
                    cookies_dir=get_cookies_dir(),
                    options=backfill_opts,
                    progress_callback=self.progress.emit,
                )
                extra_entries = extra_data[0] if isinstance(extra_data, tuple) else extra_data

                def _entry_key(ent: Dict) -> str:
                    u = (ent.get("url") or "").strip()
                    vid = (ent.get("id") or _safe_id_from_url(u)).strip()
                    if vid:
                        return f"id:{vid.lower()}"
                    return f"url:{u.lower()}"

                seen_keys = {
                    _entry_key(e) for e in latest_entries
                    if isinstance(e, dict) and e.get("url")
                }
                added_extra = 0
                for e in (extra_entries or []):
                    if not isinstance(e, dict) or not e.get("url"):
                        continue
                    key = _entry_key(e)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    latest_entries.append(e)
                    added_extra += 1

                if added_extra > 0:
                    for e in latest_entries:
                        if not isinstance(e, dict):
                            continue
                        if not e.get("id"):
                            e["id"] = _safe_id_from_url(e.get("url", ""))
                        e["platform"] = platform_key
                        e["creator"] = creator_name or self.creator_folder.name

                    annotated = [
                        normalise_entry(e)
                        for e in latest_entries
                        if isinstance(e, dict) and e.get("url")
                    ]
                    selected, debug_log = select_videos(
                        entries=annotated,
                        n_videos=n_target,
                        skip_downloaded=dup_ctrl,
                        popular_enabled=use_popular_fallback,
                        random_enabled=randomize_links,
                        already_downloaded=already_downloaded,
                        platform=platform_key,
                    )
                    debug_log.append({
                        "action": f"{platform_key}_backfill",
                        "added": added_extra,
                        "backfill_url": backfill_url[:120],
                    })
                    self.progress.emit(
                        f"{platform_key.title()} backfill added {added_extra} links. Re-selected {len(selected)}/{n_target}."
                    )
                else:
                    debug_log.append({
                        "action": f"{platform_key}_backfill",
                        "added": 0,
                        "backfill_url": backfill_url[:120],
                    })
            except Exception as bf_exc:
                logging.warning("%s backfill failed: %s", platform_key.title(), bf_exc)
                debug_log.append({"action": f"{platform_key}_backfill_error", "error": str(bf_exc)[:120]})

        # Remove session-already-attempted duplicates
        selected = [
            e for e in selected
            if (_key(e) not in session_ids and _key(e) not in attempted_ids)
        ]

        for d in debug_log:
            print(f"[SelectionDebug] {d}")

        print(f"[CreatorProfile] Selection: {len(selected)}/{n_target} from {len(annotated)} annotated")

        # ── Fallback 1: Duplicate fallback ────────────────────────────
        # When skip_downloaded removed all candidates, pick the most
        # recent duplicate so the run is never empty.
        if not selected and annotated and dup_ctrl:
            supported_annotated = [
                e for e in annotated
                if _is_supported_video_url(e.get("url", ""), platform_key)
            ]
            logging.info(
                "[SelectionFallback] skip_downloaded emptied selection "
                "(%d annotated, %d supported) — picking latest duplicate",
                len(annotated), len(supported_annotated),
            )
            # Sort by recency, pick latest
            from .selection_policy import _recency_key
            sorted_by_date = sorted(supported_annotated, key=_recency_key, reverse=True)
            # Filter out session-attempted
            for candidate in sorted_by_date:
                ck = _key(candidate)
                if ck not in session_ids and ck not in attempted_ids:
                    candidate["_selection_reason"] = "duplicate_fallback"
                    selected = [candidate]
                    debug_log.append({"action": "duplicate_fallback", "url": candidate.get("url", "")[:80]})
                    self.progress.emit("All videos already downloaded — re-downloading latest as fallback.")
                    print(f"[SelectionFallback] Picked duplicate: {candidate.get('url', '')[:80]}")
                    break

        # ── Fallback 2: History fallback ──────────────────────────────
        # When extraction returned 0 links OR only unsupported links,
        # try up to 3 random URLs from persisted download history.
        annotated_has_supported = any(
            _is_supported_video_url(e.get("url", ""), platform_key) for e in annotated
        ) if annotated else False
        if not selected and (not annotated or not annotated_has_supported):
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
                    sample_count = min(3, len(platform_history), n_target)
                    history_sample = random.sample(platform_history, sample_count)
                    selected = []
                    for h in history_sample:
                        entry = {
                            "url": h["url"],
                            "id": _safe_id_from_url(h["url"]),
                            "platform": platform_key,
                            "creator": h.get("creator", self.creator_folder.name),
                            "_selection_reason": "history_fallback",
                        }
                        selected.append(entry)
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
        _download_entries(selected, "Selected")

        # â"€â"€ Post-processing (edit + watermark) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
        if downloads and not self._stop:
            print(f"[CreatorProfile] @{self.creator_folder.name}: Download phase complete ({len(downloads)} videos). Starting post-processing...")

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
                    keep_original=preserve_source,
                    ffmpeg=self.ffmpeg,
                    progress_cb=self.progress.emit,
                )
                if result_path == fp and wm_enabled:
                    self.progress.emit(f"  WARNING: watermark failed for {fp.name} - kept original")
                return result_path

            mode = self.config.editing_mode
            if mode == "split" and ffmpeg_ok:
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
        status = "success" if count >= n_target else ("partial" if count > 0 else "failed")
        self.config.update_last_activity(status, tier_used or "N/A", count)
        self.config.save()

        if count == 0 and not result.get("error"):
            result["error"] = last_error_message or "No videos were downloaded"
            print(f"[CreatorProfile] @{self.creator_folder.name}: FAIL REASON: {result['error']}")
        elif 0 < count < n_target and not result.get("error"):
            result["error"] = last_error_message or f"Only {count}/{n_target} downloaded"
            print(f"[CreatorProfile] @{self.creator_folder.name}: PARTIAL: {result['error']}")

        result["success"] = count >= n_target
        result["downloaded"] = count
        result["target"] = n_target
        result["tier_used"] = tier_used
        self.progress.emit(f"Done: {count}/{n_target} | Tier: {tier_used or 'N/A'}")
        print(f"[CreatorProfile] @{self.creator_folder.name}: Finished ({count}/{n_target}).\n")

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


