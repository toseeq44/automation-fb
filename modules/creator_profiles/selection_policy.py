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
    yt_content_type: str = "all",
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

    # YouTube content type filter (shorts / long / all)
    if platform_hint == "youtube" and yt_content_type in ("shorts", "long"):
        before_yt = len(pool)
        preferred = [e for e in pool if _is_yt_short(e["url"]) == (yt_content_type == "shorts")]
        if preferred:
            pool = preferred
            dropped_yt = before_yt - len(pool)
            if dropped_yt:
                debug.append({"action": "yt_content_filter", "type": yt_content_type, "dropped": dropped_yt})
        else:
            # Fallback: preferred type yielded 0, keep all (don't starve pipeline)
            debug.append({"action": "yt_content_filter_fallback", "type": yt_content_type, "reason": "no_matches"})

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

    # 8-way dispatch based on (skip, popular, random) combination
    _dispatch = {
        (False, False, False): _mode_noskip_latest,
        (False, True,  False): _mode_noskip_popular,
        (False, False, True):  _mode_noskip_random,
        (False, True,  True):  _mode_noskip_popular_random,
        (True,  False, False): _mode_skip_latest,
        (True,  True,  False): _mode_skip_popular,
        (True,  False, True):  _mode_skip_random,
        (True,  True,  True):  _mode_skip_popular_random,
    }
    mode_fn = _dispatch[(skip_downloaded, popular_enabled, random_enabled)]
    selected = mode_fn(pool, n_videos, debug)

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
                # Facebook video URLs come in two forms:
                #   /<user>/videos/<numeric_id>
                #   /<user>/videos/<title-slug>/<numeric_id>
                # Accept if ANY segment after "videos" is numeric.
                try:
                    idx = parts.index("videos")
                    after_videos = parts[idx + 1:]
                    numeric_ids = [p for p in after_videos if p.isdigit()]
                    if numeric_ids:
                        vid_id = numeric_ids[-1]  # last numeric segment is the ID
                        user = parts[0] if idx > 0 else ""
                        if user:
                            return f"https://www.facebook.com/{user}/videos/{vid_id}"
                        return f"https://www.facebook.com/videos/{vid_id}"
                    return ""
                except (ValueError, IndexError):
                    return ""
            if path.startswith("/watch/") or path == "/watch":
                v = (q.get("v") or [""])[0].strip()
                if v and v.isdigit():
                    return f"https://www.facebook.com/watch/?v={v}"
                # Also accept /watch/{numeric_id} path format
                watch_seg = path[len("/watch/"):].strip("/")
                if watch_seg and watch_seg.isdigit():
                    return f"https://www.facebook.com/watch/?v={watch_seg}"
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


def _is_yt_short(url: str) -> bool:
    """Return True if the URL is a YouTube Shorts link."""
    return "/shorts/" in (url or "").lower()


def _is_supported_video_url(url: str, platform_hint: str = "") -> bool:
    """Return True only for actual video/post URLs, not tab/navigation URLs."""
    try:
        return bool(_canonical_video_url(url, platform_hint))
    except Exception:
        return False


def _mode_label(skip: bool, popular: bool, rand: bool) -> str:
    parts = []
    parts.append("skip" if skip else "noskip")
    if popular:
        parts.append("popular")
    if rand:
        parts.append("random")
    if not popular and not rand:
        parts.append("latest")
    return "_".join(parts)


# ---------------------------------------------------------------------------
# Shared helpers for mode functions
# ---------------------------------------------------------------------------

def _split_pinned(pool: List[dict]) -> Tuple[List[dict], List[dict]]:
    """Split pool into (non_pinned, pinned) preserving order."""
    non_pinned = [e for e in pool if not e.get("is_pinned")]
    pinned = [e for e in pool if e.get("is_pinned")]
    return non_pinned, pinned


def _fill_from_pinned(
    selected: List[dict], pinned: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    """Exhaustion fallback: if non-pinned didn't fill N, add pinned entries."""
    if len(selected) >= n or not pinned:
        return selected
    selected_urls = {e["url"] for e in selected}
    for e in pinned:
        if len(selected) >= n:
            break
        if e["url"] not in selected_urls:
            e = dict(e)
            e["_selection_reason"] = "pinned_fallback"
            selected.append(e)
    if any(e.get("_selection_reason") == "pinned_fallback" for e in selected):
        debug.append({"action": "pinned_fallback_used",
                       "count": sum(1 for e in selected if e.get("_selection_reason") == "pinned_fallback")})
    return selected


# ---------------------------------------------------------------------------
# Skip OFF modes (1-4): no download filtering, select from ALL entries
# ---------------------------------------------------------------------------

def _mode_noskip_latest(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    """Mode 1 (skip=OFF, popular=OFF, random=OFF): Newest N entries."""
    non_pinned, pinned = _split_pinned(pool)
    non_pinned.sort(key=_recency_key, reverse=True)
    selected = non_pinned[:n]
    for s in selected:
        s["_selection_reason"] = "latest_non_pinned"
    selected = _fill_from_pinned(selected, pinned, n, debug)
    debug.append({"action": "mode_noskip_latest", "selected": len(selected)})
    return selected[:n]


def _mode_noskip_popular(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    """Mode 2 (skip=OFF, popular=ON, random=OFF): Most popular N entries."""
    non_pinned, pinned = _split_pinned(pool)
    non_pinned.sort(key=_popularity_key)
    selected = non_pinned[:n]
    for s in selected:
        s["_selection_reason"] = "popular"
    selected = _fill_from_pinned(selected, pinned, n, debug)
    debug.append({"action": "mode_noskip_popular", "selected": len(selected)})
    return selected[:n]


def _mode_noskip_random(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    """Mode 3 (skip=OFF, popular=OFF, random=ON): Random N entries."""
    non_pinned, pinned = _split_pinned(pool)
    pick = min(n, len(non_pinned))
    selected = random.sample(non_pinned, pick) if pick else []
    for s in selected:
        s["_selection_reason"] = "random"
    selected = _fill_from_pinned(selected, pinned, n, debug)
    debug.append({"action": "mode_noskip_random", "selected": len(selected)})
    return selected[:n]


def _mode_noskip_popular_random(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    """Mode 4 (skip=OFF, popular=ON, random=ON): Random wide sample, rank by popularity, top N."""
    non_pinned, pinned = _split_pinned(pool)
    sample_size = min(len(non_pinned), max(n * 3, 20))
    sample = random.sample(non_pinned, sample_size) if sample_size else []
    sample.sort(key=_popularity_key)
    selected = sample[:n]
    for s in selected:
        s["_selection_reason"] = "popular_random"
    selected = _fill_from_pinned(selected, pinned, n, debug)
    debug.append({"action": "mode_noskip_popular_random", "sample_size": sample_size, "selected": len(selected)})
    return selected[:n]


# ---------------------------------------------------------------------------
# Skip ON modes (5-8): already-downloaded removed from pool before entry
# ---------------------------------------------------------------------------

def _mode_skip_latest(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    """Mode 5 (skip=ON, popular=OFF, random=OFF): Hierarchical date-walk.

    Groups unseen videos by date, walks newest→oldest, picks from each group.
    Entries without dates go to a fallback group processed last.
    Exhaustion fallback: pinned entries fill remainder.
    """
    non_pinned, pinned = _split_pinned(pool)

    # Group by date
    date_groups: Dict[str, List[dict]] = {}
    for e in non_pinned:
        date_key = (e.get("posted_at") or "")[:8] or "00000000"
        date_groups.setdefault(date_key, []).append(e)

    # Sort dates descending (newest first), no-date group last
    sorted_dates = sorted(
        (d for d in date_groups if d != "00000000"),
        reverse=True,
    )
    if "00000000" in date_groups:
        sorted_dates.append("00000000")

    selected: List[dict] = []
    for date_key in sorted_dates:
        if len(selected) >= n:
            break
        group = date_groups[date_key]
        # Within each date group, sort by recency (sub-day granularity if available)
        group.sort(key=_recency_key, reverse=True)
        for e in group:
            if len(selected) >= n:
                break
            e["_selection_reason"] = f"date_walk_{date_key}"
            selected.append(e)

    selected = _fill_from_pinned(selected, pinned, n, debug)
    debug.append({
        "action": "mode_skip_latest",
        "date_groups": len(date_groups),
        "selected": len(selected),
    })
    return selected[:n]


def _mode_skip_popular(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    """Mode 6 (skip=ON, popular=ON, random=OFF): Most popular N from unseen."""
    non_pinned, pinned = _split_pinned(pool)
    non_pinned.sort(key=_popularity_key)
    selected = non_pinned[:n]
    for s in selected:
        s["_selection_reason"] = "popular_unseen"
    selected = _fill_from_pinned(selected, pinned, n, debug)
    debug.append({"action": "mode_skip_popular", "selected": len(selected)})
    return selected[:n]


def _mode_skip_random(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    """Mode 7 (skip=ON, popular=OFF, random=ON): Random N from unseen."""
    non_pinned, pinned = _split_pinned(pool)
    pick = min(n, len(non_pinned))
    selected = random.sample(non_pinned, pick) if pick else []
    for s in selected:
        s["_selection_reason"] = "random_unseen"
    selected = _fill_from_pinned(selected, pinned, n, debug)
    debug.append({"action": "mode_skip_random", "selected": len(selected)})
    return selected[:n]


def _mode_skip_popular_random(
    pool: List[dict], n: int, debug: List[dict],
) -> List[dict]:
    """Mode 8 (skip=ON, popular=ON, random=ON): Random sample from unseen, rank by popularity, top N."""
    non_pinned, pinned = _split_pinned(pool)
    sample_size = min(len(non_pinned), max(n * 3, 20))
    sample = random.sample(non_pinned, sample_size) if sample_size else []
    sample.sort(key=_popularity_key)
    selected = sample[:n]
    for s in selected:
        s["_selection_reason"] = "popular_random_unseen"
    selected = _fill_from_pinned(selected, pinned, n, debug)
    debug.append({"action": "mode_skip_popular_random", "sample_size": sample_size, "selected": len(selected)})
    return selected[:n]
