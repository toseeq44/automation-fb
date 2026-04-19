"""
Shared client-presence timing helpers for the license server.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone


DEFAULT_HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("CLIENT_HEARTBEAT_INTERVAL_SECONDS", "45"))
ONLINE_WINDOW_SECONDS = int(
    os.getenv("CLIENT_ONLINE_WINDOW_SECONDS", str(max(120, DEFAULT_HEARTBEAT_INTERVAL_SECONDS * 3)))
)
RECENT_WINDOW_SECONDS = int(
    os.getenv("CLIENT_RECENT_WINDOW_SECONDS", str(max(1800, ONLINE_WINDOW_SECONDS * 4)))
)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_dt(value) -> datetime | None:
    if not value:
        return None
    if getattr(value, "tzinfo", None) is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def presence_state_code(last_seen, is_online: bool) -> str:
    normalized_last_seen = _normalize_dt(last_seen)
    if not normalized_last_seen:
        return "offline"

    seconds = max(0, int((_utc_now_naive() - normalized_last_seen).total_seconds()))
    if is_online and seconds <= ONLINE_WINDOW_SECONDS:
        return "online"
    if seconds <= RECENT_WINDOW_SECONDS:
        return "recent"
    return "offline"


def presence_state_label(last_seen, is_online: bool) -> str:
    code = presence_state_code(last_seen, is_online)
    if code == "online":
        return "Online"
    if code == "recent":
        return "Recent"
    return "Offline"
