"""
ixBrowser Browser Launcher
Launches browser programmatically using ixBrowser API
Attaches Selenium WebDriver to opened profile
"""

from __future__ import annotations

import logging
import time
import platform
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Windows-specific imports for window management
if platform.system() == "Windows":
    try:
        import win32gui
        import win32con
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False
        logger.debug("[IXLauncher] pywin32 not available - parent window hiding disabled")
else:
    HAS_WIN32 = False

# Try to import Selenium
try:
    from selenium.webdriver import Chrome
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False
    Chrome = None
    Options = None
    Service = None
    logger.warning("[IXLauncher] Selenium not installed!")
    logger.warning("[IXLauncher] Install with: pip install selenium")


class BrowserLauncher:
    """Launches and manages ixBrowser profiles with Selenium."""

    def __init__(self, client: Any):
        """
        Initialize browser launcher.

        Args:
            client: IXBrowserClient instance from connection_manager
        """
        self.client = client
        self.current_profile_id: Optional[int] = None
        self.driver: Optional[Any] = None
        self.session_info: Optional[Dict[str, Any]] = None

        logger.info("[IXLauncher] Browser launcher initialized")

    def _hide_ixbrowser_parent_window(self) -> bool:
        """
        Hide ixBrowser parent window to make it look like manual opening.

        Returns:
            True if parent window was found and hidden
        """
        if not HAS_WIN32:
            logger.debug("[IXLauncher] Win32 API not available, cannot hide parent window")
            return False

        try:
            # Find ixBrowser main window
            def find_ixbrowser_window(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    # Look for ixBrowser main application window
                    if "ixBrowser" in title and "facebook.com" not in title.lower():
                        windows.append(hwnd)
                return True

            windows = []
            win32gui.EnumWindows(find_ixbrowser_window, windows)

            if windows:
                for hwnd in windows:
                    # Minimize the window instead of hiding (less disruptive)
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                    logger.info("[IXLauncher] ✓ ixBrowser parent window minimized")
                return True
            else:
                logger.debug("[IXLauncher] ixBrowser parent window not found")
                return False

        except Exception as e:
            logger.debug("[IXLauncher] Error hiding parent window: %s", str(e))
            return False

    def _normalize_browser_window_title(self) -> bool:
        """
        Normalize browser window title to remove proxy information.
        Changes title from "[US.Proxy]65.195.110.75|ergergd facebook.com"
        to "ergergd facebook.com"

        Returns:
            True if title was normalized
        """
        if not HAS_WIN32:
            logger.debug("[IXLauncher] Win32 API not available, cannot normalize title")
            return False

        try:
            # Find browser window with proxy information in title
            def find_browser_window_with_proxy(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    # Look for proxy pattern in title: [Location.Proxy]IP|ProfileName
                    if "].Proxy]" in title or "[" in title and "|" in title:
                        windows.append((hwnd, title))
                return True

            windows = []
            win32gui.EnumWindows(find_browser_window_with_proxy, windows)

            if windows:
                for hwnd, old_title in windows:
                    # Extract clean title: remove "[Location.Proxy]IP|" prefix
                    # Pattern: [US.Proxy]65.195.110.75|ergergd facebook.com -> ergergd facebook.com
                    if "|" in old_title:
                        clean_title = old_title.split("|", 1)[1].strip()
                        win32gui.SetWindowText(hwnd, clean_title)
                        logger.info("[IXLauncher] ✓ Browser window title normalized")
                        logger.info("[IXLauncher]   From: %s", old_title)
                        logger.info("[IXLauncher]   To: %s", clean_title)
                return True
            else:
                logger.debug("[IXLauncher] No browser window with proxy info found")
                return False

        except Exception as e:
            logger.debug("[IXLauncher] Error normalizing title: %s", str(e))
            return False

    def launch_profile(
        self,
        profile_id: int,
        load_extensions: bool = True,
        cookies_backup: bool = False,
        startup_args: Optional[list] = None
    ) -> bool:
        """
        Launch ixBrowser profile.

        Args:
            profile_id: Profile ID to launch
            load_extensions: Whether to load extensions
            cookies_backup: Whether to backup cookies
            startup_args: Additional Chrome startup arguments

        Returns:
            True if launched successfully
        """
        if not self.client:
            logger.error("[IXLauncher] No client provided!")
            return False

        logger.info("[IXLauncher] Launching profile ID: %s", profile_id)

        # Default startup args
        if startup_args is None:
            startup_args = []

        # Log startup args (if any)
        if startup_args:
            logger.info("[IXLauncher] Startup args: %s", startup_args)
        else:
            logger.info("[IXLauncher] Launching with default browser settings (no custom args)")

        try:
            # Open profile using official API
            open_result = self.client.open_profile(
                profile_id=profile_id,
                load_extensions=load_extensions,
                load_profile_info_page=False,
                cookies_backup=cookies_backup,
                startup_args=startup_args
            )

            if open_result is None:
                logger.error("[IXLauncher] Failed to open profile!")
                logger.error("[IXLauncher]   Error code: %s", self.client.code)
                logger.error("[IXLauncher]   Error message: %s", self.client.message)
                return False

            # Store session info
            self.session_info = open_result
            self.current_profile_id = profile_id

            webdriver_path = open_result.get('webdriver')
            debugging_address = open_result.get('debugging_address')

            logger.info("[IXLauncher] ✓ Profile opened successfully!")
            logger.info("[IXLauncher]   WebDriver: %s", webdriver_path)
            logger.info("[IXLauncher]   Debug Address: %s", debugging_address)

            # Wait for browser to fully start
            logger.info("[IXLauncher] Waiting for browser to start...")
            time.sleep(2)

            # Normalize browser experience to mimic manual opening
            logger.info("[IXLauncher] Normalizing browser window appearance...")

            # 1. Minimize ixBrowser parent window
            self._hide_ixbrowser_parent_window()

            # 2. Clean up browser window title (remove proxy info)
            time.sleep(0.5)  # Small delay to ensure window is ready
            self._normalize_browser_window_title()

            return True

        except Exception as e:
            logger.error("[IXLauncher] Error launching profile: %s", str(e))
            return False

    def attach_selenium(self) -> bool:
        """
        Attach Selenium WebDriver to launched profile.

        Returns:
            True if Selenium attached successfully
        """
        if not HAS_SELENIUM:
            logger.error("[IXLauncher] Selenium not installed!")
            logger.error("[IXLauncher] Install with: pip install selenium")
            return False

        if not self.session_info:
            logger.error("[IXLauncher] No active session! Launch profile first.")
            return False

        webdriver_path = self.session_info.get('webdriver')
        debugging_address = self.session_info.get('debugging_address')

        if not webdriver_path or not debugging_address:
            logger.error("[IXLauncher] Invalid session info!")
            return False

        logger.info("[IXLauncher] Attaching Selenium WebDriver...")
        logger.info("[IXLauncher]   WebDriver: %s", webdriver_path)
        logger.info("[IXLauncher]   Debug Address: %s", debugging_address)

        try:
            # Configure Chrome options
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", debugging_address)

            # Create Selenium driver (Selenium 4+ syntax)
            self.driver = Chrome(
                service=Service(webdriver_path),
                options=chrome_options
            )

            logger.info("[IXLauncher] ✓ Selenium attached successfully!")

            # Maximize browser window
            try:
                self.driver.maximize_window()
                logger.info("[IXLauncher] ✓ Browser window maximized")
            except Exception as e:
                logger.debug("[IXLauncher] Could not maximize window: %s", str(e))

            # Get current URL to verify
            try:
                current_url = self.driver.current_url
                logger.info("[IXLauncher]   Current URL: %s", current_url)
            except Exception:
                logger.debug("[IXLauncher]   Could not get current URL")

            return True

        except Exception as e:
            logger.error("[IXLauncher] Failed to attach Selenium: %s", str(e))
            self.driver = None
            return False

    def get_driver(self) -> Optional[Any]:
        """
        Get Selenium WebDriver instance.

        Returns:
            WebDriver instance or None
        """
        if not self.driver:
            logger.warning("[IXLauncher] No driver available! Attach Selenium first.")
        return self.driver

    def navigate_to(self, url: str) -> bool:
        """
        Navigate to URL using Selenium.

        Args:
            url: URL to navigate to

        Returns:
            True if navigation successful
        """
        if not self.driver:
            logger.error("[IXLauncher] No driver available!")
            return False

        logger.info("[IXLauncher] Navigating to: %s", url)

        try:
            self.driver.get(url)
            logger.info("[IXLauncher] ✓ Navigation successful!")
            return True
        except Exception as e:
            logger.error("[IXLauncher] Navigation failed: %s", str(e))
            return False

    def close_profile(self) -> bool:
        """
        Close current profile.

        Returns:
            True if closed successfully
        """
        if not self.current_profile_id:
            logger.warning("[IXLauncher] No profile to close!")
            return True

        logger.info("[IXLauncher] Closing profile ID: %s", self.current_profile_id)

        try:
            # Close Selenium driver first (if exists)
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("[IXLauncher] ✓ Selenium driver closed")
                except Exception as e:
                    logger.debug("[IXLauncher] Error closing driver: %s", str(e))
                finally:
                    self.driver = None

            # Close profile via API
            close_result = self.client.close_profile(self.current_profile_id)

            if close_result is None:
                logger.error("[IXLauncher] Failed to close profile!")
                logger.error("[IXLauncher]   Error: %s", self.client.message)
                return False

            logger.info("[IXLauncher] ✓ Profile closed successfully!")

            # Clear state
            self.current_profile_id = None
            self.session_info = None

            return True

        except Exception as e:
            logger.error("[IXLauncher] Error closing profile: %s", str(e))
            return False

    def is_profile_open(self) -> bool:
        """
        Check if profile is currently open.

        Returns:
            True if profile is open
        """
        return self.current_profile_id is not None

    def get_current_profile_id(self) -> Optional[int]:
        """
        Get current profile ID.

        Returns:
            Profile ID or None
        """
        return self.current_profile_id

    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current session information.

        Returns:
            Session info dictionary or None
        """
        return self.session_info


if __name__ == "__main__":
    # Test mode
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    from connection_manager import ConnectionManager

    print("\n" + "="*60)
    print("Testing ixBrowser Browser Launcher")
    print("="*60 + "\n")

    # Connect to API
    manager = ConnectionManager()
    if not manager.connect():
        print("✗ Connection failed!")
        exit(1)

    client = manager.get_client()

    # Get first profile
    profiles = manager.get_profile_list(limit=1)
    if not profiles:
        print("✗ No profiles found!")
        exit(1)

    profile_id = profiles[0]['profile_id']
    print(f"Using profile: {profiles[0]['name']} (ID: {profile_id})\n")

    # Launch profile
    launcher = BrowserLauncher(client)

    if launcher.launch_profile(profile_id):
        print("\n✓ Profile launched!")

        # Attach Selenium
        if launcher.attach_selenium():
            print("✓ Selenium attached!")

            # Navigate to test page
            if launcher.navigate_to("https://www.ixbrowser.com"):
                print("✓ Navigation successful!")

            # Wait
            print("\nWaiting 10 seconds...")
            time.sleep(10)

        # Close profile
        if launcher.close_profile():
            print("\n✓ Profile closed!")
    else:
        print("\n✗ Failed to launch profile!")

    manager.disconnect()
