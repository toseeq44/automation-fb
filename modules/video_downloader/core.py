"""
modules/video_downloader/core.py
FAST Multi-Method Video Downloader (Based on Batch File Approach)

FEATURES:
- Method 1: EXACT batch file approach (FASTEST - runs first!)
- Method 2: Simple optimized yt-dlp
- Method 3: Alternative format fallback
- Smart folder processing (auto-detect creator folders)
- Triple cookie system
- Crash protection
"""

import yt_dlp
import os
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
import re
import subprocess
import typing


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
    """FAST Video Downloader - Batch File Approach (runs first!)"""

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

        # Auto-retry settings
        self.max_retries = options.get('max_retries', 3)

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

    def _method1_batch_file_approach(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """
        METHOD 1: EXACT BATCH FILE APPROACH (FASTEST!)
        This is your proven fast method - runs FIRST

        Command from batch file:
        yt-dlp --cookies cookies.txt --rm-cache-dir --throttled-rate 500K
               -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
               --restrict-filenames --no-warnings --retries 3
        """
        try:
            self.progress.emit("🚀 Method 1: BATCH FILE APPROACH (Fast!)")

            cmd = [
                'yt-dlp',
                '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                '--rm-cache-dir',  # Clear cache (from batch file)
                '--throttled-rate', '500K',  # Prevent rate limiting (from batch file)
                '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',  # EXACT format from batch
                '--restrict-filenames',  # Safe filenames (from batch file)
                '--no-warnings',  # Clean output (from batch file)
                '--retries', str(self.max_retries),  # From batch file
                '--continue',  # Resume downloads
                '--no-check-certificate',  # Bypass SSL issues
            ]

            # Add cookies if available
            if cookie_file:
                cmd.extend(['--cookies', cookie_file])
                self.progress.emit(f"🍪 Using cookies: {Path(cookie_file).name}")

            cmd.append(url)

            # Run command
            self.progress.emit("⏳ Downloading with batch file method...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes max
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                self.progress.emit("✅ Method 1 SUCCESS - Download complete!")
                return True
            else:
                error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                self.progress.emit(f"⚠️ Method 1 failed: {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            self.progress.emit("⚠️ Method 1 timeout (30 min exceeded)")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ Method 1 error: {str(e)[:100]}")
            return False

    def _method2_optimized_ytdlp(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """METHOD 2: Optimized yt-dlp with library"""
        try:
            self.progress.emit("🔄 Method 2: Optimized yt-dlp")

            ydl_opts = {
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
                'quiet': True,
                'no_warnings': True,
                'retries': self.max_retries,
                'fragment_retries': self.max_retries,
                'continuedl': True,
                'nocheckcertificate': True,
                'restrictfilenames': True,
                'progress_hooks': [self._progress_hook],
            }

            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.progress.emit("✅ Method 2 SUCCESS")
            return True

        except Exception as e:
            self.progress.emit(f"⚠️ Method 2 failed: {str(e)[:100]}")
            return False

    def _method3_alternative_formats(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """METHOD 3: Alternative format combinations"""
        try:
            self.progress.emit("🔄 Method 3: Alternative formats")

            # Try different format combinations
            format_options = [
                'best[ext=mp4]',
                'bestvideo+bestaudio',
                'best',
            ]

            for fmt in format_options:
                try:
                    ydl_opts = {
                        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                        'format': fmt,
                        'quiet': True,
                        'no_warnings': True,
                        'retries': self.max_retries,
                        'continuedl': True,
                        'nocheckcertificate': True,
                        'restrictfilenames': True,
                    }

                    if cookie_file:
                        ydl_opts['cookiefile'] = cookie_file

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])

                    self.progress.emit(f"✅ Method 3 SUCCESS (format: {fmt})")
                    return True

                except Exception:
                    continue

            self.progress.emit("⚠️ Method 3 failed - all formats tried")
            return False

        except Exception as e:
            self.progress.emit(f"⚠️ Method 3 error: {str(e)[:100]}")
            return False

    def _progress_hook(self, d):
        """Progress hook for yt-dlp"""
        try:
            if self.cancelled:
                raise Exception("Cancelled by user")

            if d['status'] == 'downloading':
                # Extract speed
                speed = d.get('speed', 0)
                if speed:
                    speed_mb = speed / (1024 * 1024)
                    self.download_speed.emit(f"{speed_mb:.2f} MB/s")

                # Extract ETA
                eta = d.get('eta', 0)
                if eta:
                    mins, secs = divmod(eta, 60)
                    self.eta.emit(f"{int(mins)}m {int(secs)}s")

                # Extract progress
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                if total > 0:
                    percent = int((downloaded / total) * 100)
                    self.progress_percent.emit(percent)

        except Exception:
            pass

    def download_video_all_methods(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """
        TRY ALL 3 METHODS - BATCH FILE METHOD RUNS FIRST!
        """
        methods = [
            self._method1_batch_file_approach,  # FASTEST - runs first!
            self._method2_optimized_ytdlp,
            self._method3_alternative_formats,
        ]

        for method in methods:
            if self.cancelled:
                return False

            try:
                success = method(url, output_path, cookie_file)
                if success:
                    return True
            except Exception as e:
                self.progress.emit(f"Method error: {str(e)[:100]}")
                continue

        return False

    def cancel(self):
        """Cancel the download"""
        self.cancelled = True
        self.progress.emit("⚠️ Cancellation requested...")

    def run(self):
        """Main download loop - crash protected"""
        try:
            if not self.urls:
                self.finished.emit(False, "❌ No URLs provided")
                return

            total = len(self.urls)
            self.progress.emit("="*60)
            self.progress.emit(f"🚀 STARTING DOWNLOAD: {total} videos")
            self.progress.emit(f"📍 Using FAST batch file method first!")
            self.progress.emit("="*60)

            for i, url in enumerate(self.urls, 1):
                if self.cancelled:
                    break

                self.progress.emit(f"\n{'='*60}")
                self.progress.emit(f"📥 [{i}/{total}] {url[:80]}...")
                self.progress.emit(f"{'='*60}")

                # Get cookie file
                cookie_file = self.get_cookie_file(url)

                # Determine output path (creator-specific if possible)
                creator = _extract_creator_from_url(url)
                if creator != "downloads":
                    output_path = os.path.join(self.save_path, f"@{creator}")
                    self.progress.emit(f"📁 Creator: @{creator}")
                else:
                    output_path = self.save_path

                os.makedirs(output_path, exist_ok=True)

                # Try all methods (BATCH FILE METHOD FIRST!)
                success = self.download_video_all_methods(url, output_path, cookie_file)

                if success:
                    self.success_count += 1
                    self.progress.emit(f"✅ [{i}/{total}] Downloaded successfully!")
                    self.video_complete.emit(url)
                else:
                    self.progress.emit(f"❌ [{i}/{total}] ALL METHODS FAILED")

                # Update overall progress
                pct = int((i / total) * 100)
                self.progress_percent.emit(pct)

            # Final summary
            self.progress.emit("\n" + "="*60)
            if self.cancelled:
                self.finished.emit(False, f"⚠️ Cancelled - {self.success_count}/{total} downloaded")
            elif self.success_count == total:
                self.finished.emit(True, f"✅ ALL DONE! {self.success_count}/{total} videos downloaded")
            elif self.success_count > 0:
                self.finished.emit(True, f"⚠️ Partial success: {self.success_count}/{total} downloaded")
            else:
                self.finished.emit(False, f"❌ Failed - 0/{total} downloaded")

        except Exception as e:
            self.progress.emit(f"❌ CRITICAL ERROR: {str(e)[:200]}")
            self.finished.emit(False, f"❌ Error: {str(e)[:100]}")
