"""
Facebook Auto Uploader Module
Automates video uploads to Facebook pages using anti-detect browsers
"""

from .auth_handler import AuthHandler
from .browser_launcher import BrowserLauncher
from .configuration import AutomationMode, SettingsManager
from .core import FacebookAutoUploader
from .gui import AutoUploaderPage
from .history_manager import HistoryManager

__all__ = [
    'AuthHandler',
    'AutomationMode',
    'BrowserLauncher',
    'FacebookAutoUploader',
    'HistoryManager',
    'AutoUploaderPage',
    'SettingsManager',
]
__version__ = '1.0.0'
