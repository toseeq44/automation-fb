"""
Link Grabber Configuration
Enhanced settings for reliable link extraction
"""

# ============================================================================
# USER AGENT ROTATION (20+ Realistic User Agents)
# ============================================================================

USER_AGENTS = [
    # Chrome - Windows 10/11
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',

    # Chrome - Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',

    # Chrome - Linux
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',

    # Firefox - Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',

    # Firefox - Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13.5; rv:120.0) Gecko/20100101 Firefox/120.0',

    # Firefox - Linux
    'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',

    # Edge - Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',

    # Safari - Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',

    # Safari - iOS (Mobile)
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',

    # Chrome - Android
    'Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36',
]

# ============================================================================
# PLATFORM-SPECIFIC RATE LIMITS (seconds between requests)
# ============================================================================

RATE_LIMITS = {
    'youtube': 3,      # YouTube: 1 request every 3 seconds
    'instagram': 5,    # Instagram: 1 request every 5 seconds (strict)
    'tiktok': 4,       # TikTok: 1 request every 4 seconds
    'facebook': 6,     # Facebook: 1 request every 6 seconds
    'twitter': 3,      # Twitter/X: 1 request every 3 seconds
    'default': 3,      # Default for other platforms
}

# ============================================================================
# RETRY SETTINGS
# ============================================================================

RETRY_CONFIG = {
    'max_attempts': 3,           # Try each method 3 times
    'backoff_factor': 2,         # Exponential backoff: 2^attempt seconds
    'base_delay': 2,             # Base delay for exponential backoff
    'between_methods_delay': 3,  # Delay between different methods
}

# ============================================================================
# DELAY SETTINGS (Anti-Bot Delays)
# ============================================================================

DELAY_CONFIG = {
    'before_request_min': 2,     # Minimum delay before request (seconds)
    'before_request_max': 5,     # Maximum delay before request (seconds)
    'after_fail_min': 5,         # Minimum delay after failed attempt
    'after_fail_max': 10,        # Maximum delay after failed attempt
}

# ============================================================================
# PROXY SETTINGS
# ============================================================================

PROXY_CONFIG = {
    'max_proxies': 2,                    # User can provide max 2 proxies
    'validation_timeout': 10,            # Proxy validation timeout (seconds)
    'test_urls': {
        'ip_check': 'https://httpbin.org/ip',
        'youtube': 'https://www.youtube.com',
        'instagram': 'https://www.instagram.com',
    },
    'speed_threshold': 5,                # Max acceptable response time (seconds)
}

# ============================================================================
# YT-DLP CONFIGURATION
# ============================================================================

YTDLP_CONFIG = {
    'timeout': 30,                       # Request timeout (seconds)
    'retries': 3,                        # Number of retries
    'socket_timeout': 30,                # Socket timeout
    'no_warnings': True,                 # Suppress warnings
    'quiet': True,                       # Quiet mode
    'no_color': True,                    # No colored output
    'extract_flat': True,                # Extract playlist info only (faster)
}

# ============================================================================
# METHOD PRIORITY (Intelligence System Default)
# ============================================================================

METHOD_PRIORITY = [
    'method_2',  # yt-dlp --get-url (fastest)
    'method_1',  # yt-dlp --dump-json (comprehensive)
    'method_3',  # yt-dlp -j (alternative)
    'method_4',  # yt-dlp --flat-playlist
    'method_5',  # yt-dlp playlist extraction
    'method_7',  # Instaloader (Instagram specific)
    'method_8',  # Selenium (most reliable, slowest)
    'method_6',  # yt-dlp single video (last resort)
]

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_CONFIG = {
    'show_detailed_logs': True,          # Show detailed extraction logs
    'log_proxy_usage': True,             # Log which proxy is used
    'log_user_agent': True,              # Log which user agent is used
    'log_timing': True,                  # Log time taken for each method
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_rate_limit(platform: str) -> int:
    """
    Get rate limit for a specific platform

    Args:
        platform: Platform name (youtube, instagram, tiktok, etc.)

    Returns:
        Rate limit in seconds
    """
    platform_lower = platform.lower()
    for key in RATE_LIMITS:
        if key in platform_lower:
            return RATE_LIMITS[key]
    return RATE_LIMITS['default']


def get_platform_from_url(url: str) -> str:
    """
    Extract platform name from URL

    Args:
        url: URL string

    Returns:
        Platform name (youtube, instagram, tiktok, etc.)
    """
    url_lower = url.lower()

    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    elif 'instagram.com' in url_lower:
        return 'instagram'
    elif 'tiktok.com' in url_lower:
        return 'tiktok'
    elif 'facebook.com' in url_lower or 'fb.com' in url_lower:
        return 'facebook'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'twitter'
    else:
        return 'default'
