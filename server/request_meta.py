"""
Helpers for extracting useful client network information behind proxies/tunnels.
"""
from __future__ import annotations

import ipaddress
from typing import Optional


def _normalize_ip(value: str | None) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    # X-Forwarded-For can contain a list; first hop is the original client.
    if "," in text:
        text = text.split(",", 1)[0].strip()
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return None


def extract_client_public_ip(req) -> str:
    """
    Best-effort public/client IP resolution behind Cloudflare, reverse proxies,
    and local forwarding tools such as cloudflared.
    """
    header_candidates = [
        req.headers.get("CF-Connecting-IP"),
        req.headers.get("True-Client-IP"),
        req.headers.get("X-Forwarded-For"),
        req.headers.get("X-Real-IP"),
    ]

    for candidate in header_candidates:
        resolved = _normalize_ip(candidate)
        if resolved:
            return resolved

    return _normalize_ip(getattr(req, "remote_addr", None)) or "unknown"
