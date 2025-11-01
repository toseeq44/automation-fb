"""
Login Detector - Determines login status and provides UI element coordinates
Uses ImageMatcher to detect login status and find interactive elements
"""

import logging
import time
from typing import Optional, Dict, Tuple
from pathlib import Path

from .image_matcher import ImageMatcher


class LoginDetector:
    """Detect login status and find UI element coordinates"""

    # Login status constants
    LOGGED_IN = 'LOGGED_IN'
    NOT_LOGGED_IN = 'NOT_LOGGED_IN'
    UNCLEAR = 'UNCLEAR'

    # UI Element types
    PROFILE_ICON = 'current_profile_cordinates'
    LOGOUT_BUTTON = 'current_profile_relatedOption_cordinates'
    LOGIN_FORM = 'new_login_cordinates'

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize login detector

        Args:
            template_dir: Directory containing template images
        """
        self.matcher = ImageMatcher(template_dir)
        self.last_status = None
        self.status_confidence = 0.0

    def check_login_status(self, screenshot=None) -> str:
        """
        Check if user is logged in

        Args:
            screenshot: Screenshot to analyze (takes new one if None)

        Returns:
            'LOGGED_IN', 'NOT_LOGGED_IN', or 'UNCLEAR'
        """
        logging.info("🔍 Checking login status...")

        if screenshot is None:
            screenshot = self.matcher.take_screenshot()
            if screenshot is None:
                logging.error("Failed to take screenshot")
                return self.UNCLEAR

        status = self.matcher.detect_login_status(screenshot)
        self.last_status = status

        if status == self.LOGGED_IN:
            logging.info("✅ User is LOGGED IN")
            return self.LOGGED_IN
        elif status == self.NOT_LOGGED_IN:
            logging.info("📝 User needs to LOG IN")
            return self.NOT_LOGGED_IN
        else:
            logging.warning("❓ Could not determine login status")
            return self.UNCLEAR

    def get_profile_icon_coords(self, screenshot=None) -> Optional[Tuple[int, int]]:
        """
        Get profile icon coordinates (for clicking to open menu)

        Args:
            screenshot: Screenshot to analyze

        Returns:
            (x, y) tuple or None
        """
        if screenshot is None:
            screenshot = self.matcher.take_screenshot()
            if screenshot is None:
                return None

        coords = self.matcher.find_ui_element(self.PROFILE_ICON, screenshot)
        if coords:
            logging.debug(f"Found profile icon at {coords}")
        return coords

    def get_logout_button_coords(self, screenshot=None) -> Optional[Tuple[int, int]]:
        """
        Get logout button coordinates (in dropdown menu)

        Args:
            screenshot: Screenshot to analyze

        Returns:
            (x, y) tuple or None
        """
        if screenshot is None:
            screenshot = self.matcher.take_screenshot()
            if screenshot is None:
                return None

        coords = self.matcher.find_ui_element(self.LOGOUT_BUTTON, screenshot)
        if coords:
            logging.debug(f"Found logout button at {coords}")
        return coords

    def get_login_form_coords(self, screenshot=None) -> Optional[Tuple[int, int]]:
        """
        Get login form coordinates (approximate center)

        Args:
            screenshot: Screenshot to analyze

        Returns:
            (x, y) tuple or None
        """
        if screenshot is None:
            screenshot = self.matcher.take_screenshot()
            if screenshot is None:
                return None

        coords = self.matcher.find_ui_element(self.LOGIN_FORM, screenshot)
        if coords:
            logging.debug(f"Found login form at {coords}")
        return coords

    def get_all_login_ui_coords(self, screenshot=None) -> Dict[str, Optional[Tuple[int, int]]]:
        """
        Get all login-related UI element coordinates

        Args:
            screenshot: Screenshot to analyze

        Returns:
            Dictionary with element names as keys and coordinates as values
        """
        if screenshot is None:
            screenshot = self.matcher.take_screenshot()
            if screenshot is None:
                return {}

        elements = [
            self.PROFILE_ICON,
            self.LOGOUT_BUTTON,
            self.LOGIN_FORM
        ]

        coords = self.matcher.find_multiple_elements(elements, screenshot)
        return coords

    def wait_for_login(self, timeout: int = 30, check_interval: int = 2) -> bool:
        """
        Wait for user to login

        Args:
            timeout: Maximum time to wait (seconds)
            check_interval: Time between checks (seconds)

        Returns:
            True if logged in, False if timeout
        """
        logging.info(f"⏳ Waiting for login (max {timeout}s)...")

        start_time = time.time()

        while (time.time() - start_time) < timeout:
            status = self.check_login_status()

            if status == self.LOGGED_IN:
                elapsed = int(time.time() - start_time)
                logging.info(f"✅ Login detected after {elapsed}s")
                return True

            remaining = timeout - int(time.time() - start_time)
            if remaining > 0:
                logging.debug(f"  Still waiting... ({remaining}s remaining)")
            time.sleep(check_interval)

        logging.warning(f"⚠ Login timeout after {timeout}s")
        return False

    def wait_for_logout(self, timeout: int = 10, check_interval: int = 2) -> bool:
        """
        Wait for user to logout

        Args:
            timeout: Maximum time to wait (seconds)
            check_interval: Time between checks (seconds)

        Returns:
            True if logged out, False if timeout
        """
        logging.info(f"⏳ Waiting for logout (max {timeout}s)...")

        start_time = time.time()

        while (time.time() - start_time) < timeout:
            status = self.check_login_status()

            if status == self.NOT_LOGGED_IN:
                elapsed = int(time.time() - start_time)
                logging.info(f"✅ Logout verified after {elapsed}s")
                return True

            remaining = timeout - int(time.time() - start_time)
            if remaining > 0:
                logging.debug(f"  Still waiting... ({remaining}s remaining)")
            time.sleep(check_interval)

        logging.warning(f"⚠ Logout timeout after {timeout}s")
        return False

    def is_logged_in(self, screenshot=None) -> bool:
        """
        Quick check if logged in

        Args:
            screenshot: Screenshot to analyze

        Returns:
            True if logged in
        """
        status = self.check_login_status(screenshot)
        return status == self.LOGGED_IN

    def needs_login(self, screenshot=None) -> bool:
        """
        Quick check if needs login

        Args:
            screenshot: Screenshot to analyze

        Returns:
            True if needs login
        """
        status = self.check_login_status(screenshot)
        return status == self.NOT_LOGGED_IN
