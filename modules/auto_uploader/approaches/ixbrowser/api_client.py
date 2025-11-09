"""Helper client for ixBrowser Local API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class IXBrowserAPIError(RuntimeError):
    """Raised when the ixBrowser local API responds with an error."""

    def __init__(self, message: str, payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.payload = payload or {}


@dataclass
class IXProfileInfo:
    """Simplified representation of an ixBrowser profile."""

    profile_id: str
    profile_name: str
    status: str = ""
    raw: Dict[str, Any] = None


@dataclass
class IXProfileSession:
    """Data returned when a profile is opened."""

    profile_id: str
    webdriver_url: Optional[str]
    debugging_address: Optional[str]
    raw: Dict[str, Any]


class IXBrowserAPI:
    """Tiny wrapper around ixBrowser's local REST API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: int = 20,
    ) -> None:
        if not base_url:
            raise IXBrowserAPIError("ixBrowser API base URL is missing.")

        base_url = base_url.strip()
        if not base_url.startswith("http"):
            base_url = f"http://{base_url}"

        lower_url = base_url.lower().rstrip("/")
        if not lower_url.endswith("/api/v2") and not lower_url.endswith("/v2"):
            base_url = f"{base_url.rstrip('/')}/v2"

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip() if api_key else ""
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

        if self.api_key:
            self._session.headers["Authorization"] = f"APIKEY {self.api_key}"

        self._profile_cache: List[IXProfileInfo] = []
        logger.debug("IXBrowserAPI initialized (base_url=%s)", self.base_url)

    # ------------------------------------------------------------------ #
    # Public helpers                                                     #
    # ------------------------------------------------------------------ #
    def list_profiles(self, *, use_cache: bool = True) -> List[IXProfileInfo]:
        """Return all profiles available on the ixBrowser instance."""
        if use_cache and self._profile_cache:
            return list(self._profile_cache)

        data = self._request("POST", "/profile-list", json={})
        profile_payload = self._extract_list(data)

        profiles: List[IXProfileInfo] = []
        for item in profile_payload:
            profile_id = item.get("profile_id") or item.get("id")
            profile_name = item.get("profile_name") or item.get("name") or ""
            status = item.get("status") or item.get("profile_status") or ""
            if not profile_id:
                continue
            profiles.append(
                IXProfileInfo(
                    profile_id=str(profile_id),
                    profile_name=str(profile_name),
                    status=str(status),
                    raw=item,
                )
            )

        self._profile_cache = list(profiles)
        return profiles

    def find_profile(self, identifier: str) -> Optional[IXProfileInfo]:
        """Find a profile either by ID or by name."""
        identifier = (identifier or "").strip()
        if not identifier:
            return None

        profiles = self.list_profiles()
        ident_lower = identifier.lower()

        for profile in profiles:
            if profile.profile_id.lower() == ident_lower:
                return profile

        for profile in profiles:
            if profile.profile_name.lower() == ident_lower:
                return profile

        # Try loose contains match for convenience
        for profile in profiles:
            if ident_lower in profile.profile_name.lower():
                return profile

        return None

    def open_profile(self, profile_id: str, **options: Any) -> IXProfileSession:
        """Open an ixBrowser profile and return session info."""
        payload: Dict[str, Any] = {"profile_id": profile_id}
        payload.update(options)

        data = self._request("POST", "/profile-open", json=payload)
        session_payload = self._extract_data(data)

        webdriver_url = session_payload.get("webdriver") or session_payload.get("webdriver_url")
        debugging_address = session_payload.get("debugging_address") or session_payload.get("debuggingAddress")

        return IXProfileSession(
            profile_id=session_payload.get("profile_id", profile_id),
            webdriver_url=webdriver_url,
            debugging_address=debugging_address,
            raw=session_payload,
        )

    def close_profile(self, profile_id: str) -> bool:
        """Close a running ixBrowser profile."""
        payload = {"profile_id": profile_id}
        data = self._request("POST", "/profile-close", json=payload)
        session_payload = self._extract_data(data)
        logger.debug("ixBrowser profile '%s' closed: %s", profile_id, session_payload)
        return True

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        url = self._build_url(path)
        try:
            response = self._session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise IXBrowserAPIError(f"Unable to reach ixBrowser API at {self.base_url}: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("ixBrowser API returned non-JSON body: %s", response.text[:200])
            raise IXBrowserAPIError("ixBrowser API returned invalid JSON.", {"text": response.text}) from exc

        if response.status_code >= 400:
            raise IXBrowserAPIError(
                f"ixBrowser API HTTP {response.status_code}: {payload}",
                payload,
            )

        code = payload.get("code")
        if code not in (0, 200, None):
            raise IXBrowserAPIError(payload.get("message", "Unknown ixBrowser API error"), payload)

        return payload

    @staticmethod
    def _extract_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "list" in data and isinstance(data["list"], list):
                return data["list"]
            if "profiles" in data and isinstance(data["profiles"], list):
                return data["profiles"]
        if "profiles" in payload and isinstance(payload["profiles"], list):
            return payload["profiles"]
        if "list" in payload and isinstance(payload["list"], list):
            return payload["list"]
        return []

    @staticmethod
    def _extract_data(payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return payload

    def _build_url(self, path: str) -> str:
        """Combine base URL with relative path safely."""
        if path.startswith("http"):
            return path

        cleaned = path.strip()
        if cleaned.startswith("/"):
            cleaned = cleaned[1:]

        return f"{self.base_url}/{cleaned}"
