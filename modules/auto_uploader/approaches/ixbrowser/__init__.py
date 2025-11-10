"""
ixBrowser automation approach package.
Uses official ixbrowser-local-api library for programmatic browser control.
"""

from .workflow import IXBrowserApproach, IXAutomationContext
from .config_handler import IXBrowserConfig
from .connection_manager import ConnectionManager
from .browser_launcher import BrowserLauncher
from .login_manager import LoginManager

__all__ = [
    "IXBrowserApproach",
    "IXAutomationContext",
    "IXBrowserConfig",
    "ConnectionManager",
    "BrowserLauncher",
    "LoginManager",
]
