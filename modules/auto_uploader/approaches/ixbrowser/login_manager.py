"""
ixBrowser Login Manager
Detects current login status and manages login/logout
Checks if correct user is logged in Facebook
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Try to import Selenium
try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False
    By = None
    WebDriverWait = None
    EC = None
    logger.warning("[IXLogin] Selenium not installed!")


class LoginManager:
    """Manages Facebook login detection and authentication."""

    def __init__(self, driver: Any, expected_email: str, expected_password: str):
        """
        Initialize login manager.

        Args:
            driver: Selenium WebDriver instance
            expected_email: Expected logged-in email
            expected_password: Password for login if needed
        """
        self.driver = driver
        self.expected_email = expected_email
        self.expected_password = expected_password

        logger.info("[IXLogin] Login manager initialized")
        logger.info("[IXLogin]   Expected email: %s", expected_email)

    def navigate_to_facebook(self) -> bool:
        """
        Navigate to Facebook homepage.

        Returns:
            True if navigation successful
        """
        logger.info("[IXLogin] Navigating to Facebook...")

        try:
            self.driver.get("https://www.facebook.com")
            time.sleep(3)  # Wait for page load

            logger.info("[IXLogin] ✓ Navigated to Facebook")
            logger.info("[IXLogin]   Current URL: %s", self.driver.current_url)
            return True

        except Exception as e:
            logger.error("[IXLogin] Navigation failed: %s", str(e))
            return False

    def check_login_status(self) -> tuple[bool, Optional[str]]:
        """
        Check if user is logged in and get current user email.

        Returns:
            Tuple of (is_logged_in, current_email)
        """
        logger.info("[IXLogin] Checking login status...")

        try:
            # Wait a bit for page to load
            time.sleep(2)

            # Method 1: Check for profile icon/menu (indicates logged in)
            profile_selectors = [
                "div[aria-label*='Account']",
                "div[aria-label*='Your profile']",
                "svg[aria-label='Your profile']",
                "a[aria-label*='Profile']",
                "div[role='banner'] svg",  # Top navigation icons
            ]

            is_logged_in = False
            for selector in profile_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.info("[IXLogin] ✓ Found profile indicator: %s", selector)
                        is_logged_in = True
                        break
                except Exception:
                    continue

            if not is_logged_in:
                # Check if login form is present (means not logged in)
                try:
                    login_button = self.driver.find_element(By.NAME, "login")
                    if login_button:
                        logger.info("[IXLogin] ✗ Login form detected - user NOT logged in")
                        return False, None
                except NoSuchElementException:
                    pass

            if is_logged_in:
                logger.info("[IXLogin] ✓ User is logged in")

                # Try to get current email
                current_email = self._get_current_user_email()

                if current_email:
                    logger.info("[IXLogin]   Current user: %s", current_email)
                else:
                    logger.info("[IXLogin]   Could not detect current user email")

                return True, current_email
            else:
                logger.info("[IXLogin] ✗ User is NOT logged in")
                return False, None

        except Exception as e:
            logger.error("[IXLogin] Error checking login status: %s", str(e))
            # Assume not logged in on error
            return False, None

    def _get_current_user_email(self) -> Optional[str]:
        """
        Try to extract current logged-in user email.

        Returns:
            Email string or None
        """
        logger.info("[IXLogin] Attempting to detect current user email...")

        try:
            # Method 1: Navigate to settings page
            original_url = self.driver.current_url

            try:
                self.driver.get("https://www.facebook.com/settings")
                time.sleep(2)

                # Look for email in settings page
                email_selectors = [
                    "//div[contains(text(), '@')]",
                    "//span[contains(text(), '@')]",
                    "//td[contains(text(), '@')]",
                ]

                for selector in email_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        for elem in elements:
                            text = elem.text.strip()
                            if "@" in text and "." in text:
                                # Basic email validation
                                if len(text) < 100 and " " not in text:
                                    logger.info("[IXLogin] ✓ Detected email from settings: %s", text)
                                    # Go back to original page
                                    self.driver.get(original_url)
                                    return text
                    except Exception:
                        continue

                # Go back to original page
                self.driver.get(original_url)
                time.sleep(1)

            except Exception as e:
                logger.debug("[IXLogin] Settings page method failed: %s", str(e))
                # Go back to original page
                try:
                    self.driver.get(original_url)
                except Exception:
                    pass

            # Method 2: Check cookies for email hint
            try:
                cookies = self.driver.get_cookies()
                for cookie in cookies:
                    if 'c_user' in cookie.get('name', ''):
                        # Facebook user ID cookie exists
                        logger.info("[IXLogin] User ID cookie found (logged in confirmed)")
                        break
            except Exception:
                pass

            logger.info("[IXLogin] Could not extract email automatically")
            return None

        except Exception as e:
            logger.error("[IXLogin] Error getting current email: %s", str(e))
            return None

    def verify_correct_user_logged_in(self) -> bool:
        """
        Check if correct user (expected email) is logged in.

        Returns:
            True if correct user is logged in
        """
        logger.info("[IXLogin] Verifying correct user is logged in...")

        is_logged_in, current_email = self.check_login_status()

        if not is_logged_in:
            logger.info("[IXLogin] ✗ No user logged in")
            return False

        if not current_email:
            logger.warning("[IXLogin] ⚠ User is logged in but email unknown")
            logger.warning("[IXLogin]   Cannot verify if correct user")
            # Assume correct user if we can't detect email
            return True

        # Compare emails (case-insensitive)
        if current_email.lower() == self.expected_email.lower():
            logger.info("[IXLogin] ✓ Correct user is logged in!")
            return True
        else:
            logger.warning("[IXLogin] ✗ Wrong user logged in!")
            logger.warning("[IXLogin]   Expected: %s", self.expected_email)
            logger.warning("[IXLogin]   Current: %s", current_email)
            return False

    def logout(self) -> bool:
        """
        Logout current user from Facebook.

        Returns:
            True if logout successful
        """
        logger.info("[IXLogin] Logging out current user...")

        try:
            # Navigate to logout URL directly
            logout_url = "https://www.facebook.com/logout.php"

            logger.info("[IXLogin] Navigating to logout URL...")
            self.driver.get(logout_url)
            time.sleep(3)

            # Verify logout
            is_logged_in, _ = self.check_login_status()

            if not is_logged_in:
                logger.info("[IXLogin] ✓ Logout successful!")
                return True
            else:
                logger.warning("[IXLogin] ⚠ Logout may have failed - user still appears logged in")
                return False

        except Exception as e:
            logger.error("[IXLogin] Logout failed: %s", str(e))
            return False

    def login(self) -> bool:
        """
        Login to Facebook with expected credentials.

        Returns:
            True if login successful
        """
        logger.info("[IXLogin] Logging in to Facebook...")
        logger.info("[IXLogin]   Email: %s", self.expected_email)

        try:
            # Navigate to Facebook login page
            self.driver.get("https://www.facebook.com")
            time.sleep(2)

            # Find email input
            logger.info("[IXLogin] Entering email...")
            email_input = self.driver.find_element(By.ID, "email")
            email_input.clear()
            email_input.send_keys(self.expected_email)

            # Find password input
            logger.info("[IXLogin] Entering password...")
            password_input = self.driver.find_element(By.ID, "pass")
            password_input.clear()
            password_input.send_keys(self.expected_password)

            # Click login button
            logger.info("[IXLogin] Clicking login button...")
            login_button = self.driver.find_element(By.NAME, "login")
            login_button.click()

            # Wait for navigation
            logger.info("[IXLogin] Waiting for login to complete...")
            time.sleep(5)

            # Check if login successful
            is_logged_in, _ = self.check_login_status()

            if is_logged_in:
                logger.info("[IXLogin] ✓ Login successful!")
                return True
            else:
                logger.error("[IXLogin] ✗ Login failed!")
                return False

        except Exception as e:
            logger.error("[IXLogin] Login error: %s", str(e))
            return False

    def ensure_correct_user_logged_in(self) -> bool:
        """
        Ensure correct user is logged in.
        - If correct user already logged in → do nothing
        - If wrong user logged in → logout and login
        - If no user logged in → login

        Returns:
            True if correct user is logged in at the end
        """
        logger.info("[IXLogin] Ensuring correct user is logged in...")

        # Navigate to Facebook first
        if not self.navigate_to_facebook():
            logger.error("[IXLogin] Failed to navigate to Facebook!")
            return False

        # Check current status
        is_logged_in, current_email = self.check_login_status()

        # Case 1: Correct user already logged in
        if is_logged_in and current_email and current_email.lower() == self.expected_email.lower():
            logger.info("[IXLogin] ✓ Correct user already logged in - no action needed")
            return True

        # Case 2: Wrong user logged in - need to logout first
        if is_logged_in and current_email and current_email.lower() != self.expected_email.lower():
            logger.info("[IXLogin] Wrong user logged in - logging out...")
            if not self.logout():
                logger.error("[IXLogin] Failed to logout wrong user!")
                return False

            # Wait after logout
            time.sleep(2)

        # Case 3: No user logged in (or after logout) - need to login
        logger.info("[IXLogin] Logging in with correct credentials...")
        if not self.login():
            logger.error("[IXLogin] Failed to login!")
            return False

        # Final verification
        if self.verify_correct_user_logged_in():
            logger.info("[IXLogin] ✓ Correct user is now logged in!")
            return True
        else:
            logger.error("[IXLogin] ✗ Failed to ensure correct user logged in!")
            return False


if __name__ == "__main__":
    # Test mode
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print("\n" + "="*60)
    print("Testing ixBrowser Login Manager")
    print("="*60 + "\n")

    print("Note: This requires browser to be launched first")
    print("Run browser_launcher.py test mode first")
