"""Utility helpers for parsing and normalising video URLs."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Union

# Regex that captures any obvious URL-like token (http(s), ftp, or www.)
_URL_CANDIDATE_RE = re.compile(
    r"((?:https?|ftps?)://[^\s<>'\"]+|www\.[^\s<>'\"]+)",
    re.IGNORECASE,
)

# Basic scheme matcher so we know whether we need to prepend https://
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)

# Domain-style strings such as example.com/abc
_DOMAIN_RE = re.compile(r"^[\w.-]+\.[a-z]{2,}(?:/[\w./?=&%+-]*)?\Z", re.IGNORECASE)


def normalize_url(url: str) -> str:
    """Normalise URLs so duplicate detection is consistent."""

    try:
        url = re.sub(r"[?&]utm_[^&]*", "", url)
        url = re.sub(r"[?&]fbclid=[^&]*", "", url)
        if "tiktok.com" in url:
            match = re.search(r"/video/(\d+)", url)
            if match:
                return f"tiktok_{match.group(1)}"
        elif "youtube.com" in url or "youtu.be" in url:
            match = re.search(r"(?:v=|/)([a-zA-Z0-9_-]{11})", url)
            if match:
                return f"youtube_{match.group(1)}"
        elif "instagram.com" in url:
            match = re.search(r"/(?:p|reel)/([^/?]+)", url)
            if match:
                return f"instagram_{match.group(1)}"
        return url.strip()
    except Exception:
        return url.strip()


def coerce_bool(value, default: bool = True) -> bool:
    """Best-effort boolean parsing that honours user intent."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        val = value.strip().lower()
        if val in {"true", "1", "yes", "on", "enable", "enabled"}:
            return True
        if val in {"false", "0", "no", "off", "disable", "disabled"}:
            return False
    try:
        return bool(value)
    except Exception:
        return default


def quality_to_format(quality: Optional[str]) -> Optional[str]:
    """Translate human readable quality labels into yt-dlp format strings."""

    if not quality:
        return None
    lookup = {
        "mobile": "bestvideo[height<=480][ext=mp4]+bestaudio/best[height<=480]",
        "low": "bestvideo[height<=480][ext=mp4]+bestaudio/best[height<=480]",
        "medium": "bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]",
        "hd": "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080]",
        "4k": "bestvideo[height<=2160][ext=mp4]+bestaudio/best[height<=2160]",
        "best": "bestvideo+bestaudio/best",
    }
    return lookup.get(str(quality).strip().lower())


def _iter_raw_candidates(url_input: Union[str, Iterable]) -> Iterable[str]:
    """Yield raw URL-like candidates from a string or iterable input."""

    if isinstance(url_input, str):
        text = url_input.replace("\r", "\n")
        matches = _URL_CANDIDATE_RE.findall(text)
        if matches:
            for match in matches:
                yield match
        else:
            # Fallback split on whitespace / commas / semicolons
            for token in re.split(r"[\s,;]+", text):
                yield token
    else:
        for item in url_input:
            if isinstance(item, dict):
                url = item.get("url")
                if url:
                    yield url
            else:
                yield str(item)


def extract_urls(url_input: Union[str, Iterable]) -> List[str]:
    """Extract cleaned, deduplicated URLs from arbitrary user input."""

    cleaned: List[str] = []
    seen = set()

    for raw in _iter_raw_candidates(url_input):
        if not raw:
            continue
        url = raw.strip().strip('\'"<>\u200b')
        if not url:
            continue
        if not _SCHEME_RE.match(url):
            if url.lower().startswith("www.") or _DOMAIN_RE.match(url):
                url = "https://" + url.lstrip("/")
            else:
                continue
        if "://" in url:
            scheme, rest = url.split("://", 1)
            url = f"{scheme.lower()}://{rest}"
        normalized = normalize_url(url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(url)

    return cleaned


__all__ = [
    "coerce_bool",
    "extract_urls",
    "normalize_url",
    "quality_to_format",
]
