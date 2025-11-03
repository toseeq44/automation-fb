"""
Facebook Auto Uploader Module
Automates video uploads to Facebook pages using anti-detect browsers

New modular architecture with backward compatibility for legacy code.
"""

# Prefer the modular implementation; fall back to legacy for compatibility.
from enum import Enum

try:
    from .auth.credential_manager import CredentialManager as AuthHandler
    from .browser.launcher import BrowserLauncher
    from .config.settings_manager import SettingsManager
    from .core.orchestrator import UploadOrchestrator as FacebookAutoUploader
    from .tracking.upload_tracker import UploadTracker as HistoryManager
    from .ui.main_window import AutoUploaderPage

    class AutomationMode(str, Enum):
        """Lightweight placeholder until the new enum is defined."""

        FREE = "free_automation"
        GOLOGIN = "gologin"
        IX = "ix"
        VPN = "vpn"

    LEGACY_MODE = False
except ImportError:  # pragma: no cover - compatibility path
    from ._legacy.auth_handler import AuthHandler
    from ._legacy.browser_launcher import BrowserLauncher
    from ._legacy.configuration import AutomationMode, SettingsManager
    from ._legacy.core import FacebookAutoUploader
    from ._legacy.gui import AutoUploaderPage
    from ._legacy.history_manager import HistoryManager
    LEGACY_MODE = True

__all__ = [
    'AuthHandler',
    'AutomationMode',
    'BrowserLauncher',
    'FacebookAutoUploader',
    'HistoryManager',
    'AutoUploaderPage',
    'SettingsManager',
]
__version__ = '2.0.0'  # New modular version
__legacy_mode__ = LEGACY_MODE
