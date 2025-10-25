"""
modules/link_grabber/core.py
ULTIMATE LINK GRABBER - All Techniques Combined

Features:
- ALL extraction methods: yt-dlp, instaloader, gallery-dl, playwright, selenium, requests
- PER-CREATOR FOLDERS for both single and bulk mode
- Desktop/Toseeq Links Grabber/@{CreatorName}/{CreatorName}_links.txt
- Automatic duplicate removal
- Crash protection
- Multi-platform support
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
import shlex
from urllib.parse import urlparse


# ============ HELPER FUNCTIONS ============

def _safe_filename(s: str) -> str:
    """Sanitize filename"""
    try:
        s = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s.strip())
        return s[:200] if s else "unknown"
    except Exception:
        return "unknown"


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
        return platform_key or 'unknown'


def _detect_platform_key(url: str) -> str:
    """Detect platform from URL"""
    try:
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
    except Exception:
        pass
    return 'unknown'


def _find_cookie_file(cookies_dir: Path, platform_key: str) -> typing.Optional[str]:
    """Find cookie file - Simple names: instagram.txt, youtube.txt, etc."""
    try:
        # Platform-specific files
        cookie_file = cookies_dir / f"{platform_key}.txt"
        if cookie_file.exists() and cookie_file.stat().st_size > 10:
            return str(cookie_file)

        # Fallback: cookies.txt
        fallback = cookies_dir / "cookies.txt"
        if fallback.exists() and fallback.stat().st_size > 10:
            return str(fallback)
    except Exception:
        pass

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

    domain = domain_map.get(platform_key)
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
    try:
        # Platform-specific normalization
        if 'youtube.com/watch?v=' in url:
            # Extract video ID only for YouTube
            match = re.search(r'v=([^&]+)', url)
            if match:
                return f"youtube_{match.group(1)}"
        elif 'youtu.be/' in url:
            match = re.search(r'youtu\.be/([^/?]+)', url)
            if match:
                return f"youtube_{match.group(1)}"
        elif 'instagram.com/p/' in url:
            match = re.search(r'/p/([^/?]+)', url)
            if match:
                return f"instagram_{match.group(1)}"
        elif 'tiktok.com/@' in url and '/video/' in url:
            match = re.search(r'/video/(\d+)', url)
            if match:
                return f"tiktok_{match.group(1)}"

        # General normalization
        url = url.split('?')[0].split('#')[0]
        return url.lower().rstrip('/')
    except Exception:
        return url


def _remove_duplicate_entries(entries: typing.List[dict]) -> typing.List[dict]:
    """Remove duplicate entries based on normalized URLs"""
    try:
        seen = set()
        unique_entries = []
        
        for entry in entries:
            normalized = _normalize_url(entry['url'])
            if normalized not in seen:
                seen.add(normalized)
                unique_entries.append(entry)
                
        return unique_entries
    except Exception:
        return entries


def _create_creator_folder(creator_name: str) -> Path:
    """Create creator folder and return path"""
    desktop = Path.home() / "Desktop"
    base_folder = desktop / "Toseeq Links Grabber"
    
    safe_creator = _safe_filename(f"@{creator_name}")
    creator_folder = base_folder / safe_creator
    creator_folder.mkdir(parents=True, exist_ok=True)
    
    return creator_folder


def _save_links_to_file(creator_name: str, links: typing.List[dict], creator_folder: Path) -> str:
    """Save links to creator's folder and return file path"""
    filename = f"{_safe_filename(creator_name)}_links.txt"
    filepath = creator_folder / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Creator: {creator_name}\n")
        f.write(f"# Total Links: {len(links)}\n")
        f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("#" * 50 + "\n\n")
        
        for link in links:
            f.write(f"{link['url']}\n")

    return str(filepath)


# ============ ALL EXTRACTION METHODS ============

def _method_ytdlp_get_url(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
    """METHOD 1: yt-dlp --get-url (Fastest)"""
    try:
        cmd = ['yt-dlp', '--get-url', '--flat-playlist', '--ignore-errors', '--no-warnings']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        # Platform optimizations
        if platform_key == 'youtube':
            if any(x in url.lower() for x in ['/@', '/channel/', '/c/', '/user/']):
                base_url = url.split('/videos')[0].split('/streams')[0].split('/shorts')[0]
                url = base_url + '/videos'
            # Skip formats to avoid duplicates
            cmd.extend(['--extractor-args', 'youtube:skip=dash,hls,thumbnails'])

        cmd.append(url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8',
            errors='replace'
        )

        if result.stdout:
            urls = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and line.strip().startswith('http')
            ]

            if urls:
                # Filter platform-specific URLs
                filtered_urls = []
                for u in urls:
                    if platform_key == 'youtube' and ('youtube.com/watch?v=' in u or 'youtu.be/' in u):
                        filtered_urls.append(u)
                    elif platform_key == 'instagram' and 'instagram.com/p/' in u:
                        filtered_urls.append(u)
                    elif platform_key == 'tiktok' and 'tiktok.com/@' in u and '/video/' in u:
                        filtered_urls.append(u)
                    elif platform_key not in ['youtube', 'instagram', 'tiktok']:
                        filtered_urls.append(u)
                
                if filtered_urls:
                    return [{'url': u, 'title': u} for u in filtered_urls]

    except Exception as e:
        logging.debug(f"Method 1 (yt-dlp --get-url) failed: {e}")

    return []


def _method_ytdlp_dump_json(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
    """METHOD 2: yt-dlp --dump-json (Detailed)"""
    try:
        cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--ignore-errors', '--no-warnings']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        # Platform-specific optimizations
        if platform_key == 'instagram':
            cmd.extend(['--extractor-args', 'instagram:feed_count=100'])
        elif platform_key == 'youtube':
            cmd.extend(['--extractor-args', 'youtube:player_client=android'])

        cmd.append(url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            encoding='utf-8',
            errors='replace'
        )

        if result.stdout:
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
                except (json.JSONDecodeError, KeyError):
                    continue

            return entries

    except Exception as e:
        logging.debug(f"Method 2 (yt-dlp --dump-json) failed: {e}")

    return []


def _method_instaloader(url: str, platform_key: str, cookie_file: str = None) -> typing.List[dict]:
    """METHOD 3: Instaloader for Instagram"""
    if platform_key != 'instagram':
        return []

    try:
        import instaloader

        username_match = re.search(r'instagram\.com/([^/?#]+)', url)
        if not username_match or username_match.group(1) in ['p', 'reel', 'tv', 'stories']:
            return []

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
        entries = []

        for post in profile.get_posts():
            entries.append({
                'url': f"https://www.instagram.com/p/{post.shortcode}/",
                'title': (post.caption or 'Instagram Post')[:100]
            })
            if len(entries) >= 100:  # Limit for performance
                break

        return entries

    except ImportError:
        logging.debug("Instaloader not installed")
    except Exception as e:
        logging.debug(f"Method 3 (instaloader) failed: {e}")

    return []


def _method_gallery_dl(url: str, platform_key: str, cookie_file: str = None) -> typing.List[dict]:
    """METHOD 4: gallery-dl for Instagram/TikTok"""
    if platform_key not in ['instagram', 'tiktok']:
        return []

    try:
        cmd = ['gallery-dl', '--dump-json', '--quiet']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        cmd.append(url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8',
            errors='replace'
        )

        if result.stdout:
            entries = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    post_url = data.get('post_url') or data.get('url')
                    if post_url:
                        entries.append({'url': post_url, 'title': f'{platform_key.title()} Post'})
                except (json.JSONDecodeError, KeyError):
                    continue

            return entries

    except FileNotFoundError:
        logging.debug("gallery-dl not installed")
    except Exception as e:
        logging.debug(f"Method 4 (gallery-dl) failed: {e}")

    return []


def _method_playwright(url: str, platform_key: str) -> typing.List[dict]:
    """METHOD 5: Playwright browser automation"""
    if platform_key not in ['tiktok', 'instagram']:
        return []

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Set user agent
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            page.goto(url, timeout=30000)
            time.sleep(3)

            entries = []
            
            if platform_key == 'tiktok':
                # Scroll to load videos
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(1)
                
                video_links = page.query_selector_all('a[href*="/video/"]')
                for link in video_links:
                    if href := link.get_attribute('href'):
                        full_url = f"https://www.tiktok.com{href}" if not href.startswith('http') else href
                        entries.append({'url': full_url, 'title': 'TikTok Video'})
            
            elif platform_key == 'instagram':
                # Scroll to load posts
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(1)
                
                post_links = page.query_selector_all('a[href*="/p/"]')
                for link in post_links:
                    if href := link.get_attribute('href'):
                        full_url = f"https://www.instagram.com{href}" if not href.startswith('http') else href
                        entries.append({'url': full_url, 'title': 'Instagram Post'})

            browser.close()
            return entries

    except ImportError:
        logging.debug("Playwright not installed")
    except Exception as e:
        logging.debug(f"Method 5 (playwright) failed: {e}")

    return []


def _method_selenium(url: str, platform_key: str) -> typing.List[dict]:
    """METHOD 6: Selenium browser automation"""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(5)

        entries = []
        
        if platform_key == 'instagram':
            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/p/"]')
            for link in links:
                if href := link.get_attribute('href'):
                    entries.append({'url': href, 'title': 'Instagram Post'})
        
        elif platform_key == 'tiktok':
            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/video/"]')
            for link in links:
                if href := link.get_attribute('href'):
                    entries.append({'url': href, 'title': 'TikTok Video'})
        
        elif platform_key == 'youtube':
            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/watch?v="]')
            for link in links:
                if href := link.get_attribute('href'):
                    entries.append({'url': href, 'title': 'YouTube Video'})

        driver.quit()
        return entries

    except ImportError:
        logging.debug("Selenium not installed")
    except Exception as e:
        logging.debug(f"Method 6 (selenium) failed: {e}")

    return []


def extract_links_all_methods(url: str, platform_key: str, cookies_dir: Path, options: dict = None, progress_callback=None) -> typing.Tuple[typing.List[dict], str]:
    """
    Try ALL extraction methods in sequence
    """
    try:
        options = options or {}
        max_videos = int(options.get('max_videos', 0) or 0)
        creator = _extract_creator_from_url(url, platform_key)

        # Find cookies
        cookie_file = _find_cookie_file(cookies_dir, platform_key)
        temp_cookie_file = None

        if not cookie_file:
            temp_cookie_file = _extract_browser_cookies(platform_key)
            cookie_file = temp_cookie_file

        entries = []
        methods_tried = []

        # METHOD 1: yt-dlp --get-url
        if progress_callback:
            progress_callback("🔄 Method 1: yt-dlp --get-url")
        method_entries = _method_ytdlp_get_url(url, platform_key, cookie_file, max_videos)
        if method_entries:
            entries.extend(method_entries)
            methods_tried.append("yt-dlp --get-url")

        # METHOD 2: yt-dlp --dump-json
        if not entries and progress_callback:
            progress_callback("🔄 Method 2: yt-dlp --dump-json")
        if not entries:
            method_entries = _method_ytdlp_dump_json(url, platform_key, cookie_file, max_videos)
            if method_entries:
                entries.extend(method_entries)
                methods_tried.append("yt-dlp --dump-json")

        # METHOD 3: Instaloader (Instagram only)
        if not entries and platform_key == 'instagram':
            if progress_callback:
                progress_callback("🔄 Method 3: Instaloader")
            method_entries = _method_instaloader(url, platform_key, cookie_file)
            if method_entries:
                entries.extend(method_entries)
                methods_tried.append("instaloader")

        # METHOD 4: gallery-dl
        if not entries and platform_key in ['instagram', 'tiktok']:
            if progress_callback:
                progress_callback("🔄 Method 4: gallery-dl")
            method_entries = _method_gallery_dl(url, platform_key, cookie_file)
            if method_entries:
                entries.extend(method_entries)
                methods_tried.append("gallery-dl")

        # METHOD 5: Playwright
        if not entries and platform_key in ['tiktok', 'instagram']:
            if progress_callback:
                progress_callback("🔄 Method 5: Playwright")
            method_entries = _method_playwright(url, platform_key)
            if method_entries:
                entries.extend(method_entries)
                methods_tried.append("playwright")

        # METHOD 6: Selenium
        if not entries:
            if progress_callback:
                progress_callback("🔄 Method 6: Selenium")
            method_entries = _method_selenium(url, platform_key)
            if method_entries:
                entries.extend(method_entries)
                methods_tried.append("selenium")

        # Cleanup temp cookies
        if temp_cookie_file and os.path.exists(temp_cookie_file):
            try:
                os.unlink(temp_cookie_file)
            except:
                pass

        # Remove duplicates and apply limits
        if entries:
            entries = _remove_duplicate_entries(entries)
            
            if max_videos > 0:
                entries = entries[:max_videos]

            if progress_callback:
                progress_callback(f"✅ Success with: {', '.join(methods_tried)} - {len(entries)} links")

        return entries, creator

    except Exception as e:
        if progress_callback:
            progress_callback(f"❌ All methods failed: {str(e)[:200]}")
        return [], "unknown"


# ============ THREAD CLASSES ============

class LinkGrabberThread(QThread):
    """Single URL - ALL methods with per-creator folders"""

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
        self.creator_name = ""

        this_file = Path(__file__).resolve()
        self.cookies_dir = this_file.parent.parent.parent / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

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

            # Extract using ALL methods
            def progress_cb(msg):
                self.progress.emit(msg)

            entries, creator = extract_links_all_methods(
                self.url,
                platform_key,
                self.cookies_dir,
                self.options,
                progress_callback=progress_cb
            )

            self.creator_name = creator

            if not entries:
                error_msg = (
                    f"❌ No links found from @{creator}\n\n"
                    "Possible reasons:\n"
                    "• Private account (add cookies)\n"
                    "• Invalid URL\n"
                    "• Platform blocking\n"
                    "• No content available"
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

            # AUTO-SAVE for single URL (same as bulk behavior)
            if self.found_links and self.creator_name:
                self.progress.emit("💾 Auto-saving to creator folder...")
                saved_path = self._save_to_creator_folder()
                self.progress.emit(f"✅ Saved: {saved_path}")

            self.progress.emit(f"✅ Success! {len(self.found_links)} links from @{creator}")
            self.progress_percent.emit(100)

            self.finished.emit(True, f"✅ {len(self.found_links)} links from @{creator}", self.found_links)

        except Exception as e:
            error_msg = f"❌ Unexpected error: {str(e)[:200]}"
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg, self.found_links)

    def _save_to_creator_folder(self) -> str:
        """Save to creator folder and return file path"""
        if not self.found_links or not self.creator_name:
            return ""

        creator_folder = _create_creator_folder(self.creator_name)
        filepath = _save_links_to_file(self.creator_name, self.found_links, creator_folder)
        
        # Emit save signal for GUI
        self.save_triggered.emit(filepath, self.found_links)
        
        return filepath

    def save_to_file(self):
        """Manual save trigger (for GUI button)"""
        if self.found_links and self.creator_name:
            saved_path = self._save_to_creator_folder()
            self.progress.emit(f"💾 Manually saved: {saved_path}")

    def cancel(self):
        self.is_cancelled = True


class BulkLinkGrabberThread(QThread):
    """Bulk URLs - ALL methods with per-creator folders"""

    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    link_found = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str, list)
    save_triggered = pyqtSignal(str, list)

    def __init__(self, urls: typing.List[str], options: dict = None):
        super().__init__()
        self.urls = [u.strip() for u in urls if u.strip()]
        self.options = options or {}
        self.is_cancelled = False
        self.found_links = []
        self.creator_data = {}  # {creator_name: {'links': [], 'count': 0}}

        this_file = Path(__file__).resolve()
        self.cookies_dir = this_file.parent.parent.parent / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def run(self):
        try:
            total_urls = len(self.urls)
            if total_urls == 0:
                self.finished.emit(False, "❌ No URLs provided", [])
                return

            # Remove duplicate URLs
            unique_urls = []
            seen_urls = set()
            for url in self.urls:
                normalized = _normalize_url(url)
                if normalized not in seen_urls:
                    seen_urls.add(normalized)
                    unique_urls.append(url)

            duplicates_removed = len(self.urls) - len(unique_urls)
            if duplicates_removed > 0:
                self.progress.emit(f"🧹 Removed {duplicates_removed} duplicate URLs")

            self.progress.emit(f"🚀 Processing {len(unique_urls)} unique URLs...")
            self.progress.emit("=" * 60)

            self.found_links = []
            self.creator_data = {}

            # Process each URL
            for i, url in enumerate(unique_urls, 1):
                if self.is_cancelled:
                    break

                self.progress.emit(f"\n📌 [{i}/{len(unique_urls)}] {url[:60]}...")
                self.progress_percent.emit(int((i / len(unique_urls)) * 30))

                platform_key = _detect_platform_key(url)

                def progress_cb(msg):
                    self.progress.emit(f"  {msg}")

                entries, creator = extract_links_all_methods(
                    url,
                    platform_key,
                    self.cookies_dir,
                    self.options,
                    progress_callback=progress_cb
                )

                # Initialize creator data if not exists
                if creator not in self.creator_data:
                    self.creator_data[creator] = {
                        'links': [],
                        'source_urls': [],
                        'platform': platform_key
                    }

                # Add to results
                for entry in entries:
                    if self.is_cancelled:
                        break
                    self.found_links.append(entry)
                    self.creator_data[creator]['links'].append(entry)
                    self.creator_data[creator]['source_urls'].append(url)
                    self.link_found.emit(entry['url'], entry['url'])

                # Save this creator immediately
                if entries:
                    saved_path = self._save_creator_immediately(creator)
                    self.progress.emit(f"💾 Saved: {saved_path}")

                self.progress.emit(f"✅ [{i}/{len(unique_urls)}] {len(entries)} links from @{creator}")

                pct = 30 + int((i / len(unique_urls)) * 65)
                self.progress_percent.emit(pct)

            if self.is_cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. {len(self.found_links)} total links.", self.found_links)
                return

            # Create summary file
            summary_path = self._create_summary_file()
            
            # Final report
            self.progress.emit("\n" + "=" * 60)
            self.progress.emit("🎉 BULK EXTRACTION COMPLETE!")
            self.progress.emit("=" * 60)
            self.progress.emit(f"📊 URLs Processed: {len(unique_urls)}")
            self.progress.emit(f"👥 Creators Found: {len(self.creator_data)}")
            self.progress.emit(f"🔗 Total Links: {len(self.found_links)}")
            if duplicates_removed > 0:
                self.progress.emit(f"🧹 Duplicates Removed: {duplicates_removed}")
            
            self.progress.emit("\n📁 Creator Folders:")
            for creator_name, data in self.creator_data.items():
                self.progress.emit(f"  ├── @{creator_name}/ ({len(data['links'])} links)")
            
            self.progress.emit(f"\n📄 Summary: {summary_path}")
            self.progress.emit("=" * 60)

            self.progress_percent.emit(100)
            self.finished.emit(True, f"✅ Bulk complete! {len(self.found_links)} links from {len(self.creator_data)} creators.", self.found_links)

        except Exception as e:
            error_msg = f"❌ Bulk error: {str(e)[:200]}"
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg, self.found_links)

    def _save_creator_immediately(self, creator_name: str) -> str:
        """Save a creator's links immediately and return file path"""
        if creator_name not in self.creator_data:
            return ""

        creator_folder = _create_creator_folder(creator_name)
        filepath = _save_links_to_file(
            creator_name, 
            self.creator_data[creator_name]['links'], 
            creator_folder
        )
        
        return filepath

    def _create_summary_file(self) -> str:
        """Create bulk extraction summary file"""
        desktop = Path.home() / "Desktop"
        base_folder = desktop / "Toseeq Links Grabber"
        
        summary_file = base_folder / "BULK_EXTRACTION_SUMMARY.txt"
        
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("# BULK LINK EXTRACTION SUMMARY\n")
            f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total URLs: {len(self.urls)}\n")
            f.write(f"# Unique URLs: {len(set(self.urls))}\n")
            f.write(f"# Total Creators: {len(self.creator_data)}\n")
            f.write(f"# Total Links: {len(self.found_links)}\n")
            f.write("#" * 60 + "\n\n")
            
            f.write("CREATOR BREAKDOWN:\n")
            f.write("=" * 50 + "\n\n")
            
            for creator_name, data in self.creator_data.items():
                f.write(f"🎯 {creator_name}\n")
                f.write(f"   Platform: {data.get('platform', 'unknown')}\n")
                f.write(f"   Links: {len(data['links'])}\n")
                f.write(f"   Source URLs: {len(data['source_urls'])}\n")
                f.write(f"   Folder: @{_safe_filename(creator_name)}/\n")
                f.write(f"   File: {_safe_filename(creator_name)}_links.txt\n\n")
            
            f.write("\nPROCESSED URLs:\n")
            f.write("=" * 50 + "\n")
            for url in self.urls:
                f.write(f"- {url}\n")
        
        return str(summary_file)

    def save_to_file(self):
        """Manual save trigger - creates summary"""
        if not self.creator_data:
            self.progress.emit("❌ No links to save")
            return

        summary_path = self._create_summary_file()
        self.progress.emit(f"📄 Summary created: {summary_path}")
        
        # Emit save signal
        desktop = Path.home() / "Desktop"
        base_folder = desktop / "Toseeq Links Grabber"
        self.save_triggered.emit(str(base_folder), self.found_links)

    def cancel(self):
        self.is_cancelled = True