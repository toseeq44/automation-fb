"""
modules/link_grabber/core.py
INTELLIGENT LINK GRABBER - Smart & Self-Learning

Features:
- ALL extraction methods: yt-dlp, instaloader, gallery-dl, playwright, selenium, requests
- PER-CREATOR FOLDERS for both single and bulk mode
- Desktop/Links Grabber/@{CreatorName}/{CreatorName}_links.txt
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
import random
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


def _validate_cookie_file(cookie_file: str, max_age_days: int = 14) -> dict:
    """
    ENHANCED: Validate cookie file for freshness and format validity

    Checks:
    1. File exists and has content
    2. File age (freshness) - warns if older than max_age_days
    3. Valid Netscape format
    4. Contains non-expired cookies

    Args:
        cookie_file: Path to cookie file
        max_age_days: Maximum age in days before warning (default 14)

    Returns:
        dict with:
        - valid: bool (overall validity)
        - fresh: bool (file age <= max_age_days)
        - age_days: int (file age in days)
        - total_cookies: int (total lines)
        - expired_cookies: int (count of expired cookies)
        - warnings: list[str] (validation warnings)
    """
    result = {
        'valid': False,
        'fresh': True,
        'age_days': 0,
        'total_cookies': 0,
        'expired_cookies': 0,
        'warnings': []
    }

    try:
        from datetime import datetime, timedelta
        import time

        cookie_path = Path(cookie_file)

        # Check 1: File exists and has content
        if not cookie_path.exists():
            result['warnings'].append(f"❌ Cookie file not found: {cookie_file}")
            return result

        file_size = cookie_path.stat().st_size
        if file_size < 10:
            result['warnings'].append(f"⚠️ Cookie file too small ({file_size} bytes)")
            return result

        # Check 2: File freshness (modification time)
        mod_time = cookie_path.stat().st_mtime
        file_age = datetime.now() - datetime.fromtimestamp(mod_time)
        result['age_days'] = file_age.days

        if file_age.days > max_age_days:
            result['fresh'] = False
            result['warnings'].append(
                f"⚠️ Cookie file is {file_age.days} days old (older than {max_age_days} days)"
            )
            result['warnings'].append(f"   💡 Consider refreshing cookies for better success rate")

        # Check 3: Valid Netscape format and cookie expiration
        current_timestamp = int(time.time())

        with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        cookie_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
        result['total_cookies'] = len(cookie_lines)

        if result['total_cookies'] == 0:
            result['warnings'].append(f"⚠️ No cookies found in file (only comments/blank lines)")
            return result

        # Check cookie expiration dates
        expired_count = 0
        for line in cookie_lines:
            parts = line.strip().split('\t')
            if len(parts) >= 5:  # Valid Netscape format has 7 fields, but 5 minimum
                try:
                    expires = int(parts[4])  # Expiration timestamp
                    if expires > 0 and expires < current_timestamp:
                        expired_count += 1
                except (ValueError, IndexError):
                    continue

        result['expired_cookies'] = expired_count

        if expired_count > 0:
            expiry_pct = (expired_count / result['total_cookies']) * 100
            if expiry_pct > 50:
                result['warnings'].append(
                    f"⚠️ {expired_count}/{result['total_cookies']} cookies expired ({expiry_pct:.0f}%)"
                )
                result['warnings'].append(f"   💡 Cookie refresh recommended")

        # All checks passed
        result['valid'] = True

        # Add success message if fresh and minimal warnings
        if result['fresh'] and len(result['warnings']) == 0:
            logging.debug(f"✓ Cookie validation passed: {result['total_cookies']} cookies, {result['age_days']} days old")

    except Exception as e:
        result['warnings'].append(f"❌ Cookie validation error: {str(e)[:100]}")

    return result


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
    base_folder = desktop / "Links Grabber"
    
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


# ============ ENHANCED FEATURES (2026 Upgrade) ============

def _get_chrome120_headers() -> list:
    """
    ENHANCED: Return realistic Chrome 120 headers for better platform compatibility

    These headers make yt-dlp look more like a real browser, helping to avoid detection.
    Based on actual Chrome 120 on Windows 10.

    Returns:
        list: Command line arguments to add headers to yt-dlp
    """
    headers = []

    # Accept header (what content types browser accepts)
    headers.extend(['--add-header', 'Accept:text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'])

    # Accept-Language (browser language preference)
    headers.extend(['--add-header', 'Accept-Language:en-US,en;q=0.9'])

    # Accept-Encoding (supported compression methods)
    headers.extend(['--add-header', 'Accept-Encoding:gzip, deflate, br'])

    # Sec-Ch-Ua (Chrome client hints - brand and version)
    headers.extend(['--add-header', 'Sec-Ch-Ua:"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'])

    # Sec-Ch-Ua-Mobile (desktop browser, not mobile)
    headers.extend(['--add-header', 'Sec-Ch-Ua-Mobile:?0'])

    # Sec-Ch-Ua-Platform (operating system)
    headers.extend(['--add-header', 'Sec-Ch-Ua-Platform:"Windows"'])

    # Sec-Fetch-Dest (what type of resource is being fetched)
    headers.extend(['--add-header', 'Sec-Fetch-Dest:document'])

    # Sec-Fetch-Mode (how the request was initiated)
    headers.extend(['--add-header', 'Sec-Fetch-Mode:navigate'])

    # Sec-Fetch-Site (relationship between origin and target)
    headers.extend(['--add-header', 'Sec-Fetch-Site:none'])

    # Sec-Fetch-User (user-initiated navigation)
    headers.extend(['--add-header', 'Sec-Fetch-User:?1'])

    # Upgrade-Insecure-Requests (browser supports HTTPS upgrades)
    headers.extend(['--add-header', 'Upgrade-Insecure-Requests:1'])

    # DNT (Do Not Track header)
    headers.extend(['--add-header', 'DNT:1'])

    return headers


def _parse_proxy_format(proxy: str) -> str:
    """
    ENHANCED: Parse and convert proxy format to standard format with URL encoding

    Supports ALL 5 formats:
    1. ip:port                                    → http://ip:port
    2. user:pass@ip:port                          → http://user:pass@ip:port
    3. ip:port:user:pass (provider format)        → http://user:pass@ip:port
    4. socks5://user:pass@ip:port                 → socks5://user:pass@ip:port
    5. With URL encoding for special chars        → http://user:P%40ss@ip:port

    Special features:
    - Automatically detects and preserves SOCKS5 protocol
    - URL-encodes passwords with special characters (:@#%&= etc.)
    - Handles all common provider formats
    - Backward compatible with existing proxies

    Args:
        proxy: Proxy string in any supported format

    Returns:
        Standardized proxy URL with proper encoding
    """
    try:
        from urllib.parse import quote

        proxy = proxy.strip()

        # If already has protocol (http/https/socks), parse and encode credentials
        if proxy.startswith('http://') or proxy.startswith('https://') or proxy.startswith('socks'):
            # Extract protocol
            if proxy.startswith('socks5://'):
                protocol = 'socks5://'
                rest = proxy[10:]
            elif proxy.startswith('socks4://'):
                protocol = 'socks4://'
                rest = proxy[10:]
            elif proxy.startswith('https://'):
                protocol = 'https://'
                rest = proxy[8:]
            else:
                protocol = 'http://'
                rest = proxy[7:]

            # Check if has credentials
            if '@' in rest:
                creds, server = rest.split('@', 1)
                if ':' in creds:
                    user, password = creds.split(':', 1)
                    # URL encode password for special characters
                    password_encoded = quote(password, safe='')
                    return f"{protocol}{user}:{password_encoded}@{server}"

            return proxy  # Already formatted, return as-is

        # Check for @ symbol (standard format: user:pass@ip:port)
        if '@' in proxy:
            # Format: user:pass@ip:port
            creds, server = proxy.split('@', 1)
            if ':' in creds:
                user, password = creds.split(':', 1)
                # URL encode password for special characters
                password_encoded = quote(password, safe='')
                return f"http://{user}:{password_encoded}@{server}"
            else:
                return f"http://{proxy}"

        # Split by colon to check format
        parts = proxy.split(':')

        if len(parts) == 4:
            # Format: ip:port:user:pass (provider format)
            ip, port, user, password = parts
            # URL encode password for special characters
            password_encoded = quote(password, safe='')
            return f"http://{user}:{password_encoded}@{ip}:{port}"

        elif len(parts) == 2:
            # Format: ip:port (no authentication)
            return f"http://{proxy}"

        else:
            # Unknown format, try as-is
            logging.warning(f"⚠️ Unknown proxy format (parts={len(parts)}): {proxy[:30]}..., using as-is")
            return f"http://{proxy}"

    except Exception as e:
        logging.error(f"❌ Failed to parse proxy format: {e}")
        return f"http://{proxy}"


def _validate_proxy(proxy: str, timeout: int = 10) -> dict:
    """
    Enhanced proxy validation with detailed error reporting

    Validates proxy by testing connection to httpbin.org
    Supports all proxy formats via _parse_proxy_format()

    Args:
        proxy: Proxy string in any format
        timeout: Validation timeout in seconds

    Returns:
        dict with:
        - 'working': bool
        - 'response_time': float
        - 'ip': str (detected IP through proxy)
        - 'error': str (error message if failed)
    """
    result = {
        'working': False,
        'response_time': 999,
        'ip': 'Unknown',
        'error': ''
    }

    try:
        import requests
        from requests.packages.urllib3.exceptions import InsecureRequestWarning

        # Suppress SSL warnings for proxy testing
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        # Parse proxy format (handles all 3 formats)
        proxy_url = _parse_proxy_format(proxy)
        logging.debug(f"Parsed proxy: {proxy} → {proxy_url}")

        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }

        # Try HTTP first (faster, less SSL issues)
        try:
            start_time = time.time()
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxies,
                timeout=timeout,
                verify=False
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                result['working'] = True
                result['response_time'] = round(response_time, 2)
                try:
                    result['ip'] = response.json().get('origin', 'Working')
                except:
                    result['ip'] = 'Working'

                logging.info(f"Proxy validated: {result['ip']} ({result['response_time']}s)")
                return result

        except requests.exceptions.ProxyError as e:
            result['error'] = f"Proxy connection failed: {str(e)[:50]}"
        except requests.exceptions.Timeout:
            result['error'] = "Proxy timeout (too slow)"
        except requests.exceptions.ConnectionError as e:
            result['error'] = f"Connection error: {str(e)[:50]}"
        except Exception as http_error:
            # HTTP failed, try HTTPS as fallback
            try:
                start_time = time.time()
                response = requests.get(
                    'https://httpbin.org/ip',
                    proxies=proxies,
                    timeout=timeout,
                    verify=False
                )
                response_time = time.time() - start_time

                if response.status_code == 200:
                    result['working'] = True
                    result['response_time'] = round(response_time, 2)
                    try:
                        result['ip'] = response.json().get('origin', 'Working')
                    except:
                        result['ip'] = 'Working'

                    logging.info(f"Proxy validated (HTTPS): {result['ip']} ({result['response_time']}s)")
                    return result

            except requests.exceptions.ProxyError as e:
                result['error'] = f"Proxy auth failed: {str(e)[:50]}"
            except requests.exceptions.Timeout:
                result['error'] = "Proxy timeout (too slow)"
            except requests.exceptions.ConnectionError as e:
                result['error'] = f"Connection error: {str(e)[:50]}"
            except Exception as https_error:
                result['error'] = f"Both HTTP/HTTPS failed: {str(https_error)[:50]}"

    except ImportError:
        result['error'] = "requests library not available"
    except Exception as e:
        result['error'] = f"Validation error: {str(e)[:100]}"
        logging.error(f"Proxy validation error: {e}")

    return result


def _get_random_user_agent() -> str:
    """Get random user agent from config pool"""
    try:
        from .config import USER_AGENTS
        import random
        return random.choice(USER_AGENTS)
    except:
        # Fallback if config not available
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def _apply_rate_limit(platform_key: str, custom_delay: float = None):
    """
    ENHANCED: Apply intelligent rate limit delay based on platform

    Uses platform-specific delays to mimic human behavior and avoid detection.

    Args:
        platform_key: Platform name (youtube, instagram, etc.)
        custom_delay: Custom delay override (seconds)
    """
    try:
        if custom_delay is not None:
            time.sleep(custom_delay)
            return

        from .config import DELAY_CONFIG
        import random

        # ENHANCED: Use platform-specific delays if available
        platform_delays = DELAY_CONFIG.get('platform_delays', {})

        if platform_key in platform_delays:
            # Platform-specific delay range
            min_delay, max_delay = platform_delays[platform_key]
            logging.debug(f"Using platform-specific delay for {platform_key}: {min_delay}-{max_delay}s")
        else:
            # General delay range
            min_delay = DELAY_CONFIG['before_request_min']
            max_delay = DELAY_CONFIG['before_request_max']
            logging.debug(f"Using general delay for {platform_key}: {min_delay}-{max_delay}s")

        # Add random jitter (human-like behavior)
        delay = random.uniform(min_delay, max_delay)

        logging.debug(f"⏱️ Rate limit: waiting {delay:.2f}s for {platform_key}")
        time.sleep(delay)

    except Exception as e:
        # Fallback: 2-3 second delay
        import random
        logging.warning(f"Rate limit fallback due to error: {e}")
        time.sleep(random.uniform(2, 3))


def _get_ytdlp_binary_path() -> str:
    """
    Multi-location yt-dlp detection with fallback chain

    Priority Order:
    1. Bundled yt-dlp.exe (in EXE) - Most reliable for distribution
    2. System yt-dlp (in PATH) - If user has installed/updated
    3. User's custom locations - Common installation directories

    Returns:
        Path to yt-dlp binary or command
    """
    import sys

    try:
        # PRIORITY 1: Bundled yt-dlp.exe (in EXE distribution) - MOST RELIABLE
        if getattr(sys, 'frozen', False):
            # Running as bundled EXE
            base_path = sys._MEIPASS
            ytdlp_path = os.path.join(base_path, 'bin', 'yt-dlp.exe')

            if os.path.exists(ytdlp_path):
                logging.info(f"✓ Using bundled yt-dlp: {ytdlp_path}")
                return ytdlp_path

        # PRIORITY 2: System yt-dlp (in PATH) - USER MANAGED/UPDATED
        try:
            result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                timeout=5,
                text=True,
                errors='ignore'
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logging.info(f"✓ Using system yt-dlp (v{version})")
                return 'yt-dlp'
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # PRIORITY 3: User's custom locations (common installation directories)
        user_locations = [
            r"C:\yt-dlp\yt-dlp.exe",  # Recommended location
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'yt-dlp', 'yt-dlp.exe'),
            os.path.join(os.environ.get('APPDATA', ''), 'yt-dlp', 'yt-dlp.exe'),
            os.path.join(Path.home(), 'yt-dlp', 'yt-dlp.exe'),
            os.path.join(Path.home(), 'yt-dlp.exe'),
            r"C:\Program Files\yt-dlp\yt-dlp.exe",
        ]

        for location in user_locations:
            try:
                expanded = os.path.expandvars(location)
                if os.path.exists(expanded):
                    logging.info(f"✓ Using user's yt-dlp: {expanded}")
                    return expanded
            except:
                continue

        # Ultimate fallback - try system command anyway
        logging.warning("⚠ No yt-dlp found in known locations, trying system command")
        return 'yt-dlp'

    except Exception as e:
        logging.error(f"Error detecting yt-dlp: {e}")
        return 'yt-dlp'


def _execute_ytdlp_dual(url: str, options: dict, proxy: str = None, user_agent: str = None) -> typing.List[dict]:
    """
    DUAL YT-DLP APPROACH: Try Python API first, fallback to binary

    Args:
        url: URL to extract
        options: yt-dlp options dict
        proxy: Proxy string (optional)
        user_agent: User agent string (optional)

    Returns:
        List of extracted entries with url, title, date
    """
    entries = []

    # Add proxy and user agent to options
    if proxy:
        options['proxy'] = f"http://{proxy}" if not proxy.startswith('http') else proxy
    if user_agent:
        options['user_agent'] = user_agent

    # ===== APPROACH 1: Python API (Faster, Better Error Handling) =====
    try:
        import yt_dlp

        logging.debug("Trying yt-dlp Python API...")

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)

            if info:
                # Handle playlist
                if 'entries' in info:
                    for entry in info['entries']:
                        if entry:
                            entries.append({
                                'url': entry.get('webpage_url') or entry.get('url', ''),
                                'title': entry.get('title', 'Untitled')[:100],
                                'date': entry.get('upload_date', '00000000')
                            })
                # Handle single video
                else:
                    entries.append({
                        'url': info.get('webpage_url') or info.get('url', ''),
                        'title': info.get('title', 'Untitled')[:100],
                        'date': info.get('upload_date', '00000000')
                    })

                if entries:
                    logging.debug(f"✓ Python API success: {len(entries)} links")
                    return entries

    except Exception as e:
        logging.warning(f"❌ yt-dlp Python API failed:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")
        logging.warning(f"   Proxy: {options.get('proxy', 'None')}")
        logging.warning(f"   User-Agent: {options.get('user_agent', 'Default')[:50]}")

    # ===== APPROACH 2: Binary Subprocess (Fallback) =====
    try:
        logging.debug("Falling back to yt-dlp binary...")

        ytdlp_path = _get_ytdlp_binary_path()

        cmd = [ytdlp_path, '--dump-json', '--flat-playlist', '--ignore-errors', '--no-warnings']

        # ENHANCED: Add realistic Chrome 120 headers to avoid detection
        cmd.extend(_get_chrome120_headers())

        # Add proxy
        if proxy:
            cmd.extend(['--proxy', options.get('proxy', proxy)])

        # Add user agent
        if user_agent:
            cmd.extend(['--user-agent', user_agent])

        # Add cookies
        if 'cookiesfrombrowser' in options:
            cmd.extend(['--cookies-from-browser', options['cookiesfrombrowser']])
        elif 'cookiefile' in options:
            cmd.extend(['--cookies', options['cookiefile']])

        # Add max videos
        if 'playlistend' in options:
            cmd.extend(['--playlist-end', str(options['playlistend'])])

        cmd.append(url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=options.get('socket_timeout', 30),
            encoding='utf-8',
            errors='replace'
        )

        if result.stdout:
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
                except:
                    continue

            if entries:
                logging.debug(f"✓ Binary success: {len(entries)} links")
                return entries
            else:
                # No entries found - log detailed error info
                logging.warning(f"❌ yt-dlp binary returned 0 results:")
                logging.warning(f"   Command: {' '.join(cmd)}")
                logging.warning(f"   Exit code: {result.returncode}")
                if result.stdout:
                    logging.warning(f"   Stdout: {result.stdout[:500]}")
                if result.stderr:
                    logging.warning(f"   Stderr: {result.stderr[:500]}")

    except Exception as e:
        logging.warning(f"❌ yt-dlp binary exception:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")

    return entries


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


def _method_ytdlp_enhanced(
    url: str,
    platform_key: str,
    cookie_file: str = None,
    max_videos: int = 0,
    cookie_browser: str = None,
    proxy: str = None,
    user_agent: str = None,
    apply_delay: bool = True
) -> typing.List[dict]:
    """
    ENHANCED YT-DLP METHOD: Uses dual approach (Python API + Binary fallback)
    with proxy, user agent rotation, and rate limiting
    """
    try:
        # Apply rate limiting before request
        if apply_delay:
            _apply_rate_limit(platform_key)

        # Get random user agent if not provided
        if not user_agent:
            user_agent = _get_random_user_agent()

        # Build yt-dlp options
        from .config import YTDLP_CONFIG

        options = {
            'quiet': YTDLP_CONFIG['quiet'],
            'no_warnings': YTDLP_CONFIG['no_warnings'],
            'ignore_errors': True,
            'extract_flat': 'in_playlist',
            'socket_timeout': YTDLP_CONFIG['socket_timeout'],
        }

        # Add cookies
        if cookie_browser:
            options['cookiesfrombrowser'] = cookie_browser
        elif cookie_file:
            options['cookiefile'] = cookie_file

        # Add playlist limit
        if max_videos > 0:
            options['playlistend'] = max_videos

        # Platform-specific optimizations
        if platform_key == 'instagram':
            options['extractor_args'] = {'instagram': {'feed_count': 100}}
        elif platform_key == 'youtube':
            options['extractor_args'] = {'youtube': {'player_client': 'android'}}

        # Execute with dual approach
        entries = _execute_ytdlp_dual(url, options, proxy, user_agent)

        if entries:
            # Sort by date (newest first)
            entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)
            logging.debug(f"Enhanced yt-dlp: {len(entries)} links extracted")
            return entries
        else:
            # No results from dual approach
            logging.warning(f"❌ Method 0 (Enhanced) returned 0 results:")
            logging.warning(f"   URL: {url}")
            logging.warning(f"   Both Python API and binary fallback failed")
            return []

    except Exception as e:
        logging.warning(f"❌ Method 0 (Enhanced) exception:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")

    return []


def _method_ytdlp_dump_json(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None, proxy: str = None, user_agent: str = None) -> typing.List[dict]:
    """METHOD 1: yt-dlp --dump-json (WITH DATES) - PRIMARY METHOD + Proxy + Chrome Headers"""
    try:
        cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--ignore-errors', '--no-warnings']

        # ENHANCED: Add realistic Chrome 120 headers to avoid detection
        cmd.extend(_get_chrome120_headers())

        # Cookie handling: browser OR file (2025 approach)
        if cookie_browser:
            cmd.extend(['--cookies-from-browser', cookie_browser])
        elif cookie_file:
            cmd.extend(['--cookies', cookie_file])

        # Add proxy if available (CRITICAL for IP blocks)
        if proxy:
            proxy_url = proxy if proxy.startswith('http') else f"http://{proxy}"
            cmd.extend(['--proxy', proxy_url])
            logging.debug(f"Method 1: Using proxy {proxy_url.split('@')[-1][:20]}...")

        # Add user agent if provided
        if user_agent:
            cmd.extend(['--user-agent', user_agent])
            logging.debug(f"Method 1: Using UA {user_agent[:40]}...")

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
        else:
            # No results - log detailed error info
            logging.warning(f"❌ Method 1 (--dump-json) returned 0 results:")
            logging.warning(f"   Command: {' '.join(cmd)}")
            logging.warning(f"   Exit code: {result.returncode}")
            if result.stdout:
                logging.warning(f"   Stdout: {result.stdout[:500]}")
            if result.stderr:
                logging.warning(f"   Stderr: {result.stderr[:500]}")

    except Exception as e:
        logging.warning(f"❌ Method 1 (--dump-json) exception:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")

    return []


def _method_ytdlp_get_url(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None, proxy: str = None) -> typing.List[dict]:
    """METHOD 2: yt-dlp --get-url (FAST, NO DATES) - SIMPLIFIED + Proxy + Chrome Headers"""
    try:
        # SIMPLE COMMAND like the working batch script: yt-dlp URL --flat-playlist --get-url
        cmd = ['yt-dlp', '--flat-playlist', '--get-url', '--ignore-errors']

        # ENHANCED: Add realistic Chrome 120 headers to avoid detection
        cmd.extend(_get_chrome120_headers())

        # Cookie handling: browser OR file
        if cookie_browser:
            cmd.extend(['--cookies-from-browser', cookie_browser])
        elif cookie_file:
            cmd.extend(['--cookies', cookie_file])

        # Add proxy if available (CRITICAL for IP blocks)
        if proxy:
            proxy_url = proxy if proxy.startswith('http') else f"http://{proxy}"
            cmd.extend(['--proxy', proxy_url])
            logging.debug(f"Method 2: Using proxy {proxy_url.split('@')[-1][:20]}...")

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
                logging.warning(f"❌ Method 2 (--get-url) returned 0 results:")
                logging.warning(f"   Command: {' '.join(cmd)}")
                logging.warning(f"   Exit code: {result.returncode}")
                logging.warning(f"   Raw output: {result.stdout[:500]}")
                if result.stderr:
                    logging.warning(f"   Stderr: {result.stderr[:500]}")
        else:
            # result.stdout is empty
            logging.warning(f"❌ Method 2 (--get-url) returned empty output:")
            logging.warning(f"   Command: {' '.join(cmd)}")
            logging.warning(f"   Exit code: {result.returncode}")
            if result.stderr:
                logging.warning(f"   Stderr: {result.stderr[:500]}")

    except Exception as e:
        logging.warning(f"❌ Method 2 (--get-url) exception:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")

    return []


def _method_ytdlp_with_retry(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None, proxy: str = None) -> typing.List[dict]:
    """METHOD 3: yt-dlp with retries (PERSISTENT) + Proxy + Chrome Headers"""
    try:
        cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--ignore-errors',
               '--retries', '10', '--fragment-retries', '10', '--extractor-retries', '5',
               '--socket-timeout', '30']

        # ENHANCED: Add realistic Chrome 120 headers to avoid detection
        cmd.extend(_get_chrome120_headers())

        # Cookie handling: browser OR file
        if cookie_browser:
            cmd.extend(['--cookies-from-browser', cookie_browser])
        elif cookie_file:
            cmd.extend(['--cookies', cookie_file])

        # Add proxy if available
        if proxy:
            proxy_url = proxy if proxy.startswith('http') else f"http://{proxy}"
            cmd.extend(['--proxy', proxy_url])
            logging.debug(f"Method 3: Using proxy {proxy_url.split('@')[-1][:20]}...")

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

            if entries:
                entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)
                return entries
            else:
                # No results - log detailed error info
                logging.warning(f"❌ Method 3 (with retry) returned 0 results:")
                logging.warning(f"   Command: {' '.join(cmd)}")
                logging.warning(f"   Exit code: {result.returncode}")
                if result.stdout:
                    logging.warning(f"   Stdout: {result.stdout[:500]}")
                if result.stderr:
                    logging.warning(f"   Stderr: {result.stderr[:500]}")
        else:
            # result.stdout is empty
            logging.warning(f"❌ Method 3 (with retry) returned empty output:")
            logging.warning(f"   Command: {' '.join(cmd)}")
            logging.warning(f"   Exit code: {result.returncode}")
            if result.stderr:
                logging.warning(f"   Stderr: {result.stderr[:500]}")

    except Exception as e:
        logging.warning(f"❌ Method 3 (with retry) exception:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")

    return []


def _method_ytdlp_user_agent(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None, proxy: str = None) -> typing.List[dict]:
    """METHOD 4: yt-dlp with different user agent (ANTI-BLOCK) + Proxy + Chrome Headers"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile"
    ]

    for ua in user_agents:
        try:
            cmd = ['yt-dlp', '--dump-json', '--flat-playlist', '--ignore-errors',
                   '--user-agent', ua]

            # ENHANCED: Add realistic Chrome 120 headers to avoid detection
            cmd.extend(_get_chrome120_headers())

            # Cookie handling: browser OR file
            if cookie_browser:
                cmd.extend(['--cookies-from-browser', cookie_browser])
            elif cookie_file:
                cmd.extend(['--cookies', cookie_file])

            # Add proxy if available
            if proxy:
                proxy_url = proxy if proxy.startswith('http') else f"http://{proxy}"
                cmd.extend(['--proxy', proxy_url])
                logging.debug(f"Method 4: Using proxy {proxy_url.split('@')[-1][:20]}... with UA: {ua[:40]}")

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
                else:
                    # No results with this UA - log and try next
                    logging.debug(f"Method 4: No results with UA: {ua[:40]}")
            else:
                # Empty stdout - log and try next
                logging.debug(f"Method 4: Empty output with UA: {ua[:40]}")
                if result.stderr:
                    logging.debug(f"   Stderr: {result.stderr[:300]}")

        except Exception as e:
            logging.debug(f"Method 4: Exception with UA {ua[:40]}: {str(e)[:200]}")
            continue

    # All user agents failed
    logging.warning(f"❌ Method 4 (user agent rotation) failed:")
    logging.warning(f"   Tried {len(user_agents)} different user agents")
    logging.warning(f"   URL: {url}")
    return []


def _method_instaloader(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0) -> typing.List[dict]:
    """METHOD 5: Instaloader (INSTAGRAM SPECIALIST) - No artificial limits"""
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
                    logging.info(f"✅ Loaded {len(cookies_dict)} cookies for Instagram")
            except Exception as e:
                logging.debug(f"Cookie loading failed: {e}")

        profile = instaloader.Profile.from_username(loader.context, username)
        logging.info(f"📊 Instagram profile: @{username} ({profile.mediacount} posts)")

        entries = []

        # Respect max_videos from GUI (0 = unlimited)
        for idx, post in enumerate(profile.get_posts(), 1):
            entries.append({
                'url': f"https://www.instagram.com/p/{post.shortcode}/",
                'title': (post.caption or 'Instagram Post')[:100],
                'date': post.date_utc.strftime('%Y%m%d') if post.date_utc else '00000000'
            })

            # Progress logging every 50 posts
            if idx % 50 == 0:
                logging.info(f"📥 Extracted {idx} Instagram posts...")

            # Only break if limit is specified (0 means unlimited)
            if max_videos > 0 and len(entries) >= max_videos:
                logging.info(f"✅ Reached Instagram limit of {max_videos} posts")
                break

        # Sort by date (newest first)
        entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)
        logging.info(f"✅ Successfully extracted {len(entries)} Instagram posts")
        return entries

    except ImportError:
        logging.error("❌ Instaloader not installed. Install: pip install instaloader")
    except Exception as e:
        logging.error(f"❌ Method 5 (instaloader) failed: {e}")
        import traceback
        logging.debug(traceback.format_exc())

    return []


def _method_gallery_dl(url: str, platform_key: str, cookie_file: str = None, proxy: str = None) -> typing.List[dict]:
    """METHOD 6: gallery-dl (INSTAGRAM/TIKTOK) + Proxy Support"""
    if platform_key not in ['instagram', 'tiktok']:
        return []

    try:
        cmd = ['gallery-dl', '--dump-json', '--quiet']

        if cookie_file:
            cmd.extend(['--cookies', cookie_file])

        # Add proxy if available
        if proxy:
            proxy_url = proxy if proxy.startswith('http') else f"http://{proxy}"
            cmd.extend(['--proxy', proxy_url])
            logging.debug(f"Method 6 (gallery-dl): Using proxy {proxy_url.split('@')[-1][:20]}...")

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


def _method_playwright(url: str, platform_key: str, cookie_file: str = None, proxy: str = None, max_videos: int = 0) -> typing.List[dict]:
    """
    METHOD 7: Playwright Browser Automation - ENHANCED WITH STEALTH

    Uses real Chromium browser to bypass advanced bot detection.
    Includes stealth mode, proxy support, and human-like behavior.
    """
    if platform_key not in ['tiktok', 'instagram', 'youtube']:
        return []

    try:
        from playwright.sync_api import sync_playwright
        import random

        logging.debug(f"🎭 Starting Playwright method for {platform_key}")

        with sync_playwright() as p:
            # ENHANCED: Launch options with stealth
            launch_options = {
                'headless': True,
                'args': [
                    '--disable-blink-features=AutomationControlled',  # Hide automation
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            }

            # ENHANCED: Use bundled Chromium if available
            # Check multiple possible locations (Windows: .exe, Linux/Mac: no extension)
            base_path = Path(__file__).parent.parent.parent / 'bin'
            chromium_paths = [
                base_path / 'chromium' / 'chromium.exe',  # Windows (in chromium folder) ✅ Your setup
                base_path / 'chromium.exe',                # Windows (direct)
                base_path / 'chromium' / 'chrome.exe',     # Windows (alternative name)
                base_path / 'chromium',                    # Linux/Mac (no extension)
            ]

            chromium_path = None
            for path in chromium_paths:
                if path.exists() and path.is_file():
                    chromium_path = path
                    logging.debug(f"✓ Found bundled Chromium: {chromium_path}")
                    break

            if chromium_path:
                launch_options['executable_path'] = str(chromium_path)
                logging.debug(f"✅ Using bundled Chromium from bin/ folder")
            else:
                logging.debug(f"⚠️ Bundled Chromium not found, using system Chromium (auto-download)")

            # ENHANCED: Add proxy if available
            if proxy:
                parsed_proxy = _parse_proxy_format(proxy)
                if parsed_proxy.startswith('http'):
                    # Extract proxy server (remove credentials for Playwright)
                    if '@' in parsed_proxy:
                        # Format: http://user:pass@ip:port
                        proxy_parts = parsed_proxy.split('@')
                        proxy_server = f"http://{proxy_parts[1]}"
                        logging.debug(f"🌐 Playwright using proxy: {proxy_parts[1][:25]}...")
                    else:
                        proxy_server = parsed_proxy
                        logging.debug(f"🌐 Playwright using proxy: {proxy_server[:25]}...")

                    launch_options['proxy'] = {'server': proxy_server}

            browser = p.chromium.launch(**launch_options)

            # ENHANCED: Context with realistic Chrome fingerprint
            context_options = {
                'user_agent': _get_random_user_agent(),
                'viewport': {'width': 1920, 'height': 1080},
                'locale': 'en-US',
                'timezone_id': 'America/New_York',
                'permissions': ['geolocation'],
                'color_scheme': 'light',
                'extra_http_headers': {
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                }
            }

            context = browser.new_context(**context_options)

            # ENHANCED: Add stealth scripts to hide automation
            context.add_init_script("""
                // Overwrite the `navigator.webdriver` property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false
                });

                // Overwrite the `navigator.plugins` property
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Overwrite the `navigator.languages` property
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });

                // Chrome runtime
                window.chrome = {
                    runtime: {}
                };

                // Permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            # Load cookies if available
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
                        logging.debug(f"✓ Loaded {len(playwright_cookies)} cookies")
                    except Exception as e:
                        logging.debug(f"Cookie loading failed: {e}")

            page = context.new_page()

            # ENHANCED: Human-like page loading
            base_url_map = {
                'tiktok': 'https://www.tiktok.com/',
                'instagram': 'https://www.instagram.com/',
                'youtube': 'https://www.youtube.com/'
            }
            seed_url = base_url_map.get(platform_key, url)

            # Visit homepage first (more human-like)
            try:
                page.goto(seed_url, timeout=30000, wait_until='domcontentloaded')
                time.sleep(random.uniform(1.0, 2.5))  # Random pause
            except Exception:
                pass

            # Now visit target URL
            page.goto(url, timeout=30000, wait_until='domcontentloaded')
            time.sleep(random.uniform(2.0, 4.0))  # Longer initial pause

            entries = []

            # ENHANCED: Platform-specific extraction with human-like scrolling
            if platform_key == 'tiktok':
                previous_count = 0
                no_change_count = 0
                scroll_count = 0
                max_scrolls = 50 if max_videos == 0 else min(50, max_videos // 5 + 5)

                while no_change_count < 3 and scroll_count < max_scrolls:
                    video_links = page.query_selector_all('a[href*="/video/"]')
                    current_count = len(video_links)

                    if current_count == previous_count:
                        no_change_count += 1
                    else:
                        no_change_count = 0

                    # ENHANCED: Human-like scrolling (variable distance)
                    scroll_distance = random.randint(800, 1200)
                    page.evaluate(f"window.scrollBy(0, {scroll_distance})")

                    # ENHANCED: Random pauses (mimics reading)
                    pause = random.uniform(1.5, 3.5)
                    time.sleep(pause)

                    previous_count = current_count
                    scroll_count += 1

                    if max_videos > 0 and current_count >= max_videos:
                        break

                for link in video_links:
                    if max_videos > 0 and len(entries) >= max_videos:
                        break
                    if href := link.get_attribute('href'):
                        full_url = f"https://www.tiktok.com{href}" if not href.startswith('http') else href
                        entries.append({'url': full_url, 'title': 'TikTok Video', 'date': '00000000'})

            elif platform_key == 'instagram':
                previous_count = 0
                no_change_count = 0
                scroll_count = 0
                max_scrolls = 50 if max_videos == 0 else min(50, max_videos // 5 + 5)

                while no_change_count < 3 and scroll_count < max_scrolls:
                    post_links = page.query_selector_all('a[href*="/p/"], a[href*="/reel/"], a[href*="/tv/"]')
                    current_count = len(post_links)

                    if current_count == previous_count:
                        no_change_count += 1
                    else:
                        no_change_count = 0

                    # ENHANCED: Human-like scrolling
                    scroll_distance = random.randint(600, 1000)
                    page.evaluate(f"window.scrollBy(0, {scroll_distance})")

                    # ENHANCED: Random pauses
                    pause = random.uniform(2.0, 4.0)
                    time.sleep(pause)

                    previous_count = current_count
                    scroll_count += 1

                    if max_videos > 0 and current_count >= max_videos:
                        break

                for link in post_links:
                    if max_videos > 0 and len(entries) >= max_videos:
                        break
                    if href := link.get_attribute('href'):
                        full_url = f"https://www.instagram.com{href}" if not href.startswith('http') else href
                        entries.append({'url': full_url, 'title': 'Instagram Post', 'date': '00000000'})

            elif platform_key == 'youtube':
                # FIXED: YouTube support with SIMPLE selector (matches Selenium)
                previous_count = 0
                no_change_count = 0
                scroll_count = 0
                max_scrolls = 30 if max_videos == 0 else min(30, max_videos // 10 + 3)

                while no_change_count < 3 and scroll_count < max_scrolls:
                    # FIXED: Use same simple selector as Selenium (PROVEN TO WORK!)
                    # Finds: /watch?v= (regular videos) AND /shorts/ (shorts)
                    video_links = page.query_selector_all('a[href*="/watch?v="], a[href*="/shorts/"]')
                    current_count = len(video_links)

                    if current_count == previous_count:
                        no_change_count += 1
                    else:
                        no_change_count = 0

                    # Human-like scrolling
                    scroll_distance = random.randint(1000, 1500)
                    page.evaluate(f"window.scrollBy(0, {scroll_distance})")
                    pause = random.uniform(1.0, 2.5)
                    time.sleep(pause)

                    previous_count = current_count
                    scroll_count += 1

                    if max_videos > 0 and current_count >= max_videos:
                        break

                for link in video_links:
                    if max_videos > 0 and len(entries) >= max_videos:
                        break
                    if href := link.get_attribute('href'):
                        if '/watch?v=' in href or '/shorts/' in href:
                            full_url = f"https://www.youtube.com{href}" if not href.startswith('http') else href
                            # Clean URL (remove tracking & playlist params)
                            full_url = full_url.split('&')[0].split('?list=')[0]
                            title = link.get_attribute('title') or link.get_attribute('aria-label') or 'YouTube Video'
                            entries.append({'url': full_url, 'title': title[:100], 'date': '00000000'})

            context.close()
            browser.close()

            if entries:
                logging.debug(f"✓ Playwright extracted {len(entries)} links")
            else:
                logging.debug(f"⚠️ Playwright found 0 links")

            return entries

    except ImportError:
        logging.debug("❌ Playwright not installed (pip install playwright)")
    except Exception as e:
        logging.debug(f"❌ Method 7 (playwright) failed: {str(e)[:100]}")

    return []


def _method_selenium(
    url: str,
    platform_key: str,
    max_videos: int = 0,
    cookie_file: str = None,
    proxy: str = None,
    progress_callback=None
) -> typing.List[dict]:
    """
    METHOD 8: Selenium Headless (ENHANCED with Proxy + Cookies + Stealth)

    The MOST RELIABLE method - uses real browser automation with:
    - Headless Chrome for stealth
    - Proxy support (HTTP/SOCKS with authentication)
    - Cookie injection for authenticated access
    - Anti-detection measures
    - Human-like scrolling behavior
    """
    driver = None
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options

        options = Options()

        # HEADLESS MODE: Run without visible window
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

        # STEALTH FEATURES: Avoid detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # REALISTIC BROWSER FINGERPRINT
        user_agent = _get_random_user_agent()
        options.add_argument(f'--user-agent={user_agent}')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--lang=en-US,en;q=0.9')

        # PROXY SUPPORT: Critical for IP blocking avoidance
        if proxy:
            proxy_url = proxy if proxy.startswith('http') else f"http://{proxy}"
            options.add_argument(f'--proxy-server={proxy_url}')
            if progress_callback:
                progress_callback(f"🌐 Selenium: Using proxy {proxy_url.split('@')[-1][:30]}...")
            logging.info(f"Selenium: Proxy configured: {proxy_url.split('@')[-1][:30]}")

        driver = webdriver.Chrome(options=options)

        # Override navigator.webdriver property (anti-detection)
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
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

        # Navigate to target URL
        if cookies_loaded:
            if progress_callback:
                progress_callback(f"🍪 Selenium: Cookies injected, loading target page...")
            driver.get(url)
        else:
            if progress_callback:
                progress_callback(f"🌐 Selenium: Loading page (no cookies)...")
            driver.get(url)

        # Wait for page to load
        time.sleep(5)

        # Platform-specific selectors
        selector_map = {
            'tiktok': 'a[href*="/video/"]',
            'instagram': 'a[href*="/p/"], a[href*="/reel/"]',
            'youtube': 'a[href*="/watch?v="], a[href*="/shorts/"]'  # FIXED: Added Shorts support
        }
        selector = selector_map.get(platform_key, 'a')

        seen_urls: typing.Set[str] = set()
        scroll_attempts = 0
        stagnant_rounds = 0

        if progress_callback:
            progress_callback(f"📜 Selenium: Scrolling and extracting links...")

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
                if progress_callback:
                    progress_callback(f"✓ Selenium: Reached limit of {max_videos} videos")
                break

            # Check if we found new links this round
            new_links_found = len(seen_urls) - before_count
            if new_links_found == 0:
                stagnant_rounds += 1
                if progress_callback and stagnant_rounds == 1:
                    progress_callback(f"⏳ Selenium: No new links, continuing... ({len(seen_urls)} total)")
            else:
                stagnant_rounds = 0
                if progress_callback and scroll_attempts % 5 == 0:
                    progress_callback(f"📊 Selenium: Found {len(seen_urls)} links so far...")

            # Human-like scrolling with random variation
            scroll_amount = random.randint(1200, 1800)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount})")

            # Random delay to mimic human behavior
            delay = random.uniform(1.5, 2.5)
            time.sleep(delay)
            scroll_attempts += 1

        if progress_callback:
            progress_callback(f"✅ Selenium: Extraction complete - {len(seen_urls)} links found")

        entries = []
        limit = max_videos or len(seen_urls)
        for href in list(seen_urls)[:limit]:
            entries.append({'url': href, 'title': '', 'date': '00000000'})

        logging.info(f"Selenium method: Successfully extracted {len(entries)} links")
        return entries

    except ImportError:
        logging.warning("❌ Selenium not installed (pip install selenium)")
        if progress_callback:
            progress_callback("❌ Selenium not available - install with: pip install selenium")
    except Exception as e:
        logging.warning(f"❌ Selenium method failed:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")
        logging.warning(f"   Platform: {platform_key}")
        if proxy:
            logging.warning(f"   Proxy: {proxy.split('@')[-1][:30]}")
        if progress_callback:
            progress_callback(f"❌ Selenium error: {str(e)[:100]}")
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

            # ENHANCED: Validate cookie freshness and quality
            validation = _validate_cookie_file(cookie_file, max_age_days=14)
            if validation['warnings']:
                for warning in validation['warnings']:
                    progress_callback(f"   {warning}")
            else:
                # Show cookie stats if valid and fresh
                progress_callback(f"   ✓ {validation['total_cookies']} cookies, {validation['age_days']} days old")

        # If we've materialized a cookie file, stop passing cookie_browser to yt-dlp.
        # yt-dlp's --cookies-from-browser mode ignores manual files and was causing 0 results
        # when users selected "Use Browser" but only had exported Netscape cookies.
        if cookie_file:
            cookie_browser = None

        entries: typing.List[dict] = []
        seen_normalized: typing.Set[str] = set()

        # Extract proxy settings from options (support for 1-2 proxies)
        proxy_list = options.get('proxies', []) or []
        active_proxy = proxy_list[0] if proxy_list else None  # Use first proxy if available
        use_enhancements = options.get('use_enhancements', True)  # Enable enhancements by default

        # FIXED: Auto-append /videos or /shorts to YouTube URLs if needed
        original_url = url
        if platform_key == 'youtube' and '@' in url:
            # Check if URL already has a tab suffix
            if not any(suffix in url for suffix in ['/videos', '/shorts', '/streams', '/playlists', '/community', '/channels', '/about']):
                # No tab specified - try /videos first (most common)
                url = f"{url.rstrip('/')}/videos"
                if progress_callback:
                    progress_callback(f"📝 YouTube URL normalized:")
                    progress_callback(f"   From: {original_url}")
                    progress_callback(f"   To: {url}")
                    progress_callback(f"   💡 Tip: Use /@username/videos or /@username/shorts for direct access")

        # Check yt-dlp version and log it
        ytdlp_version = "Unknown"
        ytdlp_location = "Unknown"
        try:
            # Try to get version from Python module
            import yt_dlp
            ytdlp_version = yt_dlp.version.__version__
            ytdlp_location = "Python module"
        except:
            # Try to get version from binary
            try:
                ytdlp_path = _get_ytdlp_binary_path()
                result = subprocess.run(
                    [ytdlp_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    encoding='utf-8',
                    errors='replace'
                )
                if result.stdout:
                    ytdlp_version = result.stdout.strip().split()[0]
                    ytdlp_location = ytdlp_path if ytdlp_path != 'yt-dlp' else "System PATH"
            except:
                pass

        # Show configuration summary
        if progress_callback:
            progress_callback(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            progress_callback(f"📊 Extraction Configuration:")
            progress_callback(f"   • Creator: @{creator}")
            progress_callback(f"   • Platform: {platform_key.title()}")
            progress_callback(f"   • yt-dlp: v{ytdlp_version} ({ytdlp_location})")
            if active_proxy:
                progress_callback(f"   • Proxy: {active_proxy} ✓")
            if cookie_file:
                progress_callback(f"   • Cookies: Loaded ✓")
            if max_videos > 0:
                progress_callback(f"   • Limit: {max_videos} videos")
            else:
                progress_callback(f"   • Limit: All videos (unlimited)")
            if use_enhancements:
                progress_callback(f"   • Enhancements: Enabled (Dual yt-dlp + UA Rotation)")
            progress_callback(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Define all available methods (pass cookie_browser to yt-dlp methods)
        # PRIORITY ORDER: Enhanced method first, then fallback methods
        all_methods = [
            ("Method 0: Enhanced yt-dlp (Dual API + Proxy + UA Rotation)",
             lambda: _method_ytdlp_enhanced(url, platform_key, cookie_file, max_videos, cookie_browser, active_proxy),
             use_enhancements),  # Only use if enhancements enabled

            ("Method 2: yt-dlp --get-url (SIMPLE - Like Batch Script)",
             lambda: _method_ytdlp_get_url(url, platform_key, cookie_file, max_videos, cookie_browser, active_proxy),
             True),

            ("Method 1: yt-dlp --dump-json (with dates)",
             lambda: _method_ytdlp_dump_json(url, platform_key, cookie_file, max_videos, cookie_browser, active_proxy),
             True),

            ("Method 3: yt-dlp with retries",
             lambda: _method_ytdlp_with_retry(url, platform_key, cookie_file, max_videos, cookie_browser, active_proxy),
             True),

            ("Method 4: yt-dlp with user agent",
             lambda: _method_ytdlp_user_agent(url, platform_key, cookie_file, max_videos, cookie_browser, active_proxy),
             True),

            ("Method 6: gallery-dl",
             lambda: _method_gallery_dl(url, platform_key, cookie_file, active_proxy),
             platform_key in ['instagram', 'tiktok']),

            ("Method 5: Instaloader",
             lambda: _method_instaloader(url, platform_key, cookie_file, max_videos),
             platform_key == 'instagram'),

            ("Method 7: Playwright (ENHANCED: Stealth + Proxy + Human Behavior)",
             lambda: _method_playwright(url, platform_key, cookie_file, active_proxy, max_videos),
             platform_key in ['tiktok', 'instagram', 'youtube']),

            ("Method 8: Selenium Headless (ENHANCED: Proxy + Cookies + Stealth)",
             lambda: _method_selenium(url, platform_key, max_videos, cookie_file, active_proxy, progress_callback),
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

                    # If this was the learned "best" method and it failed, inform user we'll try others
                    if method_name == best_method_name and best_method_name:
                        progress_callback(f"   🔄 Best method didn't work, continuing with other methods...")

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
                progress_callback(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                progress_callback(f"✅ Extraction Complete!")
                progress_callback(f"   • Total Links: {len(entries)}")
                if successful_method:
                    progress_callback(f"   • Method Used: {successful_method}")
                if active_proxy:
                    progress_callback(f"   • Proxy Used: {active_proxy}")
                progress_callback(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        else:
            if progress_callback:
                progress_callback(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                progress_callback(f"❌ No links found after trying all methods")
                progress_callback(f"💡 Suggestions:")
                progress_callback(f"   • Try updating cookies")
                progress_callback(f"   • Use a different proxy")
                progress_callback(f"   • Check if the account is private")
                progress_callback(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

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

        # Use root cookies folder - persistent path (works in dev and EXE mode)
        from modules.config.paths import get_cookies_dir
        self.cookies_dir = get_cookies_dir()

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

        # Use root cookies folder - persistent path (works in dev and EXE mode)
        from modules.config.paths import get_cookies_dir
        self.cookies_dir = get_cookies_dir()

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
        base_folder = desktop / "Links Grabber"
        
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
        base_folder = desktop / "Links Grabber"
        self.save_triggered.emit(str(base_folder), self.found_links)

    def cancel(self):
        self.is_cancelled = True
