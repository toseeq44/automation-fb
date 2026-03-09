"""
Selection policy for CreatorProfile video pipeline.

Pure, testable functions that implement all selection modes.
No side effects, no imports beyond stdlib.

This module is the SINGLE place where selection logic lives.
Both single-card and Run-All call the same functions.

Data model per entry:
  url         str        (required)
  posted_at   str|None   YYYYMMDD or sortable timestamp (nullable)
  is_pinned   bool       default False
  views       int|None
  likes       int|None
  comments    int|None
  platform    str
  creator     str
  id          str        unique video identifier
"""

from __future__ import annotations

import logging
import random
import re
from datetime import datetime, timedelta
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, urlparse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entry normalisation
# ---------------------------------------------------------------------------

def normalise_entry(entry: dict) -> dict:
    """Ensure every entry has all required fields with safe defaults."""
    return {
        "url": entry.get("url", ""),
        "posted_at": entry.get("posted_at") or entry.get("date") or None,
        "is_pinned": bool(entry.get("is_pinned", False)),
        "views": _safe_int(entry.get("views") or entry.get("view_count")),
        "likes": _safe_int(entry.get("likes") or entry.get("like_count")),
        "comments": _safe_int(entry.get("comments") or entry.get("comment_count")),
        "platform": entry.get("platform", ""),
        "creator": entry.get("creator", ""),
        "id": entry.get("id", ""),
        "title": entry.get("title", ""),
        # Preserve any extra keys (e.g. _meta) without breaking
        **{k: v for k, v in entry.items() if k not in {
            "url", "posted_at", "date", "is_pinned", "views", "likes",
            "comments", "platform", "creator", "id", "title",
            "view_count", "like_count", "comment_count",
        }},
    }


def _safe_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Popularity ranking
# ---------------------------------------------------------------------------

def _popularity_key(entry: dict) -> Tuple:
    """Sort key for popularity ranking.

    Priority: views desc > likes desc > comments desc > recency desc.
    None values sort after any real value.
    """
    def _desc(val):
        if val is None:
            return (1, 0)  # Sort after real values
        return (0, -val)

    recency = entry.get("posted_at") or "00000000"
    return (
        _desc(entry.get("views")),
        _desc(entry.get("likes")),
        _desc(entry.get("comments")),
        (0, recency),  # higher date string = more recent = better, negate via tuple
    )


def _recency_key(entry: dict) -> str:
    """Sort key for recency (newer first)."""
    return entry.get("posted_at") or "00000000"


# ---------------------------------------------------------------------------
# Core selection function
# ---------------------------------------------------------------------------

def select_videos(
    entries: List[dict],
    n_videos: int,
    skip_downloaded: bool,
    popular_enabled: bool,
    random_enabled: bool,
    already_downloaded: FrozenSet[str],
    platform: str = "",
) -> Tuple[List[dict], List[dict]]:
    """Select videos according to user preferences.

    Returns:
        (selected, debug_log)
        - selected: final entries for downloader (len <= n_videos)
        - debug_log: list of {url, reason} dicts (for structured logging only)

    The returned entries are in the order the downloader should process them.
    """
    if not entries or n_videos <= 0:
        return [], []

    # Normalise all entries
    pool = [normalise_entry(e) for e in entries if e.get("url")]

    debug: List[dict] = []

    # Drop non-video/navigation URLs (e.g. facebook /reel/?s=tab).
    # Also canonicalise recoverable video links (share/wrapper variants).
    platform_hint = (platform or "").strip().lower()
    canonicalized = 0
    unsupported_samples: List[str] = []
    normalized_pool: List[dict] = []
    for e in pool:
        raw_url = (e.get("url") or "").strip()
        canon = _canonical_video_url(raw_url, platform_hint)
        if not canon:
            if len(unsupported_samples) < 3 and raw_url:
                unsupported_samples.append(raw_url[:140])
            continue
        if canon != raw_url:
            canonicalized += 1
            e = dict(e)
            e["url"] = canon
        normalized_pool.append(e)
    dropped_unsupported = len(pool) - len(normalized_pool)
    pool = normalized_pool

    if canonicalized:
        debug.append({"action": "canonicalized_video_url", "count": canonicalized})
    if dropped_unsupported:
        payload = {"action": "drop_unsupported_url", "count": dropped_unsupported}
        if unsupported_samples:
            payload["samples"] = unsupported_samples
        debug.append(payload)

    # De-dup after canonicalization
    seen_urls: Set[str] = set()
    deduped_pool: List[dict] = []
    dropped_dupes = 0
    for e in pool:
        key = (e.get("url") or "").strip().lower()
        if not key:
            continue
        if key in seen_urls:
            dropped_dupes += 1
            continue
        seen_urls.add(key)
        deduped_pool.append(e)
    pool = deduped_pool
    if dropped_dupes:
        debug.append({"action": "drop_duplicate_url_after_normalize", "count": dropped_dupes})

    # Remove already-downloaded if skip enabled
    if skip_downloaded:
        before = len(pool)
        pool = [e for e in pool if e["id"] not in already_downloaded]
        skipped = before - len(pool)
        if skipped:
            debug.append({"action": "skip_downloaded", "count": skipped})

    if not pool:
        debug.append({"action": "pool_empty_after_filter"})
        return [], debug

    if not skip_downloaded:
        # Mode D: skip=false — same engine, just no duplicate filtering
        # Pick newest entries (respects pinned exclusion for latest path)
        selected = _select_mode_a(pool, n_videos, debug)
    elif popular_enabled and random_enabled:
        # Mode C: skip + popular + random
        selected = _select_mode_c(pool, n_videos, platform, debug)
    elif popular_enabled:
        # Mode B: skip + popular
        selected = _select_mode_b(pool, n_videos, platform, debug)
    else:
        # Mode A: skip only (newest non-pinned)
        selected = _select_mode_a(pool, n_videos, debug)

    logger.info(
        "[SelectionDecision] mode=%s n_requested=%d n_selected=%d platform=%s",
        _mode_label(skip_downloaded, popular_enabled, random_enabled),
        n_videos,
        len(selected),
        platform,
    )
    for s in selected:
        debug.append({
            "action": "selected",
            "url": s.get("url", "")[:80],
            "reason": s.get("_selection_reason", "unknown"),
        })

    return selected, debug


def _detect_platform_from_url(url: str) -> str:
    u = (url or "").lower()
    if "facebook.com" in u or "fb.com" in u:
        return "facebook"
    if "instagram.com" in u:
        return "instagram"
    if "tiktok.com" in u:
        return "tiktok"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "x.com" in u or "twitter.com" in u:
        return "twitter"
    return ""


def _is_instagram_shortcode(value: str) -> bool:
    token = (value or "").strip()
    if not token:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{5,64}", token))


def _canonical_video_url(url: str, platform_hint: str = "") -> str:
    """
    Canonicalise known platform video URLs.
    Returns empty string when URL is navigation/login/non-video.
    """
    try:
        if not url:
            return ""

        raw = str(url).strip()
        parsed = urlparse(raw)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").strip()
        q = parse_qs(parsed.query or "")
        lower_url = raw.lower()
        parts = [p for p in path.split("/") if p]
        lparts = [p.lower() for p in parts]

        platform = platform_hint or _detect_platform_from_url(raw)

        # Global hard rejects
        if any(token in lower_url for token in (
            "login.php", "forced_account_switch", "_fb_noscript"
        )):
            return ""

        # Handle instagram redirect wrapper links.
        if "instagram.com" in host and host.startswith("l.") and q.get("u"):
            nested = unquote((q.get("u") or [""])[0].strip())
            if nested:
                return _canonical_video_url(nested, "instagram")
            return ""

        if platform == "facebook":
            # Valid examples:
            # /reel/<id>, /<user>/videos/<id>, /watch/?v=<id>, /share/v/<id>
            if len(parts) >= 2 and lparts[0] in {"reel", "reels"}:
                reel_id = parts[1].strip("/")
                if reel_id:
                    return f"https://www.facebook.com/reel/{reel_id}"
            if "/videos/" in path:
                # Require numeric video ID segment
                try:
                    idx = parts.index("videos")
                    if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                        return f"https://www.facebook.com/{'/'.join(parts)}"
                    return ""
                except ValueError:
                    return ""
            if path.startswith("/watch/"):
                v = (q.get("v") or [""])[0].strip()
                if v and v.isdigit():
                    return f"https://www.facebook.com/watch/?v={v}"
                return ""
            if path.startswith("/share/v/"):
                share_id = path[len("/share/v/"):].strip("/")
                if share_id:
                    return f"https://www.facebook.com/share/v/{share_id}"
                return ""
            return ""

        if platform == "instagram":
            _IG_MEDIA = {"reel", "reels", "p", "tv"}

            # /reel/<code>, /reels/<code>, /p/<code>, /tv/<code>
            if len(parts) >= 2 and lparts[0] in _IG_MEDIA:
                code = parts[1].strip("/")
                if _is_instagram_shortcode(code):
                    prefix = "reel" if lparts[0] == "reels" else lparts[0]
                    return f"https://www.instagram.com/{prefix}/{code}/"
                return ""

            # /<username>/reel/<code>, /<username>/reels/<code>, etc.
            if len(parts) >= 3 and lparts[1] in _IG_MEDIA:
                code = parts[2].strip("/")
                if _is_instagram_shortcode(code):
                    prefix = "reel" if lparts[1] == "reels" else lparts[1]
                    return f"https://www.instagram.com/{prefix}/{code}/"
                return ""

            # /share/reel/<code>, /share/p/<code>, /share/tv/<code>
            if len(parts) >= 3 and lparts[0] == "share" and lparts[1] in _IG_MEDIA:
                code = parts[2].strip("/")
                if _is_instagram_shortcode(code):
                    prefix = "reel" if lparts[1] == "reels" else lparts[1]
                    return f"https://www.instagram.com/{prefix}/{code}/"
                return ""

            # Anything else under instagram profile/tabs is navigation, not direct video.
            return ""

        if platform == "tiktok":
            # /@user/video/<digits>
            if len(parts) >= 3 and parts[0].startswith("@") and parts[1] == "video":
                if parts[2].isdigit():
                    return f"https://www.tiktok.com/{parts[0]}/video/{parts[2]}"
            return ""

        if platform == "youtube":
            if "youtu.be" in host:
                vid = path.strip("/")
                return f"https://www.youtube.com/watch?v={vid}" if vid else ""
            if path.startswith("/watch"):
                v = (q.get("v") or [""])[0].strip()
                return f"https://www.youtube.com/watch?v={v}" if v else ""
            if path.startswith("/shorts/"):
                sid = path[len("/shorts/"):].strip("/")
                return f"https://www.youtube.com/shorts/{sid}" if sid else ""
            return ""

        # Unknown platform: allow through (do not over-block)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return raw
        return ""
    except Exception:
        return ""


def _is_supported_video_url(url: str, platform_hint: str = "") -> bool:
    """Return True only for actual video/post URLs, not tab/navigation URLs."""
    try:
        return bool(_canonical_video_url(url, platform_hint))
    except Exception:
        return False


def _mode_label(skip: bool, popular: bool, rand: bool) -> str:
    if not skip:
        return "D_no_skip"
    if popular and rand:
        return "C_skip_popular_random"
    if popular:
        return "B_skip_popular"
    return "A_skip_latest"


# ---------------------------------------------------------------------------
# Mode A: newest non-pinned unseen
# ---------------------------------------------------------------------------

def _select_mode_a(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    """Choose newest non-pinned entries.

    Pinned entries are intentionally excluded from latest-mode output.
    """
    non_pinned = [e for e in pool if not e.get("is_pinned")]
    # Sort by recency desc
    non_pinned.sort(key=_recency_key, reverse=True)

    selected = non_pinned[:n]
    for s in selected:
        s["_selection_reason"] = "latest_non_pinned"

    if len(selected) < n:
        debug.append({
            "action": "mode_a_shortfall_non_pinned_only",
            "have": len(selected),
            "need": n,
        })

    return selected[:n]


# ---------------------------------------------------------------------------
# Mode B: skip + popular
# ---------------------------------------------------------------------------

def _select_mode_b(
    pool: List[dict], n: int, platform: str, debug: List[dict],
) -> List[dict]:
    """Mode B: latest non-pinned first, then fill from popularity.

    TikTok/YouTube: pick latest non-pinned unseen, fill remainder from popularity.
    Instagram/Facebook: build pool from latest 50, rank by popularity, pick top N.
    """
    if platform in ("instagram", "facebook"):
        return _select_mode_b_ig_fb(pool, n, debug)
    return _select_mode_b_tiktok_yt(pool, n, debug)


def _select_mode_b_tiktok_yt(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    non_pinned = [e for e in pool if not e.get("is_pinned")]
    non_pinned.sort(key=_recency_key, reverse=True)

    selected = non_pinned[:n]
    for s in selected:
        s["_selection_reason"] = "latest_non_pinned"

    if len(selected) < n:
        # Fill from popularity-ranked remainder
        selected_urls = {s["url"] for s in selected}
        remainder = [e for e in pool if e["url"] not in selected_urls]
        remainder.sort(key=_popularity_key)
        for e in remainder:
            if len(selected) >= n:
                break
            e["_selection_reason"] = "popularity_fill"
            selected.append(e)
        debug.append({
            "action": "mode_b_popularity_fill",
            "filled": len(selected) - len([s for s in selected if s.get("_selection_reason") == "latest_non_pinned"]),
        })

    return selected[:n]


def _select_mode_b_ig_fb(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    # Build pool from latest 50 entries (sorted by recency)
    sorted_pool = sorted(pool, key=_recency_key, reverse=True)[:50]

    # Rank by popularity
    sorted_pool.sort(key=_popularity_key)
    selected = sorted_pool[:n]
    for s in selected:
        s["_selection_reason"] = "ig_fb_popularity_top"

    debug.append({
        "action": "mode_b_ig_fb",
        "pool_size": len(sorted_pool),
        "selected": len(selected),
    })
    return selected[:n]


# ---------------------------------------------------------------------------
# Mode C: skip + popular + random
# ---------------------------------------------------------------------------

def _select_mode_c(
    pool: List[dict], n: int, platform: str, debug: List[dict],
) -> List[dict]:
    """Mode C: latest non-pinned first, then random sample from broad pool,
    popularity-rank the sample, return top N.
    """
    # 1. Start with latest non-pinned unseen
    non_pinned = [e for e in pool if not e.get("is_pinned")]
    non_pinned.sort(key=_recency_key, reverse=True)
    latest_picks = non_pinned[:max(1, n // 2)]
    for s in latest_picks:
        s["_selection_reason"] = "latest_anchor"

    # 2. Build broad pool (latest 100, pinned allowed)
    broad = sorted(pool, key=_recency_key, reverse=True)[:100]
    already_selected = {e["url"] for e in latest_picks}
    remaining = [e for e in broad if e["url"] not in already_selected]

    # 3. Random sample from remaining
    sample_size = min(len(remaining), max(n * 3, 20))
    sample = random.sample(remaining, min(sample_size, len(remaining)))

    # 4. Popularity-rank the sample
    sample.sort(key=_popularity_key)
    needed = n - len(latest_picks)
    fill = sample[:needed]
    for s in fill:
        s["_selection_reason"] = "random_popularity"

    selected = latest_picks + fill
    debug.append({
        "action": "mode_c",
        "latest_anchor": len(latest_picks),
        "random_fill": len(fill),
        "broad_pool": len(broad),
    })
    return selected[:n]
