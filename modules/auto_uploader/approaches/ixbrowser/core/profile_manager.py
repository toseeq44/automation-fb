"""
Profile Manager for ixBrowser Approach

Handles multi-profile workflow:
- Fetch profiles from ixBrowser API
- Track current profile index
- Open/close profiles sequentially
- Check profile completion
- Resume from crash/interruption

Usage:
    profile_mgr = ProfileManager(connection_manager, state_manager)
    profiles = profile_mgr.fetch_profiles()

    while not profile_mgr.all_profiles_complete():
        profile = profile_mgr.get_current_profile()
        # ... process profile ...
        profile_mgr.move_to_next_profile()
"""

import logging
import time
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages multi-profile workflow for ixBrowser automation."""

    def __init__(self, connection_manager, state_manager):
        """
        Initialize Profile Manager.

        Args:
            connection_manager: ConnectionManager instance for API access
            state_manager: StateManager instance for state persistence
        """
        self.connection_manager = connection_manager
        self.state_manager = state_manager

        # Profile data
        self.profiles: List[Dict[str, Any]] = []
        self.current_profile_index: int = 0

        # Currently open profile
        self.current_launcher = None
        self.current_driver = None

        logger.info("[ProfileManager] Initialized")

    def fetch_profiles(self, limit: int = 9999) -> List[Dict[str, Any]]:
        """
        Fetch all profiles from ixBrowser API.

        Args:
            limit: Maximum profiles to fetch (default: 9999 - essentially unlimited)

        Returns:
            List of profile dictionaries with 'profile_id', 'name', etc.
        """
        try:
            logger.info("[ProfileManager] Fetching ALL profiles from ixBrowser API...")

            profiles = self.connection_manager.get_profile_list(limit=limit)

            if not profiles:
                logger.warning("[ProfileManager] No profiles found in ixBrowser!")
                return []

            self.profiles = profiles
            logger.info("[ProfileManager] ✓ Retrieved %d profile(s)", len(profiles))

            # Log all profiles
            for idx, profile in enumerate(profiles, 1):
                profile_id = profile.get('profile_id', 'unknown')
                profile_name = profile.get('name', 'Unknown')
                logger.info("[ProfileManager]   %d. %s (ID: %s)", idx, profile_name, profile_id)

            return profiles

        except Exception as e:
            logger.error("[ProfileManager] Failed to fetch profiles: %s", str(e))
            return []

    def load_state(self):
        """
        Load profile state from StateManager.

        Restores current_profile_index and profile completion status.
        """
        try:
            state = self.state_manager.load_profile_state()

            if state:
                self.current_profile_index = state.get('current_profile_index', 0)
                logger.info("[ProfileManager] ✓ Loaded state: Profile index %d",
                           self.current_profile_index)
            else:
                self.current_profile_index = 0
                logger.info("[ProfileManager] No saved state, starting from profile 0")

        except Exception as e:
            logger.warning("[ProfileManager] Failed to load state: %s", str(e))
            self.current_profile_index = 0

    def save_state(self):
        """Save current profile state to StateManager."""
        try:
            state = {
                'current_profile_index': self.current_profile_index,
                'total_profiles': len(self.profiles),
                'last_updated': time.strftime("%Y-%m-%d %H:%M:%S")
            }

            self.state_manager.save_profile_state(state)
            logger.debug("[ProfileManager] State saved: Profile index %d",
                        self.current_profile_index)

        except Exception as e:
            logger.error("[ProfileManager] Failed to save state: %s", str(e))

    def get_current_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get currently active profile.

        Returns:
            Profile dictionary or None if no profiles
        """
        if not self.profiles:
            logger.warning("[ProfileManager] No profiles available")
            return None

        if self.current_profile_index >= len(self.profiles):
            logger.warning("[ProfileManager] Profile index out of range: %d/%d",
                          self.current_profile_index, len(self.profiles))
            return None

        profile = self.profiles[self.current_profile_index]
        return profile

    def get_current_profile_info(self) -> Dict[str, Any]:
        """
        Get current profile information for logging.

        Returns:
            Dict with profile_id, name, index, total
        """
        profile = self.get_current_profile()

        if not profile:
            return {
                'profile_id': None,
                'name': 'Unknown',
                'index': self.current_profile_index,
                'total': len(self.profiles)
            }

        return {
            'profile_id': profile.get('profile_id'),
            'name': profile.get('name', 'Unknown'),
            'index': self.current_profile_index + 1,  # 1-based for display
            'total': len(self.profiles)
        }

    def open_profile(self, launcher) -> bool:
        """
        Open current profile using provided launcher.

        Args:
            launcher: BrowserLauncher instance

        Returns:
            True if successful, False otherwise
        """
        try:
            profile = self.get_current_profile()
            if not profile:
                logger.error("[ProfileManager] No current profile to open")
                return False

            profile_id = profile.get('profile_id')
            profile_name = profile.get('name', 'Unknown')

            logger.info("[ProfileManager] ═══════════════════════════════════════════")
            logger.info("[ProfileManager] Opening Profile")
            logger.info("[ProfileManager] ═══════════════════════════════════════════")
            logger.info("[ProfileManager] Profile: %s (ID: %s)", profile_name, profile_id)
            logger.info("[ProfileManager] Position: %d/%d",
                       self.current_profile_index + 1, len(self.profiles))

            # Launch profile with no custom args (clean opening)
            if not launcher.launch_profile(profile_id, startup_args=[]):
                logger.error("[ProfileManager] ✗ Failed to launch profile")
                return False

            # Attach Selenium
            if not launcher.attach_selenium():
                logger.error("[ProfileManager] ✗ Failed to attach Selenium")
                return False

            driver = launcher.get_driver()
            if not driver:
                logger.error("[ProfileManager] ✗ Driver not available")
                return False

            # Store launcher and driver
            self.current_launcher = launcher
            self.current_driver = driver

            logger.info("[ProfileManager] ✓ Profile opened successfully!")
            return True

        except Exception as e:
            logger.error("[ProfileManager] Failed to open profile: %s", str(e))
            return False

    def close_profile(self) -> bool:
        """
        Close currently open profile.

        Returns:
            True if successful, False otherwise
        """
        try:
            profile = self.get_current_profile()
            if not profile:
                logger.debug("[ProfileManager] No current profile to close")
                return True

            profile_name = profile.get('name', 'Unknown')
            profile_id = profile.get('profile_id')

            logger.info("[ProfileManager] ═══════════════════════════════════════════")
            logger.info("[ProfileManager] Closing Profile")
            logger.info("[ProfileManager] ═══════════════════════════════════════════")
            logger.info("[ProfileManager] Profile: %s (ID: %s)", profile_name, profile_id)

            # Close using launcher if available
            if self.current_launcher:
                try:
                    self.current_launcher.close_profile()
                    logger.info("[ProfileManager] ✓ Launcher closed profile")
                except Exception as e:
                    logger.warning("[ProfileManager] Launcher close failed: %s", str(e))

            # Close via API
            try:
                client = self.connection_manager.get_client()
                if client:
                    client.close_profile(profile_id)
                    logger.info("[ProfileManager] ✓ API closed profile")
            except Exception as e:
                logger.warning("[ProfileManager] API close failed: %s", str(e))

            # Clear references
            self.current_launcher = None
            self.current_driver = None

            # Brief wait for cleanup
            time.sleep(2)

            logger.info("[ProfileManager] ✓ Profile closed successfully!")
            return True

        except Exception as e:
            logger.error("[ProfileManager] Failed to close profile: %s", str(e))
            return False

    def move_to_next_profile(self) -> bool:
        """
        Move to next profile in sequence.

        Returns:
            True if moved to next profile, False if all profiles complete
        """
        self.current_profile_index += 1

        if self.current_profile_index >= len(self.profiles):
            logger.info("[ProfileManager] ═══════════════════════════════════════════")
            logger.info("[ProfileManager] Completed All Profiles!")
            logger.info("[ProfileManager] ═══════════════════════════════════════════")
            logger.info("[ProfileManager] Total profiles processed: %d", len(self.profiles))
            logger.info("[ProfileManager] All profiles have been processed")
            return False

        # Save state
        self.save_state()

        profile = self.get_current_profile()
        profile_name = profile.get('name', 'Unknown') if profile else 'Unknown'

        logger.info("[ProfileManager] ═══════════════════════════════════════════")
        logger.info("[ProfileManager] Moving to Next Profile")
        logger.info("[ProfileManager] ═══════════════════════════════════════════")
        logger.info("[ProfileManager] Next profile: %s", profile_name)
        logger.info("[ProfileManager] Position: %d/%d",
                   self.current_profile_index + 1, len(self.profiles))

        return True

    def all_profiles_complete(self) -> bool:
        """
        Check if all profiles have been processed.

        Returns:
            True if all profiles done, False otherwise
        """
        return self.current_profile_index >= len(self.profiles)

    def reset_to_first_profile(self):
        """Reset to first profile (for new day or manual restart)."""
        logger.info("[ProfileManager] Resetting to first profile")
        self.current_profile_index = 0
        self.save_state()

    def get_driver(self):
        """
        Get currently active Selenium driver.

        Returns:
            WebDriver instance or None
        """
        return self.current_driver

    def get_profile_folder_path(self, base_path: str) -> Optional[Path]:
        """
        Get folder path for current profile.

        Args:
            base_path: Base path (e.g., Desktop/creators data/)

        Returns:
            Path to profile folder or None if not found
        """
        profile = self.get_current_profile()
        if not profile:
            return None

        profile_name = profile.get('name', 'Unknown')
        profile_folder = Path(base_path) / profile_name

        return profile_folder
