"""
modules/creator_profiles/download_engine.py
Tiered downloader + optional post-processing for creator profiles.
"""

import json
import random
import shutil
import subprocess
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

import yt_dlp
from PyQt5.QtCore import QThread, pyqtSignal

from .config_manager import CreatorConfig


def _safe_id_from_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    # Try common video id patterns first
    patterns = [
        r"v=([A-Za-z0-9_-]{6,})",           # youtube watch?v=
        r"youtu\.be/([A-Za-z0-9_-]{6,})",   # youtu.be/id
        r"/video/(\d+)",                    # tiktok/facebook style
        r"/reel/([A-Za-z0-9_-]+)",          # instagram reel
        r"/p/([A-Za-z0-9_-]+)",             # instagram post
    ]
    for pat in patterns:
        m = re.search(pat, u, re.IGNORECASE)
        if m:
            return m.group(1)
    # fallback: whole normalized URL
    return u.rstrip("/")


def read_links_from_creator_folder(folder: Path) -> List[Dict]:
    """
    Read URLs from creator folder files like *_links*.txt and return flat entries.
    Order is preserved from files so latest-first behavior depends on file ordering.
    """
    folder = Path(folder)
    files: List[Path] = []
    files.extend(sorted(folder.glob("*_links*.txt")))
    if not files:
        files.extend(sorted(folder.glob("*links*.txt")))
    if not files:
        files.extend(sorted(folder.glob("*.txt")))

    entries: List[Dict] = []
    seen = set()
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith(("http://", "https://")):
                        continue
                    url = line.split()[0].strip()
                    key = url.rstrip("/")
                    if key in seen:
                        continue
                    seen.add(key)
                    entries.append(
                        {
                            "id": _safe_id_from_url(url),
                            "url": url,
                            "title": Path(url).name or "Video",
                            "upload_date": "",
                        }
                    )
        except Exception:
            continue
    return entries


def has_links_in_creator_folder(folder: Path) -> bool:
    return len(read_links_from_creator_folder(folder)) > 0


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


def _popular_url(url: str, platform: str) -> str:
    url = (url or "").rstrip("/")
    if platform == "youtube":
        base = url.split("?")[0]
        if "/videos" not in base:
            base += "/videos"
        return base + "?view=0&sort=p&flow=grid"
    return url


def get_video_list(
    url: str,
    max_count: int,
    mode: str = "latest",
    dateafter: str = None,
    datebefore: str = None,
) -> List[Dict]:
    platform = _detect_platform(url)
    fetch_url = _popular_url(url, platform) if mode == "popular" else url

    opts = {
        "extract_flat": True,
        "playlistend": max(max_count, 10),
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "socket_timeout": 30,
    }
    if dateafter:
        opts["dateafter"] = dateafter
    if datebefore:
        opts["datebefore"] = datebefore

    videos: List[Dict] = []
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(fetch_url, download=False)
            if not info:
                return videos
            entries = info.get("entries") or ([info] if info.get("id") else [])
            for e in entries:
                if not e:
                    continue
                vid_url = e.get("webpage_url") or e.get("url", "")
                if not vid_url:
                    continue
                videos.append(
                    {
                        "id": e.get("id", ""),
                        "url": vid_url,
                        "title": e.get("title", "Untitled"),
                        "upload_date": e.get("upload_date", ""),
                    }
                )
    except Exception:
        pass
    return videos


def download_video(
    url: str,
    output_folder: Path,
    ffmpeg: str = "ffmpeg",
    progress_cb: Callable[[str], None] = None,
) -> Optional[Path]:
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    opts = {
        "outtmpl": str(output_folder / "%(title)s.%(ext)s"),
        "format": "best[ext=mp4]/mp4/best",
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "socket_timeout": 60,
        "retries": 3,
    }
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

    return result_path[0]


def split_video(input_path: Path, output_folder: Path, segment_sec: float, ffmpeg: str = "ffmpeg") -> List[Path]:
    input_path = Path(input_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem
    ext = input_path.suffix or ".mp4"
    pattern = str(output_folder / f"{stem}_part%03d{ext}")

    cmd = [
        ffmpeg,
        "-i",
        str(input_path),
        "-c",
        "copy",
        "-f",
        "segment",
        "-segment_time",
        str(int(segment_sec)),
        "-reset_timestamps",
        "1",
        "-avoid_negative_ts",
        "make_zero",
        pattern,
        "-y",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            return sorted(output_folder.glob(f"{stem}_part*{ext}"))
    except Exception:
        pass
    return []


def apply_preset(input_path: Path, output_folder: Path, preset_name: str, ffmpeg: str = "ffmpeg") -> Optional[Path]:
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


class CreatorDownloadWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, creator_folder: Path, creator_url: str, parent=None):
        super().__init__(parent)
        self.creator_folder = Path(creator_folder)
        self.creator_url = creator_url
        self.config = CreatorConfig(creator_folder)
        self.ffmpeg = _ffmpeg_path()
        self._stop = False

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
        n_target = self.config.n_videos
        dup_ctrl = self.config.duplication_control
        use_popular_fallback = self.config.popular_fallback
        prefer_popular_first = self.config.prefer_popular_first
        randomize_links = self.config.randomize_links

        downloads: List[Path] = []
        tier_used = None
        session_ids = set()

        def _key(vid: Dict) -> str:
            return (vid.get("id") or vid.get("url") or "").strip()

        def _filtered(videos: List[Dict]) -> List[Dict]:
            items: List[Dict] = []
            for vid in videos:
                key = _key(vid)
                if not key:
                    continue
                if key in session_ids:
                    continue
                if dup_ctrl and vid.get("id") and self.config.is_downloaded(vid["id"]):
                    continue
                items.append(vid)
            if randomize_links:
                random.shuffle(items)
            return items

        def _consume(videos: List[Dict], label: str):
            nonlocal tier_used
            for vid in videos:
                if self._stop or len(downloads) >= n_target:
                    return
                url = vid.get("url", "")
                if not url:
                    continue

                self.progress.emit(f"Download: {vid.get('title', 'Untitled')[:60]}")
                fp = download_video(url, self.creator_folder / "downloads", self.ffmpeg, self.progress.emit)
                if not fp:
                    continue

                downloads.append(fp)
                if vid.get("id"):
                    self.config.add_downloaded_id(vid["id"])
                session_ids.add(_key(vid))
                tier_used = label
                self.config.append_activity_event(
                    "download_completed",
                    {"video_id": vid.get("id", ""), "title": vid.get("title", ""), "tier": label},
                )
                self.progress.emit(f"Progress: {len(downloads)}/{n_target}")

        # Fallback mode: no creator URL, use folder links directly.
        if not (self.creator_url or "").strip():
            self.progress.emit("Creator URL missing, using local *_links*.txt files")
            self.config.append_activity_event("link_extraction", {"source": "local_links_files"})
            local_entries = read_links_from_creator_folder(self.creator_folder)
            if randomize_links:
                random.shuffle(local_entries)
            _consume(_filtered(local_entries), "Folder Links")
        else:
            self.progress.emit("Tier 1: Latest videos")
            latest = get_video_list(self.creator_url, max_count=max(n_target * 4, 20), mode="latest")
            _consume(_filtered(latest), "Tier 1: Latest Videos")

        def _weekly_pass():
            week_index = 0
            while not self._stop and len(downloads) < n_target and week_index <= 8:
                remaining = n_target - len(downloads)
                start = datetime.now() - timedelta(days=(week_index + 1) * 7)
                end = datetime.now() - timedelta(days=week_index * 7)
                label = "Tier 2: Latest Week" if week_index == 0 else f"Tier 3: Previous Week -{week_index}"
                self.progress.emit(f"{label} ({remaining} needed)")
                weekly = get_video_list(
                    self.creator_url,
                    max_count=max(remaining * 4, 20),
                    mode="latest",
                    dateafter=start.strftime("%Y%m%d"),
                    datebefore=end.strftime("%Y%m%d"),
                )
                _consume(_filtered(weekly), label)
                week_index += 1

        def _popular_pass():
            if self._stop or len(downloads) >= n_target or not use_popular_fallback:
                return
            remaining = n_target - len(downloads)
            self.progress.emit(f"Popular fallback ({remaining} needed)")
            popular = get_video_list(self.creator_url, max_count=max(remaining * 4, 20), mode="popular")
            _consume(_filtered(popular), "Popular Fallback")

        if (self.creator_url or "").strip():
            if prefer_popular_first:
                _popular_pass()
                _weekly_pass()
            else:
                _weekly_pass()
                _popular_pass()

        if downloads and not self._stop:
            mode = self.config.editing_mode
            if mode == "split":
                out_dir = self.creator_folder / "split_output"
                for fp in downloads:
                    if self._stop:
                        break
                    parts = split_video(fp, out_dir, self.config.split_duration, self.ffmpeg)
                    self.config.append_activity_event(
                        "output_finalized",
                        {"mode": "split", "source": fp.name, "parts": len(parts)},
                    )
            elif mode == "preset" and self.config.preset_name:
                out_dir = self.creator_folder / "edited_output"
                for fp in downloads:
                    if self._stop:
                        break
                    out = apply_preset(fp, out_dir, self.config.preset_name, self.ffmpeg)
                    self.config.append_activity_event(
                        "output_finalized",
                        {"mode": "preset", "source": fp.name, "output": out.name if out else ""},
                    )

        count = len(downloads)
        status = "success" if count >= n_target else ("partial" if count > 0 else "failed")
        self.config.update_last_activity(status, tier_used or "N/A", count)
        self.config.save()

        result["success"] = count > 0
        result["downloaded"] = count
        result["tier_used"] = tier_used
        self.progress.emit(f"Done: {count}/{n_target} | Tier: {tier_used or 'N/A'}")
