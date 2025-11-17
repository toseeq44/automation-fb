"""
modules/link_grabber/core.py
INTELLIGENT LINK GRABBER - Smart & Self-Learning

Features:
- 🧠 INTELLIGENT: Learns which method works best for each creator
- 📅 DATE EXTRACTION: Gets upload dates and sorts newest first
- 🔄 RETRY MECHANISM: Auto-retries on failures
- 🍪 COOKIE SUPPORT: Uses cookies from root/cookies folder
- 📊 PERFORMANCE TRACKING: Records and optimizes method selection
- 🎯 MULTI-METHOD: 10+ extraction methods with fallback
- 🗂️ PER-CREATOR FOLDERS: Organized output
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
from datetime import datetime
from urllib.parse import urlparse

# Import intelligence system
try:
    from .intelligence import get_learning_system
except ImportError:
    # Fallback if intelligence not available
    def get_learning_system():
        return None


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
    """Find cookie file - prioritize chrome_cookies.txt master file"""
    try:
        # PRIORITY 1: Master chrome_cookies.txt (2025 approach - one file for all platforms)
        master_cookie = cookies_dir / "chrome_cookies.txt"
        if master_cookie.exists() and master_cookie.stat().st_size > 10:
            return str(master_cookie)

        # PRIORITY 2: Platform-specific files (legacy support)
        cookie_file = cookies_dir / f"{platform_key}.txt"
        if cookie_file.exists() and cookie_file.stat().st_size > 10:
            return str(cookie_file)

        # PRIORITY 3: Generic fallback
        fallback = cookies_dir / "cookies.txt"
        if fallback.exists() and fallback.stat().st_size > 10:
            return str(fallback)
    except Exception:
        pass

    return None


def _get_platform_domain(platform_key: str) -> str:
    """Return the primary cookie domain for a platform"""
    domain_map = {
        'youtube': '.youtube.com',
        'instagram': '.instagram.com',
        'tiktok': '.tiktok.com',
        'facebook': '.facebook.com',
        'twitter': '.twitter.com'
    }
    return domain_map.get(platform_key, '')


def _extract_browser_cookies(platform_key: str, preferred_browser: str = None) -> typing.Optional[str]:
    """Extract cookies from browser (fallback)"""
    try:
        import browser_cookie3 as bc3
    except ImportError:
        return None

    domain = _get_platform_domain(platform_key)
    browsers = [
        ('chrome', getattr(bc3, 'chrome', None)),
        ('edge', getattr(bc3, 'edge', None)),
        ('firefox', getattr(bc3, 'firefox', None))
    ]

    if preferred_browser:
        preferred_browser = preferred_browser.lower()
        browsers = [b for b in browsers if b[0] == preferred_browser]

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


def _load_cookies_from_file(cookie_file: str, platform_key: str) -> typing.List[dict]:
    """Load cookies from Netscape cookie file filtered by platform domain"""
    cookies: typing.List[dict] = []
    if not cookie_file or not os.path.exists(cookie_file):
        return cookies

    domain_filter = _get_platform_domain(platform_key).lstrip('.')

    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line or line.startswith('#'):
                    continue

                parts = line.strip().split('\t')
                if len(parts) < 7:
                    continue

                domain, flag, path, secure, expires, name, value = parts[:7]

                if domain_filter and domain_filter not in domain:
                    continue

                try:
                    expires_int = int(float(expires))
                except (ValueError, TypeError):
                    expires_int = 0

                cookies.append({
                    'domain': domain.strip(),
                    'path': path or '/',
                    'secure': secure.upper() == 'TRUE',
                    'expires': expires_int if expires_int > 0 else None,
                    'name': name,
                    'value': value
                })
    except Exception:
        return []

    return cookies


def _normalize_url(url: str) -> str:
    """Normalize URL for duplicate detection"""
    try:
        # Platform-specific normalization
        if 'youtube.com/watch?v=' in url:
            match = re.search(r'v=([^&]+)', url)
            if match:
                return f"youtube_{match.group(1)}"
        elif 'youtu.be/' in url:
            match = re.search(r'youtu\.be/([^/?]+)', url)
            if match:
                return f"youtube_{match.group(1)}"
        elif 'instagram.com/p/' in url or 'instagram.com/reel/' in url:
            match = re.search(r'/(p|reel)/([^/?]+)', url)
            if match:
                return f"instagram_{match.group(2)}"
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


def _parse_upload_date(date_str: str) -> str:
    """Parse upload date from YYYYMMDD to YYYY-MM-DD"""
    try:
        if not date_str or date_str == '00000000':
            return 'Unknown'

        # YYYYMMDD format from yt-dlp
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        return date_str
    except Exception:
        return 'Unknown'


def _create_creator_folder(creator_name: str) -> Path:
    """Create creator folder and return path"""
    desktop = Path.home() / "Desktop"
    base_folder = desktop / "Links Graber"

    safe_creator = _safe_filename(f"@{creator_name}")
    creator_folder = base_folder / safe_creator
    creator_folder.mkdir(parents=True, exist_ok=True)

    return creator_folder


def _save_links_to_file(creator_name: str, links: typing.List[dict], creator_folder: Path) -> str:
    """Save links to creator's folder with dates"""
    filename = f"{_safe_filename(creator_name)}_links.txt"
    filepath = creator_folder / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Creator: {creator_name}\n")
        f.write(f"# Total Links: {len(links)}\n")
        f.write(f"# Sorted: Newest First\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("#" * 70 + "\n\n")

        for link in links:
            url = link['url']
            date = link.get('date', 'Unknown')
            title = link.get('title', '')

            # Format: URL # Date - Title (optional)
            if date != 'Unknown':
                f.write(f"{url}  # {date}")
                if title:
                    f.write(f" - {title[:50]}")
                f.write("\n")
            else:
                f.write(f"{url}\n")

    return str(filepath)


# ============ EXTRACTION METHODS ============

def _retry_on_failure(func, max_retries=3, delay=2):
    """Retry a function on failure with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(delay * (2 ** attempt))  # 2s, 4s, 8s
    return None


def _method_ytdlp_dump_json(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None) -> typing.List[dict]:
    """METHOD 1: yt-dlp --dump-json (WITH DATES) - PRIMARY METHOD"""
    try:
        cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--ignore-errors', '--no-warnings']

        # Cookie handling: browser OR file (2025 approach)
        if cookie_browser:
            cmd.extend(['--cookies-from-browser', cookie_browser])
        elif cookie_file:
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
                            'title': data.get('title', 'Untitled')[:100],
                            'date': data.get('upload_date', '00000000')
                        })
                except (json.JSONDecodeError, KeyError):
                    continue

            # Sort by date (newest first)
            entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)
            return entries

    except Exception as e:
        logging.debug(f"Method 1 (yt-dlp --dump-json) failed: {e}")

    return []


def _method_ytdlp_get_url(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None) -> typing.List[dict]:
    """METHOD 2: yt-dlp --get-url (FAST, NO DATES) - SIMPLIFIED LIKE BATCH SCRIPT"""
    try:
        # SIMPLE COMMAND like the working batch script: yt-dlp URL --flat-playlist --get-url
        cmd = ['yt-dlp', '--flat-playlist', '--get-url']

        # Cookie handling: browser OR file
        if cookie_browser:
            cmd.extend(['--cookies-from-browser', cookie_browser])
        elif cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        cmd.append(url)

        # DEBUG: Log the exact command being run
        logging.info(f"Running command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8',
            errors='replace'
        )

        # DEBUG: Log stdout and stderr
        if result.stdout:
            logging.info(f"STDOUT: {result.stdout[:500]}")
        if result.stderr:
            logging.info(f"STDERR: {result.stderr[:500]}")

        if result.stdout:
            urls = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and line.strip().startswith('http')
            ]

            # SIMPLIFIED: Don't filter, return all URLs found
            if urls:
                logging.info(f"Found {len(urls)} URLs before filtering")
                return [{'url': u, 'title': '', 'date': '00000000'} for u in urls]
            else:
                logging.warning(f"No http URLs found in output. Raw output: {result.stdout[:200]}")

    except Exception as e:
        logging.error(f"Method 2 (yt-dlp --get-url) exception: {e}")

    return []


def _method_ytdlp_with_retry(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None) -> typing.List[dict]:
    """METHOD 3: yt-dlp with retries (PERSISTENT)"""
    try:
        cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--ignore-errors',
               '--retries', '10', '--fragment-retries', '10', '--extractor-retries', '5',
               '--socket-timeout', '30']

        # Cookie handling: browser OR file
        if cookie_browser:
            cmd.extend(['--cookies-from-browser', cookie_browser])
        elif cookie_file:
            cmd.extend(['--cookies', cookie_file])

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        cmd.append(url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=240,
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
                            'title': data.get('title', '')[:100],
                            'date': data.get('upload_date', '00000000')
                        })
                except:
                    continue

            entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)
            return entries

    except Exception as e:
        logging.debug(f"Method 3 (yt-dlp with retry) failed: {e}")

    return []


def _method_ytdlp_user_agent(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None) -> typing.List[dict]:
    """METHOD 4: yt-dlp with different user agent (ANTI-BLOCK)"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile"
    ]

    for ua in user_agents:
        try:
            cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--ignore-errors',
                   '--user-agent', ua]

            # Cookie handling: browser OR file
            if cookie_browser:
                cmd.extend(['--cookies-from-browser', cookie_browser])
            elif cookie_file:
                cmd.extend(['--cookies', cookie_file])

            if max_videos > 0:
                cmd.extend(['--playlist-end', str(max_videos)])

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
                                'title': data.get('title', '')[:100],
                                'date': data.get('upload_date', '00000000')
                            })
                    except:
                        continue

                if entries:
                    entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)
                    return entries

        except Exception:
            continue

    return []


def _method_instaloader(url: str, platform_key: str, cookie_file: str = None) -> typing.List[dict]:
    """METHOD 5: Instaloader (INSTAGRAM SPECIALIST)"""
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
            download_pictures=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False
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
                'title': (post.caption or 'Instagram Post')[:100],
                'date': post.date_utc.strftime('%Y%m%d') if post.date_utc else '00000000'
            })
            if len(entries) >= 100:  # Limit for performance
                break

        # Sort by date (newest first)
        entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)
        return entries

    except ImportError:
        logging.debug("Instaloader not installed")
    except Exception as e:
        logging.debug(f"Method 5 (instaloader) failed: {e}")

    return []


def _method_gallery_dl(url: str, platform_key: str, cookie_file: str = None) -> typing.List[dict]:
    """METHOD 6: gallery-dl (INSTAGRAM/TIKTOK)"""
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
                        # Try to get date
                        date = data.get('date', '00000000')
                        if isinstance(date, int):
                            date = str(date)[:8]

                        entries.append({
                            'url': post_url,
                            'title': data.get('description', f'{platform_key.title()} Post')[:100],
                            'date': date
                        })
                except (json.JSONDecodeError, KeyError):
                    continue

            # Sort by date if available
            if entries:
                entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)
            return entries

    except FileNotFoundError:
        logging.debug("gallery-dl not installed")
    except Exception as e:
        logging.debug(f"Method 6 (gallery-dl) failed: {e}")

    return []


def _method_playwright(url: str, platform_key: str, cookie_file: str = None) -> typing.List[dict]:
    """METHOD 7: Playwright (BROWSER AUTOMATION - LAST RESORT)"""
    if platform_key not in ['tiktok', 'instagram']:
        return []

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            # Load cookies if available so we can access private/region locked content
            if cookie_file:
                cookies = _load_cookies_from_file(cookie_file, platform_key)
                playwright_cookies = []
                for cookie in cookies:
                    cookie_dict = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie.get('domain') or '',
                        'path': cookie.get('path', '/'),
                        'secure': cookie.get('secure', False),
                        'httpOnly': False,
                    }
                    if cookie.get('expires'):
                        cookie_dict['expires'] = cookie['expires']
                    playwright_cookies.append(cookie_dict)

                if playwright_cookies:
                    try:
                        context.add_cookies(playwright_cookies)
                    except Exception:
                        pass

            page = context.new_page()

            base_url_map = {
                'tiktok': 'https://www.tiktok.com/',
                'instagram': 'https://www.instagram.com/'
            }
            seed_url = base_url_map.get(platform_key, url)

            try:
                page.goto(seed_url, timeout=30000)
                time.sleep(1)
            except Exception:
                pass

            page.goto(url, timeout=30000)
            time.sleep(3)

            entries = []

            if platform_key == 'tiktok':
                # Adaptive scrolling - scroll until no new content
                previous_count = 0
                no_change_count = 0

                while no_change_count < 3:
                    video_links = page.query_selector_all('a[href*="/video/"]')
                    current_count = len(video_links)

                    if current_count == previous_count:
                        no_change_count += 1
                    else:
                        no_change_count = 0

                    previous_count = current_count
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(2)

                for link in video_links:
                    if href := link.get_attribute('href'):
                        full_url = f"https://www.tiktok.com{href}" if not href.startswith('http') else href
                        entries.append({'url': full_url, 'title': 'TikTok Video', 'date': '00000000'})

            elif platform_key == 'instagram':
                # Adaptive scrolling for Instagram
                previous_count = 0
                no_change_count = 0

                while no_change_count < 3:
                    post_links = page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')
                    current_count = len(post_links)

                    if current_count == previous_count:
                        no_change_count += 1
                    else:
                        no_change_count = 0

                    previous_count = current_count
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(2)

                for link in post_links:
                    if href := link.get_attribute('href'):
                        full_url = f"https://www.instagram.com{href}" if not href.startswith('http') else href
                        entries.append({'url': full_url, 'title': 'Instagram Post', 'date': '00000000'})

            context.close()
            browser.close()
            return entries

    except ImportError:
        logging.debug("Playwright not installed")
    except Exception as e:
        logging.debug(f"Method 7 (playwright) failed: {e}")

    return []


def _method_selenium(
    url: str,
    platform_key: str,
    max_videos: int = 0,
    cookie_file: str = None
) -> typing.List[dict]:
    """METHOD 8: Selenium (ABSOLUTE LAST RESORT with cookies)"""
    driver = None
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        options.add_argument('--window-size=1400,900')

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(40)

        # Load cookies if available (critical for TikTok private/region locked pages)
        cookies_loaded = False
        cookies = _load_cookies_from_file(cookie_file, platform_key) if cookie_file else []
        base_url_map = {
            'tiktok': 'https://www.tiktok.com/',
            'instagram': 'https://www.instagram.com/',
            'youtube': 'https://www.youtube.com/'
        }
        seed_url = base_url_map.get(platform_key, url)

        if cookies:
            driver.get(seed_url)
            time.sleep(2)
            for cookie in cookies:
                try:
                    payload = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'path': cookie.get('path', '/'),
                        'domain': cookie.get('domain', '').lstrip('.') or None,
                        'secure': cookie.get('secure', False)
                    }
                    if cookie.get('expires'):
                        payload['expiry'] = cookie['expires']
                    driver.add_cookie(payload)
                    cookies_loaded = True
                except Exception:
                    continue

        if cookies_loaded:
            driver.get(url)
        else:
            driver.get(url)

        time.sleep(5)

        selector_map = {
            'tiktok': 'a[href*="/video/"]',
            'instagram': 'a[href*="/p/"], a[href*="/reel/"]',
            'youtube': 'a[href*="/watch?v="]'
        }
        selector = selector_map.get(platform_key, 'a')

        seen_urls: typing.Set[str] = set()
        scroll_attempts = 0
        stagnant_rounds = 0

        while scroll_attempts < 20 and stagnant_rounds < 3:
            links = driver.find_elements(By.CSS_SELECTOR, selector)
            before_count = len(seen_urls)

            for link in links:
                href = link.get_attribute('href')
                if not href:
                    continue
                if platform_key == 'tiktok' and '/video/' not in href:
                    continue
                seen_urls.add(href)
                if max_videos and len(seen_urls) >= max_videos:
                    break

            if max_videos and len(seen_urls) >= max_videos:
                break

            if len(seen_urls) == before_count:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0

            driver.execute_script("window.scrollBy(0, 1500)")
            time.sleep(2)
            scroll_attempts += 1

        entries = []
        limit = max_videos or len(seen_urls)
        for href in list(seen_urls)[:limit]:
            entries.append({'url': href, 'title': '', 'date': '00000000'})

        return entries

    except ImportError:
        logging.debug("Selenium not installed")
    except Exception as e:
        logging.debug(f"Method 8 (selenium) failed: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return []


def extract_links_intelligent(
    url: str,
    platform_key: str,
    cookies_dir: Path,
    options: dict = None,
    progress_callback=None,
) -> typing.Tuple[typing.List[dict], str]:
    """
    INTELLIGENT EXTRACTION with learning system

    Uses learning cache to try best method first, then falls back to others.
    Records performance for future optimization.
    """

    try:
        options = options or {}
        max_videos = int(options.get('max_videos', 0) or 0)
        force_all_methods = bool(options.get('force_all_methods', False))
        cookie_browser = options.get('cookie_browser')  # "chrome", "firefox", "edge", or None
        creator = _extract_creator_from_url(url, platform_key)

        # Get learning system
        learning_system = get_learning_system()

        # Cookie handling: browser OR file
        cookie_file = None
        temp_cookie_files: typing.List[str] = []

        if cookie_browser:
            if progress_callback:
                progress_callback(f"🍪 Using {cookie_browser.title()} browser cookies directly")
            extracted = _extract_browser_cookies(platform_key, cookie_browser)
            if extracted:
                temp_cookie_files.append(extracted)
                cookie_file = extracted

        if not cookie_file:
            cookie_file = _find_cookie_file(cookies_dir, platform_key)

        if not cookie_file:
            extracted = _extract_browser_cookies(platform_key)
            if extracted:
                temp_cookie_files.append(extracted)
                cookie_file = extracted

        if cookie_file and progress_callback:
            cookie_name = Path(cookie_file).name
            progress_callback(f"🍪 Using cookies: {cookie_name}")

        # If we've materialized a cookie file, stop passing cookie_browser to yt-dlp.
        # yt-dlp's --cookies-from-browser mode ignores manual files and was causing 0 results
        # when users selected "Use Browser" but only had exported Netscape cookies.
        if cookie_file:
            cookie_browser = None

        entries: typing.List[dict] = []
        seen_normalized: typing.Set[str] = set()

        # Define all available methods (pass cookie_browser to yt-dlp methods)
        # PRIORITY ORDER: Simplest working methods first!
        all_methods = [
            ("Method 2: yt-dlp --get-url (SIMPLE - Like Batch Script)",
             lambda: _method_ytdlp_get_url(url, platform_key, cookie_file, max_videos, cookie_browser),
             True),

            ("Method 1: yt-dlp --dump-json (with dates)",
             lambda: _method_ytdlp_dump_json(url, platform_key, cookie_file, max_videos, cookie_browser),
             True),

            ("Method 3: yt-dlp with retries",
             lambda: _method_ytdlp_with_retry(url, platform_key, cookie_file, max_videos, cookie_browser),
             True),

            ("Method 4: yt-dlp with user agent",
             lambda: _method_ytdlp_user_agent(url, platform_key, cookie_file, max_videos, cookie_browser),
             True),

            ("Method 6: gallery-dl",
             lambda: _method_gallery_dl(url, platform_key, cookie_file),
             platform_key in ['instagram', 'tiktok']),

            ("Method 5: Instaloader",
             lambda: _method_instaloader(url, platform_key, cookie_file),
             platform_key == 'instagram'),

            ("Method 7: Playwright",
             lambda: _method_playwright(url, platform_key, cookie_file),
             platform_key in ['tiktok', 'instagram']),

            ("Method 8: Selenium",
             lambda: _method_selenium(url, platform_key, max_videos, cookie_file),
             True),
        ]

        # Filter allowed methods
        available_methods = [(name, func) for name, func, allowed in all_methods if allowed]

        # INTELLIGENCE: Check if we have learning data for this creator
        best_method_name = None
        if learning_system:
            best_method_name = learning_system.get_best_method(creator, platform_key)

            if best_method_name and progress_callback:
                progress_callback(f"🧠 Learning cache found for @{creator}")
                progress_callback(f"🎯 Best method: {best_method_name}")

        # Reorder methods to try best one first
        if best_method_name:
            # Move best method to front
            reordered = []
            best_method_func = None

            for name, func in available_methods:
                if name == best_method_name:
                    best_method_func = (name, func)
                else:
                    reordered.append((name, func))

            if best_method_func:
                available_methods = [best_method_func] + reordered

        # Try methods
        successful_method = None

        for method_name, method_func in available_methods:
            if max_videos > 0 and len(entries) >= max_videos:
                break

            if progress_callback:
                progress_callback(f"🔄 Trying: {method_name}")

            start_time = time.time()
            method_entries = []
            error_msg = ""

            try:
                method_entries = method_func()
            except Exception as e:
                error_msg = str(e)[:200]
                if progress_callback:
                    progress_callback(f"⚠️ {method_name} failed: {error_msg[:100]}")

            time_taken = time.time() - start_time

            # Merge unique entries
            added = 0
            for entry in method_entries:
                if max_videos > 0 and len(entries) >= max_videos:
                    break

                url_value = entry.get('url')
                if not url_value:
                    continue

                normalized = _normalize_url(url_value)
                if normalized in seen_normalized:
                    continue

                seen_normalized.add(normalized)
                entries.append(entry)
                added += 1

            # Record performance in learning system
            if learning_system:
                success = added > 0
                learning_system.record_performance(
                    creator,
                    platform_key,
                    method_name,
                    success,
                    added,
                    time_taken,
                    error_msg
                )

            if added > 0:
                successful_method = method_name
                if progress_callback:
                    progress_callback(f"✅ {method_name} → {added} links in {time_taken:.1f}s")

                if not force_all_methods:
                    break  # Stop on first success
            else:
                if progress_callback:
                    progress_callback(f"⚠️ {method_name} → 0 links")

        # Cleanup temp cookies
        for temp_cookie_file in temp_cookie_files:
            if temp_cookie_file and os.path.exists(temp_cookie_file):
                try:
                    os.unlink(temp_cookie_file)
                except Exception:
                    pass

        # Final processing
        if entries:
            # Remove duplicates
            entries = _remove_duplicate_entries(entries)

            # Sort by date (newest first)
            entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)

            # Limit if needed
            if max_videos > 0:
                entries = entries[:max_videos]

            if progress_callback:
                progress_callback(f"✅ Total: {len(entries)} unique links")
                if successful_method:
                    progress_callback(f"🎯 Successful method: {successful_method}")

        return entries, creator

    except Exception as e:
        if progress_callback:
            progress_callback(f"❌ Critical error: {str(e)[:200]}")
        return [], "unknown"


# ============ THREAD CLASSES ============

class LinkGrabberThread(QThread):
    """Single URL extraction with intelligence"""

    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    link_found = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str, list)

    def __init__(self, url: str, options: dict = None):
        super().__init__()
        self.url = (url or "").strip()
        self.options = options or {}
        self.is_cancelled = False
        self.found_links = []
        self.creator_name = ""

        # Use root cookies folder
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

            # Intelligent extraction
            def progress_cb(msg):
                self.progress.emit(msg)

            entries, creator = extract_links_intelligent(
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
                    "• Private account (add cookies via GUI)\n"
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

                # Format display with date
                date_str = _parse_upload_date(entry.get('date', '00000000'))
                display_text = f"{entry['url']}"
                if date_str != 'Unknown':
                    display_text += f"  ({date_str})"

                self.progress.emit(f"🔗 [{idx}/{total}] {display_text[:100]}...")
                self.link_found.emit(entry['url'], display_text)

                pct = 60 + int((idx / total) * 35)
                self.progress_percent.emit(min(pct, 95))

            if self.is_cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. Got {len(self.found_links)} links.", self.found_links)
                return

            self.progress.emit(f"✅ Success! {len(self.found_links)} links from @{creator}")
            self.progress.emit("💾 Use 'Save to Folder' in the GUI to export these links.")
            self.progress_percent.emit(100)

            self.finished.emit(True, f"✅ {len(self.found_links)} links from @{creator}", self.found_links)

        except Exception as e:
            error_msg = f"❌ Unexpected error: {str(e)[:200]}"
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg, self.found_links)

    def cancel(self):
        self.is_cancelled = True


class BulkLinkGrabberThread(QThread):
    """Bulk URLs extraction with intelligence"""

    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    link_found = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str, list)

    def __init__(self, urls: typing.List[str], options: dict = None):
        super().__init__()
        self.urls = [u.strip() for u in urls if u.strip()]
        self.options = options or {}
        self.is_cancelled = False
        self.found_links = []
        self.creator_data = {}

        # Use root cookies folder
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

                entries, creator = extract_links_intelligent(
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

                    # Format with date
                    date_str = _parse_upload_date(entry.get('date', '00000000'))
                    display_text = entry['url']
                    if date_str != 'Unknown':
                        display_text += f"  ({date_str})"

                    self.link_found.emit(entry['url'], display_text)

                self.progress.emit(f"✅ [{i}/{len(unique_urls)}] {len(entries)} links from @{creator}")

                pct = 30 + int((i / len(unique_urls)) * 65)
                self.progress_percent.emit(pct)

            if self.is_cancelled:
                self.finished.emit(False, f"⚠️ Cancelled. {len(self.found_links)} total links.", self.found_links)
                return

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

            self.progress.emit("\n💾 Use 'Save to Folder' to export all creators.")
            self.progress.emit("=" * 60)

            self.progress_percent.emit(100)
            self.finished.emit(True, f"✅ Bulk complete! {len(self.found_links)} links from {len(self.creator_data)} creators.", self.found_links)

        except Exception as e:
            error_msg = f"❌ Bulk error: {str(e)[:200]}"
            self.progress.emit(error_msg)
            self.finished.emit(False, error_msg, self.found_links)

    def cancel(self):
        self.is_cancelled = True
