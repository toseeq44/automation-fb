"""
NSTbrowser Automation Workflow
Complete integration using official nstbrowser library
"""

from __future__ import annotations

import logging
import os
import time
import subprocess
import platform
from dataclasses import dataclass
from typing import Optional

from ..base_approach import (
    ApproachConfig,
    BaseApproach,
    CreatorData,
    WorkItem,
    WorkflowResult,
)

# Import our components
from .config_handler import NSTBrowserConfig
from .connection_manager import NSTConnectionManager
from .browser_launcher import NSTBrowserLauncher

# Import reusable components from ixbrowser
from ..ixbrowser.upload_helper import VideoUploadHelper
from ..ixbrowser.window_manager import bring_window_to_front_windows, maximize_window_windows

# Phase 2: Import robustness components
from ..ixbrowser.core.state_manager import StateManager
from ..ixbrowser.core.network_monitor import NetworkMonitor
from ..ixbrowser.core.folder_queue import FolderQueueManager
from ..ixbrowser.core.profile_manager import ProfileManager
from ..ixbrowser.config.upload_config import USER_CONFIG

logger = logging.getLogger(__name__)


def bring_browser_to_front(driver) -> bool:
    """
    Bring browser window to front using OS-level commands.
    This ensures the window is visible above ALL other windows including the Python app.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        True if successful
    """
    try:
        logger.info("[Window] ═══════════════════════════════════════════")
        logger.info("[Window] Bringing Browser Window to FRONT")
        logger.info("[Window] ═══════════════════════════════════════════")

        # Get window title
        window_title = driver.title
        logger.info("[Window] Window title: '%s'", window_title)

        # Method 1: Selenium maximize (basic)
        try:
            driver.maximize_window()
            driver.switch_to.window(driver.current_window_handle)
            driver.execute_script("window.focus();")
            logger.info("[Window] ✓ Selenium maximize applied")
        except Exception as e:
            logger.debug("[Window] Selenium focus failed: %s", str(e))

        # Method 2: OS-specific commands
        system = platform.system()
        logger.info("[Window] Detected OS: %s", system)

        success = False

        if system == "Windows":
            # Use dedicated Windows window manager
            logger.info("[Window] Using Windows-specific window management...")

            # Try to bring window to front
            if bring_window_to_front_windows(window_title, partial_match=True):
                success = True
                logger.info("[Window] ✓ Windows window manager successful!")

            # Also try to maximize
            maximize_window_windows(window_title)

        elif system == "Linux":
            # Linux: Use wmctrl or xdotool
            try:
                # Try wmctrl first
                try:
                    subprocess.run(
                        ["wmctrl", "-a", window_title],
                        check=False,
                        timeout=2,
                        capture_output=True
                    )
                    logger.info("[Window] ✓ wmctrl applied")
                    success = True
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

                # Try xdotool as fallback
                if not success:
                    try:
                        subprocess.run(
                            ["xdotool", "search", "--name", window_title, "windowactivate"],
                            check=False,
                            timeout=2,
                            capture_output=True
                        )
                        logger.info("[Window] ✓ xdotool applied")
                        success = True
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        pass

            except Exception as e:
                logger.debug("[Window] Linux commands failed: %s", str(e))

        # Final attempts
        try:
            driver.execute_script("window.focus(); window.scrollTo(0, 0);")
        except:
            pass

        time.sleep(1)  # Give OS time to process

        logger.info("[Window] ═══════════════════════════════════════════")
        if success:
            logger.info("[Window] ✓✓✓ WINDOW NOW VISIBLE ON TOP! ✓✓✓")
        else:
            logger.warning("[Window] ⚠ Window focus attempted (may need manual check)")
        logger.info("[Window] ═══════════════════════════════════════════")

        return True  # Return True even if OS commands failed (Selenium might work)

    except Exception as e:
        logger.error("[Window] Fatal error: %s", str(e))
        return False


@dataclass
class NSTAutomationContext:
    """Holds state for a specific NSTbrowser session."""

    profile_id: str  # String format for NSTbrowser
    launcher: NSTBrowserLauncher


class NSTBrowserApproach(BaseApproach):
    """
    NSTbrowser approach using official nstbrowser library.

    Features:
    - Automatic desktop app launch
    - Programmatic browser control via API
    - Selenium WebDriver integration
    - Profile management
    - Multi-profile support
    - Daily limit enforcement
    """

    def __init__(self, config: ApproachConfig) -> None:
        super().__init__(config)

        logger.info("[NSTApproach] Initializing NSTbrowser approach...")

        # Initialize components
        self._config_handler: Optional[NSTBrowserConfig] = None
        self._connection_manager: Optional[NSTConnectionManager] = None
        self._current_context: Optional[NSTAutomationContext] = None

        # Phase 2: Initialize robustness components
        self._state_manager = StateManager()
        self._network_monitor = NetworkMonitor(check_interval=10)
        self._folder_queue: Optional[FolderQueueManager] = None
        self._profile_manager: Optional[ProfileManager] = None

        logger.info("[NSTApproach] ✓ Phase 2 robustness components initialized")

        # Load configuration
        self._setup_configuration(config)

    def _setup_configuration(self, config: ApproachConfig) -> None:
        """Setup configuration from ApproachConfig."""
        logger.info("[NSTApproach] Setting up configuration...")

        credentials = config.credentials or {}

        # Get NSTbrowser API credentials
        base_url = (
            credentials.get("base_url")
            or "http://127.0.0.1:8848"
        )

        api_key = credentials.get("api_key", "")
        email = credentials.get("email", "")
        password = credentials.get("password", "")

        # Initialize config handler
        self._config_handler = NSTBrowserConfig()

        # Check if we have credentials in config
        if api_key and email and password:
            logger.info("[NSTApproach] Using NSTbrowser credentials from ApproachConfig")
            self._config_handler.set_credentials(email, password, api_key, base_url)
        elif self._config_handler.validate_config()[0]:
            logger.info("[NSTApproach] Using saved NSTbrowser credentials from config file")
        else:
            logger.warning("[NSTApproach] No NSTbrowser credentials configured!")
            logger.warning("[NSTApproach] Please provide api_key, email, password in approach config")

    # ------------------------------------------------------------------ #
    # BaseApproach contract                                              #
    # ------------------------------------------------------------------ #
    def initialize(self) -> bool:
        """Initialize connection to NSTbrowser API."""
        logger.info("[NSTApproach] Initializing connection...")

        valid, msg = self._config_handler.validate_config()
        if not valid:
            logger.error("[NSTApproach] Configuration incomplete: %s", msg)
            logger.error("[NSTApproach] Required: api_key, email, password for NSTbrowser")
            return False

        # Get configuration
        creds = self._config_handler.get_credentials()
        api_key = creds['api_key']
        email = creds['email']
        password = creds['password']
        base_url = creds['base_url']

        logger.info("[NSTApproach] Connecting to: %s", base_url)

        # Initialize connection manager (with auto-launch)
        self._connection_manager = NSTConnectionManager(
            api_key=api_key,
            base_url=base_url,
            auto_launch=True,
            email=email,
            password=password
        )

        # Attempt connection (will auto-launch NSTbrowser if needed)
        if not self._connection_manager.connect():
            logger.error("[NSTApproach] Failed to connect to NSTbrowser API!")
            return False

        logger.info("[NSTApproach] ✓ Connection established successfully!")
        return True

    def open_browser(self, account_name: str) -> bool:
        """Browser lifecycle handled in execute_workflow."""
        return True

    def login(self, email: str, password: str) -> bool:
        """Login handled in execute_workflow."""
        return True

    def logout(self) -> bool:
        """Logout handled in execute_workflow."""
        return True

    def close_browser(self) -> bool:
        """Browser close handled in execute_workflow."""
        return True

    # ------------------------------------------------------------------ #
    # Main workflow (copied from ixBrowser and adapted for NSTbrowser)   #
    # ------------------------------------------------------------------ #
    def execute_workflow(self, work_item: WorkItem) -> WorkflowResult:
        """
        Execute complete NSTbrowser workflow.

        Steps:
        1. Launch Profile via API
        2. Attach Selenium WebDriver
        3. Enumerate Browser Tabs
        4. Bookmark-Folder Comparison
        5. Upload Videos to Bookmarks
        6. Workflow Complete (Profile remains open)
        """
        result = WorkflowResult(success=False, account_name=work_item.account_name)

        # Step 0: Initialize if not already done
        if not self._initialized:
            logger.info("[NSTApproach] ═══════════════════════════════════════════")
            logger.info("[NSTApproach] STEP 0: Initializing Approach")
            logger.info("[NSTApproach] ═══════════════════════════════════════════")

            if not self.initialize():
                result.add_error("Initialization failed")
                return result

            self._initialized = True
            logger.info("[NSTApproach] ✓ Initialization successful!")

        # Check connection
        if not self._connection_manager or not self._connection_manager.is_connected():
            result.add_error("Not connected to NSTbrowser API.")
            return result

        # Get client
        client = self._connection_manager.get_client()
        if not client:
            result.add_error("Failed to get API client.")
            return result

        # Phase 2A: Initialize ProfileManager (adapted for NSTbrowser)
        logger.info("[NSTApproach] ═══════════════════════════════════════════")
        logger.info("[NSTApproach] Phase 2A: Multi-Profile Support")
        logger.info("[NSTApproach] ═══════════════════════════════════════════")

        self._profile_manager = ProfileManager(
            connection_manager=self._connection_manager,
            state_manager=self._state_manager
        )

        # Fetch ALL profiles from NSTbrowser (unlimited)
        all_profiles = self._profile_manager.fetch_profiles()

        if not all_profiles:
            result.add_error("No profiles found in NSTbrowser. Please create a profile first.")
            return result

        logger.info("[NSTApproach] ✓ Multi-profile mode enabled")
        logger.info("[NSTApproach] ✓ Total profiles: %d", len(all_profiles))
        logger.info("[NSTApproach] ✓ Bot will process ALL profiles sequentially")

        # Load profile state (for crash recovery)
        self._profile_manager.load_state()

        # Check global daily limit BEFORE starting
        logger.info("[NSTApproach] ═══════════════════════════════════════════")
        logger.info("[NSTApproach] Global Daily Limit Check")
        logger.info("[NSTApproach] ═══════════════════════════════════════════")

        user_type = USER_CONFIG.get('user_type', 'basic')
        daily_limit = USER_CONFIG.get('daily_limit_basic', 200)

        initial_limit_status = self._state_manager.check_daily_limit(
            user_type=user_type,
            limit=daily_limit
        )

        logger.info("[NSTApproach] User Type: %s", user_type.upper())
        logger.info("[NSTApproach] %s", initial_limit_status['message'])

        # If limit already reached, stop here
        if initial_limit_status['limit_reached']:
            logger.warning("[NSTApproach] ═══════════════════════════════════════════")
            logger.warning("[NSTApproach] GLOBAL DAILY LIMIT ALREADY REACHED!")
            logger.warning("[NSTApproach] ═══════════════════════════════════════════")
            logger.warning("[NSTApproach] Uploaded today: %d bookmarks", initial_limit_status['current_count'])
            logger.warning("[NSTApproach] Daily limit: %d bookmarks", initial_limit_status['limit'])
            logger.warning("[NSTApproach] Please wait until tomorrow to upload more videos.")
            logger.warning("[NSTApproach] ═══════════════════════════════════════════")
            result.add_error("Global daily limit already reached")
            return result

        logger.info("[NSTApproach] ═══════════════════════════════════════════")

        # ═══════════════════════════════════════════════════════════
        # MAIN PROFILE LOOP - Process all profiles sequentially
        # ═══════════════════════════════════════════════════════════

        total_successful_uploads = 0
        profile_results = []

        try:
            # Loop through all profiles
            while not self._profile_manager.all_profiles_complete():
                # Check global daily limit before each profile
                current_limit_status = self._state_manager.check_daily_limit(
                    user_type=user_type,
                    limit=daily_limit
                )

                if current_limit_status['limit_reached']:
                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                    logger.warning("[NSTApproach] GLOBAL DAILY LIMIT REACHED!")
                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                    logger.warning("[NSTApproach] Uploaded today: %d/%d bookmarks",
                                 current_limit_status['current_count'],
                                 current_limit_status['limit'])
                    logger.warning("[NSTApproach] Stopping all profile processing")
                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                    break

                # Get current profile
                current_profile = self._profile_manager.get_current_profile()
                if not current_profile:
                    logger.error("[NSTApproach] No current profile available")
                    break

                # NSTbrowser uses 'id' field (string format)
                profile_id = str(current_profile.get('id'))
                profile_name = current_profile.get('name', 'Unknown')
                profile_info = self._profile_manager.get_current_profile_info()

                logger.info("[NSTApproach] ═══════════════════════════════════════════")
                logger.info("[NSTApproach] PROCESSING PROFILE %d/%d",
                           profile_info['index'], profile_info['total'])
                logger.info("[NSTApproach] ═══════════════════════════════════════════")
                logger.info("[NSTApproach] Profile: %s (ID: %s)", profile_name, profile_id)
                logger.info("[NSTApproach] Global uploads today: %d",
                           current_limit_status['current_count'])
                if user_type.lower() == 'basic':
                    logger.info("[NSTApproach] Remaining: %d/%d",
                               current_limit_status['remaining'],
                               current_limit_status['limit'])

                # Process this single profile
                profile_upload_count = self._process_single_profile(
                    profile_id=profile_id,
                    profile_name=profile_name,
                    client=client,
                    user_type=user_type,
                    daily_limit=daily_limit
                )

                # Track results
                profile_results.append({
                    'profile_name': profile_name,
                    'profile_id': profile_id,
                    'uploads': profile_upload_count
                })

                total_successful_uploads += profile_upload_count

                # Check if limit reached after this profile
                post_profile_limit = self._state_manager.check_daily_limit(
                    user_type=user_type,
                    limit=daily_limit
                )

                if post_profile_limit['limit_reached']:
                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                    logger.warning("[NSTApproach] Daily limit reached after profile: %s", profile_name)
                    logger.warning("[NSTApproach] Stopping multi-profile processing")
                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                    break

                # Move to next profile
                has_more = self._profile_manager.move_to_next_profile()
                if not has_more:
                    # All profiles processed - round complete, stop here
                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                    logger.info("[NSTApproach] ROUND COMPLETE!")
                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                    logger.info("[NSTApproach] All profiles have been processed")

                    # Check daily limit status to inform user
                    round_limit_status = self._state_manager.check_daily_limit(
                        user_type=user_type,
                        limit=daily_limit
                    )

                    logger.info("[NSTApproach] User type: %s", user_type.upper())
                    if user_type.lower() == 'basic':
                        logger.info("[NSTApproach] Daily usage: %d/%d bookmarks",
                                   round_limit_status['current_count'],
                                   round_limit_status['limit'])
                        logger.info("[NSTApproach] Remaining: %d uploads",
                                   round_limit_status['remaining'])
                    else:
                        logger.info("[NSTApproach] Pro user - unlimited uploads")

                    # Show appropriate message based on limit status
                    if round_limit_status['limit_reached']:
                        logger.info("[NSTApproach] ")
                        logger.info("[NSTApproach] ⚠ DAILY LIMIT REACHED!")
                        logger.info("[NSTApproach] Please wait until tomorrow or upgrade to PRO")
                    else:
                        logger.info("[NSTApproach] ")
                        logger.info("[NSTApproach] ✓ Round completed successfully!")
                        logger.info("[NSTApproach] You can start another round if you want")

                    logger.info("[NSTApproach] ═══════════════════════════════════════════")

                    # Reset to first profile for next run (but don't continue automatically)
                    self._profile_manager.reset_to_first_profile()
                    logger.info("[NSTApproach] Profile index reset to 0 (ready for next run)")

                    break  # Exit loop - user will restart if they want another round

                # Brief pause between profiles
                logger.info("[NSTApproach] Waiting 5 seconds before next profile...")
                time.sleep(5)

            # Display multi-profile summary
            logger.info("[NSTApproach] ═══════════════════════════════════════════")
            logger.info("[NSTApproach] Multi-Profile Session Summary")
            logger.info("[NSTApproach] ═══════════════════════════════════════════")
            logger.info("[NSTApproach] Total profiles processed: %d", len(profile_results))
            logger.info("[NSTApproach] Total uploads this session: %d", total_successful_uploads)

            final_limit_status = self._state_manager.check_daily_limit(
                user_type=user_type,
                limit=daily_limit
            )
            logger.info("[NSTApproach] Global daily uploads: %d", final_limit_status['current_count'])

            for idx, pr in enumerate(profile_results, 1):
                logger.info("[NSTApproach]   %d. %s: %d upload(s)",
                           idx, pr['profile_name'], pr['uploads'])

            logger.info("[NSTApproach] ═══════════════════════════════════════════")

            result.creators_processed = total_successful_uploads
            result.success = True

        except Exception as e:
            logger.error("[NSTApproach] Multi-profile workflow error: %s", str(e))
            result.add_error(str(e))

        return result

    def _process_single_profile(self, profile_id: str, profile_name: str,
                                 client, user_type: str, daily_limit: int) -> int:
        """
        Process a single profile completely.

        Args:
            profile_id: Profile ID to process (string format for NSTbrowser)
            profile_name: Profile name
            client: NSTbrowser API client
            user_type: User type (basic/pro)
            daily_limit: Daily upload limit

        Returns:
            Number of successful uploads for this profile
        """
        upload_count = 0

        try:
            # Create browser launcher
            launcher = NSTBrowserLauncher(client)

            # Step 1: Launch Profile via API
            logger.info("[NSTApproach] ═══════════════════════════════════════════")
            logger.info("[NSTApproach] STEP 1: Launch Profile")
            logger.info("[NSTApproach] ═══════════════════════════════════════════")

            # Open profile using ProfileManager
            if not self._profile_manager.open_profile(launcher):
                logger.error("[NSTApproach] Failed to open profile: %s", profile_name)
                return 0

            # Get driver from ProfileManager
            driver = self._profile_manager.get_driver()
            if not driver:
                logger.error("[NSTApproach] Driver not available")
                self._profile_manager.close_profile()
                return 0

            logger.info("[NSTApproach] ✓ Profile opened and Selenium attached!")

            # IMPORTANT: Bring browser window to FRONT (always visible) - OS-LEVEL
            bring_browser_to_front(driver)

            # Step 3: Enumerate tabs and URLs
            logger.info("[NSTApproach] ═══════════════════════════════════════════")
            logger.info("[NSTApproach] STEP 3: Enumerate Browser Tabs")
            logger.info("[NSTApproach] ═══════════════════════════════════════════")

            try:
                # Get all window handles (tabs)
                all_tabs = driver.window_handles
                tab_count = len(all_tabs)

                logger.info("[NSTApproach] Total tabs open: %d", tab_count)

                # Store current tab to return to it later
                original_tab = driver.current_window_handle

                # Enumerate each tab
                for idx, tab_handle in enumerate(all_tabs, 1):
                    try:
                        # Switch to tab
                        driver.switch_to.window(tab_handle)

                        # Get URL
                        url = driver.current_url
                        title = driver.title

                        logger.info("[NSTApproach] Tab %d/%d:", idx, tab_count)
                        logger.info("[NSTApproach]   URL: %s", url)
                        logger.info("[NSTApproach]   Title: %s", title)
                    except Exception as e:
                        logger.warning("[NSTApproach] Tab %d: Error accessing - %s", idx, str(e))

                # Return to original tab
                driver.switch_to.window(original_tab)
                logger.info("[NSTApproach] ✓ Tab enumeration complete!")

            except Exception as e:
                logger.error("[NSTApproach] Failed to enumerate tabs: %s", str(e))

            # Step 4: Bookmark-Folder Comparison
            logger.info("[NSTApproach] ═══════════════════════════════════════════")
            logger.info("[NSTApproach] STEP 4: Bookmark-Folder Comparison")
            logger.info("[NSTApproach] ═══════════════════════════════════════════")

            try:
                # 1. Get Desktop path
                desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
                creators_base = os.path.join(desktop_path, "creators data")
                profile_folder = os.path.join(creators_base, profile_name)

                logger.info("[NSTApproach] Checking folders...")
                logger.info("[NSTApproach]   Desktop: %s", desktop_path)
                logger.info("[NSTApproach]   Creators base: %s", creators_base)
                logger.info("[NSTApproach]   Profile folder: %s", profile_folder)

                # 2. Check if folders exist
                if not os.path.exists(creators_base):
                    error_msg = f"'creators data' folder not found on Desktop: {creators_base}"
                    logger.error("[NSTApproach] %s", error_msg)
                    raise FileNotFoundError(error_msg)

                if not os.path.exists(profile_folder):
                    # Profile folder missing - SKIP this profile and continue
                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                    logger.warning("[NSTApproach] Profile Folder Not Found - SKIPPING")
                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                    logger.warning("[NSTApproach] Profile: %s", profile_name)
                    logger.warning("[NSTApproach] Expected path: %s", profile_folder)
                    logger.warning("[NSTApproach] Please create: Desktop/creators data/%s/", profile_name)
                    logger.warning("[NSTApproach] Skipping to next profile...")
                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")

                    # Don't throw error, just skip by not executing upload code
                    # Set flags to skip upload section
                    facebook_bookmarks = []
                    matched = []
                else:
                    # Profile folder exists - proceed with normal workflow

                    # 3. Get all creator folders (subfolders)
                    creator_folders = [
                        f for f in os.listdir(profile_folder)
                        if os.path.isdir(os.path.join(profile_folder, f))
                    ]
                    logger.info("[NSTApproach] ✓ Found %d creator folder(s)", len(creator_folders))

                    # 4. Open new tab for bookmarks
                    logger.info("[NSTApproach] Opening new tab...")
                    driver.execute_script("window.open('about:blank', '_blank');")
                    driver.switch_to.window(driver.window_handles[-1])
                    logger.info("[NSTApproach] ✓ New tab opened")

                    # 5. Navigate to bookmarks
                    logger.info("[NSTApproach] Accessing bookmarks...")
                    driver.get("chrome://bookmarks/")
                    time.sleep(2)

                    # 6. Get all bookmarks with titles and URLs
                    bookmark_script = """
                        return new Promise((resolve) => {
                            chrome.bookmarks.getTree((tree) => {
                                let bookmarks = [];
                                function extractBookmarks(nodes) {
                                    nodes.forEach(node => {
                                        if (node.url) {
                                            bookmarks.push({
                                                title: node.title,
                                                url: node.url
                                            });
                                        }
                                        if (node.children) {
                                            extractBookmarks(node.children);
                                        }
                                    });
                                }
                                extractBookmarks(tree);
                                resolve(bookmarks);
                            });
                        });
                    """

                    all_bookmarks = driver.execute_script(bookmark_script)
                    logger.info("[NSTApproach] ✓ Retrieved %d total bookmark(s)", len(all_bookmarks))

                    # 7. Filter Facebook bookmarks only
                    facebook_bookmarks = [
                        b for b in all_bookmarks
                        if "facebook.com" in b['url']
                    ]
                    logger.info("[NSTApproach] ✓ Filtered %d Facebook bookmark(s)", len(facebook_bookmarks))

                    # 8. Extract bookmark titles (creator names)
                    bookmark_names = [b['title'] for b in facebook_bookmarks]

                    # 9. Compare bookmarks with folders
                    matched = [name for name in bookmark_names if name in creator_folders]
                    missing = [name for name in bookmark_names if name not in creator_folders]
                    extra = [folder for folder in creator_folders if folder not in bookmark_names]

                    # 10. Console Output - Summary
                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                    logger.info("[NSTApproach] Bookmark-Folder Comparison Result")
                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                    logger.info("[NSTApproach] Profile: %s", profile_name)
                    logger.info("[NSTApproach] Creator Folder: %s", profile_folder)
                    logger.info("[NSTApproach] ")
                    logger.info("[NSTApproach] Total bookmarks: %d", len(all_bookmarks))
                    logger.info("[NSTApproach] Facebook bookmarks: %d", len(facebook_bookmarks))
                    logger.info("[NSTApproach] Matched folders: %d", len(matched))
                    logger.info("[NSTApproach] Missing folders: %d", len(missing))
                    logger.info("[NSTApproach] Extra folders: %d", len(extra))
                    logger.info("[NSTApproach] ")
                    logger.info("[NSTApproach] Details:")

                    # Show matched
                    for name in matched:
                        logger.info("[NSTApproach] ✓ %s - Folder exists", name)

                    # Show missing
                    for name in missing:
                        logger.info("[NSTApproach] ✗ %s - Folder missing", name)

                    # Show extra
                    for name in extra:
                        logger.info("[NSTApproach] ⚠ %s - Extra folder (no bookmark)", name)

                    logger.info("[NSTApproach] ═══════════════════════════════════════════")

            except FileNotFoundError as e:
                logger.error("[NSTApproach] %s", str(e))
                # Note: Errors logged but profile processing continues
            except Exception as e:
                logger.error("[NSTApproach] Bookmark-folder comparison failed: %s", str(e))
                # Note: Errors logged but profile processing continues

            # Step 5: Upload Videos to Bookmarks (Phase 2: With Queue & Resume)
            logger.info("[NSTApproach] ═══════════════════════════════════════════")
            logger.info("[NSTApproach] STEP 5: Upload Videos to Bookmarks (Phase 2)")
            logger.info("[NSTApproach] ═══════════════════════════════════════════")

            try:
                # Only proceed if we have matched bookmarks
                if not facebook_bookmarks:
                    logger.warning("[NSTApproach] No Facebook bookmarks found, skipping uploads")
                elif not matched:
                    logger.warning("[NSTApproach] No matched folders found, skipping uploads")
                else:
                    # Phase 2: Initialize folder queue manager
                    self._folder_queue = FolderQueueManager(
                        base_path=profile_folder,
                        state_manager=self._state_manager
                    )
                    # Force reset for each new profile (fresh start)
                    self._folder_queue.initialize_queue(force_reset=True)

                    # Phase 2: Detect total folders (for tracking/logging only)
                    all_folders = self._folder_queue.get_all_folders()
                    total_folders = len(all_folders)

                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                    logger.info("[NSTApproach] Folder Detection")
                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                    logger.info("[NSTApproach] Total creator folders detected: %d", total_folders)
                    logger.info("[NSTApproach] Upload mode: UNLIMITED")
                    logger.info("[NSTApproach] Bot will process all videos in all folders")
                    logger.info("[NSTApproach] Resume functionality: ENABLED")
                    logger.info("[NSTApproach] ═══════════════════════════════════════════")

                    # Phase 2: Check for resume
                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                    logger.info("[NSTApproach] Resume Check")
                    logger.info("[NSTApproach] ═══════════════════════════════════════════")

                    current_position = self._state_manager.get_current_position()
                    if current_position.get('current_upload', {}).get('video_file'):
                        logger.info("[NSTApproach] ✓ Found incomplete upload:")
                        logger.info("[NSTApproach]   Video: %s",
                                   current_position['current_upload'].get('video_name', 'unknown'))
                        logger.info("[NSTApproach]   Progress: %d%%",
                                   current_position['current_upload'].get('progress_last_seen', 0))
                        logger.info("[NSTApproach]   Attempt: %d",
                                   current_position['current_upload'].get('attempt', 0))
                        logger.info("[NSTApproach] Bot will resume from this position")
                    else:
                        logger.info("[NSTApproach] No incomplete uploads found - starting fresh")

                    logger.info("[NSTApproach] ═══════════════════════════════════════════")

                    # Phase 2: Check daily limit (Basic vs Pro user)
                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                    logger.info("[NSTApproach] Daily Limit Check")
                    logger.info("[NSTApproach] ═══════════════════════════════════════════")

                    limit_status = self._state_manager.check_daily_limit(
                        user_type=user_type,
                        limit=daily_limit
                    )

                    logger.info("[NSTApproach] User Type: %s", user_type.upper())
                    logger.info("[NSTApproach] %s", limit_status['message'])

                    # If limit reached for basic users, log warning and skip (don't throw exception)
                    if limit_status['limit_reached']:
                        logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                        logger.warning("[NSTApproach] DAILY LIMIT REACHED - Skipping Profile")
                        logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                        logger.warning("[NSTApproach] User: %s", user_type.upper())
                        logger.warning("[NSTApproach] Uploaded today: %d bookmarks", limit_status['current_count'])
                        logger.warning("[NSTApproach] Daily limit: %d bookmarks", limit_status['limit'])
                        logger.warning("[NSTApproach] ")
                        logger.warning("[NSTApproach] Skipping upload processing for this profile.")
                        logger.warning("[NSTApproach] Please wait until tomorrow to upload more videos.")
                        logger.warning("[NSTApproach] Or upgrade to PRO for unlimited uploads!")
                        logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                        # Note: upload_count stays 0, profile will be closed, multi-profile loop continues
                        upload_count = 0  # Explicitly set to 0 and skip upload section
                    else:
                        # Limit not reached - proceed with normal upload workflow
                        logger.info("[NSTApproach] ═══════════════════════════════════════════")

                        # Phase 2: Initialize upload helper with Phase 2 components
                        upload_helper = VideoUploadHelper(
                            driver,
                            state_manager=self._state_manager,
                            network_monitor=self._network_monitor
                        )

                        # Phase 2: Start network monitoring
                        self._network_monitor.start_monitoring()
                        logger.info("[NSTApproach] ✓ Network monitoring started")

                        upload_results = []
                        total_uploads_this_run = 0

                        logger.info("[NSTApproach] Starting folder processing...")
                        logger.info("[NSTApproach] User type: %s", user_type.upper())
                        if user_type.lower() == 'pro':
                            logger.info("[NSTApproach] Upload mode: UNLIMITED (Pro user)")
                        else:
                            logger.info("[NSTApproach] Upload mode: %d/%d bookmarks today",
                                       limit_status['current_count'], limit_status['limit'])
                        logger.info("[NSTApproach] Processing one folder at a time")
                        logger.info("[NSTApproach] Press Ctrl+C to stop bot (state will be saved)")
                        logger.info("[NSTApproach] ")

                        # Track if we found any videos in current cycle (to detect empty profile)
                        starting_cycle = self._folder_queue.get_cycle_count()
                        folders_checked_in_cycle = 0
                        total_folders = len(all_folders)

                        # Phase 2: Process folders one at a time (unlimited - no limit)
                        # Bot will continue until user stops it or all folders are processed
                        while True:
                            # Get current folder from queue
                            current_folder = self._folder_queue.get_current_folder()
                            if not current_folder:
                                logger.warning("[NSTApproach] No folders in queue, stopping")
                                break

                            folder_name = os.path.basename(current_folder)

                            # Check if this folder has a matching bookmark
                            matching_bookmark = None
                            for bookmark in facebook_bookmarks:
                                if bookmark['title'] == folder_name:
                                    matching_bookmark = bookmark
                                    break

                            if not matching_bookmark:
                                logger.info("[NSTApproach] Folder '%s' has no bookmark, skipping", folder_name)
                                self._folder_queue.move_to_next_folder()
                                continue

                            # Get videos in folder (excludes 'uploaded videos' subfolder)
                            videos = self._folder_queue.get_videos_in_folder(current_folder)

                            if not videos:
                                logger.info("[NSTApproach] ───────────────────────────────────────────────")
                                logger.info("[NSTApproach] Folder: %s", folder_name)
                                logger.info("[NSTApproach] Status: No videos remaining (all uploaded or empty)")
                                logger.info("[NSTApproach] ───────────────────────────────────────────────")

                                # Mark folder complete and move to next
                                self._folder_queue.mark_current_folder_complete()
                                self._folder_queue.move_to_next_folder()

                                # Track empty folders
                                folders_checked_in_cycle += 1

                                # Check if we've gone through ALL folders without finding videos
                                if folders_checked_in_cycle >= total_folders:
                                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                                    logger.info("[NSTApproach] Profile Complete - No Videos Found")
                                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                                    logger.info("[NSTApproach] Checked all %d folders", total_folders)
                                    logger.info("[NSTApproach] No videos remaining in any folder")
                                    logger.info("[NSTApproach] This profile is complete!")
                                    logger.info("[NSTApproach] ═══════════════════════════════════════════")
                                    break  # Exit upload loop - profile complete

                                continue

                            # Reset counter - we found videos!
                            folders_checked_in_cycle = 0

                            # Check daily limit BEFORE uploading (for basic users)
                            if user_type.lower() == 'basic':
                                current_limit_check = self._state_manager.check_daily_limit(
                                    user_type=user_type,
                                    limit=daily_limit
                                )

                                if current_limit_check['limit_reached']:
                                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                                    logger.warning("[NSTApproach] DAILY LIMIT REACHED!")
                                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                                    logger.warning("[NSTApproach] Uploaded today: %d/%d bookmarks",
                                                 current_limit_check['current_count'],
                                                 current_limit_check['limit'])
                                    logger.warning("[NSTApproach] Daily limit reached during upload session.")
                                    logger.warning("[NSTApproach] Please wait until tomorrow.")
                                    logger.warning("[NSTApproach] ═══════════════════════════════════════════")
                                    break  # Exit upload loop

                            # Process this folder
                            logger.info("[NSTApproach] ───────────────────────────────────────────────")
                            logger.info("[NSTApproach] Processing: %s", folder_name)
                            logger.info("[NSTApproach] Videos remaining: %d", len(videos))
                            logger.info("[NSTApproach] Current cycle: #%d", self._folder_queue.get_cycle_count())
                            if user_type.lower() == 'basic':
                                logger.info("[NSTApproach] Daily usage: %d/%d bookmarks",
                                           current_limit_check['current_count'],
                                           current_limit_check['limit'])
                            logger.info("[NSTApproach] ───────────────────────────────────────────────")

                            # Upload video to bookmark (uploads ONE video per call)
                            success = upload_helper.upload_to_bookmark(matching_bookmark, current_folder)

                            upload_results.append({
                                'bookmark': folder_name,
                                'success': success
                            })

                            total_uploads_this_run += 1

                            if success:
                                logger.info("[NSTApproach] ✓ Upload successful")

                                # Increment daily counter after successful upload
                                # Pass bookmark name for per-bookmark tracking and deduplication
                                self._state_manager.increment_daily_bookmarks(count=1, bookmark_name=folder_name)
                                logger.debug("[NSTApproach] Daily bookmark counter updated for '%s'", folder_name)

                                # Brief pause between uploads
                                logger.info("[NSTApproach] Waiting 5 seconds before next upload...")
                                time.sleep(5)

                                # Check if folder has more videos
                                remaining = self._folder_queue.get_videos_in_folder(current_folder)
                                if not remaining:
                                    # Folder complete - move to next
                                    logger.info("[NSTApproach] ✓ Folder '%s' complete (no videos remaining)", folder_name)
                                    self._folder_queue.mark_current_folder_complete()
                                    self._folder_queue.move_to_next_folder()
                                else:
                                    logger.info("[NSTApproach] Folder '%s' has %d video(s) remaining", folder_name, len(remaining))
                                    # Continue with same folder (will upload next video)
                            else:
                                logger.error("[NSTApproach] ✗ Upload failed")
                                # Failed upload (video already deleted by upload_helper after 3 retries)
                                # Move to next video in same folder
                                continue

                        # Phase 2: Stop network monitoring
                        self._network_monitor.stop_monitoring()

                        # Calculate summary statistics
                        successful = sum(1 for r in upload_results if r['success'])
                        failed = sum(1 for r in upload_results if not r['success'])

                        # Display upload summary for this profile
                        logger.info("[NSTApproach] ═══════════════════════════════════════════")
                        logger.info("[NSTApproach] Profile Upload Summary: %s", profile_name)
                        logger.info("[NSTApproach] ═══════════════════════════════════════════")
                        logger.info("[NSTApproach] Total uploads attempted: %d", len(upload_results))
                        logger.info("[NSTApproach] Successful: %d", successful)
                        logger.info("[NSTApproach] Failed: %d", failed)
                        logger.info("[NSTApproach] Current queue position:")
                        queue_status = self._folder_queue.get_queue_status()
                        logger.info("[NSTApproach]   Folder: %d/%d", queue_status['current_index'] + 1, queue_status['total_folders'])
                        logger.info("[NSTApproach]   Cycle: #%d", queue_status['cycle'])
                        logger.info("[NSTApproach] ═══════════════════════════════════════════")

                        # Track upload count for this profile
                        upload_count = successful

            except Exception as e:
                logger.error("[NSTApproach] Video upload failed: %s", str(e))
                # Stop network monitor on error
                if self._network_monitor:
                    self._network_monitor.stop_monitoring()

            # Step 6: Close Profile
            logger.info("[NSTApproach] ═══════════════════════════════════════════")
            logger.info("[NSTApproach] STEP 6: Close Profile")
            logger.info("[NSTApproach] ═══════════════════════════════════════════")

            # Close profile using ProfileManager
            self._profile_manager.close_profile()
            logger.info("[NSTApproach] ✓ Profile closed successfully")

        except Exception as e:
            logger.error("[NSTApproach] Profile processing failed: %s", str(e))
            # Try to close profile on error
            if self._profile_manager:
                try:
                    self._profile_manager.close_profile()
                except:
                    pass

        return upload_count

    def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("[NSTApproach] Cleaning up resources...")

        try:
            # Stop network monitor
            if self._network_monitor:
                self._network_monitor.stop_monitoring()

            # Disconnect from API
            if self._connection_manager:
                self._connection_manager.disconnect()

            logger.info("[NSTApproach] ✓ Cleanup complete")

        except Exception as e:
            logger.error("[NSTApproach] Error during cleanup: %s", str(e))


# Export for factory registration
__all__ = ['NSTBrowserApproach']
