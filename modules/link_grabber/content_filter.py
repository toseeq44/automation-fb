"""
Platform-specific content filtering for extracted links.
"""

from __future__ import annotations

from typing import Dict, List

try:
    from .config import CONTENT_FILTER_RULES
except Exception:
    CONTENT_FILTER_RULES = {
        "youtube": {
            "include_patterns": ["/watch?v=", "/shorts/"],
            "exclude_patterns": ["/playlist?", "/community/", "/@", "/channel/"],
            "grab_tabs": ["videos", "shorts"],
        },
        "tiktok": {
            "include_patterns": ["/video/"],
            "exclude_patterns": [],
            "grab_tabs": [],
        },
        "instagram": {
            "include_patterns": ["/reel/"],
            "exclude_patterns": ["/p/", "/tv/", "/stories/"],
            "grab_tabs": ["reels"],
        },
        "twitter": {
            "include_patterns": ["/status/"],
            "exclude_patterns": ["/i/", "/home", "/explore", "/search"],
            "grab_tabs": ["media"],
        },
        "facebook": {
            "include_patterns": ["/reel/", "/videos/", "/watch/", "/share/v/"],
            "exclude_patterns": ["/photos/", "/posts/", "/about/", "/events/"],
            "grab_tabs": ["videos", "reels"],
        },
    }


class ContentFilter:
    """Filter extracted entries to platform-appropriate content types."""

    def __init__(self):
        self.rules: Dict[str, dict] = CONTENT_FILTER_RULES

    def filter_entries(self, entries: List[dict], platform_key: str) -> List[dict]:
        platform_key = (platform_key or "").lower().strip()
        if not entries:
            return []
        if platform_key not in self.rules:
            return entries

        filtered: List[dict] = []
        seen = set()

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("url", "")).strip()
            if not url:
                continue
            if not self.is_valid_content(url, platform_key):
                continue
            if url in seen:
                continue
            seen.add(url)
            filtered.append(entry)

        return filtered

    def is_valid_content(self, url: str, platform_key: str) -> bool:
        platform_key = (platform_key or "").lower().strip()
        rule = self.rules.get(platform_key)
        if not rule:
            return True

        target = (url or "").lower()
        includes = [p.lower() for p in rule.get("include_patterns", [])]
        excludes = [p.lower() for p in rule.get("exclude_patterns", [])]

        if includes and not any(token in target for token in includes):
            return False
        if excludes and any(token in target for token in excludes):
            return False
        return True

    def get_profile_url_for_content(self, base_url: str, platform_key: str) -> List[str]:
        platform_key = (platform_key or "").lower().strip()
        base = (base_url or "").strip().rstrip("/")
        if not base:
            return []

        if platform_key == "youtube":
            return [f"{base}/videos", f"{base}/shorts"]
        if platform_key == "instagram":
            return [f"{base}/reels/"]
        if platform_key == "facebook":
            return [f"{base}/videos/", f"{base}/reels/"]
        if platform_key == "tiktok":
            return [base]
        if platform_key == "twitter":
            return [f"{base}/media"]
        return [base]
