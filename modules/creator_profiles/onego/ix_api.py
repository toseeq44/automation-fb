"""
Fresh IX Browser API client for OneGo.
Communicates with the ixBrowser local REST API to list/open/close profiles.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger(__name__)


class IXAPIError(RuntimeError):
    """Raised on any IX API communication failure."""

    def __init__(self, message: str, payload: Optional[Dict[str, Any]] = None, code: Optional[int] = None):
        super().__init__(message)
        self.payload = payload or {}
        self.code = code


@dataclass
class IXProfile:
    profile_id: str
    profile_name: str
    status: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IXSession:
    profile_id: str
    debugging_address: Optional[str] = None
    webdriver_url: Optional[str] = None
    webdriver_path: Optional[str] = None  # path to chromedriver executable
    raw: Dict[str, Any] = field(default_factory=dict)


class IXBrowserClient:
    """Minimal client for ixBrowser local API (v2)."""

    def __init__(self, base_url: str, *, timeout: int = 120):
        base_url = (base_url or "").strip()
        if not base_url:
            raise IXAPIError("IX API base URL is empty.")
        if not base_url.startswith("http"):
            base_url = f"http://{base_url}"

        lower = base_url.lower().rstrip("/")
        if not lower.endswith("/api/v2") and not lower.endswith("/v2"):
            base_url = f"{base_url.rstrip('/')}/api/v2"

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        log.debug("[OneGo-IX] client init base_url=%s", self.base_url)

    # -- profiles ----------------------------------------------------------

    def list_profiles(self, *, limit: int = 9999) -> List[IXProfile]:
        """
        Return IX profiles.

        Uses a large limit and common pagination payload shapes to avoid
        default server-side short lists.
        """
        max_limit = max(1, int(limit or 1))
        payload_candidates = [
            {"limit": max_limit},
            {"page": 1, "limit": max_limit},
            {"current": 1, "size": max_limit},
            {},
        ]

        best_items: List[Dict[str, Any]] = []
        first_error: Optional[IXAPIError] = None

        for payload in payload_candidates:
            try:
                data = self._post("/profile-list", payload)
            except IXAPIError as exc:
                if first_error is None:
                    first_error = exc
                continue

            items = self._extract_list(data)
            if len(items) > len(best_items):
                best_items = items

            # Try page-based continuation when server reports total > first page.
            total = self._extract_total(data)
            supports_page = "page" in payload and isinstance(payload.get("page"), int)
            if supports_page and total and len(items) < min(total, max_limit):
                seen_ids = {
                    str(i.get("profile_id") or i.get("id"))
                    for i in items
                    if i.get("profile_id") or i.get("id")
                }
                page = 2
                while len(seen_ids) < min(total, max_limit):
                    paged_payload = dict(payload)
                    paged_payload["page"] = page
                    page_data = self._post("/profile-list", paged_payload)
                    page_items = self._extract_list(page_data)
                    if not page_items:
                        break

                    added = False
                    for item in page_items:
                        pid = item.get("profile_id") or item.get("id")
                        if not pid:
                            continue
                        spid = str(pid)
                        if spid in seen_ids:
                            continue
                        seen_ids.add(spid)
                        items.append(item)
                        added = True
                        if len(seen_ids) >= max_limit:
                            break
                    if not added:
                        break
                    page += 1

                if len(items) > len(best_items):
                    best_items = items

            if len(best_items) >= max_limit:
                break

        if not best_items and first_error is not None:
            raise first_error

        return self._build_profiles(best_items[:max_limit])

    def find_profile(self, hint: str) -> Optional[IXProfile]:
        hint = (hint or "").strip().lower()
        if not hint:
            return None
        for p in self.list_profiles():
            if p.profile_id.lower() == hint or p.profile_name.lower() == hint:
                return p
        for p in self.list_profiles():
            if hint in p.profile_name.lower():
                return p
        return None

    def open_profile(self, profile_id: str) -> IXSession:
        try:
            pid = int(profile_id)
        except (ValueError, TypeError):
            pid = profile_id
        data = self._post("/profile-open", {"profile_id": pid})
        session_data = self._extract_data(data)

        webdriver_url = (
            session_data.get("webdriver")
            or session_data.get("webdriver_url")
            or session_data.get("webdriver_path")
        )
        debug_addr = (
            session_data.get("debugging_address")
            or session_data.get("debuggingAddress")
            or session_data.get("debug_port")
            or session_data.get("debugPort")
        )
        if debug_addr and str(debug_addr).isdigit():
            debug_addr = f"127.0.0.1:{debug_addr}"

        # webdriver_path: the chromedriver executable for this profile's browser
        wd_path = (
            session_data.get("webdriver_path")
            or session_data.get("driver_path")
            or session_data.get("chromedriver_path")
        )
        # webdriver_url may actually be a local path (IX returns it in 'webdriver')
        if not wd_path and webdriver_url and not webdriver_url.startswith("http"):
            wd_path = webdriver_url

        return IXSession(
            profile_id=session_data.get("profile_id", str(pid)),
            debugging_address=debug_addr,
            webdriver_url=webdriver_url,
            webdriver_path=wd_path,
            raw=session_data,
        )

    def close_profile(self, profile_id: str) -> bool:
        try:
            pid = int(profile_id)
        except (ValueError, TypeError):
            pid = profile_id
        try:
            self._post("/profile-close", {"profile_id": pid})
            return True
        except IXAPIError as exc:
            log.warning("[OneGo-IX] close_profile failed: %s", exc)
            return False

    # -- internals ---------------------------------------------------------

    def _post(self, path: str, payload: dict) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            resp = self._session.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise IXAPIError(f"Cannot reach IX API at {url}: {exc}") from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise IXAPIError(f"IX API returned non-JSON: {resp.text[:200]}") from exc

        if resp.status_code >= 400:
            raise IXAPIError(f"IX API HTTP {resp.status_code}", data)

        error_obj = data.get("error")
        if isinstance(error_obj, dict):
            code = error_obj.get("code")
            if code == 2013:
                raise IXAPIError(
                    "IX kernel missing — please start ixBrowser first",
                    data, code=2013,
                )
            if code not in (0, 200, None):
                raise IXAPIError(
                    f"IX API error code={code}: {error_obj.get('message', '')}",
                    data, code=code,
                )
        else:
            code = data.get("code")
            if code == 2013:
                raise IXAPIError(
                    "IX kernel missing — please start ixBrowser first",
                    data, code=2013,
                )
            if code not in (0, 200, None):
                raise IXAPIError(data.get("message", "Unknown IX error"), data, code=code)

        return data

    @staticmethod
    def _extract_list(payload: Dict[str, Any]) -> list:
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("data", "list", "profiles"):
                if isinstance(data.get(key), list):
                    return data[key]
        for key in ("profiles", "list"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return []

    @staticmethod
    def _extract_total(payload: Dict[str, Any]) -> Optional[int]:
        data = payload.get("data")
        if isinstance(data, dict):
            total = data.get("total")
            if isinstance(total, int):
                return total
        total = payload.get("total")
        if isinstance(total, int):
            return total
        return None

    @staticmethod
    def _build_profiles(items: List[Dict[str, Any]]) -> List[IXProfile]:
        profiles: List[IXProfile] = []
        seen: set[str] = set()
        for item in items:
            pid = item.get("profile_id") or item.get("id")
            if not pid:
                continue
            spid = str(pid)
            if spid in seen:
                continue
            seen.add(spid)
            pname = item.get("profile_name") or item.get("name") or ""
            status = item.get("status") or item.get("profile_status") or ""
            profiles.append(
                IXProfile(
                    profile_id=spid,
                    profile_name=str(pname),
                    status=str(status),
                    raw=item,
                )
            )
        return profiles

    @staticmethod
    def _extract_data(payload: Dict[str, Any]) -> dict:
        data = payload.get("data")
        if isinstance(data, dict):
            inner = data.get("data")
            if isinstance(inner, dict):
                return inner
            return data
        return payload
