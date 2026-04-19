"""
Simple Firestore license admin helper for the Firebase MVP flow.

This script lets you create/update customer license documents without opening
Firestore manually for every client.
"""
from __future__ import annotations

import argparse
import json
import random
import string
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from modules.license.firebase_license_manager import FirestoreLicenseManager


def _build_manager() -> FirestoreLicenseManager:
    manager = FirestoreLicenseManager(app_version="1.0.0")
    manager._ensure_authenticated()
    return manager


def _normalize_expiry(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Expiry is required.")

    if "T" in raw:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        parsed = datetime.fromisoformat(f"{raw}T00:00:00+00:00")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat()


def _generate_license_key(prefix: str) -> str:
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(random.choice(alphabet) for _ in range(8))
    return f"{prefix}-{suffix}"


def _print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_create(args: argparse.Namespace) -> int:
    manager = _build_manager()
    license_key = str(args.license_key or "").strip() or _generate_license_key(args.prefix)
    payload = {
        "active": str(args.active).strip().lower() in {"1", "true", "yes", "y", "on"},
        "plan": str(args.plan or "basic").strip().lower(),
        "expiryAt": _normalize_expiry(args.expiry),
        "boundHardwareId": "",
        "boundDeviceName": "",
        "lastSeenAt": "",
        "lastInstallationId": "",
        "notes": str(args.notes or "").strip(),
    }
    manager._patch_document("licenses", license_key, payload)
    print(f"License created: {license_key}")
    _print_json(payload)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    manager = _build_manager()
    document = manager._get_document("licenses", args.license_key)
    if not document:
        print(f"License not found: {args.license_key}")
        return 1
    _print_json(document)
    return 0


def cmd_unbind(args: argparse.Namespace) -> int:
    manager = _build_manager()
    document = manager._get_document("licenses", args.license_key)
    if not document:
        print(f"License not found: {args.license_key}")
        return 1

    payload = {
        "boundHardwareId": "",
        "boundDeviceName": "",
        "lastInstallationId": "",
        "lastSeenAt": manager._iso_now(),
    }
    manager._patch_document("licenses", args.license_key, payload)
    print(f"License unbound: {args.license_key}")
    _print_json(payload)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    manager = _build_manager()
    document = manager._get_document("licenses", args.license_key)
    if not document:
        print(f"License not found: {args.license_key}")
        return 1

    payload: Dict[str, Any] = {}
    if args.plan:
        payload["plan"] = str(args.plan).strip().lower()
    if args.expiry:
        payload["expiryAt"] = _normalize_expiry(args.expiry)
    if args.notes is not None:
        payload["notes"] = str(args.notes).strip()
    if args.active is not None:
        payload["active"] = str(args.active).strip().lower() in {"1", "true", "yes", "y", "on"}

    if not payload:
        print("Nothing to update.")
        return 1

    manager._patch_document("licenses", args.license_key, payload)
    print(f"License updated: {args.license_key}")
    _print_json(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Firebase Firestore licenses for OneSoul.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a new license document.")
    create_parser.add_argument("--license-key", help="Explicit license key. If omitted, one is auto-generated.")
    create_parser.add_argument("--prefix", default="ONESOUL", help="Prefix for auto-generated license keys.")
    create_parser.add_argument("--plan", default="basic", help="License plan: basic/pro")
    create_parser.add_argument("--expiry", required=True, help="Expiry date. Examples: 2026-12-31 or 2026-12-31T00:00:00+00:00")
    create_parser.add_argument("--notes", default="", help="Optional customer notes.")
    create_parser.add_argument("--active", default="true", help="true/false")
    create_parser.set_defaults(func=cmd_create)

    show_parser = subparsers.add_parser("show", help="Show one license document.")
    show_parser.add_argument("license_key", help="License key/document ID")
    show_parser.set_defaults(func=cmd_show)

    update_parser = subparsers.add_parser("update", help="Update plan/expiry/active/notes on an existing license.")
    update_parser.add_argument("license_key", help="License key/document ID")
    update_parser.add_argument("--plan", help="basic/pro")
    update_parser.add_argument("--expiry", help="New expiry date")
    update_parser.add_argument("--notes", help="New notes")
    update_parser.add_argument("--active", help="true/false")
    update_parser.set_defaults(func=cmd_update)

    unbind_parser = subparsers.add_parser("unbind", help="Clear the hardware/device binding for a license.")
    unbind_parser.add_argument("license_key", help="License key/document ID")
    unbind_parser.set_defaults(func=cmd_unbind)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
