"""
modules/link_grabber/core.py
Multi-method link grabber with creator-specific folders.

Features:
- Multiple extraction methods (yt-dlp, platform-specific tools, etc.)
- All platforms: YouTube, TikTok, Instagram, Facebook, Twitter
- Creator folders: Desktop/Toseeq Links Grabber/@{CreatorName}/{CreatorName}_links.txt
- Automatic fallback between methods
"""

from PyQt5.QtCore import QThread, pyqtSignal
from pathlib import Path
import os
import subprocess
import tempfile
import re
import time
import typing
import json
import logging


# ============ HELPER FUNCTIONS ============

def _safe_filename(s: str) -> str:
    """Sanitize filename"""
    s = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s.strip())
    return s[:200] if s else "unknown"


def _extract_creator_from_url(url: str, platform_key: str) -> str:
    """Extract creator name from URL"""
    try:
        url_lower = url.lower()
        if platform_key == 'youtube':
            if '/@' in url_lower:
                match = re.search(r'/@([^/?#]+)', url_lower)
                if match:
                    return match.group(1)
            for pattern in [r'/channel/([^/?#]+)', r'/c/([^/?#]+)', r'/user/([^/?#]+)']:
                match = re.search(pattern, url_lower)
                if match:
                    return match.group(1)
        elif platform_key == 'instagram':
            match = re.search(r'instagram\.com/([^/?#]+)', url_lower)
            if match and match.group(1) not in ['p', 'reel', 'tv', 'stories']:
                return match.group(1)
        elif platform_key == 'tiktok':
            match = re.search(r'tiktok\.com/@([^/?#]+)', url_lower)
            if match:
                return match.group(1)
        elif platform_key in ['twitter', 'facebook']:
            match = re.search(r'(?:twitter|x|facebook)\.com/([^/?#]+)', url_lower)
            if match:
                return match.group(1)

        # Fallback
        parts = url.rstrip('/').split('/')
        return parts[-1] if parts else platform_key
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


def _find_cookie_file(cookies_dir: Path, platform_key: str) -> typing.Optional[str]:
    """Find cookie file - Simple names: instagram.txt, youtube.txt, etc."""
    cookie_file = cookies_dir / f"{platform_key}.txt"
    if cookie_file.exists() and cookie_file.stat().st_size > 10:
        return str(cookie_file)

    fallback = cookies_dir / "cookies.txt"
    if fallback.exists() and fallback.stat().st_size > 10:
        return str(fallback)

    return None


def _extract_browser_cookies(platform_key: str) -> typing.Optional[str]:
    """Extract cookies from browser"""
    try:
        import browser_cookie3 as bc3
    except ImportError:
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
        ('chrome', getattr(bc3, 'chrome', None)),
        ('edge', getattr(bc3, 'edge', None)),
        ('firefox', getattr(bc3, 'firefox', None))
    ]

    for browser_name, browser_func in browsers:
        if not browser_func:
            continue
        try:
            cookie_jar = browser_func(domain_name=domain) if domain else browser_func()

            if cookie_jar and len(cookie_jar) > 0:
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.txt',
                    delete=False,
                    encoding='utf-8'
                )

                temp_file.write("# Netscape HTTP Cookie File\n")
                temp_file.write(f"# Extracted from {browser_name}\n\n")

                for cookie in cookie_jar:
                    domain = getattr(cookie, 'domain', '')
                    flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                    path = getattr(cookie, 'path', '/')
                    secure = 'TRUE' if getattr(cookie, 'secure', False) else 'FALSE'
                    expires = str(int(getattr(cookie, 'expires', 0))) if getattr(cookie, 'expires', 0) else '0'
                    name = getattr(cookie, 'name', '')
                    value = getattr(cookie, 'value', '')

                    temp_file.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")

                temp_file.close()
                return temp_file.name

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


# ============ EXTRACTION METHODS ============

def _extract_ytdlp_get_url(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
    """METHOD 1: yt-dlp --get-url (Fastest)"""
    try:
        cmd = ['yt-dlp', '--get-url', '--flat-playlist', '--ignore-errors', '--no-warnings']
        if cookie_file:
            cmd.extend(['--cookies', cookie_file])
        if max_videos > 0:
            cmd.append(f'--playlist-end={max_videos}')

        # Platform optimizations
        if platform_key == 'youtube':
            if any(x in url.lower() for x in ['/@', '/channel/', '/c/', '/user/']):
                base_url = url.split('/videos')[0].split('/streams')[0].split('/shorts')[0]
                url = base_url + '/videos'
            cmd.extend(['--extractor-args', 'youtube:skip=dash,hls'])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and result.stdout:
            urls = [line.strip() for line in result.stdout.splitlines() if line.strip().startswith('http')]
            return [{'url': u, 'title': u} for u in urls]
    except Exception:
        pass

    return []


def _extract_ytdlp_json(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
    """METHOD 2: yt-dlp --dump-json (More detailed, good for Instagram)"""
    try:
        cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--ignore-errors', '--no-warnings']
        if cookie_file:
            cmd.extend(['--cookies', cookie_file])
        if max_videos > 0:
            cmd.append(f'--playlist-end={max_videos}')

        # Platform-specific args
        if platform_key == 'instagram':
            cmd.extend([
                '--extractor-args', 'instagram:feed_count=100',
                '--user-agent', 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X)'
            ])
        elif platform_key == 'youtube':
            cmd.extend(['--extractor-args', 'youtube:player_client=android'])
        elif platform_key == 'tiktok':
            cmd.extend(['--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode == 0 and result.stdout:
            entries = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    video_url = data.get('webpage_url') or data.get('url')
                    if video_url:
                        entries.append({
                            'url': video_url,
                            'title': data.get('title', 'Untitled')[:100]
                        })
                except json.JSONDecodeError:
                    continue
            return entries
    except Exception:
        pass

    return []


def _extract_platform_specific(url: str, platform_key: str, cookie_file: str = None) -> typing.List[dict]:
    """METHOD 3: Platform-specific tools (Instaloader for Instagram, etc.)"""
    entries = []

    try:
        if platform_key == 'instagram':
            # Try instaloader for Instagram
            try:
                import instaloader
                username_match = re.search(r'instagram\.com/([^/?#]+)', url)
                if username_match and username_match.group(1) not in ['p', 'reel', 'tv', 'stories']:
                    username = username_match.group(1)
                    loader = instaloader.Instaloader(
                        quiet=True,
                        download_videos=False,
                        save_metadata=False,
                        download_pictures=False
                    )

                    # Load cookies if available
                    if cookie_file:
                        try:
                            cookies_dict = {}
                            with open(cookie_file, 'r', encoding='utf-8') as f:
                                for line in f:
                                    if line.strip() and not line.startswith('#'):
                                        parts = line.strip().split('\t')
                                        if len(parts) >= 7:
                                            cookies_dict[parts[5]] = parts[6]
                            if cookies_dict:
                                loader.context._session.cookies.update(cookies_dict)
                        except Exception:
                            pass

                    profile = instaloader.Profile.from_username(loader.context, username)
                    for post in profile.get_posts():
                        entries.append({
                            'url': f"https://www.instagram.com/p/{post.shortcode}/",
                            'title': (post.caption or 'Instagram Post')[:100]
                        })
                        if len(entries) >= 100:
                            break
            except Exception:
                pass

    except Exception:
        pass

    return entries


def extract_links_all_methods(url: str, platform_key: str, cookies_dir: Path, options: dict = None) -> typing.Tuple[typing.List[dict], str]:
    """Try ALL methods in priority order until success"""
    options = options or {}
    max_videos = int(options.get('max_videos', 0) or 0)
    creator = _extract_creator_from_url(url, platform_key)

    # Find cookies
    cookie_file = _find_cookie_file(cookies_dir, platform_key)
    temp_cookie_file = None

    if not cookie_file:
        temp_cookie_file = _extract_browser_cookies(platform_key)
        if temp_cookie_file:
            cookie_file = temp_cookie_file

    entries = []

    # METHOD 1: yt-dlp --get-url (Fastest)
    if not entries:
        entries = _extract_ytdlp_get_url(url, platform_key, cookie_file, max_videos)

    # METHOD 2: yt-dlp --dump-json (Better for Instagram)
    if not entries:
        entries = _extract_ytdlp_json(url, platform_key, cookie_file, max_videos)

    # METHOD 3: Platform-specific tools (Instaloader for Instagram)
    if not entries:
        entries = _extract_platform_specific(url, platform_key, cookie_file)

    # Cleanup temp cookies
    if temp_cookie_file and os.path.exists(temp_cookie_file):
        try:
            os.unlink(temp_cookie_file)
        except:
            pass

    # Apply limits
    if max_videos > 0 and entries:
        entries = entries[:max_videos]

    # Remove duplicates
    if entries:
        unique_urls = {}
        for entry in entries:
            normalized = _normalize_url(entry['url'])
            if normalized not in unique_urls:
                unique_urls[normalized] = entry
        entries = list(unique_urls.values())

    return entries, creator


# ============ THREAD CLASSES ============

class LinkGrabberThread(QThread):
    """Single URL link grabber with multiple methods"""

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

    def _save_links_to_creator_folder(self, creator_name: str, links: typing.List[dict]) -> str:
        """Save to: Desktop/Toseeq Links Grabber/@{CreatorName}/{CreatorName}_links.txt"""
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
            self.progress_percent.emit(10)

            platform_key = _detect_platform_key(self.url)

            if platform_key == 'unknown':
                self.finished.emit(False, "❌ Unsupported platform", [])
                return

            self.progress.emit(f"✅ Platform: {platform_key.upper()}")
            self.progress_percent.emit(20)

            # Extract using all methods
            self.progress.emit("🚀 Starting multi-method extraction...")
            entries, creator = extract_links_all_methods(
                self.url, platform_key, self.cookies_dir, self.options
            )

            if not entries:
                error_msg = (
                    f"❌ No links found from @{creator}\n\n"
                    "Try:\n"
                    "• Add cookies to cookies/ folder\n"
                    f"• Cookie file: {platform_key}.txt\n"
                    "• Check if account is public"
                )
                self.finished.emit(False, error_msg, [])
                return

            self.progress.emit(f"✅ Found {len(entries)} items from @{creator}")
            self.progress_percent.emit(60)

            # Process results
            total = len(entries)
            self.found_links = []

            for idx, entry in enumerate(entries, 1):
                if self.is_cancelled:
                    break

                self.found_links.append(entry)
                self.progress.emit(f"🔗 [{idx}/{total}] {entry['url'][:80]}...")
                self.link_found.emit(entry['url'], entry['url'])

                pct = 60 + int((idx / total) * 35)
                self.progress_percent.emit(min(pct, 95))

            if self.is_cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. Got {len(self.found_links)} links.", self.found_links)
                return

            self.progress.emit(f"✅ Success! {len(self.found_links)} links from @{creator}")
            self.progress_percent.emit(100)

            self.finished.emit(True, f"✅ {len(self.found_links)} links from @{creator}", self.found_links)

        except Exception as e:
            error_msg = f"❌ Unexpected error: {str(e)[:200]}"
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg, self.found_links)

    def cancel(self):
        self.is_cancelled = True


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
        self.creator_data = {}

        this_file = Path(__file__).resolve()
        self.cookies_dir = this_file.parent.parent.parent / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def _save_creator_to_folder(self, creator_name: str, links: typing.List[dict]) -> str:
        """Save to: Desktop/Toseeq Links Grabber/@{CreatorName}/{CreatorName}_links.txt"""
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
        """Save all creators to their folders"""
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
            self.progress.emit(f"🔍 Checking {total_urls} URLs...")
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

                self.progress.emit(f"\n📌 [{i}/{len(unique_urls)}] {url[:60]}...")

                platform_key = _detect_platform_key(url)
                entries, creator = extract_links_all_methods(
                    url,
                    platform_key,
                    self.cookies_dir,
                    self.options
                )

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

                self.progress.emit(f"✅ [{i}/{len(unique_urls)}] {len(entries)} links from @{creator}")

                pct = int((i / len(unique_urls)) * 95)
                self.progress_percent.emit(pct)

            if self.is_cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. {len(self.found_links)} total links.", self.found_links)
                return

            # Final summary
            self.progress.emit("\n" + "="*50)
            self.progress.emit("🎉 BULK COMPLETE!")
            self.progress.emit("="*50)
            self.progress.emit(f"📊 URLs: {len(unique_urls)}")
            self.progress.emit(f"👥 Creators: {len(self.creator_data)}")
            self.progress.emit(f"🔗 Total Links: {len(self.found_links)}")
            if duplicates_removed > 0:
                self.progress.emit(f"🧹 Duplicates: {duplicates_removed}")
            self.progress.emit("\n📁 Saved Folders:")
            for creator_name, data in self.creator_data.items():
                self.progress.emit(f"  ├── @{creator_name}/ ({len(data['links'])} links)")
            self.progress.emit("="*50)

            self.progress_percent.emit(100)
            self.finished.emit(True, f"✅ Bulk complete! {len(self.found_links)} links from {len(self.creator_data)} creators.", self.found_links)

        except Exception as e:
            self.finished.emit(False, f"❌ Bulk error: {str(e)[:200]}", self.found_links)

    def cancel(self):
        self.is_cancelled = True
