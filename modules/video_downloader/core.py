"""
modules/video_downloader/core.py
TRIPLE COOKIES FALLBACK SYSTEM:
1. cookies/cookies.txt (First priority)
2. cookies/platform_cookies.txt (Second priority)
3. Desktop/toseeq-cookies.txt (Third priority)
4. Browser auto cookies (Last fallback)
"""

import yt_dlp
import os
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
import re
import tempfile


class VideoDownloaderThread(QThread):
    """Video downloader with triple cookies fallback"""
    
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
    
    def get_cookie_file_triple_fallback(self, url):
        """
        TRIPLE FALLBACK SYSTEM:
        Priority 1: cookies/cookies.txt
        Priority 2: cookies/youtube_cookies.txt (platform-specific)
        Priority 3: Desktop/toseeq-cookies.txt
        Priority 4: Browser auto cookies
        """
        url_lower = url.lower()
        
        # Get project root and cookies directory
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        cookies_dir = project_root / "cookies"
        cookies_dir.mkdir(parents=True, exist_ok=True)
        
        # PRIORITY 1: cookies/cookies.txt (Universal)
        universal_cookie = cookies_dir / "cookies.txt"
        if universal_cookie.exists() and universal_cookie.stat().st_size > 10:
            self.progress.emit(f"✅ Using universal cookies: {universal_cookie.name}")
            return str(universal_cookie)
        
        # PRIORITY 2: Platform-specific cookies
        platform_map = {
            'youtube': 'youtube_cookies.txt',
            'instagram': 'instagram_cookies.txt',
            'tiktok': 'tiktok_cookies.txt',
            'facebook': 'facebook_cookies.txt',
            'twitter': 'twitter_cookies.txt'
        }
        
        for platform, cookie_file in platform_map.items():
            if platform in url_lower:
                platform_cookie = cookies_dir / cookie_file
                if platform_cookie.exists() and platform_cookie.stat().st_size > 10:
                    self.progress.emit(f"✅ Using {platform} cookies: {cookie_file}")
                    return str(platform_cookie)
        
        # PRIORITY 3: Desktop/toseeq-cookies.txt
        desktop_cookie = Path.home() / "Desktop" / "toseeq-cookies.txt"
        if desktop_cookie.exists() and desktop_cookie.stat().st_size > 10:
            self.progress.emit(f"✅ Using desktop cookies: toseeq-cookies.txt")
            return str(desktop_cookie)
        
        # PRIORITY 4: Browser auto cookies (last resort)
        self.progress.emit("🔄 No manual cookies found, trying browser cookies...")
        
        try:
            import browser_cookie3
            
            domain_map = {
                'youtube.com': '.youtube.com',
                'instagram.com': '.instagram.com',
                'tiktok.com': '.tiktok.com',
                'facebook.com': '.facebook.com',
                'twitter.com': '.twitter.com'
            }
            
            for domain_key, domain_val in domain_map.items():
                if domain_key in url_lower:
                    browsers = [
                        ('Chrome', browser_cookie3.chrome),
                        ('Edge', browser_cookie3.edge),
                        ('Firefox', browser_cookie3.firefox)
                    ]
                    
                    for browser_name, browser_func in browsers:
                        try:
                            cj = browser_func(domain_name=domain_val)
                            if len(cj) > 0:
                                temp_file = self._save_cookies_to_temp(cj)
                                if temp_file:
                                    self.progress.emit(f"✅ Using {browser_name} browser cookies")
                                    return temp_file
                        except:
                            continue
        except:
            pass
        
        self.progress.emit("⚠️ No cookies available (trying without cookies)")
        return None
    
    def _save_cookies_to_temp(self, cookiejar):
        """Save cookiejar to temp file"""
        try:
            temp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
            temp.write("# Netscape HTTP Cookie File\n")
            
            for cookie in cookiejar:
                domain = cookie.domain
                flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                path = cookie.path
                secure = 'TRUE' if cookie.secure else 'FALSE'
                expires = str(int(cookie.expires)) if cookie.expires else '0'
                name = cookie.name
                value = cookie.value
                
                line = f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n"
                temp.write(line)
            
            temp.close()
            self._temp_files.append(temp.name)
            return temp.name
        except:
            return None
    
    def cleanup_temp_files(self):
        """Clean up temp files"""
        for f in self._temp_files:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except:
                pass
        self._temp_files = []

    def clean_ansi(self, text):
        """Remove ANSI color codes"""
        return re.sub(r'\x1b\[[0-9;]*m', '', str(text)).strip()

    def progress_hook(self, d):
        """Progress callback from yt-dlp"""
        if self.cancelled:
            return

        try:
            if d['status'] == 'downloading':
                # Extract progress
                percent_str = self.clean_ansi(d.get('_percent_str', '0%'))
                percent = 0
                try:
                    percent = int(float(percent_str.replace('%', '').strip()))
                except:
                    percent = 0
                self.progress_percent.emit(min(percent, 100))

                # Extract speed and ETA
                speed = self.clean_ansi(d.get('_speed_str', 'N/A'))
                eta_time = self.clean_ansi(d.get('_eta_str', 'N/A'))

                # Get file info
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)

                info = d.get('info_dict', {})
                title = info.get('title', 'Unknown')
                if len(title) > 40:
                    title = title[:37] + "..."

                # Format size
                mb_downloaded = downloaded // 1024 // 1024
                mb_total = total // 1024 // 1024 if total > 0 else 0
                size_str = f"{mb_downloaded}MB/{mb_total}MB" if mb_total > 0 else f"{mb_downloaded}MB/??"

                # Emit signals
                self.progress.emit(f"📥 [{title}] {size_str} | {speed} | ETA: {eta_time}")
                self.download_speed.emit(speed)
                self.eta.emit(eta_time)

            elif d['status'] == 'finished':
                # Download complete
                filepath = d.get('filepath') or d.get('_filename')
                
                if not filepath and 'info_dict' in d:
                    info = d['info_dict']
                    ext = info.get('ext', 'mp4')
                    title = info.get('title', 'Unknown')
                    filepath = os.path.join(self.save_path, f"{title}.{ext}")
                
                filename = os.path.basename(filepath) if filepath else "Unknown.mp4"
                
                # Count success (only .mp4 files)
                if filename.endswith('.mp4'):
                    self.progress.emit(f"✅ Completed: {filename}")
                    self.video_complete.emit(filename)
                    self.success_count += 1

            elif d['status'] == 'error':
                error = d.get('error', 'Unknown error')
                self.progress.emit(f"❌ Error: {str(error)[:100]}")

        except Exception:
            pass  # Ignore hook errors

    def run(self):
        """Main download execution"""
        if not self.urls:
            self.finished.emit(False, "❌ No URLs provided")
            return

        # Create save directory
        try:
            os.makedirs(self.save_path, exist_ok=True)
        except Exception as e:
            self.finished.emit(False, f"❌ Cannot create folder: {str(e)}")
            return

        # Get cookies using triple fallback
        cookie_file = self.get_cookie_file_triple_fallback(self.urls[0]) if self.urls else None

        # Quality settings
        quality_map = {
            'Best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'Medium': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best',
            'Low': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best'
        }
        
        quality = self.options.get('quality', 'Best')
        format_string = quality_map.get(quality, quality_map['Best'])

        # Configure yt-dlp
        ydl_opts = {
            'format': format_string,
            'outtmpl': os.path.join(self.save_path, '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',  # Force merge to mp4
            'progress_hooks': [self.progress_hook],
            'retries': 5,
            'fragment_retries': 5,
            'ignoreerrors': False,
            'continuedl': True,
            'noplaylist': not self.options.get('playlist', False),
            'restrict_filenames': True,
            'windowsfilenames': True,
            'no_warnings': True,
            'quiet': False,
            'no_check_certificate': True,
            'keepvideo': False,  # Don't keep separate video/audio files
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',  # Convert to mp4
            }],
            'postprocessor_args': [
                '-c:v', 'copy',  # Copy video (fast)
                '-c:a', 'aac',   # AAC audio
                '-movflags', '+faststart'  # Web optimization
            ],
        }

        # Add cookies if available
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file

        # Additional options
        if self.options.get('subtitles'):
            ydl_opts['writesubtitles'] = True
            ydl_opts['writeautomaticsub'] = True
            ydl_opts['subtitleslangs'] = ['en', 'ur', 'all']
        
        if self.options.get('thumbnail'):
            ydl_opts['writethumbnail'] = True

        # Start download
        try:
            self.progress.emit(f"🚀 Starting download of {len(self.urls)} video(s)...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download(self.urls)
            
            # Cleanup
            self.cleanup_temp_files()
            
            # Success message
            if self.success_count == len(self.urls):
                msg = f"✅ Success! Downloaded {self.success_count}/{len(self.urls)} videos"
            elif self.success_count > 0:
                msg = f"⚠️ Partial: {self.success_count}/{len(self.urls)} videos downloaded"
            else:
                msg = f"❌ Failed: 0/{len(self.urls)} videos downloaded"
            
            self.finished.emit(self.success_count > 0, msg)
        
        except Exception as e:
            self.cleanup_temp_files()
            error = str(e)[:200]
            self.progress.emit(f"❌ Error: {error}")
            self.finished.emit(False, f"❌ Download failed: {error}")

    def cancel(self):
        """Cancel download"""
        self.cancelled = True
        self.cleanup_temp_files()
        self.progress.emit("⚠️ Cancelling download...")