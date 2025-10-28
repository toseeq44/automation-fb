"""
modules/video_downloader/core.py
SMART Video Downloader with Resume, Platform Fallbacks & Accurate Folder Save

FEATURES:
- Every video always saves in the same folder as its link source text file
- TikTok multi-method (IP bypass, retries)
- Platform-specific fallback (YouTube, Instagram, Facebook, Twitter)
- Smart cookies: triple fallback
- Dupe skip (no repeated download)
- Remove downloaded link from its source txt
- Last-24-hour skip per folder
- Resume support, progress, speed, ETA, cancel
"""

import yt_dlp
import os
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
import re
import subprocess
from datetime import datetime, timedelta

# ===================== HELPERS ====================

def _safe_filename(s: str) -> str:
    try:
        s = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s.strip())
        return s[:200] if s else "video"
    except Exception:
        return "video"

def _normalize_url(url: str) -> str:
    try:
        url = re.sub(r'[?&]utm_[^&]*', '', url)
        url = re.sub(r'[?&]fbclid=[^&]*', '', url)
        if 'tiktok.com' in url:
            match = re.search(r'/video/(\d+)', url)
            if match:
                return f"tiktok_{match.group(1)}"
        elif 'youtube.com' in url or 'youtu.be' in url:
            match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', url)
            if match:
                return f"youtube_{match.group(1)}"
        elif 'instagram.com' in url:
            match = re.search(r'/(?:p|reel)/([^/?]+)', url)
            if match:
                return f"instagram_{match.group(1)}"
        return url.strip()
    except Exception:
        return url.strip()

def _detect_platform(url: str) -> str:
    url = url.lower()
    if 'tiktok.com' in url: return 'tiktok'
    if 'youtube.com' in url or 'youtu.be' in url: return 'youtube'
    if 'instagram.com' in url: return 'instagram'
    if 'facebook.com' in url or 'fb.com' in url: return 'facebook'
    if 'twitter.com' in url or 'x.com' in url: return 'twitter'
    return 'other'

# ===================== MAIN THREAD ====================
class VideoDownloaderThread(QThread):
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    download_speed = pyqtSignal(str)
    eta = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    video_complete = pyqtSignal(str)

    def __init__(self, urls, save_path, options, parent=None):
        super().__init__(parent)
        # Accept string/list input for URLs
        if isinstance(urls, str):
            self.urls = [u.strip() for u in urls.replace(',', '\n').splitlines() if u.strip()]
        else:
            self.urls = [u.strip() for u in urls if u.strip()]
        self.save_path = save_path
        self.options = options or {}
        self.cancelled = False
        self.success_count = 0
        self.skipped_count = 0
        self.max_retries = self.options.get('max_retries', 3)
        self.force_all_methods = bool(self.options.get('force_all_methods', False))
        self.format_override = self.options.get('format') or None
        self.skip_recent_window = bool(self.options.get('skip_recent_window', True))
        self.downloaded_links_file = Path(save_path) / ".downloaded_links.txt"
        self.downloaded_links = self._load_downloaded_links()

    def _load_downloaded_links(self) -> set:
        try:
            if self.downloaded_links_file.exists():
                with open(self.downloaded_links_file, 'r', encoding='utf-8') as f:
                    return set(line.strip() for line in f if line.strip())
        except Exception:
            pass
        return set()

    def _mark_as_downloaded(self, url: str):
        try:
            normalized = _normalize_url(url)
            self.downloaded_links.add(normalized)
            with open(self.downloaded_links_file, 'a', encoding='utf-8') as f:
                f.write(f"{normalized}\n")
        except Exception as e:
            self.progress.emit(f"⚠️ Could not save download record: {str(e)[:50]}")

    def _is_already_downloaded(self, url: str) -> bool:
        normalized = _normalize_url(url)
        return normalized in self.downloaded_links

    def _should_skip_folder(self, folder_path: str) -> bool:
        if not self.skip_recent_window:
            return False
        try:
            timestamp_file = Path(folder_path) / ".last_download_time.txt"
            if timestamp_file.exists():
                with open(timestamp_file, 'r') as f:
                    last_time_str = f.read().strip()
                    last_time = datetime.fromisoformat(last_time_str)
                    if datetime.now() - last_time < timedelta(hours=24):
                        return True
        except Exception:
            pass
        return False

    def _update_folder_timestamp(self, folder_path: str):
        try:
            timestamp_file = Path(folder_path) / ".last_download_time.txt"
            with open(timestamp_file, 'w') as f:
                f.write(datetime.now().isoformat())
        except Exception:
            pass

    def _remove_from_source_txt(self, url: str, source_folder: str):
        try:
            source_path = Path(source_folder)
            if not source_path.exists(): return
            for txt_file in source_path.glob("*.txt"):
                if txt_file.name.startswith('.'): continue
                try:
                    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    new_lines = [line for line in lines if url.strip() not in line]
                    if len(new_lines) != len(lines):
                        with open(txt_file, 'w', encoding='utf-8') as f:
                            f.writelines(new_lines)
                        self.progress.emit(f"🗑️ Removed from {txt_file.name}")
                except Exception:
                    continue
        except Exception:
            pass

    def get_cookie_file(self, url):
        try:
            url_lower = url.lower()
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            cookies_dir = project_root / "cookies"
            cookies_dir.mkdir(parents=True, exist_ok=True)
            # Universal
            universal_cookie = cookies_dir / "cookies.txt"
            if universal_cookie.exists() and universal_cookie.stat().st_size > 10:
                return str(universal_cookie)
            # Platform-specific
            platform_map = {
                'youtube': 'youtube.txt',
                'instagram': 'instagram.txt',
                'tiktok': 'tiktok.txt',
                'facebook': 'facebook.txt',
                'twitter': 'twitter.txt'
            }
            for platform, cookie_file in platform_map.items():
                if platform in url_lower:
                    platform_cookie = cookies_dir / cookie_file
                    if platform_cookie.exists() and platform_cookie.stat().st_size > 10:
                        return str(platform_cookie)
            # Desktop fallback
            desktop_cookie = Path.home() / "Desktop" / "toseeq-cookies.txt"
            if desktop_cookie.exists() and desktop_cookie.stat().st_size > 10:
                return str(desktop_cookie)
        except Exception:
            pass
        return None

    # -----------------------
    # ==== Download Methods per Platform ====

    def _method1_batch_file_approach(self, url, output_path, cookie_file=None):
        try:
            self.progress.emit("🚀 Method 1: YT-DLP BATCH FILE")
            default_format = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
            format_candidates = []
            if self.format_override:
                format_candidates.append(self.format_override)
            format_candidates.append(default_format)

            for idx, fmt in enumerate(format_candidates, 1):
                if idx > 1:
                    self.progress.emit(f"🔁 Retrying Method 1 with fallback format ({fmt})")
                cmd = [
                    'yt-dlp',
                    '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                    '--rm-cache-dir', '--throttled-rate', '500K',
                    '-f', fmt,
                    '--restrict-filenames', '--no-warnings', '--retries', str(self.max_retries),
                    '--continue', '--no-check-certificate'
                ]
                if cookie_file:
                    cmd.extend(['--cookies', cookie_file])
                    self.progress.emit(f"🍪 Using cookies: {Path(cookie_file).name}")
                cmd.append(url)
                self.progress.emit("⏳ Downloading...")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=1800,
                    encoding='utf-8',
                    errors='replace'
                )
                if result.returncode == 0:
                    self.progress.emit("✅ Method 1 SUCCESS!")
                    return True
                error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                self.progress.emit(f"⚠️ Method 1 failed (format {fmt}): {error_msg}")
            return False
        except subprocess.TimeoutExpired:
            self.progress.emit("⚠️ Method 1 timeout")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ Method 1 error: {str(e)[:100]}")
            return False

    def _method2_tiktok_special(self, url, output_path, cookie_file=None):
        try:
            if 'tiktok.com' not in url.lower():
                return False
            self.progress.emit("🎵 TikTok SPECIAL (multi approach)")
            tiktok_approaches = [
                {
                    'http_headers': {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36'},
                    'extractor_args': {'tiktok': {'webpage_download': True}}
                },
                {'format': 'best', 'http_headers': {'User-Agent': 'okhttp'}},
                None
            ]
            for i, approach in enumerate(tiktok_approaches, 1):
                try:
                    self.progress.emit(f"🔄 TikTok Approach {i}/3...")
                    if approach is None:
                        # Subprocess with geobypass etc
                        cmd = [
                            'yt-dlp',
                            '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                            '--geo-bypass', '--user-agent', 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
                            '--restrict-filenames', '--no-warnings', url
                        ]
                        if cookie_file:
                            cmd.extend(['--cookies', cookie_file])
                        result = subprocess.run(cmd, capture_output=True, timeout=300)
                        if result.returncode == 0:
                            self.progress.emit(f"✅ TikTok Approach {i} SUCCESS!")
                            return True
                    else:
                        base_opts = {
                            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                            'quiet': True, 'no_warnings': True,
                            'restrictfilenames': True, 'geo_bypass': True
                        }
                        base_opts.update(approach)
                        format_candidates = []
                        if self.format_override:
                            format_candidates.append(self.format_override)
                        default_fmt = base_opts.get('format', 'best')
                        if default_fmt not in format_candidates:
                            format_candidates.append(default_fmt)
                        for fmt in format_candidates:
                            try:
                                opts = dict(base_opts)
                                opts['format'] = fmt
                                if cookie_file:
                                    opts['cookiefile'] = cookie_file
                                with yt_dlp.YoutubeDL(opts) as ydl:
                                    ydl.download([url])
                                self.progress.emit(f"✅ TikTok Approach {i} SUCCESS!")
                                return True
                            except Exception as inner_e:
                                self.progress.emit(f"⚠️ TikTok Approach {i} failed (format {fmt}): {str(inner_e)[:60]}")
                                continue
                except Exception as e:
                    self.progress.emit(f"⚠️ TikTok Approach {i} failed: {str(e)[:50]}")
                    continue
            self.progress.emit("⚠️ All TikTok approaches failed")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ TikTok special error: {str(e)[:100]}")
            return False

    def _method3_optimized_ytdlp(self, url, output_path, cookie_file=None):
        try:
            self.progress.emit("🔄 Method 3: Optimized yt-dlp")
            default_format = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
            format_candidates = []
            if self.format_override:
                format_candidates.append(self.format_override)
            format_candidates.append(default_format)
            for idx, fmt in enumerate(format_candidates, 1):
                try:
                    if idx > 1:
                        self.progress.emit(f"🔁 Method 3 retry with fallback format ({fmt})")
                    ydl_opts = {
                        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                        'format': fmt,
                        'quiet': True, 'no_warnings': True, 'retries': self.max_retries,
                        'fragment_retries': self.max_retries, 'continuedl': True, 'nocheckcertificate': True,
                        'restrictfilenames': True, 'progress_hooks': [self._progress_hook],
                    }
                    if cookie_file:
                        ydl_opts['cookiefile'] = cookie_file
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    self.progress.emit("✅ Method 3 SUCCESS")
                    return True
                except Exception as inner_e:
                    self.progress.emit(f"⚠️ Method 3 failed (format {fmt}): {str(inner_e)[:100]}")
                    continue
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ Method 3 error: {str(e)[:100]}")
            return False

    def _method4_alternative_formats(self, url, output_path, cookie_file=None):
        try:
            self.progress.emit("🔄 Method 4: Alternative formats")
            format_options = ['best[ext=mp4]', 'bestvideo+bestaudio', 'best']
            if self.format_override:
                if self.format_override in format_options:
                    format_options.remove(self.format_override)
                format_options.insert(0, self.format_override)
            for fmt in format_options:
                try:
                    ydl_opts = {
                        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                        'format': fmt,
                        'quiet': True, 'no_warnings': True, 'retries': self.max_retries,
                        'continuedl': True, 'nocheckcertificate': True, 'restrictfilenames': True,
                    }
                    if cookie_file: ydl_opts['cookiefile'] = cookie_file
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    self.progress.emit(f"✅ Method 4 SUCCESS (format: {fmt})")
                    return True
                except Exception:
                    continue
            self.progress.emit("⚠️ Method 4 failed")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ Method 4 error: {str(e)[:100]}")
            return False

    def _method5_force_ipv4(self, url, output_path, cookie_file=None):
        try:
            self.progress.emit("🔄 Method 5: Force IPv4 fallback")
            format_string = self.format_override or 'best'
            cmd = [
                'yt-dlp',
                '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                '-f', format_string,
                '--force-ipv4', '--no-warnings', '--geo-bypass',
                '--retries', str(self.max_retries), '--ignore-errors', '--continue',
                '--restrict-filenames', '--no-check-certificate'
            ]
            if cookie_file:
                cmd.extend(['--cookies', cookie_file])
                self.progress.emit(f"🍪 Using cookies: {Path(cookie_file).name}")
            cmd.append(url)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900,
                encoding='utf-8',
                errors='replace'
            )
            if result.returncode == 0:
                self.progress.emit("✅ Method 5 SUCCESS!")
                return True
            error_msg = result.stderr[:200] if result.stderr else "Unknown error"
            self.progress.emit(f"⚠️ Method 5 failed: {error_msg}")
            return False
        except subprocess.TimeoutExpired:
            self.progress.emit("⚠️ Method 5 timeout")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ Method 5 error: {str(e)[:100]}")
            return False

    def _progress_hook(self, d):
        try:
            if self.cancelled:
                raise Exception("Cancelled by user")
            if d['status'] == 'downloading':
                speed = d.get('speed', 0)
                if speed:
                    speed_mb = speed / (1024 * 1024)
                    self.download_speed.emit(f"{speed_mb:.2f} MB/s")
                eta = d.get('eta', 0)
                if eta:
                    mins, secs = divmod(eta, 60)
                    self.eta.emit(f"{int(mins)}m {int(secs)}s")
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                if total > 0:
                    percent = int((downloaded / total) * 100)
                    self.progress_percent.emit(percent)
        except Exception:
            pass

    # ---- MAIN DOWNLOAD LOOP ----

    def run(self):
        try:
            if not self.urls:
                self.finished.emit(False, "❌ No URLs provided")
                return
            total = len(self.urls)
            self.progress.emit("="*60)
            self.progress.emit("🧠 SMART DOWNLOADER STARTING")
            self.progress.emit(f"📊 Total links: {total}")
            self.progress.emit("="*60)
            if self.force_all_methods:
                self.progress.emit("🛡️ Multi-strategy fallback enabled")
            # Map URLs to their source folder by looking up all *.txt in save_path (recursive)
            url_folder_map = {}
            for root, dirs, files in os.walk(self.save_path):
                for fname in files:
                    if fname.endswith(".txt") and not fname.startswith('.'):
                        txt_path = Path(root) / fname
                        try:
                            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                                for line in f:
                                    url = line.strip()
                                    if url:
                                        url_folder_map[url] = root
                        except Exception:
                            continue
            # Fallback: direct URLs go to main save_path
            for url in self.urls:
                if url not in url_folder_map:
                    url_folder_map[url] = self.save_path
            processed = 0
            for url in self.urls:
                if self.cancelled: break
                folder = url_folder_map.get(url, self.save_path)
                os.makedirs(folder, exist_ok=True)
                if self._should_skip_folder(folder):
                    self.progress.emit(f"\n⏭️ SKIPPING (in 24h): [{folder}] {url[:60]}")
                    self.skipped_count += 1
                    processed += 1
                    continue
                processed += 1
                if self._is_already_downloaded(url):
                    self.progress.emit(f"⏭️ [{processed}/{total}] Already downloaded, skipping...")
                    self.skipped_count += 1
                    continue
                self.progress.emit(f"\n📥 [{processed}/{total}] {url[:80]}...")
                cookie_file = self.get_cookie_file(url)
                # Platform-wize methods
                platform = _detect_platform(url)
                if platform == 'tiktok':
                    methods = [
                        self._method2_tiktok_special,
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method4_alternative_formats,
                    ]
                else:
                    methods = [
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method4_alternative_formats,
                    ]
                if self.force_all_methods:
                    methods.append(self._method5_force_ipv4)
                # Try all methods
                success = False
                for method in methods:
                    if self.cancelled: break
                    try:
                        if method(url, folder, cookie_file):
                            success = True
                            break
                    except Exception as e:
                        self.progress.emit(f"Method error: {str(e)[:100]}")
                if success:
                    self.success_count += 1
                    self.progress.emit(f"✅ [{processed}/{total}] Downloaded!")
                    self._mark_as_downloaded(url)
                    self._remove_from_source_txt(url, folder)
                    self._update_folder_timestamp(folder)
                    self.video_complete.emit(url)
                else:
                    self.progress.emit(f"❌ [{processed}/{total}] ALL METHODS FAILED")
                pct = int((processed / total) * 100)
                self.progress_percent.emit(pct)
            self.progress.emit("\n" + "="*60)
            self.progress.emit("📊 FINAL REPORT:")
            self.progress.emit(f"✅ Successfully downloaded: {self.success_count}")
            self.progress.emit(f"⏭️ Skipped (already done): {self.skipped_count}")
            self.progress.emit(f"❌ Failed: {total - self.success_count - self.skipped_count}")
            self.progress.emit("="*60)
            if self.cancelled:
                self.finished.emit(False, f"⚠️ Cancelled - {self.success_count} downloaded")
            elif self.success_count + self.skipped_count == total:
                self.finished.emit(True, f"✅ ALL DONE! {self.success_count} new, {self.skipped_count} skipped")
            elif self.success_count > 0:
                self.finished.emit(True, f"⚠️ Partial: {self.success_count} downloaded, {self.skipped_count} skipped")
            else:
                self.finished.emit(False, f"❌ Failed - 0 downloaded")
        except Exception as e:
            self.progress.emit(f"❌ CRITICAL ERROR: {str(e)[:200]}")
            self.finished.emit(False, f"❌ Error: {str(e)[:100]}")

    def cancel(self):
        self.cancelled = True
        self.progress.emit("⚠️ Cancellation requested...")
