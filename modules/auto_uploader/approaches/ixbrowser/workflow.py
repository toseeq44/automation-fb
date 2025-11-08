"""
IX Browser Workflow
===================
API-based browser automation with IX Browser Cloud API.

This approach uses:
- IX Browser Cloud API for profile management
- Selenium WebDriver for browser automation
- Direct element interaction (no image recognition)
- Faster and more reliable than desktop approach

Features:
- Remote profile opening via API
- Selenium-based login/logout
- No desktop shortcuts needed
- Team collaboration support (with Cloud API)

Example:
    >>> config = ApproachConfig(
    ...     mode='ixbrowser',
    ...     credentials={
    ...         'api_key': 'your-api-key',
    ...         'email': 'user@example.com',
    ...         'password': 'xxx',
    ...         'profile_name': 'MyProfile1'
    ...     },
    ...     browser_type='ix'
    ... )
    >>> approach = IXBrowserApproach(config)
    >>> result = approach.execute_workflow(work_item)
"""
import logging
import time
from pathlib import Path
from typing import Dict, Optional

from ..base_approach import BaseApproach, ApproachConfig

# Import ixbrowser-specific components
from .api_client import IXAPIClient
from .auth_manager import IXAuthManager
from .selenium_connector import SeleniumConnector
from .selenium_login import SeleniumLoginHandler


class IXBrowserApproach(BaseApproach):
    """
    IX Browser Approach Implementation

    Uses IX Browser Cloud API and Selenium for reliable
    browser automation without image recognition.
    """

    def __init__(self, config: ApproachConfig):
        """Initialize IX Browser approach"""
        super().__init__(config)

        # Components (initialized in initialize())
        self.api_client: Optional[IXAPIClient] = None
        self.auth_manager: Optional[IXAuthManager] = None
        self.selenium_connector: Optional[SeleniumConnector] = None
        self.login_handler: Optional[SeleniumLoginHandler] = None

        # State
        self.driver = None  # Selenium WebDriver
        self.current_profile_id: Optional[str] = None
        self.current_account: Optional[str] = None
        self.debugging_address: Optional[str] = None

        logging.info("✓ IXBrowserApproach instance created")

    def initialize(self) -> bool:
        """
        Initialize all components

        Returns:
            True if all components initialized successfully
        """
        logging.info("")
        logging.info("="*60)
        logging.info("INITIALIZING IX BROWSER APPROACH")
        logging.info("="*60)

        try:
            # Step 1: Initialize Auth Manager
            logging.info("")
            logging.info("🔧 Step 1/4: Initializing Auth Manager...")

            # Import here to avoid circular dependency
            from ...config.settings_manager import SettingsManager
            from ...auth.credential_manager import CredentialManager

            settings = SettingsManager()
            credentials = CredentialManager()

            self.auth_manager = IXAuthManager(settings, credentials)
            logging.info("   ✓ Auth Manager ready")

            # Step 2: Validate credentials
            logging.info("")
            logging.info("🔧 Step 2/4: Validating credentials...")

            if not self.auth_manager.validate_credentials():
                logging.error("❌ Credential validation failed")
                return False

            logging.info("   ✓ Credentials valid")

            # Step 3: Initialize API Client
            logging.info("")
            logging.info("🔧 Step 3/4: Initializing API Client...")

            creds = self.auth_manager.get_api_credentials()
            api_key = creds.get('api_key')

            self.api_client = IXAPIClient(api_key=api_key)
            logging.info("   ✓ API Client ready")

            # Step 4: Initialize Selenium Connector
            logging.info("")
            logging.info("🔧 Step 4/4: Initializing Selenium Connector...")

            self.selenium_connector = SeleniumConnector()
            logging.info("   ✓ Selenium Connector ready")

            logging.info("")
            logging.info("✅ ALL COMPONENTS INITIALIZED SUCCESSFULLY")
            logging.info("="*60)
            logging.info("")

            return True

        except Exception as e:
            logging.error(f"❌ Initialization failed: {e}", exc_info=True)
            return False

    def open_browser(self, account_name: str) -> bool:
        """
        Open browser profile via API

        Args:
            account_name: Account folder name

        Returns:
            True if browser opened successfully
        """
        logging.info("")
        logging.info("="*60)
        logging.info(f"OPENING IX BROWSER PROFILE (Account: {account_name})")
        logging.info("="*60)

        try:
            self.current_account = account_name

            # Step 1: Get profile name from credentials
            logging.info("")
            logging.info("📋 Step 1/4: Loading profile name...")

            creds = self.auth_manager.get_api_credentials()
            profile_name = creds.get('profile_name')

            if not profile_name:
                logging.error("❌ Profile name not configured")
                return False

            logging.info(f"   Profile Name: {profile_name}")

            # Step 2: Find profile via API
            logging.info("")
            logging.info("📋 Step 2/4: Finding profile via API...")

            profile = self.api_client.find_profile_by_name(profile_name)

            if not profile:
                logging.error(f"❌ Profile '{profile_name}' not found")
                return False

            profile_id = profile['profile_id']
            self.current_profile_id = profile_id

            logging.info(f"   ✓ Profile found: {profile_id}")

            # Step 3: Open profile via API
            logging.info("")
            logging.info("📋 Step 3/4: Opening profile via API...")

            result = self.api_client.open_profile(profile_id)

            if not result:
                logging.error("❌ Failed to open profile via API")
                return False

            self.debugging_address = result.get('debugging_address')
            webdriver_endpoint = result.get('webdriver')

            logging.info(f"   ✓ Profile opened")
            logging.info(f"   Debug Address: {self.debugging_address}")

            # Step 4: Connect Selenium to browser
            logging.info("")
            logging.info("📋 Step 4/4: Connecting Selenium to browser...")

            if not self.debugging_address:
                logging.error("❌ No debugging address returned from API")
                return False

            self.driver = self.selenium_connector.connect(self.debugging_address)

            if not self.driver:
                logging.error("❌ Failed to connect Selenium")
                return False

            # Initialize login handler
            self.login_handler = SeleniumLoginHandler(self.driver)

            logging.info("")
            logging.info("✅ IX BROWSER PROFILE OPENED SUCCESSFULLY")
            logging.info("="*60)
            logging.info("")

            return True

        except Exception as e:
            logging.error(f"❌ Error opening browser: {e}", exc_info=True)
            return False

    def login(self, email: str, password: str) -> bool:
        """
        Login to Facebook using Selenium

        Args:
            email: Login email
            password: Login password

        Returns:
            True if login successful
        """
        logging.info("")
        logging.info("="*60)
        logging.info(f"LOGGING IN WITH SELENIUM: {email}")
        logging.info("="*60)

        try:
            if not self.login_handler:
                logging.error("❌ Login handler not initialized")
                return False

            if not self.driver:
                logging.error("❌ Selenium driver not connected")
                return False

            # Use Selenium-based login
            result = self.login_handler.login(email, password)

            if result:
                logging.info("")
                logging.info("✅ LOGIN SUCCESSFUL")
                logging.info("="*60)
                logging.info("")
                return True
            else:
                logging.error("")
                logging.error("❌ LOGIN FAILED")
                logging.info("="*60)
                logging.info("")
                return False

        except Exception as e:
            logging.error(f"❌ Login error: {e}", exc_info=True)
            return False

    def logout(self) -> bool:
        """
        Logout from Facebook using Selenium

        Returns:
            True if logout successful
        """
        logging.info("")
        logging.info("="*60)
        logging.info("LOGGING OUT WITH SELENIUM")
        logging.info("="*60)

        try:
            if not self.login_handler:
                logging.error("❌ Login handler not initialized")
                return False

            if not self.driver:
                logging.error("❌ Selenium driver not connected")
                return False

            # Use Selenium-based logout
            result = self.login_handler.logout()

            if result:
                logging.info("")
                logging.info("✅ LOGOUT SUCCESSFUL")
                logging.info("="*60)
                logging.info("")
                return True
            else:
                logging.warning("")
                logging.warning("⚠️  LOGOUT COMPLETED (may need manual verification)")
                logging.info("="*60)
                logging.info("")
                return True  # Return True anyway - partial success

        except Exception as e:
            logging.error(f"❌ Logout error: {e}", exc_info=True)
            return False

    def close_browser(self) -> bool:
        """
        Close browser profile via API

        Returns:
            True if browser closed successfully
        """
        logging.info("")
        logging.info("="*60)
        logging.info("CLOSING IX BROWSER PROFILE")
        logging.info("="*60)

        success = True

        try:
            # Step 1: Disconnect Selenium
            if self.driver:
                logging.info("")
                logging.info("📋 Step 1/2: Disconnecting Selenium...")

                try:
                    self.selenium_connector.disconnect(self.driver)
                    self.driver = None
                    logging.info("   ✓ Selenium disconnected")
                except Exception as e:
                    logging.warning(f"   ⚠️  Selenium disconnect warning: {e}")
                    # Continue anyway

            # Step 2: Close profile via API
            if self.current_profile_id and self.api_client:
                logging.info("")
                logging.info("📋 Step 2/2: Closing profile via API...")

                try:
                    result = self.api_client.close_profile(self.current_profile_id)

                    if result:
                        logging.info("   ✓ Profile closed via API")
                    else:
                        logging.warning("   ⚠️  API close failed - profile may still be open")
                        success = False

                except Exception as e:
                    logging.warning(f"   ⚠️  API close warning: {e}")
                    success = False

            # Wait for cleanup
            time.sleep(2)

            logging.info("")
            if success:
                logging.info("✅ IX BROWSER CLOSED SUCCESSFULLY")
            else:
                logging.info("⚠️  IX BROWSER CLOSE COMPLETED WITH WARNINGS")
            logging.info("="*60)
            logging.info("")

            return success

        except Exception as e:
            logging.error(f"❌ Error closing browser: {e}", exc_info=True)
            return False

    def cleanup(self) -> None:
        """Cleanup resources"""
        logging.info("🧹 Cleaning up resources...")

        # Reset state
        self.current_account = None
        self.current_profile_id = None
        self.debugging_address = None
        self.driver = None
        self.login_handler = None

        # API client and connector remain initialized for next workflow

        logging.info("✓ Cleanup complete")

    def __str__(self) -> str:
        """String representation"""
        return (
            f"IXBrowserApproach("
            f"profile_id={self.current_profile_id}, "
            f"account={self.current_account}, "
            f"api_mode={self.auth_manager.get_api_mode() if self.auth_manager else 'unknown'}"
            f")"
        )
