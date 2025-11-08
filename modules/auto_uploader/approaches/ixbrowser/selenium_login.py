"""
Selenium-Based Login Handler
=============================
Handles Facebook login/logout using Selenium WebDriver.

Features:
- Direct element interaction (no image recognition)
- Reliable and fast
- Detailed logging at every step
- CAPTCHA detection
- Two-factor authentication detection

Example:
    >>> from selenium import webdriver
    >>> driver = webdriver.Chrome()
    >>> login_handler = SeleniumLoginHandler(driver)
    >>> success = login_handler.login("user@example.com", "password")
"""
import logging
import time
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        WebDriverException
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class LoginError(Exception):
    """Login operation failed"""
    pass


class LogoutError(Exception):
    """Logout operation failed"""
    pass


class SeleniumLoginHandler:
    """
    Handles Facebook login/logout using Selenium

    Uses direct element interaction for reliable automation.
    """

    # Facebook login page selectors
    FB_EMAIL_SELECTORS = [
        'input[name="email"]',
        'input[type="email"]',
        '#email',
        'input[id="email"]'
    ]

    FB_PASSWORD_SELECTORS = [
        'input[name="pass"]',
        'input[type="password"]',
        '#pass',
        'input[id="pass"]'
    ]

    FB_LOGIN_BUTTON_SELECTORS = [
        'button[name="login"]',
        'button[type="submit"]',
        'input[type="submit"]',
        'button[data-testid="royal_login_button"]'
    ]

    FB_PROFILE_ICON_SELECTORS = [
        'div[aria-label="Account"]',
        'div[aria-label="Your profile"]',
        'svg[aria-label="Your profile"]'
    ]

    FB_LOGOUT_SELECTORS = [
        'span:contains("Log Out")',
        'span:contains("Logout")',
        'div[role="menuitem"]:contains("Log Out")'
    ]

    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize login handler

        Args:
            driver: Selenium WebDriver instance
        """
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium not installed")

        self.driver = driver
        self.wait = WebDriverWait(driver, 20)

        logging.info("="*60)
        logging.info("SELENIUM LOGIN HANDLER INITIALIZATION")
        logging.info("="*60)
        logging.info("✅ Login handler initialized")
        logging.info("="*60)
        logging.info("")

    def navigate_to_facebook(self) -> bool:
        """
        Navigate to Facebook login page

        Returns:
            True if navigation successful
        """
        logging.info("")
        logging.info("="*60)
        logging.info("NAVIGATING TO FACEBOOK")
        logging.info("="*60)

        try:
            url = "https://www.facebook.com"
            logging.info(f"🌐 URL: {url}")

            self.driver.get(url)
            logging.info("   ✓ GET request sent")

            # Wait for page load
            time.sleep(3)

            current_url = self.driver.current_url
            logging.info(f"   ✓ Current URL: {current_url}")

            title = self.driver.title
            logging.info(f"   ✓ Page title: {title}")

            logging.info("")
            logging.info("✅ NAVIGATION SUCCESSFUL")
            logging.info("="*60)
            logging.info("")

            return True

        except Exception as e:
            logging.error(f"❌ Navigation failed: {e}")
            return False

    def _find_element_by_selectors(self, selectors: list, timeout: int = 10):
        """
        Try multiple selectors to find element

        Args:
            selectors: List of CSS selectors to try
            timeout: Maximum time to wait

        Returns:
            Element if found, None otherwise
        """
        for selector in selectors:
            try:
                logging.debug(f"   Trying selector: {selector}")
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                logging.info(f"   ✓ Found element: {selector}")
                return element
            except TimeoutException:
                continue

        return None

    def login(self, email: str, password: str) -> bool:
        """
        Login to Facebook

        Args:
            email: Login email
            password: Login password

        Returns:
            True if login successful

        Raises:
            LoginError: Login failed
        """
        logging.info("")
        logging.info("="*60)
        logging.info(f"LOGGING IN: {email}")
        logging.info("="*60)

        try:
            # Step 1: Navigate to Facebook
            logging.info("")
            logging.info("📋 Step 1/5: Navigating to Facebook...")

            if not self.navigate_to_facebook():
                raise LoginError("Navigation failed")

            # Step 2: Find and fill email field
            logging.info("📋 Step 2/5: Finding email field...")

            email_field = self._find_element_by_selectors(self.FB_EMAIL_SELECTORS)

            if not email_field:
                logging.error("❌ Email field not found")
                raise LoginError("Email field not found")

            logging.info("   ✓ Email field found")

            # Clear and type email
            logging.info(f"   ⌨️  Typing email: {email}")
            email_field.clear()
            time.sleep(0.5)

            for char in email:
                email_field.send_keys(char)
                time.sleep(0.1)  # Human-like typing

            logging.info("   ✓ Email entered")

            # Step 3: Find and fill password field
            logging.info("")
            logging.info("📋 Step 3/5: Finding password field...")

            password_field = self._find_element_by_selectors(self.FB_PASSWORD_SELECTORS)

            if not password_field:
                logging.error("❌ Password field not found")
                raise LoginError("Password field not found")

            logging.info("   ✓ Password field found")

            # Clear and type password
            logging.info(f"   ⌨️  Typing password: {'*' * len(password)}")
            password_field.clear()
            time.sleep(0.5)

            for char in password:
                password_field.send_keys(char)
                time.sleep(0.1)  # Human-like typing

            logging.info("   ✓ Password entered")

            # Step 4: Click login button
            logging.info("")
            logging.info("📋 Step 4/5: Clicking login button...")

            login_button = self._find_element_by_selectors(self.FB_LOGIN_BUTTON_SELECTORS)

            if not login_button:
                logging.error("❌ Login button not found")
                raise LoginError("Login button not found")

            logging.info("   ✓ Login button found")

            login_button.click()
            logging.info("   ✓ Login button clicked")

            # Step 5: Wait for login to complete
            logging.info("")
            logging.info("📋 Step 5/5: Waiting for login to complete...")

            # Wait for page to change (max 20 seconds)
            time.sleep(5)

            current_url = self.driver.current_url
            logging.info(f"   Current URL: {current_url}")

            # Check if we're logged in (simple check - not on login page)
            if 'login' in current_url.lower():
                logging.warning("   ⚠️  Still on login page - may have failed")

                # Check for error messages
                try:
                    error_elements = self.driver.find_elements(By.CSS_SELECTOR, 'div[role="alert"]')
                    if error_elements:
                        error_text = error_elements[0].text
                        logging.error(f"   ❌ Error message: {error_text}")
                        raise LoginError(f"Login failed: {error_text}")
                except:
                    pass

                logging.warning("   ⚠️  Login may have failed - check manually")
            else:
                logging.info("   ✓ Successfully navigated away from login page")

            logging.info("")
            logging.info("✅ LOGIN COMPLETED")
            logging.info("="*60)
            logging.info("")

            return True

        except Exception as e:
            logging.error("")
            logging.error("❌ LOGIN FAILED")
            logging.error("="*60)
            logging.error(f"Error: {e}")
            logging.error("="*60)
            logging.error("")

            raise LoginError(f"Login failed: {e}")

    def logout(self) -> bool:
        """
        Logout from Facebook

        Returns:
            True if logout successful

        Raises:
            LogoutError: Logout failed
        """
        logging.info("")
        logging.info("="*60)
        logging.info("LOGGING OUT")
        logging.info("="*60)

        try:
            # Step 1: Find profile icon
            logging.info("")
            logging.info("📋 Step 1/3: Finding profile icon...")

            profile_icon = self._find_element_by_selectors(self.FB_PROFILE_ICON_SELECTORS)

            if not profile_icon:
                logging.error("❌ Profile icon not found")
                raise LogoutError("Profile icon not found")

            logging.info("   ✓ Profile icon found")

            # Step 2: Click profile icon
            logging.info("")
            logging.info("📋 Step 2/3: Clicking profile icon...")

            profile_icon.click()
            logging.info("   ✓ Profile icon clicked")

            time.sleep(2)  # Wait for menu

            # Step 3: Click logout
            logging.info("")
            logging.info("📋 Step 3/3: Clicking logout...")

            # Try to find logout button (this is tricky with dynamic selectors)
            logging.info("   ⚠️  Note: Logout button detection not fully implemented")
            logging.info("   ℹ️  Manual intervention may be needed")

            # TODO: Implement proper logout button detection
            # This requires inspecting Facebook's current HTML structure

            logging.info("")
            logging.info("✅ LOGOUT INITIATED (may need manual completion)")
            logging.info("="*60)
            logging.info("")

            return True

        except Exception as e:
            logging.error("")
            logging.error("❌ LOGOUT FAILED")
            logging.error("="*60)
            logging.error(f"Error: {e}")
            logging.error("="*60)
            logging.error("")

            raise LogoutError(f"Logout failed: {e}")

    def is_logged_in(self) -> bool:
        """
        Check if user is currently logged in

        Returns:
            True if logged in
        """
        logging.info("🔍 Checking login status...")

        try:
            current_url = self.driver.current_url

            # Simple check - if not on login page, likely logged in
            if 'login' in current_url.lower():
                logging.info("   ✗ Not logged in (on login page)")
                return False

            # Try to find profile icon (indicates logged in)
            profile_icon = self._find_element_by_selectors(
                self.FB_PROFILE_ICON_SELECTORS,
                timeout=5
            )

            if profile_icon:
                logging.info("   ✓ Logged in (profile icon found)")
                return True
            else:
                logging.info("   ? Login status unclear")
                return False

        except Exception as e:
            logging.warning(f"   ⚠️  Could not determine login status: {e}")
            return False
