"""
modules/link_grabber/core.py
Simple and fast link grabber using yt-dlp.

Features:
- Multi-platform: YouTube, TikTok, Instagram, Facebook, Twitter
- Creator-specific folders: Desktop/Toseeq Links Grabber/@{CreatorName}/{CreatorName}_links.txt
- Duplicate removal
- Cookie support
- Clean and reliable
"""

from PyQt5.QtCore import QThread, pyqtSignal
from pathlib import Path
import os
import subprocess
import shlex
import tempfile
import re
import typing


# ============ HELPER FUNCTIONS ============

def _safe_filename(s: str) -> str:
    """Sanitize filename"""
    s = s.strip()
    s = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s)
    s = re.sub(r'\s+', '_', s)
    return s[:200] if s else "unknown"


def _extract_creator_from_url(url: str, platform_key: str) -> str:
    """Extract creator name from URL"""
    try:
        u = url.strip().rstrip('/')

        if platform_key == 'youtube':
            # @username
            m = re.search(r'@([A-Za-z0-9_\-\.]+)', u)
            if m:
                return m.group(1)
            # /channel/ID
            m = re.search(r'/channel/([^/?#]+)', u)
            if m:
                return m.group(1)
            # /c/name
            m = re.search(r'/c/([^/?#]+)', u)
            if m:
                return m.group(1)
            return 'youtube'

        elif platform_key == 'tiktok':
            m = re.search(r'tiktok\.com/@([^/?#]+)', u)
            if m:
                return m.group(1)
            return 'tiktok'

        elif platform_key == 'instagram':
            m = re.search(r'instagram\.com/([^/?#]+)', u)
            if m and m.group(1) not in ['p', 'reel', 'tv', 'stories']:
                return m.group(1)
            return 'instagram'

        elif platform_key == 'facebook':
            m = re.search(r'facebook\.com/([^/?#]+)', u)
            if m:
                return m.group(1)
            return 'facebook'

        elif platform_key == 'twitter':
            m = re.search(r'(?:twitter|x)\.com/([^/?#]+)', u)
            if m:
                return m.group(1)
            return 'twitter'

        return platform_key
    except Exception:
        return platform_key


def _detect_platform_key(url: str) -> str:
    """Detect platform from URL"""
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


def _manual_cookie_path(cookies_dir: Path, platform_key: str) -> typing.Optional[str]:
    """Find manual cookie file"""
    # Simple names: instagram.txt, youtube.txt, etc.
    cookie_file = cookies_dir / f"{platform_key}.txt"
    if cookie_file.exists() and cookie_file.stat().st_size > 10:
        return str(cookie_file)

    # Fallback to cookies.txt
    fallback = cookies_dir / "cookies.txt"
    if fallback.exists() and fallback.stat().st_size > 10:
        return str(fallback)

    return None


def _try_browser_cookies_tempfile(platform_key: str) -> typing.Optional[str]:
    """Extract browser cookies"""
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


def _normalize_url(url: str) -> str:
    """Normalize URL for duplicate detection"""
    url = url.split('?')[0].split('#')[0]
    url = url.lower().rstrip('/')
    return url


def _remove_duplicates(urls: typing.List[str]) -> typing.List[str]:
    """Remove duplicate URLs"""
    seen = set()
    unique = []
    for url in urls:
        normalized = _normalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            unique.append(url)
    return unique


# ============ THREAD CLASSES ============

class LinkGrabberThread(QThread):
    """Single URL link grabber"""

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
        """Run yt-dlp to fetch video URLs"""
        cookie_file = _manual_cookie_path(self.cookies_dir, platform_key)
        if cookie_file:
            self.progress.emit(f"✅ Using manual cookies: {Path(cookie_file).name}")
        else:
            browser_tf = _try_browser_cookies_tempfile(platform_key)
            if browser_tf:
                cookie_file = browser_tf
                self._temp_cookie_files.append(browser_tf)
                self.progress.emit("✅ Using browser cookies")
            else:
                self.progress.emit("🍪 No cookies - proceeding without cookies")

        # Build yt-dlp command
        cmd_parts = ['yt-dlp', '--quiet', '--no-warnings', '--flat-playlist', '--get-url', '--ignore-errors', '--no-check-certificate']

        if platform_key == 'youtube':
            if '/@' in url.lower() or '/channel/' in url.lower() or '/c/' in url.lower():
                base_url = url.split('/videos')[0].split('/streams')[0].split('/shorts')[0].split('/playlists')[0]
                if base_url != url:
                    self.progress.emit(f"🔄 Using base channel URL")
                    url = base_url
            cmd_parts.extend(['--extractor-args', 'youtube:skip=dash,hls'])

        max_videos = int(self.options.get('max_videos', 0) or 0)
        if max_videos > 0:
            cmd_parts.append(f'--playlist-end={max_videos}')

        if cookie_file:
            cmd_parts.append(f'--cookies={cookie_file}')

        cmd_parts.append(url)

        try:
            self.progress.emit(f"📡 Executing yt-dlp...")
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
                    error_msg = "Content is private/unavailable. Try adding cookies."
                elif 'login' in error_msg.lower():
                    error_msg = "Login required. Please add cookies."
                elif 'region' in error_msg.lower():
                    error_msg = "Content not available in your region."
                elif 'removed' in error_msg.lower():
                    error_msg = "Content has been removed."
                elif 'age' in error_msg.lower():
                    error_msg = "Age-restricted. Try adding cookies."
                self.progress.emit(f"❌ Error: {error_msg}")
                return [], "unknown"

            # Parse URLs and remove duplicates
            urls = [line.strip() for line in stdout.splitlines() if line.strip() and (line.startswith('http://') or line.startswith('https://'))]
            urls = _remove_duplicates(urls)
            self.progress.emit(f"📊 Found {len(urls)} unique video URLs")

            creator = _extract_creator_from_url(url, platform_key)
            video_entries = [{'url': url, 'title': url} for url in urls]
            return video_entries, creator

        except FileNotFoundError:
            self.progress.emit("❌ yt-dlp not found. Please install yt-dlp.")
            return [], "unknown"
        except Exception as e:
            self.progress.emit(f"❌ Error: {str(e)[:200]}")
            return [], "unknown"

    def _save_links_to_creator_folder(self, creator_name: str, links: typing.List[dict]) -> str:
        """Save links to: Desktop/Toseeq Links Grabber/@{CreatorName}/{CreatorName}_links.txt"""
        desktop = Path.home() / "Desktop"
        base_folder = desktop / "Toseeq Links Grabber"

        # Folder: @CreatorName
        safe_creator = _safe_filename(f"@{creator_name}")
        creator_folder = base_folder / safe_creator
        creator_folder.mkdir(parents=True, exist_ok=True)

        # File: CreatorName_links.txt
        filename = f"{_safe_filename(creator_name)}_links.txt"
        filepath = creator_folder / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for link in links:
                f.write(f"{link['url']}\n")

        return str(filepath)

    def save_to_file(self, creator_name: str):
        """Save links to file"""
        if self.found_links:
            saved_path = self._save_links_to_creator_folder(creator_name, self.found_links)
            self.save_triggered.emit(saved_path, self.found_links)

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

            entries, creator = self._build_command_and_process(self.url, platform_key)
            if not entries:
                self._cleanup_temp_cookies()
                self.finished.emit(False, "❌ No videos found. Try using cookies.", [])
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
                self.progress.emit(f"🔗 Found: {entry['url']}")
                self.link_found.emit(entry['url'], entry['url'])
                pct = 25 + int((idx / total) * 70)
                self.progress_percent.emit(min(pct, 95))

            if self.is_cancelled:
                self._cleanup_temp_cookies()
                self.finished.emit(False, f"⚠️ Cancelled. Extracted {len(self.found_links)} links.", self.found_links)
                return

            self.progress.emit(f"✅ Extracted {len(self.found_links)} unique links. Click 'Save to Folder'.")
            self.progress_percent.emit(100)
            self._cleanup_temp_cookies()
            self.finished.emit(True, f"✅ Done! {len(self.found_links)} unique links.", self.found_links)

        except Exception as exc:
            self._cleanup_temp_cookies()
            msg = f"❌ Unexpected error: {str(exc)[:200]}"
            self.progress.emit(msg)
            self.finished.emit(False, msg, self.found_links)

    def cancel(self):
        self.is_cancelled = True
        self._cleanup_temp_cookies()


class BulkLinkGrabberThread(QThread):
    """Bulk URL link grabber with per-creator folders"""

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
        self.creator_data = {}  # Track each creator's links

        this_file = Path(__file__).resolve()
        self.cookies_dir = this_file.parent.parent.parent / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def _save_creator_to_folder(self, creator_name: str, links: typing.List[dict]) -> str:
        """Save creator's links to: Desktop/Toseeq Links Grabber/@{CreatorName}/{CreatorName}_links.txt"""
        desktop = Path.home() / "Desktop"
        base_folder = desktop / "Toseeq Links Grabber"

        # Folder: @CreatorName
        safe_creator = _safe_filename(f"@{creator_name}")
        creator_folder = base_folder / safe_creator
        creator_folder.mkdir(parents=True, exist_ok=True)

        # File: CreatorName_links.txt
        filename = f"{_safe_filename(creator_name)}_links.txt"
        filepath = creator_folder / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for link in links:
                f.write(f"{link['url']}\n")

        return str(filepath)

    def save_to_file(self):
        """Save all creators' links to their respective folders"""
        if not self.creator_data:
            self.progress.emit("❌ No links to save")
            return

        for creator_name, data in self.creator_data.items():
            if data['links']:
                saved_path = self._save_creator_to_folder(creator_name, data['links'])
                self.progress.emit(f"💾 Saved: {saved_path}")

        self.progress.emit(f"✅ All {len(self.creator_data)} creators saved!")

    def run(self):
        try:
            total_urls = len(self.urls)
            if total_urls == 0:
                self.finished.emit(False, "❌ No URLs provided", [])
                return

            # Remove duplicates
            self.progress.emit(f"🔍 Checking {total_urls} URLs for duplicates...")
            unique_urls = _remove_duplicates(self.urls)
            duplicates_removed = len(self.urls) - len(unique_urls)

            if duplicates_removed > 0:
                self.progress.emit(f"🧹 Removed {duplicates_removed} duplicate URLs")

            self.progress.emit(f"✅ Processing {len(unique_urls)} unique URLs...")
            self.progress.emit("="*50)

            self.found_links = []
            self.creator_data = {}

            # Process each URL
            for i, url in enumerate(unique_urls, 1):
                if self.is_cancelled:
                    break

                self.progress.emit(f"\n📌 [{i}/{len(unique_urls)}] Processing: {url[:60]}...")

                runner = LinkGrabberThread(url, self.options)
                platform_key = _detect_platform_key(url)
                entries, creator = runner._build_command_and_process(url, platform_key)

                max_videos = int(self.options.get('max_videos', 0) or 0)
                if max_videos > 0:
                    entries = entries[:max_videos]

                # Track creator data
                if creator not in self.creator_data:
                    self.creator_data[creator] = {
                        'links': [],
                        'url': url,
                        'platform': platform_key
                    }

                # Add links
                for entry in entries:
                    if self.is_cancelled:
                        break
                    self.found_links.append(entry)
                    self.creator_data[creator]['links'].append(entry)
                    self.link_found.emit(entry['url'], entry['url'])

                # Save this creator immediately
                if entries:
                    saved_path = self._save_creator_to_folder(creator, entries)
                    self.progress.emit(f"💾 Saved to: {saved_path}")

                self.progress.emit(f"✅ [{i}/{len(unique_urls)}] Extracted {len(entries)} links from: @{creator}")

                pct = int((i / len(unique_urls)) * 95)
                self.progress_percent.emit(pct)
                runner._cleanup_temp_cookies()

            if self.is_cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. {len(self.found_links)} total links.", self.found_links)
                return

            # Final summary
            self.progress.emit("\n" + "="*50)
            self.progress.emit("🎉 BULK EXTRACTION COMPLETE!")
            self.progress.emit("="*50)
            self.progress.emit(f"📊 Processed: {len(unique_urls)} unique URLs")
            self.progress.emit(f"👥 Creators: {len(self.creator_data)}")
            self.progress.emit(f"🔗 Total Links: {len(self.found_links)}")
            if duplicates_removed > 0:
                self.progress.emit(f"🧹 Duplicates Removed: {duplicates_removed}")
            self.progress.emit("\n📁 Saved Folders:")
            for creator_name, data in self.creator_data.items():
                self.progress.emit(f"  ├── @{creator_name}/ ({len(data['links'])} links)")
            self.progress.emit("="*50)

            self.progress_percent.emit(100)
            self.finished.emit(True, f"✅ Bulk complete! {len(self.found_links)} total links from {len(self.creator_data)} creators.", self.found_links)

        except Exception as e:
            self.finished.emit(False, f"❌ Bulk error: {str(e)[:200]}", self.found_links)

    def cancel(self):
        self.is_cancelled = True
