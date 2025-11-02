"""
Session Validator
=================
Validates Facebook session status and cookie validity.

Integrates with browser/screen_detector.py for intelligent session validation.
"""

import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import TimeoutException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from ..browser.screen_detector import ScreenDetector
from ..browser.mouse_controller import MouseController


class SessionValidator:
    """Validates Facebook session status using intelligent detection."""

    # Essential Facebook cookies
    ESSENTIAL_COOKIES = ['c_user', 'xs', 'datr']

    def __init__(self, driver: Optional[Any] = None, config: Optional[Dict] = None):
        """
        Initialize session validator.

        Args:
            driver: Selenium WebDriver instance
            config: Configuration dictionary
        """
        self.driver = driver
        self.config = config or {}
        self.screen_detector = ScreenDetector()
        self.mouse = MouseController()

        self.last_validation_time = None
        self.session_valid = False

        logging.debug("SessionValidator initialized")

    def is_logged_in(self) -> bool:
        """
        Check if user is logged into Facebook.

        Uses image recognition for accurate detection.

        Returns:
            True if logged in

        Example:
            >>> validator = SessionValidator(driver)
            >>> if not validator.is_logged_in():
            >>>     # Need to login
            >>>     login_handler.login_with_credentials(email, password)
        """
        logging.debug("Checking if logged in...")

        try:
            # Primary method: Image recognition
            user_status = self.screen_detector.detect_user_status()

            if user_status['logged_in']:
                logging.info("✓ User is logged in (confidence: %.2f)", user_status.get('confidence', 0))
                return True

            # Secondary method: Check URL and cookies
            if self.driver:
                current_url = self.driver.current_url

                # If on login page, definitely not logged in
                if 'login' in current_url.lower():
                    logging.info("✗ User not logged in (on login page)")
                    return False

                # Check for essential cookies
                has_cookies = self._check_essential_cookies()
                if has_cookies:
                    logging.info("✓ User appears logged in (has cookies)")
                    return True

            logging.info("✗ User not logged in")
            return False

        except Exception as e:
            logging.error("Error checking login status: %s", e, exc_info=True)
            return False

    def validate_cookies(self) -> bool:
        """
        Validate Facebook cookies.

        Returns:
            True if cookies are valid

        Example:
            >>> validator = SessionValidator(driver)
            >>> if not validator.validate_cookies():
            >>>     print("Cookies invalid, need to re-login")
        """
        logging.debug("Validating cookies...")

        if not self.driver:
            logging.error("No WebDriver available")
            return False

        try:
            cookies = self.driver.get_cookies()

            # Check for essential cookies
            cookie_names = [c['name'] for c in cookies]

            missing_cookies = []
            for essential in self.ESSENTIAL_COOKIES:
                if essential not in cookie_names:
                    missing_cookies.append(essential)

            if missing_cookies:
                logging.warning("✗ Missing essential cookies: %s", missing_cookies)
                return False

            # Check cookie expiry
            now = datetime.now().timestamp()
            expired_cookies = []

            for cookie in cookies:
                if 'expiry' in cookie:
                    if cookie['expiry'] < now:
                        expired_cookies.append(cookie['name'])

            if expired_cookies:
                logging.warning("✗ Expired cookies: %s", expired_cookies)
                return False

            logging.info("✓ Cookies are valid")
            return True

        except Exception as e:
            logging.error("Error validating cookies: %s", e, exc_info=True)
            return False

    def check_session_expiry(self) -> Optional[datetime]:
        """
        Check session expiry time based on cookie expiry.

        Returns:
            Expiry datetime or None

        Example:
            >>> expiry = validator.check_session_expiry()
            >>> if expiry:
            >>>     print(f"Session expires at: {expiry}")
        """
        logging.debug("Checking session expiry...")

        if not self.driver:
            return None

        try:
            cookies = self.driver.get_cookies()

            # Find the cookie with earliest expiry (that's our session limit)
            earliest_expiry = None

            for cookie in cookies:
                if cookie['name'] in self.ESSENTIAL_COOKIES and 'expiry' in cookie:
                    expiry_timestamp = cookie['expiry']
                    expiry_dt = datetime.fromtimestamp(expiry_timestamp)

                    if earliest_expiry is None or expiry_dt < earliest_expiry:
                        earliest_expiry = expiry_dt

            if earliest_expiry:
                logging.info("Session expires at: %s", earliest_expiry.isoformat())
            else:
                logging.debug("No expiry information found")

            return earliest_expiry

        except Exception as e:
            logging.error("Error checking expiry: %s", e, exc_info=True)
            return None

    def refresh_session(self) -> bool:
        """
        Refresh session by navigating to Facebook homepage.

        Returns:
            True if refreshed successfully

        Example:
            >>> validator = SessionValidator(driver)
            >>> if validator.is_session_expired():
            >>>     validator.refresh_session()
        """
        logging.info("Refreshing session...")

        if not self.driver:
            logging.error("No WebDriver available")
            return False

        try:
            # Navigate to Facebook homepage to refresh cookies
            self.driver.get('https://www.facebook.com')

            # Show circular animation while waiting
            self.mouse.circular_idle_movement(duration=2.0, radius=35)

            time.sleep(3)

            # Verify still logged in
            if self.is_logged_in():
                logging.info("✓ Session refreshed successfully")
                return True
            else:
                logging.warning("✗ Session refresh failed - user not logged in")
                return False

        except Exception as e:
            logging.error("Error refreshing session: %s", e, exc_info=True)
            return False

    def is_session_expired(self) -> bool:
        """
        Check if session has expired.

        Returns:
            True if expired

        Example:
            >>> if validator.is_session_expired():
            >>>     print("Session expired, need to re-login")
        """
        logging.debug("Checking if session expired...")

        try:
            # Check if logged in
            if not self.is_logged_in():
                logging.info("Session expired (not logged in)")
                return True

            # Check cookie expiry
            expiry = self.check_session_expiry()
            if expiry:
                now = datetime.now()
                if now >= expiry:
                    logging.info("Session expired (cookies expired)")
                    return True

            logging.debug("Session not expired")
            return False

        except Exception as e:
            logging.error("Error checking if expired: %s", e, exc_info=True)
            return True  # Assume expired on error

    def get_session_age(self) -> Optional[timedelta]:
        """
        Get approximate session age based on cookie creation.

        Returns:
            Timedelta representing session age or None

        Example:
            >>> age = validator.get_session_age()
            >>> if age:
            >>>     print(f"Session is {age.total_seconds() / 3600:.1f} hours old")
        """
        logging.debug("Getting session age...")

        if not self.driver:
            return None

        try:
            cookies = self.driver.get_cookies()

            # Find datr cookie (created when browser first visits Facebook)
            for cookie in cookies:
                if cookie['name'] == 'datr':
                    # Estimate age based on expiry (datr typically expires in 2 years)
                    if 'expiry' in cookie:
                        expiry_timestamp = cookie['expiry']
                        expiry_dt = datetime.fromtimestamp(expiry_timestamp)

                        # Assuming 2-year validity, work backwards
                        creation_estimate = expiry_dt - timedelta(days=730)
                        age = datetime.now() - creation_estimate

                        logging.debug("Estimated session age: %s", age)
                        return age

            logging.debug("Could not determine session age")
            return None

        except Exception as e:
            logging.error("Error getting session age: %s", e, exc_info=True)
            return None

    def validate_session(self, full_check: bool = True) -> Dict[str, Any]:
        """
        Perform comprehensive session validation.

        Args:
            full_check: Perform full validation including image recognition

        Returns:
            Dictionary with validation results

        Example:
            >>> result = validator.validate_session()
            >>> if result['valid']:
            >>>     print("Session is valid")
            >>> else:
            >>>     print(f"Session invalid: {result['issues']}")
        """
        logging.info("Validating session (full_check=%s)...", full_check)

        result = {
            'valid': False,
            'logged_in': False,
            'cookies_valid': False,
            'expired': False,
            'issues': [],
            'timestamp': datetime.now().isoformat()
        }

        try:
            # Check if logged in
            logged_in = self.is_logged_in()
            result['logged_in'] = logged_in

            if not logged_in:
                result['issues'].append('Not logged in')
                return result

            # Check cookies
            cookies_valid = self.validate_cookies()
            result['cookies_valid'] = cookies_valid

            if not cookies_valid:
                result['issues'].append('Invalid cookies')

            # Check expiry
            expired = self.is_session_expired()
            result['expired'] = expired

            if expired:
                result['issues'].append('Session expired')

            # Determine overall validity
            if logged_in and cookies_valid and not expired:
                result['valid'] = True
                self.session_valid = True
                self.last_validation_time = datetime.now()
                logging.info("✓ Session is VALID")
            else:
                logging.warning("✗ Session is INVALID: %s", result['issues'])

            return result

        except Exception as e:
            logging.error("Error validating session: %s", e, exc_info=True)
            result['issues'].append(f"Validation error: {str(e)}")
            return result

    def wait_for_valid_session(self, timeout: int = 60, check_interval: int = 5) -> bool:
        """
        Wait for session to become valid.

        Args:
            timeout: Maximum time to wait
            check_interval: Time between checks

        Returns:
            True if session became valid within timeout
        """
        logging.info("Waiting for valid session (timeout: %ds)...", timeout)

        start_time = time.time()

        while time.time() - start_time < timeout:
            result = self.validate_session(full_check=True)

            if result['valid']:
                elapsed = time.time() - start_time
                logging.info("✓ Session valid after %.1fs", elapsed)
                return True

            logging.debug("Session not yet valid: %s", result['issues'])
            time.sleep(check_interval)

        logging.warning("✗ Session did not become valid within timeout")
        return False

    def _check_essential_cookies(self) -> bool:
        """
        Internal method to check for essential cookies.

        Returns:
            True if essential cookies present
        """
        if not self.driver:
            return False

        try:
            cookies = self.driver.get_cookies()
            cookie_names = [c['name'] for c in cookies]

            for essential in self.ESSENTIAL_COOKIES:
                if essential not in cookie_names:
                    return False

            return True

        except:
            return False

    def set_driver(self, driver: Any) -> None:
        """
        Set or update WebDriver instance.

        Args:
            driver: Selenium WebDriver
        """
        self.driver = driver
        logging.debug("WebDriver updated")

    def get_session_info(self) -> Dict[str, Any]:
        """
        Get detailed session information.

        Returns:
            Dictionary with session details

        Example:
            >>> info = validator.get_session_info()
            >>> print(f"Logged in: {info['logged_in']}")
            >>> print(f"Expiry: {info['expiry']}")
        """
        info = {
            'logged_in': self.is_logged_in(),
            'cookies_valid': self.validate_cookies(),
            'expired': self.is_session_expired(),
            'expiry': None,
            'age': None,
            'last_validation': self.last_validation_time.isoformat() if self.last_validation_time else None
        }

        expiry = self.check_session_expiry()
        if expiry:
            info['expiry'] = expiry.isoformat()

        age = self.get_session_age()
        if age:
            info['age'] = str(age)

        return info
