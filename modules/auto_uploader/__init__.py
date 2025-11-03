"""
Facebook Auto Uploader Module
Automates video uploads to Facebook pages using anti-detect browsers.

This package now relies on the modular architecture. The legacy implementation
has been retired, but public imports remain backwards compatible via lazy
loading to avoid pulling heavy optional dependencies (such as ``psutil``)
until they are actually needed.
"""

from __future__ import annotations

from enum import Enum
from importlib import import_module
from typing import Any, Dict


class AutomationMode(str, Enum):
    """Lightweight placeholder until the full enum lands."""

    FREE = "free_automation"
    GOLOGIN = "gologin"
    IX = "ix"
    VPN = "vpn"


_EXPORT_MAP: Dict[str, str] = {
    "AuthHandler": ".auth.credential_manager:CredentialManager",
    "BrowserLauncher": ".browser.launcher:BrowserLauncher",
    "SettingsManager": ".config.settings_manager:SettingsManager",
    "FacebookAutoUploader": ".core.orchestrator:UploadOrchestrator",
    "HistoryManager": ".tracking.upload_tracker:UploadTracker",
    "AutoUploaderPage": ".ui.main_window:AutoUploaderPage",
}

__all__ = [
    "AuthHandler",
    "AutomationMode",
    "BrowserLauncher",
    "FacebookAutoUploader",
    "HistoryManager",
    "AutoUploaderPage",
    "SettingsManager",
]
__version__ = "2.0.0"
__legacy_mode__ = False


def __getattr__(name: str) -> Any:
    """Lazily import public objects so optional dependencies load on demand."""
    target = _EXPORT_MAP.get(name)
    if not target:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

    module_path, attr_name = target.split(":", 1)
    module = import_module(module_path, package=__name__)
    value = getattr(module, attr_name)
    globals()[name] = value  # Cache for future lookups
    return value
