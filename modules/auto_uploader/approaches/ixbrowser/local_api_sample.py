"""
Simple helper script to demonstrate ixBrowser Local API usage.

Requirements:
    pip install requests

Usage:
    python -m modules.auto_uploader.approaches.ixbrowser.local_api_sample
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import requests

BASE_URL = os.environ.get("IX_API_BASE", "http://127.0.0.1:53200/v2").rstrip("/")
HEADERS = {"Content-Type": "application/json"}


def _build_url(path: str) -> str:
    path = path.strip()
    if path.startswith("http"):
        return path
    if path.startswith("/"):
        path = path[1:]
    return f"{BASE_URL}/{path}"


def _request(method: str, path: str, json: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = _build_url(path)
    response = requests.request(method, url, json=json, headers=HEADERS, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in (0, 200, None):
        raise RuntimeError(f"ixBrowser API error: {payload}")
    return payload


def _extract_profiles(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("list"), list):
            return data["list"]
        if isinstance(data.get("profiles"), list):
            return data["profiles"]
    if isinstance(payload.get("profiles"), list):
        return payload["profiles"]
    if isinstance(payload.get("list"), list):
        return payload["list"]
    return []


def main() -> None:
    profile_payload = _request("POST", "profile-list", json={})
    profiles = _extract_profiles(profile_payload)
    if not profiles:
        raise RuntimeError("No ixBrowser profiles returned by the Local API.")

    first_profile = profiles[0]
    profile_id = first_profile.get("profile_id") or first_profile.get("id")
    profile_name = first_profile.get("profile_name") or first_profile.get("name") or profile_id

    print(f"Launching profile: {profile_name} ({profile_id})")
    session_payload = _request(
        "POST",
        "profile-open",
        json={"profile_id": profile_id, "cookies_backup": False, "load_profile_info_page": False},
    )
    session_data = session_payload.get("data", session_payload)
    debugging_address = session_data.get("debugging_address") or session_data.get("debuggingAddress")
    print(f"Debugging address: {debugging_address}")

    try:
        print("Profile is running. Attach your automation to the debugging address.")
    finally:
        _request("POST", "profile-close", json={"profile_id": profile_id})
        print("Profile closed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - convenience script
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
