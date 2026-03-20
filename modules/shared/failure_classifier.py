"""
Failure classification for recovery decisions.

Pure utility — no side effects, no imports beyond stdlib.
"""

from enum import Enum, auto


class FailureType(Enum):
    AUTH_EXPIRED = auto()      # Session/cookie expired or invalidated
    AUTH_MISSING = auto()      # No credentials available at all
    AUTH_WALL = auto()         # Page returned empty (auth wall, no error text)
    RATE_LIMITED = auto()      # Platform throttled or challenged
    CONTENT_GONE = auto()      # 404, deleted, or unavailable content
    NETWORK_ERROR = auto()     # Connection/timeout/DNS failures
    UNKNOWN = auto()           # Unclassified failure


# ── Pattern tables ──────────────────────────────────────────────

_AUTH_EXPIRED_PATTERNS = (
    "login", "sign in", "logged out", "session", "unauthorized", "401",
    "forbidden", "403", "cookie", "expired", "auth", "credential",
    "please log in", "not authenticated", "authentication required",
)

_AUTH_WALL_PATTERNS = (
    "auth_wall_suspected", "0_links:",
)

_RATE_LIMIT_PATTERNS = (
    "rate limit", "too many requests", "429", "throttl",
    "captcha", "verify", "suspicious", "blocked", "cooldown",
)

# Platform-specific challenge patterns (conservative for Instagram)
_PLATFORM_CHALLENGE_PATTERNS: dict[str, tuple[str, ...]] = {
    "instagram": ("/challenge/", "challenge_required"),
    "facebook": ("checkpoint", "challenge",),
    "tiktok": ("challenge",),
    "twitter": ("challenge",),
    "youtube": ("challenge",),
}

_CONTENT_GONE_PATTERNS = (
    "404", "not found", "deleted", "unavailable", "removed", "private",
    "does not exist", "no longer available",
)

_NETWORK_PATTERNS = (
    "timeout", "timed out", "connection", "dns", "network", "unreachable",
    "refused", "reset", "ssl", "certificate",
)


def classify_failure(error_text: str, platform: str = "") -> FailureType:
    """Classify an error string into a FailureType."""
    if not error_text:
        return FailureType.UNKNOWN

    lower = error_text.lower()

    # Auth wall (explicit marker from 0-link detection)
    if any(p in lower for p in _AUTH_WALL_PATTERNS):
        return FailureType.AUTH_WALL

    # Rate limiting (check before auth — rate limit messages sometimes contain "login")
    if any(p in lower for p in _RATE_LIMIT_PATTERNS):
        return FailureType.RATE_LIMITED

    # Platform-specific challenge tokens (conservative for Instagram)
    challenge_tokens = _PLATFORM_CHALLENGE_PATTERNS.get(platform, ("challenge",))
    if any(p in lower for p in challenge_tokens):
        return FailureType.RATE_LIMITED

    # Auth expired/missing
    if any(p in lower for p in _AUTH_EXPIRED_PATTERNS):
        return FailureType.AUTH_EXPIRED

    # Content gone
    if any(p in lower for p in _CONTENT_GONE_PATTERNS):
        return FailureType.CONTENT_GONE

    # Network errors
    if any(p in lower for p in _NETWORK_PATTERNS):
        return FailureType.NETWORK_ERROR

    return FailureType.UNKNOWN


def is_auth_failure(failure_type: FailureType) -> bool:
    """Return True if the failure type warrants auth recovery."""
    return failure_type in (
        FailureType.AUTH_EXPIRED,
        FailureType.AUTH_MISSING,
        FailureType.AUTH_WALL,
    )
