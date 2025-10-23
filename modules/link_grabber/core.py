"""
modules/link_grabber/core.py - ENHANCED VERSION
Multi-platform link grabber with multiple fallback methods
Supports: YouTube, Instagram, TikTok, Facebook, Twitter
Features:
- Creator-specific folders
- Duplicate detection
- Multiple extraction methods per platform
- Comprehensive error handling
"""

from PyQt5.QtCore import QThread, pyqtSignal
from pathlib import Path
import os
import subprocess
import shlex
import tempfile
import re
import json
import typing
import time

# Helper: sanitize filenames
def _safe_filename(s: str) -> str:
    s = s.strip()
    s = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s)
    s = re.sub(r'\s+', '_', s)
    if not s:
        return "unknown"
    return s[:200]

# Helper: extract creator/username from URL
def _extract_creator_from_url(url: str, platform_key: str) -> str:
    try:
        u = url.strip().rstrip('/')

        # YouTube
        if platform_key == 'youtube':
            # @username format
            m = re.search(r'@([A-Za-z0-9_\-\.]+)', u)
            if m:
                return m.group(1)
            # /channel/ID format
            m = re.search(r'/channel/([^/?#]+)', u)
            if m:
                return m.group(1)
            # /c/username format
            m = re.search(r'/c/([^/?#]+)', u)
            if m:
                return m.group(1)
            # /user/username format
            m = re.search(r'/user/([^/?#]+)', u)
            if m:
                return m.group(1)

        # Instagram
        elif platform_key == 'instagram':
            m = re.search(r'instagram\.com/([^/?#]+)', u)
            if m:
                username = m.group(1)
                # Remove common paths
                if username not in ['p', 'reel', 'tv', 'stories', 'explore']:
                    return username

        # TikTok
        elif platform_key == 'tiktok':
            m = re.search(r'tiktok\.com/@([^/?#]+)', u)
            if m:
                return m.group(1)

        # Twitter/X
        elif platform_key == 'twitter':
            m = re.search(r'(?:twitter|x)\.com/([^/?#]+)', u)
            if m:
                username = m.group(1)
                # Remove common paths
                if username not in ['home', 'explore', 'notifications', 'messages', 'i']:
                    return username

        # Facebook
        elif platform_key == 'facebook':
            m = re.search(r'facebook\.com/([^/?#]+)', u)
            if m:
                username = m.group(1)
                # Remove common paths
                if username not in ['home', 'watch', 'groups', 'pages', 'gaming']:
                    return username

        # Fallback: use last part of URL
        parts = [p for p in u.split('/') if p]
        if parts:
            return parts[-1]

        return platform_key

    except Exception:
        return 'unknown'

# Detect platform from URL
def _detect_platform_key(url: str) -> str:
    u = url.lower()
    if 'youtube.com' in u or 'youtu.be' in u:
        return 'youtube'
    if 'instagram.com' in u:
        return 'instagram'
    if 'tiktok.com' in u:
        return 'tiktok'
    if 'facebook.com' in u or 'fb.com' in u or 'fb.watch' in u:
        return 'facebook'
    if 'twitter.com' in u or 'x.com' in u:
        return 'twitter'
    return 'unknown'

# Get manual cookie file
def _manual_cookie_path(cookies_dir: Path, platform_key: str) -> typing.Optional[str]:
    """
    Check multiple cookie file locations:
    1. Project cookies/ folder
    2. Desktop (desktop/toseeq-cookies.txt or platform-specific)
    """
    # Priority 1: Project cookies folder
    mapping = {
        'youtube': 'youtube_cookies.txt',
        'instagram': 'instagram_cookies.txt',
        'tiktok': 'tiktok_cookies.txt',
        'facebook': 'facebook_cookies.txt',
        'twitter': 'twitter_cookies.txt'
    }

    name = mapping.get(platform_key, f'{platform_key}_cookies.txt')
    p = cookies_dir / name
    if p.exists() and p.stat().st_size > 10:
        return str(p)

    # Priority 2: Universal cookies.txt
    universal = cookies_dir / 'cookies.txt'
    if universal.exists() and universal.stat().st_size > 10:
        return str(universal)

    # Priority 3: Desktop cookies
    desktop = Path.home() / "Desktop"
    desktop_cookie = desktop / "toseeq-cookies.txt"
    if desktop_cookie.exists() and desktop_cookie.stat().st_size > 10:
        return str(desktop_cookie)

    return None

# Try browser cookies
def _try_browser_cookies_tempfile(platform_key: str) -> typing.Optional[str]:
    try:
        import browser_cookie3 as bc3
    except Exception:
        return None

    domain_map = {
        'youtube': '.youtube.com',
        'instagram': '.instagram.com',
        'tiktok': '.tiktok.com',
        'facebook': '.facebook.com',
        'twitter': '.twitter.com'
    }
    domain = domain_map.get(platform_key, None)

    browsers = [
        getattr(bc3, 'chrome', None),
        getattr(bc3, 'edge', None),
        getattr(bc3, 'firefox', None)
    ]

    for bfunc in browsers:
        if not bfunc:
            continue
        try:
            cj = bfunc(domain_name=domain) if domain else bfunc()
            if cj and len(cj) > 0:
                tf = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
                tf.write("# Netscape HTTP Cookie File\n")
                for ck in cj:
                    d = getattr(ck, 'domain', '')
                    flag = 'TRUE' if d.startswith('.') else 'FALSE'
                    path = getattr(ck, 'path', '/')
                    secure = 'TRUE' if getattr(ck, 'secure', False) else 'FALSE'
                    expires = getattr(ck, 'expires', None)
                    exp = str(int(expires)) if expires else '0'
                    name = getattr(ck, 'name', '')
                    val = getattr(ck, 'value', '')
                    tf.write(f"{d}\t{flag}\t{path}\t{secure}\t{exp}\t{name}\t{val}\n")
                tf.close()
                return tf.name
        except Exception:
            continue
    return None


class EnhancedLinkExtractor:
    """
    Multi-method link extraction with fallbacks
    """

    def __init__(self, progress_callback=None):
        self.progress = progress_callback or (lambda x: None)
        self._temp_files = []

    def cleanup(self):
        """Clean up temporary files"""
        for tf in self._temp_files:
            try:
                if os.path.exists(tf):
                    os.unlink(tf)
            except:
                pass
        self._temp_files = []

    def extract_links(self, url: str, platform: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """
        Extract links using multiple methods based on platform
        """
        self.progress(f"🔍 Extracting links from {platform}...")

        # Try methods in order of reliability
        methods = self._get_extraction_methods(platform)

        for method_name, method_func in methods:
            try:
                self.progress(f"⚙️ Trying method: {method_name}...")
                links = method_func(url, cookie_file, max_videos)

                if links:
                    self.progress(f"✅ Success with {method_name}: {len(links)} links found")
                    return links
                else:
                    self.progress(f"⚠️ {method_name} returned no links, trying next method...")

            except Exception as e:
                self.progress(f"⚠️ {method_name} failed: {str(e)[:100]}, trying next method...")
                continue

        # If all methods fail
        self.progress(f"❌ All extraction methods failed for {url}")
        return []

    def _get_extraction_methods(self, platform: str) -> typing.List[typing.Tuple[str, typing.Callable]]:
        """
        Get extraction methods for each platform
        """
        methods_map = {
            'youtube': [
                ("YT-DLP Standard", self._ytdlp_standard),
                ("YT-DLP Flat Playlist", self._ytdlp_flat),
                ("YT-DLP JSON", self._ytdlp_json),
            ],
            'instagram': [
                ("YT-DLP with Cookies", self._ytdlp_instagram),
                ("Instaloader", self._instaloader_method),
                ("YT-DLP Alternative", self._ytdlp_instagram_alt),
            ],
            'tiktok': [
                ("YT-DLP with Cookies", self._ytdlp_tiktok),
                ("YT-DLP Alternative", self._ytdlp_tiktok_alt),
            ],
            'facebook': [
                ("YT-DLP Standard", self._ytdlp_facebook),
                ("YT-DLP Alternative", self._ytdlp_facebook_alt),
            ],
            'twitter': [
                ("YT-DLP Standard", self._ytdlp_twitter),
                ("YT-DLP with Auth", self._ytdlp_twitter_alt),
            ],
        }

        return methods_map.get(platform, [("YT-DLP Generic", self._ytdlp_standard)])

    # ========== YOUTUBE METHODS ==========

    def _ytdlp_standard(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """Standard yt-dlp extraction"""
        cmd = ['yt-dlp', '--flat-playlist', '--get-id', '--get-title', '--no-warnings', '--ignore-errors']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            lines = result.stdout.strip().split('\n')
            links = []
            base_url = "https://www.youtube.com/watch?v="

            # Parse output (alternating title and ID)
            for i in range(0, len(lines), 2):
                if i + 1 < len(lines):
                    title = lines[i]
                    video_id = lines[i + 1]
                    links.append({'url': f"{base_url}{video_id}", 'title': title})

            return links

        return []

    def _ytdlp_flat(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """Flat playlist method"""
        cmd = ['yt-dlp', '--flat-playlist', '--print', 'url', '--no-warnings', '--ignore-errors']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        # YouTube specific: skip HLS/DASH
        cmd.extend(['--extractor-args', 'youtube:skip=dash,hls;player_skip=configs'])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            urls = [line.strip() for line in result.stdout.split('\n') if line.strip().startswith('http')]
            return [{'url': u, 'title': u} for u in urls]

        return []

    def _ytdlp_json(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """JSON dump method"""
        cmd = ['yt-dlp', '--flat-playlist', '--dump-single-json', '--no-warnings', '--ignore-errors']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout)
                entries = data.get('entries', [])
                links = []

                for entry in entries:
                    if entry:
                        video_id = entry.get('id', '')
                        title = entry.get('title', 'Unknown')
                        if video_id:
                            links.append({
                                'url': f"https://www.youtube.com/watch?v={video_id}",
                                'title': title
                            })

                return links
            except json.JSONDecodeError:
                pass

        return []

    # ========== INSTAGRAM METHODS ==========

    def _ytdlp_instagram(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """Instagram with yt-dlp and cookies"""
        cmd = ['yt-dlp', '--flat-playlist', '--print', 'url', '--no-warnings', '--ignore-errors', '--no-check-certificate']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            urls = [line.strip() for line in result.stdout.split('\n') if line.strip().startswith('http')]
            return [{'url': u, 'title': u} for u in urls]

        return []

    def _instaloader_method(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """Use instaloader library"""
        try:
            import instaloader

            L = instaloader.Instaloader()

            # Extract username
            match = re.search(r'instagram\.com/([^/?#]+)', url)
            if not match:
                return []

            username = match.group(1)

            # Load session if cookies available
            if cookie_file:
                try:
                    L.load_session_from_file(username, cookie_file)
                except:
                    pass

            profile = instaloader.Profile.from_username(L.context, username)

            links = []
            count = 0

            for post in profile.get_posts():
                if max_videos > 0 and count >= max_videos:
                    break

                links.append({
                    'url': f"https://www.instagram.com/p/{post.shortcode}/",
                    'title': post.caption[:100] if post.caption else "Instagram Post"
                })
                count += 1

            return links

        except Exception as e:
            self.progress(f"⚠️ Instaloader error: {str(e)[:100]}")
            return []

    def _ytdlp_instagram_alt(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """Alternative Instagram extraction"""
        # Try with different options
        cmd = ['yt-dlp', '--flat-playlist', '--get-id', '--no-warnings', '--ignore-errors', '--no-check-certificate']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            ids = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            return [{'url': f"https://www.instagram.com/p/{id}/", 'title': id} for id in ids]

        return []

    # ========== TIKTOK METHODS ==========

    def _ytdlp_tiktok(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """TikTok with yt-dlp"""
        cmd = ['yt-dlp', '--flat-playlist', '--print', 'url', '--no-warnings', '--ignore-errors', '--no-check-certificate']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            urls = [line.strip() for line in result.stdout.split('\n') if line.strip().startswith('http')]
            return [{'url': u, 'title': u} for u in urls]

        return []

    def _ytdlp_tiktok_alt(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """Alternative TikTok method"""
        cmd = ['yt-dlp', '--flat-playlist', '--get-id', '--no-warnings', '--ignore-errors']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            ids = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            return [{'url': f"https://www.tiktok.com/@user/video/{id}", 'title': id} for id in ids]

        return []

    # ========== FACEBOOK METHODS ==========

    def _ytdlp_facebook(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """Facebook with yt-dlp"""
        cmd = ['yt-dlp', '--flat-playlist', '--print', 'url', '--no-warnings', '--ignore-errors', '--no-check-certificate']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            urls = [line.strip() for line in result.stdout.split('\n') if line.strip().startswith('http')]
            return [{'url': u, 'title': u} for u in urls]

        return []

    def _ytdlp_facebook_alt(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """Alternative Facebook method"""
        cmd = ['yt-dlp', '--flat-playlist', '--get-id', '--no-warnings', '--ignore-errors']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])}

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            ids = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            return [{'url': f"https://www.facebook.com/watch/?v={id}", 'title': id} for id in ids]

        return []

    # ========== TWITTER METHODS ==========

    def _ytdlp_twitter(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """Twitter with yt-dlp"""
        cmd = ['yt-dlp', '--flat-playlist', '--print', 'url', '--no-warnings', '--ignore-errors']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            urls = [line.strip() for line in result.stdout.split('\n') if line.strip().startswith('http')]
            return [{'url': u, 'title': u} for u in urls]

        return []

    def _ytdlp_twitter_alt(self, url: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
        """Alternative Twitter method"""
        cmd = ['yt-dlp', '--flat-playlist', '--get-id', '--no-warnings', '--ignore-errors', '--no-check-certificate']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            ids = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            return [{'url': f"https://twitter.com/i/status/{id}", 'title': id} for id in ids]

        return []


class LinkGrabberThread(QThread):
    """Single-URL link grabber"""
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    link_found = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str, list)
    save_triggered = pyqtSignal(str, list)

    def __init__(self, url: str, options: dict = None):
        super().__init__()
        self.url = (url or "").strip()
        self.options = options or {}
        self.is_cancelled = False
        self.found_links = []
        this_file = Path(__file__).resolve()
        self.cookies_dir = this_file.parent.parent.parent / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
        self.extractor = EnhancedLinkExtractor(progress_callback=self.progress.emit)

    def run(self):
        try:
            if not self.url:
                self.finished.emit(False, "❌ No URL provided", [])
                return

            self.progress.emit("🔍 Detecting platform...")
            self.progress_percent.emit(5)
            platform_key = _detect_platform_key(self.url)
            self.progress.emit(f"✅ Platform: {platform_key}")
            self.progress_percent.emit(15)

            # Get cookies
            cookie_file = _manual_cookie_path(self.cookies_dir, platform_key)
            if cookie_file:
                self.progress.emit(f"✅ Using manual cookies: {Path(cookie_file).name}")
            else:
                browser_cookies = _try_browser_cookies_tempfile(platform_key)
                if browser_cookies:
                    cookie_file = browser_cookies
                    self.progress.emit("✅ Using browser cookies")
                else:
                    self.progress.emit("🍪 No cookies - trying without authentication")

            self.progress_percent.emit(25)

            # Extract links
            max_videos = int(self.options.get('max_videos', 0) or 0)
            links = self.extractor.extract_links(self.url, platform_key, cookie_file, max_videos)

            self.extractor.cleanup()

            if not links:
                self.finished.emit(False, "❌ No links found. Check URL and cookies.", [])
                return

            self.progress.emit(f"🔁 Processing {len(links)} links...")
            self.progress_percent.emit(50)

            # Emit links
            for idx, entry in enumerate(links, 1):
                if self.is_cancelled:
                    break

                self.found_links.append(entry)
                display = entry.get('title', entry['url'])[:100]
                self.progress.emit(f"🔗 {idx}/{len(links)}: {display}")
                self.link_found.emit(entry['url'], display)

                pct = 50 + int((idx / len(links)) * 45)
                self.progress_percent.emit(min(pct, 95))

            if self.is_cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. Extracted {len(self.found_links)} links.", self.found_links)
                return

            self.progress.emit(f"✅ Extracted {len(self.found_links)} links!")
            self.progress_percent.emit(100)
            self.finished.emit(True, f"✅ Done! {len(self.found_links)} links extracted.", self.found_links)

        except Exception as exc:
            self.extractor.cleanup()
            msg = f"❌ Error: {str(exc)[:200]}"
            self.progress.emit(msg)
            self.finished.emit(False, msg, self.found_links)

    def save_to_file(self, creator_name: str):
        """Save links to creator-specific folder"""
        if self.found_links:
            saved_path = self._save_links_to_creator_folder(creator_name, self.found_links)
            self.save_triggered.emit(saved_path, self.found_links)

    def _save_links_to_creator_folder(self, creator_name: str, links: typing.List[dict]) -> str:
        """
        Save links to: Desktop/Toseeq Links Grabber/{CreatorName}/{CreatorName}-links.txt
        """
        desktop = Path.home() / "Desktop"
        base_folder = desktop / "Toseeq Links Grabber"
        base_folder.mkdir(parents=True, exist_ok=True)

        # Sanitize creator name
        safe_creator = _safe_filename(creator_name)

        # Create creator-specific folder
        creator_folder = base_folder / safe_creator
        creator_folder.mkdir(parents=True, exist_ok=True)

        # Create file
        filename = f"{safe_creator}-links.txt"
        filepath = creator_folder / filename

        # Write links
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# Links for: {creator_name}\n")
            f.write(f"# Total links: {len(links)}\n")
            f.write(f"# Saved: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n")
            for link in links:
                f.write(f"{link['url']}\n")

        return str(filepath)

    def cancel(self):
        self.is_cancelled = True
        self.extractor.cleanup()


class BulkLinkGrabberThread(QThread):
    """
    Bulk URL grabber with:
    - Duplicate removal
    - One creator at a time
    - Creator-specific folders
    """
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    link_found = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str, list)
    save_triggered = pyqtSignal(str, list)

    def __init__(self, urls: typing.List[str], options: dict = None):
        super().__init__()
        self.urls = [u.strip() for u in urls if u.strip()] or []
        self.options = options or {}
        self.is_cancelled = False
        self.found_links = []
        this_file = Path(__file__).resolve()
        self.cookies_dir = this_file.parent.parent.parent / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def run(self):
        try:
            total_urls = len(self.urls)
            if total_urls == 0:
                self.finished.emit(False, "❌ No URLs provided", [])
                return

            self.progress.emit(f"🚀 Starting bulk extraction for {total_urls} URL(s)...")
            self.progress_percent.emit(5)

            # Step 1: Remove duplicates
            unique_urls = self._remove_duplicates(self.urls)
            removed = total_urls - len(unique_urls)

            if removed > 0:
                self.progress.emit(f"🔍 Removed {removed} duplicate URL(s)")
                self.progress.emit(f"✅ Processing {len(unique_urls)} unique URL(s)")

            self.progress_percent.emit(10)

            # Step 2: Process each URL
            all_results = []

            for idx, url in enumerate(unique_urls, 1):
                if self.is_cancelled:
                    break

                self.progress.emit(f"\n{'='*60}")
                self.progress.emit(f"📌 Creator {idx}/{len(unique_urls)}: {url[:50]}...")
                self.progress.emit(f"{'='*60}")

                # Detect platform
                platform_key = _detect_platform_key(url)
                creator_name = _extract_creator_from_url(url, platform_key)

                self.progress.emit(f"🔍 Platform: {platform_key} | Creator: {creator_name}")

                # Get cookies
                cookie_file = _manual_cookie_path(self.cookies_dir, platform_key)
                if cookie_file:
                    self.progress.emit(f"✅ Cookies: {Path(cookie_file).name}")
                else:
                    browser_cookies = _try_browser_cookies_tempfile(platform_key)
                    if browser_cookies:
                        cookie_file = browser_cookies
                        self.progress.emit("✅ Using browser cookies")

                # Extract links
                extractor = EnhancedLinkExtractor(progress_callback=self.progress.emit)
                max_videos = int(self.options.get('max_videos', 0) or 0)

                links = extractor.extract_links(url, platform_key, cookie_file, max_videos)
                extractor.cleanup()

                if links:
                    # Save to creator-specific folder
                    saved_path = self._save_links_to_creator_folder(creator_name, links)
                    self.progress.emit(f"💾 Saved {len(links)} links to: {saved_path}")

                    # Emit links
                    for link in links:
                        self.link_found.emit(link['url'], link.get('title', link['url']))
                        self.found_links.append(link)

                    all_results.append({
                        'creator': creator_name,
                        'url': url,
                        'links': len(links),
                        'path': saved_path
                    })
                else:
                    self.progress.emit(f"⚠️ No links found for {creator_name}")

                # Update progress
                pct = 10 + int((idx / len(unique_urls)) * 85)
                self.progress_percent.emit(pct)

            if self.is_cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. Processed {len(all_results)} creator(s).", self.found_links)
                return

            # Final summary
            self.progress.emit(f"\n{'='*60}")
            self.progress.emit("🎉 BULK EXTRACTION COMPLETE!")
            self.progress.emit(f"{'='*60}")
            self.progress.emit(f"✅ Total creators processed: {len(all_results)}")
            self.progress.emit(f"✅ Total links extracted: {len(self.found_links)}")

            for result in all_results:
                self.progress.emit(f"  📁 {result['creator']}: {result['links']} links")

            self.progress.emit(f"\n💾 All links saved in creator-specific folders!")
            self.progress.emit(f"📂 Location: Desktop/Toseeq Links Grabber/")
            self.progress_percent.emit(100)

            self.finished.emit(True, f"✅ All done! {len(all_results)} creator(s) processed.", self.found_links)

        except Exception as e:
            msg = f"❌ Bulk error: {str(e)[:200]}"
            self.progress.emit(msg)
            self.finished.emit(False, msg, self.found_links)

    def _remove_duplicates(self, urls: typing.List[str]) -> typing.List[str]:
        """Remove duplicate URLs"""
        seen = set()
        unique = []

        for url in urls:
            # Normalize URL
            normalized = url.lower().rstrip('/').split('?')[0]

            if normalized not in seen:
                seen.add(normalized)
                unique.append(url)

        return unique

    def _save_links_to_creator_folder(self, creator_name: str, links: typing.List[dict]) -> str:
        """Save links to creator-specific folder"""
        desktop = Path.home() / "Desktop"
        base_folder = desktop / "Toseeq Links Grabber"
        base_folder.mkdir(parents=True, exist_ok=True)

        # Sanitize creator name
        safe_creator = _safe_filename(creator_name)

        # Create creator-specific folder
        creator_folder = base_folder / safe_creator
        creator_folder.mkdir(parents=True, exist_ok=True)

        # Create file
        filename = f"{safe_creator}-links.txt"
        filepath = creator_folder / filename

        # Write links
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# Links for: {creator_name}\n")
            f.write(f"# Total links: {len(links)}\n")
            f.write(f"# Saved: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n")
            for link in links:
                f.write(f"{link['url']}\n")

        return str(filepath)

    def cancel(self):
        self.is_cancelled = True
