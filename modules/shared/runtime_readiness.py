"""
Runtime readiness checks for link grabbing and downloading.

This module centralizes dependency/version checks so creator profile flows
can degrade explicitly instead of silently attempting unsupported strategies.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import re
import shutil
from pathlib import Path
from typing import Dict, Optional


_MIN_VERSIONS = {
    "yt_dlp": "2026.3.17",
}


def _version_tuple(value: str) -> tuple:
    parts = [int(p) for p in re.findall(r"\d+", str(value or ""))]
    return tuple(parts)


def _version_ok(current: Optional[str], minimum: Optional[str]) -> bool:
    if not minimum:
        return True
    if not current:
        return False
    return _version_tuple(current) >= _version_tuple(minimum)


def _module_version(module_name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(module_name)
    except Exception:
        pass
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", None)
        if version:
            return str(version)
        version_obj = getattr(module, "version", None)
        version = getattr(version_obj, "__version__", None)
        if version:
            return str(version)
    except Exception:
        pass
    return None


def _module_status(module_name: str, min_version: Optional[str] = None) -> Dict:
    version = _module_version(module_name)
    installed = version is not None
    return {
        "installed": installed,
        "version": version,
        "min_version": min_version,
        "ok": installed and _version_ok(version, min_version),
    }


def _playwright_browser_runtime_status() -> Dict:
    """Best-effort check for local Playwright browser binaries."""
    status = {
        "installed": False,
        "version": None,
        "min_version": None,
        "ok": False,
        "path": "",
    }
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        status["error"] = str(exc)
        return status

    try:
        with sync_playwright() as playwright:
            for browser_type in (
                getattr(playwright, "chromium", None),
                getattr(playwright, "firefox", None),
                getattr(playwright, "webkit", None),
            ):
                if browser_type is None:
                    continue
                try:
                    candidate = str(browser_type.executable_path or "").strip()
                except Exception:
                    candidate = ""
                if not candidate:
                    continue
                status["path"] = candidate
                status["installed"] = Path(candidate).exists()
                status["ok"] = status["installed"]
                return status
    except Exception as exc:
        status["error"] = str(exc)
        return status

    return status


def get_runtime_readiness(platform: str = "") -> Dict:
    """Return runtime readiness and degradations for creator-profile flows."""
    platform = (platform or "").strip().lower()
    components = {
        "yt_dlp": _module_status("yt_dlp", _MIN_VERSIONS["yt_dlp"]),
        "playwright": _module_status("playwright"),
        "selenium": _module_status("selenium"),
        "instaloader": _module_status("instaloader"),
        "curl_cffi": _module_status("curl_cffi"),
        "pytest": _module_status("pytest"),
    }
    components["playwright_browser_runtime"] = _playwright_browser_runtime_status()
    components["playwright_cli"] = {
        "installed": bool(shutil.which("playwright")),
        "version": None,
        "min_version": None,
        "ok": bool(shutil.which("playwright")),
    }

    issues = []
    warnings = []

    if not components["yt_dlp"]["ok"]:
        issues.append(
            "yt-dlp is missing or older than the branch minimum required version"
        )
    if not components["playwright"]["installed"]:
        warnings.append("Playwright Python package is missing; browser-based link grabbing is unavailable")
    elif not components["playwright_browser_runtime"]["ok"]:
        pw_err = components["playwright_browser_runtime"].get("error", "")
        if pw_err:
            warnings.append(f"Playwright browser runtime check failed ({pw_err}); continuing in degraded mode")
        else:
            warnings.append("Playwright browser binaries are missing; run 'playwright install chromium'")
    if not components["playwright_cli"]["installed"]:
        warnings.append("Playwright CLI is not on PATH")
    if not components["selenium"]["installed"]:
        warnings.append("Selenium is missing; IXBrowser and Selenium fallbacks will be degraded")
    if not components["instaloader"]["installed"]:
        warnings.append("Instaloader is missing; Instagram fallback depth is reduced")
    if not components["pytest"]["installed"]:
        warnings.append("pytest is missing; automated regression verification is unavailable")

    platform_mode = "normal"
    if platform == "tiktok" and not components["curl_cffi"]["installed"]:
        platform_mode = "browser_first"
        warnings.append(
            "curl_cffi is missing; TikTok downloader should use browser/IX-first mode"
        )
    elif platform and platform in {"instagram", "facebook", "youtube"} and not components["playwright"]["installed"]:
        platform_mode = "degraded"

    ready = not issues
    return {
        "ready": ready,
        "platform": platform,
        "platform_mode": platform_mode,
        "components": components,
        "issues": issues,
        "warnings": warnings,
    }
