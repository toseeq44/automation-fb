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
from modules.shared.auth_network_hub import AuthNetworkHub


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
    proxy_url: str = None,
    cookiefile: str = None,
) -> List[Dict]:
    normalized_url = CreatorConfig._normalize_profile_url(url) or url
    platform = _detect_platform(normalized_url)
    fetch_url = _popular_url(normalized_url, platform) if mode == "popular" else normalized_url

    opts = {
        "extract_flat": True,
        "playlistend": max(max_count, 10),
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "socket_timeout": 30,
    }
    if proxy_url:
        opts["proxy"] = proxy_url
    if cookiefile:
        opts["cookiefile"] = cookiefile
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
        # Hard guard: never allow bulk profile/reels URL to download many items.
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

    # Absolute safety net: if extractor still created multiple fresh videos, keep only one.
    try:
        fresh_videos = [
            p for p in output_folder.iterdir()
            if p.is_file() and p.name not in before_files and p.suffix.lower() in video_exts
        ]
        if len(fresh_videos) > 1:
            # Keep newest file and remove other newly created extras.
            fresh_videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            keep = fresh_videos[0]
            for extra in fresh_videos[1:]:
                try:
                    extra.unlink()
                except Exception:
                    pass
            if progress_cb:
                progress_cb(
                    f"    Enforced single-video cap: kept '{keep.name}', removed {len(fresh_videos) - 1} extra file(s)"
                )
            result_path[0] = keep
    except Exception:
        pass

    return result_path[0]


def _ffprobe_path(ffmpeg: str) -> str:
    if ffmpeg and ffmpeg != "ffmpeg":
        p = Path(ffmpeg)
        probe_name = "ffprobe.exe" if p.suffix.lower() == ".exe" else "ffprobe"
        sibling = p.with_name(probe_name)
        if sibling.exists():
            return str(sibling)
    return shutil.which("ffprobe") or "ffprobe"


def _probe_duration_seconds(input_path: Path, ffmpeg: str = "ffmpeg") -> float:
    # First try ffprobe (fast and structured), then fallback to ffmpeg stderr parsing.
    try:
        cmd = [
            _ffprobe_path(ffmpeg),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            value = (r.stdout or "").strip()
            sec = float(value)
            if sec > 0:
                return sec
    except Exception:
        pass

    try:
        r = subprocess.run(
            [ffmpeg, "-i", str(input_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = (r.stderr or "") + "\n" + (r.stdout or "")
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2))
            ss = float(m.group(3))
            sec = (hh * 3600) + (mm * 60) + ss
            if sec > 0:
                return sec
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

    parts: List[Path] = []
    start = 0.0
    idx = 1
    max_parts = 2000
    epsilon = 0.02
    min_tail_sec = 0.35
    min_valid_part_sec = 0.20

    # Remove stale split parts from previous runs for this same source file.
    for stale in output_folder.glob(f"{stem}_part*{out_ext}"):
        try:
            stale.unlink()
        except Exception:
            pass

    while start < duration - epsilon and idx <= max_parts:
        remaining = duration - start
        if remaining <= min_tail_sec:
            break
        chunk = min(segment_sec, remaining)
        out_path = output_folder / f"{stem}_part{idx:03d}{out_ext}"

        if progress_cb:
            progress_cb(f"    Split part {idx}: {start:.2f}s -> {start + chunk:.2f}s")

        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{chunk:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-fflags",
            "+genpts",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-fps_mode",
            "cfr",
            "-af",
            "aresample=async=1:first_pts=0",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-avoid_negative_ts",
            "make_zero",
            "-movflags",
            "+faststart",
            str(out_path),
            "-y",
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if r.returncode != 0:
                # Fallback command for edge files where explicit mapping fails.
                cmd2 = [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(input_path),
                    "-ss",
                    f"{start:.3f}",
                    "-t",
                    f"{chunk:.3f}",
                    "-fflags",
                    "+genpts",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "22",
                    "-pix_fmt",
                    "yuv420p",
                    "-fps_mode",
                    "cfr",
                    "-af",
                    "aresample=async=1:first_pts=0",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-avoid_negative_ts",
                    "make_zero",
                    str(out_path),
                    "-y",
                ]
                r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=1800)
                if r2.returncode != 0:
                    break

            if out_path.exists() and out_path.stat().st_size > 0:
                actual_part_sec = _probe_duration_seconds(out_path, ffmpeg)
                if actual_part_sec >= min_valid_part_sec:
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
        n_target = self.config.n_videos
        dup_ctrl = self.config.duplication_control
        use_popular_fallback = self.config.popular_fallback
        prefer_popular_first = self.config.prefer_popular_first
        randomize_links = self.config.randomize_links
        keep_original_after_edit = self.config.keep_original_after_edit

        ytdlp_state = self.auth_hub.resolve_ytdlp()
        if not ytdlp_state.get("usable"):
            self.progress.emit("Warning: yt-dlp executable unavailable/unusable; Python API fallback in use.")
            if ytdlp_state.get("error"):
                self.progress.emit(f"    yt-dlp detail: {ytdlp_state['error']}")
            self.progress.emit("    Tip: keep latest at C:\\yt-dlp\\yt-dlp.exe")

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

                platform = _detect_platform(url)
                cookie_file = self.auth_hub.pick_cookie_file(platform, str(self.creator_folder))
                active_proxy = self._active_proxy()
                self.progress.emit(f"Download: {vid.get('title', 'Untitled')[:60]}")
                fp = download_video(
                    url,
                    self.creator_folder,
                    self.ffmpeg,
                    self.progress.emit,
                    proxy_url=active_proxy,
                    cookiefile=cookie_file,
                )
                if not fp and active_proxy:
                    # Retry once on next proxy when available.
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
            creator_platform = _detect_platform(self.creator_url)
            creator_cookie = self.auth_hub.pick_cookie_file(creator_platform, str(self.creator_folder))
            latest = get_video_list(
                self.creator_url,
                max_count=max(n_target * 4, 20),
                mode="latest",
                proxy_url=self._active_proxy(),
                cookiefile=creator_cookie,
            )
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
                    proxy_url=self._active_proxy(),
                    cookiefile=self.auth_hub.pick_cookie_file(_detect_platform(self.creator_url), str(self.creator_folder)),
                )
                _consume(_filtered(weekly), label)
                week_index += 1

        def _popular_pass():
            if self._stop or len(downloads) >= n_target or not use_popular_fallback:
                return
            remaining = n_target - len(downloads)
            self.progress.emit(f"Popular fallback ({remaining} needed)")
            popular = get_video_list(
                self.creator_url,
                max_count=max(remaining * 4, 20),
                mode="popular",
                proxy_url=self._active_proxy(),
                cookiefile=self.auth_hub.pick_cookie_file(_detect_platform(self.creator_url), str(self.creator_folder)),
            )
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
                out_dir = self.creator_folder
                for fp in downloads:
                    if self._stop:
                        break
                    parts = split_video(
                        fp,
                        out_dir,
                        self.config.split_duration,
                        self.ffmpeg,
                        self.progress.emit,
                    )
                    self.config.append_activity_event(
                        "output_finalized",
                        {"mode": "split", "source": fp.name, "parts": len(parts)},
                    )
                    if parts and not keep_original_after_edit and fp.exists():
                        try:
                            fp.unlink()
                            self.progress.emit(f"Removed original: {fp.name}")
                        except Exception:
                            pass
            elif mode == "preset" and self.config.preset_name:
                out_dir = self.creator_folder
                for fp in downloads:
                    if self._stop:
                        break
                    out = apply_preset(fp, out_dir, self.config.preset_name, self.ffmpeg)
                    self.config.append_activity_event(
                        "output_finalized",
                        {"mode": "preset", "source": fp.name, "output": out.name if out else ""},
                    )
                    if out and not keep_original_after_edit and fp.exists():
                        try:
                            fp.unlink()
                            self.progress.emit(f"Removed original: {fp.name}")
                        except Exception:
                            pass

        count = len(downloads)
        status = "success" if count >= n_target else ("partial" if count > 0 else "failed")
        self.config.update_last_activity(status, tier_used or "N/A", count)
        self.config.save()

        result["success"] = count > 0
        result["downloaded"] = count
        result["tier_used"] = tier_used
        self.progress.emit(f"Done: {count}/{n_target} | Tier: {tier_used or 'N/A'}")
