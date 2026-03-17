"""Core implementation for the smart video downloader."""

import os
import subprocess
import re
import time
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yt_dlp
from PyQt5.QtCore import QThread, pyqtSignal
from modules.shared.auth_network_hub import AuthNetworkHub

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

def _extract_creator_from_url(url: str) -> str:
    """Extract creator/channel name from URL path as fallback."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        parts = [p for p in (parsed.path or '').split('/') if p]
        if not parts:
            return ""
        # Skip common non-creator path segments
        skip = {'watch', 'reel', 'reels', 'video', 'videos', 'shorts', 'live', 'p', 'tv', 'share', 'stories'}
        for part in parts:
            if part.startswith('@'):
                return part.lstrip('@')
            if part.lower() not in skip and not part.isdigit():
                return part
    except Exception:
        pass
    return ""


def _get_random_user_agent() -> str:
    """
    Get random user agent from shared pool to avoid detection.
    Now uses the same 20+ user agents as Link Grabber for consistency.
    """
    try:
        from modules.shared.user_agents import get_random_user_agent
        return get_random_user_agent()
    except ImportError:
        # Fallback if shared module not available
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def _get_chrome120_headers() -> list:
    """
    ENHANCED: Return realistic Chrome 120 headers for better platform compatibility
    Synced with Link Grabber for consistency.

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

def _resolve_ffmpeg_path() -> Optional[str]:
    """
    Resolve ffmpeg executable path from bundle, repo, env, or PATH.
    Returns absolute path when possible, else None.
    """
    try:
        from modules.video_editor.utils import check_ffmpeg, get_ffmpeg_path
        if check_ffmpeg():
            path = get_ffmpeg_path()
            if path:
                if path == 'ffmpeg':
                    which_path = shutil.which("ffmpeg")
                    if which_path:
                        return which_path
                elif Path(path).exists():
                    return path
    except Exception:
        pass

    env_path = os.getenv("FFMPEG_PATH")
    if env_path:
        if env_path == 'ffmpeg':
            which_path = shutil.which("ffmpeg")
            if which_path:
                return which_path
        elif Path(env_path).exists():
            return env_path

    repo_root = Path(__file__).resolve().parents[2]
    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    candidates = [
        repo_root / "ffmpeg" / "bin" / exe_name,
        repo_root / "ffmpeg" / exe_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path

    if os.name == "nt":
        fallbacks = [
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/ffmpeg/ffmpeg.exe"),
        ]
        for fallback in fallbacks:
            if fallback.exists():
                return str(fallback)

    return None

def _validate_cookie_file(cookie_file: str, max_age_days: int = 14) -> dict:
    """
    ENHANCED: Validate cookie file for freshness and format validity
    Synced with Link Grabber for consistency.

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
        import time
        import logging

        cookie_path = Path(cookie_file)

        # Check 1: File exists and has content
        if not cookie_path.exists():
            result['warnings'].append(f"âŒ Cookie file not found: {cookie_file}")
            return result

        file_size = cookie_path.stat().st_size
        if file_size < 10:
            result['warnings'].append(f"âš ï¸ Cookie file too small ({file_size} bytes)")
            return result

        # Check 2: File freshness (modification time)
        mod_time = cookie_path.stat().st_mtime
        file_age = datetime.now() - datetime.fromtimestamp(mod_time)
        result['age_days'] = file_age.days

        if file_age.days > max_age_days:
            result['fresh'] = False
            result['warnings'].append(
                f"âš ï¸ Cookie file is {file_age.days} days old (older than {max_age_days} days)"
            )
            result['warnings'].append(f"   ðŸ’¡ Consider refreshing cookies for better success rate")

        # Check 3: Valid Netscape format and cookie expiration
        current_timestamp = int(time.time())

        with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        cookie_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
        result['total_cookies'] = len(cookie_lines)

        if result['total_cookies'] == 0:
            result['warnings'].append(f"âš ï¸ No cookies found in file (only comments/blank lines)")
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
                    f"âš ï¸ {expired_count}/{result['total_cookies']} cookies expired ({expiry_pct:.0f}%)"
                )
                result['warnings'].append(f"   ðŸ’¡ Cookie refresh recommended")

        # All checks passed
        result['valid'] = True

        # Add success message if fresh and minimal warnings
        if result['fresh'] and len(result['warnings']) == 0:
            logging.debug(f"âœ“ Cookie validation passed: {result['total_cookies']} cookies, {result['age_days']} days old")

    except Exception as e:
        result['warnings'].append(f"âŒ Cookie validation error: {str(e)[:100]}")

    return result


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
        self.auth_hub = AuthNetworkHub()
        # Accept flexible input for URLs (string, list, dicts from Link Grabber, etc.)
        # Preserve _meta from Link Grabber entries before extracting URLs
        self._url_meta = {}
        if isinstance(urls, list):
            for item in urls:
                if isinstance(item, dict) and '_meta' in item and 'url' in item:
                    self._url_meta[item['url'].strip()] = item['_meta']
        self.urls = extract_urls(urls)
        self.save_path = save_path
        # Ensure options behave like a dict so feature flags don't break older callers
        if options is None:
            self.options = {}
        elif isinstance(options, dict):
            self.options = options
        else:
            # Some legacy callers pass QVariants/objects â€“ fall back to empty dict but keep reference
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
        # Optional per-URL budgets (used by some platform strategies)
        self.youtube_time_budget_sec = float(self.options.get('youtube_time_budget_sec', 0) or 0)
        self.youtube_max_attempts = int(self.options.get('youtube_max_attempts', 0) or 0)
        # Map quality preference to yt-dlp format selection if caller didn't supply one
        format_override = self.options.get('format')
        if not format_override:
            quality_pref = self.options.get('quality')
            format_override = quality_to_format(quality_pref)
        self.format_override = format_override
        self.ffmpeg_path = _resolve_ffmpeg_path()
        self._format_fallback_applied = False
        if not self.ffmpeg_path and self.format_override:
            if 'bestvideo' in self.format_override or '+' in self.format_override:
                self.format_override = 'best[ext=mp4]/best'
                self._format_fallback_applied = True

        # Proxy configuration (for IP block bypass) - ENHANCED
        # Priority: Options â†’ Link Grabber config â†’ Environment variable
        self.proxies = self._load_proxies_from_config()
        self.current_proxy_index = 0
        self.proxy_url = self.options.get('proxy_url', os.environ.get('HTTPS_PROXY', ''))  # Legacy support

        # Auth configuration: Collect ALL and prioritize (profile-first)
        self._all_cookie_files = []
        if self.urls:
            first_url = self.urls[0]
            first_platform = self.auth_hub.detect_platform(first_url)
            try:
                from modules.shared.session_authority import get_session_authority
                authority = get_session_authority()
                profile_cookie = authority.ensure_fresh_cookies(first_platform)
                if profile_cookie:
                    self._all_cookie_files.append(profile_cookie)
            except Exception:
                pass
            # Managed CDP auth assist: when managed Chrome is running,
            # its active session keeps cookies fresh.  Re-export from the
            # profile if no cookie was obtained above and the flag is ON.
            if not self._all_cookie_files and first_platform in (
                "instagram", "facebook", "tiktok",
            ):
                try:
                    from modules.shared.managed_chrome_session import (
                        MANAGED_CDP_ATTACH_FIRST,
                        get_managed_chrome_session,
                    )
                    if MANAGED_CDP_ATTACH_FIRST:
                        mgr = get_managed_chrome_session()
                        if mgr.is_running():
                            # Managed Chrome is alive — force a fresh export
                            try:
                                sa = get_session_authority()
                                fresh = sa.force_browser_cookie_refresh(first_platform)
                                if fresh:
                                    self._all_cookie_files.append(fresh)
                            except Exception:
                                pass
                except ImportError:
                    pass
            # Add file-scan candidates (dedup against profile cookie)
            for cf in self.auth_hub.valid_cookie_files(first_platform):
                if cf not in self._all_cookie_files:
                    self._all_cookie_files.append(cf)
            
        # Rate limiting (to avoid triggering IP blocks)
        self.last_request_times = {}  # domain -> timestamp
        self.rate_limit_delay = self.options.get('rate_limit_delay', 2.5)  # seconds between requests

        # Failed URLs tracking (for detailed error reporting)
        self.failed_urls = []  # [(url, reason)]

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
            self.progress.emit(f"âš ï¸ Could not save download record: {str(e)[:50]}")

    def _is_already_downloaded(self, url: str) -> bool:
        """Check if already downloaded (bulk mode only)"""
        if not self.is_bulk_mode:
            return False  # Never skip in single mode

        normalized = normalize_url(url)
        return normalized in self.downloaded_links

    def _load_proxies_from_config(self) -> list:
        """
        Load proxy settings from shared config.

        Returns:
            list: Parsed proxy URLs ready for use.
        """
        try:
            import logging

            proxies = list(self.auth_hub.get_proxy_pool())
            if proxies:
                logging.info(f"âœ… Loaded {len(proxies)} proxy(ies) from shared config")
            else:
                logging.warning("âš ï¸ No proxies found in shared config")
            return proxies
        except Exception as e:
            logging.error(f"âŒ Failed to load proxies from shared config: {e}")
            return []

    def _parse_proxy_format(self, proxy: str) -> str:
        """
        ENHANCED: Parse and convert proxy format to standard format with URL encoding
        Synced with Link Grabber for consistency.

        Supports ALL 5 formats:
        1. ip:port                                    â†’ http://ip:port
        2. user:pass@ip:port                          â†’ http://user:pass@ip:port
        3. ip:port:user:pass (provider format)        â†’ http://user:pass@ip:port
        4. socks5://user:pass@ip:port                 â†’ socks5://user:pass@ip:port
        5. With URL encoding for special chars        â†’ http://user:P%40ss@ip:port

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
                # Unknown format, return empty to skip
                logging.warning(f"âš ï¸ Unknown proxy format (parts={len(parts)}): {proxy[:30]}...")
                return ""

        except Exception as e:
            logging.error(f"âŒ Failed to parse proxy format: {e}")
            return ""

    def _get_current_proxy(self) -> Optional[str]:
        """
        Get current proxy from the pool.

        Returns:
            str: Current proxy URL or None if no proxies available
        """
        if not self.proxies:
            return None

        quarantined = self._quarantined_proxies()
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_proxy_index]
            if proxy not in quarantined:
                return proxy
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return None

    def _rotate_proxy(self):
        """Switch to next proxy in the pool (circular rotation)"""
        if len(self.proxies) > 1:
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            self.progress.emit(f"   ðŸ”„ Switched to proxy {self.current_proxy_index + 1}/{len(self.proxies)}")
            return True
        return False

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
                self.progress.emit(f"   â³ Rate limiting: waiting {wait_time:.1f}s...")
            time.sleep(wait_time)

        self.last_request_times[domain] = time.time()

    # Removed old timestamp logic - now using history.json only

    def _get_ytdlp_command(self):
        """
        Get yt-dlp command with shared resolver and validation.

        Returns:
            str or None: Runnable command path or None for Python API fallback.
        """
        # Cache the result to avoid repeated lookups
        if hasattr(self, '_ytdlp_cmd_cache'):
            return self._ytdlp_cmd_cache

        try:
            resolved = self.auth_hub.resolve_ytdlp()
            cmd = resolved.get("path")

            if cmd and resolved.get("usable"):
                self._ytdlp_cmd_cache = cmd
                return cmd

            if cmd and not resolved.get("usable"):
                self.progress.emit("ERROR: yt-dlp found but not runnable.")
                if resolved.get("error"):
                    self.progress.emit(f"ERROR: {resolved['error']}")
                self.progress.emit("INFO: Install/update yt-dlp at C:\\yt-dlp\\yt-dlp.exe or fix PATH.")

            self._ytdlp_cmd_cache = None
            return None
        except Exception:
            self._ytdlp_cmd_cache = None
            return None

    def _verify_cli(self, cmd: str, args: list) -> bool:
        if not cmd:
            return False
        try:
            result = subprocess.run(
                [cmd] + list(args),
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8',
                errors='replace',
            )
            return result.returncode == 0
        except Exception:
            return False

    def _ffmpeg_cli_args(self) -> list:
        if not self.ffmpeg_path:
            return []
        return ['--ffmpeg-location', self.ffmpeg_path]

    def _apply_ffmpeg_ydl_opts(self, ydl_opts: dict) -> None:
        if not self.ffmpeg_path:
            return
        ydl_opts['ffmpeg_location'] = self.ffmpeg_path

    # ------------------------------------------------------------------
    # Central download verifier
    # ------------------------------------------------------------------
    _JUNK_EXTENSIONS = frozenset({'.part', '.tmp', '.ytdl', '.temp', '.downloading'})
    _VIDEO_EXTENSIONS = frozenset({
        '.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.wmv', '.m4v',
    })
    _AUDIO_EXTENSIONS = frozenset({
        '.mp3', '.m4a', '.ogg', '.opus', '.wav', '.aac', '.flac',
    })
    _IMAGE_EXTENSIONS = frozenset({
        '.jpg', '.jpeg', '.png', '.gif', '.webp',
    })
    _MEDIA_EXTENSIONS = frozenset(
        _VIDEO_EXTENSIONS.union(_AUDIO_EXTENSIONS).union(_IMAGE_EXTENSIONS)
    )
    _MIN_MEDIA_SIZE = 10_000  # 10 KB — anything smaller is almost certainly not a real video

    def _resolve_expected_extensions(self, expected_kind: Optional[str] = None) -> frozenset:
        """Resolve the allowed output extensions for this run."""
        kind = expected_kind
        if kind is None:
            kind = self.options.get('_expected_media_kind')
        kind = str(kind or "").strip().lower()
        if kind == "video":
            return self._VIDEO_EXTENSIONS
        if kind == "audio":
            return self._AUDIO_EXTENSIONS
        if kind in {"av", "video_audio"}:
            return frozenset(self._VIDEO_EXTENSIONS.union(self._AUDIO_EXTENSIONS))
        return self._MEDIA_EXTENSIONS

    def _snapshot_folder(self, folder: str) -> set:
        """Take a recursive snapshot of all files in folder (path → mtime+size)."""
        result = set()
        try:
            for root, _dirs, files in os.walk(folder):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        st = os.stat(fp)
                        result.add((fp, st.st_size, st.st_mtime_ns))
                    except OSError:
                        pass
        except OSError:
            pass
        return result

    def _verify_download(self, folder: str, before: set, tag: str = "",
                         expected_kind: Optional[str] = None) -> list:
        """Compare folder state after download. Return list of new valid media files.

        A file is considered valid if:
          - it did not exist in *before* snapshot (or grew in size)
          - extension is a known media type (not .part / .tmp / .ytdl)
          - size >= _MIN_MEDIA_SIZE
        """
        new_files = []
        expected_extensions = self._resolve_expected_extensions(expected_kind)
        try:
            for root, _dirs, files in os.walk(folder):
                for f in files:
                    fp = os.path.join(root, f)
                    ext = os.path.splitext(f)[1].lower()
                    # Skip junk / incomplete
                    if ext in self._JUNK_EXTENSIONS:
                        continue
                    try:
                        st = os.stat(fp)
                    except OSError:
                        continue
                    # Must be new or changed
                    key = (fp, st.st_size, st.st_mtime_ns)
                    if key in before:
                        continue
                    # Must be a real media file
                    if ext not in expected_extensions:
                        continue
                    if st.st_size < self._MIN_MEDIA_SIZE:
                        continue
                    new_files.append(fp)
        except OSError:
            pass

        if new_files and tag:
            self.progress.emit(f"   {tag} verified: {Path(new_files[0]).name}")
        elif tag:
            self.progress.emit(f"   {tag} no valid media file created")
        return new_files

    def _quarantined_proxies(self) -> set:
        """Return the set of proxy URLs quarantined this session."""
        if not hasattr(self, '_proxy_quarantine'):
            self._proxy_quarantine = set()
        return self._proxy_quarantine

    def _quarantine_proxy(self, proxy: str) -> None:
        """Mark a proxy as dead for the rest of this session."""
        self._quarantined_proxies().add(proxy)
        self.progress.emit(f"   [DL-proxy] quarantined dead proxy")

    def _get_healthy_proxy(self) -> Optional[str]:
        """Get current proxy, skipping quarantined ones. Returns None if all dead."""
        quarantined = self._quarantined_proxies()
        if not self.proxies:
            return None
        # Try from current index forward
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_proxy_index]
            if proxy not in quarantined:
                return proxy
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return None  # All quarantined

    def _download_with_proxy_fallback(self, ydl_opts: dict, url: str,
                                       output_path: str, tag: str) -> bool:
        """Try download with proxy, then without. Verify file creation.

        Returns True only when a valid media file is confirmed on disk.
        """
        before = self._snapshot_folder(output_path)

        # Attempt 1: with healthy proxy
        proxy = self._get_healthy_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy
            self.progress.emit(f"   {tag} proxy: {proxy.split('@')[-1][:25]}")
            try:
                retcode = self._run_ytdlp(ydl_opts, url)
                new_files = self._verify_download(output_path, before, tag)
                if new_files:
                    return True
                # No file created — quarantine proxy (dead or silently failing)
                self._quarantine_proxy(proxy)
            except Exception:
                self._quarantine_proxy(proxy)

        # Attempt 2: without proxy
        ydl_opts.pop('proxy', None)
        self.progress.emit(f"   {tag} retrying without proxy...")
        before = self._snapshot_folder(output_path)  # re-snapshot
        try:
            self._run_ytdlp(ydl_opts, url)
            new_files = self._verify_download(output_path, before, tag)
            if new_files:
                return True
        except Exception:
            pass

        return False

    @staticmethod
    def _run_ytdlp(ydl_opts: dict, url: str) -> int:
        """Run yt-dlp and return its exit code (0 = success)."""
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.download([url])

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
                    self.progress.emit(f"ðŸ§¹ Removed leftover file: {filename}")

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
                        self.progress.emit(f"ðŸ—‘ï¸ Removed from {txt_file.name}")
                except Exception:
                    continue
        except Exception:
            pass

    def get_cookie_file(self, url, source_folder=None):
        """
        Return the most relevant cookie file for a URL.

        Decision order (profile-first):
          1. SessionAuthority: fresh export from persistent browser profile
          2. AuthNetworkHub: existing per-platform cookie files
          3. Generic / legacy fallbacks

        Also stores all valid cookie files in self._all_cookie_files for fallback attempts.
        """
        import logging

        platform = self.auth_hub.detect_platform(url)

        # Step 1: Try SessionAuthority (fresh profile export)
        try:
            from modules.shared.session_authority import get_session_authority
            authority = get_session_authority()
            best = authority.get_best_cookie_file(platform, source_folder)
            if best:
                # Also populate fallback list
                valid_cookies = self.auth_hub.valid_cookie_files(platform, source_folder)
                # Ensure the authority's pick is first
                if best not in valid_cookies:
                    valid_cookies.insert(0, best)
                self._all_cookie_files = valid_cookies
                logging.info(
                    "[VideoDownloader] Cookie for %s: %s (via SessionAuthority)",
                    platform, Path(best).name,
                )
                return best
        except Exception as exc:
            logging.debug("[VideoDownloader] SessionAuthority unavailable: %s", exc)

        # Step 2: Fallback to direct file scan
        try:
            valid_cookies = self.auth_hub.valid_cookie_files(platform, source_folder)
            self._all_cookie_files = valid_cookies
            if valid_cookies:
                logging.info(
                    "[VideoDownloader] Cookie for %s: %s (file scan fallback)",
                    platform, Path(valid_cookies[0]).name,
                )
                return valid_cookies[0]
        except Exception:
            pass

        logging.info("[VideoDownloader] No cookie file found for %s", platform)
        return None

    # -----------------------
    # ==== Download Methods per Platform ====

    def _method1_batch_file_approach(self, url, output_path, cookie_file=None):
        try:
            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] ðŸš€ [DL-1] YT-DLP Standard")

            # Smart yt-dlp detection
            ytdlp_cmd = self._get_ytdlp_command()
            if not ytdlp_cmd:
                self.progress.emit(f"   âš ï¸ yt-dlp not found, skipping command-based method")
                return False

            format_string = self.format_override or 'best'

            # Get user agent (shared pool)
            user_agent = _get_random_user_agent()

            # Get current proxy
            current_proxy = self._get_current_proxy()

            ydl_opts = {
                'outtmpl': os.path.join(output_path, '%(title).80s.%(ext)s'),
                'format': format_string,
                'rm_cachedir': True,
                'restrictfilenames': True,
                'no_warnings': True,
                'retries': self.max_retries,
                'continuedl': True,
                'nocheckcertificate': True,
                'noplaylist': True,
                'progress_hooks': [self._progress_hook],
                'http_headers': {
                    'User-Agent': user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            }
            self._apply_ffmpeg_ydl_opts(ydl_opts)

            # Add proxy if available
            if current_proxy:
                ydl_opts['proxy'] = current_proxy
                self.progress.emit(f"   ðŸŒ Proxy: {current_proxy.split('@')[-1][:20]}...")  # Hide credentials
            else:
                self.progress.emit(f"   âš ï¸ No proxy (IP blocks possible)")

            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file
                self.progress.emit(f"   ðŸª Cookies: {Path(cookie_file).name}")

            self.progress.emit(f"   ðŸŽ­ UA: {user_agent[:45]}...")

            self.progress.emit(f"   Starting download...")

            # Use central verified download with proxy fallback
            if self._download_with_proxy_fallback(ydl_opts, url, output_path, "[DL-1]"):
                elapsed = (datetime.now() - start_time).total_seconds()
                self.progress.emit(f"   SUCCESS in {elapsed:.1f}s")
                return True
            else:
                elapsed = (datetime.now() - start_time).total_seconds()
                self.progress.emit(f"   FAILED ({elapsed:.1f}s)")
                return False
        except Exception as e:
            self.progress.emit(f"   âŒ Exception: {str(e)[:100]}")
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
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] ðŸŽµ [DL-2] TikTok Enhanced (Multi-Strategy)")

            # Apply rate limiting
            self._apply_rate_limit('tiktok.com')

            # UPDATED: Modern TikTok formats (2025) - old format IDs removed
            # Old 'http-264-hd-1' and 'http-264-hd-0' no longer work with new TikTok API
            tiktok_formats = [
                ('best[ext=mp4]/best', 'ðŸŽ¥ Best MP4'),
                ('bestvideo+bestaudio/best', 'ðŸŽ¬ Best Quality'),
                ('best', 'âœ¨ Best Available'),
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
            self.progress.emit(f"   ðŸ“¥ Strategy 1: Direct download")
            result = self._try_tiktok_download(url, output_path, cookie_files_to_try,
                                               tiktok_formats, use_proxy=False, retry_count=0)
            if result['success']:
                elapsed = (datetime.now() - start_time).total_seconds()
                self.progress.emit(f"   âœ… SUCCESS ({elapsed:.1f}s) {result['message']}")
                return True

            # Check if IP blocked
            ip_blocked = result.get('ip_blocked', False)

            # STRATEGY 2: Try with proxy (if available and IP blocked)
            # Prefer proxy pool first; fall back to legacy self.proxy_url.
            proxy_available = bool(self._get_current_proxy() or self.proxy_url)
            if ip_blocked and proxy_available:
                self.progress.emit(f"   ðŸŒ Strategy 2: Trying with proxy (IP block detected)")
                time.sleep(2)  # Brief delay before retry

                result = self._try_tiktok_download(url, output_path, cookie_files_to_try,
                                                   tiktok_formats, use_proxy=True, retry_count=0)
                if result['success']:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    self.progress.emit(f"   âœ… SUCCESS via proxy ({elapsed:.1f}s) {result['message']}")
                    return True
                # Rotate proxy pool for the remaining attempts (best-effort)
                if self._rotate_proxy():
                    self.progress.emit("   ðŸ”„ Rotating proxy for retries...")

            # STRATEGY 3: Retry with exponential backoff (if IP blocked)
            if ip_blocked:
                self.progress.emit(f"   ðŸ”„ Strategy 3: Retry with exponential backoff")

                for retry_attempt in range(2):  # Try 2 more times
                    wait_time = 2 ** (retry_attempt + 1)  # 2s, 4s
                    self.progress.emit(f"   â³ Waiting {wait_time}s before retry {retry_attempt + 1}/2...")
                    time.sleep(wait_time)

                    # Try with enhanced headers and random user agent
                    # Retry with proxy if we have any proxy source.
                    retry_use_proxy = bool(self._get_current_proxy() or self.proxy_url)
                    result = self._try_tiktok_download(url, output_path, cookie_files_to_try,
                                                       tiktok_formats, use_proxy=retry_use_proxy,
                                                       retry_count=retry_attempt + 1)
                    if result['success']:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        self.progress.emit(f"   âœ… SUCCESS on retry {retry_attempt + 1} ({elapsed:.1f}s) {result['message']}")
                        return True

            # ALL STRATEGIES FAILED
            elapsed = (datetime.now() - start_time).total_seconds()
            self.progress.emit(f"   âŒ All strategies failed ({elapsed:.1f}s)")

            # Show specific error message
            if ip_blocked:
                self._show_tiktok_ip_block_help()
            else:
                self.progress.emit(f"   ðŸ’¡ Tips:")
                self.progress.emit(f"      â€¢ Make sure cookies/tiktok.txt exists")
                self.progress.emit(f"      â€¢ Video might be private or age-restricted")
                self.progress.emit(f"      â€¢ Try adding TikTok cookies (same as Link Grabber)")

            return False

        except Exception as e:
            self.progress.emit(f"   âŒ TikTok error: {str(e)[:100]}")
            return False

    def _try_tiktok_download(self, url, output_path, cookie_files, formats, use_proxy=False, retry_count=0):
        """
        Try TikTok download with given configuration
        Returns: {'success': bool, 'message': str, 'ip_blocked': bool}
        """
        # Smart yt-dlp detection
        ytdlp_cmd = self._get_ytdlp_command()
        if not ytdlp_cmd:
            return {
                'success': False,
                'message': 'yt-dlp command not found',
                'ip_blocked': False
            }

        last_error = ""
        ip_blocked = False

        for cookie_attempt_idx, current_cookie in enumerate(cookie_files, 1):
            if cookie_attempt_idx > 1:
                self.progress.emit(f"   ðŸ”„ Cookie {cookie_attempt_idx}/{len(cookie_files)}")
                if current_cookie:
                    self.progress.emit(f"   ðŸª Using: {Path(current_cookie).name}")

            for i, (fmt, desc) in enumerate(formats, 1):
                try:
                    # Only show format on first attempt to reduce noise
                    if retry_count == 0 and cookie_attempt_idx == 1:
                        self.progress.emit(f"   ðŸ”„ Format {i}/{len(formats)}: {desc}")

                    # Build command with enhanced headers
                    user_agent = _get_random_user_agent()

                    cmd = [
                        ytdlp_cmd,  # Use detected command
                        '-o', os.path.join(output_path, '%(title).80s.%(ext)s'),
                        '-f', fmt,
                        '--no-playlist',
                        '--geo-bypass',
                        '--user-agent', user_agent,
                        '--restrict-filenames',
                        '--no-warnings',
                        '--retries', str(self.max_retries),
                    ]

                    # ENHANCED: Add realistic Chrome 120 headers + TikTok-specific referer
                    cmd.extend(_get_chrome120_headers())
                    cmd.extend(self._ffmpeg_cli_args())
                    cmd.extend(['--add-header', 'Referer:https://www.tiktok.com/'])

                    # Add proxy if requested.
                    # Prefer proxy pool; fall back to legacy proxy_url/env proxy.
                    if use_proxy:
                        proxy = self._get_current_proxy() or self.proxy_url
                        if proxy:
                            cmd.extend(['--proxy', proxy])

                    if current_cookie:
                        cmd.extend(['--cookies', current_cookie])

                    cmd.append(url)

                    result = subprocess.run(cmd, capture_output=True, text=True,
                                          timeout=300, encoding='utf-8', errors='replace')

                    if result.returncode == 0:
                        watermark_status = "ðŸŽ‰ NO WATERMARK!" if "hd-1" in fmt else ""
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
                            self.progress.emit(f"   âŒ Error: {error_snippet}")

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
        self.progress.emit("   â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—")
        self.progress.emit("   â•‘  ðŸš« TIKTOK IP BLOCK DETECTED                  â•‘")
        self.progress.emit("   â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•")
        self.progress.emit("")
        self.progress.emit("   ðŸ”§ SOLUTIONS:")
        self.progress.emit("")
        self.progress.emit("   1ï¸âƒ£ Use VPN or Proxy:")
        self.progress.emit("      â€¢ Enable VPN on your computer")
        self.progress.emit("      â€¢ Or set proxy: export HTTPS_PROXY=socks5://127.0.0.1:1080")
        self.progress.emit("      â€¢ Try different proxy location")
        self.progress.emit("")
        self.progress.emit("   2ï¸âƒ£ Wait and Retry:")
        self.progress.emit("      â€¢ TikTok may have rate-limited your IP")
        self.progress.emit("      â€¢ Wait 15-60 minutes and try again")
        self.progress.emit("      â€¢ Temporary blocks usually expire")
        self.progress.emit("")
        self.progress.emit("   3ï¸âƒ£ Check Video Availability:")
        self.progress.emit("      â€¢ Video might be private/deleted")
        self.progress.emit("      â€¢ Try opening in browser first")
        self.progress.emit("      â€¢ Check if region-locked")
        self.progress.emit("")
        self.progress.emit("   ðŸ’¡ Quick fix: Switch to different network (WiFi â†” Mobile data)")
        self.progress.emit("")

    def _method3_optimized_ytdlp(self, url, output_path, cookie_file=None):
        try:
            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] ðŸ”„ [DL-3] yt-dlp with Cookies")

            # Get user agent and proxy
            user_agent = _get_random_user_agent()
            current_proxy = self._get_current_proxy()

            format_string = self.format_override or 'best'
            ydl_opts = {
                'outtmpl': os.path.join(output_path, '%(title).80s.%(ext)s'),
                'format': format_string,
                'quiet': True,
                'no_warnings': True,
                'retries': self.max_retries,
                'fragment_retries': self.max_retries,
                'continuedl': True,
                'nocheckcertificate': True,
                'restrictfilenames': True,
                'progress_hooks': [self._progress_hook],
                'http_headers': {'User-Agent': user_agent},  # UA rotation
            }
            self._apply_ffmpeg_ydl_opts(ydl_opts)

            # Add proxy if available
            if current_proxy:
                ydl_opts['proxy'] = current_proxy
                self.progress.emit(f"   ðŸŒ Proxy: {current_proxy.split('@')[-1][:20]}...")
            else:
                self.progress.emit(f"   âš ï¸ No proxy (IP blocks possible)")

            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file
                cf_path = Path(cookie_file)
                source_tag = " [Profile]" if "_chromium_profile" in cf_path.name else " [Manual/Auth]"
                self.progress.emit(f"   ðŸ ª Cookies: {cf_path.name}{source_tag}")
            else:
                self.progress.emit(f"   âš ï¸  No cookies (may fail for private content)")

            self.progress.emit(f"   ðŸŽ­ UA: {user_agent[:45]}...")

            # Use central verified download with proxy fallback
            if self._download_with_proxy_fallback(ydl_opts, url, output_path, "[DL-3]"):
                elapsed = (datetime.now() - start_time).total_seconds()
                self.progress.emit(f"   SUCCESS in {elapsed:.1f}s")
                return True
            else:
                elapsed = (datetime.now() - start_time).total_seconds()
                self.progress.emit(f"   FAILED ({elapsed:.1f}s)")
                return False

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0
            error_msg = str(e)
            self.progress.emit(f"   âŒ FAILED ({elapsed:.1f}s)")

            # Give specific hints based on error
            if 'login required' in error_msg.lower() or 'rate' in error_msg.lower():
                self.progress.emit(f"   ðŸ’¡ Hint: Need cookies for this content")
            elif 'private' in error_msg.lower():
                self.progress.emit(f"   ðŸ’¡ Hint: Content is private")

            self.progress.emit(f"   ðŸ“ Error: {error_msg[:200]}")
            return False

    def _method_instagram_enhanced(self, url, output_path, cookie_file=None):
        """Enhanced Instagram downloader with cookie validation and multiple fallbacks"""
        try:
            if 'instagram.com' not in url.lower():
                return False

            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] ðŸ“¸ [DL-7] Instagram Enhanced Method")

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
            self.progress.emit(f"   ðŸª Found {total_cookies} cookie file(s) to try")

            # Try each cookie file
            for cookie_idx, current_cookie_file in enumerate(cookie_files_to_try, 1):
                if cookie_idx > 1:
                    self.progress.emit(f"   ðŸ”„ Trying alternate cookie file ({cookie_idx}/{total_cookies})")

                self.progress.emit(f"   ðŸª Using: {Path(current_cookie_file).name}")

                # Validate cookie
                cookie_is_valid = False
                validator = InstagramCookieValidator()
                validation = validator.validate_cookie_file(current_cookie_file)

                if validation['is_valid']:
                    self.progress.emit(f"   ðŸ”‘ Valid Instagram cookies!")
                    cookie_is_valid = True
                else:
                    self.progress.emit(f"   âš ï¸ Cookie validation failed:")
                    for error in validation['errors'][:1]:  # Show first error only
                        self.progress.emit(f"      â€¢ {error}")

                    if validation['is_expired']:
                        self.progress.emit(f"   ðŸ’¡ Cookies expired - trying next...")
                    elif not validation['has_sessionid']:
                        self.progress.emit(f"   ðŸ’¡ No sessionid found - trying next...")

                    # Try next cookie if validation failed
                    continue

                # Try download with validated cookie
                self.progress.emit(f"   ðŸ“¥ Attempting download...")

                # Smart yt-dlp detection
                ytdlp_cmd = self._get_ytdlp_command()
                if not ytdlp_cmd:
                    self.progress.emit(f"   âš ï¸ yt-dlp not found, skipping")
                    continue

                # Get UA and proxy
                user_agent = _get_random_user_agent()
                current_proxy = self._get_current_proxy()

                ydl_opts = {
                    'outtmpl': os.path.join(output_path, '%(title).80s.%(ext)s'),
                    'cookiefile': current_cookie_file,
                    'format': 'best',
                    'quiet': True,
                    'no_warnings': True,
                    'restrictfilenames': True,
                    'progress_hooks': [self._progress_hook],
                    'http_headers': {
                        'User-Agent': user_agent,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }
                }
                self._apply_ffmpeg_ydl_opts(ydl_opts)
                if current_proxy:
                    ydl_opts['proxy'] = current_proxy
                    self.progress.emit(f"   ðŸŒ  Proxy: {current_proxy.split('@')[-1][:20]}...")

                self.progress.emit(f"   ðŸŽ­ UA: {user_agent[:45]}...")

                # Use central verified download with proxy fallback
                if self._download_with_proxy_fallback(ydl_opts, url, output_path, "[DL-7]"):
                    elapsed = (datetime.now() - start_time).total_seconds()
                    self.progress.emit(f"   [DL-7] success ({elapsed:.1f}s)")
                    return True
                else:
                    self.progress.emit(f"   [DL-7] fail: no file with this cookie")

            # If all cookie files failed, show helpful error message
            elapsed = (datetime.now() - start_time).total_seconds()
            self.progress.emit(f"   âŒ All cookie attempts failed ({elapsed:.1f}s)")
            self.progress.emit(f"   ")
            self.progress.emit(f"   â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—")
            self.progress.emit(f"   â•‘  ðŸ“¸ INSTAGRAM AUTHENTICATION REQUIRED         â•‘")
            self.progress.emit(f"   â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•")
            self.progress.emit(f"   ")
            self.progress.emit(f"   ðŸ”§ QUICK FIX:")
            self.progress.emit(f"   ")
            self.progress.emit(f"   1ï¸âƒ£ Same cookies work for Link Grabber & Downloader!")
            self.progress.emit(f"      â€¢ If Link Grabber works, Downloader will too")
            self.progress.emit(f"      â€¢ Export cookies to: cookies/instagram.txt")
            self.progress.emit(f"   ")
            self.progress.emit(f"   2ï¸âƒ£ How to export cookies:")
            self.progress.emit(f"      a) Install browser extension:")
            self.progress.emit(f"         'Get cookies.txt LOCALLY'")
            self.progress.emit(f"      b) Login to Instagram in browser")
            self.progress.emit(f"      c) Click extension â†’ Export")
            self.progress.emit(f"      d) Save as: cookies/instagram.txt")
            self.progress.emit(f"   ")
            self.progress.emit(f"   3ï¸âƒ£ Make sure:")
            self.progress.emit(f"      â€¢ You're logged into Instagram in browser")
            self.progress.emit(f"      â€¢ Cookies are NOT expired (< 30 days old)")
            self.progress.emit(f"      â€¢ File contains 'sessionid' cookie")
            self.progress.emit(f"   ")
            self.progress.emit(f"   ðŸ’¡ Checked {total_cookies} cookie file(s) - all invalid/expired")
            self.progress.emit(f"   ")
            return False

        except Exception as e:
            self.progress.emit(f"   âŒ Instagram enhanced error: {str(e)[:100]}")
            return False


    def _method_facebook_enhanced(self, url, output_path, cookie_file=None):
        """
        Robust Facebook download strategy:
        1. Try with primary cookie file
        2. Fallback to all other valid cookie files
        3. Rotating User Agents and headers
        """
        try:
            if 'facebook.com' not in url.lower() and 'fb.com' not in url.lower():
                return False

            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] ðŸ“¦ [DL-8] Facebook Enhanced Strategy")

            # Collect candidates
            cookie_files = []
            if cookie_file:
                cookie_files.append(cookie_file)
            
            # Add all known valid cookies from the hub
            if hasattr(self, '_all_cookie_files'):
                for cf in self._all_cookie_files:
                    if cf and cf not in cookie_files:
                        cookie_files.append(cf)
            
            # Deduplicate while preserving order
            seen = set()
            unique_cookies = []
            for cf in cookie_files:
                if cf not in seen:
                    seen.add(cf)
                    unique_cookies.append(cf)
            
            if not unique_cookies:
                unique_cookies = [None]

            total_cookies = len([c for c in unique_cookies if c])
            self.progress.emit(f"   ðŸ”  Found {total_cookies} cookie candidate(s)")

            for idx, current_cookie_file in enumerate(unique_cookies, 1):
                if self.cancelled: return False

                user_agent = _get_random_user_agent()
                current_proxy = self._get_current_proxy()
                
                # Simplified but robust opts
                ydl_opts = {
                    'outtmpl': os.path.join(output_path, '%(title).80s.%(ext)s'),
                    'format': self.format_override or 'best',
                    'quiet': True,
                    'no_warnings': True,
                    'retries': self.max_retries,
                    'continuedl': True,
                    'nocheckcertificate': True,
                    'restrictfilenames': True,
                    'progress_hooks': [self._progress_hook],
                    'http_headers': {
                        'User-Agent': user_agent,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }
                }
                
                if current_cookie_file:
                    ydl_opts['cookiefile'] = current_cookie_file
                    self.progress.emit(f"   ðŸ ª Attempt {idx}: {Path(current_cookie_file).name}")
                else:
                    self.progress.emit(f"   âš ï¸  Attempt {idx}: No cookies")

                if current_proxy:
                    ydl_opts['proxy'] = current_proxy

                self._apply_ffmpeg_ydl_opts(ydl_opts)

                # Use central verified download with proxy fallback
                if self._download_with_proxy_fallback(ydl_opts, url, output_path, "[DL-8]"):
                    elapsed = (datetime.now() - start_time).total_seconds()
                    self.progress.emit(f"   Facebook Success ({elapsed:.1f}s)")
                    return True
                else:
                    self.progress.emit(f"   [DL-8] Attempt {idx} failed: no verified file")
                    continue

            return False

        except Exception as e:
            self.progress.emit(f"   â Œ Facebook error: {str(e)[:100]}")
            return False

    def _method_instaloader(self, url, output_path, cookie_file=None):
        try:
            if 'instagram.com' not in url.lower():
                return False
            try:
                import instaloader
            except ImportError:
                self.progress.emit("âš ï¸ Instaloader not installed; skipping fallback")
                return False

            self.progress.emit("ðŸ“¸ [DL-10] Instaloader fallback")
            match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)", url, re.IGNORECASE)
            if not match:
                self.progress.emit("âš ï¸ Could not detect Instagram shortcode for Instaloader")
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
                    self.progress.emit(f"âš ï¸ Instaloader cookie load failed: {str(cookie_error)[:60]}")

            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            target = post.owner_username or "instagram"
            loader.download_post(post, target=target)
            self.progress.emit("âœ… Instaloader SUCCESS")
            return True
        except Exception as e:
            self.progress.emit(f"âš ï¸ Instaloader error: {str(e)[:100]}")
            return False

    def _method_gallery_dl(self, url, output_path, cookie_file=None):
        """gallery-dl fallback for Instagram, Twitter, etc."""
        try:
            self.progress.emit("ðŸ–¼ï¸ [DL-9] gallery-dl fallback")
            cmd = [
                'gallery-dl',
                '--dest', output_path,
                '--filename', '{title}_{id}.{extension}',
                '--no-mtime',
            ]

            if cookie_file:
                cmd.extend(['--cookies', cookie_file])
                self.progress.emit(f"ðŸª Using cookies: {Path(cookie_file).name}")

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
                self.progress.emit("âœ… gallery-dl SUCCESS!")
                return True
            else:
                error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                self.progress.emit(f"âš ï¸ gallery-dl failed: {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            self.progress.emit("âš ï¸ gallery-dl timeout")
            return False
        except FileNotFoundError:
            self.progress.emit("âš ï¸ gallery-dl not installed")
            return False
        except Exception as e:
            self.progress.emit(f"âš ï¸ gallery-dl error: {str(e)[:100]}")
            return False

    def _method6_youtube_dl_fallback(self, url, output_path, cookie_file=None):
        """youtube-dl as final fallback (older but sometimes works)"""
        try:
            self.progress.emit("ðŸ”„ [DL-6] youtube-dl fallback (legacy)")
            format_string = self.format_override or 'best'
            cmd = [
                'youtube-dl',
                '-o', os.path.join(output_path, '%(title).80s.%(ext)s'),
                '-f', format_string,
                '--no-warnings',
                '--retries', str(self.max_retries),
                '--continue',
                '--no-check-certificate'
            ]
            cmd.extend(self._ffmpeg_cli_args())

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
                self.progress.emit("âœ… youtube-dl SUCCESS!")
                return True
            else:
                self.progress.emit("âš ï¸ youtube-dl failed")
                return False

        except subprocess.TimeoutExpired:
            self.progress.emit("âš ï¸ youtube-dl timeout")
            return False
        except FileNotFoundError:
            self.progress.emit("âš ï¸ youtube-dl not installed")
            return False
        except Exception as e:
            self.progress.emit(f"âš ï¸ youtube-dl error: {str(e)[:100]}")
            return False

    def _method_youtube_smart(self, url, output_path, cookie_file=None):
        """
        YouTube-optimized download.
        Key insight: android_vr/ios clients do NOT support cookies (yt-dlp skips them
        and falls back to web which has PO-token issues). Must call them cookie-free.
        """
        try:
            from datetime import datetime
            start_time = datetime.now()
            self.progress.emit(f"[{start_time.strftime('%H:%M:%S')}] [DL-11] YouTube Smart Download")

            user_agent = _get_random_user_agent()
            is_shorts = '/shorts/' in url.lower()

            user_fmt = self.format_override if self.format_override else None
            time_budget_sec = float(self.youtube_time_budget_sec or 0)
            max_attempts = int(self.youtube_max_attempts or 0)
            attempt_count = 0

            # Clients and whether they accept cookies
            # android_vr/ios: yt-dlp silently skips them when cookies are passed
            # -> must be used without cookies
            if is_shorts:
                client_cookie_pairs = [
                    ('android_vr', None),          # best for Shorts, no cookies
                    ('ios',        None),          # fallback mobile, no cookies
                    ('web',        cookie_file),   # web supports cookies
                    ('android',    None),          # android no cookies
                    ('web',        None),          # web anonymous last
                ]
            else:
                client_cookie_pairs = [
                    ('web',        cookie_file),   # web + cookies (most compatible)
                    ('android_vr', None),          # android_vr no cookies
                    ('ios',        None),          # ios no cookies
                    ('android',    None),          # android no cookies
                    ('web',        None),          # web anonymous last
                ]
            # Deduplicate
            seen_cc = set()
            unique_pairs = []
            for cc in client_cookie_pairs:
                key = (cc[0], cc[1] or '')
                if key not in seen_cc:
                    seen_cc.add(key)
                    unique_pairs.append(cc)

            def _build_fmts():
                fmts = []
                if user_fmt:
                    fmts.append(user_fmt)
                fmts.append(None)                       # yt-dlp picks best
                fmts.append('bestvideo+bestaudio/best') # no ext restriction
                fmts.append('best')
                seen = set()
                result = []
                for f in fmts:
                    k = f or '__default__'
                    if k not in seen:
                        seen.add(k)
                        result.append(f)
                return result

            def _try_yt(fmt, client, cookie, use_proxy):
                class SilentLogger:
                    def debug(self, msg): pass
                    def warning(self, msg): pass
                    def error(self, msg): pass

                ydl_opts = {
                    'outtmpl': os.path.join(output_path, '%(title).80s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'logger': SilentLogger(),
                    'retries': self.max_retries,
                    'fragment_retries': self.max_retries,
                    'continuedl': True,
                    'nocheckcertificate': True,
                    'restrictfilenames': True,
                    'progress_hooks': [self._progress_hook],
                    'http_headers': {'User-Agent': user_agent},
                    'extractor_args': {'youtube': {'player_client': [client]}},
                }
                if fmt:
                    ydl_opts['format'] = fmt
                if cookie:
                    ydl_opts['cookiefile'] = cookie
                self._apply_ffmpeg_ydl_opts(ydl_opts)
                if use_proxy:
                    proxy = self._get_current_proxy()
                    if proxy:
                        ydl_opts['proxy'] = proxy
                return self._run_ytdlp(ydl_opts, url) == 0

            def _run_strategy(label, use_proxy):
                nonlocal attempt_count
                if use_proxy:
                    proxy_info = self._get_current_proxy()
                    self.progress.emit(f"   [YT] {label} | proxy: {proxy_info.split('@')[-1][:20] if proxy_info else 'none'}")
                else:
                    self.progress.emit(f"   [YT] {label} | direct")

                fmts = _build_fmts()
                for client, cookie in unique_pairs:
                    if self.cancelled:
                        return False
                    if time_budget_sec > 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        if elapsed >= time_budget_sec:
                            self.progress.emit(f"   [YT] Budget hit ({elapsed:.1f}s/{time_budget_sec:.0f}s), stopping smart loop")
                            return False
                    cookie_label = Path(cookie).name if cookie else 'no-cookie'
                    for fmt in fmts:
                        if self.cancelled:
                            return False
                        if time_budget_sec > 0:
                            elapsed = (datetime.now() - start_time).total_seconds()
                            if elapsed >= time_budget_sec:
                                self.progress.emit(f"   [YT] Budget hit ({elapsed:.1f}s/{time_budget_sec:.0f}s), stopping smart loop")
                                return False
                        if max_attempts > 0 and attempt_count >= max_attempts:
                            self.progress.emit(f"   [YT] Attempt cap hit ({attempt_count}/{max_attempts}), stopping smart loop")
                            return False
                        fmt_label = fmt if fmt else '(default)'
                        self.progress.emit(f"   [YT] {client} / {cookie_label} / {fmt_label[:40]}")
                        try:
                            attempt_count += 1
                            if _try_yt(fmt, client, cookie, use_proxy):
                                elapsed = (datetime.now() - start_time).total_seconds()
                                self.progress.emit(f"   [YT] SUCCESS in {elapsed:.1f}s  [{client}/{cookie_label}]")
                                return True
                        except Exception as e:
                            err = str(e).lower()
                            if 'requested format is not available' in err:
                                continue        # try next format for this client
                            elif 'only images are available' in err:
                                self.progress.emit("   [YT] No video in this URL (images only)")
                                return False
                            elif any(x in err for x in ('failed to extract any player response',
                                                         'no video formats found')):
                                self.progress.emit(f"   [YT] {client}: player blocked, skip")
                                break           # this client blocked, try next
                            elif any(x in err for x in ('sign in', 'login required',
                                                         'private', 'join this channel')):
                                self.progress.emit(f"   [YT] Login required")
                                return False
                            else:
                                self.progress.emit(f"   [YT] {client}: {str(e)[:80]}")
                                break           # unknown error, try next client
                return False

            if _run_strategy("Strategy 1: Direct", use_proxy=False):
                return True

            if self.cancelled:
                return False

            current_proxy = self._get_current_proxy()
            if current_proxy:
                if _run_strategy("Strategy 2: Via proxy", use_proxy=True):
                    return True

            elapsed = (datetime.now() - start_time).total_seconds()
            self.progress.emit(f"   [YT] FAILED ({elapsed:.1f}s)")
            self.progress.emit("   [YT] Hint: refresh cookies or run: yt-dlp -U")
            return False

        except Exception as e:
            self.progress.emit(f"   [YT] error: {str(e)[:120]}")
            return False

    def _method4_alternative_formats(self, url, output_path, cookie_file=None):
        try:
            self.progress.emit("[DL-4] Alternative formats")

            # Get UA and proxy once for this method
            user_agent = _get_random_user_agent()
            current_proxy = self._get_current_proxy()

            if current_proxy:
                self.progress.emit(f"   ðŸŒ Proxy: {current_proxy.split('@')[-1][:20]}...")
            else:
                self.progress.emit(f"   âš ï¸ No proxy (IP blocks possible)")
            self.progress.emit(f"   ðŸŽ­ UA: {user_agent[:45]}...")

            format_options = [
                'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'best[ext=mp4]',
                'best',
            ]
            if self.format_override and self.format_override not in format_options:
                format_options.insert(0, self.format_override)
            elif self.format_override:
                # Prioritize selected format
                format_options.remove(self.format_override)
                format_options.insert(0, self.format_override)
            for fmt in format_options:
                try:
                    class SilentLogger:
                        def debug(self, msg): pass
                        def warning(self, msg): pass
                        def error(self, msg): pass

                    ydl_opts = {
                        'outtmpl': os.path.join(output_path, '%(title).80s.%(ext)s'),
                        'format': fmt,
                        'quiet': True, 'no_warnings': True, 'logger': SilentLogger(), 'retries': self.max_retries,
                        'continuedl': True, 'nocheckcertificate': True, 'restrictfilenames': True,
                        'http_headers': {'User-Agent': user_agent},
                    }
                    if current_proxy:
                        ydl_opts['proxy'] = current_proxy
                    if cookie_file: ydl_opts['cookiefile'] = cookie_file
                    self._apply_ffmpeg_ydl_opts(ydl_opts)
                    # Use central verified download with proxy fallback
                    if self._download_with_proxy_fallback(ydl_opts, url, output_path, "[DL-4]"):
                        self.progress.emit(f"Method 4 SUCCESS (format: {fmt})")
                        return True
                except Exception:
                    continue
            self.progress.emit("âš ï¸ Method 4 failed")
            return False
        except Exception as e:
            self.progress.emit(f"âš ï¸ Method 4 error: {str(e)[:100]}")
            return False

    def _method5_force_ipv4(self, url, output_path, cookie_file=None):
        try:
            self.progress.emit("ðŸ”„ [DL-5] Force IPv4 fallback")

            # Smart yt-dlp detection
            ytdlp_cmd = self._get_ytdlp_command()
            if not ytdlp_cmd:
                self.progress.emit(f"   âš ï¸ yt-dlp not found, skipping")
                return False

            # Get UA and proxy
            user_agent = _get_random_user_agent()
            current_proxy = self._get_current_proxy()

            format_string = self.format_override or 'best'
            cmd = [
                ytdlp_cmd,  # Use detected command
                '-o', os.path.join(output_path, '%(title).80s.%(ext)s'),
                '-f', format_string,
                '--force-ipv4', '--no-warnings', '--geo-bypass',
                '--retries', str(self.max_retries), '--ignore-errors', '--continue',
                '--restrict-filenames', '--no-check-certificate',
                '--user-agent', user_agent,
            ]

            # ENHANCED: Add realistic Chrome 120 headers to avoid detection
            cmd.extend(_get_chrome120_headers())
            cmd.extend(self._ffmpeg_cli_args())

            # Add proxy
            if current_proxy:
                cmd.extend(['--proxy', current_proxy])
                self.progress.emit(f"   ðŸŒ Proxy: {current_proxy.split('@')[-1][:20]}...")
            else:
                self.progress.emit(f"   âš ï¸ No proxy (IP blocks possible)")

            if cookie_file:
                cmd.extend(['--cookies', cookie_file])
                self.progress.emit(f"   ðŸª Cookies: {Path(cookie_file).name}")

            self.progress.emit(f"   ðŸŽ­ UA: {user_agent[:45]}...")
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
                self.progress.emit("âœ… Method 5 SUCCESS!")
                return True
            error_msg = result.stderr[:200] if result.stderr else "Unknown error"
            self.progress.emit(f"âš ï¸ Method 5 failed: {error_msg}")
            return False
        except subprocess.TimeoutExpired:
            self.progress.emit("âš ï¸ Method 5 timeout")
            return False
        except Exception as e:
            self.progress.emit(f"âš ï¸ Method 5 error: {str(e)[:100]}")
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
                self.finished.emit(False, "âŒ No URLs provided")
                return
            total = len(self.urls)
            ytdlp_cmd = self._get_ytdlp_command()
            if not ytdlp_cmd:
                self.progress.emit("ERROR: yt-dlp not found; using Python API fallback.")
            if self.ffmpeg_path and not self._verify_cli(self.ffmpeg_path, ['-version']):
                self.progress.emit("ERROR: ffmpeg found but not runnable. Check installation.")
                self.ffmpeg_path = None
                if self.format_override and not self._format_fallback_applied:
                    if 'bestvideo' in self.format_override or '+' in self.format_override:
                        self.format_override = 'best[ext=mp4]/best'
                        self._format_fallback_applied = True
            if not self.ffmpeg_path:
                self.progress.emit("ERROR: ffmpeg not found; audio/video may download separately.")
            if self._format_fallback_applied:
                self.progress.emit("WARNING: ffmpeg missing; using single-file format (lower quality).")

            # Show mode clearly
            mode_name = "ðŸ”¹ BULK MODE" if self.is_bulk_mode else "ðŸ”¸ SINGLE MODE"
            self.progress.emit("="*60)
            self.progress.emit(f"ðŸš€ SMART DOWNLOADER STARTING - {mode_name}")
            self.progress.emit(f"ðŸ“Š Total links: {total}")

            if self.is_bulk_mode:
                self.progress.emit(f"ðŸ“‚ Creators: {len(self.bulk_creators)}")
                self.progress.emit("âœ… History tracking: ON")
                self.progress.emit("âœ… Auto URL cleanup: ON")
                self.progress.emit(f"ðŸ“ Track file: {self.downloaded_links_file.name}")
            else:
                self.progress.emit("ðŸ“ Save: Desktop/Toseeq Downloads")
                self.progress.emit("âš¡ Simple mode: No tracking, no extra files")
                self.progress.emit("ðŸš« File creation: DISABLED")
                # Clean up any leftover tracking files from old runs
                self._cleanup_tracking_files(self.save_path)

            # Show proxy status
            if self.proxies:
                self.progress.emit(f"ðŸŒ Proxies loaded: {len(self.proxies)}")
                for idx, proxy in enumerate(self.proxies, 1):
                    proxy_display = proxy.split('@')[-1][:25] if '@' in proxy else proxy[:25]
                    self.progress.emit(f"   Proxy {idx}: {proxy_display}...")
            else:
                self.progress.emit("âš ï¸ WARNING: No proxies configured - IP blocks possible!")
                self.progress.emit("   ðŸ’¡ Add proxies in Link Grabber for better success rate")

            self.progress.emit("="*60)
            if self.force_all_methods:
                self.progress.emit("ðŸ›¡ï¸ Multi-strategy fallback enabled")
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
                    self.progress.emit(f"â­ï¸ [{processed}/{total}] Already downloaded, skipping...")
                    self.skipped_count += 1
                    continue
                self.progress.emit(f"\nðŸ“¥ [{processed}/{total}] {url[:80]}...")
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
                elif platform == 'youtube':
                    methods = [
                        self._method_youtube_smart,          # No-proxy first + smart format fallback
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method4_alternative_formats,
                        self._method5_force_ipv4,
                        self._method6_youtube_dl_fallback,
                    ]
                elif platform == 'facebook':
                    methods = [
                        self._method_facebook_enhanced,
                        self._method1_batch_file_approach,
                        self._method3_optimized_ytdlp,
                        self._method4_alternative_formats,
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
                    # Limit to first 3-4 methods for speed (but will try all if they fail)
                    methods = methods[:4]

                # Resolve creator for strategy memory
                _creator = ""
                _meta = self._url_meta.get(url, {})
                if _meta.get('creator'):
                    _creator = _meta['creator']
                elif self.options.get('_creator_hint'):
                    _creator = self.options['_creator_hint']
                else:
                    _creator = _extract_creator_from_url(url)

                # Strategy memory: reorder methods if we have learning data
                try:
                    from modules.link_grabber.intelligence import get_learning_system
                    _ls = get_learning_system()
                    _best_dl = _ls.get_best_download_method(_creator, platform)
                    if _best_dl:
                        _method_ids = {m.__name__: m for m in methods}
                        if _best_dl in _method_ids:
                            _best_m = _method_ids[_best_dl]
                            methods = [_best_m] + [m for m in methods if m is not _best_m]
                except Exception:
                    pass

                # Stable method-name → number mapping for debug logs.
                _DL_NUM = {
                    "_method1_batch_file_approach": 1,
                    "_method2_tiktok_special":      2,
                    "_method3_optimized_ytdlp":     3,
                    "_method4_alternative_formats":  4,
                    "_method5_force_ipv4":           5,
                    "_method6_youtube_dl_fallback":  6,
                    "_method_instagram_enhanced":    7,
                    "_method_facebook_enhanced":     8,
                    "_method_gallery_dl":            9,
                    "_method_instaloader":          10,
                    "_method_youtube_smart":        11,
                }

                # Try all methods until one succeeds
                success = False
                attempted_methods = 0
                last_dl_error = ""
                expected_media_kind = str(self.options.get('_expected_media_kind') or "").strip().lower() or None
                for _m_idx, method in enumerate(methods):
                    if self.cancelled: break
                    attempted_methods += 1
                    _dl_tag = f"[DL-{_DL_NUM.get(method.__name__, '?')}]"
                    _dl_start = time.time()
                    method_error = ""
                    try:
                        method_before = self._snapshot_folder(folder)
                        method_ok = bool(method(url, folder, cookie_file))
                        verified_files = self._verify_download(
                            folder, method_before, expected_kind=expected_media_kind,
                        )
                        if verified_files:
                            success = True
                            try:
                                verified_path = max(
                                    verified_files,
                                    key=lambda fp: os.stat(fp).st_mtime_ns,
                                )
                            except OSError:
                                verified_path = verified_files[0]
                            verified_name = Path(verified_path).name
                            state_label = "success" if method_ok else "recovered output"
                            self.progress.emit(f"{_dl_tag} {state_label}: {verified_name}")
                            try:
                                from modules.link_grabber.intelligence import get_learning_system
                                get_learning_system().record_download_performance(
                                    _creator, platform, method.__name__,
                                    True, time.time() - _dl_start)
                            except Exception:
                                pass
                            break
                        if method_ok:
                            method_error = "reported success but created no verified media"
                        else:
                            method_error = "no verified media created"
                    except Exception as e:
                        method_error = str(e)[:200]
                    last_dl_error = f"{method.__name__}: {method_error}"
                    self.progress.emit(f"{_dl_tag} failed: {method_error[:140]}")
                    if attempted_methods < len(methods):
                        _next_m = methods[_m_idx + 1]
                        _next_tag = f"[DL-{_DL_NUM.get(_next_m.__name__, '?')}]"
                        self.progress.emit(f"{_dl_tag} trying {_next_tag}...")
                    try:
                        from modules.link_grabber.intelligence import get_learning_system
                        get_learning_system().record_download_performance(
                            _creator, platform, method.__name__,
                            False, time.time() - _dl_start, last_dl_error)
                    except Exception:
                        pass

                # Recovery chain if all methods failed
                if not success and not self.cancelled:
                    try:
                        from modules.shared.failure_classifier import classify_failure, is_auth_failure
                        from modules.shared.recovery_chain import RecoveryChain
                        from modules.shared.session_authority import get_session_authority
                        _ft = classify_failure(last_dl_error, platform)
                        _auth_triggered = is_auth_failure(_ft)

                        # Auth-wall fallback: some methods fail with generic
                        # "method_returned_false" while the browser session is
                        # actually valid. In that case still trigger recovery.
                        if not _auth_triggered:
                            try:
                                _sa = get_session_authority()
                                _sess = _sa.get_session_status()
                                _strict = _sa.get_login_status()
                                if _sess.get(platform) or _strict.get(platform):
                                    _auth_triggered = True
                                    _ft = classify_failure("auth_wall_suspected", platform)
                            except Exception:
                                pass

                        if _auth_triggered:
                            self.progress.emit("Checking access...")
                            # Pre-recovery: managed CDP fresh export
                            try:
                                from modules.shared.managed_chrome_session import (
                                    MANAGED_CDP_ATTACH_FIRST,
                                    get_managed_chrome_session,
                                )
                                if MANAGED_CDP_ATTACH_FIRST and platform in (
                                    "instagram", "facebook", "tiktok",
                                ):
                                    _mgr = get_managed_chrome_session()
                                    if _mgr.is_running():
                                        _sa2 = get_session_authority()
                                        _cdp_fresh = _sa2.force_browser_cookie_refresh(platform)
                                        if _cdp_fresh and _cdp_fresh not in self._all_cookie_files:
                                            self._all_cookie_files.insert(0, _cdp_fresh)
                                            for method in methods[:2]:
                                                try:
                                                    if method(url, folder, _cdp_fresh):
                                                        success = True
                                                        break
                                                except Exception:
                                                    pass
                            except ImportError:
                                pass
                            except Exception:
                                pass
                            if not success:
                                _rc = RecoveryChain().attempt_recovery(platform, _ft)
                                if _rc.cookie_path:
                                    cookie_file = _rc.cookie_path
                                    if cookie_file not in self._all_cookie_files:
                                        self._all_cookie_files.insert(0, cookie_file)
                                    for method in methods[:2]:
                                        try:
                                            if method(url, folder, cookie_file):
                                                success = True
                                                break
                                        except Exception:
                                            pass
                    except ImportError:
                        pass

                # Final outcome: success or fail
                if success:
                    self.success_count += 1
                    self.progress.emit(f"Downloaded [{processed}/{total}]")
                    self._mark_as_downloaded(url)
                    self._remove_from_source_txt(url, folder)
                    self.video_complete.emit(url)
                elif not self.cancelled:
                    self.progress.emit(f"Failed [{processed}/{total}]")
                    reason = "All download methods failed"
                    self.failed_urls.append((url, reason))
                pct = int((processed / total) * 100)
                self.progress_percent.emit(pct)
            self.progress.emit("\n" + "="*60)
            self.progress.emit("ðŸ“Š FINAL REPORT:")
            self.progress.emit(f"âœ… Successfully downloaded: {self.success_count}/{total}")
            self.progress.emit(f"â­ï¸ Skipped (already done): {self.skipped_count}")
            failed_count = total - self.success_count - self.skipped_count
            self.progress.emit(f"âŒ Failed: {failed_count}")

            # Calculate success rate
            if total > 0:
                success_rate = (self.success_count / total * 100)
                self.progress.emit(f"ðŸ“ˆ Success Rate: {success_rate:.1f}%")

                # Success rate assessment
                if success_rate >= 95:
                    self.progress.emit("ðŸŽ‰ EXCELLENT! Almost all videos downloaded!")
                elif success_rate >= 80:
                    self.progress.emit("ðŸ‘ GOOD! Most videos downloaded successfully")
                elif success_rate >= 50:
                    self.progress.emit("âš ï¸ NEEDS IMPROVEMENT - Check failed downloads below")
                else:
                    self.progress.emit("âŒ CRITICAL - Many downloads failed")

            # Enhanced Failed URLs Report
            if self.failed_urls:
                self.progress.emit("\n" + "â”"*60)
                self.progress.emit(f"âŒ FAILED DOWNLOADS - Detailed Report ({len(self.failed_urls)} videos):")
                self.progress.emit("â”"*60)

                for idx, (failed_url, reason) in enumerate(self.failed_urls[:10], 1):  # Show first 10
                    self.progress.emit(f"\n{idx}. {failed_url[:65]}...")
                    self.progress.emit(f"   ðŸ’” Reason: {reason}")

                    # Suggest solutions based on common issues
                    if 'cookie' in reason.lower():
                        self.progress.emit(f"   ðŸ’¡ Solution: Update cookies file")
                    elif 'private' in reason.lower():
                        self.progress.emit(f"   ðŸ’¡ Solution: Check if video is private/deleted")
                    elif 'proxy' in reason.lower() or 'ip block' in reason.lower():
                        self.progress.emit(f"   ðŸ’¡ Solution: Add/change proxy in Link Grabber")
                    else:
                        self.progress.emit(f"   ðŸ’¡ Solution: Try different quality or enable VPN")

                if len(self.failed_urls) > 10:
                    self.progress.emit(f"\n... and {len(self.failed_urls) - 10} more failed downloads")

                self.progress.emit("\n" + "â”"*60)

            self.progress.emit("="*60)

            # Update history.json for bulk mode
            if self.history_manager and self.bulk_creators:
                self.progress.emit("\nðŸ“ Updating download history...")
                try:
                    # Track downloads per creator
                    creator_stats = {}  # {creator: {'success': 0, 'failed': 0}}

                    # Count successes/failures per creator
                    for creator, creator_info in self.bulk_creators.items():
                        # === FIX: Normalize creator links for accurate matching ===
                        raw_links = creator_info.get('links', [])
                        creator_links_normalized = set(normalize_url(link) for link in raw_links)

                        success = 0
                        failed = 0

                        for url in self.urls:
                            # === FIX: Normalize current URL for comparison ===
                            url_normalized = normalize_url(url)

                            # Now comparison will work correctly
                            if url_normalized in creator_links_normalized:
                                # FIX: Check using NORMALIZED url (downloaded_links contains normalized URLs)
                                if url_normalized in self.downloaded_links:
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
                        self.progress.emit(f"  âœ“ {creator}: {stats['success']} downloaded, {stats['failed']} failed")

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

                                    self.progress.emit(f"  ðŸ—‘ï¸ Updated {Path(links_file).name}")
                                except Exception as e:
                                    self.progress.emit(f"  âš ï¸ Failed to update {Path(links_file).name}: {str(e)[:50]}")

                    self.progress.emit("âœ… History updated!")
                except Exception as e:
                    self.progress.emit(f"âš ï¸ History update failed: {str(e)[:100]}")

            if self.cancelled:
                self.finished.emit(False, f"âš ï¸ Cancelled - {self.success_count} downloaded")
            elif self.success_count + self.skipped_count == total:
                self.finished.emit(True, f"âœ… ALL DONE! {self.success_count} new, {self.skipped_count} skipped")
            elif self.success_count > 0:
                self.finished.emit(True, f"âš ï¸ Partial: {self.success_count} downloaded, {self.skipped_count} skipped")
            else:
                self.finished.emit(False, f"âŒ Failed - 0 downloaded")
        except Exception as e:
            self.progress.emit(f"âŒ CRITICAL ERROR: {str(e)[:200]}")
            self.finished.emit(False, f"âŒ Error: {str(e)[:100]}")

    def cancel(self):
        self.cancelled = True
        self.progress.emit("âš ï¸ Cancellation requested...")



