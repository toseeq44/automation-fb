"""
NSTbrowser Connection Manager
Manages API connection using official nstbrowser library
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Try to import official library
try:
    from nstbrowser import NstbrowserClient
    HAS_OFFICIAL_LIBRARY = True
except ImportError:
    HAS_OFFICIAL_LIBRARY = False
    NstbrowserClient = None
    logger.error("[NSTConnection] Official library not installed!")
    logger.error("[NSTConnection] Please install: pip install nstbrowser")

# Import desktop launcher
from .desktop_launcher import NSTDesktopLauncher


class NSTConnectionManager:
    """Manages connection to NSTbrowser API."""

    def __init__(self, api_key: str, base_url: str = "http://127.0.0.1:8848",
                 auto_launch: bool = True, email: Optional[str] = None,
                 password: Optional[str] = None):
        """
        Initialize connection manager.

        Args:
            api_key: NSTbrowser API key (UUID format)
            base_url: NSTbrowser API base URL
            auto_launch: Automatically launch NSTbrowser if not running
            email: NSTbrowser login email (for auto-login)
            password: NSTbrowser login password (for auto-login)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.auto_launch = auto_launch
        self.email = email
        self.password = password
        self._client: Optional[Any] = None
        self._is_connected = False

        # Extract host and port from base_url
        self._host, self._port = self._parse_base_url(base_url)

        # Initialize desktop launcher
        self._desktop_launcher: Optional[NSTDesktopLauncher] = None
        if auto_launch:
            self._desktop_launcher = NSTDesktopLauncher(
                host=self._host,
                port=self._port,
                email=email,
                password=password
            )

        logger.info("[NSTConnection] Initializing connection manager...")
        logger.info("[NSTConnection]   Base URL: %s", base_url)
        logger.info("[NSTConnection]   Host: %s", self._host)
        logger.info("[NSTConnection]   Port: %s", self._port)
        logger.info("[NSTConnection]   Auto-launch: %s", auto_launch)
        if email:
            logger.info("[NSTConnection]   Auto-login enabled: Yes (email: %s)", email)

    def _parse_base_url(self, base_url: str) -> tuple[str, int]:
        """
        Parse base URL to extract host and port.

        Args:
            base_url: Full base URL

        Returns:
            Tuple of (host, port)
        """
        # Remove protocol
        url = base_url.replace("http://", "").replace("https://", "")

        # Remove trailing slashes
        url = url.rstrip("/")

        # Split host and port
        if ":" in url:
            host, port_str = url.split(":", 1)
            # Remove any path after port
            port_str = port_str.split("/")[0]
            try:
                port = int(port_str)
            except ValueError:
                logger.warning("[NSTConnection] Invalid port '%s', using default 8848", port_str)
                port = 8848
        else:
            host = url.split("/")[0]
            port = 8848

        return host, port

    def connect(self) -> bool:
        """
        Establish connection to NSTbrowser API.

        If auto_launch is enabled and API is not available,
        automatically launches NSTbrowser desktop application.

        Returns:
            True if connection successful
        """
        if not HAS_OFFICIAL_LIBRARY:
            logger.error("[NSTConnection] Cannot connect - official library not installed!")
            logger.error("[NSTConnection] Install with: pip install nstbrowser")
            return False

        if not self.api_key:
            logger.error("[NSTConnection] Cannot connect - API key not provided!")
            return False

        # Auto-launch NSTbrowser if enabled
        if self.auto_launch and self._desktop_launcher:
            logger.info("[NSTConnection] ═══════════════════════════════════════════")
            logger.info("[NSTConnection] Auto-Launch Check")
            logger.info("[NSTConnection] ═══════════════════════════════════════════")

            if not self._desktop_launcher.ensure_running(timeout=60):
                logger.error("[NSTConnection] ✗ Failed to ensure NSTbrowser is running!")
                logger.error("[NSTConnection] Please start NSTbrowser manually or check installation")
                return False

        logger.info("[NSTConnection] Connecting to NSTbrowser API...")
        logger.info("[NSTConnection]   Target: %s:%s", self._host, self._port)
        logger.info("[NSTConnection]   API Key: %s...%s", self.api_key[:8], self.api_key[-8:])

        try:
            # Initialize official client with API key
            self._client = NstbrowserClient(api_key=self.api_key)

            # Test connection by getting profile list
            logger.info("[NSTConnection] Testing connection...")
            response = self._client.profiles.get_profiles(data={"page": 1, "pageSize": 1})

            # Debug: Log the actual response structure
            logger.debug("[NSTConnection] Raw response type: %s", type(response))
            logger.debug("[NSTConnection] Raw response: %s", response)

            if response is None or response.get('code') != 0:
                error_msg = response.get('message', 'Unknown error') if response else 'No response'
                logger.error("[NSTConnection] Connection test failed!")
                logger.error("[NSTConnection]   Error: %s", error_msg)
                logger.error("[NSTConnection]   Response code: %s", response.get('code') if response else 'N/A')
                self._is_connected = False
                return False

            total_profiles = response.get('data', {}).get('total', 0)
            logger.info("[NSTConnection] ✓ Connection successful!")
            logger.info("[NSTConnection]   Total profiles available: %s", total_profiles)
            self._is_connected = True
            return True

        except Exception as e:
            logger.error("[NSTConnection] Connection failed: %s", str(e))
            self._is_connected = False
            return False

    def is_connected(self) -> bool:
        """
        Check if connection is active.

        Returns:
            True if connected
        """
        return self._is_connected

    def get_client(self) -> Optional[Any]:
        """
        Get the underlying NstbrowserClient instance.

        Returns:
            NstbrowserClient instance or None
        """
        if not self._is_connected:
            logger.warning("[NSTConnection] Not connected! Call connect() first.")
            return None
        return self._client

    def get_profile_list(self, page: int = 1, page_size: int = 100) -> Optional[List[Dict[str, Any]]]:
        """
        Get list of available profiles.

        Args:
            page: Page number (1-indexed)
            page_size: Number of profiles per page

        Returns:
            List of profile dictionaries or None on error
        """
        if not self._is_connected or not self._client:
            logger.error("[NSTConnection] Not connected!")
            return None

        logger.info("[NSTConnection] Fetching profile list (page=%s, page_size=%s)...", page, page_size)

        try:
            response = self._client.profiles.get_profiles(
                data={"page": page, "pageSize": page_size}
            )

            # Debug: Log response structure
            logger.debug("[NSTConnection] get_profile_list response type: %s", type(response))
            logger.debug("[NSTConnection] get_profile_list response: %s", response)

            if response is None or response.get('code') != 0:
                error_msg = response.get('message', 'Unknown error') if response else 'No response'
                logger.error("[NSTConnection] Failed to get profiles!")
                logger.error("[NSTConnection]   Error: %s", error_msg)
                logger.error("[NSTConnection]   Response code: %s", response.get('code') if response else 'N/A')
                return None

            profiles = response.get('data', {}).get('list', [])
            total = response.get('data', {}).get('total', 0)

            logger.info("[NSTConnection] ✓ Retrieved %s profile(s) (total: %s)", len(profiles), total)
            return profiles

        except Exception as e:
            logger.error("[NSTConnection] Error getting profiles: %s", str(e))
            return None

    def find_profile_by_id(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """
        Find specific profile by ID.

        Args:
            profile_id: Profile ID

        Returns:
            Profile dictionary or None
        """
        if not self._is_connected or not self._client:
            logger.error("[NSTConnection] Not connected!")
            return None

        logger.info("[NSTConnection] Looking for profile ID: %s", profile_id)

        try:
            # Get all profiles and search for matching ID
            # Note: NSTbrowser API might have a direct profile lookup method
            # This is a fallback that gets all profiles and filters
            profiles = self.get_profile_list(page_size=1000)

            if profiles is None:
                return None

            for profile in profiles:
                if str(profile.get('id')) == str(profile_id):
                    logger.info("[NSTConnection] ✓ Found profile: %s", profile.get('name', 'Unknown'))
                    return profile

            logger.error("[NSTConnection] Profile %s not found!", profile_id)
            return None

        except Exception as e:
            logger.error("[NSTConnection] Error finding profile: %s", str(e))
            return None

    def test_connection(self) -> bool:
        """
        Test if connection is working.

        Returns:
            True if connection works
        """
        logger.info("[NSTConnection] Testing connection...")

        if not self._is_connected:
            logger.error("[NSTConnection] Not connected!")
            return False

        try:
            profiles = self.get_profile_list(page_size=1)
            success = profiles is not None

            if success:
                logger.info("[NSTConnection] ✓ Connection test passed!")
            else:
                logger.error("[NSTConnection] ✗ Connection test failed!")

            return success

        except Exception as e:
            logger.error("[NSTConnection] Connection test error: %s", str(e))
            return False

    def disconnect(self) -> None:
        """Disconnect from API."""
        logger.info("[NSTConnection] Disconnecting...")
        self._client = None
        self._is_connected = False
        logger.info("[NSTConnection] ✓ Disconnected")


if __name__ == "__main__":
    # Test mode
    import sys
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print("\n" + "="*60)
    print("Testing NSTbrowser Connection")
    print("="*60 + "\n")

    # Get API key from environment or command line
    api_key = input("Enter NSTbrowser API key: ").strip()

    if not api_key:
        print("✗ API key required!")
        sys.exit(1)

    # Test connection
    manager = NSTConnectionManager(api_key=api_key)

    if manager.connect():
        print("\n✓ Connection successful!")

        # Test profile list
        profiles = manager.get_profile_list(page_size=5)
        if profiles:
            print(f"\n✓ Found {len(profiles)} profile(s):")
            for p in profiles:
                print(f"  - {p.get('name', 'Unknown')} (ID: {p.get('id')})")

        manager.disconnect()
    else:
        print("\n✗ Connection failed!")
