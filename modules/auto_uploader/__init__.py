"""
Facebook Auto Uploader Module
Automates video uploads to Facebook pages using anti-detect browsers

New modular architecture with backward compatibility for legacy code.
"""

# Backward compatibility: Import from legacy folder for old GUI
try:
    from ._legacy.auth_handler import AuthHandler
    from ._legacy.browser_launcher import BrowserLauncher
    from ._legacy.configuration import AutomationMode, SettingsManager
    from ._legacy.core import FacebookAutoUploader
    from ._legacy.gui import AutoUploaderPage
    from ._legacy.history_manager import HistoryManager
    LEGACY_MODE = True
except ImportError:
    # New modular imports (for future use)
    from .auth.credential_manager import CredentialManager as AuthHandler
    from .browser.launcher import BrowserLauncher
    from .config.settings_manager import SettingsManager
    from .core.orchestrator import UploadOrchestrator as FacebookAutoUploader
    from .ui.setup_wizard import SetupWizard as AutoUploaderPage
    from .tracking.upload_tracker import UploadTracker as HistoryManager
    AutomationMode = None  # Will be defined in new structure
    LEGACY_MODE = False

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
