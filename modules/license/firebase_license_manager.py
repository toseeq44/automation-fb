"""
Firebase-backed license manager for the MVP Firestore licensing flow.

This implementation is intentionally online-first and lightweight. It keeps the
same public interface that the UI/startup code already expects while swapping
the backing store from the local Flask server to Firebase Auth + Firestore.
"""
from __future__ import annotations

import base64
import json
import hashlib
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from cryptography.fernet import Fernet

from modules.config import get_config
from modules.config.utils import get_config_directory
from modules.logging import get_logger

from .creator_links_tracking import collect_creator_links_snapshot
from .hardware_id import generate_hardware_id, get_device_name, get_preferred_lan_ip
from .license_manager import LicenseManager as LegacyServerLicenseManager


FIREBASE_AUTH_SIGNUP_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
FIREBASE_TOKEN_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"
FIRESTORE_API_ROOT = "https://firestore.googleapis.com/v1"
AUTH_REFRESH_GRACE_SECONDS = 120
FATAL_STARTUP_STATUSES = {
    "firebase_config_missing",
    "firebase_unreachable",
    "firebase_auth_failed",
}


class FirestoreLicenseManager:
    """
    Firestore-only MVP license manager.

    The manager keeps a small encrypted local cache for the active license and
    Firebase auth tokens, but all validation is performed online.
    """

    def __init__(
        self,
        server_url: str = "",
        app_version: str = "1.0.0",
        fallback_urls: Optional[List[str]] = None,
        bootstrap_urls: Optional[List[str]] = None,
        remember_last_good_url: Optional[bool] = None,
        provider: Optional[str] = None,
    ):
        self.logger = get_logger("OneSoulFirebaseLicense")
        self.app_version = app_version
        self.provider = "firebase"
        self.server_url = ""
        self.license_dir = Path.home() / ".onesoul"
        self.config_dir = get_config_directory()
        self.license_file = self.license_dir / "license.dat"
        self.identity_file = self.license_dir / "installation.json"
        self.auth_state_file = self.license_dir / "firebase_auth.dat"
        self.license_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.installation_id = self._load_or_create_installation_id()
        self.last_status_code = "uninitialized"
        self._io_lock = threading.RLock()
        self._config = get_config()
        self._firebase_config = self._load_firebase_config()
        self.encryption_key = self._generate_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        self._startup_validation_complete = False

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
            "created_at": self._iso_now(),
        }
        self.identity_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return installation_id

    def _generate_encryption_key(self) -> bytes:
        hardware_id = generate_hardware_id()
        key_material = hashlib.sha256(hardware_id.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(key_material)

    def _load_firebase_config(self) -> Dict[str, str]:
        firebase = self._config.get("license.firebase", {}) or {}
        return {
            "api_key": str(firebase.get("api_key", "") or "").strip(),
            "auth_domain": str(firebase.get("auth_domain", "") or "").strip(),
            "project_id": str(firebase.get("project_id", "") or "").strip(),
            "app_id": str(firebase.get("app_id", "") or "").strip(),
        }

    def _config_ready(self) -> bool:
        return bool(
            self._firebase_config.get("api_key")
            and self._firebase_config.get("project_id")
            and self._firebase_config.get("app_id")
        )

    def _firebase_hint(self) -> str:
        project_id = self._firebase_config.get("project_id", "")
        if project_id:
            return f"firebase://{project_id}"
        return ""

    def get_active_server_url(self) -> str:
        return self._firebase_hint()

    def get_server_url_candidates(self) -> List[str]:
        hint = self._firebase_hint()
        return [hint] if hint else []

    def _client_network_snapshot(self) -> Dict[str, str]:
        return {
            "client_lan_ip": get_preferred_lan_ip(),
        }

    def _write_encrypted_json(self, path: Path, payload: Dict[str, Any]) -> None:
        with self._io_lock:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            encrypted = self.fernet.encrypt(raw)
            path.write_bytes(encrypted)

    def _read_encrypted_json(self, path: Path) -> Optional[Dict[str, Any]]:
        with self._io_lock:
            try:
                if not path.exists():
                    return None
                encrypted = path.read_bytes()
                raw = self.fernet.decrypt(encrypted)
                payload = json.loads(raw.decode("utf-8"))
                if isinstance(payload, dict):
                    return payload
            except Exception:
                try:
                    path.unlink()
                except Exception:
                    pass
        return None

    def _load_local_license(self) -> Optional[Dict[str, Any]]:
        return self._read_encrypted_json(self.license_file)

    def _save_local_license(self, payload: Dict[str, Any]) -> None:
        self._write_encrypted_json(self.license_file, payload)

    def _load_auth_state(self) -> Optional[Dict[str, Any]]:
        return self._read_encrypted_json(self.auth_state_file)

    def _save_auth_state(self, payload: Dict[str, Any]) -> None:
        self._write_encrypted_json(self.auth_state_file, payload)

    def wipe_local_license_artifacts(self, preserve_identity: bool = True) -> None:
        with self._io_lock:
            for path in (self.license_file, self.auth_state_file):
                try:
                    if path.exists():
                        path.unlink()
                except Exception:
                    pass

            if not preserve_identity:
                try:
                    if self.identity_file.exists():
                        self.identity_file.unlink()
                except Exception:
                    pass

    def _iso_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _parse_iso_datetime(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None

    def _is_expired(self, expiry_value: Any) -> bool:
        expiry = self._parse_iso_datetime(expiry_value)
        if expiry is None:
            return True
        return expiry <= datetime.now(timezone.utc)

    def _days_remaining(self, expiry_value: Any) -> int:
        expiry = self._parse_iso_datetime(expiry_value)
        if expiry is None:
            return 0
        delta = expiry - datetime.now(timezone.utc)
        return max(0, delta.days)

    def _firestore_value_to_python(self, value: Dict[str, Any]) -> Any:
        if "stringValue" in value:
            return value["stringValue"]
        if "booleanValue" in value:
            return bool(value["booleanValue"])
        if "integerValue" in value:
            return int(value["integerValue"])
        if "doubleValue" in value:
            return float(value["doubleValue"])
        if "timestampValue" in value:
            return value["timestampValue"]
        if "nullValue" in value:
            return None
        if "arrayValue" in value:
            values = value.get("arrayValue", {}).get("values", [])
            return [self._firestore_value_to_python(item) for item in values]
        if "mapValue" in value:
            fields = value.get("mapValue", {}).get("fields", {})
            return {key: self._firestore_value_to_python(item) for key, item in fields.items()}
        return None

    def _python_to_firestore_value(self, value: Any) -> Dict[str, Any]:
        if value is None:
            return {"nullValue": None}
        if isinstance(value, bool):
            return {"booleanValue": value}
        if isinstance(value, int) and not isinstance(value, bool):
            return {"integerValue": str(value)}
        if isinstance(value, float):
            return {"doubleValue": value}
        if isinstance(value, datetime):
            dt = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return {"timestampValue": dt.isoformat()}
        if isinstance(value, dict):
            return {
                "mapValue": {
                    "fields": {key: self._python_to_firestore_value(item) for key, item in value.items()}
                }
            }
        if isinstance(value, list):
            return {"arrayValue": {"values": [self._python_to_firestore_value(item) for item in value]}}
        return {"stringValue": str(value)}

    def _document_to_python(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        fields = payload.get("fields", {}) or {}
        data = {key: self._firestore_value_to_python(value) for key, value in fields.items()}
        if payload.get("name"):
            data["_document_name"] = payload["name"]
        return data

    def _document_path(self, collection: str, doc_id: str) -> str:
        project_id = self._firebase_config.get("project_id", "")
        encoded_collection = quote(collection, safe="")
        encoded_doc_id = quote(doc_id, safe="")
        return f"{FIRESTORE_API_ROOT}/projects/{project_id}/databases/(default)/documents/{encoded_collection}/{encoded_doc_id}"

    def _collection_path(self, collection: str) -> str:
        project_id = self._firebase_config.get("project_id", "")
        encoded_collection = quote(collection, safe="")
        return f"{FIRESTORE_API_ROOT}/projects/{project_id}/databases/(default)/documents/{encoded_collection}"

    def _ensure_config(self) -> None:
        self._firebase_config = self._load_firebase_config()
        if self._config_ready():
            return
        self._set_status("firebase_config_missing")
        raise RuntimeError(
            "Firebase license configuration is incomplete. Please fill license.firebase.api_key, "
            "license.firebase.project_id, and license.firebase.app_id in config.json."
        )

    def _sign_in_anonymously(self) -> Dict[str, Any]:
        self._ensure_config()
        url = f"{FIREBASE_AUTH_SIGNUP_URL}?key={quote(self._firebase_config['api_key'], safe='')}"
        response = requests.post(url, json={"returnSecureToken": True}, timeout=15)
        payload = response.json()
        if response.status_code != 200:
            raise RuntimeError(payload.get("error", {}).get("message", "Firebase anonymous sign-in failed"))
        return payload

    def _refresh_id_token(self, refresh_token: str) -> Dict[str, Any]:
        self._ensure_config()
        response = requests.post(
            f"{FIREBASE_TOKEN_REFRESH_URL}?key={quote(self._firebase_config['api_key'], safe='')}",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        payload = response.json()
        if response.status_code != 200:
            raise RuntimeError(payload.get("error", {}).get("message", "Firebase token refresh failed"))
        return payload

    def _normalize_auth_payload(self, payload: Dict[str, Any], refreshed: bool = False) -> Dict[str, Any]:
        expires_in_raw = payload.get("expiresIn", "3600")
        try:
            expires_in = int(float(expires_in_raw))
        except Exception:
            expires_in = 3600
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in))
        return {
            "id_token": str(payload.get("idToken") or payload.get("id_token") or "").strip(),
            "refresh_token": str(payload.get("refreshToken") or payload.get("refresh_token") or "").strip(),
            "local_id": str(payload.get("localId") or payload.get("user_id") or "").strip(),
            "expires_at": expires_at.isoformat(),
            "refreshed_at": self._iso_now() if refreshed else "",
            "project_id": self._firebase_config.get("project_id", ""),
        }

    def _ensure_authenticated(self) -> Dict[str, Any]:
        try:
            self._ensure_config()
            auth_state = self._load_auth_state()
            if auth_state:
                expiry = self._parse_iso_datetime(auth_state.get("expires_at"))
                if expiry and expiry > datetime.now(timezone.utc) + timedelta(seconds=AUTH_REFRESH_GRACE_SECONDS):
                    return auth_state

                refresh_token = str(auth_state.get("refresh_token", "")).strip()
                if refresh_token:
                    try:
                        refreshed = self._normalize_auth_payload(self._refresh_id_token(refresh_token), refreshed=True)
                        self._save_auth_state(refreshed)
                        return refreshed
                    except Exception:
                        # If the refresh endpoint is temporarily failing, fall back
                        # to a brand-new anonymous sign-in before giving up.
                        pass

            fresh = self._normalize_auth_payload(self._sign_in_anonymously())
            self._save_auth_state(fresh)
            return fresh
        except requests.exceptions.RequestException as exc:
            self._set_status("firebase_unreachable")
            raise RuntimeError(f"Could not reach Firebase: {exc}") from exc
        except Exception as exc:
            if self.last_status_code != "firebase_config_missing":
                self._set_status("firebase_auth_failed")
            raise RuntimeError(str(exc)) from exc

    def _firestore_request(
        self,
        method: str,
        url: str,
        *,
        json_payload: Optional[Dict[str, Any]] = None,
        params: Optional[List[Tuple[str, str]]] = None,
        allow_not_found: bool = False,
    ) -> Optional[Dict[str, Any]]:
        auth_state = self._ensure_authenticated()
        headers = {
            "Authorization": f"Bearer {auth_state['id_token']}",
            "Accept": "application/json",
        }
        if json_payload is not None:
            headers["Content-Type"] = "application/json"

        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=json_payload,
            params=params,
            timeout=20,
        )
        if response.status_code == 404 and allow_not_found:
            return None
        if response.status_code in (200, 201):
            if response.content:
                return response.json()
            return {}

        try:
            payload = response.json()
        except ValueError:
            payload = {"error": {"message": response.text.strip() or f"HTTP {response.status_code}"}}

        message = payload.get("error", {}).get("message", f"HTTP {response.status_code}")
        raise RuntimeError(f"Firestore request failed: {message}")

    def _get_document(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        payload = self._firestore_request(
            "GET",
            self._document_path(collection, doc_id),
            allow_not_found=True,
        )
        if not payload:
            return None
        return self._document_to_python(payload)

    def _patch_document(self, collection: str, doc_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        params = [("updateMask.fieldPaths", key) for key in data.keys()]
        payload = {
            "fields": {key: self._python_to_firestore_value(value) for key, value in data.items()},
        }
        response = self._firestore_request(
            "PATCH",
            self._document_path(collection, doc_id),
            json_payload=payload,
            params=params,
        )
        return self._document_to_python(response or {})

    def _add_document(self, collection: str, data: Dict[str, Any]) -> None:
        payload = {
            "fields": {key: self._python_to_firestore_value(value) for key, value in data.items()},
        }
        self._firestore_request(
            "POST",
            self._collection_path(collection),
            json_payload=payload,
        )

    def _upsert_installation(self, local_license: Dict[str, Any], status: str) -> None:
        payload = {
            "licenseKey": local_license.get("license_key", ""),
            "hardwareId": local_license.get("hardware_id", ""),
            "deviceName": local_license.get("device_name") or get_device_name(),
            "appVersion": self.app_version,
            "status": status,
            "lastSeenAt": self._iso_now(),
            "lastLanIp": self._client_network_snapshot().get("client_lan_ip", ""),
            "lastValidationAt": self._iso_now(),
        }
        self._patch_document("installations", self.installation_id, payload)

    def _update_license_presence(self, license_key: str) -> None:
        self._patch_document(
            "licenses",
            license_key,
            {
                "lastSeenAt": self._iso_now(),
                "lastInstallationId": self.installation_id,
            },
        )

    def _log_event(self, license_key: str, event_type: str, message: str) -> None:
        try:
            self._add_document(
                "license_events",
                {
                    "installationId": self.installation_id,
                    "licenseKey": license_key,
                    "eventType": event_type,
                    "message": message,
                    "createdAt": self._iso_now(),
                },
            )
        except Exception:
            self.logger.debug(f"Skipping license event write for {event_type}", "License")

    def _build_cached_license(self, license_key: str, document: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "license_key": license_key,
            "hardware_id": generate_hardware_id(),
            "device_name": get_device_name(),
            "installation_id": self.installation_id,
            "plan_type": str(document.get("plan", "basic") or "basic").lower(),
            "expiry_date": str(document.get("expiryAt", "") or ""),
            "last_validation": self._iso_now(),
        }

    def _creator_snapshot_doc_id(self, license_key: str, installation_id: Optional[str] = None) -> str:
        base = str(license_key or "").strip() or str(installation_id or "").strip() or self.installation_id
        return base.replace("/", "_")

    def _cached_startup_grace_hours(self) -> int:
        try:
            raw = int(self._config.get("license.startup_offline_grace_hours", 72) or 72)
        except Exception:
            raw = 72
        return max(0, raw)

    def _can_use_cached_startup_license(self, local_license: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
        if not local_license:
            return False, "No local license cache available."

        cached_hardware_id = str(local_license.get("hardware_id", "") or "").strip()
        current_hardware_id = generate_hardware_id()
        if not cached_hardware_id or cached_hardware_id != current_hardware_id:
            self.wipe_local_license_artifacts()
            return False, "Cached license does not match this hardware anymore."

        expiry_value = local_license.get("expiry_date")
        if self._is_expired(expiry_value):
            return False, "Cached license has expired."

        last_validation = self._parse_iso_datetime(local_license.get("last_validation"))
        if last_validation is None:
            return False, "Cached license has no recent validation timestamp."

        grace_hours = self._cached_startup_grace_hours()
        if grace_hours <= 0:
            return False, "Offline startup grace is disabled."

        age = datetime.now(timezone.utc) - last_validation
        if age > timedelta(hours=grace_hours):
            return False, "Cached license validation is too old for offline startup."

        return True, f"Using cached license because Firebase is temporarily unreachable. Last validation was {int(age.total_seconds() // 3600)} hour(s) ago."

    def _validate_remote_license_document(
        self,
        license_key: str,
        document: Optional[Dict[str, Any]],
        hardware_id: str,
    ) -> Tuple[bool, str]:
        if not document:
            return False, "License key was not found in Firestore."
        if not bool(document.get("active", False)):
            return False, "This license is inactive."
        if self._is_expired(document.get("expiryAt")):
            return False, "This license has expired."

        bound_hardware_id = str(document.get("boundHardwareId", "") or "").strip()
        if bound_hardware_id and bound_hardware_id != hardware_id:
            return False, "This license is already bound to another device."

        return True, ""

    def activate_license(self, license_key: str) -> Tuple[bool, str]:
        license_key = str(license_key or "").strip()
        if not license_key:
            self._set_status("activation_failed")
            return False, "Please enter a license key."

        try:
            self._ensure_authenticated()
            hardware_id = generate_hardware_id()
            device_name = get_device_name()
            document = self._get_document("licenses", license_key)
            ok, message = self._validate_remote_license_document(license_key, document, hardware_id)
            if not ok:
                self._set_status("activation_failed")
                self._log_event(license_key, "activation_failed", message)
                return False, message

            bound_hardware_id = str(document.get("boundHardwareId", "") or "").strip()
            patch = {
                "boundHardwareId": bound_hardware_id or hardware_id,
                "boundDeviceName": device_name,
                "lastSeenAt": self._iso_now(),
                "lastInstallationId": self.installation_id,
            }
            updated = self._patch_document("licenses", license_key, patch)
            local_license = self._build_cached_license(license_key, updated)
            self._save_local_license(local_license)
            self._upsert_installation(local_license, "startup")
            self._log_event(license_key, "activation", f"Activated on {device_name}")
            self._set_status("activated")
            return True, f"License activated successfully on {device_name}"
        except Exception as exc:
            message = str(exc)
            self.logger.error(message, "License")
            if self.last_status_code not in FATAL_STARTUP_STATUSES:
                self._set_status("activation_error")
            return False, message

    def validate_license(self, force_online: bool = False) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        local_license = self._load_local_license()
        try:
            self._ensure_authenticated()
        except Exception as exc:
            if not force_online and self.last_status_code in {"firebase_unreachable", "firebase_auth_failed"}:
                can_use_cached, cached_message = self._can_use_cached_startup_license(local_license)
                if can_use_cached:
                    self._startup_validation_complete = True
                    self._set_status("validated_cached_startup")
                    return True, cached_message, self.get_license_info(local_license)
            return False, str(exc), None

        if not local_license:
            self._set_status("no_license")
            return False, "No license found. Please activate a license first.", None

        current_hardware_id = generate_hardware_id()
        cached_hardware_id = str(local_license.get("hardware_id", "")).strip()
        if current_hardware_id != cached_hardware_id:
            self._set_status("hardware_mismatch")
            self.wipe_local_license_artifacts()
            return False, "Hardware mismatch. Local license cache has been cleared.", None

        try:
            document = self._get_document("licenses", str(local_license.get("license_key", "")))
            ok, message = self._validate_remote_license_document(
                str(local_license.get("license_key", "")),
                document,
                current_hardware_id,
            )
            if not ok:
                self._set_status("license_invalid")
                self._log_event(str(local_license.get("license_key", "")), "validation_failed", message)
                self.wipe_local_license_artifacts()
                return False, message, None

            refreshed = self._build_cached_license(str(local_license.get("license_key", "")), document or {})
            self._save_local_license(refreshed)
            self._upsert_installation(refreshed, "running")
            self._update_license_presence(refreshed["license_key"])
            self._startup_validation_complete = True
            self._set_status("validated_online")
            return True, "License is valid", self.get_license_info(refreshed)
        except Exception as exc:
            message = str(exc)
            self.logger.error(message, "License")
            if self.last_status_code not in FATAL_STARTUP_STATUSES:
                self._set_status("validation_error")
            return False, message, None

    def _load_valid_local_license(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        local_license = self._load_local_license()
        if not local_license:
            return None, "No local license cache available."
        if str(local_license.get("hardware_id", "")).strip() != generate_hardware_id():
            self.wipe_local_license_artifacts()
            return None, "Cached license does not match this hardware anymore."
        return local_license, None

    def send_heartbeat(self, event_type: str = "running") -> Tuple[bool, str]:
        local_license, error = self._load_valid_local_license()
        if not local_license:
            return False, error or "No local license cache available."

        try:
            document = self._get_document("licenses", str(local_license.get("license_key", "")))
            ok, message = self._validate_remote_license_document(
                str(local_license.get("license_key", "")),
                document,
                str(local_license.get("hardware_id", "")),
            )
            if not ok:
                self._set_status("heartbeat_denied")
                return False, message

            self._upsert_installation(local_license, event_type or "running")
            self._update_license_presence(str(local_license.get("license_key", "")))
            self._set_status("heartbeat_ok")
            return True, f"Heartbeat accepted ({event_type})"
        except Exception as exc:
            self._set_status("heartbeat_offline")
            return False, str(exc)

    def _execute_server_task(self, local_license: Dict[str, Any], task_name: str) -> Tuple[bool, str]:
        if str(task_name or "").strip().lower() != "collect_creator_urls":
            return False, "Unknown or malformed tracking task."

        try:
            license_key = str(local_license.get("license_key", "") or "").strip()
            snapshot_doc_id = self._creator_snapshot_doc_id(license_key, self.installation_id)
            snapshot = collect_creator_links_snapshot(
                installation_id=self.installation_id,
                device_name=local_license.get("device_name") or get_device_name(),
            )
            self._patch_document(
                "creator_snapshots",
                snapshot_doc_id,
                {
                    "snapshotId": snapshot_doc_id,
                    "installationId": self.installation_id,
                    "licenseKey": license_key,
                    "deviceName": local_license.get("device_name") or get_device_name(),
                    "generatedAt": self._iso_now(),
                    "creatorCount": int(snapshot.get("creator_count", 0) or 0),
                    "payload": snapshot,
                },
            )
            self._patch_document(
                "installations",
                self.installation_id,
                {
                    "pendingTask": "",
                    "lastTrackingStatus": "completed",
                    "lastTrackingError": "",
                    "creatorSnapshotId": snapshot_doc_id,
                    "creatorSnapshotAt": self._iso_now(),
                    "lastSeenAt": self._iso_now(),
                    "status": "running",
                },
            )
            self._set_status("tracking_uploaded")
            return True, "Creator links snapshot uploaded."
        except Exception as exc:
            self._patch_document(
                "installations",
                self.installation_id,
                {
                    "pendingTask": "",
                    "lastTrackingStatus": "failed",
                    "lastTrackingError": str(exc),
                    "lastSeenAt": self._iso_now(),
                    "status": "running",
                },
            )
            self._set_status("tracking_collect_failed")
            return False, f"Tracking task failed: {exc}"

    def poll_admin_tasks(self) -> Tuple[bool, str]:
        local_license, error = self._load_valid_local_license()
        if not local_license:
            return False, error or "No local license cache available."

        try:
            installation = self._get_document("installations", self.installation_id) or {}
            pending_task = str(installation.get("pendingTask", "") or "").strip()
            if not pending_task:
                return True, "No pending tasks."
            return self._execute_server_task(local_license, pending_task)
        except Exception as exc:
            return False, str(exc)

    def deactivate_license(self) -> Tuple[bool, str]:
        local_license, error = self._load_valid_local_license()
        if not local_license:
            self._set_status("no_license")
            return False, error or "No license found to deactivate."

        try:
            document = self._get_document("licenses", str(local_license.get("license_key", "")))
            if not document:
                self.wipe_local_license_artifacts()
                self._set_status("deactivated")
                return True, "Local license cache cleared."

            bound_hardware_id = str(document.get("boundHardwareId", "") or "").strip()
            if bound_hardware_id and bound_hardware_id != str(local_license.get("hardware_id", "")):
                self._set_status("deactivate_failed")
                return False, "Cannot deactivate because the license is bound to another device."

            self._patch_document(
                "licenses",
                str(local_license.get("license_key", "")),
                {
                    "boundHardwareId": "",
                    "boundDeviceName": "",
                    "lastInstallationId": "",
                    "lastSeenAt": self._iso_now(),
                },
            )
            self._patch_document(
                "installations",
                self.installation_id,
                {
                    "status": "offline",
                    "pendingTask": "",
                    "lastSeenAt": self._iso_now(),
                },
            )
            self._log_event(str(local_license.get("license_key", "")), "deactivation", "License deactivated")
            self.wipe_local_license_artifacts()
            self._set_status("deactivated")
            return True, "License deactivated successfully. You can now activate it on another device."
        except Exception as exc:
            self._set_status("deactivation_error")
            return False, str(exc)

    def get_license_info(
        self,
        local_license_override: Optional[Dict[str, Any]] = None,
        lease_payload_override: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        local_license = local_license_override or self._load_local_license()
        if not local_license:
            return None

        expiry_value = local_license.get("expiry_date")
        return {
            "license_key": local_license.get("license_key"),
            "hardware_id": local_license.get("hardware_id"),
            "device_name": local_license.get("device_name"),
            "installation_id": local_license.get("installation_id"),
            "plan_type": str(local_license.get("plan_type", "basic") or "basic").lower(),
            "expiry_date": expiry_value,
            "last_validation": local_license.get("last_validation"),
            "days_remaining": self._days_remaining(expiry_value),
        }

    def is_license_valid(self) -> bool:
        is_valid, _, _ = self.validate_license()
        return is_valid

    def get_license_status_text(self) -> str:
        info = self.get_license_info()
        if not info:
            return "âš ï¸ No License"

        days = int(info.get("days_remaining", 0) or 0)
        if days > 7:
            return f"âœ… Active ({days} days remaining)"
        if days > 0:
            return f"âš ï¸ Expiring Soon ({days} days remaining)"
        return "âš ï¸ Expired"

    def should_force_shutdown(self) -> bool:
        return (not self._startup_validation_complete) and self.last_status_code in FATAL_STARTUP_STATUSES


class LicenseManager:
    """
    Provider-switching facade.

    Firebase is the default active provider for this MVP, while the old local
    Flask-backed manager is still available for future reuse.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:5000",
        app_version: str = "1.0.0",
        fallback_urls: Optional[List[str]] = None,
        bootstrap_urls: Optional[List[str]] = None,
        remember_last_good_url: Optional[bool] = None,
        provider: Optional[str] = None,
    ):
        config = get_config()
        chosen_provider = str(provider or config.get("license.provider", "firebase") or "firebase").strip().lower()
        if chosen_provider == "firebase":
            self._delegate = FirestoreLicenseManager(
                server_url=server_url,
                app_version=app_version,
                fallback_urls=fallback_urls,
                bootstrap_urls=bootstrap_urls,
                remember_last_good_url=remember_last_good_url,
                provider=chosen_provider,
            )
        else:
            self._delegate = LegacyServerLicenseManager(
                server_url=server_url,
                app_version=app_version,
                fallback_urls=fallback_urls,
                bootstrap_urls=bootstrap_urls,
                remember_last_good_url=remember_last_good_url,
            )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._delegate, item)


__all__ = [
    "LicenseManager",
    "FirestoreLicenseManager",
    "LegacyServerLicenseManager",
]
