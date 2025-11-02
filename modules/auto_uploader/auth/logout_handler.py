"""
Logout Handler
==============
Handles Facebook logout operations and session cleanup.

Integrates with browser/login_manager for intelligent logout.
"""

import logging
import time
from typing import Optional, Dict, Any

from ..browser.login_manager import LoginManager
from ..browser.mouse_controller import MouseController


class LogoutHandler:
    """Handles logout operations using intelligent browser module."""

    def __init__(self, driver: Optional[Any] = None, config: Optional[Dict] = None):
        """
        Initialize logout handler.

        Args:
            driver: Selenium WebDriver instance
            config: Configuration dictionary
        """
        self.driver = driver
        self.config = config or {}
        self.login_manager = LoginManager(driver)
        self.mouse = MouseController()

        logging.debug("LogoutHandler initialized")

    def logout(self, timeout: int = 30) -> bool:
        """
        Perform Facebook logout using intelligent detection.

        Uses browser/login_manager.logout_current_user() which:
        - Detects user status with image recognition
        - Hovers over profile icon
        - Detects logout dropdown
        - Clicks logout
        - Handles browser close popups

        Args:
            timeout: Maximum time to wait for logout

        Returns:
            True if logged out successfully

        Example:
            >>> handler = LogoutHandler(driver)
            >>> if handler.logout():
            >>>     print("Logged out successfully")
        """
        logging.info("Logging out from Facebook...")

        if not self.driver:
            logging.error("No WebDriver available")
            return False

        # Use browser/login_manager for intelligent logout
        success = self.login_manager.logout_current_user(timeout=timeout)

        if success:
            logging.info("✓ Logout successful")
        else:
            logging.warning("✗ Logout may have failed")

        return success

    def clear_session_data(self) -> bool:
        """
        Clear session data (cookies, localStorage, sessionStorage).

        Args:
            None (uses self.driver)

        Returns:
            True if cleared successfully

        Example:
            >>> handler = LogoutHandler(driver)
            >>> handler.logout()
            >>> handler.clear_session_data()  # Extra cleanup
        """
        logging.info("Clearing session data...")

        if not self.driver:
            logging.error("No WebDriver available")
            return False

        try:
            # Clear cookies
            self.driver.delete_all_cookies()
            logging.debug("✓ Cookies cleared")

            # Clear localStorage
            try:
                self.driver.execute_script("window.localStorage.clear();")
                logging.debug("✓ localStorage cleared")
            except Exception as e:
                logging.warning("Could not clear localStorage: %s", e)

            # Clear sessionStorage
            try:
                self.driver.execute_script("window.sessionStorage.clear();")
                logging.debug("✓ sessionStorage cleared")
            except Exception as e:
                logging.warning("Could not clear sessionStorage: %s", e)

            logging.info("✓ Session data cleared")
            return True

        except Exception as e:
            logging.error("Error clearing session data: %s", e, exc_info=True)
            return False

    def logout_and_clear(self, timeout: int = 30) -> bool:
        """
        Logout and clear all session data.

        Combines logout() and clear_session_data().

        Args:
            timeout: Maximum time to wait for logout

        Returns:
            True if both operations successful

        Example:
            >>> handler = LogoutHandler(driver)
            >>> handler.logout_and_clear()  # Complete cleanup
        """
        logging.info("Logging out and clearing session data...")

        # Logout first
        logout_success = self.logout(timeout=timeout)

        # Then clear session data
        clear_success = self.clear_session_data()

        if logout_success and clear_success:
            logging.info("✓ Logout and cleanup completed")
            return True
        else:
            logging.warning("✗ Logout/cleanup may be incomplete")
            return False

    def force_logout(self) -> bool:
        """
        Force logout by directly navigating to logout URL.

        Use this if standard logout fails.

        Returns:
            True if navigation successful

        Example:
            >>> handler = LogoutHandler(driver)
            >>> if not handler.logout():
            >>>     handler.force_logout()  # Try force logout
        """
        logging.info("Attempting force logout...")

        if not self.driver:
            logging.error("No WebDriver available")
            return False

        try:
            # Navigate to Facebook logout URL
            logout_url = "https://www.facebook.com/logout.php"
            self.driver.get(logout_url)

            # Show animation while waiting
            self.mouse.circular_idle_movement(duration=2.0, radius=35)

            time.sleep(3)

            logging.info("✓ Force logout completed")
            return True

        except Exception as e:
            logging.error("Error during force logout: %s", e, exc_info=True)
            return False

    def verify_logout(self) -> bool:
        """
        Verify that logout was successful.

        Uses image recognition to check if user is logged out.

        Returns:
            True if logged out

        Example:
            >>> handler = LogoutHandler(driver)
            >>> handler.logout()
            >>> if handler.verify_logout():
            >>>     print("Verified: User is logged out")
        """
        logging.info("Verifying logout status...")

        status = self.login_manager.check_login_status()

        if not status.get('logged_in', True):  # Default to True if check fails
            logging.info("✓ Verified: User is logged out")
            return True
        else:
            logging.warning("✗ Verification failed: User may still be logged in")
            return False

    def logout_with_verification(self, timeout: int = 30, retry_count: int = 2) -> bool:
        """
        Logout with automatic verification and retry.

        Args:
            timeout: Maximum time to wait for each logout attempt
            retry_count: Number of retry attempts if verification fails

        Returns:
            True if logout verified

        Example:
            >>> handler = LogoutHandler(driver)
            >>> success = handler.logout_with_verification(retry_count=3)
        """
        logging.info("Logging out with verification (retries: %d)...", retry_count)

        for attempt in range(retry_count + 1):
            logging.info("Logout attempt %d/%d", attempt + 1, retry_count + 1)

            # Attempt logout
            self.logout(timeout=timeout)

            # Verify
            time.sleep(2)
            if self.verify_logout():
                logging.info("✓ Logout verified on attempt %d", attempt + 1)
                return True

            # If not verified and retries remaining
            if attempt < retry_count:
                logging.warning("Logout not verified, retrying...")
                time.sleep(2)
            else:
                logging.warning("✗ Logout verification failed after %d attempts", retry_count + 1)
                # Try force logout as last resort
                logging.info("Attempting force logout as last resort...")
                self.force_logout()
                time.sleep(2)
                return self.verify_logout()

        return False

    def clear_specific_cookies(self, cookie_names: list) -> bool:
        """
        Clear specific cookies by name.

        Args:
            cookie_names: List of cookie names to clear

        Returns:
            True if cleared successfully

        Example:
            >>> handler = LogoutHandler(driver)
            >>> handler.clear_specific_cookies(['c_user', 'xs'])
        """
        logging.info("Clearing specific cookies: %s", cookie_names)

        if not self.driver:
            logging.error("No WebDriver available")
            return False

        try:
            for cookie_name in cookie_names:
                try:
                    self.driver.delete_cookie(cookie_name)
                    logging.debug("✓ Cleared cookie: %s", cookie_name)
                except Exception as e:
                    logging.warning("Could not clear cookie '%s': %s", cookie_name, e)

            logging.info("✓ Specific cookies cleared")
            return True

        except Exception as e:
            logging.error("Error clearing specific cookies: %s", e, exc_info=True)
            return False

    def set_driver(self, driver: Any) -> None:
        """
        Set or update WebDriver instance.

        Args:
            driver: Selenium WebDriver
        """
        self.driver = driver
        self.login_manager.set_driver(driver)
        logging.debug("WebDriver updated")

    def get_logout_status(self) -> Dict[str, Any]:
        """
        Get detailed logout status.

        Returns:
            Dictionary with logout status info

        Example:
            >>> status = handler.get_logout_status()
            >>> print(f"Logged out: {status['logged_out']}")
        """
        login_status = self.login_manager.check_login_status()

        status = {
            'logged_out': not login_status.get('logged_in', False),
            'logged_in': login_status.get('logged_in', False),
            'confidence': login_status.get('confidence', 0.0)
        }

        return status
