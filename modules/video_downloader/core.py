"""Core implementation for the smart video downloader."""

import os
import subprocess
import re
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yt_dlp
from PyQt5.QtCore import QThread, pyqtSignal

from .url_utils import (
    coerce_bool,
    extract_urls,
    normalize_url,
    quality_to_format,
)
from .history_manager import HistoryManager
from .instagram_helper import (
    InstagramCookieValidator,
    get_instagram_cookie_instructions,
    test_instagram_cookies,
)

# ===================== HELPERS ====================

def _detect_platform(url: str) -> str:
    url = url.lower()
    if 'tiktok.com' in url: return 'tiktok'
    if 'youtube.com' in url or 'youtu.be' in url: return 'youtube'
    if 'instagram.com' in url: return 'instagram'
    if 'facebook.com' in url or 'fb.com' in url: return 'facebook'
    if 'twitter.com' in url or 'x.com' in url: return 'twitter'
    return 'other'

def _get_random_user_agent() -> str:
    """Get random user agent to avoid detection"""
    user_agents = [
        # Real mobile browsers
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36',
        # TikTok app user agents (more realistic)
        'com.zhiliaoapp.musically/2023405020 (Linux; U; Android 13; en_US; Pixel 7; Build/TP1A.220624.014; Cronet/TTNetVersion:7d6d3f56 2023-03-22 QuicVersion:47946a6c 2023-01-18)',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    return random.choice(user_agents)

def _is_ip_block_error(error_text: str) -> bool:
    """Detect if error is due to IP blocking"""
    if not error_text:
        return False

    # Remove ANSI color codes (e.g., [0;31m, [0m)
    import re
    clean_text = re.sub(r'\x1b\[[0-9;]*m', '', error_text)
    clean_text = clean_text.lower()

    ip_block_indicators = [
        'ip address is blocked',
        'ip blocked',
        'access denied',
        '403 forbidden',
        'not available in your country',
        'video is not available',
        'this video isn\'t available',
        'region',
    ]

    return any(indicator in clean_text for indicator in ip_block_indicators)

def _parse_proxy_format(proxy: str) -> str:
    """
    Parse and convert proxy format to standard HTTP format.

    Supports 3 formats:
    1. ip:port                          → http://ip:port
    2. user:pass@ip:port                → http://user:pass@ip:port
    3. ip:port:user:pass (provider)     → http://user:pass@ip:port

    Args:
        proxy: Raw proxy string in any supported format

    Returns:
        str: Proxy URL in standard HTTP format
    """
    if not proxy:
        return ''

    proxy = proxy.strip()

    # Already formatted with protocol
    if proxy.startswith('http://') or proxy.startswith('https://') or proxy.startswith('socks'):
        return proxy

    # Format 2: user:pass@ip:port (standard)
    if '@' in proxy:
        return f"http://{proxy}"

    # Split by colon to detect format
    parts = proxy.split(':')

    # Format 3: ip:port:user:pass (provider format - user's format!)
    if len(parts) == 4:
        ip, port, user, password = parts
        return f"http://{user}:{password}@{ip}:{port}"

    # Format 1: ip:port (no authentication)
    elif len(parts) == 2:
        return f"http://{proxy}"

    # Unknown format - try as-is
    else:
        return f"http://{proxy}"

def _load_proxies_from_config():
    """
    Load proxies from Link Grabber's saved configuration.

    Returns list of proxies that can be used for downloads.
    Uses the same config file that Link Grabber saves to.

    Returns:
        list: List of proxy URLs (max 2 as per user requirement)
    """
    try:
        from modules.config.paths import get_config_dir
        import json
        import logging

        config_file = get_config_dir() / "proxy_settings.json"

        if not config_file.exists():
            logging.debug("No proxy config found - will use direct connection")
            return []

        # Read Link Grabber's saved proxies
        with open(config_file, 'r') as f:
            settings = json.load(f)

        proxies = []

        # Get both proxies (max 2 as per user requirement)
        proxy1 = settings.get('proxy1', '').strip()
        proxy2 = settings.get('proxy2', '').strip()

        # Parse and add proxy1
        if proxy1:
            parsed = _parse_proxy_format(proxy1)
            if parsed:
                proxies.append(parsed)
                logging.info(f"✓ Loaded Proxy 1: {proxy1[:20]}...")

        # Parse and add proxy2
        if proxy2:
            parsed = _parse_proxy_format(proxy2)
            if parsed:
                proxies.append(parsed)
                logging.info(f"✓ Loaded Proxy 2: {proxy2[:20]}...")

        if proxies:
            logging.info(f"📡 Total {len(proxies)} proxy(ies) loaded from Link Grabber")
        else:
            logging.debug("No valid proxies found in config")

        return proxies

    except Exception as e:
        import logging
        logging.warning(f"Failed to load proxies from config: {e}")
        return []

# ===================== MAIN THREAD ====================
class VideoDownloaderThread(QThread):
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    download_speed = pyqtSignal(str)
    eta = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    video_complete = pyqtSignal(str)

    # default safeguards so attribute lookups never explode even if init fails mid-way
    skip_recent_window = True

    def __init__(self, urls, save_path, options, parent=None, bulk_mode_data=None):
        super().__init__(parent)
        # Accept flexible input for URLs (string, list, dicts from Link Grabber, etc.)
        self.urls = extract_urls(urls)
        self.save_path = save_path
        # Ensure options behave like a dict so feature flags don't break older callers
        if options is None:
            self.options = {}
        elif isinstance(options, dict):
            self.options = options
        else:
            # Some legacy callers pass QVariants/objects – fall back to empty dict but keep reference
            try:
                self.options = dict(options)
            except Exception:
                self.options = {}
        self.cancelled = False
        self.success_count = 0
        self.skipped_count = 0
        self.skip_recent_window = coerce_bool(
            self.options.get('skip_recent_window'),
            default=self.skip_recent_window,
        )
        self.max_retries = self.options.get('max_retries', 3)
        self.force_all_methods = bool(self.options.get('force_all_methods', False))
        # Map quality preference to yt-dlp format selection if caller didn't supply one
        format_override = self.options.get('format')
        if not format_override:
            quality_pref = self.options.get('quality')
            format_override = quality_to_format(quality_pref)
        self.format_override = format_override

        # Proxy configuration (for IP block bypass)
        # ENHANCED: Load proxies from Link Grabber's saved config (automatic!)
        self.available_proxies = _load_proxies_from_config()  # List of all available proxies
        self.current_proxy_index = 0  # Track which proxy we're currently using

        # Set initial proxy (try config first, then options, then environment)
        if self.available_proxies:
            self.proxy_url = self.available_proxies[0]  # Use first proxy from config
        else:
            self.proxy_url = self.options.get('proxy_url', os.environ.get('HTTPS_PROXY', ''))

        # Rate limiting (to avoid triggering IP blocks)
        self.last_request_times = {}  # domain -> timestamp
        self.rate_limit_delay = self.options.get('rate_limit_delay', 2.5)  # seconds between requests

        # Bulk mode support
        self.bulk_mode_data = bulk_mode_data
        self.history_manager = None
        self.is_bulk_mode = bulk_mode_data and bulk_mode_data.get('enabled')

        if self.is_bulk_mode:
            self.history_manager = bulk_mode_data.get('history_manager')
            self.bulk_creators = bulk_mode_data.get('creators', {})
            # Only create tracking files in bulk mode
            self.downloaded_links_file = Path(save_path) / ".downloaded_links.txt"
            self.downloaded_links = self._load_downloaded_links()
        else:
            # Single mode: NO tracking files
            self.bulk_creators = {}
            self.downloaded_links_file = None
            self.downloaded_links = set()

    def _load_downloaded_links(self) -> set:
        """Load downloaded links (bulk mode only)"""
        if not self.is_bulk_mode or not self.downloaded_links_file:
            return set()  # Single mode: never load files

        try:
            if self.downloaded_links_file.exists():
                with open(self.downloaded_links_file, 'r', encoding='utf-8') as f:
                    return set(line.strip() for line in f if line.strip())
        except Exception:
            pass
        return set()

    def _mark_as_downloaded(self, url: str):
        """Mark URL as downloaded (bulk mode only)"""
        # TRIPLE SAFETY CHECK: Never create files in single mode!
        if not self.is_bulk_mode:
            return  # Single mode: NO file operations

        if not self.downloaded_links_file:
            return  # Extra safety: no file path set

        try:
            normalized = normalize_url(url)
            self.downloaded_links.add(normalized)

            # Write to file (only in bulk mode)
            with open(self.downloaded_links_file, 'a', encoding='utf-8') as f:
                f.write(f"{normalized}\n")
        except Exception as e:
            self.progress.emit(f"⚠️ Could not save download record: {str(e)[:50]}")

    def _is_already_downloaded(self, url: str) -> bool:
        """Check if already downloaded (bulk mode only)"""
        if not self.is_bulk_mode:
            return False  # Never skip in single mode

        normalized = normalize_url(url)
        return normalized in self.downloaded_links

    def _apply_rate_limit(self, domain: str):
        """Apply rate limiting to avoid triggering IP blocks"""
        if domain not in self.last_request_times:
            self.last_request_times[domain] = time.time()
            return

        now = time.time()
        elapsed = now - self.last_request_times[domain]

        if elapsed < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - elapsed
            if wait_time > 0.1:  # Only show message if waiting more than 100ms
                self.progress.emit(f"   ⏳ Rate limiting: waiting {wait_time:.1f}s...")
            time.sleep(wait_time)

        self.last_request_times[domain] = time.time()

    def _get_proxy_status_message(self, use_proxy=False) -> str:
        """Get formatted proxy status message for logging"""
        if not use_proxy or not self.proxy_url:
            if self.available_proxies:
                return "No proxy (available but not requested)"
            else:
                return "No proxy (IP blocks possible)"
        else:
            # Show partial proxy for privacy (hide credentials)
            proxy_display = self.proxy_url
            if '@' in proxy_display:
                # Format: http://user:pass@ip:port → http://***:***@ip:port
                parts = proxy_display.split('@')
                if len(parts) == 2:
                    proxy_display = f"{parts[0].split(':')[0]}://***:***@{parts[1]}"
            return f"Using proxy: {proxy_display}"

    def _try_download_with_auto_proxy_fallback(self, method, url, output_path, cookie_file=None):
        """
        Intelligent auto-fallback wrapper for download methods.

        Strategy:
        1. Try method with direct connection (fast, works most times)
        2. If fails with IP block AND proxy available → retry with proxy
        3. Return success/failure

        This mimics anti-detection browsers: try normal first, switch to proxy if blocked.

        Args:
            method: Download method function to call
            url: Video URL
            output_path: Save directory
            cookie_file: Optional cookie file path

        Returns:
            bool: True if download succeeded (direct or via proxy), False otherwise
        """
        # === STRATEGY 1: Try direct connection first ===
        try:
            result = method(url, output_path, cookie_file, use_proxy=False)
            if result:
                return True  # Success with direct connection!
        except Exception as e:
            # Method threw exception - treat as failure
            import logging
            logging.debug(f"Direct attempt exception: {e}")

        # === STRATEGY 2: Auto-fallback to proxy if available ===
        if self.available_proxies and self.proxy_url:
            self.progress.emit("")
            self.progress.emit("   ╔═══════════════════════════════════════════════╗")
            self.progress.emit("   ║  🌐 AUTO-SWITCHING TO PROXY                   ║")
            self.progress.emit("   ╚═══════════════════════════════════════════════╝")
            self.progress.emit("   🔄 Direct connection failed, trying with proxy...")
            self.progress.emit("")

            try:
                result = method(url, output_path, cookie_file, use_proxy=True)
                if result:
                    self.progress.emit("   🎉 SUCCESS via proxy!")
                    return True
            except Exception as e:
                import logging
                logging.debug(f"Proxy attempt exception: {e}")

        # Both strategies failed
        return False

    # Removed old timestamp logic - now using history.json only

    def _cleanup_tracking_files(self, folder_path: str):
        """Remove any leftover tracking files (for single mode cleanup)"""
        if self.is_bulk_mode:
            return  # Don't cleanup in bulk mode

        try:
            folder = Path(folder_path)
            if not folder.exists():
                return

            # Remove old tracking files if they exist
            tracking_files = [
                '.downloaded_links.txt',
                '.last_download_time.txt',
                '.download_history.txt',  # Any other variants
            ]

            for filename in tracking_files:
                file_path = folder / filename
                if file_path.exists():
                    file_path.unlink()
                    self.progress.emit(f"🧹 Removed leftover file: {filename}")

        except Exception as e:
            # Silent fail - not critical
            pass

    def _remove_from_source_txt(self, url: str, source_folder: str):
        """Remove URL from source txt file (bulk mode only)"""
        if not self.is_bulk_mode:
            return  # Skip in single mode

        try:
            source_path = Path(source_folder)
            if not source_path.exists(): return
            for txt_file in source_path.glob("*.txt"):
                if txt_file.name.startswith('.'): continue
                try:
                    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    target = url.strip()
                    if not target:
                        continue
                    target_lower = target.lower()
                    new_lines = [
                        line
                        for line in lines
                        if target not in line and target_lower not in line.lower()
                    ]
                    if len(new_lines) != len(lines):
                        with open(txt_file, 'w', encoding='utf-8') as f:
                            f.writelines(new_lines)
                        self.progress.emit(f"🗑️ Removed from {txt_file.name}")
                except Exception:
                    continue
        except Exception:
            pass

    def get_cookie_file(self, url, source_folder=None):
        """Return the most relevant cookies file for the given URL."""
        # IMPROVED: Returns first valid cookie (single cookie for backward compatibility)
        # But also stores all valid cookies in self._all_cookie_files for fallback
        try:
            candidates = []
            platform = _detect_platform(url)

            def _extend_with_platform_variants(base_path: Path):
                if not base_path:
                    return
                names = ["cookies.txt"]
                if platform != 'other':
                    names.insert(0, f"{platform}.txt")
                for name in names:
                    candidate = base_path / name
                    if candidate not in candidates:
                        candidates.append(candidate)

            if source_folder:
                folder_path = Path(source_folder)
                _extend_with_platform_variants(folder_path)
                cookies_sub = folder_path / "cookies"
                _extend_with_platform_variants(cookies_sub)
                parent_cookies = folder_path.parent / "cookies"
                if parent_cookies != cookies_sub:
                    _extend_with_platform_variants(parent_cookies)

            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            cookies_dir = project_root / "cookies"
            cookies_dir.mkdir(parents=True, exist_ok=True)

            if platform != 'other':
                platform_cookie = cookies_dir / f"{platform}.txt"
                _extend_with_platform_variants(platform_cookie.parent)

            universal_cookie = cookies_dir / "cookies.txt"
            if universal_cookie not in candidates:
                candidates.append(universal_cookie)

            desktop_cookie = Path.home() / "Desktop" / "toseeq-cookies.txt"
            if desktop_cookie not in candidates:
                candidates.append(desktop_cookie)

            # IMPROVED: Store ALL valid cookie files for fallback attempts
            valid_cookies = []
            for candidate in candidates:
                try:
                    if candidate and candidate.exists() and candidate.stat().st_size > 10:
                        valid_cookies.append(str(candidate))
                except Exception:
                    continue

            # Store for fallback use
            self._all_cookie_files = valid_cookies

            # Return first valid cookie (backward compatible)
            if valid_cookies:
                return valid_cookies[0]

        except Exception:
            pass
        return None

    # -----------------------
    # ==== Download Methods per Platform ====

    def _method1_batch_file_approach(self, url, output_path, cookie_file=None, use_proxy=False):
        try:
            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] 🚀 Method 1: YT-DLP Standard")

            # Show proxy status
            self.progress.emit(f"   {self._get_proxy_status_message(use_proxy)}")

            # Smart yt-dlp detection
            ytdlp_cmd = self._get_ytdlp_command()
            if not ytdlp_cmd:
                self.progress.emit(f"   ⚠️ yt-dlp not found, skipping")
                return False

            # Random user agent for better success
            user_agent = _get_random_user_agent()
            self.progress.emit(f"   🎭 UA: {user_agent[:50]}...")

            format_string = self.format_override or 'best'
            cmd = [
                ytdlp_cmd,
                '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                '--rm-cache-dir',
                '-f', format_string,
                '--user-agent', user_agent,
                '--restrict-filenames', '--no-warnings', '--retries', str(self.max_retries),
                '--continue', '--no-check-certificate',
                '--no-playlist',  # Don't download playlists
            ]

            # Add proxy if enabled
            if use_proxy and self.proxy_url:
                cmd.extend(['--proxy', self.proxy_url])

            if cookie_file:
                cmd.extend(['--cookies', cookie_file])
                self.progress.emit(f"   🍪 Cookies: {Path(cookie_file).name}")

            cmd.append(url)

            self.progress.emit(f"   ⏳ Starting download...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, encoding='utf-8', errors='replace')

            elapsed = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                self.progress.emit(f"   ✅ SUCCESS in {elapsed:.1f}s")
                return True
            else:
                error_msg = result.stderr[:300] if result.stderr else "Unknown error"
                self.progress.emit(f"   ❌ FAILED ({elapsed:.1f}s)")
                self.progress.emit(f"   📝 Error: {error_msg}")
            return False
        except subprocess.TimeoutExpired:
            self.progress.emit(f"   ⏱️ TIMEOUT (30min limit)")
            return False
        except Exception as e:
            self.progress.emit(f"   ❌ Exception: {str(e)[:100]}")
            return False

    def _method2_tiktok_special(self, url, output_path, cookie_file=None):
        """
        Enhanced TikTok download with:
        - IP block detection and retry
        - Proxy support
        - Better headers and user agent rotation
        - Rate limiting
        - Exponential backoff
        """
        try:
            if 'tiktok.com' not in url.lower():
                return False

            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] 🎵 TikTok Enhanced (Multi-Strategy)")

            # Apply rate limiting
            self._apply_rate_limit('tiktok.com')

            # IMPROVED: Prioritize watermark-free formats
            tiktok_formats = [
                ('http-264-hd-1', '🎉 HD No Watermark'),
                ('http-264-hd-0', '⚠️ HD With Watermark'),
                ('best[ext=mp4][height<=1080]', 'Best MP4 1080p'),
                ('bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 'Best Video+Audio'),
                ('best', 'Best Available'),
            ]

            # Collect all available cookies
            cookie_files_to_try = []
            if cookie_file:
                cookie_files_to_try.append(cookie_file)

            if hasattr(self, '_all_cookie_files'):
                for cf in self._all_cookie_files:
                    if cf and cf not in cookie_files_to_try:
                        cookie_files_to_try.append(cf)

            if not cookie_files_to_try:
                cookie_files_to_try.append(None)

            # STRATEGY 1: Try direct download (fast, works 70% of time)
            self.progress.emit(f"   📥 Strategy 1: Direct download")
            result = self._try_tiktok_download(url, output_path, cookie_files_to_try,
                                               tiktok_formats, use_proxy=False, retry_count=0)
            if result['success']:
                elapsed = (datetime.now() - start_time).total_seconds()
                self.progress.emit(f"   ✅ SUCCESS ({elapsed:.1f}s) {result['message']}")
                return True

            # Check if IP blocked
            ip_blocked = result.get('ip_blocked', False)

            # STRATEGY 2: Try with proxy (if available and IP blocked)
            if ip_blocked and self.proxy_url:
                self.progress.emit(f"   🌐 Strategy 2: Trying with proxy (IP block detected)")
                time.sleep(2)  # Brief delay before retry

                result = self._try_tiktok_download(url, output_path, cookie_files_to_try,
                                                   tiktok_formats, use_proxy=True, retry_count=0)
                if result['success']:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    self.progress.emit(f"   ✅ SUCCESS via proxy ({elapsed:.1f}s) {result['message']}")
                    return True

            # STRATEGY 3: Retry with exponential backoff (if IP blocked)
            if ip_blocked:
                self.progress.emit(f"   🔄 Strategy 3: Retry with exponential backoff")

                for retry_attempt in range(2):  # Try 2 more times
                    wait_time = 2 ** (retry_attempt + 1)  # 2s, 4s
                    self.progress.emit(f"   ⏳ Waiting {wait_time}s before retry {retry_attempt + 1}/2...")
                    time.sleep(wait_time)

                    # Try with enhanced headers and random user agent
                    result = self._try_tiktok_download(url, output_path, cookie_files_to_try,
                                                       tiktok_formats, use_proxy=bool(self.proxy_url),
                                                       retry_count=retry_attempt + 1)
                    if result['success']:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        self.progress.emit(f"   ✅ SUCCESS on retry {retry_attempt + 1} ({elapsed:.1f}s) {result['message']}")
                        return True

            # ALL STRATEGIES FAILED
            elapsed = (datetime.now() - start_time).total_seconds()
            self.progress.emit(f"   ❌ All strategies failed ({elapsed:.1f}s)")

            # Show specific error message
            if ip_blocked:
                self._show_tiktok_ip_block_help()
            else:
                self.progress.emit(f"   💡 Tips:")
                self.progress.emit(f"      • Make sure cookies/tiktok.txt exists")
                self.progress.emit(f"      • Video might be private or age-restricted")
                self.progress.emit(f"      • Try adding TikTok cookies (same as Link Grabber)")

            return False

        except Exception as e:
            self.progress.emit(f"   ❌ TikTok error: {str(e)[:100]}")
            return False

    def _try_tiktok_download(self, url, output_path, cookie_files, formats, use_proxy=False, retry_count=0):
        """
        Try TikTok download with given configuration
        Returns: {'success': bool, 'message': str, 'ip_blocked': bool}
        """
        last_error = ""
        ip_blocked = False

        for cookie_attempt_idx, current_cookie in enumerate(cookie_files, 1):
            if cookie_attempt_idx > 1:
                self.progress.emit(f"   🔄 Cookie {cookie_attempt_idx}/{len(cookie_files)}")
                if current_cookie:
                    self.progress.emit(f"   🍪 Using: {Path(current_cookie).name}")

            for i, (fmt, desc) in enumerate(formats, 1):
                try:
                    # Only show format on first attempt to reduce noise
                    if retry_count == 0 and cookie_attempt_idx == 1:
                        self.progress.emit(f"   🔄 Format {i}/{len(formats)}: {desc}")

                    # Build command with enhanced headers
                    user_agent = _get_random_user_agent()

                    cmd = [
                        'yt-dlp',
                        '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                        '-f', fmt,
                        '--no-playlist',
                        '--geo-bypass',
                        '--user-agent', user_agent,
                        '--restrict-filenames',
                        '--no-warnings',
                        '--retries', str(self.max_retries),
                        # Enhanced headers for better bot evasion
                        '--add-header', 'Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        '--add-header', 'Accept-Language:en-US,en;q=0.9',
                        '--add-header', 'Accept-Encoding:gzip, deflate, br',
                        '--add-header', 'Referer:https://www.tiktok.com/',
                    ]

                    # Add proxy if requested
                    if use_proxy and self.proxy_url:
                        cmd.extend(['--proxy', self.proxy_url])

                    if current_cookie:
                        cmd.extend(['--cookies', current_cookie])

                    cmd.append(url)

                    result = subprocess.run(cmd, capture_output=True, text=True,
                                          timeout=300, encoding='utf-8', errors='replace')

                    if result.returncode == 0:
                        watermark_status = "🎉 NO WATERMARK!" if "hd-1" in fmt else ""
                        proxy_status = " via proxy" if use_proxy else ""
                        return {
                            'success': True,
                            'message': f"{watermark_status}{proxy_status}",
                            'ip_blocked': False
                        }
                    else:
                        # Check BOTH stdout and stderr (yt-dlp can use either)
                        error_output = (result.stderr or '') + (result.stdout or '')
                        last_error = error_output

                        # Show error on last attempt for debugging
                        if i == len(formats) and cookie_attempt_idx == len(cookie_files):
                            error_snippet = error_output[:150] if error_output else "Unknown error"
                            self.progress.emit(f"   ❌ Error: {error_snippet}")

                        # Check if IP blocked
                        if _is_ip_block_error(error_output):
                            ip_blocked = True

                except Exception as e:
                    last_error = str(e)
                    continue

        return {
            'success': False,
            'message': last_error[:100] if last_error else "Unknown error",
            'ip_blocked': ip_blocked
        }

    def _show_tiktok_ip_block_help(self):
        """Show helpful message when IP block detected"""
        self.progress.emit("")
        self.progress.emit("   ╔═══════════════════════════════════════════════╗")
        self.progress.emit("   ║  🚫 TIKTOK IP BLOCK DETECTED                  ║")
        self.progress.emit("   ╚═══════════════════════════════════════════════╝")
        self.progress.emit("")
        self.progress.emit("   🔧 SOLUTIONS:")
        self.progress.emit("")
        self.progress.emit("   1️⃣ Use VPN or Proxy:")
        self.progress.emit("      • Enable VPN on your computer")
        self.progress.emit("      • Or set proxy: export HTTPS_PROXY=socks5://127.0.0.1:1080")
        self.progress.emit("      • Try different proxy location")
        self.progress.emit("")
        self.progress.emit("   2️⃣ Wait and Retry:")
        self.progress.emit("      • TikTok may have rate-limited your IP")
        self.progress.emit("      • Wait 15-60 minutes and try again")
        self.progress.emit("      • Temporary blocks usually expire")
        self.progress.emit("")
        self.progress.emit("   3️⃣ Check Video Availability:")
        self.progress.emit("      • Video might be private/deleted")
        self.progress.emit("      • Try opening in browser first")
        self.progress.emit("      • Check if region-locked")
        self.progress.emit("")
        self.progress.emit("   💡 Quick fix: Switch to different network (WiFi ↔ Mobile data)")
        self.progress.emit("")

    def _method3_optimized_ytdlp(self, url, output_path, cookie_file=None, use_proxy=False):
        try:
            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] 🔄 Method 3: yt-dlp with Cookies")

            # Show proxy status
            self.progress.emit(f"   {self._get_proxy_status_message(use_proxy)}")

            # Random user agent
            user_agent = _get_random_user_agent()
            self.progress.emit(f"   🎭 UA: {user_agent[:50]}...")

            format_string = self.format_override or 'best'
            ydl_opts = {
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'format': format_string,
                'quiet': True,
                'no_warnings': True,
                'retries': self.max_retries,
                'fragment_retries': self.max_retries,
                'continuedl': True,
                'nocheckcertificate': True,
                'restrictfilenames': True,
                'progress_hooks': [self._progress_hook],
                'http_headers': {'User-Agent': user_agent},
            }

            # Add proxy if enabled
            if use_proxy and self.proxy_url:
                ydl_opts['proxy'] = self.proxy_url

            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file
                self.progress.emit(f"   🍪 Cookies: {Path(cookie_file).name}")
            else:
                self.progress.emit(f"   ⚠️ No cookies (may fail for private content)")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            elapsed = (datetime.now() - start_time).total_seconds()
            self.progress.emit(f"   ✅ SUCCESS in {elapsed:.1f}s")
            return True

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0
            error_msg = str(e)
            self.progress.emit(f"   ❌ FAILED ({elapsed:.1f}s)")

            # Give specific hints based on error
            if 'login required' in error_msg.lower() or 'rate' in error_msg.lower():
                self.progress.emit(f"   💡 Hint: Need cookies for this content")
            elif 'private' in error_msg.lower():
                self.progress.emit(f"   💡 Hint: Content is private")

            self.progress.emit(f"   📝 Error: {error_msg[:200]}")
            return False

    def _method_instagram_enhanced(self, url, output_path, cookie_file=None, use_proxy=False):
        """Enhanced Instagram downloader with cookie validation and multiple fallbacks"""
        try:
            if 'instagram.com' not in url.lower():
                return False

            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] 📸 Instagram Enhanced Method")
            self.progress.emit(f"   {self._get_proxy_status_message(use_proxy)}")

            # Smart yt-dlp detection
            ytdlp_cmd = self._get_ytdlp_command()
            if not ytdlp_cmd:
                self.progress.emit(f"   ⚠️ yt-dlp not found, skipping")
                return False

            # IMPROVED: Collect ALL available cookie files to try
            cookie_files_to_try = []

            # Add primary cookie file
            if cookie_file and Path(cookie_file).exists():
                cookie_files_to_try.append(cookie_file)

            # Add other available cookies as fallback
            if hasattr(self, '_all_cookie_files'):
                for cf in self._all_cookie_files:
                    if cf and cf not in cookie_files_to_try and Path(cf).exists():
                        # Only add if file name suggests it might work for Instagram
                        if 'instagram' in Path(cf).name.lower() or 'cookies.txt' in Path(cf).name.lower():
                            cookie_files_to_try.append(cf)

            total_cookies = len(cookie_files_to_try)
            self.progress.emit(f"   🍪 Found {total_cookies} cookie file(s) to try")

            # Try each cookie file
            for cookie_idx, current_cookie_file in enumerate(cookie_files_to_try, 1):
                if cookie_idx > 1:
                    self.progress.emit(f"   🔄 Trying alternate cookie file ({cookie_idx}/{total_cookies})")

                self.progress.emit(f"   🍪 Using: {Path(current_cookie_file).name}")

                # Validate cookie
                cookie_is_valid = False
                validator = InstagramCookieValidator()
                validation = validator.validate_cookie_file(current_cookie_file)

                if validation['is_valid']:
                    self.progress.emit(f"   🔑 Valid Instagram cookies!")
                    cookie_is_valid = True
                else:
                    self.progress.emit(f"   ⚠️ Cookie validation failed:")
                    for error in validation['errors'][:1]:  # Show first error only
                        self.progress.emit(f"      • {error}")

                    if validation['is_expired']:
                        self.progress.emit(f"   💡 Cookies expired - trying next...")
                    elif not validation['has_sessionid']:
                        self.progress.emit(f"   💡 No sessionid found - trying next...")

                    # Try next cookie if validation failed
                    continue

                # Try download with validated cookie
                self.progress.emit(f"   📥 Attempting download...")

                user_agent = _get_random_user_agent()
                self.progress.emit(f"   🎭 UA: {user_agent[:50]}...")

                cmd = [
                    ytdlp_cmd,
                    '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                    '--cookies', current_cookie_file,
                    '--user-agent', user_agent,
                    '-f', 'best',
                    '--no-playlist',
                    '--restrict-filenames',
                    '--no-warnings',
                ]

                # Add proxy if enabled
                if use_proxy and self.proxy_url:
                    cmd.extend(['--proxy', self.proxy_url])

                cmd.append(url)

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, encoding='utf-8', errors='replace')

                if result.returncode == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    self.progress.emit(f"   ✅ SUCCESS with {Path(current_cookie_file).name} ({elapsed:.1f}s)")
                    return True
                else:
                    error_snippet = result.stderr[:100] if result.stderr else "Unknown"
                    self.progress.emit(f"   ❌ Download failed: {error_snippet}")

            # If all cookie files failed, show helpful error message
            elapsed = (datetime.now() - start_time).total_seconds()
            self.progress.emit(f"   ❌ All cookie attempts failed ({elapsed:.1f}s)")
            self.progress.emit(f"   ")
            self.progress.emit(f"   ╔═══════════════════════════════════════════════╗")
            self.progress.emit(f"   ║  📸 INSTAGRAM AUTHENTICATION REQUIRED         ║")
            self.progress.emit(f"   ╚═══════════════════════════════════════════════╝")
            self.progress.emit(f"   ")
            self.progress.emit(f"   🔧 QUICK FIX:")
            self.progress.emit(f"   ")
            self.progress.emit(f"   1️⃣ Same cookies work for Link Grabber & Downloader!")
            self.progress.emit(f"      • If Link Grabber works, Downloader will too")
            self.progress.emit(f"      • Export cookies to: cookies/instagram.txt")
            self.progress.emit(f"   ")
            self.progress.emit(f"   2️⃣ How to export cookies:")
            self.progress.emit(f"      a) Install browser extension:")
            self.progress.emit(f"         'Get cookies.txt LOCALLY'")
            self.progress.emit(f"      b) Login to Instagram in browser")
            self.progress.emit(f"      c) Click extension → Export")
            self.progress.emit(f"      d) Save as: cookies/instagram.txt")
            self.progress.emit(f"   ")
            self.progress.emit(f"   3️⃣ Make sure:")
            self.progress.emit(f"      • You're logged into Instagram in browser")
            self.progress.emit(f"      • Cookies are NOT expired (< 30 days old)")
            self.progress.emit(f"      • File contains 'sessionid' cookie")
            self.progress.emit(f"   ")
            self.progress.emit(f"   💡 Checked {total_cookies} cookie file(s) - all invalid/expired")
            self.progress.emit(f"   ")
            return False

        except Exception as e:
            self.progress.emit(f"   ❌ Instagram enhanced error: {str(e)[:100]}")
            return False

    def _method_instaloader(self, url, output_path, cookie_file=None):
        try:
            if 'instagram.com' not in url.lower():
                return False
            try:
                import instaloader
            except ImportError:
                self.progress.emit("⚠️ Instaloader not installed; skipping fallback")
                return False

            self.progress.emit("📸 Instaloader fallback")
            match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)", url, re.IGNORECASE)
            if not match:
                self.progress.emit("⚠️ Could not detect Instagram shortcode for Instaloader")
                return False

            shortcode = match.group(1)
            loader = instaloader.Instaloader(
                dirname_pattern=os.path.join(output_path, "{target}"),
                filename_pattern="{shortcode}",
                download_videos=True,
                download_video_thumbnails=False,
                download_pictures=False,
                download_comments=False,
                save_metadata=False,
                quiet=True,
                compress_json=False,
            )

            if cookie_file:
                try:
                    cookies_dict = {}
                    with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as handle:
                        for line in handle:
                            stripped = line.strip()
                            if not stripped or stripped.startswith('#'):
                                continue
                            parts = stripped.split('\t')
                            if len(parts) >= 7:
                                cookies_dict[parts[5]] = parts[6]
                    if cookies_dict:
                        loader.context._session.cookies.update(cookies_dict)
                except Exception as cookie_error:
                    self.progress.emit(f"⚠️ Instaloader cookie load failed: {str(cookie_error)[:60]}")

            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            target = post.owner_username or "instagram"
            loader.download_post(post, target=target)
            self.progress.emit("✅ Instaloader SUCCESS")
            return True
        except Exception as e:
            self.progress.emit(f"⚠️ Instaloader error: {str(e)[:100]}")
            return False

    def _method_gallery_dl(self, url, output_path, cookie_file=None):
        """gallery-dl fallback for Instagram, Twitter, etc."""
        try:
            self.progress.emit("🖼️ gallery-dl fallback")
            cmd = [
                'gallery-dl',
                '--dest', output_path,
                '--filename', '{title}_{id}.{extension}',
                '--no-mtime',
            ]

            if cookie_file:
                cmd.extend(['--cookies', cookie_file])
                self.progress.emit(f"🍪 Using cookies: {Path(cookie_file).name}")

            cmd.append(url)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                self.progress.emit("✅ gallery-dl SUCCESS!")
                return True
            else:
                error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                self.progress.emit(f"⚠️ gallery-dl failed: {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            self.progress.emit("⚠️ gallery-dl timeout")
            return False
        except FileNotFoundError:
            self.progress.emit("⚠️ gallery-dl not installed")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ gallery-dl error: {str(e)[:100]}")
            return False

    def _method6_youtube_dl_fallback(self, url, output_path, cookie_file=None):
        """youtube-dl as final fallback (older but sometimes works)"""
        try:
            self.progress.emit("🔄 youtube-dl fallback (legacy)")
            format_string = self.format_override or 'best'
            cmd = [
                'youtube-dl',
                '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                '-f', format_string,
                '--no-warnings',
                '--retries', str(self.max_retries),
                '--continue',
                '--no-check-certificate'
            ]

            if cookie_file:
                cmd.extend(['--cookies', cookie_file])

            cmd.append(url)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                self.progress.emit("✅ youtube-dl SUCCESS!")
                return True
            else:
                self.progress.emit("⚠️ youtube-dl failed")
                return False

        except subprocess.TimeoutExpired:
            self.progress.emit("⚠️ youtube-dl timeout")
            return False
        except FileNotFoundError:
            self.progress.emit("⚠️ youtube-dl not installed")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ youtube-dl error: {str(e)[:100]}")
            return False

    def _method4_alternative_formats(self, url, output_path, cookie_file=None, use_proxy=False):
        try:
            self.progress.emit("🔄 Method 4: Alternative formats")
            self.progress.emit(f"   {self._get_proxy_status_message(use_proxy)}")

            user_agent = _get_random_user_agent()
            self.progress.emit(f"   🎭 UA: {user_agent[:50]}...")

            format_options = ['best[ext=mp4]', 'bestvideo+bestaudio', 'best']
            if self.format_override and self.format_override not in format_options:
                format_options.insert(0, self.format_override)
            elif self.format_override:
                # Prioritize selected format
                format_options.remove(self.format_override)
                format_options.insert(0, self.format_override)
            for fmt in format_options:
                try:
                    ydl_opts = {
                        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                        'format': fmt,
                        'quiet': True, 'no_warnings': True, 'retries': self.max_retries,
                        'continuedl': True, 'nocheckcertificate': True, 'restrictfilenames': True,
                        'http_headers': {'User-Agent': user_agent},
                    }
                    if use_proxy and self.proxy_url:
                        ydl_opts['proxy'] = self.proxy_url
                    if cookie_file: ydl_opts['cookiefile'] = cookie_file
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    self.progress.emit(f"✅ Method 4 SUCCESS (format: {fmt})")
                    return True
                except Exception:
                    continue
            self.progress.emit("⚠️ Method 4 failed")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ Method 4 error: {str(e)[:100]}")
            return False

    def _method5_force_ipv4(self, url, output_path, cookie_file=None, use_proxy=False):
        try:
            self.progress.emit("🔄 Method 5: Force IPv4 fallback")
            self.progress.emit(f"   {self._get_proxy_status_message(use_proxy)}")

            # Smart yt-dlp detection
            ytdlp_cmd = self._get_ytdlp_command()
            if not ytdlp_cmd:
                self.progress.emit(f"   ⚠️ yt-dlp not found, skipping")
                return False

            user_agent = _get_random_user_agent()
            self.progress.emit(f"   🎭 UA: {user_agent[:50]}...")

            format_string = self.format_override or 'best'
            cmd = [
                ytdlp_cmd,
                '-o', os.path.join(output_path, '%(title)s.%(ext)s'),
                '-f', format_string,
                '--user-agent', user_agent,
                '--force-ipv4', '--no-warnings', '--geo-bypass',
                '--retries', str(self.max_retries), '--ignore-errors', '--continue',
                '--restrict-filenames', '--no-check-certificate'
            ]

            if use_proxy and self.proxy_url:
                cmd.extend(['--proxy', self.proxy_url])

            if cookie_file:
                cmd.extend(['--cookies', cookie_file])
                self.progress.emit(f"   🍪 Cookies: {Path(cookie_file).name}")

            cmd.append(url)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900,
                encoding='utf-8',
                errors='replace'
            )
            if result.returncode == 0:
                self.progress.emit("✅ Method 5 SUCCESS!")
                return True
            error_msg = result.stderr[:200] if result.stderr else "Unknown error"
            self.progress.emit(f"⚠️ Method 5 failed: {error_msg}")
            return False
        except subprocess.TimeoutExpired:
            self.progress.emit("⚠️ Method 5 timeout")
            return False
        except Exception as e:
            self.progress.emit(f"⚠️ Method 5 error: {str(e)[:100]}")
            return False

    def _progress_hook(self, d):
        try:
            if self.cancelled:
                raise Exception("Cancelled by user")
            if d['status'] == 'downloading':
                speed = d.get('speed', 0)
                if speed:
                    speed_mb = speed / (1024 * 1024)
                    self.download_speed.emit(f"{speed_mb:.2f} MB/s")
                eta = d.get('eta', 0)
                if eta:
                    mins, secs = divmod(eta, 60)
                    self.eta.emit(f"{int(mins)}m {int(secs)}s")
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                if total > 0:
                    percent = int((downloaded / total) * 100)
                    self.progress_percent.emit(percent)
        except Exception:
            pass

    # ---- MAIN DOWNLOAD LOOP ----

    def run(self):
        try:
            if not self.urls:
                self.finished.emit(False, "❌ No URLs provided")
                return
            total = len(self.urls)

            # Show mode clearly
            mode_name = "🔹 BULK MODE" if self.is_bulk_mode else "🔸 SINGLE MODE"
            self.progress.emit("="*60)
            self.progress.emit(f"🚀 SMART DOWNLOADER STARTING - {mode_name}")
            self.progress.emit(f"📊 Total links: {total}")

            if self.is_bulk_mode:
                self.progress.emit(f"📂 Creators: {len(self.bulk_creators)}")
                self.progress.emit("✅ History tracking: ON")
                self.progress.emit("✅ Auto URL cleanup: ON")
                self.progress.emit(f"📝 Track file: {self.downloaded_links_file.name}")
            else:
                self.progress.emit("📁 Save: Desktop/Toseeq Downloads")
                self.progress.emit("⚡ Simple mode: No tracking, no extra files")
                self.progress.emit("🚫 File creation: DISABLED")
                # Clean up any leftover tracking files from old runs
                self._cleanup_tracking_files(self.save_path)

            # Show proxy status
            if self.available_proxies:
                self.progress.emit(f"🌐 Proxies loaded: {len(self.available_proxies)} from Link Grabber")
                self.progress.emit("✅ Auto-fallback: Direct → Proxy (if blocked)")
            else:
                self.progress.emit("⚠️ WARNING: No proxies configured - IP blocks possible!")
                self.progress.emit("   💡 Add proxies in Link Grabber for better success rate")

            self.progress.emit("="*60)
            if self.force_all_methods:
                self.progress.emit("🛡️ Multi-strategy fallback enabled")
            # Map URLs to their source folder by looking up all *.txt in save_path (recursive)
            url_folder_map = {}
            for root, dirs, files in os.walk(self.save_path):
                for fname in files:
                    if fname.endswith(".txt") and not fname.startswith('.'):
                        txt_path = Path(root) / fname
                        try:
                            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                                for line in f:
                                    raw_url = line.strip()
                                    if not raw_url:
                                        continue
                                    key = normalize_url(raw_url)
                                    if key:
                                        url_folder_map[key] = root
                        except Exception:
                            continue
            # Fallback: direct URLs go to main save_path
            for url in self.urls:
                key = normalize_url(url)
                if key not in url_folder_map:
                    url_folder_map[key] = self.save_path
            processed = 0
            for url in self.urls:
                if self.cancelled: break
                folder = url_folder_map.get(normalize_url(url), self.save_path)
                os.makedirs(folder, exist_ok=True)
                # Skip logic handled by history.json in bulk mode
                processed += 1
                if self._is_already_downloaded(url):
                    self.progress.emit(f"⏭️ [{processed}/{total}] Already downloaded, skipping...")
                    self.skipped_count += 1
                    continue
                self.progress.emit(f"\n📥 [{processed}/{total}] {url[:80]}...")
                cookie_file = self.get_cookie_file(url, folder)
                # Platform-wise methods with enhanced fallbacks
                platform = _detect_platform(url)
                if platform == 'tiktok':
                    methods = [
                        self._method2_tiktok_special,
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method4_alternative_formats,
                        self._method5_force_ipv4,
                        self._method6_youtube_dl_fallback,
                    ]
                elif platform == 'instagram':
                    methods = [
                        self._method_instagram_enhanced,  # NEW: Try browser cookies first
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method_gallery_dl,
                        self._method_instaloader,
                        self._method4_alternative_formats,
                    ]
                elif platform == 'twitter':
                    methods = [
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method_gallery_dl,
                        self._method4_alternative_formats,
                        self._method5_force_ipv4,
                    ]
                else:
                    methods = [
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method4_alternative_formats,
                        self._method5_force_ipv4,
                        self._method6_youtube_dl_fallback,
                    ]

                # Force all methods adds extras
                if not self.force_all_methods:
                    # Limit to first 3-4 methods for speed
                    methods = methods[:4]
                # Try all methods with intelligent proxy fallback
                success = False
                for method in methods:
                    if self.cancelled: break
                    try:
                        # ENHANCED: Auto-fallback to proxy if direct fails (anti-detection style!)
                        if self._try_download_with_auto_proxy_fallback(method, url, folder, cookie_file):
                            success = True
                            break
                    except Exception as e:
                        self.progress.emit(f"   ⚠️ Method error: {str(e)[:100]}")
                if success:
                    self.success_count += 1
                    self.progress.emit(f"✅ [{processed}/{total}] Downloaded!")
                    self._mark_as_downloaded(url)
                    self._remove_from_source_txt(url, folder)
                    # Timestamp tracking handled by history.json
                    self.video_complete.emit(url)
                else:
                    self.progress.emit(f"❌ [{processed}/{total}] ALL METHODS FAILED")
                pct = int((processed / total) * 100)
                self.progress_percent.emit(pct)
            self.progress.emit("\n" + "="*60)
            self.progress.emit("📊 FINAL REPORT:")
            self.progress.emit(f"✅ Successfully downloaded: {self.success_count}")
            self.progress.emit(f"⏭️ Skipped (already done): {self.skipped_count}")
            self.progress.emit(f"❌ Failed: {total - self.success_count - self.skipped_count}")
            self.progress.emit("="*60)

            # Update history.json for bulk mode
            if self.history_manager and self.bulk_creators:
                self.progress.emit("\n📝 Updating download history...")
                try:
                    # Track downloads per creator
                    creator_stats = {}  # {creator: {'success': 0, 'failed': 0}}

                    # Count successes/failures per creator
                    for creator, creator_info in self.bulk_creators.items():
                        creator_links = set(creator_info.get('links', []))
                        success = 0
                        failed = 0

                        for url in self.urls:
                            if url in creator_links:
                                if url in self.downloaded_links:
                                    success += 1
                                else:
                                    failed += 1

                        creator_stats[creator] = {'success': success, 'failed': failed}

                    # Update history for each creator
                    for creator, stats in creator_stats.items():
                        status = 'success' if stats['failed'] == 0 else ('partial' if stats['success'] > 0 else 'failed')
                        self.history_manager.update_creator(
                            creator,
                            downloaded_count=stats['success'],
                            failed_count=stats['failed'],
                            status=status
                        )
                        self.progress.emit(f"  ✓ {creator}: {stats['success']} downloaded, {stats['failed']} failed")

                        # Remove successfully downloaded URLs from links file
                        if stats['success'] > 0:
                            links_file = self.bulk_creators[creator].get('links_file')
                            if links_file and Path(links_file).exists():
                                try:
                                    # Read current content
                                    with open(links_file, 'r', encoding='utf-8', errors='ignore') as f:
                                        lines = f.readlines()

                                    # Filter out downloaded links
                                    new_lines = []
                                    for line in lines:
                                        url_in_line = line.strip()
                                        if not url_in_line or url_in_line.startswith('#'):
                                            new_lines.append(line)
                                            continue

                                        # Check if this URL was downloaded
                                        is_downloaded = False
                                        for dl_url in self.downloaded_links:
                                            if url_in_line in dl_url or dl_url in url_in_line:
                                                is_downloaded = True
                                                break

                                        if not is_downloaded:
                                            new_lines.append(line)

                                    # Write back
                                    with open(links_file, 'w', encoding='utf-8') as f:
                                        f.writelines(new_lines)

                                    self.progress.emit(f"  🗑️ Updated {Path(links_file).name}")
                                except Exception as e:
                                    self.progress.emit(f"  ⚠️ Failed to update {Path(links_file).name}: {str(e)[:50]}")

                    self.progress.emit("✅ History updated!")
                except Exception as e:
                    self.progress.emit(f"⚠️ History update failed: {str(e)[:100]}")

            if self.cancelled:
                self.finished.emit(False, f"⚠️ Cancelled - {self.success_count} downloaded")
            elif self.success_count + self.skipped_count == total:
                self.finished.emit(True, f"✅ ALL DONE! {self.success_count} new, {self.skipped_count} skipped")
            elif self.success_count > 0:
                self.finished.emit(True, f"⚠️ Partial: {self.success_count} downloaded, {self.skipped_count} skipped")
            else:
                self.finished.emit(False, f"❌ Failed - 0 downloaded")
        except Exception as e:
            self.progress.emit(f"❌ CRITICAL ERROR: {str(e)[:200]}")
            self.finished.emit(False, f"❌ Error: {str(e)[:100]}")

    def cancel(self):
        self.cancelled = True
        self.progress.emit("⚠️ Cancellation requested...")
