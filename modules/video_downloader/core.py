"""
modules/video_downloader/core.py
SMART Video Downloader with Resume & TikTok Fix

FEATURES:
- TikTok multi-method approach (bypass IP blocks)
- Download tracking (no duplicate downloads)
- Auto-remove downloaded links from txt files
- 24-hour folder skip logic
- Resume capability
- Smart detection
"""

import yt_dlp
import os
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
import re
import subprocess
import typing
import json
from datetime import datetime, timedelta


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


def _normalize_url(url: str) -> str:
    """Normalize URL for tracking"""
    try:
        # Remove tracking params
        url = re.sub(r'[?&]utm_[^&]*', '', url)
        url = re.sub(r'[?&]fbclid=[^&]*', '', url)
        # Extract video ID for consistency
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


# ============ VIDEO DOWNLOADER THREAD ============

class VideoDownloaderThread(QThread):
    """SMART Video Downloader - Resume + TikTok Fix"""

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
        self.skipped_count = 0

        # Auto-retry settings
        self.max_retries = options.get('max_retries', 3)

        # Tracking files
        self.downloaded_links_file = Path(save_path) / ".downloaded_links.txt"
        self.downloaded_links = self._load_downloaded_links()

    def _load_downloaded_links(self) -> set:
        """Load previously downloaded links"""
        try:
            if self.downloaded_links_file.exists():
                with open(self.downloaded_links_file, 'r', encoding='utf-8') as f:
                    return set(line.strip() for line in f if line.strip())
        except Exception:
            pass
        return set()

    def _mark_as_downloaded(self, url: str):
        """Mark link as downloaded"""
        try:
            normalized = _normalize_url(url)
            self.downloaded_links.add(normalized)

            # Append to file
            with open(self.downloaded_links_file, 'a', encoding='utf-8') as f:
                f.write(f"{normalized}\n")
        except Exception as e:
            self.progress.emit(f"⚠️ Could not save download record: {str(e)[:50]}")

    def _is_already_downloaded(self, url: str) -> bool:
        """Check if link already downloaded"""
        normalized = _normalize_url(url)
        return normalized in self.downloaded_links

    def _should_skip_folder(self, folder_path: str) -> bool:
        """Check if folder was downloaded in last 24 hours"""
        try:
            timestamp_file = Path(folder_path) / ".last_download_time.txt"
            if timestamp_file.exists():
                with open(timestamp_file, 'r') as f:
                    last_time_str = f.read().strip()
                    last_time = datetime.fromisoformat(last_time_str)

                    # Check if within 24 hours
                    if datetime.now() - last_time < timedelta(hours=24):
                        return True
        except Exception:
            pass
        return False

    def _update_folder_timestamp(self, folder_path: str):
        """Update folder's last download timestamp"""
        try:
            timestamp_file = Path(folder_path) / ".last_download_time.txt"
            with open(timestamp_file, 'w') as f:
                f.write(datetime.now().isoformat())
        except Exception:
            pass

    def _remove_from_source_txt(self, url: str, source_folder: str):
        """Remove downloaded link from source txt file"""
        try:
            # Find txt files in source folder
            source_path = Path(source_folder)
            if not source_path.exists():
                return

            for txt_file in source_path.glob("*.txt"):
                if txt_file.name.startswith('.'):
                    continue  # Skip hidden files

                try:
                    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()

                    # Filter out the downloaded URL
                    new_lines = [line for line in lines if url.strip() not in line]

                    if len(new_lines) != len(lines):
                        # URL was found and removed
                        with open(txt_file, 'w', encoding='utf-8') as f:
                            f.writelines(new_lines)
                        self.progress.emit(f"🗑️ Removed from {txt_file.name}")
                except Exception:
                    continue

        except Exception:
            pass

    def get_cookie_file(self, url):
        """TRIPLE FALLBACK COOKIE SYSTEM - crash protected"""
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
        """METHOD 1: EXACT BATCH FILE APPROACH (FASTEST!)"""
        try:
            self.progress.emit("🚀 Method 1: BATCH FILE APPROACH")

            cmd = [
                'yt-dlp',
                '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                '--rm-cache-dir',
                '--throttled-rate', '500K',
                '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
                '--restrict-filenames',
                '--no-warnings',
                '--retries', str(self.max_retries),
                '--continue',
                '--no-check-certificate',
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
            else:
                error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                self.progress.emit(f"⚠️ Method 1 failed: {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            self.progress.emit("⚠️ Method 1 timeout")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ Method 1 error: {str(e)[:100]}")
            return False

    def _method2_tiktok_special(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """METHOD 2: TikTok Special (Multiple TikTok-specific approaches)"""
        try:
            if 'tiktok.com' not in url.lower():
                return False  # Only for TikTok

            self.progress.emit("🎵 Method 2: TikTok SPECIAL (IP Block Bypass)")

            # Try 3 different TikTok approaches
            tiktok_approaches = [
                # Approach 1: Mobile user agent
                {
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36'
                    },
                    'extractor_args': {'tiktok': {'webpage_download': True}}
                },
                # Approach 2: Different extractor
                {
                    'format': 'best',
                    'http_headers': {
                        'User-Agent': 'okhttp'
                    }
                },
                # Approach 3: Via subprocess with geo-bypass
                None  # Subprocess approach
            ]

            for i, approach in enumerate(tiktok_approaches, 1):
                try:
                    self.progress.emit(f"🔄 TikTok Approach {i}/3...")

                    if approach is None:
                        # Subprocess approach
                        cmd = [
                            'yt-dlp',
                            '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                            '--geo-bypass',
                            '--user-agent', 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
                            '--restrict-filenames',
                            '--no-warnings',
                            url
                        ]

                        if cookie_file:
                            cmd.extend(['--cookies', cookie_file])

                        result = subprocess.run(cmd, capture_output=True, timeout=300)
                        if result.returncode == 0:
                            self.progress.emit(f"✅ TikTok Approach {i} SUCCESS!")
                            return True
                    else:
                        # yt-dlp library approach
                        ydl_opts = {
                            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                            'format': approach.get('format', 'best'),
                            'quiet': True,
                            'no_warnings': True,
                            'restrictfilenames': True,
                            'geo_bypass': True,
                        }

                        ydl_opts.update(approach)

                        if cookie_file:
                            ydl_opts['cookiefile'] = cookie_file

                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])

                        self.progress.emit(f"✅ TikTok Approach {i} SUCCESS!")
                        return True

                except Exception as e:
                    self.progress.emit(f"⚠️ TikTok Approach {i} failed: {str(e)[:50]}")
                    continue

            self.progress.emit("⚠️ All TikTok approaches failed")
            return False

        except Exception as e:
            self.progress.emit(f"⚠️ TikTok special error: {str(e)[:100]}")
            return False

    def _method3_optimized_ytdlp(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """METHOD 3: Optimized yt-dlp"""
        try:
            self.progress.emit("🔄 Method 3: Optimized yt-dlp")

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

            self.progress.emit("✅ Method 3 SUCCESS")
            return True

        except Exception as e:
            self.progress.emit(f"⚠️ Method 3 failed: {str(e)[:100]}")
            return False

    def _method4_alternative_formats(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """METHOD 4: Alternative formats"""
        try:
            self.progress.emit("🔄 Method 4: Alternative formats")

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

                    self.progress.emit(f"✅ Method 4 SUCCESS (format: {fmt})")
                    return True

                except Exception:
                    continue

            self.progress.emit("⚠️ Method 4 failed")
            return False

        except Exception as e:
            self.progress.emit(f"⚠️ Method 4 error: {str(e)[:100]}")
            return False

    def _progress_hook(self, d):
        """Progress hook for yt-dlp"""
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

    def download_video_all_methods(self, url: str, output_path: str, cookie_file: str = None) -> bool:
        """TRY ALL METHODS - TikTok gets special treatment!"""

        # Check if TikTok - use TikTok-specific methods first
        if 'tiktok.com' in url.lower():
            methods = [
                self._method2_tiktok_special,  # TikTok FIRST for TikTok URLs!
                self._method1_batch_file_approach,
                self._method3_optimized_ytdlp,
                self._method4_alternative_formats,
            ]
        else:
            methods = [
                self._method1_batch_file_approach,  # Batch file first for others
                self._method3_optimized_ytdlp,
                self._method4_alternative_formats,
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
        """Main download loop - SMART with resume capability"""
        try:
            if not self.urls:
                self.finished.emit(False, "❌ No URLs provided")
                return

            total = len(self.urls)
            self.progress.emit("="*60)
            self.progress.emit(f"🧠 SMART DOWNLOADER STARTING")
            self.progress.emit(f"📊 Total links: {total}")
            self.progress.emit(f"📍 Using batch file method + TikTok fix")
            self.progress.emit("="*60)

            # Group URLs by creator for smart folder handling
            creator_urls = {}
            for url in self.urls:
                creator = _extract_creator_from_url(url)
                if creator not in creator_urls:
                    creator_urls[creator] = []
                creator_urls[creator].append(url)

            processed = 0
            for creator, urls in creator_urls.items():
                if self.cancelled:
                    break

                # Determine folder
                if creator != "downloads":
                    creator_folder = os.path.join(self.save_path, f"@{creator}")
                else:
                    creator_folder = self.save_path

                os.makedirs(creator_folder, exist_ok=True)

                # Check 24-hour skip
                if self._should_skip_folder(creator_folder):
                    self.progress.emit(f"\n⏭️ SKIPPING @{creator} - Downloaded within 24 hours")
                    self.skipped_count += len(urls)
                    processed += len(urls)
                    continue

                self.progress.emit(f"\n{'='*60}")
                self.progress.emit(f"📁 Creator: @{creator} ({len(urls)} videos)")
                self.progress.emit(f"{'='*60}")

                creator_success = 0
                for i, url in enumerate(urls, 1):
                    if self.cancelled:
                        break

                    processed += 1

                    # Check if already downloaded
                    if self._is_already_downloaded(url):
                        self.progress.emit(f"⏭️ [{processed}/{total}] Already downloaded, skipping...")
                        self.skipped_count += 1
                        continue

                    self.progress.emit(f"\n📥 [{processed}/{total}] {url[:80]}...")

                    # Get cookie file
                    cookie_file = self.get_cookie_file(url)

                    # Try all methods
                    success = self.download_video_all_methods(url, creator_folder, cookie_file)

                    if success:
                        creator_success += 1
                        self.success_count += 1
                        self.progress.emit(f"✅ [{processed}/{total}] Downloaded!")

                        # Mark as downloaded
                        self._mark_as_downloaded(url)

                        # Remove from source txt (if in creator folder)
                        self._remove_from_source_txt(url, creator_folder)

                        self.video_complete.emit(url)
                    else:
                        self.progress.emit(f"❌ [{processed}/{total}] ALL METHODS FAILED")

                    # Update progress
                    pct = int((processed / total) * 100)
                    self.progress_percent.emit(pct)

                # Update folder timestamp if any success
                if creator_success > 0:
                    self._update_folder_timestamp(creator_folder)
                    self.progress.emit(f"✅ @{creator}: {creator_success}/{len(urls)} downloaded")

            # Final summary
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
