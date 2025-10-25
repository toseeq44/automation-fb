"""
modules/video_downloader/core.py
BULLETPROOF Multi-Method Video Downloader

FEATURES:
- 5 download methods with fallback
- Smart folder processing (auto-detect creator folders)
- Triple cookie system
- Crash protection
- Per-creator downloads to their own folders
"""

import yt_dlp
import os
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
import re
import tempfile
import subprocess
import typing
import json


# ============ HELPER FUNCTIONS ============

def _safe_filename(s: str) -> str:
    """Sanitize filename - crash protected"""
    try:
        s = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s.strip())
        return s[:200] if s else "video"
    except Exception:
        return "video"


def _extract_creator_from_url(url: str) -> str:
    """Extract creator from URL for folder organization"""
    try:
        url_lower = url.lower()

        # YouTube
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            match = re.search(r'/@([^/?#]+)', url_lower)
            if match:
                return match.group(1)
            match = re.search(r'/channel/([^/?#]+)', url_lower)
            if match:
                return match.group(1)

        # Instagram
        elif 'instagram.com' in url_lower:
            match = re.search(r'instagram\.com/([^/?#]+)', url_lower)
            if match and match.group(1) not in ['p', 'reel', 'tv']:
                return match.group(1)

        # TikTok
        elif 'tiktok.com' in url_lower:
            match = re.search(r'tiktok\.com/@([^/?#]+)', url_lower)
            if match:
                return match.group(1)

        # Twitter/Facebook
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            match = re.search(r'(?:twitter|x)\.com/([^/?#]+)', url_lower)
            if match:
                return match.group(1)
        elif 'facebook.com' in url_lower:
            match = re.search(r'facebook\.com/([^/?#]+)', url_lower)
            if match:
                return match.group(1)
    except Exception:
        pass

    return "downloads"


# ============ VIDEO DOWNLOADER THREAD ============

class VideoDownloaderThread(QThread):
    """BULLETPROOF Video Downloader with 5 methods + crash protection"""

    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    download_speed = pyqtSignal(str)
    eta = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    video_complete = pyqtSignal(str)

    def __init__(self, urls, save_path, options, parent=None):
        super().__init__(parent)

        # Handle both string and list inputs
        if isinstance(urls, str):
            self.urls = [u.strip() for u in urls.replace(',', '\n').splitlines() if u.strip()]
        else:
            self.urls = [u.strip() for u in urls if u.strip()]

        self.save_path = save_path
        self.options = options
        self.cancelled = False
        self.success_count = 0
        self._temp_files = []

        # Auto-retry settings
        self.max_retries = options.get('max_retries', 3)
        self.retry_count = {}

    def get_cookie_file(self, url):
        """
        TRIPLE FALLBACK COOKIE SYSTEM - crash protected
        """
        try:
            url_lower = url.lower()

            # Get cookies directory
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            cookies_dir = project_root / "cookies"
            cookies_dir.mkdir(parents=True, exist_ok=True)

            # PRIORITY 1: cookies/cookies.txt (Universal)
            universal_cookie = cookies_dir / "cookies.txt"
            if universal_cookie.exists() and universal_cookie.stat().st_size > 10:
                return str(universal_cookie)

            # PRIORITY 2: Platform-specific cookies
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

            # PRIORITY 3: Desktop/toseeq-cookies.txt
            desktop_cookie = Path.home() / "Desktop" / "toseeq-cookies.txt"
            if desktop_cookie.exists() and desktop_cookie.stat().st_size > 10:
                return str(desktop_cookie)

        except Exception:
            pass

        return None

    def _method1_ytdlp_standard(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """METHOD 1: Standard yt-dlp download"""
        try:
            self.progress.emit("🔄 Method 1: yt-dlp standard download")

            ydl_opts = {
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'format': self.options.get('quality', 'best'),
                'quiet': False,
                'no_warnings': False,
                'retries': 10,
                'fragment_retries': 10,
                'continuedl': True,
                'progress_hooks': [self._progress_hook],
            }

            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.progress.emit("✅ Method 1 SUCCESS")
            return True

        except Exception as e:
            self.progress.emit(f"⚠️ Method 1 failed: {str(e)[:100]}")
            return False

    def _method2_ytdlp_with_options(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """METHOD 2: yt-dlp with platform-specific options"""
        try:
            self.progress.emit("🔄 Method 2: yt-dlp with optimizations")

            ydl_opts = {
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'format': self.options.get('quality', 'best'),
                'quiet': False,
                'retries': 15,
                'fragment_retries': 15,
                'continuedl': True,
                'nocheckcertificate': True,
                'prefer_insecure': True,
                'geo_bypass': True,
                'progress_hooks': [self._progress_hook],
            }

            # Platform-specific optimizations
            url_lower = url.lower()
            if 'youtube.com' in url_lower:
                ydl_opts['extractor_args'] = {'youtube': {'player_client': ['android', 'web']}}
            elif 'instagram.com' in url_lower:
                ydl_opts['extractor_args'] = {'instagram': {'api_version': '2'}}

            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.progress.emit("✅ Method 2 SUCCESS")
            return True

        except Exception as e:
            self.progress.emit(f"⚠️ Method 2 failed: {str(e)[:100]}")
            return False

    def _method3_ytdlp_subprocess(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """METHOD 3: yt-dlp via subprocess (sometimes more reliable)"""
        try:
            self.progress.emit("🔄 Method 3: yt-dlp subprocess")

            cmd = [
                'yt-dlp',
                '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                '-f', self.options.get('quality', 'best'),
                '--retries', '15',
                '--fragment-retries', '15',
                '--continue',
                '--no-check-certificate'
            ]

            if cookie_file:
                cmd.extend(['--cookies', cookie_file])

            cmd.append(url)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes max
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                self.progress.emit("✅ Method 3 SUCCESS")
                return True
            else:
                self.progress.emit(f"⚠️ Method 3 failed: {result.stderr[:100]}")
                return False

        except subprocess.TimeoutExpired:
            self.progress.emit("⚠️ Method 3 timeout (30 minutes)")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ Method 3 failed: {str(e)[:100]}")
            return False

    def _method4_ffmpeg_download(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """METHOD 4: Direct stream download with ffmpeg"""
        try:
            self.progress.emit("🔄 Method 4: ffmpeg stream download")

            # Get stream URL first
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'format': 'best',
            }

            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = info['url']
                title = _safe_filename(info.get('title', 'video'))

            # Download with ffmpeg
            output_file = os.path.join(output_path, f"{title}.mp4")
            cmd = [
                'ffmpeg',
                '-i', stream_url,
                '-c', 'copy',
                '-y',
                output_file
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=1800
            )

            if result.returncode == 0 and os.path.exists(output_file):
                self.progress.emit("✅ Method 4 SUCCESS")
                return True
            else:
                self.progress.emit("⚠️ Method 4 failed")
                return False

        except Exception as e:
            self.progress.emit(f"⚠️ Method 4 failed: {str(e)[:100]}")
            return False

    def _method5_alternative_extractors(self, url: str, output_path: str) -> bool:
        """METHOD 5: Try alternative extractors"""
        try:
            self.progress.emit("🔄 Method 5: Alternative extractors")

            # Try different extractor options
            extractors = [
                {'prefer_free_formats': True},
                {'extract_flat': False, 'force_generic_extractor': True},
                {'youtube_include_dash_manifest': False},
            ]

            for i, extra_opts in enumerate(extractors, 1):
                try:
                    ydl_opts = {
                        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                        'format': 'best',
                        'quiet': True,
                        'no_warnings': True,
                        **extra_opts
                    }

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])

                    self.progress.emit(f"✅ Method 5 variation {i} SUCCESS")
                    return True
                except:
                    continue

            self.progress.emit("⚠️ Method 5 failed: All variations failed")
            return False

        except Exception as e:
            self.progress.emit(f"⚠️ Method 5 failed: {str(e)[:100]}")
            return False

    def download_video_all_methods(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """
        BULLETPROOF: Try all 5 methods sequentially until success
        """
        methods = [
            self._method1_ytdlp_standard,
            self._method2_ytdlp_with_options,
            self._method3_ytdlp_subprocess,
            self._method4_ffmpeg_download,
            self._method5_alternative_extractors,
        ]

        for method in methods:
            if self.cancelled:
                return False

            try:
                # Try method with cookie if available
                if 'ffmpeg' in method.__name__ or 'alternative' in method.__name__:
                    success = method(url, output_path)
                else:
                    success = method(url, output_path, cookie_file)

                if success:
                    return True
            except Exception as e:
                self.progress.emit(f"Method error: {str(e)[:100]}")
                continue

        return False

    def _progress_hook(self, d):
        """Progress callback for yt-dlp"""
        try:
            if d['status'] == 'downloading':
                if 'total_bytes' in d:
                    percent = int(d['downloaded_bytes'] / d['total_bytes'] * 100)
                    self.progress_percent.emit(percent)

                if 'speed' in d and d['speed']:
                    speed_mb = d['speed'] / 1024 / 1024
                    self.download_speed.emit(f"{speed_mb:.2f} MB/s")

                if 'eta' in d and d['eta']:
                    self.eta.emit(f"{d['eta']} seconds")

            elif d['status'] == 'finished':
                self.progress.emit("✅ Download complete, processing...")

        except Exception:
            pass

    def run(self):
        """Main download loop - crash protected"""
        try:
            if not self.urls:
                self.finished.emit(False, "❌ No URLs provided")
                return

            total = len(self.urls)
            self.progress.emit("="*60)
            self.progress.emit(f"🚀 STARTING DOWNLOAD: {total} videos")
            self.progress.emit("="*60)

            for i, url in enumerate(self.urls, 1):
                if self.cancelled:
                    break

                self.progress.emit(f"\n{'='*60}")
                self.progress.emit(f"📥 [{i}/{total}] {url[:60]}...")
                self.progress.emit(f"{'='*60}")

                # Get cookie file
                cookie_file = self.get_cookie_file(url)
                if cookie_file:
                    self.progress.emit(f"🍪 Using cookies: {Path(cookie_file).name}")

                # Determine output path (creator-specific if possible)
                creator = _extract_creator_from_url(url)
                if creator != "downloads":
                    output_path = os.path.join(self.save_path, f"@{creator}")
                else:
                    output_path = self.save_path

                os.makedirs(output_path, exist_ok=True)

                # Try all methods
                success = self.download_video_all_methods(url, output_path, cookie_file)

                if success:
                    self.success_count += 1
                    self.progress.emit(f"✅ [{i}/{total}] Downloaded successfully")
                    self.video_complete.emit(url)
                else:
                    self.progress.emit(f"❌ [{i}/{total}] ALL 5 METHODS FAILED")

                # Update overall progress
                pct = int((i / total) * 100)
                self.progress_percent.emit(pct)

            if self.cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. Downloaded {self.success_count}/{total} videos.")
                return

            # Final summary
            self.progress.emit("\n" + "="*60)
            self.progress.emit("🎉 DOWNLOAD COMPLETE!")
            self.progress.emit("="*60)
            self.progress.emit(f"✅ Success: {self.success_count}/{total} videos")
            self.progress.emit(f"❌ Failed: {total - self.success_count}/{total} videos")
            self.progress.emit("="*60)

            success_msg = f"✅ Downloaded {self.success_count}/{total} videos"
            self.finished.emit(True, success_msg)

        except Exception as e:
            error_msg = f"❌ Critical error: {str(e)[:200]}"
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg)

    def cancel(self):
        """Cancel download - safe"""
        self.cancelled = True
        self.progress.emit("⚠️ Cancelling...")
