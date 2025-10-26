import os
from pathlib import Path

def find_cookie_file_for_url(url: str) -> str | None:
    """
    Return path to cookie file for given url or None if not found.
    Search order:
      1) ./cookies/cookies.txt (universal)
      2) platform-specific cookie file under ./cookies/
      3) Desktop fallback ~/Desktop/toseeq-cookies.txt
    """
    try:
        url_lower = (url or "").lower()
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        cookies_dir = project_root / "cookies"
        cookies_dir.mkdir(parents=True, exist_ok=True)

        universal_cookie = cookies_dir / "cookies.txt"
        if universal_cookie.exists() and universal_cookie.stat().st_size > 10:
            return str(universal_cookie)

        platform_map = {
            'youtube': 'youtube.txt',
            'instagram': 'instagram.txt',
            'tiktok': 'tiktok.txt',
            'facebook': 'facebook.txt',
            'twitter': 'twitter.txt'
        }
        for platform, cookie_file in platform_map.items():
            if platform in url_lower:
                platform_cookie = cookies_dir / cookie_file
                if platform_cookie.exists() and platform_cookie.stat().st_size > 10:
                    return str(platform_cookie)

        # Desktop fallback
        desktop_cookie = Path.home() / "Desktop" / "toseeq-cookies.txt"
        if desktop_cookie.exists() and desktop_cookie.stat().st_size > 10:
            return str(desktop_cookie)
    except Exception:
        pass
    return None
