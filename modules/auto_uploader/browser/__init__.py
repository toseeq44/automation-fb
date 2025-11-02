"""
Browser Module
===============
Handles all browser-related operations for automation.

This module is HIGHLY REUSABLE and can be imported by other modules
like video_downloader, link_grabber, etc.

Submodules:
-----------
- launcher: Browser launching operations
- connector: Selenium connection management
- profile_manager: Profile opening and switching
- status_checker: Browser status monitoring
- window_manager: Window operations (cross-platform)
- session_manager: Session persistence and restoration

Example Usage:
--------------
from modules.auto_uploader.browser.launcher import BrowserLauncher
from modules.auto_uploader.browser.connector import SeleniumConnector

launcher = BrowserLauncher()
launcher.launch_gologin()

connector = SeleniumConnector()
driver = connector.connect_to_port(9222)
"""

__version__ = "2.0.0"
__all__ = [
    "BrowserLauncher",
    "SeleniumConnector",
    "ProfileManager",
    "StatusChecker",
    "WindowManager",
    "SessionManager",
]
