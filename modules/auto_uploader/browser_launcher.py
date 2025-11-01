"""High level browser launcher facade."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional, Dict

from .browser_controller import BrowserController
from .configuration import SettingsManager
from .browser_monitor import BrowserMonitor
from .screen_analyzer import ScreenAnalyzer
from .login_detector import LoginDetector
from .mouse_activity import MouseActivityIndicator, ActivityContext

# Try to import automation tools
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logging.warning("pyautogui not available for automated login")


class BrowserLauncher:
    """Delegates browser lifecycle operations to the controller."""

    def __init__(self, settings: SettingsManager):
        self.settings = settings
        self.controller = BrowserController(settings)

    def launch(self, browser_type: str, auto_handle_popups: bool = True, detect_login: bool = False):
        """
        Launch browser with intelligent monitoring and popup handling

        Args:
            browser_type: Type of browser to launch
            auto_handle_popups: Automatically close popups and notifications
            detect_login: Detect login status after launch (requires helper images)

        Returns:
            Browser window object or True if successful
        """
        logging.info("=" * 60)
        logging.info("🚀 Browser Launch Process")
        logging.info("=" * 60)

        # Initialize components
        monitor = BrowserMonitor(browser_type)
        analyzer = ScreenAnalyzer()
        login_detector = LoginDetector() if detect_login else None

        # Step 1: Check network connectivity
        logging.info("\n1️⃣  Checking network connectivity...")
        if not monitor.wait_for_network(max_retries=2):
            logging.error("❌ Network not available")
            logging.error("Please check your internet connection and try again")
            return None

        # Step 2: Launch browser using controller
        logging.info("\n2️⃣  Launching browser...")
        browser_window = self.controller.launch_browser(browser_type)
        if not browser_window:
            logging.error("❌ Failed to launch browser")
            return None

        # Step 3: Wait for browser to be ready
        logging.info("\n3️⃣  Waiting for browser to be ready...")
        window_title_patterns = {
            'gologin': ['GoLogin', 'Orbita', 'gologin'],
            'ix': ['ixBrowser', 'IX Browser', 'Incogniton', 'IX', 'incogniton']
        }

        patterns = window_title_patterns.get(browser_type, [browser_type])
        window = monitor.find_browser_window(patterns, timeout=30)

        if not window:
            logging.warning("⚠  Could not detect browser window")
            logging.warning("⚠  Browser may be running, proceeding anyway...")
        else:
            # Wait for browser to be responsive
            with ActivityContext("⏳ Waiting for browser responsiveness..."):
                if not monitor.wait_for_browser_load(timeout=15, show_activity=False):
                    logging.warning("⚠  Browser responsiveness timeout")

        # Step 4: Maximize window for better visibility
        logging.info("\n4️⃣  Maximizing window...")
        if window:
            monitor.maximize_window()

        # Step 5: Handle popups and notifications
        if auto_handle_popups:
            logging.info("\n5️⃣  Handling popups and notifications...")
            analyzer.handle_all_popups()

        # Step 6: Detect login status (if enabled)
        if login_detector:
            logging.info("\n6️⃣  Detecting login status...")
            with ActivityContext("🔍 Analyzing login status..."):
                status = login_detector.check_login_status()
                logging.info(f"Login Status: {status}")

        # Step 7: Final status
        logging.info("\n" + "=" * 60)
        logging.info("✅ Browser Launch Complete")
        logging.info("=" * 60)

        status = monitor.get_browser_status_summary()
        logging.info(f"Browser Type: {status['browser_type']}")
        logging.info(f"Window Found: {status['window_found']}")
        logging.info(f"Network Connected: {status['network_connected']}")

        return browser_window if browser_window else True

    def open_profile_shortcut(self, browser_type: str, shortcut: Path) -> bool:
        return self.controller.open_profile_via_shortcut(browser_type, shortcut)

    def connect(self, browser_type: str, profile_name: Optional[str] = None):
        return self.controller.connect_selenium(browser_type, profile_name)

    def close(self, browser_type: str, handle_exit_popup: bool = True):
        """
        Close browser with optional Exit Safely popup handling

        Args:
            browser_type: Browser type to close
            handle_exit_popup: Handle Exit Safely popup if it appears
        """
        if handle_exit_popup:
            logging.info("⏳ Closing browser (may show Exit Safely popup)...")
            analyzer = ScreenAnalyzer()

            # Try to close Exit Safely popup if it appears
            logging.info("Looking for Exit Safely popup...")
            analyzer.close_exit_safely_popup()
            time.sleep(1)

        self.controller.close_browser(browser_type)

    def close_all(self):
        self.controller.close_all()

    def logout_facebook(self) -> bool:
        """
        Logout from Facebook using image-based UI detection

        Returns:
            True if logout successful, False otherwise
        """
        logging.info("=" * 60)
        logging.info("🔓 Facebook Logout Process")
        logging.info("=" * 60)

        try:
            detector = LoginDetector()

            # Step 1: Get profile icon coordinates
            logging.info("\n1️⃣  Finding profile icon...")
            profile_coords = detector.get_profile_icon_coords()

            if not profile_coords:
                logging.warning("⚠ Could not find profile icon")
                logging.info("ℹ You may need to logout manually")
                return False

            logging.info(f"✓ Found profile icon at {profile_coords}")

            # Step 2: Click profile icon to open menu
            logging.info("\n2️⃣  Clicking profile icon...")
            pyautogui.click(profile_coords[0], profile_coords[1])
            time.sleep(2)

            # Step 3: Get logout button coordinates
            logging.info("\n3️⃣  Finding logout button...")
            logout_coords = detector.get_logout_button_coords()

            if not logout_coords:
                logging.warning("⚠ Could not find logout button")
                logging.info("ℹ Profile menu may not have loaded, trying keyboard")
                # Try using keyboard (Escape to close menu and try again)
                pyautogui.press('escape')
                time.sleep(1)
                return False

            logging.info(f"✓ Found logout button at {logout_coords}")

            # Step 4: Click logout button
            logging.info("\n4️⃣  Clicking logout button...")
            pyautogui.click(logout_coords[0], logout_coords[1])
            time.sleep(3)

            # Step 5: Verify logout
            logging.info("\n5️⃣  Verifying logout...")
            with ActivityContext("⏳ Waiting for logout confirmation..."):
                if detector.wait_for_logout(timeout=10):
                    logging.info("=" * 60)
                    logging.info("✅ Logout Successful")
                    logging.info("=" * 60)
                    return True
                else:
                    logging.warning("⚠ Logout verification timeout")
                    return False

        except Exception as e:
            logging.error(f"Error during logout: {e}")
            logging.info("⚠ Please logout manually if needed")
            return False

    def login_facebook(self, email: str, password: str) -> bool:
        """
        Login to Facebook using image-based UI detection and automation

        Args:
            email: Facebook email/username
            password: Facebook password

        Returns:
            True if login successful, False otherwise
        """
        logging.info("=" * 60)
        logging.info("🔐 Facebook Login Process")
        logging.info("=" * 60)

        if not PYAUTOGUI_AVAILABLE:
            logging.warning("⚠ pyautogui not available - manual login required")
            logging.info(f"📧 Email: {email}")
            logging.info("Please login manually in the browser window")
            return False

        try:
            detector = LoginDetector()
            wait_time = 1

            # Step 1: Find login form
            logging.info("\n1️⃣  Finding login form...")
            with ActivityContext("🔍 Locating login form..."):
                login_coords = detector.get_login_form_coords()

                if not login_coords:
                    logging.warning("⚠ Could not find login form")
                    logging.info("ℹ You may need to login manually")
                    return False

                logging.info(f"✓ Found login form at {login_coords}")

            # Step 2: Focus on login form
            logging.info("\n2️⃣  Focusing on login form...")
            pyautogui.click(login_coords[0], login_coords[1])
            time.sleep(wait_time)

            # Step 2.5: Clear any existing data
            logging.info("\n2️⃣ᐩ Clearing existing login data...")
            # Select all text in email field (Ctrl+A) and delete
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.3)
            pyautogui.press('delete')
            time.sleep(0.5)

            # Step 3: Enter email
            logging.info(f"\n3️⃣  Entering email: {email}")
            pyautogui.typewrite(email, interval=0.03)
            time.sleep(wait_time)

            # Step 4: Move to password field (usually Tab key)
            logging.info("\n4️⃣  Moving to password field...")
            pyautogui.press('tab')
            time.sleep(wait_time)

            # Step 4.5: Clear existing password if any
            logging.info("\n4️⃣ᐩ Clearing existing password...")
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.3)
            pyautogui.press('delete')
            time.sleep(0.5)

            # Step 5: Enter password
            logging.info("\n5️⃣  Entering password...")
            pyautogui.typewrite(password, interval=0.03)
            time.sleep(wait_time)

            # Step 6: Click login button (usually Enter)
            logging.info("\n6️⃣  Clicking login button...")
            pyautogui.press('enter')
            time.sleep(3)

            # Step 7: Verify login
            logging.info("\n7️⃣  Verifying login...")
            with ActivityContext("⏳ Waiting for login confirmation..."):
                if detector.wait_for_login(timeout=30):
                    logging.info("=" * 60)
                    logging.info("✅ Login Successful")
                    logging.info("=" * 60)
                    return True
                else:
                    logging.warning("⚠ Login verification timeout")
                    logging.warning("ℹ Check if a verification code or 2FA is required")
                    return False

        except Exception as e:
            logging.error(f"Error during login: {e}")
            logging.info("⚠ Please login manually")
            return False

    def handle_facebook_login(self, email: str, password: str) -> bool:
        """
        Complete Facebook login workflow with logout handling

        Detects current login status and:
        1. If logged in: logs out the current user
        2. Then logs in with provided credentials

        Args:
            email: Facebook email/username to login
            password: Facebook password

        Returns:
            True if login successful, False otherwise
        """
        logging.info("=" * 60)
        logging.info("🔄 Facebook Account Switching Process")
        logging.info("=" * 60)

        detector = LoginDetector()

        # Step 1: Check current login status
        logging.info("\n1️⃣  Checking current login status...")
        status = detector.check_login_status()

        if status == detector.LOGGED_IN:
            logging.info("✓ User is currently logged in")
            logging.info("\n2️⃣  Logging out current user...")

            if not self.logout_facebook():
                logging.warning("⚠ Could not auto-logout")
                logging.info("ℹ You may need to logout manually")
                time.sleep(3)

            time.sleep(2)

        elif status == detector.NOT_LOGGED_IN:
            logging.info("✓ User is not logged in")
        else:
            logging.warning("⚠ Could not determine login status")
            logging.info("ℹ Proceeding with login attempt")

        # Step 2: Login with new credentials
        logging.info("\n3️⃣  Logging in with provided credentials...")
        if self.login_facebook(email, password):
            logging.info("\n" + "=" * 60)
            logging.info("✅ Account Switching Complete")
            logging.info("=" * 60)
            return True
        else:
            logging.warning("\n⚠ Login failed")
            return False

