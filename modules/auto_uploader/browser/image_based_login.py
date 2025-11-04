"""
Image-Based Login Automation
=============================

Uses image recognition and pyautogui to detect login status and automate Facebook login.

Workflow:
1. Activate browser window
2. Detect user's login status using reference images
3. If logged in: Proceed to creator automation
4. If logged out: Auto-fill login form
5. Handle logout and re-login requests

Reference Images:
- sample_login_window.png: Login form detection
- check_user_status.png: User logged-in status
- user_status_dropdown.png: Logout dropdown menu
"""

import logging
import time
from pathlib import Path
from typing import Optional, Dict, Tuple

try:
    import pyautogui
    import cv2
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False

from .screen_detector import ScreenDetector


class ImageBasedLogin:
    """Automated login using pure image recognition and keyboard/mouse automation."""

    def __init__(self, debug_port: int = 9223, chromedriver_path: Optional[str] = None):
        """
        Initialize login automator.

        Args:
            debug_port: Browser debug port (not used in pure image-based approach)
            chromedriver_path: Path to chromedriver (not used in pure image-based approach)
        """
        if not AUTOMATION_AVAILABLE:
            raise ImportError("pyautogui and opencv-python are required for login automation")

        self.screen_detector = ScreenDetector()
        self.type_interval = 0.05  # Natural typing speed (milliseconds between keystrokes)

        logging.debug("ImageBasedLogin initialized (pure image-based automation)")

    def _activate_browser_window(self) -> bool:
        """Activate/focus browser window."""
        try:
            logging.debug("Activating browser window...")
            # Click center of screen to focus browser
            screenshot = self.screen_detector.capture_screen()
            height, width = screenshot.shape[:2]
            pyautogui.click(width // 2, height // 2)
            time.sleep(0.5)
            logging.info("✓ Browser window activated")
            return True
        except Exception as e:
            logging.error("Error activating browser: %s", e)
            return False

    def _detect_login_status(self) -> str:
        """
        Detect current login status using image recognition.

        Returns:
            "logged_in", "logged_out", or "unknown"
        """
        logging.info("Detecting login status...")

        # Check for user logged-in indicator
        status_result = self.screen_detector.detect_user_status()
        if status_result['logged_in']:
            logging.info("✓ User is LOGGED IN")
            return "logged_in"

        # Check for login window
        login_result = self.screen_detector.detect_custom_element("sample_login_window.png")
        if login_result['found']:
            logging.info("✓ Login window DETECTED - User is LOGGED OUT")
            return "logged_out"

        logging.warning("⚠ Could not determine login status")
        return "unknown"

    def _fill_email_field(self, email: str) -> bool:
        """Locate and fill email field."""
        try:
            logging.info("Filling email field...")
            screenshot = self.screen_detector.capture_screen()
            height, width = screenshot.shape[:2]

            # Email field is typically in upper portion of login form
            email_x = int(width * 0.5)
            email_y = int(height * 0.35)

            logging.debug("Clicking email field at (%d, %d)", email_x, email_y)
            pyautogui.click(email_x, email_y)
            time.sleep(0.3)

            # Clear existing content
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.press('delete')
            time.sleep(0.1)

            # Type email naturally
            logging.debug("Typing email: %s", email)
            for char in email:
                pyautogui.typewrite(char, interval=self.type_interval)

            time.sleep(0.3)
            logging.info("✓ Email filled: %s", email)
            return True
        except Exception as e:
            logging.error("Error filling email field: %s", e)
            return False

    def _fill_password_field(self, password: str) -> bool:
        """Locate and fill password field."""
        try:
            logging.info("Filling password field...")
            screenshot = self.screen_detector.capture_screen()
            height, width = screenshot.shape[:2]

            # Password field is below email field
            password_x = int(width * 0.5)
            password_y = int(height * 0.45)

            logging.debug("Clicking password field at (%d, %d)", password_x, password_y)
            pyautogui.click(password_x, password_y)
            time.sleep(0.3)

            # Clear existing content
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.press('delete')
            time.sleep(0.1)

            # Type password naturally
            logging.debug("Typing password (length: %d)", len(password))
            for char in password:
                pyautogui.typewrite(char, interval=self.type_interval)

            time.sleep(0.3)
            logging.info("✓ Password filled")
            return True
        except Exception as e:
            logging.error("Error filling password field: %s", e)
            return False

    def _click_login_button(self) -> bool:
        """Locate and click login button."""
        try:
            logging.info("Clicking login button...")
            screenshot = self.screen_detector.capture_screen()
            height, width = screenshot.shape[:2]

            # Login button is typically centered below password field
            button_x = int(width * 0.5)
            button_y = int(height * 0.55)

            logging.debug("Clicking login button at (%d, %d)", button_x, button_y)
            pyautogui.click(button_x, button_y)

            logging.info("✓ Login button clicked")
            return True
        except Exception as e:
            logging.error("Error clicking login button: %s", e)
            return False

    def _logout_user(self) -> bool:
        """Handle logout process using image recognition."""
        logging.info("Initiating logout...")

        try:
            # Wait for dropdown to appear
            logging.info("Waiting for user dropdown menu...")
            dropdown_result = self.screen_detector.wait_for_element(
                "user_status_dropdown.png", timeout=5
            )

            if dropdown_result['found']:
                logging.info("✓ Dropdown found at %s", dropdown_result['position'])

                # Click logout option (usually at bottom of dropdown)
                logout_x = dropdown_result['position'][0]
                logout_y = dropdown_result['position'][1] + 80

                logging.info("Clicking logout option...")
                pyautogui.click(logout_x, logout_y)
                time.sleep(2)

                logging.info("✓ Logout successful")
                return True
            else:
                logging.warning("Dropdown not found, trying user icon...")

                # Try clicking user icon directly
                screenshot = self.screen_detector.capture_screen()
                height, width = screenshot.shape[:2]

                icon_x = int(width * 0.9)
                icon_y = int(height * 0.1)

                pyautogui.click(icon_x, icon_y)
                time.sleep(0.5)
                pyautogui.click(icon_x, icon_y + 80)
                time.sleep(2)

                logging.info("✓ Logout attempt completed")
                return True

        except Exception as e:
            logging.error("Error during logout: %s", e)
            return False

    def run_login_flow(self, email: str, password: str, force_relogin: bool = False) -> bool:
        """
        Complete login flow with intelligent detection.

        Args:
            email: Email for login
            password: Password for login
            force_relogin: Force logout and re-login even if already logged in

        Returns:
            True if logged in successfully, False otherwise
        """
        logging.info("")
        logging.info("┌" + "─"*68 + "┐")
        logging.info("│ 🔐 IMAGE-BASED LOGIN FLOW - INTELLIGENT STATE DETECTION          │")
        logging.info("└" + "─"*68 + "┘")
        logging.info("")

        try:
            # Step 1: Activate browser window
            logging.info("Step 1/5: Activating browser window...")
            if not self._activate_browser_window():
                logging.error("Failed to activate browser")
                return False

            time.sleep(1)

            # Step 2: Detect login status
            logging.info("Step 2/5: Detecting login status...")
            status = self._detect_login_status()

            if status == "logged_in":
                logging.info("✓ User already logged in")

                if force_relogin:
                    logging.info("  force_relogin=True, proceeding with logout...")
                    if not self._logout_user():
                        logging.warning("  ✗ Logout failed")
                        return False

                    logging.info("  ✓ Logout successful, proceeding to login...")
                    return self._perform_login(email, password)
                else:
                    logging.info("  ✓ Already logged in, skipping login")
                    return True

            elif status == "logged_out":
                logging.info("✓ User not logged in, proceeding with login...")
                return self._perform_login(email, password)

            else:
                logging.warning("⚠ Login status unclear, attempting login...")
                return self._perform_login(email, password)

        except Exception as e:
            logging.error("Login flow error: %s", e, exc_info=True)
            return False

    def _perform_login(self, email: str, password: str) -> bool:
        """Execute login process."""
        logging.info("Step 3/5: Waiting for login page to load...")
        login_result = self.screen_detector.wait_for_element(
            "sample_login_window.png", timeout=10
        )

        if not login_result['found']:
            logging.warning("Login window not detected within timeout")
            return False

        time.sleep(1)

        # Fill credentials
        logging.info("Step 4/5: Filling login credentials...")
        if not self._fill_email_field(email):
            logging.warning("Failed to fill email field")
            return False

        time.sleep(0.5)

        if not self._fill_password_field(password):
            logging.warning("Failed to fill password field")
            return False

        time.sleep(0.5)

        # Click login button
        logging.info("Step 5/5: Clicking login button...")
        if not self._click_login_button():
            logging.warning("Failed to click login button")
            return False

        # Wait for login to complete
        logging.info("Waiting for login completion (3 seconds)...")
        time.sleep(3)

        logging.info("")
        logging.info("┌" + "─"*68 + "┐")
        logging.info("│ ✅ LOGIN PROCESS COMPLETED SUCCESSFULLY                          │")
        logging.info("└" + "─"*68 + "┘")
        logging.info("")

        return True
