"""
Enhanced Link Grabber - Multi-method approach for maximum success rate
Supports: YouTube, Instagram, TikTok, Facebook, Twitter
Methods: yt-dlp, gallery-dl, instaloader, requests-based scraping
Cookie priority: manual files > desktop file > browser extraction
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


# ============================================
# HELPER FUNCTIONS
# ============================================

def _safe_filename(s: str) -> str:
    """Sanitize filename for filesystem"""
    s = s.strip()
    s = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s)
    s = re.sub(r'\s+', '_', s)
    if not s:
        return "links"
    return s[:200]


def _extract_creator_from_url(url: str, platform_key: str) -> str:
    """Extract creator username from URL"""
    try:
        u = url.strip().rstrip('/')
        
        if platform_key == 'youtube':
            # @username format
            m = re.search(r'@([A-Za-z0-9_\-\.]+)', u)
            if m:
                return m.group(1)
            # /channel/ID format
            m = re.search(r'/channel/([^/?#]+)', u)
            if m:
                return m.group(1)
            # /c/name format
            m = re.search(r'/c/([^/?#]+)', u)
            if m:
                return m.group(1)
            # /user/name format
            m = re.search(r'/user/([^/?#]+)', u)
            if m:
                return m.group(1)
            # Fallback
            parts = u.split('/')
            if parts:
                return parts[-1] or 'youtube'
            return 'youtube'
            
        elif platform_key == 'instagram':
            # instagram.com/username
            m = re.search(r'instagram\.com/([^/?#]+)', u)
            if m:
                username = m.group(1)
                # Filter out non-username paths
                if username not in ['p', 'reel', 'tv', 'stories', 'explore', 'accounts', 'direct']:
                    return username
            return 'instagram'
            
        elif platform_key == 'tiktok':
            # tiktok.com/@username
            m = re.search(r'tiktok\.com/@([^/?#]+)', u)
            if m:
                return m.group(1)
            return 'tiktok'
            
        elif platform_key == 'twitter':
            # twitter.com/username or x.com/username
            m = re.search(r'(?:twitter|x)\.com/([^/?#]+)', u)
            if m:
                username = m.group(1)
                # Filter out non-username paths
                if username not in ['i', 'home', 'explore', 'notifications', 'messages', 'search']:
                    return username
            return 'twitter'
            
        elif platform_key == 'facebook':
            # facebook.com/username or facebook.com/pages/...
            m = re.search(r'facebook\.com/(?:pages/)?([^/?#]+)', u)
            if m:
                username = m.group(1)
                # Filter out non-username paths
                if username not in ['watch', 'groups', 'events', 'pages', 'people', 'marketplace']:
                    return username
            return 'facebook'
            
        else:
            parts = u.split('/')
            if parts:
                return parts[-1] or platform_key
            return platform_key
            
    except Exception as e:
        logging.debug(f"Error extracting creator: {e}")
        return platform_key


def _detect_platform_key(url: str) -> str:
    """Detect platform from URL"""
    u = url.lower()
    
    if 'youtube.com' in u or 'youtu.be' in u:
        return 'youtube'
    if 'instagram.com' in u or 'instagr.am' in u:
        return 'instagram'
    if 'tiktok.com' in u:
        return 'tiktok'
    if 'facebook.com' in u or 'fb.com' in u or 'fb.watch' in u:
        return 'facebook'
    if 'twitter.com' in u or 'x.com' in u:
        return 'twitter'
    
    return 'unknown'


def _find_cookie_file(cookies_dir: Path, platform_key: str) -> typing.Optional[str]:
    """
    Find cookie file with priority:
    1. Platform-specific file in cookies/ folder
    2. General cookies.txt in cookies/ folder
    3. toseeq-cookies.txt on Desktop
    4. Any file with platform name in cookies/ folder
    5. Browser extraction (if browser_cookie3 available)
    """
    
    # Priority 1: Platform-specific file
    platform_mapping = {
        'youtube': ['youtube_cookies.txt', 'youtube.txt', 'yt_cookies.txt'],
        'instagram': ['instagram_cookies.txt', 'instagram.txt', 'ig_cookies.txt', 'insta_cookies.txt'],
        'tiktok': ['tiktok_cookies.txt', 'tiktok.txt', 'tt_cookies.txt'],
        'facebook': ['facebook_cookies.txt', 'facebook.txt', 'fb_cookies.txt'],
        'twitter': ['twitter_cookies.txt', 'twitter.txt', 'x_cookies.txt'],
    }
    
    filenames = platform_mapping.get(platform_key, [f'{platform_key}_cookies.txt'])
    
    for filename in filenames:
        cookie_path = cookies_dir / filename
        if cookie_path.exists() and cookie_path.stat().st_size > 10:
            logging.info(f"✅ Found cookie file: {cookie_path.name}")
            return str(cookie_path)
    
    # Priority 2: General cookies.txt
    general_cookie = cookies_dir / 'cookies.txt'
    if general_cookie.exists() and general_cookie.stat().st_size > 10:
        logging.info(f"✅ Found general cookie file: cookies.txt")
        return str(general_cookie)
    
    # Priority 3: Desktop toseeq-cookies.txt
    desktop_cookie = Path.home() / "Desktop" / "toseeq-cookies.txt"
    if desktop_cookie.exists() and desktop_cookie.stat().st_size > 10:
        logging.info(f"✅ Found Desktop cookie file: toseeq-cookies.txt")
        return str(desktop_cookie)
    
    # Priority 4: Search for any file with platform name
    try:
        for cookie_file in cookies_dir.iterdir():
            if not cookie_file.is_file():
                continue
            
            filename_lower = cookie_file.name.lower()
            
            # Check if platform name is in filename
            if platform_key and platform_key.lower() in filename_lower:
                if cookie_file.stat().st_size > 10:
                    logging.info(f"✅ Found cookie file by pattern: {cookie_file.name}")
                    return str(cookie_file)
            
            # Check for generic cookie files
            if any(keyword in filename_lower for keyword in ['cookie', 'cookies']):
                if cookie_file.stat().st_size > 10:
                    logging.info(f"✅ Found generic cookie file: {cookie_file.name}")
                    return str(cookie_file)
    except Exception as e:
        logging.debug(f"Error searching cookie files: {e}")
    
    logging.warning(f"⚠️ No cookie file found for {platform_key}")
    return None


def _extract_browser_cookies(platform_key: str) -> typing.Optional[str]:
    """Extract cookies from browser using browser_cookie3"""
    try:
        import browser_cookie3 as bc3
    except ImportError:
        logging.debug("browser_cookie3 not installed")
        return None
    
    domain_map = {
        'youtube': '.youtube.com',
        'instagram': '.instagram.com',
        'tiktok': '.tiktok.com',
        'facebook': '.facebook.com',
        'twitter': '.twitter.com'
    }
    
    domain = domain_map.get(platform_key)
    if not domain:
        return None
    
    # Try different browsers in order
    browsers = [
        ('Chrome', getattr(bc3, 'chrome', None)),
        ('Edge', getattr(bc3, 'edge', None)),
        ('Firefox', getattr(bc3, 'firefox', None)),
    ]
    
    for browser_name, browser_func in browsers:
        if not browser_func:
            continue
        
        try:
            logging.info(f"🔍 Trying to extract cookies from {browser_name}...")
            cookie_jar = browser_func(domain_name=domain)
            
            if cookie_jar and len(cookie_jar) > 0:
                # Save to temp file in Netscape format
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.txt',
                    delete=False,
                    encoding='utf-8'
                )
                
                temp_file.write("# Netscape HTTP Cookie File\n")
                temp_file.write("# This is a generated file! Do not edit.\n\n")
                
                for cookie in cookie_jar:
                    domain = getattr(cookie, 'domain', '')
                    flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                    path = getattr(cookie, 'path', '/')
                    secure = 'TRUE' if getattr(cookie, 'secure', False) else 'FALSE'
                    expires = getattr(cookie, 'expires', None)
                    expiry = str(int(expires)) if expires else '0'
                    name = getattr(cookie, 'name', '')
                    value = getattr(cookie, 'value', '')
                    
                    temp_file.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
                
                temp_file.close()
                logging.info(f"✅ Extracted cookies from {browser_name}")
                return temp_file.name
                
        except Exception as e:
            logging.debug(f"Failed to extract from {browser_name}: {e}")
            continue
    
    logging.warning("⚠️ Could not extract cookies from any browser")
    return None


# ============================================
# EXTRACTION METHODS
# ============================================

def _extract_with_ytdlp(url: str, platform_key: str, cookie_file: str = None, timeout: int = 300) -> typing.Tuple[typing.List[dict], str]:
    """
    Method 1: Extract using yt-dlp (most reliable, works for all platforms)
    """
    try:
        logging.info("🔧 Method 1: Using yt-dlp...")
        
        # Build command
        cmd_parts = [
            'yt-dlp',
            '--flat-playlist',
            '--dump-json',
            '--quiet',
            '--no-warnings',
            '--ignore-errors',
            '--no-check-certificate'
        ]
        
        # Add cookies
        if cookie_file:
            cmd_parts.extend(['--cookies', cookie_file])
        
        # Platform-specific optimizations
        if platform_key == 'youtube':
            # For YouTube channels, ensure we get all tabs
            if '/@' in url or '/channel/' in url or '/c/' in url or '/user/' in url:
                # Remove any tab specifiers and add /videos
                base_url = url.split('/videos')[0].split('/shorts')[0].split('/streams')[0]
                url = base_url + '/videos'
            cmd_parts.extend(['--extractor-args', 'youtube:player_client=android'])
            
        elif platform_key == 'instagram':
            cmd_parts.extend([
                '--extractor-args', 'instagram:api_version=2',
                '--user-agent', 'Instagram 76.0.0.15.395 Android'
            ])
            
        elif platform_key == 'tiktok':
            cmd_parts.extend(['--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TikTok'])
        
        cmd_parts.append(url)
        
        # Execute
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            logging.warning(f"yt-dlp failed: {error_msg}")
            return [], "unknown"
        
        # Parse JSON output
        entries = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                # Extract URL
                video_url = data.get('webpage_url') or data.get('url')
                if not video_url and data.get('id'):
                    # Construct URL from ID
                    if platform_key == 'youtube':
                        video_url = f"https://www.youtube.com/watch?v={data['id']}"
                    elif platform_key == 'instagram':
                        video_url = f"https://www.instagram.com/p/{data['id']}/"
                    elif platform_key == 'tiktok':
                        video_url = f"https://www.tiktok.com/@{data.get('uploader_id', 'unknown')}/video/{data['id']}"
                
                if video_url:
                    entries.append({
                        'url': video_url,
                        'title': data.get('title', 'Untitled'),
                        'duration': data.get('duration'),
                        'view_count': data.get('view_count'),
                    })
                    
            except json.JSONDecodeError:
                # Not JSON, might be a direct URL
                if line.startswith('http'):
                    entries.append({'url': line, 'title': line})
        
        if entries:
            creator = _extract_creator_from_url(url, platform_key)
            logging.info(f"✅ yt-dlp found {len(entries)} videos")
            return entries, creator
        
        logging.warning("⚠️ yt-dlp returned no results")
        return [], "unknown"
        
    except subprocess.TimeoutExpired:
        logging.error(f"❌ yt-dlp timeout after {timeout}s")
        return [], "unknown"
    except FileNotFoundError:
        logging.error("❌ yt-dlp not found in PATH")
        return [], "unknown"
    except Exception as e:
        logging.error(f"❌ yt-dlp error: {e}")
        return [], "unknown"


def _extract_instagram_gallerydl(url: str, cookie_file: str = None) -> typing.List[dict]:
    """
    Method 2: Instagram using gallery-dl (better for Instagram than yt-dlp)
    """
    try:
        logging.info("🔧 Method 2: Using gallery-dl for Instagram...")
        
        cmd_parts = ['gallery-dl', '--dump-json', '--quiet']
        
        if cookie_file:
            cmd_parts.extend(['--cookies', cookie_file])
        
        cmd_parts.append(url)
        
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0 and result.stdout:
            entries = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    post_url = data.get('post_url') or data.get('url')
                    if post_url:
                        entries.append({
                            'url': post_url,
                            'title': data.get('description', 'Instagram Post')[:100]
                        })
                except:
                    pass
            
            if entries:
                logging.info(f"✅ gallery-dl found {len(entries)} posts")
                return entries
        
        logging.warning("⚠️ gallery-dl returned no results")
        return []
        
    except FileNotFoundError:
        logging.debug("gallery-dl not installed")
        return []
    except Exception as e:
        logging.debug(f"gallery-dl error: {e}")
        return []


def _extract_instagram_instaloader(url: str, cookie_file: str = None) -> typing.List[dict]:
    """
    Method 3: Instagram using instaloader (Python library)
    """
    try:
        logging.info("🔧 Method 3: Using instaloader for Instagram...")
        
        import instaloader
        
        # Extract username from URL
        username_match = re.search(r'instagram\.com/([^/?#]+)', url)
        if not username_match:
            return []
        
        username = username_match.group(1)
        
        # Filter out non-username paths
        if username in ['p', 'reel', 'tv', 'stories']:
            return []
        
        # Initialize instaloader
        loader = instaloader.Instaloader(
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True
        )
        
        # Login with cookies if available
        if cookie_file:
            try:
                # Instaloader can import session from cookies
                # This is a simplified version, actual implementation may vary
                pass
            except:
                pass
        
        # Get profile
        profile = instaloader.Profile.from_username(loader.context, username)
        
        # Get posts
        entries = []
        for post in profile.get_posts():
            post_url = f"https://www.instagram.com/p/{post.shortcode}/"
            entries.append({
                'url': post_url,
                'title': (post.caption or '')[:100],
                'view_count': post.video_view_count if post.is_video else None
            })
            
            # Limit to prevent hanging
            if len(entries) >= 1000:
                break
        
        if entries:
            logging.info(f"✅ instaloader found {len(entries)} posts")
            return entries
        
        return []
        
    except ImportError:
        logging.debug("instaloader not installed")
        return []
    except Exception as e:
        logging.debug(f"instaloader error: {e}")
        return []


def _extract_tiktok_playwright(url: str) -> typing.List[dict]:
    """
    Method 4: TikTok using Playwright (browser automation)
    """
    try:
        logging.info("🔧 Method 4: Using Playwright for TikTok...")
        
        from playwright.sync_api import sync_playwright
        
        # Extract username
        username_match = re.search(r'tiktok\.com/@([^/?#]+)', url)
        if not username_match:
            return []
        
        username = username_match.group(1)
        profile_url = f"https://www.tiktok.com/@{username}"
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Navigate to profile
            page.goto(profile_url, wait_until='domcontentloaded', timeout=30000)
            
            # Scroll to load videos
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 1000)")
                time.sleep(0.5)
            
            # Extract video links
            video_links = page.query_selector_all('a[href*="/video/"]')
            
            entries = []
            for link in video_links:
                href = link.get_attribute('href')
                if href and '/video/' in href:
                    if not href.startswith('http'):
                        href = f"https://www.tiktok.com{href}"
                    entries.append({'url': href, 'title': 'TikTok Video'})
            
            browser.close()
            
            if entries:
                logging.info(f"✅ Playwright found {len(entries)} videos")
                return list({v['url']: v for v in entries}.values())  # Remove duplicates
        
        return []
        
    except ImportError:
        logging.debug("playwright not installed")
        return []
    except Exception as e:
        logging.debug(f"playwright error: {e}")
        return []


def _extract_with_requests(url: str, platform_key: str, cookie_file: str = None) -> typing.List[dict]:
    """
    Method 5: Lightweight HTML scraping using requests (fallback)
    """
    try:
        logging.info("🔧 Method 5: Using requests-based scraping...")
        
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Load cookies if available
        cookies = {}
        if cookie_file:
            try:
                with open(cookie_file, 'r') as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            parts = line.split('\t')
                            if len(parts) >= 7:
                                cookies[parts[5]] = parts[6].strip()
            except:
                pass
        
        # Make request
        response = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        entries = []
        
        if platform_key == 'instagram':
            # Look for post links in HTML
            links = soup.find_all('a', href=re.compile(r'/p/[\w-]+/'))
            for link in links:
                href = link.get('href')
                if href:
                    full_url = f"https://www.instagram.com{href}" if not href.startswith('http') else href
                    entries.append({'url': full_url, 'title': 'Instagram Post'})
        
        elif platform_key == 'youtube':
            # Look for video IDs in scripts
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'videoId' in script.string:
                    video_ids = re.findall(r'"videoId":"([\w-]{11})"', script.string)
                    for vid in set(video_ids):
                        entries.append({
                            'url': f"https://www.youtube.com/watch?v={vid}",
                            'title': 'YouTube Video'
                        })
        
        if entries:
            # Remove duplicates
            unique_entries = list({v['url']: v for v in entries}.values())
            logging.info(f"✅ Requests scraping found {len(unique_entries)} items")
            return unique_entries
        
        return []
        
    except ImportError:
        logging.debug("requests or beautifulsoup4 not installed")
        return []
    except Exception as e:
        logging.debug(f"requests scraping error: {e}")
        return []


# ============================================
# MAIN EXTRACTION LOGIC
# ============================================

def extract_all_links(url: str, platform_key: str, cookies_dir: Path, options: dict = None) -> typing.Tuple[typing.List[dict], str]:
    """
    Try multiple extraction methods until one succeeds
    
    Returns: (list of video entries, creator name)
    """
    
    options = options or {}
    entries = []
    creator = _extract_creator_from_url(url, platform_key)
    
    # Find cookie file
    cookie_file = _find_cookie_file(cookies_dir, platform_key)
    
    # If no manual cookie found, try browser extraction
    temp_cookie_file = None
    if not cookie_file:
        temp_cookie_file = _extract_browser_cookies(platform_key)
        if temp_cookie_file:
            cookie_file = temp_cookie_file
            logging.info("✅ Using browser-extracted cookies")
    
    # Try methods in order of reliability
    
    # Method 1: yt-dlp (works for all platforms)
    entries, creator = _extract_with_ytdlp(url, platform_key, cookie_file)
    if entries:
        if temp_cookie_file:
            try:
                os.unlink(temp_cookie_file)
            except:
                pass
        return entries, creator
    
    # Platform-specific fallback methods
    if platform_key == 'instagram':
        # Method 2: gallery-dl
        entries_gl = _extract_instagram_gallerydl(url, cookie_file)
        if entries_gl:
            entries = entries_gl
        
        # Method 3: instaloader
        if not entries:
            entries_il = _extract_instagram_instaloader(url, cookie_file)
            if entries_il:
                entries = entries_il
    
    elif platform_key == 'tiktok':
        # Method 4: Playwright
        entries_pw = _extract_tiktok_playwright(url)
        if entries_pw:
            entries = entries_pw
    
    # Method 5: requests-based scraping (last resort)
    if not entries:
        entries = _extract_with_requests(url, platform_key, cookie_file)
    
    # Cleanup temp cookie file
    if temp_cookie_file:
        try:
            os.unlink(temp_cookie_file)
        except:
            pass
    
    return entries, creator


# ============================================
# PYQT THREAD CLASSES
# ============================================

class LinkGrabberThread(QThread):
    """Single-URL link grabber with multi-method fallback"""
    
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
        
        # Setup paths
        this_file = Path(__file__).resolve()
        self.cookies_dir = this_file.parent.parent.parent / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def run(self):
        try:
            if not self.url:
                self.finished.emit(False, "❌ No URL provided", [])
                return

            self.progress.emit("🔍 Detecting platform...")
            self.progress_percent.emit(5)
            
            platform_key = _detect_platform_key(self.url)
            
            if platform_key == 'unknown':
                self.finished.emit(False, "❌ Unsupported platform or invalid URL", [])
                return
            
            self.progress.emit(f"✅ Platform: {platform_key.upper()}")
            self.progress_percent.emit(15)
            
            # Extract links using all methods
            self.progress.emit(f"🚀 Extracting links using multiple methods...")
            self.progress_percent.emit(20)
            
            entries, creator = extract_all_links(
                self.url,
                platform_key,
                self.cookies_dir,
                self.options
            )
            
            if not entries:
                msg = (
                    f"❌ Could not extract links from @{creator}\n\n"
                    "Possible reasons:\n"
                    "• Account is private (add cookies)\n"
                    "• Invalid URL\n"
                    "• Platform blocking access\n"
                    "• No videos available"
                )
                self.finished.emit(False, msg, [])
                return

            self.progress.emit(f"✅ Found {len(entries)} videos from @{creator}")
            self.progress_percent.emit(30)
            
            # Apply limits
            max_videos = int(self.options.get('max_videos', 0) or 0)
            if max_videos > 0:
                entries = entries[:max_videos]
                self.progress.emit(f"📊 Limited to first {max_videos} videos")

            total = len(entries)
            self.found_links = []
            
            # Process entries
            for idx, entry in enumerate(entries, 1):
                if self.is_cancelled:
                    break
                
                self.found_links.append(entry)
                display = entry['url']
                self.progress.emit(f"🔗 [{idx}/{total}] {display[:80]}...")
                self.link_found.emit(entry['url'], display)
                
                # Update progress
                pct = 30 + int((idx / total) * 65)
                self.progress_percent.emit(min(pct, 95))

            if self.is_cancelled:
                self.finished.emit(
                    False,
                    f"⚠️ Cancelled. Extracted {len(self.found_links)} links.",
                    self.found_links
                )
                return

            # Success
            self.progress.emit(
                f"✅ Successfully extracted {len(self.found_links)} links from @{creator}!\n"
                "Click 'Save to Folder' to save."
            )
            self.progress_percent.emit(100)
            self.finished.emit(
                True,
                f"✅ Done! {len(self.found_links)} links from @{creator}.",
                self.found_links
            )

        except Exception as exc:
            msg = f"❌ Unexpected error: {str(exc)[:200]}"
            logging.error(msg, exc_info=True)
            self.progress.emit(msg)
            self.finished.emit(False, msg, self.found_links)

    def save_to_file(self, creator_name: str):
        """Save links to file"""
        if not self.found_links:
            return
        
        desktop = Path.home() / "Desktop"
        folder = desktop / "Toseeq Links Grabber"
        folder.mkdir(parents=True, exist_ok=True)
        
        filename = _safe_filename(creator_name) + ".txt"
        filepath = folder / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# Links from: {creator_name}\n")
            f.write(f"# Total: {len(self.found_links)}\n")
            f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("#" + "="*60 + "\n\n")
            
            for link in self.found_links:
                f.write(f"{link['url']}\n")
        
        self.save_triggered.emit(str(filepath), self.found_links)

    def cancel(self):
        self.is_cancelled = True


class BulkLinkGrabberThread(QThread):
    """Multiple URLs link grabber"""
    
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

            self.found_links = []
            self.creator_links_map = {}
            
            for i, url in enumerate(self.urls, 1):
                if self.is_cancelled:
                    break
                
                self.progress.emit(f"🚀 Processing {i}/{total_urls}: {url[:60]}...")
                
                # Detect platform
                platform_key = _detect_platform_key(url)
                
                # Extract links
                entries, creator = extract_all_links(
                    url,
                    platform_key,
                    self.cookies_dir,
                    self.options
                )
                
                # Initialize creator list
                if creator not in self.creator_links_map:
                    self.creator_links_map[creator] = []
                
                # Apply limits
                max_videos = int(self.options.get('max_videos', 0) or 0)
                if max_videos > 0:
                    entries = entries[:max_videos]

                # Add to results
                for entry in entries:
                    if self.is_cancelled:
                        break
                    
                    self.found_links.append(entry)
                    self.creator_links_map[creator].append(entry)
                    display = entry['url']
                    self.progress.emit(f"🔗 [@{creator}] {display[:60]}...")
                    self.link_found.emit(entry['url'], display)
                
                # Update progress
                pct = int((i / total_urls) * 95)
                self.progress_percent.emit(pct)

            if self.is_cancelled:
                self.finished.emit(
                    False,
                    f"⚠️ Cancelled. {len(self.found_links)} links from {len(self.creator_links_map)} creators.",
                    self.found_links
                )
                return

            # Show summary
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
        """Save links organized by creator"""
        if not self.found_links:
            return
        
        desktop = Path.home() / "Desktop"
        main_folder = desktop / "Toseeq Links Grabber"
        main_folder.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        
        # Save per creator
        for creator, links in self.creator_links_map.items():
            if not links:
                continue
            
            safe_creator = _safe_filename(creator)
            creator_folder = main_folder / safe_creator
            creator_folder.mkdir(parents=True, exist_ok=True)
            
            filename = f"{safe_creator}_links.txt"
            filepath = creator_folder / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Creator: {creator}\n")
                f.write(f"# Total Links: {len(links)}\n")
                f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("#" + "="*60 + "\n\n")
                
                for link in links:
                    f.write(f"{link['url']}\n")
            
            saved_files.append(str(filepath))
            self.progress.emit(f"💾 Saved: {safe_creator}/{filename}")
        
        # Create summary
        summary_file = main_folder / "bulk_summary.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("# BULK LINK EXTRACTION SUMMARY\n")
            f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total Creators: {len(self.creator_links_map)}\n")
            f.write(f"# Total Links: {len(self.found_links)}\n")
            f.write("#" + "="*60 + "\n\n")
            
            for creator, links in self.creator_links_map.items():
                f.write(f"📁 Creator: {creator}\n")
                f.write(f"   Links: {len(links)}\n")
                f.write(f"   Folder: {_safe_filename(creator)}/\n\n")
        
        saved_files.append(str(summary_file))
        
        main_path = str(main_folder)
        self.save_triggered.emit(main_path, self.found_links)

    def cancel(self):
        self.is_cancelled = True