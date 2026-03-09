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
from urllib.parse import urlparse, parse_qs

# Import intelligence system
try:
    from .intelligence import get_learning_system
except ImportError:
    # Fallback if intelligence not available
    def get_learning_system():
        return None

try:
    from .browser_auth import ChromiumAuthManager
    from .content_filter import ContentFilter
except ImportError:
    ChromiumAuthManager = None
    ContentFilter = None


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

        elif platform_key == 'facebook':
            parsed = urlparse(url)
            parts = [p for p in (parsed.path or '').split('/') if p]
            lower_parts = [p.lower() for p in parts]

            if lower_parts and lower_parts[0] == 'profile.php':
                fb_id = parse_qs(parsed.query or '').get('id', [''])[0].strip()
                if fb_id:
                    return f"fb_{fb_id}"
                return 'facebook_profile'

            if lower_parts and lower_parts[0] == 'people':
                if len(parts) >= 2 and parts[1]:
                    return parts[1]
                if len(parts) >= 3 and parts[2]:
                    return f"fb_{parts[2]}"
                return 'facebook_profile'

            reserved = {
                'reel', 'reels', 'videos', 'watch', 'story', 'stories', 'posts',
                'about', 'photos', 'photo', 'live', 'profile.php', 'people', 'pg',
                'groups', 'share', 'marketplace',
            }
            for part in parts:
                if part.lower() not in reserved:
                    return part

        elif platform_key == 'twitter':
            match = re.search(r'(?:twitter|x)\.com/([^/?#]+)', url_lower)
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


def _normalize_source_url(url: str, platform_key: str) -> str:
    """Normalize profile URLs so extractors receive supported canonical targets."""
    raw = (url or "").strip()
    if not raw.startswith(("http://", "https://")):
        return raw

    try:
        parsed = urlparse(raw)
        parts = [p for p in (parsed.path or "").split("/") if p]
        lower_parts = [p.lower() for p in parts]

        if platform_key == "facebook":
            # Keep profile.php?id=... as-is
            if lower_parts and lower_parts[0] == "profile.php":
                return raw.rstrip("/")
            # people/<name>/<id> -> canonical profile by name
            if lower_parts and lower_parts[0] == "people":
                if len(parts) >= 2 and parts[1]:
                    return f"https://www.facebook.com/{parts[1]}"
            reserved = {
                "reel", "reels", "videos", "watch", "story", "stories", "posts",
                "about", "photos", "photo", "live", "people", "profile.php", "pg",
                "groups", "share", "marketplace",
            }
            if parts:
                first = parts[0]
                if first.lower() not in reserved:
                    return f"https://www.facebook.com/{first}"
            return "https://www.facebook.com/"

        if platform_key == "instagram":
            reserved = {"reel", "reels", "p", "tv", "stories", "explore"}
            if parts:
                first = parts[0]
                if first.lower() not in reserved:
                    return f"https://www.instagram.com/{first}"
            return "https://www.instagram.com/"

        if platform_key == "tiktok":
            for p in parts:
                if p.startswith("@") and len(p) > 1:
                    return f"https://www.tiktok.com/{p}"
            return raw.rstrip("/")

        if platform_key == "youtube":
            if parts and parts[0].startswith("@"):
                return f"https://www.youtube.com/{parts[0]}"
            if len(parts) >= 2 and parts[0].lower() in {"channel", "c", "user"}:
                return f"https://www.youtube.com/{parts[0]}/{parts[1]}"
            return raw.rstrip("/")
    except Exception:
        return raw.rstrip("/")

    return raw.rstrip("/")


def _facebook_reels_url(url: str) -> str:
    """Return a Facebook reels-tab URL when source is a profile-like URL."""
    raw = (url or "").strip()
    if not raw:
        return raw
    try:
        parsed = urlparse(raw)
        host = (parsed.netloc or "").lower()
        if "facebook.com" not in host and "fb.com" not in host:
            return raw

        parts = [p for p in (parsed.path or "").split("/") if p]
        lower_parts = [p.lower() for p in parts]
        q = parse_qs(parsed.query or "")

        if lower_parts and lower_parts[0] == "profile.php":
            if q.get("sk", [""])[0] == "reels_tab":
                return raw
            connector = "&" if ("?" in raw) else "?"
            return f"{raw}{connector}sk=reels_tab"

        if any(p in {"reel", "reels", "videos", "watch"} for p in lower_parts):
            return raw

        if parts:
            return f"https://www.facebook.com/{parts[0]}/reels"
    except Exception:
        return raw
    return raw


def detect_platform_url_type(url: str, platform_key: str) -> str:
    """
    Classify a URL into one of four content types.

    Returns
    -------
    'profile'  â€“ bare creator/channel page  (e.g. https://youtube.com/@MrBeast)
    'video'    â€“ single video/reel/post URL (e.g. https://youtube.com/watch?v=xxx)
    'playlist' â€“ playlist or collection     (e.g. https://youtube.com/playlist?list=xxx)
    'tab'      â€“ profile sub-tab            (e.g. https://youtube.com/@MrBeast/shorts)
    'unknown'  â€“ unrecognised pattern or any parse error

    Pure urlparse + re only â€” no network calls, no side-effects.
    """
    try:
        raw = (url or "").strip().rstrip("/")
        if not raw.startswith(("http://", "https://")):
            return "unknown"

        parsed  = urlparse(raw)
        path    = parsed.path or ""
        query   = parsed.query or ""
        parts   = [p for p in path.split("/") if p]
        lparts  = [p.lower() for p in parts]

        # â”€â”€ YouTube â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if platform_key == "youtube":
            # Single video
            if "watch" in lparts and "v=" in query:
                return "video"
            if re.search(r"^/shorts/[^/]+$", path):
                return "video"
            # Playlist
            if "playlist" in lparts and "list=" in query:
                return "playlist"
            # Tab: /@user/<tab>  or  /channel/<id>/<tab>  or  /c/<name>/<tab>
            _YT_TABS = {"videos", "shorts", "streams", "live", "playlists",
                        "community", "channels", "about", "featured", "membership"}
            if len(lparts) >= 2:
                # /@username/<tab>
                if lparts[0].startswith("@") and lparts[1] in _YT_TABS:
                    return "tab"
                # /channel/<id>/<tab>  or  /c/<name>/<tab>  or  /user/<name>/<tab>
                if lparts[0] in {"channel", "c", "user"} and len(lparts) >= 3 and lparts[2] in _YT_TABS:
                    return "tab"
            # Profile: bare /@user, /channel/<id>, /c/<name>, /user/<name>
            if len(lparts) == 1 and lparts[0].startswith("@"):
                return "profile"
            if len(lparts) == 2 and lparts[0] in {"channel", "c", "user"}:
                return "profile"
            return "unknown"

        # â”€â”€ Instagram â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if platform_key == "instagram":
            # Single video / post
            if len(lparts) >= 2 and lparts[0] in {"p", "reel", "tv"}:
                return "video"
            # Tab: /{username}/<tab>
            _IG_TABS = {"reels", "tagged", "igtv", "channel", "guides"}
            if len(lparts) == 2 and lparts[1] in _IG_TABS:
                return "tab"
            # Profile: bare /{username}  (not a reserved slug)
            _IG_RESERVED = {"p", "reel", "tv", "reels", "stories", "explore",
                            "accounts", "direct", "ar"}
            if len(lparts) == 1 and lparts[0] not in _IG_RESERVED:
                return "profile"
            return "unknown"

        # â”€â”€ TikTok â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if platform_key == "tiktok":
            # Single video: /@user/video/<id>
            if len(lparts) >= 3 and lparts[0].startswith("@") and lparts[1] == "video":
                return "video"
            # Profile: bare /@user
            if len(lparts) == 1 and lparts[0].startswith("@"):
                return "profile"
            # Tag pages, sounds, etc. â€” not a supported target
            return "unknown"

        # â”€â”€ Facebook â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if platform_key == "facebook":
            q = parse_qs(query)
            # Single video / reel
            if len(lparts) >= 1 and lparts[0] == "reel":
                return "video"
            if lparts == ["watch"] or (lparts and lparts[0] == "watch" and "v=" in query):
                return "video"
            if len(lparts) >= 3 and lparts[1] == "videos" and re.match(r"^\d+$", lparts[2]):
                return "video"
            # share/v/<id>
            if len(lparts) >= 3 and lparts[0] == "share" and lparts[1] == "v":
                return "video"
            # Tab: /{user}/videos  or  /{user}/reels  (no numeric id after)
            _FB_TABS = {"videos", "reels", "photos", "about", "community",
                        "events", "live", "podcasts", "reviews", "shop"}
            if len(lparts) == 2 and lparts[1] in _FB_TABS:
                return "tab"
            # Profile: profile.php?id=...  or  /people/<name>/<id>  or  bare /{user}
            if lparts and lparts[0] == "profile.php":
                return "profile"
            if lparts and lparts[0] == "people":
                return "profile"
            _FB_RESERVED = {"reel", "reels", "watch", "videos", "share", "groups",
                            "marketplace", "gaming", "events", "pages", "ads",
                            "stories", "live", "fundraisers", "saved"}
            if len(lparts) == 1 and lparts[0] not in _FB_RESERVED:
                return "profile"
            return "unknown"

        # â”€â”€ Twitter / X â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if platform_key == "twitter":
            # Single tweet / video
            if len(lparts) >= 3 and lparts[1] == "status":
                return "video"
            # Tab: /{user}/<tab>
            _TW_TABS = {"media", "with_replies", "likes", "retweets",
                        "following", "followers", "highlights"}
            if len(lparts) == 2 and lparts[1] in _TW_TABS:
                return "tab"
            # Profile: bare /{user}
            _TW_RESERVED = {"i", "home", "explore", "notifications", "messages",
                            "settings", "compose", "search", "intent"}
            if len(lparts) == 1 and lparts[0] not in _TW_RESERVED:
                return "profile"
            return "unknown"

    except Exception:
        pass

    return "unknown"


def detect_available_tabs(
    profile_url: str,
    platform_key: str = 'youtube',
    cookie_file: str = None,
    proxy: str = None,
    timeout: int = 8,
) -> typing.List[str]:
    """
    Detect which content tabs are available on a YouTube channel page.

    Uses yt-dlp ``--dump-single-json --flat-playlist`` to fetch the channel
    metadata and extracts the 'tabs' field from the JSON response.

    Parameters
    ----------
    profile_url : str
        A YouTube channel/profile URL, e.g. 'https://www.youtube.com/@MrBeast'
    platform_key : str
        Currently only 'youtube' is supported.  Other platforms return [].
    cookie_file : str | None
        Optional path to a Netscape-format cookies.txt file passed via
        ``--cookies``.
    proxy : str | None
        Optional proxy URL passed via ``--proxy``.
    timeout : int
        Subprocess timeout in seconds (default 8).

    Returns
    -------
    list[str]
        Lowercase tab names found on the channel, e.g.
        ['videos', 'shorts', 'streams', 'playlists'].
        Returns [] on any error, timeout, or unsupported platform.
    """
    if platform_key != 'youtube':
        return []

    try:
        ytdlp_path = _get_ytdlp_binary_path()
    except Exception:
        ytdlp_path = 'yt-dlp'

    cmd = [
        ytdlp_path,
        '--dump-single-json',
        '--flat-playlist',
        '--no-warnings',
        '--ignore-errors',
        '--skip-download',
        profile_url,
    ]

    if cookie_file:
        cmd += ['--cookies', cookie_file]
    if proxy:
        cmd += ['--proxy', proxy]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        raw = (result.stdout or '').strip()
        if not raw:
            return []

        data = json.loads(raw)

        # yt-dlp returns a 'tabs' list on channel pages.
        # Each entry is a dict with a 'title' key (e.g. 'Videos', 'Shorts').
        tabs_raw = data.get('tabs', [])
        tabs: typing.List[str] = []
        for tab in tabs_raw:
            title = ''
            if isinstance(tab, dict):
                title = tab.get('title', '') or tab.get('url', '')
            elif isinstance(tab, str):
                title = tab
            name = title.strip().lower()
            if name and name not in tabs:
                tabs.append(name)

        return tabs

    except subprocess.TimeoutExpired:
        logging.warning("detect_available_tabs: yt-dlp timed out for %s", profile_url)
        return []
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logging.warning("detect_available_tabs: parse error â€” %s", exc)
        return []
    except Exception as exc:
        logging.warning("detect_available_tabs: unexpected error â€” %s", exc)
        return []



def is_chrome_running_with_debug(ports: typing.List[int] = None) -> int:
    """
    Check whether Chrome is already running with a remote-debugging port open.

    Tries each port in *ports* (default: [9222, 9223, 9224, 9229]) with a
    non-blocking TCP connect.  Returns the first open port, or 0 if none found.

    Returns
    -------
    int
        The open CDP port (e.g. 9222), or 0 if Chrome has no debug port open.
    """
    import socket as _sock
    if ports is None:
        ports = [9222, 9223, 9224, 9229]
    for port in ports:
        try:
            s = _sock.create_connection(("localhost", port), timeout=0.5)
            s.close()
            return port
        except (ConnectionRefusedError, OSError, TimeoutError):
            continue
    return 0


def detect_tabs_via_cdp(
    profile_url: str,
    platform_key: str = 'youtube',
    cdp_port: int = 0,
) -> typing.List[str]:
    """
    Layer 3: Connect to the user's running Chrome via CDP (Selenium attach),
    navigate to *profile_url*, and extract available tab names from the DOM.

    Only works when Chrome was launched with ``--remote-debugging-port``.
    Attaches to the existing session (fully logged in) without opening a new
    window, and disconnects without closing Chrome.

    Parameters
    ----------
    profile_url : str
        The channel/profile URL to navigate to.
    platform_key : str
        Platform identifier (currently only 'youtube' is parsed).
    cdp_port : int
        Explicit port to use.  Pass 0 (default) to auto-detect via
        ``is_chrome_running_with_debug()``.

    Returns
    -------
    list[str]
        Lowercase tab names extracted from the page (e.g. ['videos', 'shorts']).
        Returns [] if Chrome is not running with debug port, Selenium is
        unavailable, navigation fails, or no tabs are found.
    """
    if platform_key != 'youtube':
        return []

    # Resolve port
    port = cdp_port or is_chrome_running_with_debug()
    if not port:
        return []

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as _COptions
        from selenium.webdriver.common.by import By
    except ImportError:
        logging.debug("detect_tabs_via_cdp: selenium not available")
        return []

    opts = _COptions()
    opts.add_experimental_option("debuggerAddress", f"localhost:{port}")

    _KNOWN_SLUGS = {
        'videos', 'shorts', 'streams', 'live',
        'playlists', 'community', 'channels', 'about',
        'featured', 'membership', 'podcasts', 'releases',
    }

    def _parse_tabs(drv) -> typing.List[str]:
        found: typing.List[str] = []

        # Strategy A: classic <tp-yt-paper-tab> tab bar
        try:
            for el in drv.find_elements(By.CSS_SELECTOR, 'tp-yt-paper-tab'):
                text = (el.text or '').strip().lower().split('\n')[0]
                if text and text not in found:
                    found.append(text)
        except Exception:
            pass
        if found:
            return found

        # Strategy B: newer <yt-tab-group-shape> layout
        try:
            for el in drv.find_elements(
                By.CSS_SELECTOR,
                'yt-tab-group-shape yt-tab-shape, yt-tab-group-shape [role="tab"]',
            ):
                text = (el.text or '').strip().lower().split('\n')[0]
                if text and text not in found:
                    found.append(text)
        except Exception:
            pass
        if found:
            return found

        # Strategy C: anchor href slug matching
        try:
            for a in drv.find_elements(By.CSS_SELECTOR, 'a[href]'):
                href = (a.get_attribute('href') or '').rstrip('/')
                slug = href.split('/')[-1].lower()
                if slug in _KNOWN_SLUGS and slug not in found:
                    found.append(slug)
        except Exception:
            pass
        return found

    driver = None
    try:
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(15)
        driver.get(profile_url)

        tabs = _parse_tabs(driver)
        if not tabs:
            time.sleep(3)            # wait for lazy tab render
            tabs = _parse_tabs(driver)

        return tabs

    except Exception as exc:
        logging.debug("detect_tabs_via_cdp: %s", exc)
        return []
    finally:
        # Disconnect ChromeDriver without closing the user's Chrome window.
        try:
            if driver and driver.service:
                driver.service.stop()
        except Exception:
            pass


def detect_available_tabs_bulletproof(
    profile_url: str,
    platform_key: str = 'youtube',
    cookie_file: str = None,
    proxy: str = None,
    progress_callback=None,
) -> typing.List[str]:
    """
    3-layer tab detection with automatic fallback.

    Layers tried in order (each layer skipped if not applicable):

    Layer 1 â€” yt-dlp JSON probe (YouTube only, 8 s timeout)
        Calls ``detect_available_tabs()``.  Fastest and most reliable when
        YouTube returns JSON; fails when rate-limited or behind a cookie wall.

    Layer 2 â€” HTTP HEAD probe (YouTube only)
        Issues lightweight HEAD requests for each known tab URL and records
        which ones return HTTP 200.  Works without cookies for public channels.

    Layer 3 â€” CDP attach to running Chrome
        Calls ``detect_tabs_via_cdp()`` using the user's logged-in Chrome
        session.  Works for private/age-gated channels.  Skipped if Chrome
        has no debug port open.

    Fallback â€” empty list
        Caller uses ``PLATFORM_TAB_PRIORITY`` defaults.

    Parameters
    ----------
    profile_url : str
        Channel/profile URL.
    platform_key : str
        Platform identifier.
    cookie_file : str | None
        Netscape cookies file passed to Layer 1.
    proxy : str | None
        Proxy URL passed to Layer 1.
    progress_callback : callable | None
        Optional log sink for status messages.

    Returns
    -------
    list[str]
        Lowercase tab names (may be empty â€” caller always has hardcoded
        defaults).  Never raises.
    """
    def _log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    if platform_key != 'youtube':
        return []

    # â”€â”€ Layer 1: yt-dlp JSON probe â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _log("Tab detection L1: yt-dlp probe...")
    try:
        tabs_l1 = detect_available_tabs(
            profile_url=profile_url,
            platform_key=platform_key,
            cookie_file=cookie_file,
            proxy=proxy,
            timeout=8,
        )
        if tabs_l1:
            _log(f"Tab detection L1 success: {tabs_l1}")
            return tabs_l1
        _log("Tab detection L1: no tabs returned.")
    except Exception as exc:
        _log(f"Tab detection L1 error: {exc}")

    # â”€â”€ Layer 2: HTTP HEAD probe â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _log("Tab detection L2: HTTP HEAD probe...")
    _SLUGS_L2 = [
        'videos', 'shorts', 'streams', 'live',
        'playlists', 'community', 'releases', 'podcasts',
    ]
    try:
        import urllib.request as _ureq
        import urllib.error   as _uerr
        _UA = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
        base = profile_url.rstrip('/')
        tabs_l2: typing.List[str] = []
        for slug in _SLUGS_L2:
            try:
                req = _ureq.Request(
                    f"{base}/{slug}",
                    method='HEAD',
                    headers={'User-Agent': _UA, 'Accept-Language': 'en-US,en;q=0.9'},
                )
                with _ureq.urlopen(req, timeout=4) as resp:
                    if resp.status == 200 and slug not in tabs_l2:
                        tabs_l2.append(slug)
            except (_uerr.HTTPError, _uerr.URLError, OSError):
                pass
            except Exception:
                pass
        if tabs_l2:
            _log(f"Tab detection L2 success: {tabs_l2}")
            return tabs_l2
        _log("Tab detection L2: no tabs confirmed.")
    except Exception as exc:
        _log(f"Tab detection L2 error: {exc}")

    # â”€â”€ Layer 3: CDP attach to running Chrome â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    cdp_port = is_chrome_running_with_debug()
    if cdp_port:
        _log(f"Tab detection L3: CDP attach (port {cdp_port})...")
        try:
            tabs_l3 = detect_tabs_via_cdp(
                profile_url=profile_url,
                platform_key=platform_key,
                cdp_port=cdp_port,
            )
            if tabs_l3:
                _log(f"Tab detection L3 success: {tabs_l3}")
                return tabs_l3
            _log("Tab detection L3: no tabs found in DOM.")
        except Exception as exc:
            _log(f"Tab detection L3 error: {exc}")
    else:
        _log("Tab detection L3 skipped: Chrome debug port not open.")

    # â”€â”€ Fallback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _log("All tab detection layers exhausted; using platform defaults.")
    return []

def _get_running_browser_names() -> typing.Set[str]:
    """Best-effort detection of currently running desktop browsers on Windows."""
    names: typing.Set[str] = set()
    try:
        result = subprocess.run(
            ["tasklist"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
        out = (result.stdout or "").lower()
        if "chrome.exe" in out:
            names.add("chrome")
        if "msedge.exe" in out:
            names.add("edge")
        if "brave.exe" in out:
            names.add("brave")
        if "firefox.exe" in out:
            names.add("firefox")
    except Exception:
        pass
    return names


def _iter_browser_profile_roots() -> typing.List[typing.Tuple[str, Path]]:
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        ("chrome", Path(local_appdata) / "Google" / "Chrome" / "User Data"),
        ("edge", Path(local_appdata) / "Microsoft" / "Edge" / "User Data"),
        ("brave", Path(local_appdata) / "BraveSoftware" / "Brave-Browser" / "User Data"),
    ]
    return [(name, root) for name, root in candidates if root.exists()]

def _mask_proxy(proxy: str) -> str:
    """Hide credentials in logs while keeping host:port visible."""
    p = (proxy or "").strip()
    if not p:
        return ""
    try:
        if "@" in p:
            p = p.split("@", 1)[1]
        p = p.replace("http://", "").replace("https://", "").replace("socks5://", "").replace("socks4://", "")
        return p
    except Exception:
        return proxy


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
            result['warnings'].append(f"Ã¢ÂÅ’ Cookie file not found: {cookie_file}")
            return result

        file_size = cookie_path.stat().st_size
        if file_size < 10:
            result['warnings'].append(f"Ã¢Å¡Â Ã¯Â¸Â Cookie file too small ({file_size} bytes)")
            return result

        # Check 2: File freshness (modification time)
        mod_time = cookie_path.stat().st_mtime
        file_age = datetime.now() - datetime.fromtimestamp(mod_time)
        result['age_days'] = file_age.days

        if file_age.days > max_age_days:
            result['fresh'] = False
            result['warnings'].append(
                f"Ã¢Å¡Â Ã¯Â¸Â Cookie file is {file_age.days} days old (older than {max_age_days} days)"
            )
            result['warnings'].append(f"   Ã°Å¸â€™Â¡ Consider refreshing cookies for better success rate")

        # Check 3: Valid Netscape format and cookie expiration
        current_timestamp = int(time.time())

        with open(cookie_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        cookie_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
        result['total_cookies'] = len(cookie_lines)

        if result['total_cookies'] == 0:
            result['warnings'].append(f"Ã¢Å¡Â Ã¯Â¸Â No cookies found in file (only comments/blank lines)")
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
                    f"Ã¢Å¡Â Ã¯Â¸Â {expired_count}/{result['total_cookies']} cookies expired ({expiry_pct:.0f}%)"
                )
                result['warnings'].append(f"   Ã°Å¸â€™Â¡ Cookie refresh recommended")

        # All checks passed
        result['valid'] = True

        # Add success message if fresh and minimal warnings
        if result['fresh'] and len(result['warnings']) == 0:
            logging.debug(f"Ã¢Å“â€œ Cookie validation passed: {result['total_cookies']} cookies, {result['age_days']} days old")

    except Exception as e:
        result['warnings'].append(f"Ã¢ÂÅ’ Cookie validation error: {str(e)[:100]}")

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


def _platform_domain_tokens(platform_key: str) -> typing.List[str]:
    mapping = {
        'youtube': ['youtube.com', 'google.com', 'youtu.be'],
        'instagram': ['instagram.com'],
        'tiktok': ['tiktok.com'],
        'facebook': ['facebook.com', 'fb.com', 'messenger.com'],
        'twitter': ['twitter.com', 'x.com'],
    }
    return mapping.get(platform_key, [])


def _extract_browser_cookies(platform_key: str, preferred_browser: str = None) -> typing.Optional[str]:
    """Extract cookies from browser (fallback)"""
    try:
        import browser_cookie3 as bc3
    except ImportError:
        return None

    domain = _get_platform_domain(platform_key)
    tokens = _platform_domain_tokens(platform_key)
    browsers = [
        ('chrome', getattr(bc3, 'chrome', None)),
        ('edge', getattr(bc3, 'edge', None)),
        ('firefox', getattr(bc3, 'firefox', None))
    ]

    fallback_browsers = list(browsers)
    if preferred_browser:
        preferred_browser = preferred_browser.lower()
        browsers = [b for b in browsers if b[0] == preferred_browser] or list(browsers)

    for browser_name, browser_func in browsers:
        if not browser_func:
            continue
        try:
            # Try strict domain extraction first.
            cookie_jar = browser_func(domain_name=domain) if domain else browser_func()
            if not cookie_jar or len(cookie_jar) == 0:
                # Fallback: fetch all cookies and filter by platform domains.
                cookie_jar = browser_func()

            if cookie_jar and len(cookie_jar) > 0:
                filtered = []
                for cookie in cookie_jar:
                    c_domain = (getattr(cookie, 'domain', '') or '').lower()
                    if not tokens or any(token in c_domain for token in tokens):
                        filtered.append(cookie)

                if not filtered:
                    continue

                temp_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.txt',
                    delete=False,
                    encoding='utf-8'
                )

                temp_file.write("# Netscape HTTP Cookie File\n")
                temp_file.write(f"# Extracted from {browser_name}\n\n")

                for cookie in filtered:
                    cookie_domain = getattr(cookie, 'domain', '')
                    flag = 'TRUE' if cookie_domain.startswith('.') else 'FALSE'
                    path = getattr(cookie, 'path', '/')
                    secure = 'TRUE' if getattr(cookie, 'secure', False) else 'FALSE'
                    expires = str(int(getattr(cookie, 'expires', 0))) if getattr(cookie, 'expires', 0) else '0'
                    name = getattr(cookie, 'name', '')
                    value = getattr(cookie, 'value', '')

                    temp_file.write(f"{cookie_domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")

                temp_file.close()
                return temp_file.name

        except Exception:
            continue

    # Preferred browser may fail due profile locking/decryption; auto-try all browsers.
    if preferred_browser:
        for browser_name, browser_func in fallback_browsers:
            if not browser_func or browser_name == preferred_browser:
                continue
            try:
                cookie_jar = browser_func()
                if not cookie_jar or len(cookie_jar) == 0:
                    continue

                filtered = []
                for cookie in cookie_jar:
                    c_domain = (getattr(cookie, 'domain', '') or '').lower()
                    if not tokens or any(token in c_domain for token in tokens):
                        filtered.append(cookie)
                if not filtered:
                    continue

                temp_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.txt',
                    delete=False,
                    encoding='utf-8'
                )
                temp_file.write("# Netscape HTTP Cookie File\n")
                temp_file.write(f"# Extracted from {browser_name}\n\n")
                for cookie in filtered:
                    cookie_domain = getattr(cookie, 'domain', '')
                    flag = 'TRUE' if cookie_domain.startswith('.') else 'FALSE'
                    path = getattr(cookie, 'path', '/')
                    secure = 'TRUE' if getattr(cookie, 'secure', False) else 'FALSE'
                    expires = str(int(getattr(cookie, 'expires', 0))) if getattr(cookie, 'expires', 0) else '0'
                    name = getattr(cookie, 'name', '')
                    value = getattr(cookie, 'value', '')
                    temp_file.write(f"{cookie_domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
                temp_file.close()
                return temp_file.name
            except Exception:
                continue

    return None


def _extract_browser_cookies_db_copy(
    platform_key: str,
    preferred_browser: str = None,
    cookies_dir: Path = None,
    progress_callback=None,
) -> typing.Optional[str]:
    """
    Workflow 1: Smart cookie extraction.
      1. Detect running browsers â†’ copy locked DB
      2. No running browser â†’ read closed DB directly
      3. Still nothing â†’ open default browser from registry â†’ copy DB
    Passes all debug messages to progress_callback for GUI visibility.
    """
    try:
        from modules.shared.browser_extractor import extract_cookies_smart
        from modules.config.paths import get_cookies_dir as _get_cookies_dir

        save_path = None
        if cookies_dir:
            save_path = Path(cookies_dir) / "chrome_cookies.txt"
        else:
            try:
                save_path = _get_cookies_dir() / "chrome_cookies.txt"
            except Exception:
                pass

        result = extract_cookies_smart(
            platform_key=platform_key,
            save_to=save_path,
            preferred_browser=preferred_browser,
            cb=progress_callback,
        )
        return result
    except Exception as exc:
        logging.debug(f"_extract_browser_cookies_db_copy failed: {exc}")
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


def _apply_instaloader_session(loader, cookie_file: str, platform_key: str, proxy: str = None) -> int:
    """Configure Instaloader session with cookies, proxy, and user agent."""
    try:
        loader.context._session.headers.update({'User-Agent': _get_random_user_agent()})
    except Exception:
        pass

    if proxy:
        try:
            proxy_url = _parse_proxy_format(proxy)
            loader.context._session.proxies = {'http': proxy_url, 'https': proxy_url}
        except Exception:
            pass

    if not cookie_file:
        return 0

    try:
        cookies = _load_cookies_from_file(cookie_file, platform_key)
        csrf_token = None
        for cookie in cookies:
            if cookie.get('name') == 'csrftoken':
                csrf_token = cookie.get('value')
            loader.context._session.cookies.set(
                cookie.get('name', ''),
                cookie.get('value', ''),
                domain=cookie.get('domain'),
                path=cookie.get('path', '/') or '/',
                secure=bool(cookie.get('secure', False)),
                expires=cookie.get('expires'),
            )
        if csrf_token:
            loader.context._session.headers.update({'X-CSRFToken': csrf_token})
        loader.context._session.headers.setdefault('X-IG-App-ID', '936619743392459')
        loader.context._session.headers.setdefault('Referer', 'https://www.instagram.com/')
        return len(cookies)
    except Exception:
        return 0


def _get_instagram_expected_count(url: str, cookie_file: str, proxy: str = None) -> typing.Optional[int]:
    """
    Best-effort expected post count via lightweight HTTP (NO Instaloader).
    Returns None immediately on 429 or any error â€“ never waits/retries.
    """
    try:
        username_match = re.search(r'instagram\.com/([^/?#]+)', url, flags=re.IGNORECASE)
        if not username_match or username_match.group(1) in ['p', 'reel', 'tv', 'stories', 'explore']:
            return None

        username = username_match.group(1).strip('/')
        session = _build_requests_session(cookie_file, 'instagram', proxy)
        if not session:
            return None

        resp = session.get(
            f'https://i.instagram.com/api/v1/users/web_profile_info/?username={username}',
            timeout=8
        )

        if resp.status_code == 429:
            logging.debug(f"Instagram expected_count: 429 â€“ skipping (no wait)")
            return None
        if resp.status_code != 200:
            logging.debug(f"Instagram expected_count: HTTP {resp.status_code}")
            return None

        data = resp.json()
        count = (
            (data.get('data') or {})
            .get('user', {})
            .get('edge_owner_to_timeline_media', {})
            .get('count')
        )
        if isinstance(count, int) and count > 0:
            logging.debug(f"Instagram expected_count: {count} posts")
            return count

    except Exception as e:
        logging.debug(f"Instagram expected_count error: {e}")

    return None


def _build_requests_session(
    cookie_file: str,
    platform_key: str,
    proxy: str = None,
    user_agent: str = None,
):
    """Create a requests session with cookies and headers applied."""
    try:
        import requests
    except Exception:
        return None

    session = requests.Session()

    if not user_agent:
        user_agent = _get_random_user_agent()

    session.headers.update({
        'User-Agent': user_agent,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.instagram.com/',
        'X-IG-App-ID': '936619743392459',
        'X-Requested-With': 'XMLHttpRequest',
    })

    if proxy:
        try:
            proxy_url = _parse_proxy_format(proxy)
            session.proxies.update({'http': proxy_url, 'https': proxy_url})
        except Exception:
            pass

    if cookie_file:
        cookies = _load_cookies_from_file(cookie_file, platform_key)
        for cookie in cookies:
            try:
                session.cookies.set(
                    cookie.get('name', ''),
                    cookie.get('value', ''),
                    domain=cookie.get('domain'),
                    path=cookie.get('path', '/') or '/',
                )
            except Exception:
                continue

        csrf_token = session.cookies.get('csrftoken')
        if csrf_token:
            session.headers['X-CSRFToken'] = csrf_token

    return session


def _find_instagram_profile_doc_id(session, username: str) -> typing.Optional[str]:
    """Best-effort discovery of Instagram profile posts doc_id from HTML."""
    try:
        response = session.get(f"https://www.instagram.com/{username}/", timeout=20)
        if response.status_code != 200 or not response.text:
            return None

        html = response.text
        operation_names = [
            'PolarisProfilePostsTabQuery',
            'PolarisProfilePostsPageQuery',
            'PolarisProfilePostsQuery',
        ]

        for op_name in operation_names:
            idx = html.find(op_name)
            if idx == -1:
                continue
            snippet = html[idx:idx + 600]
            match = re.search(r'doc_id\\?":\\?"(\d+)"', snippet)
            if match:
                return match.group(1)

        # Fallback: look for doc_id near "ProfilePosts" text
        match = re.search(r'ProfilePosts.{0,200}?doc_id\\?":\\?"(\d+)"', html, re.IGNORECASE)
        if match:
            return match.group(1)

    except Exception:
        return None

    return None


def _instagram_entry_from_node(node: dict) -> typing.Optional[dict]:
    """Convert a GraphQL/JSON node into a link entry."""
    shortcode = node.get('shortcode') or node.get('code')
    if not shortcode:
        return None

    product_type = (node.get('product_type') or '').lower()
    typename = node.get('__typename', '')
    is_video = bool(node.get('is_video'))

    if product_type == 'clips' or 'GraphReel' in typename:
        path = '/reel/'
    elif product_type == 'igtv':
        path = '/tv/'
    elif is_video and 'GraphVideo' in typename:
        path = '/reel/'
    else:
        path = '/p/'

    url = f"https://www.instagram.com{path}{shortcode}/"

    date_str = '00000000'
    timestamp = node.get('taken_at_timestamp') or node.get('taken_at') or node.get('date')
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        date_str = datetime.utcfromtimestamp(timestamp).strftime('%Y%m%d')

    caption = ''
    caption_edges = node.get('edge_media_to_caption', {}).get('edges', [])
    if caption_edges:
        caption = caption_edges[0].get('node', {}).get('text', '') or ''

    return {
        'url': url,
        'title': caption[:100] if caption else 'Instagram Post',
        'date': date_str,
    }


def _instagram_entries_from_media(media: dict) -> typing.List[dict]:
    """Extract entries from an Instagram media edge container."""
    entries: typing.List[dict] = []
    edges = media.get('edges', []) or []
    for edge in edges:
        node = edge.get('node', {}) if isinstance(edge, dict) else {}
        entry = _instagram_entry_from_node(node)
        if entry:
            entries.append(entry)
    return entries


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
    1. ip:port                                    Ã¢â€ â€™ http://ip:port
    2. user:pass@ip:port                          Ã¢â€ â€™ http://user:pass@ip:port
    3. ip:port:user:pass (provider format)        Ã¢â€ â€™ http://user:pass@ip:port
    4. socks5://user:pass@ip:port                 Ã¢â€ â€™ socks5://user:pass@ip:port
    5. With URL encoding for special chars        Ã¢â€ â€™ http://user:P%40ss@ip:port

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
            logging.warning(f"Ã¢Å¡Â Ã¯Â¸Â Unknown proxy format (parts={len(parts)}): {proxy[:30]}..., using as-is")
            return f"http://{proxy}"

    except Exception as e:
        logging.error(f"Ã¢ÂÅ’ Failed to parse proxy format: {e}")
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
        # Suppress SSL warnings for proxy testing (requests no longer exposes packages.urllib3 reliably)
        try:
            import urllib3
            from urllib3.exceptions import InsecureRequestWarning
            urllib3.disable_warnings(InsecureRequestWarning)
        except Exception:
            try:
                from requests.packages.urllib3.exceptions import InsecureRequestWarning
                requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            except Exception:
                pass

        # Parse proxy format (handles all 3 formats)
        proxy_url = _parse_proxy_format(proxy)
        logging.debug(f"Parsed proxy: {proxy} Ã¢â€ â€™ {proxy_url}")

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

        logging.debug(f"Ã¢ÂÂ±Ã¯Â¸Â Rate limit: waiting {delay:.2f}s for {platform_key}")
        time.sleep(delay)

    except Exception as e:
        # Fallback: 2-3 second delay
        import random
        logging.warning(f"Rate limit fallback due to error: {e}")
        time.sleep(random.uniform(2, 3))


def _get_ytdlp_binary_path() -> str:
    """
    Resolve yt-dlp with centralized path strategy.

    Returns:
        Path to yt-dlp binary or system command.
    """
    try:
        from modules.config.paths import find_ytdlp_executable

        cmd = find_ytdlp_executable()
        if not cmd:
            logging.warning("Ã¢Å¡Â  yt-dlp not found in bundled/system/C-drive paths")
            return 'yt-dlp'

        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                timeout=5,
                text=True,
                errors='replace'
            )
            if result.returncode == 0:
                version = (result.stdout or '').strip()
                logging.info(f"Ã¢Å“â€œ Using yt-dlp: {cmd} (v{version})")
                return cmd
            logging.warning(f"Ã¢Å¡Â  yt-dlp found but not runnable: {cmd}")
        except Exception as run_err:
            logging.warning(f"Ã¢Å¡Â  yt-dlp check failed for {cmd}: {run_err}")

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
        options['proxy'] = _parse_proxy_format(proxy)  # FIXED: Properly parse ip:port:user:pass format
    if user_agent:
        options['user_agent'] = user_agent

    # ===== APPROACH 1: Python API (Faster, Better Error Handling) =====
    # Compatibility guard: cookies-from-browser option shape differs across yt-dlp builds.
    # Prefer binary path when browser-cookie mode is requested.
    skip_python_api = bool(options.get('cookiesfrombrowser'))
    try:
        if skip_python_api:
            raise RuntimeError("skip_python_api_for_browser_cookies")

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
                    logging.debug(f"Ã¢Å“â€œ Python API success: {len(entries)} links")
                    return entries

    except Exception as e:
        if str(e) == "skip_python_api_for_browser_cookies":
            logging.debug("Skipping yt-dlp Python API because browser-cookie mode is enabled")
        else:
            logging.warning(f"Ã¢ÂÅ’ yt-dlp Python API failed:")
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
                logging.debug(f"Ã¢Å“â€œ Binary success: {len(entries)} links")
                return entries
            else:
                # No entries found - log detailed error info
                logging.warning(f"Ã¢ÂÅ’ yt-dlp binary returned 0 results:")
                logging.warning(f"   Command: {' '.join(cmd)}")
                logging.warning(f"   Exit code: {result.returncode}")
                if result.stdout:
                    logging.warning(f"   Stdout: {result.stdout[:500]}")
                if result.stderr:
                    logging.warning(f"   Stderr: {result.stderr[:500]}")

    except Exception as e:
        logging.warning(f"Ã¢ÂÅ’ yt-dlp binary exception:")
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


def _method_ytdlp_primary(
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
            from .config import get_instagram_feed_count
            feed_count = get_instagram_feed_count(max_videos)
            if feed_count > 0:
                options['extractor_args'] = {'instagram': {'feed_count': feed_count}}
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
            logging.warning(f"Ã¢ÂÅ’ Method 0 (Enhanced) returned 0 results:")
            logging.warning(f"   URL: {url}")
            logging.warning(f"   Both Python API and binary fallback failed")
            return []

    except Exception as e:
        logging.warning(f"Ã¢ÂÅ’ Method 0 (Enhanced) exception:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")

    return []


def _method_ytdlp_dump_json(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None, proxy: str = None, user_agent: str = None) -> typing.List[dict]:
    """METHOD 1: yt-dlp --dump-json (WITH DATES) - PRIMARY METHOD + Proxy + Chrome Headers"""
    try:
        cmd = [_get_ytdlp_binary_path(), '--dump-json', '--flat-playlist', '--ignore-errors', '--no-warnings']

        # ENHANCED: Add realistic Chrome 120 headers to avoid detection
        cmd.extend(_get_chrome120_headers())

        # Cookie handling: browser OR file (2025 approach)
        if cookie_browser:
            cmd.extend(['--cookies-from-browser', cookie_browser])
        elif cookie_file:
            cmd.extend(['--cookies', cookie_file])

        # Add proxy if available (CRITICAL for IP blocks)
        if proxy:
            proxy_url = _parse_proxy_format(proxy)  # FIXED: Properly parse ip:port:user:pass format
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
            from .config import get_instagram_feed_count
            feed_count = get_instagram_feed_count(max_videos)
            if feed_count > 0:
                cmd.extend(['--extractor-args', f'instagram:feed_count={feed_count}'])
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
            logging.warning(f"Ã¢ÂÅ’ Method 1 (--dump-json) returned 0 results:")
            logging.warning(f"   Command: {' '.join(cmd)}")
            logging.warning(f"   Exit code: {result.returncode}")
            if result.stdout:
                logging.warning(f"   Stdout: {result.stdout[:500]}")
            if result.stderr:
                logging.warning(f"   Stderr: {result.stderr[:500]}")

    except Exception as e:
        logging.warning(f"Ã¢ÂÅ’ Method 1 (--dump-json) exception:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")

    return []


def _method_ytdlp_get_url(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None, proxy: str = None) -> typing.List[dict]:
    """METHOD 2: yt-dlp --get-url (FAST, NO DATES) - SIMPLIFIED + Proxy + Chrome Headers"""
    try:
        # SIMPLE COMMAND like the working batch script: yt-dlp URL --flat-playlist --get-url
        cmd = [_get_ytdlp_binary_path(), '--flat-playlist', '--get-url', '--ignore-errors']

        # ENHANCED: Add realistic Chrome 120 headers to avoid detection
        cmd.extend(_get_chrome120_headers())

        # Cookie handling: browser OR file
        if cookie_browser:
            cmd.extend(['--cookies-from-browser', cookie_browser])
        elif cookie_file:
            cmd.extend(['--cookies', cookie_file])

        # Add proxy if available (CRITICAL for IP blocks)
        if proxy:
            proxy_url = _parse_proxy_format(proxy)  # FIXED: Properly parse ip:port:user:pass format
            cmd.extend(['--proxy', proxy_url])
            logging.debug(f"Method 2: Using proxy {proxy_url.split('@')[-1][:20]}...")

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        if platform_key == 'instagram':
            from .config import get_instagram_feed_count
            feed_count = get_instagram_feed_count(max_videos)
            if feed_count > 0:
                cmd.extend(['--extractor-args', f'instagram:feed_count={feed_count}'])

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
                logging.warning(f"Ã¢ÂÅ’ Method 2 (--get-url) returned 0 results:")
                logging.warning(f"   Command: {' '.join(cmd)}")
                logging.warning(f"   Exit code: {result.returncode}")
                logging.warning(f"   Raw output: {result.stdout[:500]}")
                if result.stderr:
                    logging.warning(f"   Stderr: {result.stderr[:500]}")
        else:
            # result.stdout is empty
            logging.warning(f"Ã¢ÂÅ’ Method 2 (--get-url) returned empty output:")
            logging.warning(f"   Command: {' '.join(cmd)}")
            logging.warning(f"   Exit code: {result.returncode}")
            if result.stderr:
                logging.warning(f"   Stderr: {result.stderr[:500]}")

    except Exception as e:
        logging.warning(f"Ã¢ÂÅ’ Method 2 (--get-url) exception:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")

    return []


def _method_ytdlp_with_retry(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, cookie_browser: str = None, proxy: str = None) -> typing.List[dict]:
    """METHOD 3: yt-dlp with retries (PERSISTENT) + Proxy + Chrome Headers"""
    try:
        cmd = [_get_ytdlp_binary_path(), '--dump-json', '--flat-playlist', '--ignore-errors',
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
            proxy_url = _parse_proxy_format(proxy)  # FIXED: Properly parse ip:port:user:pass format
            cmd.extend(['--proxy', proxy_url])
            logging.debug(f"Method 3: Using proxy {proxy_url.split('@')[-1][:20]}...")

        if max_videos > 0:
            cmd.extend(['--playlist-end', str(max_videos)])

        if platform_key == 'instagram':
            from .config import get_instagram_feed_count
            feed_count = get_instagram_feed_count(max_videos)
            if feed_count > 0:
                cmd.extend(['--extractor-args', f'instagram:feed_count={feed_count}'])

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
                logging.warning(f"Ã¢ÂÅ’ Method 3 (with retry) returned 0 results:")
                logging.warning(f"   Command: {' '.join(cmd)}")
                logging.warning(f"   Exit code: {result.returncode}")
                if result.stdout:
                    logging.warning(f"   Stdout: {result.stdout[:500]}")
                if result.stderr:
                    logging.warning(f"   Stderr: {result.stderr[:500]}")
        else:
            # result.stdout is empty
            logging.warning(f"Ã¢ÂÅ’ Method 3 (with retry) returned empty output:")
            logging.warning(f"   Command: {' '.join(cmd)}")
            logging.warning(f"   Exit code: {result.returncode}")
            if result.stderr:
                logging.warning(f"   Stderr: {result.stderr[:500]}")

    except Exception as e:
        logging.warning(f"Ã¢ÂÅ’ Method 3 (with retry) exception:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")

    return []


def _method_instagram_graphql(
    url: str,
    platform_key: str,
    cookie_file: str = None,
    max_videos: int = 0,
    proxy: str = None,
) -> typing.List[dict]:
    """METHOD 6b: Instagram Web API (cookies + GraphQL)"""
    if platform_key != 'instagram':
        return []

    if not cookie_file or not os.path.exists(cookie_file):
        logging.debug("Method 6b: No cookie file available for Instagram web API")
        return []

    username_match = re.search(r'instagram\.com/([^/?#]+)', url, flags=re.IGNORECASE)
    if not username_match or username_match.group(1) in ['p', 'reel', 'tv', 'stories']:
        return []

    username = username_match.group(1)

    session = _build_requests_session(cookie_file, platform_key, proxy=proxy)
    if not session:
        logging.debug("Method 6b: requests session unavailable")
        return []

    entries: typing.List[dict] = []

    # Step 1: fetch profile info (web API)
    profile_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    response = session.get(profile_url, timeout=30)

    if response.status_code != 200:
        # Fallback: try legacy __a=1 endpoint
        legacy_url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
        response = session.get(legacy_url, timeout=30)

    if response.status_code != 200:
        logging.debug(f"Method 6b: Profile info failed ({response.status_code})")
        return []

    try:
        payload = response.json()
    except Exception:
        logging.debug("Method 6b: Profile info JSON decode failed")
        return []

    user_data = payload.get('data', {}).get('user') or payload.get('graphql', {}).get('user')
    if not user_data:
        logging.debug("Method 6b: Profile info missing user data")
        return []

    media = user_data.get('edge_owner_to_timeline_media', {}) or {}
    entries.extend(_instagram_entries_from_media(media))

    if max_videos > 0 and len(entries) >= max_videos:
        return entries[:max_videos]

    page_info = media.get('page_info', {}) or {}
    end_cursor = page_info.get('end_cursor')
    has_next_page = bool(page_info.get('has_next_page'))
    user_id = user_data.get('id')

    if not user_id or not end_cursor or not has_next_page:
        return entries

    doc_id = _find_instagram_profile_doc_id(session, username)
    fallback_doc_ids = [
        "17888483320059182",
        "7898261790222653",
    ]

    doc_id_candidates = [doc_id] if doc_id else []
    doc_id_candidates.extend([d for d in fallback_doc_ids if d not in doc_id_candidates])

    graphql_url = "https://www.instagram.com/graphql/query/"

    for candidate in doc_id_candidates:
        cursor = end_cursor
        has_next = has_next_page
        pagination_added = False

        while has_next and cursor:
            remaining = max_videos - len(entries) if max_videos > 0 else 50
            batch_size = min(50, remaining) if remaining > 0 else 50

            variables = {
                'id': user_id,
                'first': batch_size,
                'after': cursor,
            }

            _apply_rate_limit('instagram')

            try:
                resp = session.get(
                    graphql_url,
                    params={'doc_id': candidate, 'variables': json.dumps(variables)},
                    timeout=30,
                )
            except Exception:
                logging.debug("Method 6b: GraphQL request error")
                break

            if resp.status_code != 200:
                logging.debug(f"Method 6b: GraphQL failed ({resp.status_code}) with doc_id {candidate}")
                break

            try:
                data = resp.json()
            except Exception:
                logging.debug("Method 6b: GraphQL JSON decode failed")
                break

            if data.get('status') == 'fail':
                logging.debug(f"Method 6b: GraphQL status fail: {data.get('message', '')[:120]}")
                break

            user_block = data.get('data', {}).get('user')
            if not user_block:
                logging.debug("Method 6b: GraphQL response missing user block")
                break

            media = user_block.get('edge_owner_to_timeline_media', {}) or {}
            new_entries = _instagram_entries_from_media(media)

            if new_entries:
                entries.extend(new_entries)
                pagination_added = True
            else:
                break

            if max_videos > 0 and len(entries) >= max_videos:
                return entries[:max_videos]

            page_info = media.get('page_info', {}) or {}
            has_next = bool(page_info.get('has_next_page'))
            cursor = page_info.get('end_cursor')

        if max_videos > 0 and len(entries) >= max_videos:
            break

        # If we fetched additional pages with this doc_id, stop trying other doc_ids
        if pagination_added:
            break

    return entries


def _method_instaloader(url: str, platform_key: str, cookie_file: str = None, max_videos: int = 0, proxy: str = None) -> typing.List[dict]:
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

        cookies_loaded = _apply_instaloader_session(loader, cookie_file, platform_key, proxy)
        if cookies_loaded:
            logging.info(f"Loaded {cookies_loaded} cookies for Instagram")

        profile = instaloader.Profile.from_username(loader.context, username)
        logging.info(f"Ã°Å¸â€œÅ  Instagram profile: @{username} ({profile.mediacount} posts)")

        entries = []
        seen_shortcodes = set()
        target_count = max_videos if max_videos > 0 else 0
        max_attempts = 3
        attempt = 0

        while attempt < max_attempts:
            try:
                for idx, post in enumerate(profile.get_posts(), 1):
                    shortcode = getattr(post, 'shortcode', None)
                    if not shortcode or shortcode in seen_shortcodes:
                        continue
                    seen_shortcodes.add(shortcode)
                    entries.append({
                        'url': f"https://www.instagram.com/p/{shortcode}/",
                        'title': (post.caption or 'Instagram Post')[:100],
                        'date': post.date_utc.strftime('%Y%m%d') if post.date_utc else '00000000'
                    })

                if not error_msg:
                    last_method_error = f"0_links:{method_id}"

                    # IP PROTECTION: Add delay between post fetches to avoid rate limiting
                    # Instagram allows ~1-2 requests per second, so we use 1.5-3 second delay
                    if idx > 1 and idx % 5 == 0:  # Every 5 posts, add a longer delay
                        delay = random.uniform(3.0, 5.0)
                        logging.debug(f"   Instaloader: Fetched {idx} posts, waiting {delay:.1f}s (IP protection)...")
                        time.sleep(delay)
                    else:
                        # Regular delay between posts
                        delay = random.uniform(1.5, 2.5)
                        time.sleep(delay)

                    # Progress logging every 50 posts
                    if idx % 50 == 0:
                        logging.info(f"Extracted {idx} Instagram posts...")

                    # Only break if limit is specified (0 means unlimited)
                    if target_count > 0 and len(entries) >= target_count:
                        logging.info(f"Reached Instagram limit of {target_count} posts")
                        break

                break  # Completed without error

            except Exception as e:
                attempt += 1
                if attempt >= max_attempts:
                    logging.error(f"Instaloader stopped after {attempt} attempts: {e}")
                    break
                cooldown = min(60, 10 * attempt)
                logging.warning(f"Instaloader retry {attempt}/{max_attempts} after error: {str(e)[:120]}")
                logging.warning(f"Cooling down for {cooldown}s before retry...")
                time.sleep(cooldown)

        # Sort by date (newest first)
        entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)
        logging.info(f"Ã¢Å“â€¦ Successfully extracted {len(entries)} Instagram posts")
        return entries

    except ImportError:
        logging.error("Ã¢ÂÅ’ Instaloader not installed. Install: pip install instaloader")
    except Exception as e:
        logging.error(f"Ã¢ÂÅ’ Method 5 (instaloader) failed: {e}")
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
            proxy_url = _parse_proxy_format(proxy)  # FIXED: Properly parse ip:port:user:pass format
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
    if platform_key not in ['tiktok', 'instagram', 'youtube', 'facebook']:
        return []

    try:
        from playwright.sync_api import sync_playwright
        import random

        logging.debug(f"Ã°Å¸Å½Â­ Starting Playwright method for {platform_key}")

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
                base_path / 'chromium' / 'chromium.exe',  # Windows (in chromium folder) Ã¢Å“â€¦ Your setup
                base_path / 'chromium.exe',                # Windows (direct)
                base_path / 'chromium' / 'chrome.exe',     # Windows (alternative name)
                base_path / 'chromium',                    # Linux/Mac (no extension)
            ]

            chromium_path = None
            for path in chromium_paths:
                if path.exists() and path.is_file():
                    chromium_path = path
                    logging.debug(f"Ã¢Å“â€œ Found bundled Chromium: {chromium_path}")
                    break

            if chromium_path:
                launch_options['executable_path'] = str(chromium_path)
                logging.debug(f"Ã¢Å“â€¦ Using bundled Chromium from bin/ folder")
            else:
                logging.debug(f"Ã¢Å¡Â Ã¯Â¸Â Bundled Chromium not found, using system Chromium (auto-download)")

            # ENHANCED: Add proxy if available
            if proxy:
                parsed_proxy = _parse_proxy_format(proxy)
                if parsed_proxy.startswith('http'):
                    # Extract proxy server (remove credentials for Playwright)
                    if '@' in parsed_proxy:
                        # Format: http://user:pass@ip:port
                        proxy_parts = parsed_proxy.split('@')
                        proxy_server = f"http://{proxy_parts[1]}"
                        logging.debug(f"Ã°Å¸Å’Â Playwright using proxy: {proxy_parts[1][:25]}...")
                    else:
                        proxy_server = parsed_proxy
                        logging.debug(f"Ã°Å¸Å’Â Playwright using proxy: {proxy_server[:25]}...")

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
                        logging.debug(f"Ã¢Å“â€œ Loaded {len(playwright_cookies)} cookies")
                    except Exception as e:
                        logging.debug(f"Cookie loading failed: {e}")

            page = context.new_page()

            # ENHANCED: Human-like page loading
            base_url_map = {
                'tiktok': 'https://www.tiktok.com/',
                'instagram': 'https://www.instagram.com/',
                'youtube': 'https://www.youtube.com/',
                'facebook': 'https://www.facebook.com/',
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

            elif platform_key == 'facebook':
                # Navigate to reels page for better video discovery
                reels_url = _facebook_reels_url(url)
                if reels_url != url:
                    try:
                        page.goto(reels_url, timeout=30000, wait_until='domcontentloaded')
                        time.sleep(random.uniform(2.0, 4.0))
                    except Exception:
                        pass

                previous_count = 0
                no_change_count = 0
                scroll_count = 0
                max_scrolls = 40 if max_videos == 0 else min(40, max_videos // 5 + 5)

                fb_links = []
                while no_change_count < 3 and scroll_count < max_scrolls:
                    fb_links = page.query_selector_all(
                        'a[href*="/reel/"], a[href*="/videos/"], a[href*="/watch/"], a[href*="/share/v/"]'
                    )
                    current_count = len(fb_links)

                    if current_count == previous_count:
                        no_change_count += 1
                    else:
                        no_change_count = 0

                    # Human-like scrolling
                    scroll_distance = random.randint(700, 1100)
                    page.evaluate(f"window.scrollBy(0, {scroll_distance})")
                    pause = random.uniform(1.5, 3.5)
                    time.sleep(pause)

                    previous_count = current_count
                    scroll_count += 1

                    if max_videos > 0 and current_count >= max_videos:
                        break

                for link in fb_links:
                    if max_videos > 0 and len(entries) >= max_videos:
                        break
                    href = link.get_attribute('href')
                    if not href:
                        continue
                    lower_href = href.lower()
                    if '/reel/' not in lower_href and '/videos/' not in lower_href and '/watch/' not in lower_href and '/share/v/' not in lower_href:
                        continue
                    full_url = href if href.startswith('http') else f"https://www.facebook.com{href}"
                    entries.append({'url': full_url, 'title': 'Facebook Video', 'date': '00000000'})

            context.close()
            browser.close()

            if entries:
                logging.debug(f"Ã¢Å“â€œ Playwright extracted {len(entries)} links")
            else:
                logging.debug(f"Ã¢Å¡Â Ã¯Â¸Â Playwright found 0 links")

            return entries

    except ImportError:
        logging.debug("Ã¢ÂÅ’ Playwright not installed (pip install playwright)")
    except Exception as e:
        logging.debug(f"Ã¢ÂÅ’ Method 7 (playwright) failed: {str(e)[:100]}")

    return []


def _method_selenium(
    url: str,
    platform_key: str,
    max_videos: int = 0,
    cookie_file: str = None,
    proxy: str = None,
    progress_callback=None,
    expected_count: int = 0
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
            proxy_url = _parse_proxy_format(proxy)  # FIXED: Properly parse ip:port:user:pass format
            options.add_argument(f'--proxy-server={proxy_url}')
            if progress_callback:
                progress_callback(f"Ã°Å¸Å’Â Selenium: Using proxy {proxy_url.split('@')[-1][:30]}...")
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
        if not cookies:
            # Try live browser extraction as fallback for explicit browser mode failures.
            tmp_cookie_file = _extract_browser_cookies(platform_key)
            if tmp_cookie_file:
                cookies = _load_cookies_from_file(tmp_cookie_file, platform_key)
                try:
                    os.unlink(tmp_cookie_file)
                except Exception:
                    pass
        base_url_map = {
            'tiktok': 'https://www.tiktok.com/',
            'instagram': 'https://www.instagram.com/',
            'youtube': 'https://www.youtube.com/',
            'facebook': 'https://www.facebook.com/',
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

        target_url = _facebook_reels_url(url) if platform_key == 'facebook' else url

        # Navigate to target URL
        if cookies_loaded:
            if progress_callback:
                progress_callback(f"Ã°Å¸ÂÂª Selenium: Cookies injected, loading target page...")
            driver.get(target_url)
        else:
            if progress_callback:
                progress_callback(f"Ã°Å¸Å’Â Selenium: Loading page (no cookies)...")
            driver.get(target_url)

        # Wait for page to load
        time.sleep(5)

        target_count = max_videos if max_videos > 0 else (expected_count or 0)

        # Platform-specific selectors
        selector_map = {
            'tiktok': 'a[href*="/video/"]',
            'instagram': 'a[href*="/p/"], a[href*="/reel/"], a[href*="/tv/"]',
            'youtube': 'a[href*="/watch?v="], a[href*="/shorts/"]',  # FIXED: Added Shorts support
            'facebook': 'a[href*="/reel/"], a[href*="/videos/"], a[href*="/watch/"], a[href*="/share/v/"], a[href*="reels/"]',
        }
        selector = selector_map.get(platform_key, 'a')

        def _normalize_instagram_href(href: str) -> str:
            if href.startswith('/'):
                href = f"https://www.instagram.com{href}"
            href = href.split('?')[0].split('#')[0].rstrip('/')
            return href + '/' if not href.endswith('/') else href

        def _instagram_login_gate() -> bool:
            try:
                if 'accounts/login' in (driver.current_url or ''):
                    return True
                if driver.find_elements(By.CSS_SELECTOR, 'a[href*="/accounts/login"]'):
                    return True
                if driver.find_elements(By.XPATH, "//*[contains(text(),'Log in') or contains(text(),'Login')]"):
                    return True
            except Exception:
                return False
            return False

        def _try_click_load_more() -> bool:
            if platform_key != 'instagram':
                return False
            try:
                buttons = driver.find_elements(
                    By.XPATH,
                    "//button//*[contains(text(),'Load more') or contains(text(),'Show more')]/.."
                )
                for btn in buttons:
                    try:
                        btn.click()
                        return True
                    except Exception:
                        continue
            except Exception:
                return False
            return False

        seen_urls: typing.Set[str] = set()
        scroll_attempts = 0
        stagnant_rounds = 0
        stagnant_limit = 3
        max_scrolls = 20

        if platform_key == 'instagram':
            stagnant_limit = 5
            if target_count:
                max_scrolls = min(200, max(40, target_count // 8 + 6))
            else:
                max_scrolls = 60
        elif platform_key == 'tiktok':
            max_scrolls = 40 if max_videos == 0 else min(60, max_videos // 5 + 5)
        elif platform_key == 'youtube':
            max_scrolls = 30 if max_videos == 0 else min(50, max_videos // 10 + 5)

        try:
            last_height = driver.execute_script("return document.body.scrollHeight")
        except Exception:
            last_height = None

        if progress_callback:
            progress_callback("Selenium: Scrolling and extracting links...")

        while scroll_attempts < max_scrolls and stagnant_rounds < stagnant_limit:
            links = driver.find_elements(By.CSS_SELECTOR, selector)
            before_count = len(seen_urls)

            for link in links:
                href = link.get_attribute('href')
                if not href:
                    continue
                if platform_key == 'tiktok' and '/video/' not in href:
                    continue
                if platform_key == 'instagram':
                    if '/p/' not in href and '/reel/' not in href and '/tv/' not in href:
                        continue
                    href = _normalize_instagram_href(href)
                if platform_key == 'facebook':
                    lower_href = href.lower()
                    if '/reel/' not in lower_href and '/videos/' not in lower_href and '/watch/' not in lower_href and '/share/v/' not in lower_href:
                        continue
                seen_urls.add(href)
                if target_count and len(seen_urls) >= target_count:
                    break

            if target_count and len(seen_urls) >= target_count:
                if progress_callback:
                    progress_callback(f"Selenium: Reached limit of {target_count} items")
                break

            new_links_found = len(seen_urls) - before_count
            try:
                current_height = driver.execute_script("return document.body.scrollHeight")
            except Exception:
                current_height = last_height

            height_changed = (
                current_height is not None
                and last_height is not None
                and current_height > last_height
            )

            if new_links_found == 0 and not height_changed:
                stagnant_rounds += 1
                if platform_key == 'instagram' and stagnant_rounds >= 2:
                    if _instagram_login_gate():
                        if progress_callback:
                            progress_callback("Selenium: Instagram login required - check cookies")
                        break
                    if _try_click_load_more():
                        stagnant_rounds = 0
                        time.sleep(random.uniform(1.5, 2.5))
                if progress_callback and stagnant_rounds == 1:
                    progress_callback(f"Selenium: No new links, continuing... ({len(seen_urls)} total)")
            else:
                stagnant_rounds = 0
                if progress_callback and scroll_attempts % 5 == 0:
                    progress_callback(f"Selenium: Found {len(seen_urls)} links so far...")

            last_height = current_height

            if platform_key == 'instagram':
                scroll_amount = random.randint(800, 1400)
                delay = random.uniform(2.0, 3.5)
            else:
                scroll_amount = random.randint(1200, 1800)
                delay = random.uniform(1.5, 2.5)

            driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
            time.sleep(delay)
            scroll_attempts += 1

        if progress_callback:
            progress_callback(f"Ã¢Å“â€¦ Selenium: Extraction complete - {len(seen_urls)} links found")

        entries = []
        limit = max_videos or len(seen_urls)
        for href in list(seen_urls)[:limit]:
            entries.append({'url': href, 'title': '', 'date': '00000000'})

        logging.info(f"Selenium method: Successfully extracted {len(entries)} links")
        return entries

    except ImportError:
        logging.warning("Ã¢ÂÅ’ Selenium not installed (pip install selenium)")
        if progress_callback:
            progress_callback("Ã¢ÂÅ’ Selenium not available - install with: pip install selenium")
    except Exception as e:
        logging.warning(f"Ã¢ÂÅ’ Selenium method failed:")
        logging.warning(f"   URL: {url}")
        logging.warning(f"   Error: {str(e)[:300]}")
        logging.warning(f"   Platform: {platform_key}")
        if proxy:
            logging.warning(f"   Proxy: {proxy.split('@')[-1][:30]}")
        if progress_callback:
            progress_callback(f"Ã¢ÂÅ’ Selenium error: {str(e)[:100]}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return []


def _extract_links_from_selenium_driver(
    driver,
    platform_key: str,
    max_videos: int = 0,
    expected_count: int = 0,
    progress_callback=None,
) -> typing.List[dict]:
    """Shared extractor for selenium drivers (headless/non-headless)."""
    selector_map = {
        'tiktok': 'a[href*="/video/"]',
        'instagram': 'a[href*="/p/"], a[href*="/reel/"], a[href*="/tv/"]',
        'youtube': 'a[href*="/watch?v="], a[href*="/shorts/"]',
        'facebook': 'a[href*="/reel/"], a[href*="/videos/"], a[href*="/watch/"], a[href*="/share/v/"], a[href*="reels/"]',
    }
    selector = selector_map.get(platform_key, 'a')

    target_count = max_videos if max_videos > 0 else (expected_count or 0)
    seen_urls: typing.Set[str] = set()
    scroll_attempts = 0
    stagnant_rounds = 0
    stagnant_limit = 3
    max_scrolls = 20

    if platform_key == 'instagram':
        stagnant_limit = 5
        if target_count:
            max_scrolls = min(200, max(40, target_count // 8 + 6))
        else:
            max_scrolls = 60
    elif platform_key == 'tiktok':
        max_scrolls = 40 if max_videos == 0 else min(60, max_videos // 5 + 5)
    elif platform_key == 'youtube':
        max_scrolls = 30 if max_videos == 0 else min(50, max_videos // 10 + 5)
    elif platform_key == 'facebook':
        max_scrolls = 40 if max_videos == 0 else min(70, max_videos // 5 + 6)

    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
    except Exception:
        last_height = None

    if progress_callback:
        progress_callback("Selenium: Scrolling and extracting links...")

    while scroll_attempts < max_scrolls and stagnant_rounds < stagnant_limit:
        try:
            links = driver.find_elements("css selector", selector)
        except Exception:
            links = []

        before_count = len(seen_urls)

        for link in links:
            href = link.get_attribute('href')
            if not href:
                continue
            lower_href = href.lower()
            if platform_key == 'tiktok' and '/video/' not in lower_href:
                continue
            if platform_key == 'instagram':
                if '/p/' not in lower_href and '/reel/' not in lower_href and '/tv/' not in lower_href:
                    continue
            if platform_key == 'facebook':
                if '/reel/' not in lower_href and '/videos/' not in lower_href and '/watch/' not in lower_href and '/share/v/' not in lower_href:
                    continue
            seen_urls.add(href)
            if target_count and len(seen_urls) >= target_count:
                break

        if target_count and len(seen_urls) >= target_count:
            if progress_callback:
                progress_callback(f"Selenium: Reached limit of {target_count} items")
            break

        new_links_found = len(seen_urls) - before_count
        try:
            current_height = driver.execute_script("return document.body.scrollHeight")
        except Exception:
            current_height = last_height

        height_changed = (
            current_height is not None
            and last_height is not None
            and current_height > last_height
        )

        if new_links_found == 0 and not height_changed:
            stagnant_rounds += 1
            if progress_callback and stagnant_rounds == 1:
                progress_callback(f"Selenium: No new links, continuing... ({len(seen_urls)} total)")
        else:
            stagnant_rounds = 0
            if progress_callback and scroll_attempts % 5 == 0:
                progress_callback(f"Selenium: Found {len(seen_urls)} links so far...")

        last_height = current_height

        if platform_key in {'instagram', 'facebook'}:
            scroll_amount = random.randint(800, 1400)
            delay = random.uniform(2.0, 3.5)
        else:
            scroll_amount = random.randint(1200, 1800)
            delay = random.uniform(1.5, 2.5)

        try:
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        except Exception:
            pass
        time.sleep(delay)
        scroll_attempts += 1

    entries: typing.List[dict] = []
    for href in sorted(seen_urls):
        entries.append({
            'url': href,
            'title': f'{platform_key.title()} Video',
            'date': '00000000',
        })
    return entries


def _save_driver_cookies_to_file(driver, cookies_dir: Path, platform_key: str) -> typing.Optional[str]:
    """Persist selenium session cookies to Netscape file for reuse by yt-dlp methods."""
    try:
        tokens = _platform_domain_tokens(platform_key)
        cookies = driver.get_cookies() or []
        filtered = []
        for c in cookies:
            domain = (c.get('domain') or '').lower()
            if not tokens or any(token in domain for token in tokens):
                filtered.append(c)
        if not filtered:
            return None

        cookies_dir.mkdir(parents=True, exist_ok=True)
        out = cookies_dir / "chrome_cookies.txt"
        with open(out, 'w', encoding='utf-8') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# Saved from interactive browser session\n\n")
            for c in filtered:
                domain = c.get('domain', '')
                flag = 'TRUE' if str(domain).startswith('.') else 'FALSE'
                path = c.get('path', '/') or '/'
                secure = 'TRUE' if c.get('secure', False) else 'FALSE'
                expires = str(int(c.get('expiry', 0) or 0))
                name = c.get('name', '')
                value = c.get('value', '')
                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
        return str(out)
    except Exception:
        return None


def _method_selenium_profile(
    url: str,
    platform_key: str,
    cookies_dir: Path,
    max_videos: int = 0,
    progress_callback=None,
) -> typing.List[dict]:
    """
    Try to reuse an already logged-in local Chrome profile before manual login fallback.
    """
    if platform_key not in {'instagram', 'facebook'}:
        return []

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except Exception:
        return []

    browser_roots = _iter_browser_profile_roots()
    if not browser_roots:
        return []

    running = _get_running_browser_names()
    if running:
        # Prefer currently running browsers first as user requested.
        browser_roots.sort(key=lambda item: 0 if item[0] in running else 1)

    seed_url_map = {
        'instagram': 'https://www.instagram.com/',
        'facebook': 'https://www.facebook.com/',
    }
    seed_url = seed_url_map.get(platform_key, url)
    target_url = _facebook_reels_url(url) if platform_key == 'facebook' else url

    for browser_name, root in browser_roots:
        preferred = ["Default"] + sorted([
            p.name for p in root.iterdir()
            if p.is_dir() and p.name.startswith("Profile ")
        ])[:6]
        profile_candidates = [p for p in preferred if (root / p).exists()]

        for profile_name in profile_candidates:
            driver = None
            try:
                if progress_callback:
                    progress_callback(f"Checking existing {browser_name.title()} session ({profile_name})...")

                options = Options()
                options.add_argument('--start-maximized')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                options.add_argument(f'--user-agent={_get_random_user_agent()}')
                options.add_argument(f'--user-data-dir={root}')
                options.add_argument(f'--profile-directory={profile_name}')

                driver = webdriver.Chrome(options=options)
                driver.set_page_load_timeout(45)

                driver.get(seed_url)
                time.sleep(2.5)
                driver.get(target_url)
                time.sleep(4)

                entries = _extract_links_from_selenium_driver(
                    driver,
                    platform_key=platform_key,
                    max_videos=max_videos,
                    expected_count=0,
                    progress_callback=progress_callback,
                )
                if entries:
                    saved_cookie = _save_driver_cookies_to_file(driver, cookies_dir, platform_key)
                    if saved_cookie and progress_callback:
                        progress_callback(f"Existing session cookies saved to {Path(saved_cookie).name}")
                    if progress_callback:
                        progress_callback(
                            f"Existing browser session success ({browser_name}:{profile_name}): {len(entries)} links"
                        )
                    return entries
            except Exception as e:
                msg = str(e).lower()
                if progress_callback:
                    if "user data directory is already in use" in msg:
                        progress_callback(f"{browser_name}:{profile_name} is locked; trying next profile...")
                    else:
                        progress_callback(f"{browser_name}:{profile_name} session check failed; trying next profile...")
            finally:
                try:
                    if driver:
                        driver.quit()
                except Exception:
                    pass

    return []


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Method B: Instagram Mobile API
# Uses the official Instagram mobile-app API endpoints.
# Works with just the sessionid cookie â€” no scraping, no bot detection.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _method_instagram_mobile_api(
    url: str,
    platform_key: str,
    cookie_file: str = None,
    max_videos: int = 0,
    proxy: str = None,
) -> typing.List[dict]:
    """
    Method B: Instagram Mobile API (i.instagram.com/api/v1/)

    Calls Instagram's official mobile-app REST API.
    Requires a valid `sessionid` cookie â€” no scraping, no HTML parsing,
    no bot-detection issues.  Returns ALL posts/reels with page URLs.
    """
    if platform_key != 'instagram':
        return []

    import re as _re

    # --- extract username from URL -----------------------------------------
    m = _re.search(r'instagram\.com/([^/?#\s]+)', url)
    if not m:
        logging.debug("InstaMobileAPI: cannot extract username from URL")
        return []
    username = m.group(1).strip('/')
    # Skip non-profile URL segments
    if username in ('p', 'reel', 'tv', 'explore', 'accounts',
                    'stories', 'direct', 'reels', 'login', 'oauth'):
        logging.debug(f"InstaMobileAPI: URL is not a profile page ({username})")
        return []

    # --- get sessionid from cookie file ------------------------------------
    sessionid = None
    csrftoken  = None
    if cookie_file:
        for c in _load_cookies_from_file(cookie_file, 'instagram'):
            if c.get('name') == 'sessionid':
                sessionid = c.get('value')
            elif c.get('name') == 'csrftoken':
                csrftoken = c.get('value')

    if not sessionid:
        logging.debug("InstaMobileAPI: no sessionid in cookie file â€” skipping")
        return []

    try:
        import requests as _req
    except ImportError:
        return []

    mobile_ua = (
        'Instagram 220.0.0.30.070 Android '
        '(33/13; 420dpi; 1080x2400; Google/google; Pixel 7; lynx; lynx; en_US; 354243946)'
    )
    session = _req.Session()
    session.headers.update({
        'User-Agent': mobile_ua,
        'X-IG-App-ID': '936619743392459',
        'Accept': '*/*',
        'Accept-Language': 'en-US',
        'Accept-Encoding': 'gzip, deflate',
    })
    if csrftoken:
        session.headers['X-CSRFToken'] = csrftoken
    session.cookies.set('sessionid', sessionid, domain='.instagram.com')
    if csrftoken:
        session.cookies.set('csrftoken', csrftoken, domain='.instagram.com')

    if proxy:
        pu = _parse_proxy_format(proxy)
        session.proxies.update({'http': pu, 'https': pu})

    # --- step 1: resolve user_id -------------------------------------------
    try:
        r = session.get(
            f'https://i.instagram.com/api/v1/users/web_profile_info/?username={username}',
            timeout=15,
        )
        r.raise_for_status()
        user_id = r.json().get('data', {}).get('user', {}).get('id')
        if not user_id:
            logging.debug(f"InstaMobileAPI: user_id not found for @{username}")
            return []
        logging.debug(f"InstaMobileAPI: user_id={user_id} for @{username}")
    except Exception as exc:
        logging.debug(f"InstaMobileAPI: user lookup failed: {exc}")
        return []

    # --- step 2: paginate feed ---------------------------------------------
    results: typing.List[dict] = []
    limit   = max_videos if max_videos > 0 else 200
    max_id  = None

    for page in range(15):  # max 15 pages Ã— 50 = 750 posts
        if len(results) >= limit:
            break

        params: dict = {'count': min(50, limit - len(results))}
        if max_id:
            params['max_id'] = max_id

        try:
            r = session.get(
                f'https://i.instagram.com/api/v1/feed/user/{user_id}/',
                params=params,
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logging.debug(f"InstaMobileAPI: feed page {page+1} failed: {exc}")
            break

        items = data.get('items', [])
        if not items:
            break

        for item in items:
            shortcode = item.get('code', '')
            if not shortcode:
                continue
            post_url = f'https://www.instagram.com/p/{shortcode}/'

            caption   = item.get('caption') or {}
            title     = (caption.get('text', '') or '')[:120] if isinstance(caption, dict) else ''
            taken_at  = item.get('taken_at', 0)
            date_str  = '00000000'
            if taken_at:
                try:
                    import datetime as _dt
                    date_str = _dt.datetime.fromtimestamp(taken_at).strftime('%Y%m%d')
                except Exception:
                    pass

            results.append({
                'url':   post_url,
                'title': title or f'Instagram post by @{username}',
                'date':  date_str,
            })
            if len(results) >= limit:
                break

        if not data.get('more_available', False):
            break
        max_id = items[-1].get('pk', '') if items else ''
        if not max_id:
            break
        time.sleep(random.uniform(0.8, 1.5))

    logging.info(f"InstaMobileAPI: {len(results)} posts fetched for @{username}")
    return results


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Method C: Facebook Page HTML / JSON extraction
# Parses the structured JSON blobs Facebook embeds in every page.
# Works with c_user + xs + datr cookies â€” no Selenium required.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _method_facebook_json(
    url: str,
    platform_key: str,
    cookie_file: str = None,
    max_videos: int = 0,
    proxy: str = None,
) -> typing.List[dict]:
    """
    Method C: Facebook page-source JSON extraction.

    Facebook embeds all post/video data inside structured JSON within the
    page HTML (relay store / __SSR_INITIAL_STATE__).  We fetch the page
    with valid login cookies and extract every reel/video/watch link via
    regex over the raw JSON text.
    """
    if platform_key != 'facebook':
        return []

    import re as _re

    session = _build_requests_session(cookie_file, 'facebook', proxy=proxy)
    if not session:
        return []

    # Ensure we land on the videos/reels page for profile URLs
    target_url = url
    if not any(kw in url for kw in ('/videos', '/reels', '/watch', '/reel/')):
        if _re.search(r'facebook\.com/[^/]+/?$', url):
            target_url = url.rstrip('/') + '/videos'

    try:
        r = session.get(target_url, timeout=20, allow_redirects=True)
        if r.url and 'login' in r.url:
            logging.debug("FacebookJSON: redirected to login (cookies not valid)")
            return []
        html = r.text
    except Exception as exc:
        logging.debug(f"FacebookJSON: page fetch failed: {exc}")
        return []

    results: typing.List[dict] = []
    seen:    typing.Set[str]   = set()
    limit    = max_videos if max_videos > 0 else 500

    patterns = [
        # Full https URLs embedded in JSON
        r'"(https://www\.facebook\.com/(?:reel|watch)/[^"?]{5,120})"',
        r'"(https://www\.facebook\.com/[^"?]+/videos/\d+[^"]{0,50})"',
        r'"(https://www\.facebook\.com/watch/\?v=\d+[^"]{0,100})"',
        # Relative paths inside JSON
        r'"(/reel/[^"?]{5,100})"',
        r'"(/watch/\?v=\d+[^"]{0,100})"',
        r'"(/[^/"?]+/videos/\d+[^"]{0,80})"',
        # href= attributes in HTML
        r'href="(https://www\.facebook\.com/reel/[^"?]+)"',
        r'href="(/reel/[^"?]+)"',
    ]

    for pat in patterns:
        for m in _re.finditer(pat, html):
            raw = m.group(1)
            raw = raw.replace('\\/', '/').replace('\\u0026', '&')
            if raw.startswith('/'):
                raw = 'https://www.facebook.com' + raw
            # Normalise: keep ?v= param for /watch/ but drop everything else
            if '/watch' in raw and '?v=' in raw:
                clean = raw.split('&')[0]
            else:
                clean = raw.split('?')[0].rstrip('/')
            if not _re.search(r'/(reel|videos|watch)', clean):
                continue
            if clean in seen:
                continue
            seen.add(clean)
            results.append({'url': clean, 'title': '', 'date': '00000000'})
            if len(results) >= limit:
                break
        if len(results) >= limit:
            break

    logging.info(f"FacebookJSON: {len(results)} video links from page HTML")
    return results


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Method D: Attach Selenium to already-running Chrome via CDP debug port
# Works when Chrome is running with --remote-debugging-port (e.g. after Phase 3b
# cookie extraction relaunched Chrome).  Uses the REAL logged-in session.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _method_selenium_cdp_attach(
    url: str,
    platform_key: str,
    max_videos: int = 0,
    progress_callback=None,
    expected_count: int = 0,
) -> typing.List[dict]:
    """
    Method D: Attach Selenium to the user's running Chrome via CDP debug port.

    Connects to localhost:9222 (or 9223/9224/9229) â€” no new browser launched,
    no headless, no cookies needed.  Uses Chrome exactly as the user sees it,
    fully logged in to all platforms.

    NOTE: We deliberately do NOT call driver.quit() to avoid closing the user's
    Chrome window.  We only stop the ChromeDriver service process.
    """
    import socket as _sock

    cdp_port = None
    for port in [9222, 9223, 9224, 9229]:
        try:
            s = _sock.create_connection(("localhost", port), timeout=0.5)
            s.close()
            cdp_port = port
            break
        except (ConnectionRefusedError, OSError):
            continue

    if cdp_port is None:
        return []

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except Exception:
        return []

    options = Options()
    options.add_experimental_option("debuggerAddress", f"localhost:{cdp_port}")

    driver = None
    try:
        if progress_callback:
            progress_callback(f"Method D: Attaching to running Chrome (port {cdp_port})...")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(4)

        entries = _extract_links_from_selenium_driver(
            driver,
            platform_key=platform_key,
            max_videos=max_videos,
            expected_count=expected_count,
            progress_callback=progress_callback,
        )
        if progress_callback and entries:
            progress_callback(f"Method D (CDP attach): {len(entries)} links found")
        return entries

    except Exception as exc:
        logging.debug(f"Method D (CDP attach): {exc}")
        return []
    finally:
        # Stop ChromeDriver service WITHOUT closing the user's Chrome browser.
        try:
            if driver and driver.service:
                driver.service.stop()
        except Exception:
            pass


def _method_interactive_browser_session(
    url: str,
    platform_key: str,
    cookies_dir: Path,
    max_videos: int = 0,
    proxy: str = None,
    progress_callback=None,
    wait_seconds: int = 90,
) -> typing.List[dict]:
    """
    Final fallback:
    Opens visible browser, asks user to login manually, then extracts links from live session.
    """
    driver = None
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        # Visible browser so user can login.
        options.add_argument('--start-maximized')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(f'--user-agent={_get_random_user_agent()}')

        if proxy:
            proxy_url = _parse_proxy_format(proxy)
            options.add_argument(f'--proxy-server={proxy_url}')
            if progress_callback:
                progress_callback(f"Interactive browser: using proxy {_mask_proxy(proxy_url)}")

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)

        seed_url_map = {
            'instagram': 'https://www.instagram.com/',
            'facebook': 'https://www.facebook.com/',
            'youtube': 'https://www.youtube.com/',
            'tiktok': 'https://www.tiktok.com/',
        }
        seed_url = seed_url_map.get(platform_key, url)
        target_url = _facebook_reels_url(url) if platform_key == 'facebook' else url
        driver.get(seed_url)

        if progress_callback:
            progress_callback("=" * 40)
            progress_callback("Manual login required:")
            progress_callback(f"1) Login in opened browser window ({platform_key.title()})")
            progress_callback(f"2) Keep window open; waiting up to {wait_seconds} seconds")
            progress_callback("3) After login completes, extraction continues automatically")
            progress_callback("=" * 40)

        for sec in range(wait_seconds):
            time.sleep(1)
            if platform_key == 'facebook':
                try:
                    current = (driver.current_url or "").lower()
                    has_session = any(c.get('name') == 'c_user' for c in (driver.get_cookies() or []))
                    if has_session and 'login' not in current:
                        if progress_callback:
                            progress_callback("Facebook login detected. Continuing extraction now...")
                        break
                except Exception:
                    pass
            elif platform_key == 'instagram':
                try:
                    current = (driver.current_url or "").lower()
                    has_session = any(c.get('name') == 'sessionid' for c in (driver.get_cookies() or []))
                    if has_session and 'accounts/login' not in current:
                        if progress_callback:
                            progress_callback("Instagram login detected. Continuing extraction now...")
                        break
                except Exception:
                    pass
            if progress_callback and sec in {15, 30, 45, 60, 75}:
                progress_callback(f"Waiting for manual login... {wait_seconds - sec}s left")

        driver.get(target_url)
        time.sleep(4)

        entries = _extract_links_from_selenium_driver(
            driver,
            platform_key=platform_key,
            max_videos=max_videos,
            expected_count=0,
            progress_callback=progress_callback,
        )

        saved_cookie = _save_driver_cookies_to_file(driver, cookies_dir, platform_key)
        if saved_cookie and progress_callback:
            progress_callback(f"Session cookies saved to {Path(saved_cookie).name}")

        return entries
    except Exception as e:
        if progress_callback:
            progress_callback(f"Interactive browser fallback failed: {str(e)[:120]}")
        return []
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass


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
        use_instaloader = bool(options.get('use_instaloader', False))
        interactive_login_fallback = bool(options.get('interactive_login_fallback', True))
        manual_login_wait_seconds = int(options.get('manual_login_wait_seconds', 90) or 90)
        managed_profile_only = bool(options.get('managed_profile_only', False))
        cookie_browser = options.get('cookie_browser')  # "chrome", "firefox", "edge", or None
        explicit_browser_mode = bool(cookie_browser)
        if managed_profile_only:
            # CreatorProfile-safe mode: avoid touching local user browser profiles.
            cookie_browser = None
            explicit_browser_mode = False
            interactive_login_fallback = False
        url = _normalize_source_url(url, platform_key)
        creator = _extract_creator_from_url(url, platform_key)

        # Get learning system
        learning_system = get_learning_system()

        # Cookie handling: browser OR file
        cookie_file = None
        temp_cookie_files: typing.List[str] = []
        _auth_source_id: typing.Optional[str] = None  # tracks which source provided cookies

        # ── Managed-profile auth fallback chain ───────────────────────
        # When running in CreatorProfile mode (managed_profile_only),
        # use the AuthFallbackChain to resolve cookies with proper
        # priority, cooldown awareness, and source memory.
        if managed_profile_only:
            try:
                from modules.shared.session_authority import AuthFallbackChain
                _chain = AuthFallbackChain()
                cookie_file, _auth_source_id = _chain.resolve_cookie(
                    platform_key, creator=creator,
                )
                if cookie_file and progress_callback:
                    progress_callback(f"Cookies ready ({Path(cookie_file).name})")
                elif not cookie_file and progress_callback:
                    progress_callback("No authenticated cookies available. Trying API methods...")
            except Exception as _chain_err:
                logging.debug("[AuthFallbackChain] init/resolve failed: %s", _chain_err)

        browser_cookie_extract_failed = False
        if cookie_browser:
            if progress_callback:
                progress_callback(f"Cookie source: Browser ({cookie_browser.title()})")
            extracted = _extract_browser_cookies(platform_key, cookie_browser)
            if extracted:
                temp_cookie_files.append(extracted)
                cookie_file = extracted
            else:
                browser_cookie_extract_failed = True
                if progress_callback:
                    progress_callback("Browser cookie extraction failed (browser DB lock or access denied).")
                    progress_callback("Trying Chrome DB copy method (Workflow 1)...")
                # Try Workflow 1: copy locked Chrome/Edge DB to temp and decrypt
                extracted = _extract_browser_cookies_db_copy(platform_key, preferred_browser=cookie_browser, cookies_dir=cookies_dir, progress_callback=progress_callback)
                if extracted:
                    temp_cookie_files.append(extracted)
                    cookie_file = extracted
                    if progress_callback:
                        progress_callback("Cookie source: Chrome DB copy (bypassed lock)")
                else:
                    if progress_callback:
                        progress_callback("DB copy failed. Switching to saved cookie file fallback.")
                # Reset so file fallback below is always attempted
                explicit_browser_mode = False
                cookie_browser = None

        if not cookie_file and not explicit_browser_mode and not managed_profile_only:
            cookie_file = _find_cookie_file(cookies_dir, platform_key)
            if cookie_file and progress_callback:
                progress_callback(f"Cookie source: Saved file ({Path(cookie_file).name})")

        # If still no cookies â†’ auto-run Workflow 1 (smart browser extraction)
        if not cookie_file and not explicit_browser_mode and not managed_profile_only:
            if progress_callback:
                progress_callback("No saved cookies found. Running Workflow 1 (smart browser detection)...")
            extracted = _extract_browser_cookies_db_copy(
                platform_key,
                cookies_dir=cookies_dir,
                progress_callback=progress_callback,
            )
            if extracted:
                temp_cookie_files.append(extracted)
                cookie_file = extracted

        if not cookie_file and not explicit_browser_mode and not managed_profile_only:
            extracted = _extract_browser_cookies(platform_key)
            if extracted:
                temp_cookie_files.append(extracted)
                cookie_file = extracted

        if cookie_file and progress_callback:
            cookie_name = Path(cookie_file).name
            progress_callback(f"Cookies file: {cookie_name}")

            # ENHANCED: Validate cookie freshness and quality
            validation = _validate_cookie_file(cookie_file, max_age_days=14)
            if validation['warnings']:
                for warning in validation['warnings']:
                    progress_callback(f"   {warning}")
            else:
                # Show cookie stats if valid and fresh
                progress_callback(f"   OK: {validation['total_cookies']} cookies, {validation['age_days']} days old")

        # If we've materialized a cookie file, stop passing cookie_browser to yt-dlp.
        # yt-dlp's --cookies-from-browser mode ignores manual files and was causing 0 results
        # when users selected "Use Browser" but only had exported Netscape cookies.
        if cookie_file:
            cookie_browser = None

        entries: typing.List[dict] = []
        seen_normalized: typing.Set[str] = set()
        pre_successful_method: typing.Optional[str] = None
        successful_method_id: str = ""
        auth_manager = None
        if ChromiumAuthManager is not None:
            try:
                auth_manager = ChromiumAuthManager()
            except Exception:
                auth_manager = None

        # Extract proxy settings from options (support for 1-2 proxies)
        proxy_list = options.get('proxies', []) or []
        parsed_proxies: typing.List[str] = []
        for p in proxy_list:
            parsed = _parse_proxy_format(p)
            if parsed:
                parsed_proxies.append(parsed)
        active_proxy = parsed_proxies[0] if parsed_proxies else None  # Use first proxy if available
        use_enhancements = options.get('use_enhancements', True)  # Enable enhancements by default
        from .config import get_exhaustive_mode
        exhaustive_mode = force_all_methods or get_exhaustive_mode()

        expected_count = None
        if platform_key == 'instagram' and exhaustive_mode:
            expected_count = _get_instagram_expected_count(url, cookie_file, active_proxy)

        target_count = max_videos if max_videos > 0 else (expected_count or 0)

        # â”€â”€ Step 2.3: Intelligent tab detection for profile URLs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        url_type = detect_platform_url_type(url, platform_key)
        # Canonical base URL (no trailing slash) used by the fallback loop
        _profile_base_url = url.rstrip('/')
        _chosen_tab: str = ''
        _available_tabs: typing.List[str] = []

        if url_type == 'profile' and platform_key == 'youtube':
            cached_tab: typing.Optional[str] = None
            if learning_system:
                try:
                    cached_tab = learning_system.get_best_tab(creator, platform_key)
                except Exception:
                    cached_tab = None

            _available_tabs = ['videos', 'shorts']
            _chosen_tab = cached_tab if cached_tab in _available_tabs else 'videos'
            if progress_callback:
                progress_callback("YouTube: Will grab from both /videos and /shorts tabs")

            original_url = url
            url = f"{_profile_base_url}/{_chosen_tab}"
            if progress_callback:
                progress_callback(f"URL normalized: {original_url} -> {url}")

        # Store for tab fallback loop (used after main method loop)
        options['_chosen_tab'] = _chosen_tab
        options['_available_tabs'] = _available_tabs
        options['_url_type'] = url_type
        options['_profile_base_url'] = _profile_base_url

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
            progress_callback("-" * 32)
            progress_callback("Extraction Configuration:")
            progress_callback(f"   Creator: @{creator}")
            progress_callback(f"   Platform: {platform_key.title()}")
            progress_callback(f"   yt-dlp: v{ytdlp_version} ({ytdlp_location})")
            if active_proxy:
                progress_callback(f"   Proxy: {_mask_proxy(active_proxy)}")
            if cookie_file:
                progress_callback("   Cookies: File loaded")
            elif explicit_browser_mode:
                if browser_cookie_extract_failed:
                    progress_callback("   Cookies: Browser mode requested (direct extraction unavailable)")
                else:
                    progress_callback(f"   Cookies: Browser mode ({cookie_browser})")
            if max_videos > 0:
                progress_callback(f"   Limit: {max_videos} videos")
            else:
                progress_callback("   Limit: All videos (unlimited)")
            if expected_count:
                progress_callback(f"   Expected posts: {expected_count}")
            if use_enhancements:
                progress_callback("   Enhancements: Enabled (Dual yt-dlp + UA Rotation)")
            progress_callback("-" * 32)

        if (
            not entries
            and auth_manager is not None
            and auth_manager.is_setup_complete()
        ):
            if progress_callback:
                progress_callback("Layer 1: Chromium browser extraction (saved profile)...")
            content_filter_type = {
                'youtube': 'all_videos',
                'tiktok': 'all_videos',
                'instagram': 'reels_only',
                'twitter': 'video_tweets',
                'facebook': 'videos_reels',
            }.get(platform_key, 'all')
            browser_source_url = (
                _profile_base_url
                if (platform_key == 'youtube' and url_type == 'profile')
                else url
            )

            try:
                browser_entries = auth_manager.grab_links_via_browser(
                    url=browser_source_url,
                    platform_key=platform_key,
                    content_filter=content_filter_type,
                    max_items=max_videos,
                    progress_callback=progress_callback,
                )
                if browser_entries:
                    if ContentFilter:
                        cf = ContentFilter()
                        browser_entries = cf.filter_entries(browser_entries, platform_key)

                    for entry in browser_entries:
                        normalized = _normalize_url(entry.get('url', ''))
                        if not normalized or normalized in seen_normalized:
                            continue
                        seen_normalized.add(normalized)
                        entries.append(entry)

                    if entries:
                        pre_successful_method = "Chromium Browser (saved profile)"
                        if progress_callback:
                            progress_callback(f"Chromium browser: {len(entries)} links extracted")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Chromium browser failed: {str(e)[:100]}")
                try:
                    login_status = auth_manager.get_login_status()
                except Exception:
                    login_status = {}
                if not login_status.get(platform_key, False):
                    if progress_callback:
                        progress_callback(
                            f"Session expired for {platform_key}. Attempting silent re-login..."
                        )
                    relogin_success = auth_manager.attempt_silent_relogin(platform_key)
                    if not relogin_success and progress_callback:
                        progress_callback(
                            "Silent re-login failed. Please re-login manually in Settings."
                        )

        # Requested browser-mode flow:
        # 1) Try existing logged-in local browser session first (no manual prompt)
        # 2) If not found, continue normal methods
        # 3) Ask manual login only at final fallback
        if (
            not entries
            and platform_key in {'instagram', 'facebook'}
            and explicit_browser_mode
            and browser_cookie_extract_failed
        ):
            if progress_callback:
                progress_callback("Trying existing logged-in browser sessions before standard methods...")
            pre_entries = _method_selenium_profile(
                url=url,
                platform_key=platform_key,
                cookies_dir=cookies_dir,
                max_videos=max_videos,
                progress_callback=progress_callback,
            ) or []
            for entry in pre_entries:
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

        if (
            not entries
            and auth_manager is not None
            and not cookie_file
            and auth_manager.is_setup_complete()
        ):
            extracted_cookie = auth_manager.extract_cookies_for_platform(platform_key)
            if extracted_cookie:
                cookie_file = extracted_cookie
                cookie_browser = None
                if progress_callback:
                    progress_callback(
                        "Layer 2: Using cookies from browser profile for library methods..."
                    )

        # ── Managed CDP attach-first path ──────────────────────────────
        # When feature flag is ON, try extracting via the managed Chrome CDP
        # session BEFORE the normal method chain.  This uses the real
        # logged-in Chrome session and requires no cookies.
        if not entries:
            try:
                from modules.shared.managed_chrome_session import (
                    MANAGED_CDP_ATTACH_FIRST,
                    extract_links_via_managed_cdp,
                )
                if MANAGED_CDP_ATTACH_FIRST:
                    if platform_key == "tiktok":
                        logging.info(
                            "[TikTokPath] CDP attach-first: attempting attach-only "
                            "(no browser launch) for %s", url[:80],
                        )
                    cdp_entries = extract_links_via_managed_cdp(
                        url=url,
                        platform_key=platform_key,
                        max_videos=max_videos,
                        progress_callback=progress_callback,
                        expected_count=expected_count or 0,
                    )
                    if not cdp_entries and platform_key == "tiktok":
                        logging.info(
                            "[TikTokPath][ManagedCDP-Fallback] CDP returned 0 links "
                            "— falling back to normal extraction chain"
                        )
                    for entry in (cdp_entries or []):
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
                    if entries:
                        pre_successful_method = "Managed Chrome CDP"
                        successful_method_id = "managed_cdp_attach"
                        if progress_callback:
                            progress_callback(f"Found {len(entries)} links (managed session)")
            except ImportError:
                pass
            except Exception as _cdp_err:
                logging.debug("[ManagedCDP] attach-first failed: %s", _cdp_err)

        # Define all available methods
        # PRIORITY ORDER: Fast API methods first, browser methods as fallback
        all_methods = [
            # â”€â”€ yt-dlp methods (YouTube, TikTok, Facebook â€” NOT Instagram) â”€â”€
            ("Method 0: yt-dlp primary (Dual API + Proxy + UA Rotation)",
             lambda: _method_ytdlp_primary(url, platform_key, cookie_file, max_videos, cookie_browser, active_proxy),
             "ytdlp_primary",
             use_enhancements),

            ("Method 2: yt-dlp --get-url",
             lambda: _method_ytdlp_get_url(url, platform_key, cookie_file, max_videos, cookie_browser, active_proxy),
             "ytdlp_get_url",
             True),

            ("Method 1: yt-dlp --dump-json (with dates)",
             lambda: _method_ytdlp_dump_json(url, platform_key, cookie_file, max_videos, cookie_browser, active_proxy),
             "ytdlp_dump_json",
             True),

            ("Method 3: yt-dlp with retries",
             lambda: _method_ytdlp_with_retry(url, platform_key, cookie_file, max_videos, cookie_browser, active_proxy),
             "ytdlp_with_retry",
             True),

            # â”€â”€ gallery-dl (Instagram, TikTok fallback) â”€â”€
            ("Method 6: gallery-dl",
             lambda: _method_gallery_dl(url, platform_key, cookie_file, active_proxy),
             "gallery_dl",
             platform_key in ['instagram', 'tiktok']),

            # â”€â”€ Instagram-specific API methods â”€â”€
            ("Method 6b: Instagram GraphQL API (cookies)",
             lambda: _method_instagram_graphql(url, platform_key, cookie_file, max_videos, active_proxy),
             "instagram_graphql",
             platform_key == 'instagram'),

            ("Method 5: Instaloader",
             lambda: _method_instaloader(url, platform_key, cookie_file, max_videos, active_proxy),
             "instaloader",
             platform_key == 'instagram' and use_instaloader),

            # â”€â”€ Facebook-specific JSON extraction â”€â”€
            ("Method C: Facebook Page JSON (c_user+xs cookies -> video links)",
             lambda: _method_facebook_json(url, platform_key, cookie_file, max_videos, active_proxy),
             "facebook_json",
             platform_key == 'facebook'),

            # â”€â”€ Browser methods (all platforms) â”€â”€
            ("Method B: Instagram Mobile API (sessionid -> direct JSON)",
             lambda: _method_instagram_mobile_api(url, platform_key, cookie_file, max_videos, active_proxy),
             "instagram_mobile_api",
             platform_key == 'instagram'),

            ("Method D: Attach Selenium to running Chrome (CDP port)",
             lambda: _method_selenium_cdp_attach(url, platform_key, max_videos, progress_callback, expected_count or 0),
             "selenium_cdp_attach",
             (platform_key in {'instagram', 'facebook', 'tiktok', 'youtube'}) and (not managed_profile_only)),

            ("Method A: Selenium (Chrome user-data-dir profile)",
             lambda: _method_selenium_profile(url, platform_key, cookies_dir, max_videos, progress_callback),
             "selenium_profile",
             (platform_key in {'instagram', 'facebook'}) and (not managed_profile_only)),

            ("Method 7: Playwright (Stealth + Proxy + Human Behavior)",
             lambda: _method_playwright(url, platform_key, cookie_file, active_proxy, max_videos),
             "playwright",
             platform_key in ['tiktok', 'instagram', 'youtube', 'facebook']),

            ("Method 8: Selenium Headless (Proxy + Cookies + Stealth)",
             lambda: _method_selenium(url, platform_key, max_videos, cookie_file, active_proxy, progress_callback, expected_count),
             "selenium_headless",
             not managed_profile_only),
        ]

        # Filter allowed methods
        available_methods = [(name, func, mid) for name, func, mid, allowed in all_methods if allowed]

        # INTELLIGENCE: Check if we have learning data for this creator
        best_method_id = None
        if learning_system:
            best_method_id = learning_system.get_best_method(creator, platform_key)

            if best_method_id and progress_callback:
                progress_callback("Using preferred approach...")

        # Reorder methods to try best one first
        if best_method_id:
            # Move best method to front
            reordered = []
            best_method_func = None

            for name, func, mid in available_methods:
                if mid == best_method_id:
                    best_method_func = (name, func, mid)
                else:
                    reordered.append((name, func, mid))

            if best_method_func:
                available_methods = [best_method_func] + reordered

        # Instagram: yt-dlp extractor is officially BROKEN (marked by yt-dlp project 2025).
        # Skip ALL yt-dlp-based methods.  Try new methods first:
        #   B â†’ Mobile API (fastest, just sessionid cookie)
        #   D â†’ CDP attach (running Chrome session, no cookies needed)
        #   A â†’ Existing Browser user-data-dir (Chrome closed / different profile)
        #   8 â†’ Selenium headless (cookie injection)
        #   7 â†’ Playwright headless
        #   6b â†’ Instagram GraphQL Web API
        if platform_key == 'instagram':
            _INSTAGRAM_METHOD_IDS = {
                "instagram_mobile_api",
                "selenium_cdp_attach",
                "selenium_profile",
                "selenium_headless",
                "playwright",
                "instagram_graphql",
            }
            insta_filtered = [
                (name, func, mid) for name, func, mid in available_methods
                if mid in _INSTAGRAM_METHOD_IDS
            ]
            if insta_filtered:
                if progress_callback:
                    progress_callback("Scanning...")
                available_methods = insta_filtered
            # Priority order by method_id
            _insta_order = [
                "instagram_mobile_api",
                "selenium_cdp_attach",
                "selenium_profile",
                "selenium_headless",
                "playwright",
                "instagram_graphql",
            ]
            _order_map = {mid: i for i, mid in enumerate(_insta_order)}
            available_methods = sorted(available_methods, key=lambda x: _order_map.get(x[2], 99))

        # Facebook: put our new fast methods (JSON extraction + CDP + user-data-dir) first,
        # then Selenium/Playwright, then yt-dlp as last resort.
        elif platform_key == 'facebook':
            _fb_priority_ids = [
                "facebook_json",
                "selenium_cdp_attach",
                "selenium_profile",
                "selenium_headless",
                "playwright",
                "ytdlp_get_url",
                "ytdlp_dump_json",
                "ytdlp_with_retry",
            ]
            _fb_map = {mid: idx for idx, mid in enumerate(_fb_priority_ids)}
            available_methods = sorted(
                available_methods,
                key=lambda item: _fb_map.get(item[2], 999),
            )

        # Facebook profile URLs are often blocked/unsupported via plain yt-dlp listing.
        # Prefer browser extraction stack directly for these URL shapes.
        fb_profile_shape = False
        if platform_key == 'facebook':
            u_lower = (url or '').lower()
            try:
                parsed_fb = urlparse(url or '')
                fb_parts = [p.lower() for p in (parsed_fb.path or '').split('/') if p]
            except Exception:
                fb_parts = []

            is_direct_video_url = any(
                k in u_lower for k in ('/reel/', '/reels/', '/videos/', '/watch/', '/share/v/')
            )
            fb_profile_shape = (
                ('profile.php' in u_lower or '/people/' in u_lower) or
                (fb_parts and not is_direct_video_url)
            )
        if fb_profile_shape:
            if progress_callback:
                progress_callback("Facebook profile URL detected; prioritizing browser extraction methods.")
            _fb_browser_ids = {"selenium_headless", "playwright"}
            filtered = [(name, func, mid) for name, func, mid in available_methods if mid in _fb_browser_ids]
            if filtered:
                available_methods = filtered

        # Try methods
        successful_method = pre_successful_method
        # Preserve successful_method_id if already set by managed CDP pre-path
        if not successful_method_id:
            successful_method_id = ""
        last_method_error = ""
        if entries:
            successful_method = successful_method or "Existing Browser Session"
            if not exhaustive_mode:
                available_methods = []

        for _idx, (method_name, method_func, method_id) in enumerate(available_methods):
            if max_videos > 0 and len(entries) >= max_videos:
                break

            if progress_callback:
                progress_callback("Scanning...")

            start_time = time.time()
            method_entries = []
            error_msg = ""

            try:
                method_entries = method_func()
            except Exception as e:
                error_msg = str(e)[:200]
                last_method_error = error_msg
                if progress_callback:
                    progress_callback(f"Ã¢Å¡Â Ã¯Â¸Â {method_name} failed: {error_msg[:100]}")

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
                    method_id,
                    success,
                    added,
                    time_taken,
                    error_msg
                )

            if added > 0:
                successful_method = method_name
                successful_method_id = method_id
                if progress_callback:
                    progress_callback(f"Found {added} links")

                if target_count > 0 and len(entries) >= target_count:
                    if progress_callback:
                        progress_callback(f"Target reached: {len(entries)}/{target_count} links")
                    break

                if not exhaustive_mode:
                    break  # Stop on first success
            else:
                if progress_callback:
                    progress_callback(f"Ã¢Å¡Â Ã¯Â¸Â {method_name} Ã¢â€ â€™ 0 links")

                    # If this was the learned "best" method and it failed, inform user we'll try others
                    if method_id == best_method_id and best_method_id:
                        progress_callback("Trying other approaches...")

                # ============================================================
                # IP PROTECTION: Mandatory delay between failed method attempts
                # This prevents rapid-fire requests that could trigger IP blocking
                # ============================================================
                # Check if there are more methods to try (don't delay after last method)
                if _idx < len(available_methods) - 1:
                    delay = random.uniform(2.0, 4.0)
                    if progress_callback:
                        progress_callback(f"Waiting {delay:.1f}s...")
                    time.sleep(delay)

        # â”€â”€ Step 2.3 Tab Fallback: if primary tab yielded 0 results, try others â”€
        # Only runs for YouTube profile URLs; only uses fast (non-browser) methods.
        _url_type_fb   = options.get('_url_type', '')
        _chosen_tab_fb = options.get('_chosen_tab', '')
        _avail_tabs_fb = options.get('_available_tabs', [])
        _base_url_fb   = options.get('_profile_base_url', _profile_base_url)

        if (
            platform_key == 'youtube'
            and _url_type_fb == 'profile'
            and _avail_tabs_fb
            and (max_videos <= 0 or len(entries) < max_videos)
        ):
            remaining_tabs = [
                t for t in _avail_tabs_fb
                if t != _chosen_tab_fb
            ]
            if remaining_tabs and progress_callback:
                progress_callback(f"YouTube: trying additional tabs {remaining_tabs}")

            for alt_tab in remaining_tabs:
                if max_videos > 0 and len(entries) >= max_videos:
                    break
                alt_url = f"{_base_url_fb}/{alt_tab}"
                if progress_callback:
                    progress_callback(f"Trying tab fallback: '{alt_tab}' -> {alt_url}")

                # Fast yt-dlp methods only â€” no browser automation for tab fallback
                fast_tab_methods = [
                    (
                        f"Tab fallback: yt-dlp primary ({alt_tab})",
                        lambda u=alt_url: _method_ytdlp_primary(
                            u, platform_key, cookie_file, max_videos, cookie_browser, active_proxy
                        ),
                    ),
                    (
                        f"Tab fallback: yt-dlp --dump-json ({alt_tab})",
                        lambda u=alt_url: _method_ytdlp_dump_json(
                            u, platform_key, cookie_file, max_videos, cookie_browser, active_proxy
                        ),
                    ),
                    (
                        f"Tab fallback: yt-dlp --get-url ({alt_tab})",
                        lambda u=alt_url: _method_ytdlp_get_url(
                            u, platform_key, cookie_file, max_videos, cookie_browser, active_proxy
                        ),
                    ),
                ]

                for fb_method_name, fb_method_func in fast_tab_methods:
                    if max_videos > 0 and len(entries) >= max_videos:
                        break
                    try:
                        fb_entries = fb_method_func() or []
                    except Exception:
                        fb_entries = []

                    added = 0
                    for entry in fb_entries:
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

                    if added > 0:
                        successful_method = fb_method_name
                        if progress_callback:
                            progress_callback(
                                f"Tab fallback success: '{alt_tab}' -> +{added} links"
                            )
                        # Record winning tab in learning system
                        if learning_system:
                            try:
                                learning_system.record_best_tab(
                                    creator, platform_key, alt_tab, _avail_tabs_fb
                                )
                            except Exception:
                                pass
                        break

            # If primary tab succeeded originally, still record it as best tab
            if entries and _chosen_tab_fb and successful_method and 'Tab fallback' not in successful_method:
                if learning_system:
                    try:
                        learning_system.record_best_tab(
                            creator, platform_key, _chosen_tab_fb, _avail_tabs_fb
                        )
                    except Exception:
                        pass

        # If proxy path is blocked/rate-limited, auto retry once without proxy for IG/FB.
        if not entries and active_proxy and platform_key in {'instagram', 'facebook'}:
            if progress_callback:
                progress_callback("Retrying without proxy (proxy may be blocked/rate-limited)...")

            # Instagram: yt-dlp is officially broken â€” only use browser methods in retry
            if platform_key == 'instagram':
                if managed_profile_only:
                    no_proxy_methods = [
                        ("Method 7: Playwright (ENHANCED: Stealth + Proxy + Human Behavior)",
                         lambda: _method_playwright(url, platform_key, cookie_file, None, max_videos)),
                        ("Method 6b: Instagram Web API (cookies)",
                         lambda: _method_instagram_graphql(url, platform_key, cookie_file, max_videos, None)),
                    ]
                else:
                    no_proxy_methods = [
                        ("Method 8: Selenium Headless (ENHANCED: Proxy + Cookies + Stealth)",
                         lambda: _method_selenium(url, platform_key, max_videos, cookie_file, None, progress_callback, expected_count)),
                        ("Method 7: Playwright (ENHANCED: Stealth + Proxy + Human Behavior)",
                         lambda: _method_playwright(url, platform_key, cookie_file, None, max_videos)),
                        ("Method 6b: Instagram Web API (cookies)",
                         lambda: _method_instagram_graphql(url, platform_key, cookie_file, max_videos, None)),
                    ]
            else:
                if managed_profile_only:
                    no_proxy_methods = [
                        ("Method 7: Playwright (ENHANCED: Stealth + Proxy + Human Behavior)",
                         lambda: _method_playwright(url, platform_key, cookie_file, None, max_videos)),
                        ("Method 2: yt-dlp --get-url (SIMPLE - Like Batch Script)",
                         lambda: _method_ytdlp_get_url(url, platform_key, cookie_file, max_videos, cookie_browser, None)),
                        ("Method 1: yt-dlp --dump-json (with dates)",
                         lambda: _method_ytdlp_dump_json(url, platform_key, cookie_file, max_videos, cookie_browser, None)),
                        ("Method 3: yt-dlp with retries",
                         lambda: _method_ytdlp_with_retry(url, platform_key, cookie_file, max_videos, cookie_browser, None)),
                    ]
                else:
                    no_proxy_methods = [
                        ("Method 8: Selenium Headless (ENHANCED: Proxy + Cookies + Stealth)",
                         lambda: _method_selenium(url, platform_key, max_videos, cookie_file, None, progress_callback, expected_count)),
                        ("Method 7: Playwright (ENHANCED: Stealth + Proxy + Human Behavior)",
                         lambda: _method_playwright(url, platform_key, cookie_file, None, max_videos)),
                        ("Method 2: yt-dlp --get-url (SIMPLE - Like Batch Script)",
                         lambda: _method_ytdlp_get_url(url, platform_key, cookie_file, max_videos, cookie_browser, None)),
                        ("Method 1: yt-dlp --dump-json (with dates)",
                         lambda: _method_ytdlp_dump_json(url, platform_key, cookie_file, max_videos, cookie_browser, None)),
                        ("Method 3: yt-dlp with retries",
                         lambda: _method_ytdlp_with_retry(url, platform_key, cookie_file, max_videos, cookie_browser, None)),
                    ]

            for method_name, method_func in no_proxy_methods:
                if max_videos > 0 and len(entries) >= max_videos:
                    break
                if progress_callback:
                    progress_callback(f"Trying (no-proxy): {method_name}")

                try:
                    method_entries = method_func() or []
                except Exception:
                    method_entries = []

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

                if added > 0:
                    successful_method = f"{method_name} (no-proxy)"
                    if progress_callback:
                        progress_callback(f"Success (no-proxy): +{added} links")
                    # No-proxy retry is already a fallback pass â€” always stop on first success.
                    # exhaustive_mode only applies to the primary method loop above.
                    break

        # â”€â”€ Workflow 2 fallback: auto-login when all methods failed + no cookies â”€â”€
        if (
            not entries
            and platform_key in {'instagram', 'facebook'}
            and not cookie_file
            and not managed_profile_only
        ):
            if progress_callback:
                progress_callback("All methods failed without cookies. Attempting Workflow 2 (auto-login)...")
            try:
                from modules.shared.auto_login import auto_login_and_get_cookies
                from modules.shared.credential_store import CredentialStore
                store = CredentialStore()
                if store.has_credentials(platform_key):
                    if progress_callback:
                        progress_callback(f"[WF2] Credentials found for {platform_key}. Starting auto-login...")
                    save_path = None
                    if cookies_dir:
                        save_path = Path(cookies_dir) / "chrome_cookies.txt"
                    wf2_cookie = auto_login_and_get_cookies(
                        platform_key=platform_key,
                        save_to=save_path,
                        cb=progress_callback,
                    )
                    if wf2_cookie:
                        # Retry with newly acquired cookies
                        if progress_callback:
                            progress_callback("[WF2] Cookies obtained. Retrying Selenium with fresh cookies...")
                        try:
                            wf2_entries = _method_selenium(
                                url, platform_key, max_videos, wf2_cookie,
                                active_proxy, progress_callback, expected_count
                            )
                            for entry in (wf2_entries or []):
                                url_value = entry.get('url')
                                if not url_value:
                                    continue
                                normalized = _normalize_url(url_value)
                                if normalized not in seen_normalized:
                                    seen_normalized.add(normalized)
                                    entries.append(entry)
                            if entries:
                                successful_method = "Workflow 2 Auto-Login"
                        except Exception as wf2_err:
                            if progress_callback:
                                progress_callback(f"[WF2] Retry failed: {wf2_err}")
                else:
                    if progress_callback:
                        progress_callback(f"[WF2] No credentials for {platform_key}. Use Settings â†’ Saved Logins.")
            except ImportError:
                pass
            except Exception as wf2_ex:
                if progress_callback:
                    progress_callback(f"[WF2] Auto-login error: {wf2_ex}")

        # -- Recovery chain: managed browser/profile recovery --
        if not entries:
            try:
                from modules.shared.failure_classifier import classify_failure, is_auth_failure
                from modules.shared.recovery_chain import RecoveryChain

                _failure_type = classify_failure(last_method_error, platform_key)
                _auth_triggered = is_auth_failure(_failure_type)

                if not _auth_triggered:
                    try:
                        from modules.shared.session_authority import get_session_authority as _get_sa
                        _sa = _get_sa()
                        _sess = _sa.get_session_status()
                        _strict = _sa.get_login_status()
                        if _sess.get(platform_key) or _strict.get(platform_key):
                            _auth_triggered = True
                            _failure_type = classify_failure("auth_wall_suspected", platform_key)
                    except Exception:
                        pass

                if _auth_triggered:
                    if progress_callback:
                        progress_callback("Checking access...")

                    _recovery = RecoveryChain().attempt_recovery(platform_key, _failure_type)

                    if _recovery.cookie_path:
                        cookie_file = _recovery.cookie_path
                        for _rname, _rfunc, _rmid in available_methods[:3]:
                            try:
                                _r_entries = _rfunc()
                                for _re in (_r_entries or []):
                                    _rurl = _re.get("url")
                                    if not _rurl:
                                        continue
                                    _rnorm = _normalize_url(_rurl)
                                    if _rnorm not in seen_normalized:
                                        seen_normalized.add(_rnorm)
                                        entries.append(_re)
                                if entries:
                                    successful_method = f"Recovery ({_recovery.recovery_type})"
                                    successful_method_id = "recovery_cookie_refresh"
                                    break
                            except Exception:
                                pass

                    if not entries:
                        try:
                            from modules.shared.session_authority import get_session_authority
                            _auth_sa = get_session_authority()
                            if not _auth_sa.is_profile_busy():
                                _sess = _auth_sa.get_session_status()
                                if _sess.get(platform_key) and auth_manager:
                                    _content_filter = {
                                        'youtube': 'all_videos', 'tiktok': 'all_videos',
                                        'instagram': 'reels_only', 'twitter': 'video_tweets',
                                        'facebook': 'videos_reels',
                                    }.get(platform_key, 'all')
                                    _r_entries = auth_manager.grab_links_via_browser(
                                        url=url, platform_key=platform_key,
                                        content_filter=_content_filter, max_items=max_videos,
                                        progress_callback=progress_callback)
                                    for _re in (_r_entries or []):
                                        _rurl = _re.get("url")
                                        if not _rurl:
                                            continue
                                        _rnorm = _normalize_url(_rurl)
                                        if _rnorm not in seen_normalized:
                                            seen_normalized.add(_rnorm)
                                            entries.append(_re)
                                    if entries:
                                        successful_method = "Recovery (browser_extraction)"
                                        successful_method_id = "recovery_browser_extraction"
                        except Exception:
                            pass
            except ImportError:
                pass

        # Final fallback: open visible browser session and ask user to login manually.
        if not entries and platform_key in {'instagram', 'facebook'} and interactive_login_fallback:
            if progress_callback:
                progress_callback("No links yet. Launching interactive browser login fallback...")
            manual_entries = _method_interactive_browser_session(
                url=url,
                platform_key=platform_key,
                cookies_dir=cookies_dir,
                max_videos=max_videos,
                proxy=None,  # manual fallback works best without unstable proxies
                progress_callback=progress_callback,
                wait_seconds=max(30, min(300, manual_login_wait_seconds)),
            )
            added = 0
            for entry in manual_entries:
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
            if added > 0:
                successful_method = "Interactive Browser Session"
                if progress_callback:
                    progress_callback(f"Interactive browser fallback success: +{added} links")

        # Cleanup temp cookies
        for temp_cookie_file in temp_cookie_files:
            if temp_cookie_file and os.path.exists(temp_cookie_file):
                try:
                    os.unlink(temp_cookie_file)
                except Exception:
                    pass

        # Final processing
        if entries:
            if ContentFilter:
                try:
                    cf = ContentFilter()
                    entries = cf.filter_entries(entries, platform_key)
                    if progress_callback:
                        progress_callback(
                            f"Content filter applied: {len(entries)} {platform_key} items after filtering"
                        )
                except Exception:
                    pass

            # Remove duplicates
            entries = _remove_duplicate_entries(entries)

            # Sort by date (newest first)
            entries.sort(key=lambda x: x.get('date', '00000000'), reverse=True)

            # Limit if needed
            if max_videos > 0:
                entries = entries[:max_videos]

            # Attach _meta to each entry for downstream consumers
            _meta = {
                'creator': creator,
                'platform': platform_key,
                'extraction_method_id': successful_method_id or '',
                'auth_source': 'browser_profile' if cookie_file else 'none',
                'browser_session_used': bool(successful_method and any(
                    t in (successful_method or '').lower()
                    for t in ['chromium', 'selenium', 'browser', 'interactive', 'cdp', 'playwright', 'recovery']
                )),
                'fresh_cookie_exported': bool(cookie_file),
            }
            for entry in entries:
                entry['_meta'] = _meta

            if progress_callback:
                progress_callback(f"Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â")
                progress_callback(f"Ã¢Å“â€¦ Extraction Complete!")
                progress_callback(f"   Ã¢â‚¬Â¢ Total Links: {len(entries)}")
                if successful_method:
                    progress_callback(f"   Ã¢â‚¬Â¢ Method Used: {successful_method}")
                if active_proxy:
                    progress_callback(f"   Ã¢â‚¬Â¢ Proxy Used: {active_proxy}")
                progress_callback(f"Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â")
        else:
            if progress_callback:
                progress_callback(f"Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â")
                progress_callback(f"Ã¢ÂÅ’ No links found after trying all methods")
                progress_callback(f"Ã°Å¸â€™Â¡ Suggestions:")
                progress_callback(f"   Ã¢â‚¬Â¢ Try updating cookies")
                progress_callback(f"   Ã¢â‚¬Â¢ Use a different proxy")
                progress_callback(f"   Ã¢â‚¬Â¢ Check if the account is private")
                progress_callback(f"Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â")

        # Record auth source success for future preference
        if entries and _auth_source_id and managed_profile_only:
            try:
                from modules.shared.session_authority import AuthFallbackChain
                AuthFallbackChain().record_success(creator, platform_key, _auth_source_id)
            except Exception:
                pass

        return entries, creator

    except Exception as e:
        if progress_callback:
            progress_callback(f"Ã¢ÂÅ’ Critical error: {str(e)[:200]}")
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
                self.finished.emit(False, "Ã¢ÂÅ’ No URL provided", [])
                return

            self.progress.emit("Ã°Å¸â€Â Detecting platform...")
            self.progress_percent.emit(10)

            platform_key = _detect_platform_key(self.url)

            if platform_key == 'unknown':
                self.finished.emit(False, "Ã¢ÂÅ’ Unsupported platform", [])
                return

            self.progress.emit(f"Ã¢Å“â€¦ Platform: {platform_key.upper()}")
            self.progress_percent.emit(20)

            # Intelligent extraction
            def progress_cb(msg):
                self.progress.emit(msg)
                logging.info("[EXTRACT] %s", msg)  # Mirror to terminal for debugging

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
                    f"Ã¢ÂÅ’ No links found from @{creator}\n\n"
                    "Possible reasons:\n"
                    "Ã¢â‚¬Â¢ Private account (add cookies via GUI)\n"
                    "Ã¢â‚¬Â¢ Invalid URL\n"
                    "Ã¢â‚¬Â¢ Platform blocking\n"
                    "Ã¢â‚¬Â¢ No content available"
                )
                self.finished.emit(False, error_msg, [])
                return

            self.progress.emit(f"Ã¢Å“â€¦ Found {len(entries)} items from @{creator}")
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

                self.progress.emit(f"Ã°Å¸â€â€” [{idx}/{total}] {display_text[:100]}...")
                self.link_found.emit(entry['url'], display_text)

                pct = 60 + int((idx / total) * 35)
                self.progress_percent.emit(min(pct, 95))

            if self.is_cancelled:
                self.finished.emit(False, f"Ã¢Å¡Â Ã¯Â¸Â Cancelled. Got {len(self.found_links)} links.", self.found_links)
                return

            self.progress.emit(f"Ã¢Å“â€¦ Success! {len(self.found_links)} links from @{creator}")
            self.progress.emit("Ã°Å¸â€™Â¾ Use 'Save to Folder' in the GUI to export these links.")
            self.progress_percent.emit(100)

            self.finished.emit(True, f"Ã¢Å“â€¦ {len(self.found_links)} links from @{creator}", self.found_links)

        except Exception as e:
            error_msg = f"Ã¢ÂÅ’ Unexpected error: {str(e)[:200]}"
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
                self.finished.emit(False, "Ã¢ÂÅ’ No URLs provided", [])
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
                self.progress.emit(f"Ã°Å¸Â§Â¹ Removed {duplicates_removed} duplicate URLs")

            self.progress.emit(f"Ã°Å¸Å¡â‚¬ Processing {len(unique_urls)} unique URLs...")
            self.progress.emit("=" * 60)

            self.found_links = []
            self.creator_data = {}

            # Process each URL
            for i, url in enumerate(unique_urls, 1):
                if self.is_cancelled:
                    break

                self.progress.emit(f"\nÃ°Å¸â€œÅ’ [{i}/{len(unique_urls)}] {url[:60]}...")
                self.progress_percent.emit(int((i / len(unique_urls)) * 30))

                platform_key = _detect_platform_key(url)

                def progress_cb(msg):
                    self.progress.emit(f"  {msg}")
                    logging.info("[EXTRACT] %s", msg)  # Mirror to terminal for debugging

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

                self.progress.emit(f"Ã¢Å“â€¦ [{i}/{len(unique_urls)}] {len(entries)} links from @{creator}")

                pct = 30 + int((i / len(unique_urls)) * 65)
                self.progress_percent.emit(pct)

            if self.is_cancelled:
                self.finished.emit(False, f"Ã¢Å¡Â Ã¯Â¸Â Cancelled. {len(self.found_links)} total links.", self.found_links)
                return

            # Final report
            self.progress.emit("\n" + "=" * 60)
            self.progress.emit("Ã°Å¸Å½â€° BULK EXTRACTION COMPLETE!")
            self.progress.emit("=" * 60)
            self.progress.emit(f"Ã°Å¸â€œÅ  URLs Processed: {len(unique_urls)}")
            self.progress.emit(f"Ã°Å¸â€˜Â¥ Creators Found: {len(self.creator_data)}")
            self.progress.emit(f"Ã°Å¸â€â€” Total Links: {len(self.found_links)}")
            if duplicates_removed > 0:
                self.progress.emit(f"Ã°Å¸Â§Â¹ Duplicates Removed: {duplicates_removed}")

            self.progress.emit("\nÃ°Å¸â€œÂ Creator Folders:")
            for creator_name, data in self.creator_data.items():
                self.progress.emit(f"  Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ @{creator_name}/ ({len(data['links'])} links)")

            self.progress.emit("\nÃ°Å¸â€™Â¾ Use 'Save to Folder' to export all creators.")
            self.progress.emit("=" * 60)

            self.progress_percent.emit(100)
            self.finished.emit(True, f"Ã¢Å“â€¦ Bulk complete! {len(self.found_links)} links from {len(self.creator_data)} creators.", self.found_links)

        except Exception as e:
            error_msg = f"Ã¢ÂÅ’ Bulk error: {str(e)[:200]}"
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
                f.write(f"Ã°Å¸Å½Â¯ {creator_name}\n")
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
            self.progress.emit("Ã¢ÂÅ’ No links to save")
            return

        summary_path = self._create_summary_file()
        self.progress.emit(f"Ã°Å¸â€œâ€ž Summary created: {summary_path}")
        
        # Emit save signal
        desktop = Path.home() / "Desktop"
        base_folder = desktop / "Links Grabber"
        self.save_triggered.emit(str(base_folder), self.found_links)

    def cancel(self):
        self.is_cancelled = True
