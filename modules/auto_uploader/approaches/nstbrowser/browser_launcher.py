"""
NSTbrowser Browser Launcher
Launches browser programmatically using NSTbrowser API
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
        logger.debug("[NSTLauncher] pywin32 not available - parent window hiding disabled")
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
    logger.warning("[NSTLauncher] Selenium not installed!")
    logger.warning("[NSTLauncher] Install with: pip install selenium")


class NSTBrowserLauncher:
    """Launches and manages NSTbrowser profiles with Selenium."""

    def __init__(self, client: Any):
        """
        Initialize browser launcher.

        Args:
            client: NstbrowserClient instance from connection_manager
        """
        self.client = client
        self.current_profile_id: Optional[str] = None
        self.driver: Optional[Any] = None
        self.session_info: Optional[Dict[str, Any]] = None

        logger.info("[NSTLauncher] Browser launcher initialized")

    def _hide_nstbrowser_parent_window(self) -> bool:
        """
        Hide NSTbrowser parent window to make it look like manual opening.

        Returns:
            True if parent window was found and hidden
        """
        if not HAS_WIN32:
            logger.debug("[NSTLauncher] Win32 API not available, cannot hide parent window")
            return False

        try:
            # Find NSTbrowser main window
            def find_nstbrowser_window(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    # Look for NSTbrowser main application window
                    if "nstbrowser" in title.lower() and "facebook.com" not in title.lower():
                        windows.append(hwnd)
                return True

            windows = []
            win32gui.EnumWindows(find_nstbrowser_window, windows)

            if windows:
                for hwnd in windows:
                    # Minimize the window instead of hiding (less disruptive)
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                    logger.info("[NSTLauncher] ✓ NSTbrowser parent window minimized")
                return True
            else:
                logger.debug("[NSTLauncher] NSTbrowser parent window not found")
                return False

        except Exception as e:
            logger.debug("[NSTLauncher] Error hiding parent window: %s", str(e))
            return False

    def _normalize_browser_window_title(self) -> bool:
        """
        Normalize browser window title to remove proxy information.

        Returns:
            True if title was normalized
        """
        if not HAS_WIN32:
            logger.debug("[NSTLauncher] Win32 API not available, cannot normalize title")
            return False

        try:
            # Find browser window with proxy information in title
            def find_browser_window_with_proxy(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    # Look for proxy pattern in title
                    if "].Proxy]" in title or "[" in title and "|" in title:
                        windows.append((hwnd, title))
                return True

            windows = []
            win32gui.EnumWindows(find_browser_window_with_proxy, windows)

            if windows:
                for hwnd, old_title in windows:
                    # Extract clean title: remove proxy prefix
                    if "|" in old_title:
                        clean_title = old_title.split("|", 1)[1].strip()
                        win32gui.SetWindowText(hwnd, clean_title)
                        logger.info("[NSTLauncher] ✓ Browser window title normalized")
                        logger.info("[NSTLauncher]   From: %s", old_title)
                        logger.info("[NSTLauncher]   To: %s", clean_title)
                return True
            else:
                logger.debug("[NSTLauncher] No browser window with proxy info found")
                return False

        except Exception as e:
            logger.debug("[NSTLauncher] Error normalizing title: %s", str(e))
            return False

    def launch_profile(self, profile_id: str) -> bool:
        """
        Launch NSTbrowser profile.

        Args:
            profile_id: Profile ID to launch (string format)

        Returns:
            True if launched successfully
        """
        if not self.client:
            logger.error("[NSTLauncher] No client provided!")
            return False

        logger.info("[NSTLauncher] Launching profile ID: %s", profile_id)

        try:
            # Start browser using NSTbrowser API
            logger.info("[NSTLauncher] Starting browser via API...")
            response = self.client.browsers.start_browser(profile_id=profile_id)

            if response is None or response.get('code') != 0:
                error_msg = response.get('message', 'Unknown error') if response else 'No response'
                logger.error("[NSTLauncher] Failed to start browser!")
                logger.error("[NSTLauncher]   Error: %s", error_msg)
                return False

            logger.info("[NSTLauncher] ✓ Browser start request sent successfully!")

            # Store profile ID
            self.current_profile_id = profile_id

            # Wait for browser to fully start
            logger.info("[NSTLauncher] Waiting for browser to start...")
            time.sleep(3)

            # Get debugger address
            logger.info("[NSTLauncher] Getting debugger address...")
            debugger_response = self.client.browsers.get_browser_debugger(profile_id=profile_id)

            if debugger_response is None or debugger_response.get('code') != 0:
                error_msg = debugger_response.get('message', 'Unknown error') if debugger_response else 'No response'
                logger.error("[NSTLauncher] Failed to get debugger address!")
                logger.error("[NSTLauncher]   Error: %s", error_msg)
                return False

            # Extract debugger address from response
            debugger_data = debugger_response.get('data', {})
            debugging_address = debugger_data.get('ws', '')

            # Parse debugging address to get host:port format
            # Expected format: ws://127.0.0.1:xxxxx/devtools/browser/...
            if debugging_address.startswith('ws://'):
                # Extract host:port from ws URL
                # ws://127.0.0.1:12345/devtools/browser/... -> 127.0.0.1:12345
                parts = debugging_address.replace('ws://', '').split('/', 1)
                debugging_address = parts[0] if parts else debugging_address

            logger.info("[NSTLauncher] ✓ Profile opened successfully!")
            logger.info("[NSTLauncher]   Debug Address: %s", debugging_address)

            # Store session info
            self.session_info = {
                'profile_id': profile_id,
                'debugging_address': debugging_address,
                'debugger_data': debugger_data
            }

            # Normalize browser experience to mimic manual opening
            logger.info("[NSTLauncher] Normalizing browser window appearance...")

            # 1. Minimize NSTbrowser parent window
            self._hide_nstbrowser_parent_window()

            # 2. Clean up browser window title (remove proxy info)
            time.sleep(0.5)  # Small delay to ensure window is ready
            self._normalize_browser_window_title()

            return True

        except Exception as e:
            logger.error("[NSTLauncher] Error launching profile: %s", str(e))
            return False

    def attach_selenium(self, webdriver_path: Optional[str] = None) -> bool:
        """
        Attach Selenium WebDriver to launched profile.

        Args:
            webdriver_path: Path to chromedriver (optional, uses system default if not provided)

        Returns:
            True if Selenium attached successfully
        """
        if not HAS_SELENIUM:
            logger.error("[NSTLauncher] Selenium not installed!")
            logger.error("[NSTLauncher] Install with: pip install selenium")
            return False

        if not self.session_info:
            logger.error("[NSTLauncher] No active session! Launch profile first.")
            return False

        debugging_address = self.session_info.get('debugging_address')

        if not debugging_address:
            logger.error("[NSTLauncher] Invalid session info - no debugging address!")
            return False

        logger.info("[NSTLauncher] Attaching Selenium WebDriver...")
        logger.info("[NSTLauncher]   Debug Address: %s", debugging_address)
        if webdriver_path:
            logger.info("[NSTLauncher]   WebDriver: %s", webdriver_path)

        try:
            # Configure Chrome options
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", debugging_address)

            # Create Selenium driver (Selenium 4+ syntax)
            if webdriver_path:
                self.driver = Chrome(
                    service=Service(webdriver_path),
                    options=chrome_options
                )
            else:
                # Use system chromedriver
                self.driver = Chrome(options=chrome_options)

            logger.info("[NSTLauncher] ✓ Selenium attached successfully!")

            # Maximize browser window
            try:
                self.driver.maximize_window()
                logger.info("[NSTLauncher] ✓ Browser window maximized")
            except Exception as e:
                logger.debug("[NSTLauncher] Could not maximize window: %s", str(e))

            # Get current URL to verify
            try:
                current_url = self.driver.current_url
                logger.info("[NSTLauncher]   Current URL: %s", current_url)
            except Exception:
                logger.debug("[NSTLauncher]   Could not get current URL")

            return True

        except Exception as e:
            logger.error("[NSTLauncher] Failed to attach Selenium: %s", str(e))
            self.driver = None
            return False

    def get_driver(self) -> Optional[Any]:
        """
        Get Selenium WebDriver instance.

        Returns:
            WebDriver instance or None
        """
        if not self.driver:
            logger.warning("[NSTLauncher] No driver available! Attach Selenium first.")
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
            logger.error("[NSTLauncher] No driver available!")
            return False

        logger.info("[NSTLauncher] Navigating to: %s", url)

        try:
            self.driver.get(url)
            logger.info("[NSTLauncher] ✓ Navigation successful!")
            return True
        except Exception as e:
            logger.error("[NSTLauncher] Navigation failed: %s", str(e))
            return False

    def close_profile(self) -> bool:
        """
        Close current profile.

        Returns:
            True if closed successfully
        """
        if not self.current_profile_id:
            logger.warning("[NSTLauncher] No profile to close!")
            return True

        logger.info("[NSTLauncher] Closing profile ID: %s", self.current_profile_id)

        try:
            # Close Selenium driver first (if exists)
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("[NSTLauncher] ✓ Selenium driver closed")
                except Exception as e:
                    logger.debug("[NSTLauncher] Error closing driver: %s", str(e))
                finally:
                    self.driver = None

            # Stop browser via API
            response = self.client.browsers.stop_browser(profile_id=self.current_profile_id)

            if response is None or response.get('code') != 0:
                error_msg = response.get('message', 'Unknown error') if response else 'No response'
                logger.error("[NSTLauncher] Failed to stop browser!")
                logger.error("[NSTLauncher]   Error: %s", error_msg)
                return False

            logger.info("[NSTLauncher] ✓ Profile closed successfully!")

            # Clear state
            self.current_profile_id = None
            self.session_info = None

            return True

        except Exception as e:
            logger.error("[NSTLauncher] Error closing profile: %s", str(e))
            return False

    def is_profile_open(self) -> bool:
        """
        Check if profile is currently open.

        Returns:
            True if profile is open
        """
        return self.current_profile_id is not None

    def get_current_profile_id(self) -> Optional[str]:
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
    import sys
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    from connection_manager import NSTConnectionManager

    print("\n" + "="*60)
    print("Testing NSTbrowser Browser Launcher")
    print("="*60 + "\n")

    # Get API key
    api_key = input("Enter NSTbrowser API key: ").strip()
    if not api_key:
        print("✗ API key required!")
        sys.exit(1)

    # Connect to API
    manager = NSTConnectionManager(api_key=api_key)
    if not manager.connect():
        print("✗ Connection failed!")
        sys.exit(1)

    client = manager.get_client()

    # Get first profile
    profiles = manager.get_profile_list(page_size=1)
    if not profiles:
        print("✗ No profiles found!")
        sys.exit(1)

    profile_id = profiles[0]['id']
    print(f"Using profile: {profiles[0]['name']} (ID: {profile_id})\n")

    # Launch profile
    launcher = NSTBrowserLauncher(client)

    if launcher.launch_profile(profile_id):
        print("\n✓ Profile launched!")

        # Attach Selenium
        if launcher.attach_selenium():
            print("✓ Selenium attached!")

            # Navigate to test page
            if launcher.navigate_to("https://www.nstbrowser.io"):
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
