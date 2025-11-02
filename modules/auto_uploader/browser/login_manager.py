"""
Login Manager
=============
Handles intelligent login and logout operations with autofill detection.

This module provides:
- Intelligent logout: hover → detect dropdown → click logout → handle popup
- Intelligent login: detect autofill → clear → type credentials → login
- Autofill data clearing
- Browser close popup handling
"""

import logging
import time
from typing import Optional, Dict, Any

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("Selenium not available. Login manager may not work correctly.")

from .screen_detector import ScreenDetector
from .mouse_controller import MouseController


class LoginManager:
    """Manages intelligent login and logout operations."""

    # Facebook login selectors
    FB_EMAIL_SELECTOR = 'input[name="email"]'
    FB_PASSWORD_SELECTOR = 'input[name="pass"]'
    FB_LOGIN_BUTTON_SELECTOR = 'button[name="login"]'
    FB_PROFILE_ICON_SELECTOR = 'div[aria-label="Account"]'

    def __init__(self, driver: Optional[Any] = None):
        """
        Initialize login manager.

        Args:
            driver: Selenium WebDriver instance (optional)
        """
        self.driver = driver
        self.screen_detector = ScreenDetector()
        self.mouse = MouseController()

        logging.debug("LoginManager initialized")

    def logout_current_user(self, timeout: int = 30) -> bool:
        """
        Logout current user using intelligent detection.

        Process:
        1. Detect if user is logged in (image recognition)
        2. Hover over profile icon
        3. Detect logout dropdown (image recognition)
        4. Click logout option
        5. Handle "Safe and Exit" popup if appears

        Args:
            timeout: Maximum time to wait for logout completion

        Returns:
            True if logout successful, False otherwise

        Example:
            >>> login_mgr = LoginManager(driver)
            >>> if login_mgr.logout_current_user():
            >>>     print("Logged out successfully")
        """
        logging.info("Starting intelligent logout process...")

        try:
            # Step 1: Check if user is logged in
            user_status = self.screen_detector.detect_user_status()
            if not user_status['logged_in']:
                logging.info("User is not logged in, no logout needed")
                return True

            logging.info("User is logged in, proceeding with logout...")

            # Step 2: Find and hover over profile icon
            logging.info("Searching for profile icon...")
            if self.driver:
                try:
                    profile_icon = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, self.FB_PROFILE_ICON_SELECTOR))
                    )

                    # Get position and hover
                    location = profile_icon.location
                    size = profile_icon.size
                    center_x = location['x'] + size['width'] // 2
                    center_y = location['y'] + size['height'] // 2

                    logging.info("Hovering over profile icon at (%d, %d)", center_x, center_y)
                    self.mouse.hover_over_position(center_x, center_y, hover_duration=2.0)

                except TimeoutException:
                    logging.warning("Profile icon not found using Selenium, trying alternative method")

            # Wait for dropdown to appear
            time.sleep(1.5)

            # Step 3: Detect logout dropdown using image recognition
            logging.info("Detecting logout dropdown...")
            dropdown_result = self.screen_detector.wait_for_element(
                'user_status_dropdown.png',
                timeout=5
            )

            if not dropdown_result['found']:
                logging.error("Logout dropdown not detected after hovering")
                return False

            # Step 4: Click on logout option in dropdown
            logging.info("Clicking logout option...")
            logout_x, logout_y = dropdown_result['position']

            # Add offset to click the actual logout button (usually below the profile info)
            logout_y += 50  # Adjust based on dropdown layout

            self.mouse.click_at_position(logout_x, logout_y)

            # Wait for logout to process
            time.sleep(2)

            # Step 5: Handle "Safe and Exit" popup if it appears
            logging.info("Checking for browser close popup...")
            popup_result = self.screen_detector.detect_browser_close_popup()

            if popup_result['found']:
                logging.info("Browser close popup detected, clicking 'Safe and Exit'")
                self.handle_browser_close_popup()

            # Wait for logout to complete
            time.sleep(2)

            # Verify logout by checking user status again
            verification = self.screen_detector.detect_user_status()
            if not verification['logged_in']:
                logging.info("Logout SUCCESSFUL!")
                return True
            else:
                logging.warning("Logout may have failed, user still appears logged in")
                return False

        except Exception as e:
            logging.error("Error during logout: %s", e, exc_info=True)
            return False

    def login_user(self, email: str, password: str, timeout: int = 30) -> bool:
        """
        Login user with intelligent autofill detection and clearing.

        Process:
        1. Navigate to Facebook login page
        2. Detect autofilled data in email/password fields
        3. Clear autofill data (Ctrl+A, Delete)
        4. Type credentials with human-like timing
        5. Click login button
        6. Wait for login to complete

        Args:
            email: Facebook email/username
            password: Facebook password
            timeout: Maximum time to wait for login

        Returns:
            True if login successful, False otherwise

        Example:
            >>> login_mgr = LoginManager(driver)
            >>> login_mgr.login_user("user@email.com", "password123")
        """
        logging.info("Starting intelligent login process...")

        try:
            # Check if already logged in
            user_status = self.screen_detector.detect_user_status()
            if user_status['logged_in']:
                logging.info("User is already logged in")
                return True

            if not self.driver:
                logging.error("Selenium driver not available for login")
                return False

            # Navigate to Facebook login if not already there
            current_url = self.driver.current_url
            if 'facebook.com' not in current_url.lower():
                logging.info("Navigating to Facebook...")
                self.driver.get('https://www.facebook.com')
                time.sleep(3)

            # Find email field
            logging.info("Locating email field...")
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.FB_EMAIL_SELECTOR))
            )

            # Find password field
            logging.info("Locating password field...")
            password_field = self.driver.find_element(By.CSS_SELECTOR, self.FB_PASSWORD_SELECTOR)

            # Clear autofill data in email field
            logging.info("Clearing autofilled email data...")
            self.clear_autofill_data(email_field)

            # Type email with human-like timing
            logging.info("Typing email...")
            self.mouse.circular_idle_movement(duration=1.0, radius=30)  # Show activity
            email_field.click()
            time.sleep(0.3)
            self.mouse.type_text(email, interval=None)  # Random intervals

            # Small delay between fields
            time.sleep(0.5)

            # Clear autofill data in password field
            logging.info("Clearing autofilled password data...")
            self.clear_autofill_data(password_field)

            # Type password with human-like timing
            logging.info("Typing password...")
            password_field.click()
            time.sleep(0.3)
            self.mouse.type_text(password, interval=None)

            # Small delay before clicking login
            time.sleep(1.0)

            # Find and click login button
            logging.info("Clicking login button...")
            login_button = self.driver.find_element(By.CSS_SELECTOR, self.FB_LOGIN_BUTTON_SELECTOR)

            # Get button position
            location = login_button.location
            size = login_button.size
            button_x = location['x'] + size['width'] // 2
            button_y = location['y'] + size['height'] // 2

            # Click login button with mouse controller
            self.mouse.click_at_position(button_x, button_y)

            # Wait for login to complete
            logging.info("Waiting for login to complete...")
            time.sleep(5)

            # Show circular animation while waiting
            self.mouse.circular_idle_movement(duration=3.0, radius=40)

            # Verify login
            verification = self.screen_detector.detect_user_status()
            if verification['logged_in']:
                logging.info("Login SUCCESSFUL!")
                return True
            else:
                logging.warning("Login may have failed, user not detected as logged in")
                return False

        except TimeoutException:
            logging.error("Timeout waiting for login page elements")
            return False

        except Exception as e:
            logging.error("Error during login: %s", e, exc_info=True)
            return False

    def clear_autofill_data(self, element: Any) -> bool:
        """
        Clear autofilled data from input field.

        Uses Ctrl+A to select all, then Delete to clear.

        Args:
            element: Selenium WebElement to clear

        Returns:
            True if cleared successfully
        """
        logging.debug("Clearing autofill data from element...")

        try:
            # Click element to focus
            element.click()
            time.sleep(0.2)

            # Select all text
            self.mouse.hotkey('ctrl', 'a')
            time.sleep(0.1)

            # Delete selected text
            self.mouse.press_key('delete')
            time.sleep(0.2)

            # Verify field is empty
            current_value = element.get_attribute('value')
            if not current_value or current_value.strip() == '':
                logging.debug("Autofill data cleared successfully")
                return True
            else:
                logging.warning("Field may still contain data: '%s'", current_value)
                # Try again with backspace
                element.clear()
                return True

        except Exception as e:
            logging.error("Error clearing autofill data: %s", e, exc_info=True)
            return False

    def handle_browser_close_popup(self) -> bool:
        """
        Handle "Safe and Exit" browser close popup.

        Detects the popup using image recognition and clicks the appropriate button.

        Returns:
            True if popup handled successfully
        """
        logging.info("Handling browser close popup...")

        try:
            # Detect popup
            popup_result = self.screen_detector.detect_browser_close_popup()

            if not popup_result['found']:
                logging.debug("Browser close popup not found")
                return False

            # Get popup position
            popup_x, popup_y = popup_result['position']

            # Click "Safe and Exit" button (usually at the popup position or slightly below)
            # Adjust offset based on actual popup layout
            button_x = popup_x
            button_y = popup_y + 20  # Adjust if button is below the detected position

            logging.info("Clicking 'Safe and Exit' button at (%d, %d)", button_x, button_y)
            self.mouse.click_at_position(button_x, button_y)

            time.sleep(1)

            logging.info("Browser close popup handled")
            return True

        except Exception as e:
            logging.error("Error handling browser close popup: %s", e, exc_info=True)
            return False

    def check_login_status(self) -> Dict[str, Any]:
        """
        Check current login status.

        Returns:
            Dictionary with login status information
        """
        logging.info("Checking login status...")

        result = self.screen_detector.detect_user_status()

        status = {
            'logged_in': result['logged_in'],
            'confidence': result.get('confidence', 0.0),
            'timestamp': time.time()
        }

        logging.info("Login status: %s", "LOGGED IN" if status['logged_in'] else "LOGGED OUT")

        return status

    def wait_for_login_completion(self, timeout: int = 30) -> bool:
        """
        Wait for login process to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if login completed successfully
        """
        logging.info("Waiting for login completion (timeout: %ds)", timeout)

        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.check_login_status()

            if status['logged_in']:
                elapsed = time.time() - start_time
                logging.info("Login completed after %.1fs", elapsed)
                return True

            # Show circular animation while waiting
            self.mouse.circular_idle_movement(duration=2.0, radius=30)
            time.sleep(1)

        logging.warning("Login did not complete within timeout")
        return False

    def navigate_to_facebook(self, url: str = 'https://www.facebook.com') -> bool:
        """
        Navigate to Facebook URL.

        Args:
            url: Facebook URL to navigate to

        Returns:
            True if navigation successful
        """
        if not self.driver:
            logging.error("Selenium driver not available")
            return False

        try:
            logging.info("Navigating to: %s", url)
            self.driver.get(url)
            time.sleep(3)

            logging.info("Navigation successful")
            return True

        except Exception as e:
            logging.error("Error navigating to Facebook: %s", e, exc_info=True)
            return False

    def is_on_login_page(self) -> bool:
        """
        Check if currently on Facebook login page.

        Returns:
            True if on login page
        """
        if not self.driver:
            return False

        try:
            current_url = self.driver.current_url
            title = self.driver.title

            # Check if we're on login page
            on_login = ('login' in current_url.lower() or
                       'login' in title.lower() or
                       'facebook' in current_url.lower())

            logging.debug("On login page: %s", on_login)
            return on_login

        except Exception as e:
            logging.error("Error checking if on login page: %s", e)
            return False

    def set_driver(self, driver: Any) -> None:
        """
        Set or update the Selenium WebDriver instance.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        logging.debug("WebDriver instance updated")
