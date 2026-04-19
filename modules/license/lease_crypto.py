"""
Signed offline lease helpers for the OneSoul client.

The client only carries the public verification key. The server signs lease
payloads with the paired private key and the client verifies them locally.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


LEASE_TOKEN_PREFIX = "OSLEASE1"
LEASE_PUBLIC_KEY_B64 = "9IC5YoDK61jBr6PGtsfQ3O8qMdWfop9GUw1A7tl2CgU="


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def public_key() -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(_b64url_decode(LEASE_PUBLIC_KEY_B64))


def decode_lease_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a signed lease token.

    Raises:
        ValueError: if the token is malformed or the signature is invalid.
    """
    if not token or not token.startswith(f"{LEASE_TOKEN_PREFIX}."):
        raise ValueError("Invalid lease token format")

    try:
        _, payload_b64, signature_b64 = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Corrupted lease token") from exc

    payload_bytes = _b64url_decode(payload_b64)
    signature = _b64url_decode(signature_b64)

    try:
        public_key().verify(signature, payload_bytes)
    except Exception as exc:
        raise ValueError("Lease signature verification failed") from exc

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Lease payload decoding failed") from exc

    required = {
        "license_key",
        "hardware_id",
        "installation_id",
        "plan_type",
        "issued_at",
        "lease_expires_at",
        "lease_id",
        "app_id",
    }
    missing = required.difference(payload.keys())
    if missing:
        raise ValueError(f"Lease payload missing fields: {', '.join(sorted(missing))}")

    return payload


def validate_lease_payload(
    payload: Dict[str, Any],
    *,
    expected_license_key: str,
    expected_hardware_id: str,
    expected_installation_id: str,
    expected_app_id: str = "onesoul",
) -> Dict[str, Any]:
    """
    Validate lease claims after signature verification.

    Raises:
        ValueError: if any claim is invalid.
    """
    if payload.get("app_id") != expected_app_id:
        raise ValueError("Lease app scope mismatch")
    if payload.get("license_key") != expected_license_key:
        raise ValueError("Lease license mismatch")
    if payload.get("hardware_id") != expected_hardware_id:
        raise ValueError("Lease hardware mismatch")
    if payload.get("installation_id") != expected_installation_id:
        raise ValueError("Lease installation mismatch")

    expiry = parse_utc(payload["lease_expires_at"])
    if expiry <= utcnow():
        raise ValueError("Lease expired")

    return payload


__all__ = [
    "LEASE_TOKEN_PREFIX",
    "LEASE_PUBLIC_KEY_B64",
    "decode_lease_token",
    "validate_lease_payload",
    "parse_utc",
    "utcnow",
]
