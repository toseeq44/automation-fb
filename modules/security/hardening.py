from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import psutil


def _security_config(config) -> Dict:
    return config.get("security", {}) or {}


def _env_bypass_allowed(config) -> bool:
    return bool(_security_config(config).get("allow_dev_bypass_env", True))


def _is_bypass_enabled(config) -> bool:
    if not _env_bypass_allowed(config):
        return False
    return str(os.getenv("ONESOUL_DISABLE_SECURITY_CHECKS", "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_debugger_present() -> bool:
    try:
        if sys.gettrace():
            return True
    except Exception:
        pass

    if os.name == "nt":
        try:
            return bool(ctypes.windll.kernel32.IsDebuggerPresent())
        except Exception:
            pass
    return False


def _suspicious_process_hits(config) -> List[str]:
    keywords = [str(item or "").strip().lower() for item in _security_config(config).get("suspicious_process_keywords", [])]
    if not keywords:
        return []

    hits: List[str] = []
    for proc in psutil.process_iter(["name", "exe", "cmdline"]):
        try:
            parts = [
                str(proc.info.get("name") or "").lower(),
                str(proc.info.get("exe") or "").lower(),
                " ".join([str(x or "").lower() for x in (proc.info.get("cmdline") or [])]),
            ]
            haystack = " | ".join(parts)
            for keyword in keywords:
                if keyword and keyword in haystack:
                    hits.append(str(proc.info.get("name") or keyword))
                    break
        except Exception:
            continue
    return sorted(set(hits))


def build_user_safe_license_message(status_code: str, fallback: str) -> str:
    code = str(status_code or "").strip().lower()
    if code == "firebase_config_missing":
        return "Application license configuration is incomplete. Please contact support."
    if code in {"firebase_unreachable", "firebase_auth_failed"}:
        return "Could not verify the license service right now. Please check internet/DNS/firewall and try again."
    if code in {"license_invalid", "activation_failed", "deactivate_failed"}:
        return fallback
    return fallback if not getattr(sys, "frozen", False) else "A protected operation failed. Please try again or contact support."


def run_security_preflight(config) -> Tuple[bool, str, str]:
    if _is_bypass_enabled(config):
        return True, "Security checks bypassed by environment override.", "security_bypass_env"

    if not bool(_security_config(config).get("enabled", True)):
        return True, "Security checks disabled by config.", "security_disabled"

    if getattr(sys, "frozen", False):
        if bool(_security_config(config).get("block_on_debugger", True)) and _is_debugger_present():
            return False, "Security check failed. Please close debugging tools and try again.", "debugger_detected"

        if bool(_security_config(config).get("block_on_suspicious_processes", True)):
            hits = _suspicious_process_hits(config)
            if hits:
                return False, "Security check failed. Please close analysis tools and try again.", f"suspicious_processes:{', '.join(hits)}"

    return True, "Security checks passed.", "ok"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_runtime_integrity(config) -> Tuple[bool, str, str]:
    if _is_bypass_enabled(config):
        return True, "Integrity checks bypassed by environment override.", "integrity_bypass_env"

    if not getattr(sys, "frozen", False):
        return True, "Integrity checks skipped in source mode.", "source_mode"

    security = _security_config(config)
    if not bool(security.get("enabled", True)):
        return True, "Integrity checks disabled by config.", "security_disabled"

    exe_dir = Path(sys.executable).resolve().parent
    manifest_path = exe_dir / "onesoul_runtime_manifest.json"
    require_manifest = bool(security.get("require_runtime_manifest_in_frozen", True))

    if not manifest_path.exists():
        if require_manifest:
            return False, "Application integrity data is missing. Please reinstall OneSoul.", "manifest_missing"
        return True, "Integrity manifest not found, continuing.", "manifest_missing_allowed"

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = payload.get("files", {}) or {}
        if not files:
            return False, "Application integrity data is invalid. Please reinstall OneSoul.", "manifest_invalid"

        for rel_path, expected_hash in files.items():
            target = exe_dir / rel_path
            if not target.exists():
                return False, "A required application file is missing. Please reinstall OneSoul.", f"missing:{rel_path}"
            actual_hash = _sha256_file(target)
            if str(actual_hash).strip().lower() != str(expected_hash).strip().lower():
                return False, "Application files were modified or corrupted. Please reinstall OneSoul.", f"hash_mismatch:{rel_path}"
        return True, "Runtime integrity verified.", "ok"
    except Exception as exc:
        return False, "Application integrity check failed. Please reinstall OneSoul.", f"manifest_error:{exc}"
