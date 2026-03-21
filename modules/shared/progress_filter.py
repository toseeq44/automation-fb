"""
Progress message filter for compact card-level GUI status.

The goal here is to keep only short, user-facing messages:
- method tags like [LG-0] / [DL-1]
- simple link counts
- simple cleanup summaries
- simple IX status

Paths, cookies, proxies, config internals, and other technical noise are hidden.
"""

import re


_DEBUG_TAG_RE = re.compile(r"\[(?:DL|LG)-\d+\]")
_TIMESTAMP_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s*")
_LINK_COUNT_RE = re.compile(r"(\d+)\s*links?", re.I)

_SUPPRESS_PATTERNS = [
    re.compile(r"cookie[_\s]?file|netscape|browser_cookies[/\\]", re.I),
    re.compile(r"proxy\s*[:=]|socks[45]|http[s]?://\d+\.\d+", re.I),
    re.compile(r"user[\-_]?agent\s*[:=]|mozilla/|chrome/\d", re.I),
    re.compile(r"config\s*[:=]\s*\{|settings\s*[:=]\s*\{|options\s*[:=]\s*\{", re.I),
    re.compile(r"_has_platform_cookies|_cookie_file_has_auth|strict\.auth|browser\.session\.layer", re.I),
    re.compile(r"workflow\s*[#\d]|layer\s*[0-9]", re.I),
    re.compile(r"cookie.*valid|validat.*cookie|auth.*marker", re.I),
    re.compile(r"_safe_write|canonical.*export|profile.*sync|_last_export", re.I),
    re.compile(r"learning.*cache|method.*score|performance.*history|cache.*key", re.I),
    re.compile(r"recovery.*chain|recovery.*step|recovery.*cooldown|attempt_recovery", re.I),
    re.compile(r"rate.*limit.*wait|cooldown.*\d+\.\d+s", re.I),
    re.compile(r"successfully downloaded:|success rate:|track file:|install/update yt-dlp", re.I),
    re.compile(r"cookies:\s|using cookies:|cookie \d+/\d+|using:\s+\S+", re.I),
    re.compile(r"auth:\s+synced|cookie sync|managed profile busy|pacing profile", re.I),
    re.compile(r"attempting download\.\.\.|removed leftover file|removed from .*\.txt", re.I),
    re.compile(r"fix:\s+copy ffmpeg folder|bundled ffmpeg failed", re.I),
    re.compile(r"ffmpeg ok:|ffprobe", re.I),
    re.compile(r"demucs .*fallback|demucs .*exception|dynamic link library|c10\.dll|torch\\lib", re.I),
    re.compile(r"ffmpeg error:|error applying option|parsed_afftdn|value .* out of range", re.I),
]


def _clean_method_message(msg: str) -> str | None:
    cleaned = _TIMESTAMP_RE.sub("", msg).strip()
    match = _DEBUG_TAG_RE.search(cleaned)
    if not match:
        return None

    tag = match.group(0)
    lower = cleaned.lower()
    link_match = _LINK_COUNT_RE.search(cleaned)

    if link_match and "link" in lower:
        return f"{tag} Found {link_match.group(1)} links"
    if "success" in lower or "verified" in lower:
        return f"{tag} Success"
    if "fail" in lower or "failed" in lower or "no valid media" in lower:
        return f"{tag} Failed"
    if "alternative formats" in lower:
        return f"{tag} Trying format fallback..."
    if "retrying without proxy" in lower:
        return f"{tag} Retrying..."
    if tag.startswith("[LG-"):
        return f"{tag} Scanning links..."
    return f"{tag} Downloading..."


def _clean_cleanup_message(msg: str) -> str | None:
    if not msg.startswith("[Cleanup]"):
        return None
    lower = msg.lower()
    if "checking old media" in lower or "checking top-level media" in lower:
        return "Cleanup: checking old media..."
    if "nothing to remove" in lower:
        return "Cleanup: nothing to remove"
    removed_match = re.search(r"removed\s+(\d+)\s+old file", msg, re.I)
    if removed_match:
        return f"Cleanup: removed {removed_match.group(1)} old files"
    if "failed to scan" in lower:
        return "Cleanup: scan failed"
    return None


def _clean_ix_message(msg: str) -> str | None:
    if "[IX" not in msg:
        return None

    lower = msg.lower()
    if "trying ixbrowser fallback" in lower:
        return "[IX] Connecting..."
    if "not logged in" in lower:
        return "[IX] Login required"
    if "queue ready" in lower:
        return "[IX] Links ready"
    if "refreshing" in lower:
        return "[IX] Refreshing session..."
    if "retrying" in lower:
        return "[IX] Retrying..."
    if "did not add any usable links" in lower or "no links" in lower:
        return "[IX] No links found"
    if "failed" in lower:
        return "[IX] Failed"

    link_match = _LINK_COUNT_RE.search(msg)
    if link_match:
        return f"[IX] Found {link_match.group(1)} links"
    return "[IX] Working..."


def filter_for_gui(msg: str) -> str | None:
    """Return a short GUI-safe message, or None to hide it."""
    if not msg:
        return None

    stripped = msg.strip()
    if not stripped:
        return None

    cleanup_msg = _clean_cleanup_message(stripped)
    if cleanup_msg is not None:
        return cleanup_msg

    ix_msg = _clean_ix_message(stripped)
    if ix_msg is not None:
        return ix_msg

    tagged = _clean_method_message(stripped)
    if tagged is not None:
        return tagged

    for pattern in _SUPPRESS_PATTERNS:
        if pattern.search(stripped):
            return None

    lower = stripped.lower()
    link_match = _LINK_COUNT_RE.search(stripped)
    if lower.startswith("runtime readiness failed:"):
        return "Runtime issue"
    if lower.startswith("runtime:"):
        return stripped[:90]
    if lower.startswith("auth ticket:"):
        if "public" in lower:
            return "Using public fallback..."
        if "none" in lower:
            return "Auth required"
        return "Session ready"
    if "auth source ready:" in lower:
        return "Session ready"
    if "no authenticated cookies available" in lower:
        return "Auth required"
    if lower.startswith("managed mode: authenticated link extraction not available"):
        return "Auth required"
    if "[public]" in lower and "fallback" in lower:
        return "Trying public fallback..."
    if lower.startswith("platform:"):
        return "Starting..."
    if lower.startswith("pacing profile:"):
        return None
    if lower.startswith("progress:"):
        return "Downloading..."
    if lower.startswith("error:"):
        return "Failed"
    if "expanding link pool" in lower or "more usable link" in lower:
        return "Checking more links..."
    if "backfill" in lower and "need" in lower:
        return "Checking more links..."
    if link_match and "link" in lower:
        return f"Found {link_match.group(1)} links"
    if "trying other approaches" in lower:
        return "Trying other approaches..."
    if "fetching latest videos from profile" in lower:
        return "Checking profile..."
    if "selected" in lower and "preparing downloads" in lower:
        return "Preparing download..."
    if lower.startswith("selected download ("):
        return "Downloading..."
    if "starting downloads" in lower:
        return "Starting download..."
    if "download queue ready" in lower:
        return "Starting download..."
    if "editing: splitting into" in lower:
        return "Splitting video..."
    if lower.startswith("split part "):
        return "Splitting video..."
    if "editing: split+edit" in lower:
        return "Editing clips..."
    if "split+edit: editing" in lower:
        return "Editing clips..."
    if "split+edit: reducing background music" in lower:
        return "Removing background music..."
    if "split+edit: demucs vocals ready" in lower:
        return "Background music removed"
    if "split+edit: enhancing voice" in lower:
        return "Enhancing voice..."
    if "split+edit: done" in lower:
        return "Clip edited"
    if "split+edit: failed" in lower:
        return "Editing failed"
    if "watermark: applying" in lower:
        return "Applying watermark..."
    if "watermark: done" in lower:
        return "Watermark done"
    if "continuing:" in lower and link_match and "links extracted" in lower:
        return f"Found {link_match.group(1)} links"
    if "no primary selection available" in lower:
        return "Trying backup links..."
    if "all videos already downloaded" in lower:
        return "Using fallback video..."
    if "no existing media files found" in lower:
        return "Cleanup: nothing to remove"

    return None


def filter_queue_progress_for_card(msg: str, creator_name: str) -> str | None:
    """
    Extract and clean a creator-specific queue progress message for card UI.

    Queue-level messages like "Queue: 2/26" should not overwrite the active
    card. Only messages explicitly scoped to the current creator are returned.
    """
    text = str(msg or "").strip()
    name = str(creator_name or "").strip()
    if not text or not name:
        return None

    bare = name.lstrip("@")
    candidates = []
    for candidate in (name, bare, f"@{bare}", f"@@{bare}"):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    scoped = None
    for candidate in candidates:
        prefix = f"{candidate}: "
        if text.startswith(prefix):
            scoped = text[len(prefix):].strip()
            break

    if not scoped:
        return None

    return filter_for_gui(scoped)
