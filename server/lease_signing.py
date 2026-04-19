"""
Server-side lease signing helpers.

The client only contains the matching public key in `modules/license/lease_crypto.py`.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


LEASE_TOKEN_PREFIX = "OSLEASE1"
LEASE_SIGNING_SEED = "ONESOUL_LEASE_SIGNING_SEED_v1_2026"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _private_key() -> Ed25519PrivateKey:
    seed = hashlib.sha256(LEASE_SIGNING_SEED.encode("utf-8")).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def issue_lease_token(
    *,
    license_key: str,
    hardware_id: str,
    installation_id: str,
    plan_type: str,
    duration_days: int = 7,
    app_id: str = "onesoul",
) -> Dict[str, Any]:
    """
    Issue a signed offline lease for the client.
    """
    now = _utcnow()
    payload = {
        "app_id": app_id,
        "lease_id": secrets.token_hex(16),
        "license_key": license_key,
        "hardware_id": hardware_id,
        "installation_id": installation_id,
        "plan_type": str(plan_type or "basic").lower(),
        "issued_at": _serialize_datetime(now),
        "lease_expires_at": _serialize_datetime(now + timedelta(days=max(1, duration_days))),
    }
    payload_bytes = _canonical_payload_bytes(payload)
    signature = _private_key().sign(payload_bytes)
    token = f"{LEASE_TOKEN_PREFIX}.{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"
    return {
        "lease_token": token,
        "lease_payload": payload,
    }
