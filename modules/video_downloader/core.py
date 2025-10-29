"""Core implementation for the smart video downloader."""

import os
import subprocess
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yt_dlp
from PyQt5.QtCore import QThread, pyqtSignal

from .url_utils import (
    coerce_bool,
    extract_urls,
    normalize_url,
    quality_to_format,
)
from .history_manager import HistoryManager

# ===================== HELPERS ====================

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

    # default safeguards so attribute lookups never explode even if init fails mid-way
    skip_recent_window = True

    def __init__(self, urls, save_path, options, parent=None, bulk_mode_data=None):
        super().__init__(parent)
        # Accept flexible input for URLs (string, list, dicts from Link Grabber, etc.)
        self.urls = extract_urls(urls)
        self.save_path = save_path
        # Ensure options behave like a dict so feature flags don't break older callers
        if options is None:
            self.options = {}
        elif isinstance(options, dict):
            self.options = options
        else:
            # Some legacy callers pass QVariants/objects – fall back to empty dict but keep reference
            try:
                self.options = dict(options)
            except Exception:
                self.options = {}
        self.cancelled = False
        self.success_count = 0
        self.skipped_count = 0
        self.skip_recent_window = coerce_bool(
            self.options.get('skip_recent_window'),
            default=self.skip_recent_window,
        )
        self.max_retries = self.options.get('max_retries', 3)
        self.force_all_methods = bool(self.options.get('force_all_methods', False))
        # Map quality preference to yt-dlp format selection if caller didn't supply one
        format_override = self.options.get('format')
        if not format_override:
            quality_pref = self.options.get('quality')
            format_override = quality_to_format(quality_pref)
        self.format_override = format_override

        # Bulk mode support
        self.bulk_mode_data = bulk_mode_data
        self.history_manager = None
        self.is_bulk_mode = bulk_mode_data and bulk_mode_data.get('enabled')

        if self.is_bulk_mode:
            self.history_manager = bulk_mode_data.get('history_manager')
            self.bulk_creators = bulk_mode_data.get('creators', {})
            # Only create tracking files in bulk mode
            self.downloaded_links_file = Path(save_path) / ".downloaded_links.txt"
            self.downloaded_links = self._load_downloaded_links()
        else:
            # Single mode: NO tracking files
            self.bulk_creators = {}
            self.downloaded_links_file = None
            self.downloaded_links = set()

    def _load_downloaded_links(self) -> set:
        """Load downloaded links (bulk mode only)"""
        if not self.is_bulk_mode or not self.downloaded_links_file:
            return set()  # Single mode: never load files

        try:
            if self.downloaded_links_file.exists():
                with open(self.downloaded_links_file, 'r', encoding='utf-8') as f:
                    return set(line.strip() for line in f if line.strip())
        except Exception:
            pass
        return set()

    def _mark_as_downloaded(self, url: str):
        """Mark URL as downloaded (bulk mode only)"""
        # TRIPLE SAFETY CHECK: Never create files in single mode!
        if not self.is_bulk_mode:
            return  # Single mode: NO file operations

        if not self.downloaded_links_file:
            return  # Extra safety: no file path set

        try:
            normalized = normalize_url(url)
            self.downloaded_links.add(normalized)

            # Write to file (only in bulk mode)
            with open(self.downloaded_links_file, 'a', encoding='utf-8') as f:
                f.write(f"{normalized}\n")
        except Exception as e:
            self.progress.emit(f"⚠️ Could not save download record: {str(e)[:50]}")

    def _is_already_downloaded(self, url: str) -> bool:
        """Check if already downloaded (bulk mode only)"""
        if not self.is_bulk_mode:
            return False  # Never skip in single mode

        normalized = normalize_url(url)
        return normalized in self.downloaded_links

    # Removed old timestamp logic - now using history.json only

    def _cleanup_tracking_files(self, folder_path: str):
        """Remove any leftover tracking files (for single mode cleanup)"""
        if self.is_bulk_mode:
            return  # Don't cleanup in bulk mode

        try:
            folder = Path(folder_path)
            if not folder.exists():
                return

            # Remove old tracking files if they exist
            tracking_files = [
                '.downloaded_links.txt',
                '.last_download_time.txt',
                '.download_history.txt',  # Any other variants
            ]

            for filename in tracking_files:
                file_path = folder / filename
                if file_path.exists():
                    file_path.unlink()
                    self.progress.emit(f"🧹 Removed leftover file: {filename}")

        except Exception as e:
            # Silent fail - not critical
            pass

    def _remove_from_source_txt(self, url: str, source_folder: str):
        """Remove URL from source txt file (bulk mode only)"""
        if not self.is_bulk_mode:
            return  # Skip in single mode

        try:
            source_path = Path(source_folder)
            if not source_path.exists(): return
            for txt_file in source_path.glob("*.txt"):
                if txt_file.name.startswith('.'): continue
                try:
                    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    target = url.strip()
                    if not target:
                        continue
                    target_lower = target.lower()
                    new_lines = [
                        line
                        for line in lines
                        if target not in line and target_lower not in line.lower()
                    ]
                    if len(new_lines) != len(lines):
                        with open(txt_file, 'w', encoding='utf-8') as f:
                            f.writelines(new_lines)
                        self.progress.emit(f"🗑️ Removed from {txt_file.name}")
                except Exception:
                    continue
        except Exception:
            pass

    def get_cookie_file(self, url, source_folder=None):
        """Return the most relevant cookies file for the given URL."""

        try:
            candidates = []
            platform = _detect_platform(url)

            def _extend_with_platform_variants(base_path: Path):
                if not base_path:
                    return
                names = ["cookies.txt"]
                if platform != 'other':
                    names.insert(0, f"{platform}.txt")
                for name in names:
                    candidate = base_path / name
                    if candidate not in candidates:
                        candidates.append(candidate)

            if source_folder:
                folder_path = Path(source_folder)
                _extend_with_platform_variants(folder_path)
                cookies_sub = folder_path / "cookies"
                _extend_with_platform_variants(cookies_sub)
                parent_cookies = folder_path.parent / "cookies"
                if parent_cookies != cookies_sub:
                    _extend_with_platform_variants(parent_cookies)

            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            cookies_dir = project_root / "cookies"
            cookies_dir.mkdir(parents=True, exist_ok=True)

            if platform != 'other':
                platform_cookie = cookies_dir / f"{platform}.txt"
                _extend_with_platform_variants(platform_cookie.parent)

            universal_cookie = cookies_dir / "cookies.txt"
            if universal_cookie not in candidates:
                candidates.append(universal_cookie)

            desktop_cookie = Path.home() / "Desktop" / "toseeq-cookies.txt"
            if desktop_cookie not in candidates:
                candidates.append(desktop_cookie)

            for candidate in candidates:
                try:
                    if candidate and candidate.exists() and candidate.stat().st_size > 10:
                        return str(candidate)
                except Exception:
                    continue
        except Exception:
            pass
        return None

    # -----------------------
    # ==== Download Methods per Platform ====

    def _method1_batch_file_approach(self, url, output_path, cookie_file=None):
        try:
            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] 🚀 Method 1: YT-DLP Standard")

            format_string = self.format_override or 'best'
            cmd = [
                'yt-dlp',
                '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                '--rm-cache-dir',
                '-f', format_string,
                '--restrict-filenames', '--no-warnings', '--retries', str(self.max_retries),
                '--continue', '--no-check-certificate',
                '--no-playlist',  # Don't download playlists
            ]
            if cookie_file:
                cmd.extend(['--cookies', cookie_file])
                self.progress.emit(f"   🍪 Using cookies: {Path(cookie_file).name}")
            cmd.append(url)

            self.progress.emit(f"   ⏳ Starting download...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, encoding='utf-8', errors='replace')

            elapsed = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                self.progress.emit(f"   ✅ SUCCESS in {elapsed:.1f}s")
                return True
            else:
                error_msg = result.stderr[:300] if result.stderr else "Unknown error"
                self.progress.emit(f"   ❌ FAILED ({elapsed:.1f}s)")
                self.progress.emit(f"   📝 Error: {error_msg}")
            return False
        except subprocess.TimeoutExpired:
            self.progress.emit(f"   ⏱️ TIMEOUT (30min limit)")
            return False
        except Exception as e:
            self.progress.emit(f"   ❌ Exception: {str(e)[:100]}")
            return False

    def _method2_tiktok_special(self, url, output_path, cookie_file=None):
        try:
            if 'tiktok.com' not in url.lower():
                return False

            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] 🎵 Method 2: TikTok Special")

            # Try simple format first (avoids format selection errors)
            tiktok_formats = ['best', 'worst', 'bestvideo+bestaudio/best']

            for i, fmt in enumerate(tiktok_formats, 1):
                try:
                    self.progress.emit(f"   🔄 Attempt {i}/{len(tiktok_formats)} (format: {fmt})")

                    cmd = [
                        'yt-dlp',
                        '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                        '-f', fmt,
                        '--no-playlist',
                        '--geo-bypass',
                        '--user-agent', 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
                        '--restrict-filenames',
                        '--no-warnings',
                        '--retries', str(self.max_retries),
                    ]

                    if cookie_file:
                        cmd.extend(['--cookies', cookie_file])

                    cmd.append(url)

                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, encoding='utf-8', errors='replace')

                    if result.returncode == 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        self.progress.emit(f"   ✅ SUCCESS in {elapsed:.1f}s")
                        return True
                    else:
                        error_snippet = result.stderr[:150] if result.stderr else "Unknown"
                        self.progress.emit(f"   ❌ Failed: {error_snippet}")

                except Exception as e:
                    self.progress.emit(f"   ❌ Attempt {i} error: {str(e)[:50]}")
                    continue

            elapsed = (datetime.now() - start_time).total_seconds()
            self.progress.emit(f"   ⚠️ All attempts failed ({elapsed:.1f}s)")
            return False

        except Exception as e:
            self.progress.emit(f"   ❌ TikTok special error: {str(e)[:100]}")
            return False

    def _method3_optimized_ytdlp(self, url, output_path, cookie_file=None):
        try:
            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] 🔄 Method 3: yt-dlp with Cookies")

            format_string = self.format_override or 'best'
            ydl_opts = {
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'format': format_string,
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
                self.progress.emit(f"   🍪 Using: {Path(cookie_file).name}")
            else:
                self.progress.emit(f"   ⚠️ No cookies (may fail for private content)")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            elapsed = (datetime.now() - start_time).total_seconds()
            self.progress.emit(f"   ✅ SUCCESS in {elapsed:.1f}s")
            return True

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0
            error_msg = str(e)
            self.progress.emit(f"   ❌ FAILED ({elapsed:.1f}s)")

            # Give specific hints based on error
            if 'login required' in error_msg.lower() or 'rate' in error_msg.lower():
                self.progress.emit(f"   💡 Hint: Need cookies for this content")
            elif 'private' in error_msg.lower():
                self.progress.emit(f"   💡 Hint: Content is private")

            self.progress.emit(f"   📝 Error: {error_msg[:200]}")
            return False

    def _method_instagram_enhanced(self, url, output_path, cookie_file=None):
        """Enhanced Instagram downloader with multiple fallbacks"""
        try:
            if 'instagram.com' not in url.lower():
                return False

            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] 📸 Instagram Enhanced Method")

            # Try 1: With cookie file if available
            if cookie_file and Path(cookie_file).exists():
                self.progress.emit(f"   🍪 Attempt 1: Using cookie file")
                cmd = [
                    'yt-dlp',
                    '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                    '--cookies', cookie_file,
                    '-f', 'best',
                    '--no-playlist',
                    '--restrict-filenames',
                    '--no-warnings',
                    url
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    self.progress.emit(f"   ✅ SUCCESS with cookies ({elapsed:.1f}s)")
                    return True
                else:
                    self.progress.emit(f"   ❌ Cookie method failed")

            # Try 2: Browser cookies (Chrome)
            self.progress.emit(f"   🌐 Attempt 2: Trying browser cookies (Chrome)")
            cmd = [
                'yt-dlp',
                '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                '--cookies-from-browser', 'chrome',
                '-f', 'best',
                '--no-playlist',
                '--restrict-filenames',
                '--no-warnings',
                url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                self.progress.emit(f"   ✅ SUCCESS with browser cookies ({elapsed:.1f}s)")
                return True
            else:
                self.progress.emit(f"   ❌ Browser cookie method failed")

            # Try 3: Firefox cookies
            self.progress.emit(f"   🦊 Attempt 3: Trying Firefox cookies")
            cmd[3] = 'firefox'  # Replace 'chrome' with 'firefox'
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                self.progress.emit(f"   ✅ SUCCESS with Firefox cookies ({elapsed:.1f}s)")
                return True

            elapsed = (datetime.now() - start_time).total_seconds()
            self.progress.emit(f"   ❌ All Instagram attempts failed ({elapsed:.1f}s)")
            self.progress.emit(f"   💡 Tip: Login to Instagram in your browser first")
            return False

        except Exception as e:
            self.progress.emit(f"   ❌ Instagram enhanced error: {str(e)[:100]}")
            return False

    def _method_instaloader(self, url, output_path, cookie_file=None):
        try:
            if 'instagram.com' not in url.lower():
                return False
            try:
                import instaloader
            except ImportError:
                self.progress.emit("⚠️ Instaloader not installed; skipping fallback")
                return False

            self.progress.emit("📸 Instaloader fallback")
            match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)", url, re.IGNORECASE)
            if not match:
                self.progress.emit("⚠️ Could not detect Instagram shortcode for Instaloader")
                return False

            shortcode = match.group(1)
            loader = instaloader.Instaloader(
                dirname_pattern=os.path.join(output_path, "{target}"),
                filename_pattern="{shortcode}",
                download_videos=True,
                download_video_thumbnails=False,
                download_pictures=False,
                download_comments=False,
                save_metadata=False,
                quiet=True,
                compress_json=False,
            )

            if cookie_file:
                try:
                    cookies_dict = {}
                    with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as handle:
                        for line in handle:
                            stripped = line.strip()
                            if not stripped or stripped.startswith('#'):
                                continue
                            parts = stripped.split('\t')
                            if len(parts) >= 7:
                                cookies_dict[parts[5]] = parts[6]
                    if cookies_dict:
                        loader.context._session.cookies.update(cookies_dict)
                except Exception as cookie_error:
                    self.progress.emit(f"⚠️ Instaloader cookie load failed: {str(cookie_error)[:60]}")

            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            target = post.owner_username or "instagram"
            loader.download_post(post, target=target)
            self.progress.emit("✅ Instaloader SUCCESS")
            return True
        except Exception as e:
            self.progress.emit(f"⚠️ Instaloader error: {str(e)[:100]}")
            return False

    def _method_gallery_dl(self, url, output_path, cookie_file=None):
        """gallery-dl fallback for Instagram, Twitter, etc."""
        try:
            self.progress.emit("🖼️ gallery-dl fallback")
            cmd = [
                'gallery-dl',
                '--dest', output_path,
                '--filename', '{title}_{id}.{extension}',
                '--no-mtime',
            ]

            if cookie_file:
                cmd.extend(['--cookies', cookie_file])
                self.progress.emit(f"🍪 Using cookies: {Path(cookie_file).name}")

            cmd.append(url)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                self.progress.emit("✅ gallery-dl SUCCESS!")
                return True
            else:
                error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                self.progress.emit(f"⚠️ gallery-dl failed: {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            self.progress.emit("⚠️ gallery-dl timeout")
            return False
        except FileNotFoundError:
            self.progress.emit("⚠️ gallery-dl not installed")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ gallery-dl error: {str(e)[:100]}")
            return False

    def _method6_youtube_dl_fallback(self, url, output_path, cookie_file=None):
        """youtube-dl as final fallback (older but sometimes works)"""
        try:
            self.progress.emit("🔄 youtube-dl fallback (legacy)")
            format_string = self.format_override or 'best'
            cmd = [
                'youtube-dl',
                '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                '-f', format_string,
                '--no-warnings',
                '--retries', str(self.max_retries),
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
                timeout=900,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                self.progress.emit("✅ youtube-dl SUCCESS!")
                return True
            else:
                self.progress.emit("⚠️ youtube-dl failed")
                return False

        except subprocess.TimeoutExpired:
            self.progress.emit("⚠️ youtube-dl timeout")
            return False
        except FileNotFoundError:
            self.progress.emit("⚠️ youtube-dl not installed")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ youtube-dl error: {str(e)[:100]}")
            return False

    def _method4_alternative_formats(self, url, output_path, cookie_file=None):
        try:
            self.progress.emit("🔄 Method 4: Alternative formats")
            format_options = ['best[ext=mp4]', 'bestvideo+bestaudio', 'best']
            if self.format_override and self.format_override not in format_options:
                format_options.insert(0, self.format_override)
            elif self.format_override:
                # Prioritize selected format
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

            # Show mode clearly
            mode_name = "🔹 BULK MODE" if self.is_bulk_mode else "🔸 SINGLE MODE"
            self.progress.emit("="*60)
            self.progress.emit(f"🚀 SMART DOWNLOADER STARTING - {mode_name}")
            self.progress.emit(f"📊 Total links: {total}")

            if self.is_bulk_mode:
                self.progress.emit(f"📂 Creators: {len(self.bulk_creators)}")
                self.progress.emit("✅ History tracking: ON")
                self.progress.emit("✅ Auto URL cleanup: ON")
                self.progress.emit(f"📝 Track file: {self.downloaded_links_file.name}")
            else:
                self.progress.emit("📁 Save: Desktop/Toseeq Downloads")
                self.progress.emit("⚡ Simple mode: No tracking, no extra files")
                self.progress.emit("🚫 File creation: DISABLED")
                # Clean up any leftover tracking files from old runs
                self._cleanup_tracking_files(self.save_path)

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
                                    raw_url = line.strip()
                                    if not raw_url:
                                        continue
                                    key = normalize_url(raw_url)
                                    if key:
                                        url_folder_map[key] = root
                        except Exception:
                            continue
            # Fallback: direct URLs go to main save_path
            for url in self.urls:
                key = normalize_url(url)
                if key not in url_folder_map:
                    url_folder_map[key] = self.save_path
            processed = 0
            for url in self.urls:
                if self.cancelled: break
                folder = url_folder_map.get(normalize_url(url), self.save_path)
                os.makedirs(folder, exist_ok=True)
                # Skip logic handled by history.json in bulk mode
                processed += 1
                if self._is_already_downloaded(url):
                    self.progress.emit(f"⏭️ [{processed}/{total}] Already downloaded, skipping...")
                    self.skipped_count += 1
                    continue
                self.progress.emit(f"\n📥 [{processed}/{total}] {url[:80]}...")
                cookie_file = self.get_cookie_file(url, folder)
                # Platform-wise methods with enhanced fallbacks
                platform = _detect_platform(url)
                if platform == 'tiktok':
                    methods = [
                        self._method2_tiktok_special,
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method4_alternative_formats,
                        self._method5_force_ipv4,
                        self._method6_youtube_dl_fallback,
                    ]
                elif platform == 'instagram':
                    methods = [
                        self._method_instagram_enhanced,  # NEW: Try browser cookies first
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method_gallery_dl,
                        self._method_instaloader,
                        self._method4_alternative_formats,
                    ]
                elif platform == 'twitter':
                    methods = [
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method_gallery_dl,
                        self._method4_alternative_formats,
                        self._method5_force_ipv4,
                    ]
                else:
                    methods = [
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method4_alternative_formats,
                        self._method5_force_ipv4,
                        self._method6_youtube_dl_fallback,
                    ]

                # Force all methods adds extras
                if not self.force_all_methods:
                    # Limit to first 3-4 methods for speed
                    methods = methods[:4]
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
                    # Timestamp tracking handled by history.json
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

            # Update history.json for bulk mode
            if self.history_manager and self.bulk_creators:
                self.progress.emit("\n📝 Updating download history...")
                try:
                    # Track downloads per creator
                    creator_stats = {}  # {creator: {'success': 0, 'failed': 0}}

                    # Count successes/failures per creator
                    for creator, creator_info in self.bulk_creators.items():
                        creator_links = set(creator_info.get('links', []))
                        success = 0
                        failed = 0

                        for url in self.urls:
                            if url in creator_links:
                                if url in self.downloaded_links:
                                    success += 1
                                else:
                                    failed += 1

                        creator_stats[creator] = {'success': success, 'failed': failed}

                    # Update history for each creator
                    for creator, stats in creator_stats.items():
                        status = 'success' if stats['failed'] == 0 else ('partial' if stats['success'] > 0 else 'failed')
                        self.history_manager.update_creator(
                            creator,
                            downloaded_count=stats['success'],
                            failed_count=stats['failed'],
                            status=status
                        )
                        self.progress.emit(f"  ✓ {creator}: {stats['success']} downloaded, {stats['failed']} failed")

                        # Remove successfully downloaded URLs from links file
                        if stats['success'] > 0:
                            links_file = self.bulk_creators[creator].get('links_file')
                            if links_file and Path(links_file).exists():
                                try:
                                    # Read current content
                                    with open(links_file, 'r', encoding='utf-8', errors='ignore') as f:
                                        lines = f.readlines()

                                    # Filter out downloaded links
                                    new_lines = []
                                    for line in lines:
                                        url_in_line = line.strip()
                                        if not url_in_line or url_in_line.startswith('#'):
                                            new_lines.append(line)
                                            continue

                                        # Check if this URL was downloaded
                                        is_downloaded = False
                                        for dl_url in self.downloaded_links:
                                            if url_in_line in dl_url or dl_url in url_in_line:
                                                is_downloaded = True
                                                break

                                        if not is_downloaded:
                                            new_lines.append(line)

                                    # Write back
                                    with open(links_file, 'w', encoding='utf-8') as f:
                                        f.writelines(new_lines)

                                    self.progress.emit(f"  🗑️ Updated {Path(links_file).name}")
                                except Exception as e:
                                    self.progress.emit(f"  ⚠️ Failed to update {Path(links_file).name}: {str(e)[:50]}")

                    self.progress.emit("✅ History updated!")
                except Exception as e:
                    self.progress.emit(f"⚠️ History update failed: {str(e)[:100]}")

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
