"""
modules/creator_profiles/download_engine.py
Tiered downloader + optional post-processing for creator profiles.

Link grabbing: uses Playwright browser engine (same as Link Grabber module).
Never reads links.txt files — always visits profile fresh via browser.
"""

import json
import random
import shutil
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import yt_dlp
from PyQt5.QtCore import QThread, pyqtSignal

from .config_manager import CreatorConfig
from modules.shared.auth_network_hub import AuthNetworkHub


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_id_from_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    patterns = [
        r"v=([A-Za-z0-9_-]{6,})",
        r"youtu\.be/([A-Za-z0-9_-]{6,})",
        r"/video/(\d+)",
        r"/reel/([A-Za-z0-9_-]+)",
        r"/p/([A-Za-z0-9_-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, u, re.IGNORECASE)
        if m:
            return m.group(1)
    return u.rstrip("/")


def _ffmpeg_path() -> str:
    try:
        from modules.video_editor.utils import check_ffmpeg, get_ffmpeg_path
        if check_ffmpeg():
            p = get_ffmpeg_path()
            if p:
                return p
    except Exception:
        pass
    which = shutil.which("ffmpeg")
    if which:
        return which
    for candidate in [
        Path("bin/ffmpeg/ffmpeg.exe"),
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/ffmpeg/ffmpeg.exe"),
    ]:
        if candidate.exists():
            return str(candidate)
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


# ── Link Grabbing via Playwright (same engine as Link Grabber) ────────────────

def grab_links_via_playwright(
    creator_url: str,
    platform_key: str,
    max_count: int,
    progress_cb: Callable[[str], None] = None,
) -> List[Dict]:
    """
    Visit creator profile using Playwright Chromium browser and collect video links.
    Uses ChromiumAuthManager (same engine as Link Grabber module).

    Returns list of dicts: [{"url": ..., "title": ..., "date": ...}, ...]
    """
    try:
        from modules.link_grabber.browser_auth import ChromiumAuthManager
        auth_manager = ChromiumAuthManager()
    except Exception as e:
        if progress_cb:
            progress_cb(f"Playwright init failed: {e}")
        return []

    content_filter_map = {
        "youtube": "all_videos",
        "tiktok": "all_videos",
        "instagram": "reels_only",
        "facebook": "videos_reels",
        "other": "all_videos",
    }
    content_filter = content_filter_map.get(platform_key, "all_videos")

    if progress_cb:
        progress_cb(f"Browser: visiting {platform_key} profile...")

    try:
        entries = auth_manager.grab_links_via_browser(
            url=creator_url,
            platform_key=platform_key,
            content_filter=content_filter,
            max_items=max_count * 4 if max_count > 0 else 0,
            progress_callback=progress_cb,
        )
        if progress_cb:
            progress_cb(f"Browser: found {len(entries)} links")
        return entries
    except Exception as e:
        if progress_cb:
            progress_cb(f"Browser grab failed: {e}")
        return []


# ── Video Download ────────────────────────────────────────────────────────────

def download_video(
    url: str,
    output_folder: Path,
    ffmpeg: str = "ffmpeg",
    progress_cb: Callable[[str], None] = None,
    proxy_url: str = None,
    cookiefile: str = None,
) -> Optional[Path]:
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    video_exts = {
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".mpeg", ".mpg"
    }
    before_files = {p.name for p in output_folder.iterdir() if p.is_file()}

    opts = {
        "outtmpl": str(output_folder / "%(title)s.%(ext)s"),
        "format": "best[ext=mp4]/mp4/best",
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "playlist_items": "1",
        "playlistend": 1,
        "socket_timeout": 60,
        "retries": 3,
    }
    if proxy_url:
        opts["proxy"] = proxy_url
    if cookiefile:
        opts["cookiefile"] = cookiefile
    if ffmpeg and ffmpeg != "ffmpeg":
        opts["ffmpeg_location"] = str(Path(ffmpeg).parent)

    result_path: List[Optional[Path]] = [None]

    def _hook(d):
        if d.get("status") == "finished":
            fp = d.get("filename") or d.get("info_dict", {}).get("_filename", "")
            if fp:
                result_path[0] = Path(fp)
        if progress_cb and d.get("_percent_str"):
            progress_cb(f"    {d['_percent_str'].strip()}")

    opts["progress_hooks"] = [_hook]
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
        pass

    # Safety net: if multiple new files appeared, keep newest only
    try:
        fresh_videos = [
            p for p in output_folder.iterdir()
            if p.is_file() and p.name not in before_files and p.suffix.lower() in video_exts
        ]
        if len(fresh_videos) > 1:
            fresh_videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            keep = fresh_videos[0]
            for extra in fresh_videos[1:]:
                try:
                    extra.unlink()
                except Exception:
                    pass
            result_path[0] = keep
    except Exception:
        pass

    return result_path[0]


# ── FFprobe / Split ───────────────────────────────────────────────────────────

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


# ── Main Worker Thread ────────────────────────────────────────────────────────

class CreatorDownloadWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)

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

    def _active_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        return self.proxies[self._proxy_index]

    def _rotate_proxy(self):
        if len(self.proxies) > 1:
            self._proxy_index = (self._proxy_index + 1) % len(self.proxies)
            self.progress.emit(f"    Proxy switched to {self._proxy_index + 1}/{len(self.proxies)}")

    def stop(self):
        self._stop = True

    def run(self):
        result = {"success": False, "downloaded": 0, "tier_used": None, "error": None}
        try:
            self._execute(result)
        except Exception as e:
            result["error"] = str(e)
            self.progress.emit(f"Error: {e}")
            self.config.update_last_activity("failed", "Error", 0)
            self.config.save()
        self.finished.emit(result)

    def _execute(self, result: dict):
        # ── Load settings ──────────────────────────────────────────────────
        n_target = self.config.n_videos
        dup_ctrl = self.config.duplication_control
        use_popular_fallback = self.config.popular_fallback
        randomize_links = self.config.randomize_links
        keep_original = self.config.keep_original_after_edit

        creator_url = self.creator_url or self.config.creator_url or ""
        if not creator_url:
            inferred = self.config.ensure_creator_url()
            creator_url = inferred or ""

        if not creator_url:
            self.progress.emit("No creator URL found. Please set the URL in Edit settings.")
            self.config.update_last_activity("failed", "No URL", 0)
            self.config.save()
            return

        platform_key = _detect_platform(creator_url)
        self.progress.emit(f"Platform: {platform_key.upper()} | Target: {n_target} videos")

        downloads: List[Path] = []
        tier_used = None
        session_ids: set = set()

        def _key(vid: Dict) -> str:
            return (vid.get("id") or vid.get("url") or "").strip()

        def _is_duplicate(vid: Dict) -> bool:
            if not dup_ctrl:
                return False
            vid_id = vid.get("id") or _safe_id_from_url(vid.get("url", ""))
            if vid_id and self.config.is_downloaded(vid_id):
                return True
            return False

        def _filter_entries(entries: List[Dict]) -> List[Dict]:
            """Remove duplicates (session + persistent) from entry list."""
            result_list = []
            for vid in entries:
                key = _key(vid)
                if not key:
                    continue
                if key in session_ids:
                    continue
                if _is_duplicate(vid):
                    continue
                result_list.append(vid)
            return result_list

        def _download_entries(entries: List[Dict], label: str):
            """Download from a filtered list until n_target reached."""
            nonlocal tier_used
            for vid in entries:
                if self._stop or len(downloads) >= n_target:
                    return
                url = vid.get("url", "")
                if not url:
                    continue

                vid_platform = _detect_platform(url)
                cookie_file = self.auth_hub.pick_cookie_file(
                    vid_platform, str(self.creator_folder)
                )
                active_proxy = self._active_proxy()

                self.progress.emit(f"Downloading: {url[:80]}")
                fp = download_video(
                    url,
                    self.creator_folder,
                    self.ffmpeg,
                    self.progress.emit,
                    proxy_url=active_proxy,
                    cookiefile=cookie_file,
                )
                if not fp and active_proxy:
                    self._rotate_proxy()
                    fp = download_video(
                        url,
                        self.creator_folder,
                        self.ffmpeg,
                        self.progress.emit,
                        proxy_url=self._active_proxy(),
                        cookiefile=cookie_file,
                    )
                if not fp:
                    self.progress.emit(f"    Failed: {url[:60]}")
                    continue

                downloads.append(fp)
                vid_id = vid.get("id") or _safe_id_from_url(url)
                if vid_id:
                    self.config.add_downloaded_id(vid_id)
                session_ids.add(_key(vid))
                tier_used = label
                self.config.append_activity_event(
                    "download_completed",
                    {"video_id": vid_id, "title": vid.get("title", ""), "tier": label},
                )
                self.progress.emit(f"Progress: {len(downloads)}/{n_target}")

        # ── Tier 1: Grab latest from profile (Playwright) ─────────────────
        self.progress.emit("Tier 1: Fetching latest videos from profile...")
        latest_entries = grab_links_via_playwright(
            creator_url=creator_url,
            platform_key=platform_key,
            max_count=n_target,
            progress_cb=self.progress.emit,
        )

        # Assign IDs from URL if missing
        for e in latest_entries:
            if not e.get("id"):
                e["id"] = _safe_id_from_url(e.get("url", ""))

        # Latest entries are already ordered newest-first by browser_auth
        filtered_latest = _filter_entries(latest_entries)
        _download_entries(filtered_latest, "Tier 1: Latest")

        # ── Tier 2: If still need more videos ─────────────────────────────
        if not self._stop and len(downloads) < n_target:
            remaining = n_target - len(downloads)
            self.progress.emit(f"Need {remaining} more. Checking fallback preferences...")

            if use_popular_fallback:
                # Popular fallback: re-fetch with more links and pick by popularity order
                self.progress.emit("Tier 2: Popular fallback — fetching more links...")
                popular_entries = grab_links_via_playwright(
                    creator_url=creator_url,
                    platform_key=platform_key,
                    max_count=n_target * 4,
                    progress_cb=self.progress.emit,
                )
                for e in popular_entries:
                    if not e.get("id"):
                        e["id"] = _safe_id_from_url(e.get("url", ""))

                filtered_popular = _filter_entries(popular_entries)

                if randomize_links:
                    # Random mode: shuffle before picking
                    random.shuffle(filtered_popular)
                    self.progress.emit("Random mode: shuffled popular links")

                _download_entries(filtered_popular, "Tier 2: Popular")

            else:
                # No popular → use remaining links from same latest fetch (already have them)
                # Just try with all links collected, skip already seen
                self.progress.emit("Tier 2: Using remaining latest links...")
                remaining_latest = _filter_entries(latest_entries)
                _download_entries(remaining_latest, "Tier 2: Latest Extended")

        # ── Post-processing (edit + watermark) ────────────────────────────
        if downloads and not self._stop:
            from .watermark_engine import apply_watermark_inplace

            wm_enabled = self.config.watermark_enabled
            wm_text_cfg = self.config.watermark_text
            wm_logo_cfg = self.config.watermark_logo

            def _apply_wm(fp: Path) -> Path:
                """Apply watermark inplace if enabled. Returns final path."""
                if not wm_enabled:
                    return fp
                return apply_watermark_inplace(
                    video_path=fp,
                    creator_folder=self.creator_folder,
                    wm_text_cfg=wm_text_cfg,
                    wm_logo_cfg=wm_logo_cfg,
                    keep_original=False,
                    ffmpeg=self.ffmpeg,
                    progress_cb=self.progress.emit,
                )

            mode = self.config.editing_mode
            if mode == "split":
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
                    # Apply watermark to each split part
                    for part in parts:
                        if self._stop:
                            break
                        _apply_wm(part)
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

            elif mode == "preset" and self.config.preset_name:
                self.progress.emit(f"Editing: applying preset '{self.config.preset_name}'...")
                for fp in downloads:
                    if self._stop:
                        break
                    out = apply_preset(fp, self.creator_folder, self.config.preset_name, self.ffmpeg)
                    if out:
                        _apply_wm(out)
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

            else:
                # mode == "none" — only watermark if enabled
                for fp in downloads:
                    if self._stop:
                        break
                    _apply_wm(fp)

        # ── Finalize ───────────────────────────────────────────────────────
        count = len(downloads)
        status = "success" if count >= n_target else ("partial" if count > 0 else "failed")
        self.config.update_last_activity(status, tier_used or "N/A", count)
        self.config.save()

        result["success"] = count > 0
        result["downloaded"] = count
        result["tier_used"] = tier_used
        self.progress.emit(f"Done: {count}/{n_target} | Tier: {tier_used or 'N/A'}")
