"""Utilities for working with downloader cookie files."""

from __future__ import annotations

import hashlib
import tempfile
import time
from pathlib import Path
from typing import Iterable, Optional, Tuple


_PLATFORM_DOMAIN_MAP = {
    "instagram": ".instagram.com",
    "youtube": ".youtube.com",
    "tiktok": ".tiktok.com",
    "facebook": ".facebook.com",
    "twitter": ".twitter.com",
}


def _iter_cookie_lines(path: Path) -> Iterable[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                yield line.rstrip("\n")
    except Exception:
        return []


def _first_data_line(lines: Iterable[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def _parse_simple_cookie_lines(lines: Iterable[str]) -> Tuple[Tuple[str, str], ...]:
    entries = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in stripped:
            # Appears to already be in Netscape format – bail so caller keeps original file.
            return tuple()
        if "=" in stripped:
            name, value = stripped.split("=", 1)
        elif " " in stripped:
            name, value = stripped.split(" ", 1)
        else:
            continue
        name = name.strip()
        value = value.strip()
        if not name or not value:
            continue
        entries.append((name, value))
    return tuple(entries)


def ensure_netscape_cookie(cookie_path: Path, platform: str) -> Optional[str]:
    """Ensure *cookie_path* points to a Netscape formatted cookie file.

    If the file already matches the Netscape layout it is returned unchanged. If it
    looks like a simple ``name=value`` structure we materialise a temporary Netscape
    file so yt-dlp and instaloader can consume it. When we cannot confidently convert
    the file ``None`` is returned so the caller may fall back to another candidate.
    """

    try:
        lines = tuple(_iter_cookie_lines(cookie_path))
    except Exception:
        return None

    if not lines:
        return None

    first_data = _first_data_line(lines)
    if not first_data:
        return None
    if first_data.count("\t") >= 6 or first_data.startswith("# Netscape"):
        return str(cookie_path)

    entries = _parse_simple_cookie_lines(lines)
    if not entries:
        return None

    domain = _PLATFORM_DOMAIN_MAP.get(platform.lower())
    if not domain:
        return None

    try:
        digest = hashlib.sha1((str(cookie_path) + platform).encode("utf-8")).hexdigest()
        cache_dir = Path(tempfile.gettempdir()) / "toseeq_cookie_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        converted_path = cache_dir / f"{digest}.txt"
        expiry = str(int(time.time()) + 365 * 24 * 60 * 60)
        lines_out = [
            "# Netscape HTTP Cookie File",
            "# Converted automatically from simple format",
            "",
        ]
        for name, value in entries:
            lines_out.append(
                "\t".join(
                    [
                        domain,
                        "TRUE",
                        "/",
                        "TRUE",
                        expiry,
                        name,
                        value,
                    ]
                )
            )
        converted_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
        return str(converted_path)
    except Exception:
        return None


__all__ = ["ensure_netscape_cookie"]
