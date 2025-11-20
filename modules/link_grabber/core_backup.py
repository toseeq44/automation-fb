"""
ULTIMATE LINK GRABBER - All Methods Combined
FIXED: Per-creator folder organization in bulk mode
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
from urllib.parse import urlparse
import re

# ============================================
# CORE HELPER FUNCTIONS
# ============================================

def _safe_filename(s: str) -> str:
    """Sanitize filename"""
    s = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s.strip())
    return s[:200] if s else "unknown"

def _extract_creator_from_url(url: str, platform_key: str) -> str:
    """Extract creator username from URL"""
    try:
        url_lower = url.lower()
        if platform_key == 'youtube':
            if '/@' in url_lower:
                return re.search(r'/@([^/?#]+)', url_lower).group(1)
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

def _extract_creator_from_link(link: str) -> str:
    """Platform-specific creator extraction from individual link URL"""
    parsed = urlparse(link)
    platform = _detect_platform_key(link)
    
    try:
        if platform == 'tiktok':
            match = re.search(r'/(@[^/]+)/video/', parsed.path)
            return match.group(1).lstrip('@') if match else 'unknown_tiktok'
        
        elif platform == 'instagram':
            match = re.search(r'instagram\.com/([^/?#]+)', link.lower())
            if match and match.group(1) not in ['p', 'reel', 'tv', 'stories']:
                return match.group(1)
            return 'unknown_instagram'
        
        elif platform == 'youtube':
            match = re.search(r'/channel/([^/?#]+)', link.lower()) or re.search(r'/@([^/?#]+)', link.lower())
            if match:
                return match.group(1)
            return 'unknown_youtube'
        
        elif platform in ['twitter', 'facebook']:
            match = re.search(r'(?:twitter|x|facebook)\.com/([^/?#]+)', link.lower())
            if match and match.group(1) not in ['i', 'home', 'explore', 'watch', 'groups']:
                return match.group(1)
            return f'unknown_{platform}'
        
        return 'unknown'
    except Exception:
        return 'unknown'

def _save_links_by_creator(creator_links_map, base_dir: str):
    """Save links in per-creator folders: Desktop/Links Grabber/@creator/creator_links.txt"""
    os.makedirs(base_dir, exist_ok=True)
    saved_files = []
    for creator_index, (creator, creator_links) in enumerate(creator_links_map.items(), 1):
        if not creator_links:
            continue
        
        try:
            # Folder: @creator_name
            safe_creator = _safe_filename(f"@{creator}")
            if safe_creator == "@unknown":
                safe_creator = f"@creator_{creator_index}"
            creator_folder = os.path.join(base_dir, safe_creator)
            os.makedirs(creator_folder, exist_ok=True)

            # File: creator_name_links.txt
            safe_filename_base = _safe_filename(creator)
            filename = f"{safe_filename_base}_links.txt"
            file_path = os.path.join(creator_folder, filename)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Creator: {creator}\n")
                f.write(f"# Total Links: {len(creator_links)}\n")
                f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("#" + "="*50 + "\n\n")
                for link in creator_links:
                    f.write(f"{link['url']}\n")
            
            saved_files.append(file_path)
            logging.info(f"✅ Saved: {safe_creator}/{filename}")
        
        except Exception as e:
            logging.error(f"Error saving for {creator}: {e}")

    return saved_files

def _detect_platform_key(url: str) -> str:
    """Detect platform from URL"""
    url_lower = url.lower()
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    if 'instagram.com' in url_lower:
        return 'instagram'
    if 'tiktok.com' in url_lower:
        return 'tiktok'
    if 'facebook.com' in url_lower or 'fb.' in url_lower:
        return 'facebook'
    if 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'twitter'
    return 'unknown'

def _find_cookie_file(cookies_dir: Path, platform_key: str) -> typing.Optional[str]:
    """
    Find cookie file - SIMPLE NAMES: instagram.txt, youtube.txt, etc.
    """
    # Simple file names - exactly what you have
    simple_files = [
        f"{platform_key}.txt",  # instagram.txt, youtube.txt, etc.
        "cookies.txt"  # Fallback to general cookies
    ]
    
    for filename in simple_files:
        cookie_path = cookies_dir / filename
        if cookie_path.exists() and cookie_path.stat().st_size > 10:
            logging.info(f"✅ Found cookie file: {filename}")
            return str(cookie_path)
    
    logging.warning(f"⚠️ No cookie file found for {platform_key}")
    return None

def _extract_browser_cookies(platform_key: str) -> typing.Optional[str]:
    """Extract cookies from browser using browser_cookie3"""
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
        ('chrome', bc3.chrome),
        ('edge', bc3.edge), 
        ('firefox', bc3.firefox),
        ('safari', bc3.safari)
    ]
    
    for browser_name, browser_func in browsers:
        if not browser_func:
            continue
        try:
            logging.info(f"🔍 Trying to extract {platform_key} cookies from {browser_name}...")
            cookie_jar = browser_func(domain_name=domain) if domain else browser_func()
            
            if cookie_jar and len(cookie_jar) > 0:
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w', 
                    suffix='.txt', 
                    delete=False, 
                    encoding='utf-8'
                )
                
                temp_file.write("# Netscape HTTP Cookie File\n")
                temp_file.write(f"# Extracted from {browser_name} for {platform_key}\n")
                temp_file.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
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
                logging.info(f"✅ Extracted {len(cookie_jar)} cookies from {browser_name}")
                return temp_file.name
                
        except Exception as e:
            logging.debug(f"Failed to extract from {browser_name}: {e}")
            continue
    
    logging.warning(f"⚠️ Could not extract {platform_key} cookies from any browser")
    return None

def _load_cookies_to_instaloader(loader, cookie_file: str) -> bool:
    """Parse Netscape cookie file and load into Instaloader session"""
    try:
        cookies_dict = {}
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        name = parts[5]
                        value = parts[6]
                        cookies_dict[name] = value
        
        if cookies_dict:
            loader.context._session.cookies.update(cookies_dict)
            username = loader.test_login()
            if username:
                loader.context.username = username
                logging.info(f"✅ Loaded Instagram cookies for user: {username}")
                return True
            else:
                logging.warning("⚠️ Instagram cookies loaded but test_login failed - possibly invalid/expired")
        else:
            logging.warning("⚠️ No cookies parsed from file")
        return False
    except Exception as e:
        logging.debug(f"Failed to load cookies to Instaloader: {e}")
        return False

# ============================================
# EXTRACTION METHODS - 5 LEVEL PRIORITY
# ============================================

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
    except Exception as e:
        logging.debug(f"yt-dlp --get-url failed: {e}")
    
    return []

def _extract_ytdlp_json(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
    """METHOD 2: yt-dlp --dump-json (More detailed)"""
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
                '--user-agent', 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1'
            ])
        elif platform_key == 'youtube':
            cmd.extend(['--extractor-args', 'youtube:player_client=android'])
        elif platform_key == 'tiktok':
            cmd.extend(['--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'])
        
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
                            'title': data.get('title', 'Untitled')[:100],
                            'duration': data.get('duration'),
                            'view_count': data.get('view_count'),
                        })
                except json.JSONDecodeError:
                    continue
            return entries
    except Exception as e:
        logging.debug(f"yt-dlp JSON failed: {e}")
    
    return []

def _extract_platform_specific(url: str, platform_key: str, cookie_file: str = None) -> typing.List[dict]:
    """METHOD 3: Platform-specific tools"""
    entries = []
    
    try:
        if platform_key == 'instagram':
            # Try gallery-dl for Instagram
            try:
                cmd = ['gallery-dl', '--dump-json', '--quiet']
                if cookie_file:
                    cmd.extend(['--cookies', cookie_file])
                cmd.append(url)
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0 and result.stdout:
                    for line in result.stdout.splitlines():
                        try:
                            data = json.loads(line)
                            if post_url := data.get('post_url') or data.get('url'):
                                entries.append({'url': post_url, 'title': 'Instagram Post'})
                        except:
                            pass
            except:
                pass
            
            # Try instaloader for Instagram
            if not entries:
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
                        
                        # Load cookies manually from Netscape file
                        if cookie_file:
                            _load_cookies_to_instaloader(loader, cookie_file)
                        
                        profile = instaloader.Profile.from_username(loader.context, username)
                        for post in profile.get_posts():
                            entries.append({
                                'url': f"https://www.instagram.com/p/{post.shortcode}/",
                                'title': (post.caption or 'Instagram Post')[:100]
                            })
                            if len(entries) >= 100:  # Increased limit for better coverage
                                break
                except Exception as e:
                    logging.debug(f"Instaloader failed: {e}")
                    
        elif platform_key == 'tiktok':
            # Try Playwright for TikTok
            try:
                from playwright.sync_api import sync_playwright
                username_match = re.search(r'tiktok\.com/@([^/?#]+)', url)
                if username_match:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        page = browser.new_page()
                        
                        # Set user agent
                        page.set_extra_http_headers({
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        })
                        
                        page.goto(f"https://www.tiktok.com/@{username_match.group(1)}", timeout=30000)
                        time.sleep(3)
                        
                        # Scroll to load videos
                        for _ in range(3):
                            page.evaluate("window.scrollBy(0, 1000)")
                            time.sleep(1)
                        
                        video_links = page.query_selector_all('a[href*="/video/"]')
                        for link in video_links:
                            if href := link.get_attribute('href'):
                                full_url = f"https://www.tiktok.com{href}" if not href.startswith('http') else href
                                entries.append({'url': full_url, 'title': 'TikTok Video'})
                        
                        browser.close()
            except Exception as e:
                logging.debug(f"Playwright failed: {e}")
                
    except Exception as e:
        logging.debug(f"Platform-specific extraction failed: {e}")
    
    return entries

def _extract_with_selenium(url: str, platform_key: str) -> typing.List[dict]:
    """METHOD 4: Selenium WebDriver (Last resort browser automation)"""
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
            # Find post links
            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/p/"]')
            for link in links:
                if href := link.get_attribute('href'):
                    entries.append({'url': href, 'title': 'Instagram Post'})
                    
        elif platform_key == 'tiktok':
            # Find video links
            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/video/"]')
            for link in links:
                if href := link.get_attribute('href'):
                    entries.append({'url': href, 'title': 'TikTok Video'})
                    
        elif platform_key == 'youtube':
            # Find video links
            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/watch?v="]')
            for link in links:
                if href := link.get_attribute('href'):
                    entries.append({'url': href, 'title': 'YouTube Video'})
        
        driver.quit()
        return entries
        
    except Exception as e:
        logging.debug(f"Selenium failed: {e}")
        return []

def _extract_requests_scraping(url: str, platform_key: str, cookie_file: str = None) -> typing.List[dict]:
    """METHOD 5: Lightweight requests scraping"""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        cookies = {}
        if cookie_file:
            try:
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            parts = line.strip().split('\t')
                            if len(parts) >= 7:
                                cookies[parts[5]] = parts[6]
            except Exception as e:
                logging.debug(f"Error loading cookies: {e}")
        
        response = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        entries = []
        
        # Platform-specific parsing
        if platform_key == 'instagram':
            for link in soup.find_all('a', href=re.compile(r'/p/[\w-]+/')):
                if href := link.get('href'):
                    full_url = f"https://www.instagram.com{href}" if not href.startswith('http') else href
                    entries.append({'url': full_url, 'title': 'Instagram Post'})
                    
        elif platform_key == 'youtube':
            # Look for video IDs in page content
            video_ids = re.findall(r'"videoId":"([\w-]{11})"', response.text)
            for vid in set(video_ids):
                entries.append({'url': f"https://www.youtube.com/watch?v={vid}", 'title': 'YouTube Video'})
                
        elif platform_key == 'tiktok':
            # Look for TikTok video URLs
            tiktok_urls = re.findall(r'https://www\.tiktok\.com/@[^/]+/video/\d+', response.text)
            for tiktok_url in set(tiktok_urls):
                entries.append({'url': tiktok_url, 'title': 'TikTok Video'})
        
        return entries
        
    except Exception as e:
        logging.debug(f"Requests scraping failed: {e}")
        return []

# ============================================
# MAIN EXTRACTION LOGIC - 5 LEVEL PRIORITY
# ============================================

def extract_links_all_methods(url: str, platform_key: str, cookies_dir: Path, options: dict = None) -> typing.Tuple[typing.List[dict], str]:
    """
    Try ALL methods in priority order until success
    """
    options = options or {}
    max_videos = int(options.get('max_videos', 0) or 0)
    creator = _extract_creator_from_url(url, platform_key)
    
    # Find cookies - USING SIMPLE NAMES
    cookie_file = _find_cookie_file(cookies_dir, platform_key)
    temp_cookie_file = None
    
    # If no manual cookie found, try browser extraction
    if not cookie_file:
        temp_cookie_file = _extract_browser_cookies(platform_key)
        if temp_cookie_file:
            cookie_file = temp_cookie_file
            logging.info("✅ Using browser-extracted cookies")
    
    entries = []
    method_used = "No method succeeded"
    
    # METHOD 1: yt-dlp --get-url (Fastest)
    if not entries:
        logging.info("🔄 Method 1: yt-dlp --get-url")
        entries = _extract_ytdlp_get_url(url, platform_key, cookie_file, max_videos)
        if entries:
            method_used = "yt-dlp --get-url"
    
    # METHOD 2: yt-dlp --dump-json (Detailed)
    if not entries:
        logging.info("🔄 Method 2: yt-dlp --dump-json")
        entries = _extract_ytdlp_json(url, platform_key, cookie_file, max_videos)
        if entries:
            method_used = "yt-dlp --dump-json"
    
    # METHOD 3: Platform-specific tools
    if not entries:
        logging.info("🔄 Method 3: Platform-specific tools")
        entries = _extract_platform_specific(url, platform_key, cookie_file)
        if entries:
            method_used = "Platform-specific"
    
    # METHOD 4: Selenium
    if not entries:
        logging.info("🔄 Method 4: Selenium")
        entries = _extract_with_selenium(url, platform_key)
        if entries:
            method_used = "Selenium"
    
    # METHOD 5: Requests scraping
    if not entries:
        logging.info("🔄 Method 5: Requests scraping")
        entries = _extract_requests_scraping(url, platform_key, cookie_file)
        if entries:
            method_used = "Requests scraping"
    
    # Cleanup temp cookies
    if temp_cookie_file and os.path.exists(temp_cookie_file):
        try:
            os.unlink(temp_cookie_file)
        except:
            pass
    
    # Apply final limits
    if max_videos > 0 and entries:
        entries = entries[:max_videos]
    
    if entries:
        logging.info(f"✅ Success with {method_used}: {len(entries)} links found")
    else:
        logging.warning(f"❌ All methods failed for {url}")
    
    return entries, creator

# ============================================
# PYQT THREAD CLASSES - FIXED BULK SAVE
# ============================================

class LinkGrabberThread(QThread):
    """Single URL - All Methods"""
    
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    link_found = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str, list)
    save_triggered = pyqtSignal(str, list)

    def __init__(self, url: str, options: dict = None):
        super().__init__()
        self.url = url.strip()
        self.options = options or {}
        self.is_cancelled = False
        self.found_links = []
        
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
                self.finished.emit(False, "❌ Unsupported platform or invalid URL", [])
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
                    "Possible reasons:\n"
                    "• Private account (add cookies to cookies/ folder)\n"  
                    "• Invalid URL\n"
                    "• Platform blocking access\n"
                    "• No content available\n\n"
                    f"💡 Add cookies to: {self.cookies_dir / f'{platform_key}.txt'}"
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
                display = entry['url']
                self.progress.emit(f"🔗 [{idx}/{total}] {display[:80]}...")
                self.link_found.emit(entry['url'], display)
                
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

    def save_to_file(self, creator_name: str):
        """Save with per-creator organization (matched to bulk)"""
        if not self.found_links:
            return
            
        desktop = Path.home() / "Desktop"
        main_folder = desktop / "Links Grabber"
        main_folder.mkdir(parents=True, exist_ok=True)
        
        safe_creator = _safe_filename(f"@{creator_name}")
        creator_folder = main_folder / safe_creator
        creator_folder.mkdir(exist_ok=True)
        
        filename = f"{_safe_filename(creator_name)}_links.txt"
        filepath = creator_folder / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# Creator: {creator_name}\n")
            f.write(f"# Total Links: {len(self.found_links)}\n")
            f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Source URL: {self.url}\n")
            f.write("#" + "="*50 + "\n\n")
            
            for link in self.found_links:
                f.write(f"{link['url']}\n")
        
        self.save_triggered.emit(str(filepath), self.found_links)

    def cancel(self):
        self.is_cancelled = True


class BulkLinkGrabberThread(QThread):
    """Bulk URLs - All Methods with PROPER Per-Creator Folders"""
    
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
        self.creator_links_map = {}
        
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
            self.urls = list(set(self.urls))
            total_urls = len(self.urls)
            self.progress.emit(f"✅ Removed duplicates. Processing {total_urls} unique URLs")

            self.found_links = []
            self.creator_links_map = {}
            
            for i, url in enumerate(self.urls, 1):
                if self.is_cancelled:
                    break
                
                self.progress.emit(f"🚀 Processing {i}/{total_urls}: {url[:60]}...")
                platform_key = _detect_platform_key(url)
                
                entries, creator = extract_links_all_methods(
                    url,
                    platform_key,
                    self.cookies_dir,
                    self.options
                )
                
                if creator not in self.creator_links_map:
                    self.creator_links_map[creator] = []
                
                for entry in entries:
                    if self.is_cancelled:
                        break
                    
                    self.found_links.append(entry)
                    self.creator_links_map[creator].append(entry)
                    display = entry['url']
                    self.progress.emit(f"🔗 [@{creator}] {display[:60]}...")
                    self.link_found.emit(entry['url'], display)
                
                pct = int((i / total_urls) * 95)
                self.progress_percent.emit(pct)

            if self.is_cancelled:
                self.finished.emit(
                    False,
                    f"⚠️ Cancelled. {len(self.found_links)} links from {len(self.creator_links_map)} creators.",
                    self.found_links
                )
                return

            self.progress.emit(
                f"\n✅ BULK EXTRACTION COMPLETE!\n"
                f"📊 Total: {len(self.found_links)} links from {len(self.creator_links_map)} creators\n"
            )
            
            for creator, links in self.creator_links_map.items():
                self.progress.emit(f"  📁 @{creator}: {len(links)} links")
            
            self.progress.emit("\n💾 Click 'Save to Folder' to organize and save")
            self.progress_percent.emit(100)
            
            self.finished.emit(
                True,
                f"✅ Bulk complete! {len(self.found_links)} links from {len(self.creator_links_map)} creators.",
                self.found_links
            )

        except Exception as e:
            logging.error(f"Bulk error: {e}", exc_info=True)
            self.finished.emit(False, f"❌ Bulk error: {str(e)[:200]}", self.found_links)

    def save_to_file(self):
        """Save with proper per-creator folder organization"""
        if not self.found_links or not self.creator_links_map:
            self.progress.emit("❌ No links to save")
            return
        
        desktop = Path.home() / "Desktop"
        main_folder = desktop / "Links Grabber"
        base_dir = str(main_folder)
        
        # Save using the new helper function with creator_links_map
        saved_files = _save_links_by_creator(self.creator_links_map, base_dir)
        
        # Create comprehensive summary
        try:
            summary_file = main_folder / "BULK_EXTRACTION_SUMMARY.txt"
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write("# ULTIMATE BULK LINK GRABBER SUMMARY\n")
                f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total Creators: {len(self.creator_links_map)}\n")
                f.write(f"# Total Links: {len(self.found_links)}\n")
                f.write("#" + "="*60 + "\n\n")
                
                for creator, links in self.creator_links_map.items():
                    f.write(f"📁 Creator: {creator}\n")
                    f.write(f"   Links: {len(links)}\n")
                    f.write(f"   Folder: @{_safe_filename(creator)}/\n\n")
        
            saved_files.append(str(summary_file))
            self.progress.emit(f"💾 Saved summary: {summary_file}")
        
        except Exception as e:
            self.progress.emit(f"❌ Error creating summary: {e}")

        self.progress.emit(
            f"\n🎉 BULK SAVE COMPLETE!\n"
            f"📁 Main Folder: {main_folder}\n"
            f"💾 Files Saved: {len(saved_files)}"
        )
        self.save_triggered.emit(str(main_folder), self.found_links)

    def cancel(self):
        self.is_cancelled = True