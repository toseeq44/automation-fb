"""
modules/link_grabber/core.py
Fast link grabber (single-file) using yt-dlp subprocess for speed.
- Manual cookies in cookies/ preferred (names: youtube_cookies.txt, instagram_cookies.txt, tiktok_cookies.txt, facebook_cookies.txt, twitter_cookies.txt)
- Fallback to browser_cookie3 if available (temporary cookies)
- Produces page URLs (not media stream URLs)
- Emits signals expected by GUI:
    progress(str), progress_percent(int), link_found(str, str), finished(bool, str, list), save_triggered(str, list)
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

# Helper: sanitize filenames
def _safe_filename(s: str) -> str:
    s = s.strip()
    s = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s)
    s = re.sub(r'\s+', '_', s)
    if not s:
        return "links"
    return s[:200]

# Helper: extract creator/username from URL
def _extract_creator_from_url(url: str, platform_key: str) -> str:
    try:
        u = url.strip().rstrip('/')
        if platform_key == 'youtube':
            m = re.search(r'@([A-Za-z0-9_\-\.]+)', u)
            if m:
                return m.group(1)
            m = re.search(r'/channel/([^/?#]+)', u)
            if m:
                return m.group(1)
            m = re.search(r'/c/([^/?#]+)', u)
            if m:
                return m.group(1)
            parts = u.split('/')
            if parts:
                return parts[-1] or 'youtube'
            return 'youtube'
        else:
            m = re.search(r'tiktok\.com/@([^/?#]+)', u)
            if m:
                return m.group(1)
            m = re.search(r'instagram\.com/([^/?#]+)', u)
            if m:
                return m.group(1)
            m = re.search(r'(?:twitter|x)\.com/([^/?#]+)', u)
            if m:
                return m.group(1)
            m = re.search(r'facebook\.com/([^/?#]+)', u)
            if m:
                return m.group(1)
            parts = u.split('/')
            if parts:
                return parts[-1] or platform_key
            return platform_key
    except Exception:
        return platform_key

# Detect platform from URL
def _detect_platform_key(url: str) -> str:
    u = url.lower()
    if 'youtube.com' in u or 'youtu.be' in u:
        return 'youtube'
    if 'instagram.com' in u:
        return 'instagram'
    if 'tiktok.com' in u:
        return 'tiktok'
    if 'facebook.com' in u or 'fb.com' in u:
        return 'facebook'
    if 'twitter.com' in u or 'x.com' in u:
        return 'twitter'
    return 'unknown'

# Prepare cookie selection priority: manual first
def _manual_cookie_path(cookies_dir: Path, platform_key: str) -> typing.Optional[str]:
    mapping = {
        'youtube': 'youtube_cookies.txt',
        'instagram': 'instagram_cookies.txt',
        'tiktok': 'tiktok_cookies.txt',
        'facebook': 'facebook_cookies.txt',
        'twitter': 'twitter_cookies.txt'
    }
    name = mapping.get(platform_key, f'{platform_key}.txt')
    p = cookies_dir / name
    if p.exists() and p.stat().st_size > 10:
        return str(p)
    return None

# Try to extract browser cookies using browser_cookie3, saved to temp
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

class LinkGrabberThread(QThread):
    """Single-URL fast link grabber (yt-dlp subprocess)"""
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
        self._temp_cookie_files = []

    def _cleanup_temp_cookies(self):
        for tf in list(self._temp_cookie_files):
            try:
                if os.path.exists(tf):
                    os.unlink(tf)
            except Exception:
                pass
        self._temp_cookie_files = []

    def _build_command_and_process(self, url: str, platform_key: str) -> typing.Tuple[typing.List[dict], str]:
        """
        Run yt-dlp with --get-url to fetch video URLs.
        Returns list of video URLs and creator name.
        """
        cookie_file = _manual_cookie_path(self.cookies_dir, platform_key)
        if cookie_file:
            self.progress.emit(f"✅ Using manual cookies: {Path(cookie_file).name}")
        else:
            browser_tf = _try_browser_cookies_tempfile(platform_key)
            if browser_tf:
                cookie_file = browser_tf
                self._temp_cookie_files.append(browser_tf)
                self.progress.emit("✅ Using browser cookies (temporary)")
            else:
                self.progress.emit("🍪 No cookies found (manual or browser) - proceeding without cookies")

        # Get video URLs
        cmd_parts = ['yt-dlp', '--quiet', '--no-warnings', '--flat-playlist', '--get-url', '--ignore-errors', '--no-check-certificate']
        if platform_key == 'youtube':
            if '/@' in url.lower() or '/channel/' in url.lower() or '/c/' in url.lower():
                base_url = url.split('/videos')[0].split('/streams')[0].split('/shorts')[0].split('/playlists')[0]
                if base_url != url:
                    self.progress.emit(f"🔄 Using base channel URL: {base_url}")
                    url = base_url
            cmd_parts.append('--extractor-args')
            cmd_parts.append('youtube:skip=dash,hls;player_skip=configs')
        max_videos = int(self.options.get('max_videos', 0) or 0)
        if max_videos > 0:
            cmd_parts.append(f'--playlist-end={max_videos}')
        if cookie_file:
            cmd_parts.append(f'--cookiefile={cookie_file}')
        cmd_parts.append(url)

        try:
            self.progress.emit(f"📡 Executing yt-dlp command for URLs: {' '.join(shlex.quote(p) for p in cmd_parts)[:100]}...")
            res = subprocess.run(cmd_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', shell=False, check=False)
            stdout = res.stdout or ""
            stderr = res.stderr or ""
            if res.returncode != 0 and not stdout:
                cmd_line = " ".join(shlex.quote(p) for p in cmd_parts)
                res = subprocess.run(cmd_line, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', shell=True, check=False)
                stdout = res.stdout or ""
                stderr = res.stderr or ""

            if not stdout:
                error_msg = stderr.strip() or "No data returned from yt-dlp"
                if 'private' in error_msg.lower() or 'unavailable' in error_msg.lower():
                    error_msg = "Content is private/unavailable. Try adding valid cookies."
                elif 'login' in error_msg.lower():
                    error_msg = "Login required. Please login in browser or add manual cookies."
                elif 'region' in error_msg.lower():
                    error_msg = "Content not available in your region."
                elif 'removed' in error_msg.lower():
                    error_msg = "Content has been removed."
                elif 'age' in error_msg.lower():
                    error_msg = "Age-restricted content. Try adding cookies."
                self.progress.emit(f"❌ Error: {error_msg}")
                return [], "unknown"

            # Parse URLs
            urls = [line.strip() for line in stdout.splitlines() if line.strip() and (line.startswith('http://') or line.startswith('https://'))]
            self.progress.emit(f"📊 Found {len(urls)} video URLs")

            creator = _extract_creator_from_url(url, platform_key)
            video_entries = [{'url': url, 'title': url} for url in urls]
            return video_entries, creator

        except FileNotFoundError:
            self.progress.emit("❌ yt-dlp not found in PATH. Please ensure yt-dlp is installed and in PATH.")
            return [], "unknown"
        except Exception as e:
            self.progress.emit(f"❌ yt-dlp execution error: {str(e)[:200]}")
            return [], "unknown"

    def _save_links_to_desktop_file(self, creator_name: str, links: typing.List[dict]) -> str:
        desktop = Path.home() / "Desktop"
        folder = desktop / "Toseeq Links Grabber"
        folder.mkdir(parents=True, exist_ok=True)
        filename = _safe_filename(creator_name) + ".txt"
        filepath = folder / filename
        with open(filepath, "w", encoding="utf-8") as f:
            for link in links:
                f.write(f"{link['url']}\n")
        return str(filepath)

    def save_to_file(self, creator_name: str):
        """Trigger file save and emit signal with path"""
        if self.found_links:
            saved_path = self._save_links_to_desktop_file(creator_name, self.found_links)
            self.save_triggered.emit(saved_path, self.found_links)

    def run(self):
        try:
            if not self.url:
                self.finished.emit(False, "❌ No URL provided", [])
                return

            self.progress.emit("🔍 Detecting platform and preparing...")
            self.progress_percent.emit(5)
            platform_key = _detect_platform_key(self.url)
            self.progress.emit(f"✅ Platform detected: {platform_key}")
            self.progress_percent.emit(15)

            entries, creator = self._build_command_and_process(self.url, platform_key)
            if not entries:
                self._cleanup_temp_cookies()
                self.finished.emit(False, "❌ No videos found. Try using cookies for private content or check the URL.", [])
                return

            self.progress.emit(f"🔁 Processing {len(entries)} videos...")
            self.progress_percent.emit(25)
            max_videos = int(self.options.get('max_videos', 0) or 0)
            if max_videos > 0:
                entries = entries[:max_videos]

            total = len(entries)
            self.found_links = []
            for idx, entry in enumerate(entries, 1):
                if self.is_cancelled:
                    break
                self.found_links.append(entry)
                display = entry['url']
                self.progress.emit(f"🔗 Found: {display}")
                self.link_found.emit(entry['url'], display)
                pct = 25 + int((idx / total) * 70)
                self.progress_percent.emit(min(pct, 95))

            if self.is_cancelled:
                self._cleanup_temp_cookies()
                self.finished.emit(False, f"⚠️ Cancelled. Extracted {len(self.found_links)} links.", self.found_links)
                return

            self.progress.emit(f"✅ Extracted {len(self.found_links)} links. Click 'Save to Folder' to save.")
            self.progress_percent.emit(100)
            self._cleanup_temp_cookies()
            self.finished.emit(True, f"✅ Done! Extracted {len(self.found_links)} links.", self.found_links)

        except Exception as exc:
            self._cleanup_temp_cookies()
            msg = f"❌ Unexpected error: {str(exc)[:200]}"
            self.progress.emit(msg)
            self.finished.emit(False, msg, self.found_links)

    def cancel(self):
        self.is_cancelled = True
        self._cleanup_temp_cookies()

class BulkLinkGrabberThread(QThread):
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
        self._temp_cookie_files = []

    def _cleanup_temp_cookies(self):
        for tf in list(self._temp_cookie_files):
            try:
                if os.path.exists(tf):
                    os.unlink(tf)
            except Exception:
                pass
        self._temp_cookie_files = []

    def _save_links_to_desktop_file(self, links: typing.List[dict]) -> str:
        desktop = Path.home() / "Desktop"
        folder = desktop / "Toseeq Links Grabber"
        folder.mkdir(parents=True, exist_ok=True)
        filename = "bulk_links.txt"
        filepath = folder / filename
        with open(filepath, "w", encoding="utf-8") as f:
            for link in links:
                f.write(f"{link['url']}\n")
        return str(filepath)

    def save_to_file(self):
        """Trigger file save and emit signal with path"""
        if self.found_links:
            saved_path = self._save_links_to_desktop_file(self.found_links)
            self.save_triggered.emit(saved_path, self.found_links)

    def run(self):
        try:
            total_urls = len(self.urls)
            if total_urls == 0:
                self.finished.emit(False, "❌ No URLs provided", [])
                return

            self.found_links = []
            for i, url in enumerate(self.urls, 1):
                if self.is_cancelled:
                    break
                self.progress.emit(f"🚀 Processing {i}/{total_urls}: {url[:50]}...")
                runner = LinkGrabberThread(url, self.options)
                platform_key = _detect_platform_key(url)
                entries, creator = runner._build_command_and_process(url, platform_key)
                max_videos = int(self.options.get('max_videos', 0) or 0)
                if max_videos > 0:
                    entries = entries[:max_videos]

                for idx, entry in enumerate(entries, 1):
                    if self.is_cancelled:
                        break
                    self.found_links.append(entry)
                    display = entry['url']
                    self.progress.emit(f"🔗 Found: {display}")
                    self.link_found.emit(entry['url'], display)
                pct = int((i / total_urls) * 95)
                self.progress_percent.emit(pct)
                runner._cleanup_temp_cookies()

            if self.is_cancelled:
                self._cleanup_temp_cookies()
                self.finished.emit(False, f"⚠️ Cancelled. Extracted {len(self.found_links)} links.", self.found_links)
                return

            self.progress.emit(f"✅ Extracted {len(self.found_links)} links. Click 'Save to Folder' to save.")
            self.progress_percent.emit(100)
            self._cleanup_temp_cookies()
            self.finished.emit(True, f"✅ Bulk done. Extracted {len(self.found_links)} links.", self.found_links)

        except Exception as e:
            self._cleanup_temp_cookies()
            self.finished.emit(False, f"❌ Bulk error: {str(e)[:200]}", self.found_links)

    def cancel(self):
        self.is_cancelled = True
        self._cleanup_temp_cookies()