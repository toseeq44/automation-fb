"""
License Manager Module
Handles license activation, validation, lease verification, and heartbeat
presence tracking.
"""
from __future__ import annotations

import json
import base64
import hashlib
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from cryptography.fernet import Fernet

from modules.config.utils import get_config_directory
from .hardware_id import generate_hardware_id, get_device_name, get_preferred_lan_ip
from .lease_crypto import decode_lease_token, parse_utc, utcnow, validate_lease_payload


BOOTSTRAP_CACHE_SECONDS = 300


class LicenseManager:
    """
    Manages license operations for the OneSoul application.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:5000",
        app_version: str = "1.0.0",
        fallback_urls: Optional[List[str]] = None,
        bootstrap_urls: Optional[List[str]] = None,
        remember_last_good_url: Optional[bool] = None,
    ):
        self.app_version = app_version
        self.license_dir = Path.home() / ".onesoul"
        self.config_dir = get_config_directory()
        self.license_file = self.license_dir / "license.dat"
        self.identity_file = self.license_dir / "installation.json"
        self.endpoint_config_files = self._get_endpoint_config_files()
        self.endpoint_state_file = self.license_dir / "license_endpoint_state.json"
        self.license_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.installation_id = self._load_or_create_installation_id()
        self.grace_period_days = 7
        self.last_status_code = "uninitialized"
        self.encryption_key = self._generate_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        self._io_lock = threading.RLock()
        self._bootstrap_cache_urls: List[str] = []
        self._bootstrap_cache_refreshed_at: Optional[datetime] = None
        self.endpoint_config = self._load_endpoint_config()
        if fallback_urls:
            merged_fallbacks = list(self.endpoint_config.get("fallback_urls", []) or [])
            merged_fallbacks.extend(fallback_urls)
            self.endpoint_config["fallback_urls"] = merged_fallbacks
        if bootstrap_urls:
            merged_bootstrap_urls = list(self.endpoint_config.get("bootstrap_urls", []) or [])
            merged_bootstrap_urls.extend(bootstrap_urls)
            self.endpoint_config["bootstrap_urls"] = merged_bootstrap_urls
        if remember_last_good_url is not None:
            self.endpoint_config["remember_last_good_url"] = bool(remember_last_good_url)
        self._remember_last_good_url = bool(self.endpoint_config.get("remember_last_good_url", True))
        self.server_url = self._normalize_server_url(server_url)
        fixed_primary = self._get_primary_endpoint_url()
        if fixed_primary and (not self.server_url or self._should_ignore_dynamic_endpoint(self.server_url)):
            self.server_url = fixed_primary
        if not self.server_url:
            remembered_url = self._load_last_good_server_url()
            if remembered_url and not self._should_ignore_dynamic_endpoint(remembered_url):
                self.server_url = remembered_url

    def _set_status(self, code: str) -> None:
        self.last_status_code = code

    def _load_or_create_installation_id(self) -> str:
        try:
            if self.identity_file.exists():
                payload = json.loads(self.identity_file.read_text(encoding="utf-8"))
                installation_id = str(payload.get("installation_id", "")).strip()
                if installation_id:
                    return installation_id
        except Exception:
            pass

        installation_id = uuid.uuid4().hex
        payload = {
            "installation_id": installation_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.identity_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return installation_id

    def _generate_encryption_key(self) -> bytes:
        hardware_id = generate_hardware_id()
        key_material = hashlib.sha256(hardware_id.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(key_material)

    def _client_network_snapshot(self) -> dict:
        """Best-effort local network hints sent to the license server."""
        return {
            "client_lan_ip": get_preferred_lan_ip(),
        }

    def _default_endpoint_config(self) -> Dict[str, object]:
        return {
            "primary_url": "",
            "fallback_urls": [],
            "bootstrap_urls": [],
            "remember_last_good_url": True,
        }

    def _get_endpoint_config_files(self) -> List[Path]:
        files: List[Path] = []
        project_root = Path(__file__).resolve().parents[2]
        candidates = [
            project_root / "license_endpoints.json",
            Path.cwd() / "license_endpoints.json",
            self.config_dir / "license_endpoints.json",
        ]

        seen = set()
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except Exception:
                resolved = candidate

            key = str(resolved).lower()
            if key in seen:
                continue

            seen.add(key)
            files.append(candidate)

        return files

    def _load_endpoint_config(self) -> Dict[str, object]:
        config = self._default_endpoint_config()
        for config_file in self.endpoint_config_files:
            try:
                if not config_file.exists():
                    continue
                loaded = json.loads(config_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    config.update(loaded)
            except Exception:
                continue
        return config

    def _normalize_server_url(self, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if "://" not in text:
            if text.startswith(("localhost", "127.", "10.", "192.168.", "172.")):
                text = f"http://{text}"
            else:
                text = f"https://{text}"
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        return text.rstrip("/")

    def _is_ephemeral_quick_tunnel(self, value: object) -> bool:
        normalized = self._normalize_server_url(value)
        return normalized.endswith(".trycloudflare.com")

    def _is_local_only_endpoint(self, value: object) -> bool:
        normalized = self._normalize_server_url(value)
        if not normalized:
            return False
        host = (urlparse(normalized).hostname or "").strip().lower()
        return host in {"localhost", "127.0.0.1"}

    def _get_primary_endpoint_url(self) -> str:
        return self._normalize_server_url(self.endpoint_config.get("primary_url"))

    def _has_fixed_primary_endpoint(self) -> bool:
        primary_url = self._get_primary_endpoint_url()
        if not primary_url:
            return False
        return not self._is_ephemeral_quick_tunnel(primary_url) and not self._is_local_only_endpoint(primary_url)

    def _should_ignore_dynamic_endpoint(self, value: object) -> bool:
        normalized = self._normalize_server_url(value)
        if not normalized or not self._has_fixed_primary_endpoint():
            return False
        return self._is_ephemeral_quick_tunnel(normalized)

    def _unique_server_urls(self, values: List[object]) -> List[str]:
        seen = set()
        urls: List[str] = []
        for value in values:
            normalized = self._normalize_server_url(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        return urls

    def _load_endpoint_state(self) -> Dict[str, object]:
        try:
            if self.endpoint_state_file.exists():
                payload = json.loads(self.endpoint_state_file.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
        except Exception:
            pass
        return {}

    def _save_endpoint_state(self, payload: Dict[str, object]) -> None:
        try:
            self.endpoint_state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_last_good_server_url(self) -> str:
        state = self._load_endpoint_state()
        remembered = self._normalize_server_url(state.get("last_good_url"))
        if remembered and self._should_ignore_dynamic_endpoint(remembered):
            return ""
        return remembered

    def _remember_working_server_url(self, base_url: str) -> None:
        normalized = self._normalize_server_url(base_url)
        if not normalized:
            return
        self.server_url = normalized
        if not self._remember_last_good_url:
            return
        if self._should_ignore_dynamic_endpoint(normalized):
            return
        state = self._load_endpoint_state()
        state["last_good_url"] = normalized
        state["last_success_at"] = utcnow().isoformat()
        self._save_endpoint_state(state)

    def _fetch_bootstrap_urls(self) -> List[str]:
        bootstrap_urls = self._unique_server_urls(self.endpoint_config.get("bootstrap_urls", []) or [])
        if not bootstrap_urls:
            self._bootstrap_cache_urls = []
            self._bootstrap_cache_refreshed_at = utcnow()
            return []

        now = utcnow()
        if (
            self._bootstrap_cache_refreshed_at is not None
            and (now - self._bootstrap_cache_refreshed_at).total_seconds() < BOOTSTRAP_CACHE_SECONDS
        ):
            return list(self._bootstrap_cache_urls)

        discovered: List[str] = []
        for bootstrap_url in bootstrap_urls:
            try:
                response = requests.get(bootstrap_url, timeout=5)
                if response.status_code != 200:
                    continue
                payload = response.json()
            except Exception:
                continue

            raw_candidates: List[object] = []
            if isinstance(payload, dict):
                raw_candidates.extend([payload.get("primary_url")])
                raw_candidates.extend(payload.get("active_urls", []) or [])
                raw_candidates.extend(payload.get("fallback_urls", []) or [])
            elif isinstance(payload, list):
                raw_candidates.extend(payload)

            discovered.extend(self._unique_server_urls(raw_candidates))

        self._bootstrap_cache_urls = self._unique_server_urls(discovered)
        self._bootstrap_cache_refreshed_at = now
        return list(self._bootstrap_cache_urls)

    def _server_url_candidates(self) -> List[str]:
        state = self._load_endpoint_state()
        last_good_url = self._normalize_server_url(state.get("last_good_url"))
        if self._should_ignore_dynamic_endpoint(last_good_url):
            last_good_url = ""
        env_url = self._normalize_server_url(os.getenv("ONESOUL_LICENSE_URL"))
        endpoint_primary = self._get_primary_endpoint_url()
        endpoint_fallbacks = self._unique_server_urls(self.endpoint_config.get("fallback_urls", []) or [])
        configured_server_url = self.server_url
        if self._should_ignore_dynamic_endpoint(configured_server_url):
            configured_server_url = ""
        candidates: List[object] = [
            env_url,
            endpoint_primary,
            *self._fetch_bootstrap_urls(),
            last_good_url,
            configured_server_url,
            *endpoint_fallbacks,
        ]
        return self._unique_server_urls(candidates)

    def _should_try_next_server(self, response: requests.Response, payload: dict) -> bool:
        if response.status_code >= 500:
            return True
        content_type = str(response.headers.get("content-type", "")).lower()
        message = str(payload.get("message", "") or "").strip().lower()
        if "json" not in content_type and message.startswith(("<!doctype", "<html", "<?xml")):
            return True
        return False

    def get_active_server_url(self) -> str:
        endpoint_primary = self._get_primary_endpoint_url()
        last_good_url = self._load_last_good_server_url()
        if self._has_fixed_primary_endpoint():
            return endpoint_primary or last_good_url or self.server_url
        return last_good_url or endpoint_primary or self.server_url

    def get_server_url_candidates(self) -> List[str]:
        return self._server_url_candidates()

    def _report_creator_links(
        self,
        *,
        local_license: dict,
        task_id: str,
        success: bool,
        payload: Optional[dict] = None,
        error_message: str = "",
    ) -> Tuple[bool, str]:
        file_name = ""
        creator_count = 0
        if payload:
            creator_count = int(payload.get("creator_count", 0) or 0)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            file_name = f"creator_links_{self.installation_id}_{timestamp}.json"

        ok, response = self._make_api_request(
            "license/report-creator-links",
            {
                "license_key": local_license.get("license_key"),
                "hardware_id": local_license.get("hardware_id"),
                "installation_id": self.installation_id,
                "device_name": local_license.get("device_name") or get_device_name(),
                "task_id": task_id,
                "lease_token": local_license.get("lease_token"),
                "success": success,
                "file_name": file_name,
                "creator_count": creator_count,
                "payload": payload or {},
                "error_message": error_message,
                **self._client_network_snapshot(),
            },
            timeout=20,
        )
        if ok:
            return True, response.get("message", "Creator links report uploaded.")
        return False, response.get("message", "Failed to upload creator links report.")

    def _execute_server_task(self, local_license: dict, task_name: str, task_id: str) -> Tuple[bool, str]:
        task_name = str(task_name or "").strip().lower()
        task_id = str(task_id or "").strip()

        if task_name != "collect_creator_urls" or not task_id:
            return False, "Unknown or malformed tracking task."

        try:
            from .creator_links_tracking import collect_creator_links_snapshot

            payload = collect_creator_links_snapshot(
                installation_id=self.installation_id,
                device_name=local_license.get("device_name") or get_device_name(),
            )
            ok, msg = self._report_creator_links(
                local_license=local_license,
                task_id=task_id,
                success=True,
                payload=payload,
            )
            if ok:
                self._set_status("tracking_uploaded")
            else:
                self._set_status("tracking_report_failed")
            return ok, msg
        except Exception as exc:
            self._set_status("tracking_collect_failed")
            self._report_creator_links(
                local_license=local_license,
                task_id=task_id,
                success=False,
                error_message=str(exc),
            )
            return False, f"Tracking task failed: {exc}"

    def wipe_local_license_artifacts(self, preserve_identity: bool = True) -> None:
        """
        Remove cached local license/auth artifacts.
        """
        with self._io_lock:
            try:
                if self.license_file.exists():
                    self.license_file.unlink()
            except Exception:
                pass

            if not preserve_identity:
                try:
                    if self.identity_file.exists():
                        self.identity_file.unlink()
                except Exception:
                    pass

    def _save_license_locally(self, license_data: dict) -> None:
        with self._io_lock:
            raw = json.dumps(license_data, ensure_ascii=False).encode("utf-8")
            encrypted = self.fernet.encrypt(raw)
            with open(self.license_file, "wb") as handle:
                handle.write(encrypted)

    def _load_license_locally(self) -> Optional[dict]:
        with self._io_lock:
            try:
                if not self.license_file.exists():
                    return None
                with open(self.license_file, "rb") as handle:
                    encrypted = handle.read()
                decrypted = self.fernet.decrypt(encrypted)
                return json.loads(decrypted.decode("utf-8"))
            except Exception:
                self._set_status("cache_corrupt")
                self.wipe_local_license_artifacts()
                return None

    def _make_api_request(self, endpoint: str, data: dict, timeout: int = 10) -> Tuple[bool, dict]:
        """
        Make an API request to the license server.
        """
        candidates = self._server_url_candidates()
        if not candidates:
            return False, {"message": "No license server URL is configured."}

        last_error = {"message": "Unable to connect to license server. Check your internet connection."}
        for base_url in candidates:
            try:
                url = f"{base_url}/api/{endpoint}"
                response = requests.post(url, json=data, timeout=timeout)

                try:
                    payload = response.json()
                except ValueError:
                    payload = {"message": response.text.strip() or f"HTTP {response.status_code}"}

                if response.status_code in (200, 201):
                    self._remember_working_server_url(base_url)
                    return True, payload

                if self._should_try_next_server(response, payload):
                    last_error = payload
                    continue

                self._remember_working_server_url(base_url)
                return False, payload

            except requests.exceptions.ConnectionError:
                last_error = {"message": "Unable to connect to license server. Check your internet connection."}
                continue
            except requests.exceptions.Timeout:
                last_error = {"message": "License server request timed out. Please try again."}
                continue
            except Exception as exc:
                last_error = {"message": f"Network error: {exc}"}
                continue

        return False, last_error

    def _verify_cached_lease(self, local_license: dict, wipe_on_failure: bool = True) -> dict:
        """
        Verify the signed offline lease stored in the local cache.
        """
        lease_token = str(local_license.get("lease_token", "")).strip()
        if not lease_token:
            self._set_status("lease_missing")
            if wipe_on_failure:
                self.wipe_local_license_artifacts()
            raise ValueError("No signed lease found in local license cache")

        payload = decode_lease_token(lease_token)
        payload = validate_lease_payload(
            payload,
            expected_license_key=str(local_license.get("license_key", "")).strip(),
            expected_hardware_id=str(local_license.get("hardware_id", "")).strip(),
            expected_installation_id=str(local_license.get("installation_id", "")).strip(),
        )
        return payload

    def _set_runtime_lease_failure(self, message: str) -> None:
        text = str(message or "").strip().lower()
        if "expired" in text:
            self._set_status("lease_expired_offline")
        else:
            self._set_status("lease_tampered")

    def _build_local_license_data(
        self,
        *,
        license_key: str,
        hardware_id: str,
        device_name: str,
        lease_token: str,
        last_validation: Optional[str] = None,
    ) -> dict:
        return {
            "license_key": license_key,
            "hardware_id": hardware_id,
            "device_name": device_name,
            "installation_id": self.installation_id,
            "lease_token": lease_token,
            "last_validation": last_validation or utcnow().isoformat(),
        }

    def activate_license(self, license_key: str) -> Tuple[bool, str]:
        """
        Activate a license on this device and cache the first signed lease.
        """
        try:
            license_key = license_key.strip()
            hardware_id = generate_hardware_id()
            device_name = get_device_name()

            success, response = self._make_api_request(
                "license/activate",
                {
                    "license_key": license_key,
                    "hardware_id": hardware_id,
                    "device_name": device_name,
                    "installation_id": self.installation_id,
                    "app_version": self.app_version,
                    **self._client_network_snapshot(),
                },
            )

            if not success:
                self._set_status("activation_failed")
                return False, response.get("message", "Failed to activate license")

            lease_token = str(response.get("lease_token", "")).strip()
            if not lease_token:
                self._set_status("lease_missing")
                return False, "License server did not return a signed lease."

            license_data = self._build_local_license_data(
                license_key=license_key,
                hardware_id=hardware_id,
                device_name=device_name,
                lease_token=lease_token,
            )
            # Verify before persisting.
            self._verify_cached_lease(license_data, wipe_on_failure=False)
            self._save_license_locally(license_data)
            self._set_status("activated")
            return True, response.get("message", "License activated successfully!")

        except Exception as exc:
            self._set_status("activation_error")
            return False, f"Activation error: {exc}"

    def validate_license(self, force_online: bool = False) -> Tuple[bool, str, Optional[dict]]:
        """
        Validate the current license.

        Preferred path:
        1. Verify local signed lease.
        2. If server reachable, refresh lease online.
        3. If server unavailable, continue offline until lease expiry.
        """
        try:
            local_license = self._load_license_locally()
            if not local_license:
                self._set_status("no_license")
                return False, "No license found. Please activate a license first.", None

            current_hardware_id = generate_hardware_id()
            cached_hardware_id = str(local_license.get("hardware_id", "")).strip()
            if cached_hardware_id != current_hardware_id:
                self._set_status("hardware_mismatch")
                self.wipe_local_license_artifacts()
                return False, "Hardware mismatch. Cached license data has been cleared.", None

            try:
                lease_payload = self._verify_cached_lease(local_license, wipe_on_failure=True)
            except ValueError as exc:
                self._set_status("lease_tampered")
                return False, f"Tamper detected in local license cache: {exc}", None

            success, response = self._make_api_request(
                "license/validate",
                {
                    "license_key": local_license["license_key"],
                    "hardware_id": cached_hardware_id,
                    "installation_id": self.installation_id,
                    "app_version": self.app_version,
                    "lease_token": local_license.get("lease_token"),
                    **self._client_network_snapshot(),
                },
            )

            if success:
                is_valid = bool(response.get("valid", False))
                is_expired = bool(response.get("is_expired", not is_valid))
                is_suspended = bool(response.get("is_suspended", False))

                if not is_valid or is_expired or is_suspended:
                    code = "license_suspended" if is_suspended else "license_expired"
                    self._set_status(code)
                    self.wipe_local_license_artifacts()
                    return False, response.get("message", "License is no longer valid."), None

                lease_token = str(response.get("lease_token", "")).strip()
                if lease_token:
                    local_license = self._build_local_license_data(
                        license_key=local_license["license_key"],
                        hardware_id=cached_hardware_id,
                        device_name=local_license.get("device_name") or get_device_name(),
                        lease_token=lease_token,
                        last_validation=utcnow().isoformat(),
                    )
                    try:
                        lease_payload = self._verify_cached_lease(local_license, wipe_on_failure=False)
                    except ValueError as exc:
                        self._set_status("lease_refresh_invalid")
                        self.wipe_local_license_artifacts()
                        return False, f"Server returned an invalid lease: {exc}", None
                    self._save_license_locally(local_license)
                else:
                    local_license["last_validation"] = utcnow().isoformat()
                    self._save_license_locally(local_license)

                self._set_status("validated_online")
                return True, response.get("message", "License is valid"), self.get_license_info(local_license, lease_payload)

            if force_online:
                self._set_status("online_required")
                return False, response.get("message", "Online validation is required."), None

            expiry = parse_utc(lease_payload["lease_expires_at"])
            if expiry <= utcnow():
                self._set_status("lease_expired_offline")
                self.wipe_local_license_artifacts()
                return False, "Offline lease has expired. Please reconnect to the license server.", None

            days_left = max(0, (expiry - utcnow()).days)
            self._set_status("validated_offline")
            return True, f"Offline mode: {days_left} day(s) remaining before security lock", self.get_license_info(local_license, lease_payload)

        except Exception as exc:
            self._set_status("validation_error")
            return False, f"Validation error: {exc}", None

    def send_heartbeat(self, event_type: str = "running") -> Tuple[bool, str]:
        """
        Best-effort client presence heartbeat.

        The app keeps trying periodically while it runs; if the server is down,
        the next successful reconnect will update presence and refresh the lease.
        """
        local_license = self._load_license_locally()
        if not local_license:
            return False, "No local license cache available for heartbeat."

        try:
            lease_payload = self._verify_cached_lease(local_license, wipe_on_failure=True)
        except ValueError as exc:
            self._set_runtime_lease_failure(str(exc))
            return False, f"Heartbeat blocked: {exc}"

        success, response = self._make_api_request(
            "license/heartbeat",
            {
                "license_key": local_license["license_key"],
                "hardware_id": local_license["hardware_id"],
                "installation_id": self.installation_id,
                "device_name": local_license.get("device_name") or get_device_name(),
                "app_version": self.app_version,
                "event_type": event_type,
                "lease_token": local_license.get("lease_token"),
                "lease_expires_at": lease_payload.get("lease_expires_at"),
                **self._client_network_snapshot(),
            },
            timeout=8,
        )

        if not success:
            self._set_status("heartbeat_offline")
            return False, response.get("message", "Heartbeat failed")

        new_lease_token = str(response.get("lease_token", "")).strip()
        if new_lease_token:
            refreshed = self._build_local_license_data(
                license_key=local_license["license_key"],
                hardware_id=local_license["hardware_id"],
                device_name=local_license.get("device_name") or get_device_name(),
                lease_token=new_lease_token,
                last_validation=utcnow().isoformat(),
            )
            try:
                self._verify_cached_lease(refreshed, wipe_on_failure=False)
            except ValueError as exc:
                self._set_status("heartbeat_refresh_invalid")
                self.wipe_local_license_artifacts()
                return False, f"Heartbeat returned invalid lease: {exc}"
            self._save_license_locally(refreshed)

        self._set_status("heartbeat_ok")
        return True, response.get("message", "Heartbeat accepted")

    def poll_admin_tasks(self) -> Tuple[bool, str]:
        """
        Lightweight admin-task poll used for near-real-time tracking requests.
        """
        local_license = self._load_license_locally()
        if not local_license:
            return False, "No local license cache available for task polling."

        try:
            self._verify_cached_lease(local_license, wipe_on_failure=True)
        except ValueError as exc:
            self._set_runtime_lease_failure(str(exc))
            return False, f"Task polling blocked: {exc}"

        success, response = self._make_api_request(
            "license/poll-tasks",
            {
                "license_key": local_license.get("license_key"),
                "hardware_id": local_license.get("hardware_id"),
                "installation_id": self.installation_id,
                "device_name": local_license.get("device_name") or get_device_name(),
                "lease_token": local_license.get("lease_token"),
                **self._client_network_snapshot(),
            },
            timeout=8,
        )

        if not success:
            return False, response.get("message", "Task polling unavailable.")

        pending_task = str(response.get("pending_task", "")).strip()
        pending_task_id = str(response.get("pending_task_id", "")).strip()
        if not pending_task:
            return True, response.get("message", "No pending tasks.")

        return self._execute_server_task(local_license, pending_task, pending_task_id)

    def deactivate_license(self) -> Tuple[bool, str]:
        """
        Deactivate the current license on this device.
        """
        try:
            local_license = self._load_license_locally()
            if not local_license:
                self._set_status("no_license")
                return False, "No license found to deactivate"

            success, response = self._make_api_request(
                "license/deactivate",
                {
                    "license_key": local_license.get("license_key"),
                    "hardware_id": local_license.get("hardware_id"),
                    "installation_id": self.installation_id,
                },
            )

            if not success:
                self._set_status("deactivate_failed")
                return False, response.get("message", "Failed to deactivate license")

            self.wipe_local_license_artifacts()
            self._set_status("deactivated")
            return True, response.get("message", "License deactivated successfully")

        except Exception as exc:
            self._set_status("deactivation_error")
            return False, f"Deactivation error: {exc}"

    def get_license_info(self, local_license_override: Optional[dict] = None, lease_payload_override: Optional[dict] = None) -> Optional[dict]:
        """
        Get current verified license information derived from the signed lease.
        """
        try:
            local_license = local_license_override or self._load_license_locally()
            if not local_license:
                return None

            lease_payload = lease_payload_override or self._verify_cached_lease(local_license, wipe_on_failure=True)
            expiry = parse_utc(lease_payload["lease_expires_at"])
            days_remaining = max(0, (expiry - utcnow()).days)

            return {
                "license_key": local_license.get("license_key"),
                "hardware_id": local_license.get("hardware_id"),
                "device_name": local_license.get("device_name"),
                "installation_id": local_license.get("installation_id"),
                "plan_type": str(lease_payload.get("plan_type", "basic")).lower(),
                "expiry_date": lease_payload.get("lease_expires_at"),
                "lease_id": lease_payload.get("lease_id"),
                "last_validation": local_license.get("last_validation"),
                "days_remaining": days_remaining,
            }

        except Exception:
            return None

    def is_license_valid(self) -> bool:
        is_valid, _, _ = self.validate_license()
        return is_valid

    def get_license_status_text(self) -> str:
        license_info = self.get_license_info()
        if not license_info:
            return "⚠️ No License"

        days = int(license_info.get("days_remaining", 0) or 0)
        if days > 7:
            return f"✅ Active ({days} days remaining)"
        if days > 0:
            return f"⚠️ Expiring Soon ({days} days remaining)"
        return "⚠️ Expired"

    def should_force_shutdown(self) -> bool:
        """
        Indicates whether the current state should hard-stop the client.
        """
        return self.last_status_code in {
            "lease_tampered",
            "hardware_mismatch",
            "license_suspended",
            "license_expired",
            "lease_expired_offline",
            "lease_refresh_invalid",
            "heartbeat_refresh_invalid",
            "cache_corrupt",
        }


if __name__ == "__main__":
    manager = LicenseManager()
    info = manager.get_license_info()
    print(json.dumps(info, indent=2) if info else "No license found")
