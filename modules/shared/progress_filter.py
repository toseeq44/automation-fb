"""
Progress message filter for GUI surfaces.

Suppresses or replaces internal method names, cookie paths, proxy details,
UA strings, workflow tags, rate-limit messages, auth internals, and config dumps
so the user sees clean, friendly status messages.
"""

import re

# ── Suppression patterns (message is hidden entirely) ─────────

_SUPPRESS_PATTERNS = [
    # Cookie file paths
    re.compile(r'cookie[_\s]?file|\.txt\b|netscape|browser_cookies[/\\]', re.I),
    # Proxy details
    re.compile(r'proxy\s*[:=]|socks[45]|http[s]?://\d+\.\d+', re.I),
    # User-Agent strings
    re.compile(r'user[\-_]?agent\s*[:=]|mozilla/|chrome/\d', re.I),
    # Config/settings dumps
    re.compile(r'config\s*[:=]\s*\{|settings\s*[:=]\s*\{|options\s*[:=]\s*\{', re.I),
    # Auth internals
    re.compile(r'_has_platform_cookies|_cookie_file_has_auth|strict.auth|browser.session.layer', re.I),
    # Workflow tags
    re.compile(r'workflow\s*[#\d]|layer\s*[0-9]', re.I),
    # Cookie validation messages
    re.compile(r'cookie.*valid|validat.*cookie|auth.*marker', re.I),
    # Sync/export details
    re.compile(r'_safe_write|canonical.*export|profile.*sync|_last_export', re.I),
    # Strategy/learning internals
    re.compile(r'learning.*cache|method.*score|performance.*history|cache.*key', re.I),
    # Recovery internals (keep "Checking access..." but hide details)
    re.compile(r'recovery.*chain|recovery.*step|recovery.*cooldown|attempt_recovery', re.I),
    # Rate-limit wait messages
    re.compile(r'IP\s*Protection.*wait|rate.*limit.*wait|cooldown.*\d+\.\d+s', re.I),
]

# ── Replacement patterns (message is rewritten) ──────────────

_REPLACEMENT_RULES = [
    # Method attempt messages → generic "Scanning..."
    (re.compile(r'(?:trying|attempting|using)\s*[:.]?\s*method\s+', re.I), "Scanning..."),
    # Method names with "Method X:" prefix
    (re.compile(r'Method\s+[0-9A-Za-z]+\s*:', re.I), None),  # suppress
    # yt-dlp / gallery-dl / instaloader / selenium / playwright mentions
    (re.compile(r'\b(?:yt[\-_]?dlp|gallery[\-_]?dl|instaloader|selenium|playwright|chromium)\b', re.I), None),
    # Success with link count → keep but clean
    (re.compile(r'.+→\s*(\d+)\s*links?\s+in\s+[\d.]+s', re.I), None),  # handled specially
    # "Best method didn't work" → simplified
    (re.compile(r"best method didn't work", re.I), "Trying other approaches..."),
    # Learning cache found → simplified
    (re.compile(r'learning cache found', re.I), "Using preferred approach..."),
]


def filter_for_gui(msg: str) -> str | None:
    """Filter a progress message for GUI display.

    Returns:
        str: The cleaned message to display
        None: Message should be suppressed entirely
    """
    if not msg:
        return None

    stripped = msg.strip()
    if not stripped:
        return None

    # Check suppression patterns
    for pattern in _SUPPRESS_PATTERNS:
        if pattern.search(stripped):
            return None

    # Check replacement rules
    for pattern, replacement in _REPLACEMENT_RULES:
        if pattern.search(stripped):
            if replacement is None:
                return None
            return replacement

    # Extract link count from method success messages (e.g., "✅ Method X → 15 links in 2.3s")
    link_match = re.search(r'(\d+)\s*links?\s+in\s+[\d.]+s', stripped)
    if link_match:
        count = link_match.group(1)
        return f"Found {count} links"

    # Pass through messages that don't match any pattern
    return stripped
