"""
Shared User Agent Pool
Used by both Link Grabber and Video Downloader for consistent UA rotation

This module provides a centralized pool of realistic user agents to:
- Avoid bot detection
- Simulate real browser behavior
- Rotate across different browsers and platforms
"""

import random

# ============================================================================
# USER AGENT POOL (20+ Realistic User Agents)
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


def get_random_user_agent() -> str:
    """
    Get a random user agent from the pool.

    Returns:
        str: A randomly selected user agent string

    Example:
        >>> ua = get_random_user_agent()
        >>> print(ua)
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...'
    """
    return random.choice(USER_AGENTS)


def get_user_agent_by_platform(platform: str = 'desktop') -> str:
    """
    Get a random user agent for a specific platform type.

    Args:
        platform: Platform type ('desktop', 'mobile', 'tablet', 'random')

    Returns:
        str: A user agent matching the platform type
    """
    if platform == 'mobile':
        mobile_agents = [ua for ua in USER_AGENTS if 'Mobile' in ua or 'iPhone' in ua or 'Android' in ua]
        return random.choice(mobile_agents) if mobile_agents else get_random_user_agent()

    elif platform == 'tablet':
        tablet_agents = [ua for ua in USER_AGENTS if 'iPad' in ua]
        return random.choice(tablet_agents) if tablet_agents else get_random_user_agent()

    elif platform == 'desktop':
        desktop_agents = [ua for ua in USER_AGENTS if 'Mobile' not in ua and 'iPhone' not in ua and 'iPad' not in ua and 'Android' not in ua]
        return random.choice(desktop_agents) if desktop_agents else get_random_user_agent()

    else:  # random
        return get_random_user_agent()


# Export functions
__all__ = ['USER_AGENTS', 'get_random_user_agent', 'get_user_agent_by_platform']
