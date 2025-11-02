"""
Login Handler
=============
High-level Facebook login automation using intelligent browser module.

This wraps browser/login_manager.py with auth-specific logic.
"""

import logging
import time
from typing import Optional, Dict, Any

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("Selenium not available")

from ..browser.login_manager import LoginManager
from ..browser.mouse_controller import MouseController
from .credential_manager import CredentialManager


class LoginHandler:
    """Handles Facebook login automation using browser module."""

    def __init__(self, driver: Optional[Any] = None, config: Optional[Dict] = None):
        """
        Initialize login handler.

        Args:
            driver: Selenium WebDriver instance
            config: Configuration dictionary
        """
        self.driver = driver
        self.config = config or {}

        # Initialize components
        self.login_manager = LoginManager(driver)
        self.mouse = MouseController()
        self.credential_manager = CredentialManager()

        logging.debug("LoginHandler initialized")

    def login_with_credentials(self, email: str, password: str, timeout: int = 30) -> bool:
        """
        Login to Facebook with email and password.

        This uses the intelligent browser/login_manager for actual login.

        Args:
            email: Facebook email/username
            password: Facebook password
            timeout: Maximum time to wait for login

        Returns:
            True if login successful

        Example:
            >>> handler = LoginHandler(driver)
            >>> success = handler.login_with_credentials("user@email.com", "password123")
        """
        logging.info("Attempting login with credentials...")

        if not self.driver:
            logging.error("No WebDriver provided")
            return False

        # Use browser/login_manager for intelligent login
        success = self.login_manager.login_user(email, password, timeout=timeout)

        if success:
            logging.info("✓ Login successful")
        else:
            logging.error("✗ Login failed")

        return success

    def login_with_identifier(self, identifier: str, timeout: int = 30) -> bool:
        """
        Login using saved credentials from credential manager.

        Args:
            identifier: Credential identifier
            timeout: Maximum time to wait

        Returns:
            True if login successful

        Example:
            >>> handler = LoginHandler(driver)
            >>> handler.login_with_identifier("profile1")
        """
        logging.info("Loading credentials for: %s", identifier)

        # Load credentials
        credentials = self.credential_manager.load_credentials(identifier)

        if not credentials:
            logging.error("Credentials not found for: %s", identifier)
            return False

        email = credentials.get('email')
        password = credentials.get('password')

        if not email or not password:
            logging.error("Invalid credentials: missing email or password")
            return False

        # Login with loaded credentials
        return self.login_with_credentials(email, password, timeout=timeout)

    def is_logged_in(self) -> bool:
        """
        Check if user is currently logged in.

        Uses image recognition from browser/login_manager.

        Returns:
            True if logged in
        """
        status = self.login_manager.check_login_status()
        return status.get('logged_in', False)

    def wait_for_login(self, timeout: int = 30) -> bool:
        """
        Wait for login to complete.

        Args:
            timeout: Maximum time to wait

        Returns:
            True if login detected within timeout
        """
        return self.login_manager.wait_for_login_completion(timeout=timeout)

    def handle_checkpoint(self) -> bool:
        """
        Handle Facebook security checkpoint (if encountered).

        Returns:
            True if checkpoint handled successfully
        """
        logging.info("Checking for security checkpoint...")

        if not self.driver:
            return False

        try:
            # Check for checkpoint page
            current_url = self.driver.current_url

            if 'checkpoint' in current_url.lower():
                logging.warning("⚠ Security checkpoint detected!")
                logging.info("Manual intervention may be required")

                # Show circular animation to indicate waiting
                self.mouse.circular_idle_movement(duration=5.0, radius=50)

                return False

            logging.debug("No checkpoint detected")
            return True

        except Exception as e:
            logging.error("Error checking for checkpoint: %s", e)
            return False

    def navigate_to_login_page(self, url: str = "https://www.facebook.com") -> bool:
        """
        Navigate to Facebook login page.

        Args:
            url: Facebook URL to navigate to

        Returns:
            True if navigation successful
        """
        return self.login_manager.navigate_to_facebook(url)

    def set_driver(self, driver: Any) -> None:
        """
        Set or update WebDriver instance.

        Args:
            driver: Selenium WebDriver
        """
        self.driver = driver
        self.login_manager.set_driver(driver)
        logging.debug("WebDriver updated")

    def save_session_credentials(self, identifier: str, email: str, password: str, **extra_data) -> bool:
        """
        Save credentials for future use.

        Args:
            identifier: Unique identifier for this account
            email: Facebook email
            password: Facebook password
            **extra_data: Additional data (page_id, etc.)

        Returns:
            True if saved successfully
        """
        credentials = {
            'email': email,
            'password': password,
            **extra_data
        }

        return self.credential_manager.save_credentials(identifier, credentials)
