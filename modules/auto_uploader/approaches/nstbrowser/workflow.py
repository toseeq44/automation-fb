"""
NSTbrowser Approach Workflow
============================
Complete workflow for Facebook video upload automation using NSTbrowser.

This approach:
1. Uses NSTbrowser antidetect browser for profile management
2. Connects via official NSTbrowser API
3. Supports multi-profile automation
4. Uses Selenium for Facebook interaction
5. Implements state persistence and network monitoring
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from ..base_approach import (
    BaseApproach,
    ApproachConfig,
    WorkItem,
    WorkflowResult
)

from .config_handler import NSTBrowserConfig
from .connection_manager import NSTConnectionManager
from .browser_launcher import NSTBrowserLauncher

# Import reusable components from ixbrowser
# These components are browser-agnostic
try:
    from ..ixbrowser.core.state_manager import StateManager
    from ..ixbrowser.core.network_monitor import NetworkMonitor
    from ..ixbrowser.core.profile_manager import ProfileManager
    from ..ixbrowser.core.folder_queue_manager import FolderQueueManager
    HAS_CORE_COMPONENTS = True
except ImportError:
    HAS_CORE_COMPONENTS = False
    StateManager = None
    NetworkMonitor = None
    ProfileManager = None
    FolderQueueManager = None

logger = logging.getLogger(__name__)


class NSTBrowserApproach(BaseApproach):
    """
    NSTbrowser-based approach for Facebook video upload automation.

    This approach uses NSTbrowser's antidetect browser with multi-profile support
    and implements robust state management and network monitoring.
    """

    def __init__(self, config: ApproachConfig):
        """
        Initialize NSTbrowser approach.

        Args:
            config: Approach configuration
        """
        super().__init__(config)

        # NSTbrowser-specific components
        self._config_handler: Optional[NSTBrowserConfig] = None
        self._connection_manager: Optional[NSTConnectionManager] = None
        self._browser_launcher: Optional[NSTBrowserLauncher] = None

        # Reusable core components (from ixbrowser)
        self._state_manager: Optional[StateManager] = None
        self._network_monitor: Optional[NetworkMonitor] = None
        self._profile_manager: Optional[ProfileManager] = None
        self._folder_queue: Optional[FolderQueueManager] = None

        # Track current state
        self._current_profile_id: Optional[str] = None
        self._is_browser_open = False

        logger.info("[NSTApproach] NSTbrowser approach initialized")

    def initialize(self) -> bool:
        """
        Initialize NSTbrowser approach components.

        Sets up:
        1. Configuration handler
        2. API connection
        3. State management
        4. Network monitoring
        5. Profile management

        Returns:
            True if initialization successful
        """
        logger.info("[NSTApproach] ════════════════════════════════════════════════")
        logger.info("[NSTApproach] Initializing NSTbrowser Approach")
        logger.info("[NSTApproach] ════════════════════════════════════════════════")

        try:
            # Step 1: Initialize configuration
            logger.info("[NSTApproach] Step 1/5: Loading configuration...")
            self._config_handler = NSTBrowserConfig()

            # Get credentials from approach config
            api_key = self.config.credentials.get('api_key', '')
            email = self.config.credentials.get('email', '')
            password = self.config.credentials.get('password', '')
            base_url = self.config.credentials.get('base_url', 'http://127.0.0.1:8848')

            if not api_key:
                logger.error("[NSTApproach] ✗ API key not provided in credentials!")
                return False

            if not email or not password:
                logger.error("[NSTApproach] ✗ Email/password not provided in credentials!")
                return False

            # Set credentials
            self._config_handler.set_credentials(
                email=email,
                password=password,
                api_key=api_key,
                base_url=base_url
            )

            logger.info("[NSTApproach] ✓ Configuration loaded")

            # Step 2: Initialize connection manager
            logger.info("[NSTApproach] Step 2/5: Connecting to NSTbrowser API...")
            self._connection_manager = NSTConnectionManager(
                api_key=api_key,
                base_url=base_url,
                auto_launch=True,
                email=email,
                password=password
            )

            if not self._connection_manager.connect():
                logger.error("[NSTApproach] ✗ Failed to connect to NSTbrowser API!")
                return False

            logger.info("[NSTApproach] ✓ API connection established")

            # Step 3: Initialize browser launcher
            logger.info("[NSTApproach] Step 3/5: Setting up browser launcher...")
            client = self._connection_manager.get_client()
            if not client:
                logger.error("[NSTApproach] ✗ Failed to get API client!")
                return False

            self._browser_launcher = NSTBrowserLauncher(client)
            logger.info("[NSTApproach] ✓ Browser launcher ready")

            # Step 4: Initialize core components (if available)
            if HAS_CORE_COMPONENTS:
                logger.info("[NSTApproach] Step 4/5: Initializing core components...")

                # State manager for crash recovery
                self._state_manager = StateManager()
                logger.info("[NSTApproach]   ✓ State manager initialized")

                # Network monitor for network resilience
                self._network_monitor = NetworkMonitor(check_interval=10)
                logger.info("[NSTApproach]   ✓ Network monitor initialized")

                # Profile manager for multi-profile support
                self._profile_manager = ProfileManager()
                logger.info("[NSTApproach]   ✓ Profile manager initialized")

                # Folder queue for video management
                self._folder_queue = FolderQueueManager()
                logger.info("[NSTApproach]   ✓ Folder queue initialized")

                logger.info("[NSTApproach] ✓ All core components initialized")
            else:
                logger.warning("[NSTApproach] ⚠ Core components not available")
                logger.warning("[NSTApproach]   Advanced features (state, network monitoring) disabled")

            # Step 5: Validate setup
            logger.info("[NSTApproach] Step 5/5: Validating setup...")

            # Test API connection
            if not self._connection_manager.test_connection():
                logger.error("[NSTApproach] ✗ API connection test failed!")
                return False

            logger.info("[NSTApproach] ✓ Setup validation complete")

            logger.info("[NSTApproach] ════════════════════════════════════════════════")
            logger.info("[NSTApproach] ✓ Initialization Complete")
            logger.info("[NSTApproach] ════════════════════════════════════════════════")

            return True

        except Exception as e:
            logger.error("[NSTApproach] ✗ Initialization failed: %s", str(e), exc_info=True)
            return False

    def open_browser(self, account_name: str) -> bool:
        """
        Open browser profile via NSTbrowser API.

        Args:
            account_name: Profile name/ID to open

        Returns:
            True if browser opened successfully
        """
        logger.info("[NSTApproach] Opening browser for: %s", account_name)

        try:
            # Find profile by name or ID
            # For now, use account_name as profile_id directly
            # In production, you might want to search for profile by name
            profile_id = account_name

            # Launch profile
            if not self._browser_launcher.launch_profile(profile_id):
                logger.error("[NSTApproach] Failed to launch profile: %s", profile_id)
                return False

            # Attach Selenium
            if not self._browser_launcher.attach_selenium():
                logger.error("[NSTApproach] Failed to attach Selenium to profile")
                return False

            self._current_profile_id = profile_id
            self._is_browser_open = True

            logger.info("[NSTApproach] ✓ Browser opened and Selenium attached")
            return True

        except Exception as e:
            logger.error("[NSTApproach] Error opening browser: %s", str(e))
            return False

    def login(self, email: str, password: str) -> bool:
        """
        Login to Facebook (placeholder - implement Facebook login logic).

        Args:
            email: Facebook login email
            password: Facebook login password

        Returns:
            True if login successful
        """
        logger.info("[NSTApproach] Login requested for: %s", email)
        logger.warning("[NSTApproach] Login logic not yet implemented!")
        logger.warning("[NSTApproach] TODO: Implement Facebook login via Selenium")

        # TODO: Implement Facebook login using Selenium
        # driver = self._browser_launcher.get_driver()
        # if not driver:
        #     return False
        #
        # Navigate to Facebook, enter credentials, handle 2FA, etc.

        return True  # Placeholder

    def logout(self) -> bool:
        """
        Logout from Facebook (placeholder - implement Facebook logout logic).

        Returns:
            True if logout successful
        """
        logger.info("[NSTApproach] Logout requested")
        logger.warning("[NSTApproach] Logout logic not yet implemented!")
        logger.warning("[NSTApproach] TODO: Implement Facebook logout via Selenium")

        # TODO: Implement Facebook logout using Selenium

        return True  # Placeholder

    def close_browser(self) -> bool:
        """
        Close current browser profile.

        Returns:
            True if browser closed successfully
        """
        logger.info("[NSTApproach] Closing browser...")

        try:
            if not self._is_browser_open:
                logger.info("[NSTApproach] Browser already closed")
                return True

            if not self._browser_launcher:
                logger.warning("[NSTApproach] No browser launcher available")
                return True

            # Close profile
            if not self._browser_launcher.close_profile():
                logger.error("[NSTApproach] Failed to close profile")
                return False

            self._current_profile_id = None
            self._is_browser_open = False

            logger.info("[NSTApproach] ✓ Browser closed successfully")
            return True

        except Exception as e:
            logger.error("[NSTApproach] Error closing browser: %s", str(e))
            return False

    def cleanup(self) -> None:
        """
        Cleanup resources.

        Closes browser, disconnects API, stops monitors.
        """
        logger.info("[NSTApproach] Cleaning up resources...")

        try:
            # Close browser if still open
            if self._is_browser_open:
                self.close_browser()

            # Disconnect from API
            if self._connection_manager:
                self._connection_manager.disconnect()

            # Stop network monitor
            if self._network_monitor:
                # Network monitor cleanup (if needed)
                pass

            logger.info("[NSTApproach] ✓ Cleanup complete")

        except Exception as e:
            logger.error("[NSTApproach] Error during cleanup: %s", str(e))

    def get_driver(self):
        """
        Get Selenium WebDriver instance.

        Returns:
            WebDriver instance or None
        """
        if self._browser_launcher:
            return self._browser_launcher.get_driver()
        return None

    def navigate_to(self, url: str) -> bool:
        """
        Navigate to URL.

        Args:
            url: URL to navigate to

        Returns:
            True if navigation successful
        """
        if self._browser_launcher:
            return self._browser_launcher.navigate_to(url)
        return False

    def get_profiles(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get list of available profiles.

        Returns:
            List of profile dictionaries or None
        """
        if self._connection_manager:
            return self._connection_manager.get_profile_list()
        return None

    def __repr__(self) -> str:
        """String representation."""
        return (f"NSTBrowserApproach("
                f"connected={self._connection_manager.is_connected() if self._connection_manager else False}, "
                f"browser_open={self._is_browser_open})")


# Export for factory registration
__all__ = ['NSTBrowserApproach']
