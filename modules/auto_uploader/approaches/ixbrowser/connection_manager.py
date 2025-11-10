"""
ixBrowser Connection Manager
Manages API connection using official ixbrowser-local-api library
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Try to import official library
try:
    from ixbrowser_local_api import IXBrowserClient
    HAS_OFFICIAL_LIBRARY = True
except ImportError:
    HAS_OFFICIAL_LIBRARY = False
    IXBrowserClient = None
    logger.error("[IXConnection] Official library not installed!")
    logger.error("[IXConnection] Please install: pip install ixbrowser-local-api")


class ConnectionManager:
    """Manages connection to ixBrowser Local API."""

    def __init__(self, base_url: str = "http://127.0.0.1:53200"):
        """
        Initialize connection manager.

        Args:
            base_url: ixBrowser API base URL
        """
        self.base_url = base_url
        self._client: Optional[Any] = None
        self._is_connected = False

        # Extract host and port from base_url
        self._host, self._port = self._parse_base_url(base_url)

        logger.info("[IXConnection] Initializing connection manager...")
        logger.info("[IXConnection]   Base URL: %s", base_url)
        logger.info("[IXConnection]   Host: %s", self._host)
        logger.info("[IXConnection]   Port: %s", self._port)

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
                logger.warning("[IXConnection] Invalid port '%s', using default 53200", port_str)
                port = 53200
        else:
            host = url.split("/")[0]
            port = 53200

        return host, port

    def connect(self) -> bool:
        """
        Establish connection to ixBrowser API.

        Returns:
            True if connection successful
        """
        if not HAS_OFFICIAL_LIBRARY:
            logger.error("[IXConnection] Cannot connect - official library not installed!")
            logger.error("[IXConnection] Install with: pip install ixbrowser-local-api")
            return False

        logger.info("[IXConnection] Connecting to ixBrowser API...")
        logger.info("[IXConnection]   Target: %s:%s", self._host, self._port)

        try:
            # Initialize official client
            self._client = IXBrowserClient(target=self._host, port=self._port)

            # Test connection by getting profile list
            logger.info("[IXConnection] Testing connection...")
            profiles = self._client.get_profile_list(limit=1)

            if profiles is None:
                logger.error("[IXConnection] Connection test failed!")
                logger.error("[IXConnection]   Error code: %s", self._client.code)
                logger.error("[IXConnection]   Error message: %s", self._client.message)
                self._is_connected = False
                return False

            logger.info("[IXConnection] ✓ Connection successful!")
            logger.info("[IXConnection]   Total profiles available: %s", self._client.total)
            self._is_connected = True
            return True

        except Exception as e:
            logger.error("[IXConnection] Connection failed: %s", str(e))
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
        Get the underlying IXBrowserClient instance.

        Returns:
            IXBrowserClient instance or None
        """
        if not self._is_connected:
            logger.warning("[IXConnection] Not connected! Call connect() first.")
            return None
        return self._client

    def get_profile_list(self, limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        """
        Get list of available profiles.

        Args:
            limit: Maximum number of profiles to return

        Returns:
            List of profile dictionaries or None on error
        """
        if not self._is_connected or not self._client:
            logger.error("[IXConnection] Not connected!")
            return None

        logger.info("[IXConnection] Fetching profile list (limit=%s)...", limit)

        try:
            profiles = self._client.get_profile_list(limit=limit)

            if profiles is None:
                logger.error("[IXConnection] Failed to get profiles!")
                logger.error("[IXConnection]   Error: %s", self._client.message)
                return None

            logger.info("[IXConnection] ✓ Retrieved %s profile(s)", len(profiles))
            return profiles

        except Exception as e:
            logger.error("[IXConnection] Error getting profiles: %s", str(e))
            return None

    def find_profile_by_id(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """
        Find specific profile by ID.

        Args:
            profile_id: Profile ID

        Returns:
            Profile dictionary or None
        """
        if not self._is_connected or not self._client:
            logger.error("[IXConnection] Not connected!")
            return None

        logger.info("[IXConnection] Looking for profile ID: %s", profile_id)

        try:
            profiles = self._client.get_profile_list(profile_id=profile_id)

            if profiles is None or len(profiles) == 0:
                logger.error("[IXConnection] Profile %s not found!", profile_id)
                return None

            profile = profiles[0]
            logger.info("[IXConnection] ✓ Found profile: %s", profile.get('name', 'Unknown'))
            return profile

        except Exception as e:
            logger.error("[IXConnection] Error finding profile: %s", str(e))
            return None

    def test_connection(self) -> bool:
        """
        Test if connection is working.

        Returns:
            True if connection works
        """
        logger.info("[IXConnection] Testing connection...")

        if not self._is_connected:
            logger.error("[IXConnection] Not connected!")
            return False

        try:
            profiles = self.get_profile_list(limit=1)
            success = profiles is not None

            if success:
                logger.info("[IXConnection] ✓ Connection test passed!")
            else:
                logger.error("[IXConnection] ✗ Connection test failed!")

            return success

        except Exception as e:
            logger.error("[IXConnection] Connection test error: %s", str(e))
            return False

    def disconnect(self) -> None:
        """Disconnect from API."""
        logger.info("[IXConnection] Disconnecting...")
        self._client = None
        self._is_connected = False
        logger.info("[IXConnection] ✓ Disconnected")


if __name__ == "__main__":
    # Test mode
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print("\n" + "="*60)
    print("Testing ixBrowser Connection")
    print("="*60 + "\n")

    # Test connection
    manager = ConnectionManager()

    if manager.connect():
        print("\n✓ Connection successful!")

        # Test profile list
        profiles = manager.get_profile_list(limit=5)
        if profiles:
            print(f"\n✓ Found {len(profiles)} profile(s):")
            for p in profiles:
                print(f"  - {p.get('name', 'Unknown')} (ID: {p.get('profile_id')})")

        manager.disconnect()
    else:
        print("\n✗ Connection failed!")
