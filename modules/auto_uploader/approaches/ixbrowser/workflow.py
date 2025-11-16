"""
ixBrowser Automation Workflow
Complete integration using official ixbrowser-local-api library
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
from .config_handler import IXBrowserConfig
from .connection_manager import ConnectionManager
from .browser_launcher import BrowserLauncher
from .upload_helper import VideoUploadHelper
from .window_manager import bring_window_to_front_windows, maximize_window_windows

# Phase 2: Import robustness components
from .core.state_manager import StateManager
from .core.network_monitor import NetworkMonitor
from .core.folder_queue import FolderQueueManager
from .core.profile_manager import ProfileManager
from .config.upload_config import USER_CONFIG

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
class IXAutomationContext:
    """Holds state for a specific ixBrowser session."""

    profile_id: int
    launcher: BrowserLauncher
    login_manager: Optional[object] = None  # Not used anymore


class IXBrowserApproach(BaseApproach):
    """
    ixBrowser approach using official ixbrowser-local-api library.

    Features:
    - Automatic desktop app launch
    - Programmatic browser control via API
    - Selenium WebDriver integration
    - Profile management
    """

    def __init__(self, config: ApproachConfig) -> None:
        super().__init__(config)

        logger.info("[IXApproach] Initializing ixBrowser approach...")

        # Initialize components
        self._config_handler: Optional[IXBrowserConfig] = None
        self._connection_manager: Optional[ConnectionManager] = None
        self._current_context: Optional[IXAutomationContext] = None

        # Phase 2: Initialize robustness components
        self._state_manager = StateManager()
        self._network_monitor = NetworkMonitor(check_interval=10)
        self._folder_queue: Optional[FolderQueueManager] = None
        self._profile_manager: Optional[ProfileManager] = None

        logger.info("[IXApproach] ✓ Phase 2 robustness components initialized")

        # Load configuration
        self._setup_configuration(config)

    def _setup_configuration(self, config: ApproachConfig) -> None:
        """Setup configuration from ApproachConfig."""
        logger.info("[IXApproach] Setting up configuration...")

        credentials = config.credentials or {}

        # Get ixBrowser API credentials (not Facebook!)
        base_url = (
            credentials.get("base_url")
            or credentials.get("api_url")
            or "http://127.0.0.1:53200"
        )

        email = credentials.get("email", "")
        password = credentials.get("password", "")

        # Initialize config handler
        self._config_handler = IXBrowserConfig()

        # Check if we have credentials in config
        if email and password:
            logger.info("[IXApproach] Using ixBrowser credentials from ApproachConfig")
            self._config_handler.set_credentials(base_url, email, password)
        elif self._config_handler.is_configured():
            logger.info("[IXApproach] Using saved ixBrowser credentials from config file")
        else:
            logger.warning("[IXApproach] No ixBrowser credentials configured!")
            logger.warning("[IXApproach] Please provide base_url, email, password in approach config")

    # ------------------------------------------------------------------ #
    # BaseApproach contract                                              #
    # ------------------------------------------------------------------ #
    def initialize(self) -> bool:
        """Initialize connection to ixBrowser API."""
        logger.info("[IXApproach] Initializing connection...")

        if not self._config_handler or not self._config_handler.is_configured():
            logger.error("[IXApproach] Configuration incomplete!")
            logger.error("[IXApproach] Required: base_url, email, password for ixBrowser")
            return False

        # Get configuration
        base_url = self._config_handler.get_base_url()
        email = self._config_handler.get_email()
        password = self._config_handler.get_password()

        logger.info("[IXApproach] Connecting to: %s", base_url)

        # Initialize connection manager (with auto-launch and auto-login)
        self._connection_manager = ConnectionManager(
            base_url=base_url,
            auto_launch=True,
            email=email,
            password=password
        )

        # Attempt connection (will auto-launch ixBrowser and auto-login if needed)
        if not self._connection_manager.connect():
            logger.error("[IXApproach] Failed to connect to ixBrowser API!")
            return False

        logger.info("[IXApproach] ✓ Connection established successfully!")
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
    # Main workflow                                                      #
    # ------------------------------------------------------------------ #
    def execute_workflow(self, work_item: WorkItem) -> WorkflowResult:
        """
        Execute complete ixBrowser workflow.

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
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 0: Initializing Approach")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            if not self.initialize():
                result.add_error("Initialization failed")
                return result

            self._initialized = True
            logger.info("[IXApproach] ✓ Initialization successful!")

        # Check connection
        if not self._connection_manager or not self._connection_manager.is_connected():
            result.add_error("Not connected to ixBrowser API.")
            return result

        # Get client
        client = self._connection_manager.get_client()
        if not client:
            result.add_error("Failed to get API client.")
            return result

        # Phase 2A: Initialize ProfileManager
        logger.info("[IXApproach] ═══════════════════════════════════════════")
        logger.info("[IXApproach] Phase 2A: Multi-Profile Support")
        logger.info("[IXApproach] ═══════════════════════════════════════════")

        self._profile_manager = ProfileManager(
            connection_manager=self._connection_manager,
            state_manager=self._state_manager
        )

        # Fetch ALL profiles from ixBrowser (unlimited)
        all_profiles = self._profile_manager.fetch_profiles()

        if not all_profiles:
            result.add_error("No profiles found in ixBrowser. Please create a profile first.")
            return result

        logger.info("[IXApproach] ✓ Multi-profile mode enabled")
        logger.info("[IXApproach] ✓ Total profiles: %d", len(all_profiles))
        logger.info("[IXApproach] ✓ Bot will process ALL profiles sequentially")

        # Load profile state (for crash recovery)
        self._profile_manager.load_state()

        # Check global daily limit BEFORE starting
        logger.info("[IXApproach] ═══════════════════════════════════════════")
        logger.info("[IXApproach] Global Daily Limit Check")
        logger.info("[IXApproach] ═══════════════════════════════════════════")

        user_type = USER_CONFIG.get('user_type', 'basic')
        daily_limit = USER_CONFIG.get('daily_limit_basic', 200)

        initial_limit_status = self._state_manager.check_daily_limit(
            user_type=user_type,
            limit=daily_limit
        )

        logger.info("[IXApproach] User Type: %s", user_type.upper())
        logger.info("[IXApproach] %s", initial_limit_status['message'])

        # If limit already reached, stop here
        if initial_limit_status['limit_reached']:
            logger.warning("[IXApproach] ═══════════════════════════════════════════")
            logger.warning("[IXApproach] GLOBAL DAILY LIMIT ALREADY REACHED!")
            logger.warning("[IXApproach] ═══════════════════════════════════════════")
            logger.warning("[IXApproach] Uploaded today: %d bookmarks", initial_limit_status['current_count'])
            logger.warning("[IXApproach] Daily limit: %d bookmarks", initial_limit_status['limit'])
            logger.warning("[IXApproach] Please wait until tomorrow to upload more videos.")
            logger.warning("[IXApproach] ═══════════════════════════════════════════")
            result.add_error("Global daily limit already reached")
            return result

        logger.info("[IXApproach] ═══════════════════════════════════════════")

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
                    logger.warning("[IXApproach] ═══════════════════════════════════════════")
                    logger.warning("[IXApproach] GLOBAL DAILY LIMIT REACHED!")
                    logger.warning("[IXApproach] ═══════════════════════════════════════════")
                    logger.warning("[IXApproach] Uploaded today: %d/%d bookmarks",
                                 current_limit_status['current_count'],
                                 current_limit_status['limit'])
                    logger.warning("[IXApproach] Stopping all profile processing")
                    logger.warning("[IXApproach] ═══════════════════════════════════════════")
                    break

                # Get current profile
                current_profile = self._profile_manager.get_current_profile()
                if not current_profile:
                    logger.error("[IXApproach] No current profile available")
                    break

                profile_id = current_profile.get('profile_id')
                profile_name = current_profile.get('name', 'Unknown')
                profile_info = self._profile_manager.get_current_profile_info()

                logger.info("[IXApproach] ═══════════════════════════════════════════")
                logger.info("[IXApproach] PROCESSING PROFILE %d/%d",
                           profile_info['index'], profile_info['total'])
                logger.info("[IXApproach] ═══════════════════════════════════════════")
                logger.info("[IXApproach] Profile: %s (ID: %s)", profile_name, profile_id)
                logger.info("[IXApproach] Global uploads today: %d",
                           current_limit_status['current_count'])
                if user_type.lower() == 'basic':
                    logger.info("[IXApproach] Remaining: %d/%d",
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
                    logger.warning("[IXApproach] ═══════════════════════════════════════════")
                    logger.warning("[IXApproach] Daily limit reached after profile: %s", profile_name)
                    logger.warning("[IXApproach] Stopping multi-profile processing")
                    logger.warning("[IXApproach] ═══════════════════════════════════════════")
                    break

                # Move to next profile
                has_more = self._profile_manager.move_to_next_profile()
                if not has_more:
                    # All profiles processed - round complete, stop here
                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                    logger.info("[IXApproach] ROUND COMPLETE!")
                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                    logger.info("[IXApproach] All profiles have been processed")

                    # Check daily limit status to inform user
                    round_limit_status = self._state_manager.check_daily_limit(
                        user_type=user_type,
                        limit=daily_limit
                    )

                    logger.info("[IXApproach] User type: %s", user_type.upper())
                    if user_type.lower() == 'basic':
                        logger.info("[IXApproach] Daily usage: %d/%d bookmarks",
                                   round_limit_status['current_count'],
                                   round_limit_status['limit'])
                        logger.info("[IXApproach] Remaining: %d uploads",
                                   round_limit_status['remaining'])
                    else:
                        logger.info("[IXApproach] Pro user - unlimited uploads")

                    # Show appropriate message based on limit status
                    if round_limit_status['limit_reached']:
                        logger.info("[IXApproach] ")
                        logger.info("[IXApproach] ⚠ DAILY LIMIT REACHED!")
                        logger.info("[IXApproach] Please wait until tomorrow or upgrade to PRO")
                    else:
                        logger.info("[IXApproach] ")
                        logger.info("[IXApproach] ✓ Round completed successfully!")
                        logger.info("[IXApproach] You can start another round if you want")

                    logger.info("[IXApproach] ═══════════════════════════════════════════")

                    # Reset to first profile for next run (but don't continue automatically)
                    self._profile_manager.reset_to_first_profile()
                    logger.info("[IXApproach] Profile index reset to 0 (ready for next run)")

                    break  # Exit loop - user will restart if they want another round

                # Brief pause between profiles
                logger.info("[IXApproach] Waiting 5 seconds before next profile...")
                time.sleep(5)

            # Display multi-profile summary
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] Multi-Profile Session Summary")
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] Total profiles processed: %d", len(profile_results))
            logger.info("[IXApproach] Total uploads this session: %d", total_successful_uploads)

            final_limit_status = self._state_manager.check_daily_limit(
                user_type=user_type,
                limit=daily_limit
            )
            logger.info("[IXApproach] Global daily uploads: %d", final_limit_status['current_count'])

            for idx, pr in enumerate(profile_results, 1):
                logger.info("[IXApproach]   %d. %s: %d upload(s)",
                           idx, pr['profile_name'], pr['uploads'])

            logger.info("[IXApproach] ═══════════════════════════════════════════")

            result.creators_processed = total_successful_uploads
            result.success = True

        except Exception as e:
            logger.error("[IXApproach] Multi-profile workflow error: %s", str(e))
            result.add_error(str(e))

        return result

    def _process_single_profile(self, profile_id: int, profile_name: str,
                                 client, user_type: str, daily_limit: int) -> int:
        """
        Process a single profile completely.

        Args:
            profile_id: Profile ID to process
            profile_name: Profile name
            client: ixBrowser API client
            user_type: User type (basic/pro)
            daily_limit: Daily upload limit

        Returns:
            Number of successful uploads for this profile
        """
        upload_count = 0

        try:
            # Create browser launcher
            launcher = BrowserLauncher(client)

            # Step 1: Launch Profile via API
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 1: Launch Profile")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            # Open profile using ProfileManager
            if not self._profile_manager.open_profile(launcher):
                logger.error("[IXApproach] Failed to open profile: %s", profile_name)
                return 0

            # Get driver from ProfileManager
            driver = self._profile_manager.get_driver()
            if not driver:
                logger.error("[IXApproach] Driver not available")
                self._profile_manager.close_profile()
                return 0

            logger.info("[IXApproach] ✓ Profile opened and Selenium attached!")

            # IMPORTANT: Bring browser window to FRONT (always visible) - OS-LEVEL
            bring_browser_to_front(driver)

            # Step 3: Enumerate tabs and URLs
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 3: Enumerate Browser Tabs")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            try:
                # Get all window handles (tabs)
                all_tabs = driver.window_handles
                tab_count = len(all_tabs)

                logger.info("[IXApproach] Total tabs open: %d", tab_count)

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

                        logger.info("[IXApproach] Tab %d/%d:", idx, tab_count)
                        logger.info("[IXApproach]   URL: %s", url)
                        logger.info("[IXApproach]   Title: %s", title)
                    except Exception as e:
                        logger.warning("[IXApproach] Tab %d: Error accessing - %s", idx, str(e))

                # Return to original tab
                driver.switch_to.window(original_tab)
                logger.info("[IXApproach] ✓ Tab enumeration complete!")

            except Exception as e:
                logger.error("[IXApproach] Failed to enumerate tabs: %s", str(e))

            # Step 4: Bookmark-Folder Comparison
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 4: Bookmark-Folder Comparison")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            try:
                # 1. Get Desktop path
                desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
                creators_base = os.path.join(desktop_path, "creators data")
                profile_folder = os.path.join(creators_base, profile_name)

                logger.info("[IXApproach] Checking folders...")
                logger.info("[IXApproach]   Desktop: %s", desktop_path)
                logger.info("[IXApproach]   Creators base: %s", creators_base)
                logger.info("[IXApproach]   Profile folder: %s", profile_folder)

                # 2. Check if folders exist
                if not os.path.exists(creators_base):
                    error_msg = f"'creators data' folder not found on Desktop: {creators_base}"
                    logger.error("[IXApproach] %s", error_msg)
                    raise FileNotFoundError(error_msg)

                if not os.path.exists(profile_folder):
                    # Profile folder missing - SKIP this profile and continue
                    logger.warning("[IXApproach] ═══════════════════════════════════════════")
                    logger.warning("[IXApproach] Profile Folder Not Found - SKIPPING")
                    logger.warning("[IXApproach] ═══════════════════════════════════════════")
                    logger.warning("[IXApproach] Profile: %s", profile_name)
                    logger.warning("[IXApproach] Expected path: %s", profile_folder)
                    logger.warning("[IXApproach] Please create: Desktop/creators data/%s/", profile_name)
                    logger.warning("[IXApproach] Skipping to next profile...")
                    logger.warning("[IXApproach] ═══════════════════════════════════════════")

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
                    logger.info("[IXApproach] ✓ Found %d creator folder(s)", len(creator_folders))

                    # 4. Open new tab for bookmarks
                    logger.info("[IXApproach] Opening new tab...")
                    driver.execute_script("window.open('about:blank', '_blank');")
                    driver.switch_to.window(driver.window_handles[-1])
                    logger.info("[IXApproach] ✓ New tab opened")

                    # 5. Navigate to bookmarks
                    logger.info("[IXApproach] Accessing bookmarks...")
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
                    logger.info("[IXApproach] ✓ Retrieved %d total bookmark(s)", len(all_bookmarks))

                    # 7. Filter Facebook bookmarks only
                    facebook_bookmarks = [
                        b for b in all_bookmarks
                        if "facebook.com" in b['url']
                    ]
                    logger.info("[IXApproach] ✓ Filtered %d Facebook bookmark(s)", len(facebook_bookmarks))

                    # 8. Extract bookmark titles (creator names)
                    bookmark_names = [b['title'] for b in facebook_bookmarks]

                    # 9. Compare bookmarks with folders
                    matched = [name for name in bookmark_names if name in creator_folders]
                    missing = [name for name in bookmark_names if name not in creator_folders]
                    extra = [folder for folder in creator_folders if folder not in bookmark_names]

                    # 10. Console Output - Summary
                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                    logger.info("[IXApproach] Bookmark-Folder Comparison Result")
                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                    logger.info("[IXApproach] Profile: %s", profile_name)
                    logger.info("[IXApproach] Creator Folder: %s", profile_folder)
                    logger.info("[IXApproach] ")
                    logger.info("[IXApproach] Total bookmarks: %d", len(all_bookmarks))
                    logger.info("[IXApproach] Facebook bookmarks: %d", len(facebook_bookmarks))
                    logger.info("[IXApproach] Matched folders: %d", len(matched))
                    logger.info("[IXApproach] Missing folders: %d", len(missing))
                    logger.info("[IXApproach] Extra folders: %d", len(extra))
                    logger.info("[IXApproach] ")
                    logger.info("[IXApproach] Details:")

                    # Show matched
                    for name in matched:
                        logger.info("[IXApproach] ✓ %s - Folder exists", name)

                    # Show missing
                    for name in missing:
                        logger.info("[IXApproach] ✗ %s - Folder missing", name)

                    # Show extra
                    for name in extra:
                        logger.info("[IXApproach] ⚠ %s - Extra folder (no bookmark)", name)

                    logger.info("[IXApproach] ═══════════════════════════════════════════")

            except FileNotFoundError as e:
                logger.error("[IXApproach] %s", str(e))
                # Note: Errors logged but profile processing continues
            except Exception as e:
                logger.error("[IXApproach] Bookmark-folder comparison failed: %s", str(e))
                # Note: Errors logged but profile processing continues

            # Step 5: Upload Videos to Bookmarks (Phase 2: With Queue & Resume)
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 5: Upload Videos to Bookmarks (Phase 2)")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            try:
                # Only proceed if we have matched bookmarks
                if not facebook_bookmarks:
                    logger.warning("[IXApproach] No Facebook bookmarks found, skipping uploads")
                elif not matched:
                    logger.warning("[IXApproach] No matched folders found, skipping uploads")
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

                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                    logger.info("[IXApproach] Folder Detection")
                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                    logger.info("[IXApproach] Total creator folders detected: %d", total_folders)
                    logger.info("[IXApproach] Upload mode: UNLIMITED")
                    logger.info("[IXApproach] Bot will process all videos in all folders")
                    logger.info("[IXApproach] Resume functionality: ENABLED")
                    logger.info("[IXApproach] ═══════════════════════════════════════════")

                    # Phase 2: Check for resume
                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                    logger.info("[IXApproach] Resume Check")
                    logger.info("[IXApproach] ═══════════════════════════════════════════")

                    current_position = self._state_manager.get_current_position()
                    if current_position.get('current_upload', {}).get('video_file'):
                        logger.info("[IXApproach] ✓ Found incomplete upload:")
                        logger.info("[IXApproach]   Video: %s",
                                   current_position['current_upload'].get('video_name', 'unknown'))
                        logger.info("[IXApproach]   Progress: %d%%",
                                   current_position['current_upload'].get('progress_last_seen', 0))
                        logger.info("[IXApproach]   Attempt: %d",
                                   current_position['current_upload'].get('attempt', 0))
                        logger.info("[IXApproach] Bot will resume from this position")
                    else:
                        logger.info("[IXApproach] No incomplete uploads found - starting fresh")

                    logger.info("[IXApproach] ═══════════════════════════════════════════")

                    # Phase 2: Check daily limit (Basic vs Pro user)
                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                    logger.info("[IXApproach] Daily Limit Check")
                    logger.info("[IXApproach] ═══════════════════════════════════════════")

                    user_type = USER_CONFIG.get('user_type', 'basic')
                    daily_limit = USER_CONFIG.get('daily_limit_basic', 200)

                    limit_status = self._state_manager.check_daily_limit(
                        user_type=user_type,
                        limit=daily_limit
                    )

                    logger.info("[IXApproach] User Type: %s", user_type.upper())
                    logger.info("[IXApproach] %s", limit_status['message'])

                    # If limit reached for basic users, log warning and skip (don't throw exception)
                    if limit_status['limit_reached']:
                        logger.warning("[IXApproach] ═══════════════════════════════════════════")
                        logger.warning("[IXApproach] DAILY LIMIT REACHED - Skipping Profile")
                        logger.warning("[IXApproach] ═══════════════════════════════════════════")
                        logger.warning("[IXApproach] User: %s", user_type.upper())
                        logger.warning("[IXApproach] Uploaded today: %d bookmarks", limit_status['current_count'])
                        logger.warning("[IXApproach] Daily limit: %d bookmarks", limit_status['limit'])
                        logger.warning("[IXApproach] ")
                        logger.warning("[IXApproach] Skipping upload processing for this profile.")
                        logger.warning("[IXApproach] Please wait until tomorrow to upload more videos.")
                        logger.warning("[IXApproach] Or upgrade to PRO for unlimited uploads!")
                        logger.warning("[IXApproach] ═══════════════════════════════════════════")
                        # Note: upload_count stays 0, profile will be closed, multi-profile loop continues
                        upload_count = 0  # Explicitly set to 0 and skip upload section
                    else:
                        # Limit not reached - proceed with normal upload workflow
                        logger.info("[IXApproach] ═══════════════════════════════════════════")

                        # Phase 2: Initialize upload helper with Phase 2 components
                        upload_helper = VideoUploadHelper(
                            driver,
                            state_manager=self._state_manager,
                            network_monitor=self._network_monitor
                        )

                        # Phase 2: Start network monitoring
                        self._network_monitor.start_monitoring()
                        logger.info("[IXApproach] ✓ Network monitoring started")

                        upload_results = []
                        total_uploads_this_run = 0

                        logger.info("[IXApproach] Starting folder processing...")
                        logger.info("[IXApproach] User type: %s", user_type.upper())
                        if user_type.lower() == 'pro':
                            logger.info("[IXApproach] Upload mode: UNLIMITED (Pro user)")
                        else:
                            logger.info("[IXApproach] Upload mode: %d/%d bookmarks today",
                                       limit_status['current_count'], limit_status['limit'])
                        logger.info("[IXApproach] Processing one folder at a time")
                        logger.info("[IXApproach] Press Ctrl+C to stop bot (state will be saved)")
                        logger.info("[IXApproach] ")

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
                                logger.warning("[IXApproach] No folders in queue, stopping")
                                break

                            folder_name = os.path.basename(current_folder)

                            # Check if this folder has a matching bookmark
                            matching_bookmark = None
                            for bookmark in facebook_bookmarks:
                                if bookmark['title'] == folder_name:
                                    matching_bookmark = bookmark
                                    break

                            if not matching_bookmark:
                                logger.info("[IXApproach] Folder '%s' has no bookmark, skipping", folder_name)
                                self._folder_queue.move_to_next_folder()
                                continue

                            # Get videos in folder (excludes 'uploaded videos' subfolder)
                            videos = self._folder_queue.get_videos_in_folder(current_folder)

                            if not videos:
                                logger.info("[IXApproach] ───────────────────────────────────────────────")
                                logger.info("[IXApproach] Folder: %s", folder_name)
                                logger.info("[IXApproach] Status: No videos remaining (all uploaded or empty)")
                                logger.info("[IXApproach] ───────────────────────────────────────────────")

                                # Mark folder complete and move to next
                                self._folder_queue.mark_current_folder_complete()
                                self._folder_queue.move_to_next_folder()

                                # Track empty folders
                                folders_checked_in_cycle += 1

                                # Check if we've gone through ALL folders without finding videos
                                if folders_checked_in_cycle >= total_folders:
                                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                                    logger.info("[IXApproach] Profile Complete - No Videos Found")
                                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                                    logger.info("[IXApproach] Checked all %d folders", total_folders)
                                    logger.info("[IXApproach] No videos remaining in any folder")
                                    logger.info("[IXApproach] This profile is complete!")
                                    logger.info("[IXApproach] ═══════════════════════════════════════════")
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
                                    logger.warning("[IXApproach] ═══════════════════════════════════════════")
                                    logger.warning("[IXApproach] DAILY LIMIT REACHED!")
                                    logger.warning("[IXApproach] ═══════════════════════════════════════════")
                                    logger.warning("[IXApproach] Uploaded today: %d/%d bookmarks",
                                                 current_limit_check['current_count'],
                                                 current_limit_check['limit'])
                                    logger.warning("[IXApproach] Daily limit reached during upload session.")
                                    logger.warning("[IXApproach] Please wait until tomorrow.")
                                    logger.warning("[IXApproach] ═══════════════════════════════════════════")
                                    break  # Exit upload loop

                            # Process this folder
                            logger.info("[IXApproach] ───────────────────────────────────────────────")
                            logger.info("[IXApproach] Processing: %s", folder_name)
                            logger.info("[IXApproach] Videos remaining: %d", len(videos))
                            logger.info("[IXApproach] Current cycle: #%d", self._folder_queue.get_cycle_count())
                            if user_type.lower() == 'basic':
                                logger.info("[IXApproach] Daily usage: %d/%d bookmarks",
                                           current_limit_check['current_count'],
                                           current_limit_check['limit'])
                            logger.info("[IXApproach] ───────────────────────────────────────────────")

                            # Upload video to bookmark (uploads ONE video per call)
                            success = upload_helper.upload_to_bookmark(matching_bookmark, current_folder)

                            upload_results.append({
                                'bookmark': folder_name,
                                'success': success
                            })

                            total_uploads_this_run += 1

                            if success:
                                logger.info("[IXApproach] ✓ Upload successful")

                                # Increment daily counter after successful upload
                                self._state_manager.increment_daily_bookmarks(count=1)
                                logger.debug("[IXApproach] Daily bookmark counter incremented")

                                # Brief pause between uploads
                                logger.info("[IXApproach] Waiting 5 seconds before next upload...")
                                time.sleep(5)

                                # Check if folder has more videos
                                remaining = self._folder_queue.get_videos_in_folder(current_folder)
                                if not remaining:
                                    # Folder complete - move to next
                                    logger.info("[IXApproach] ✓ Folder '%s' complete (no videos remaining)", folder_name)
                                    self._folder_queue.mark_current_folder_complete()
                                    self._folder_queue.move_to_next_folder()
                                else:
                                    logger.info("[IXApproach] Folder '%s' has %d video(s) remaining", folder_name, len(remaining))
                                    # Continue with same folder (will upload next video)
                            else:
                                logger.error("[IXApproach] ✗ Upload failed")
                                # Failed upload (video already deleted by upload_helper after 3 retries)
                                # Move to next video in same folder
                                continue

                        # Phase 2: Stop network monitoring
                        self._network_monitor.stop_monitoring()

                        # Calculate summary statistics
                        successful = sum(1 for r in upload_results if r['success'])
                        failed = sum(1 for r in upload_results if not r['success'])

                        # Display upload summary for this profile
                        logger.info("[IXApproach] ═══════════════════════════════════════════")
                        logger.info("[IXApproach] Profile Upload Summary: %s", profile_name)
                        logger.info("[IXApproach] ═══════════════════════════════════════════")
                        logger.info("[IXApproach] Total uploads attempted: %d", len(upload_results))
                        logger.info("[IXApproach] Successful: %d", successful)
                        logger.info("[IXApproach] Failed: %d", failed)
                        logger.info("[IXApproach] Current queue position:")
                        queue_status = self._folder_queue.get_queue_status()
                        logger.info("[IXApproach]   Folder: %d/%d", queue_status['current_index'] + 1, queue_status['total_folders'])
                        logger.info("[IXApproach]   Cycle: #%d", queue_status['cycle'])
                        logger.info("[IXApproach] ═══════════════════════════════════════════")

                        # Track upload count for this profile
                        upload_count = successful

            except Exception as e:
                logger.error("[IXApproach] Video upload failed: %s", str(e))
                # Stop network monitor on error
                if self._network_monitor:
                    self._network_monitor.stop_monitoring()

        except Exception as e:
            logger.error("[IXApproach] Profile processing error: %s", str(e))

        finally:
            # IMPORTANT: Close profile after processing
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] Closing Profile: %s", profile_name)
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            try:
                self._profile_manager.close_profile()
                logger.info("[IXApproach] ✓ Profile closed successfully")
            except Exception as e:
                logger.error("[IXApproach] Failed to close profile: %s", str(e))

        return upload_count

    def _run_upload_workflow(
        self,
        work_item: WorkItem,
        context: IXAutomationContext,
        result: WorkflowResult,
    ) -> None:
        """
        Run upload workflow.

        TODO: Integrate with actual upload workflow
        For now, just log creators and mark as placeholder.
        """
        logger.info("[IXApproach] Upload workflow starting...")

        driver = context.launcher.get_driver()
        if not driver:
            result.add_error("No driver available for workflow")
            return

        # Get current URL
        try:
            current_url = driver.current_url
            logger.info("[IXApproach] Current URL: %s", current_url)
        except Exception as e:
            logger.debug("[IXApproach] Could not get URL: %s", str(e))

        # Log creators
        logger.info("[IXApproach] Processing %s creator(s)...", len(work_item.creators))

        for idx, creator in enumerate(work_item.creators, 1):
            logger.info("[IXApproach] Creator %s/%s:", idx, len(work_item.creators))
            logger.info("[IXApproach]   Profile: %s", creator.profile_name)
            logger.info("[IXApproach]   Email: %s", creator.email)
            logger.info("[IXApproach]   Page: %s", creator.page_name or "N/A")

        # Mark success - basic integration working!
        logger.info("[IXApproach] ✓ ixBrowser integration complete!")
        logger.info("[IXApproach]   - Desktop app launched automatically ✓")
        logger.info("[IXApproach]   - API connection established ✓")
        logger.info("[IXApproach]   - Profile launched programmatically ✓")
        logger.info("[IXApproach]   - Selenium attached ✓")
        logger.info("[IXApproach]   - Session info retrieved ✓")

        logger.warning("[IXApproach] ⚠ Upload workflow integration pending")
        logger.warning("[IXApproach]   Next: Integrate with UploadWorkflowOrchestrator")

        result.creators_processed = 0
        result.success = True  # Mark as success - integration working!


if __name__ == "__main__":
    # Test mode - uses saved credentials from ix_config.json
    from pathlib import Path

    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )

    print("\n" + "="*60)
    print("ixBrowser Approach - Test Mode")
    print("="*60 + "\n")

    # Check if config exists
    from .config_handler import IXBrowserConfig

    config_handler = IXBrowserConfig()

    if not config_handler.is_configured():
        print("✗ No configuration found!")
        print("\nPlease configure ixBrowser credentials first using one of these methods:")
        print("1. Through the main app's Approaches settings dialog")
        print("2. Run the config_handler test: python -m modules.auto_uploader.approaches.ixbrowser.config_handler")
        exit(1)

    print("✓ Using saved ixBrowser configuration:")
    print(f"  Base URL: {config_handler.get_base_url()}")
    print(f"  Email: {config_handler.get_email()}")
    print("\n(Note: These are ixBrowser API credentials, not Facebook credentials)")

    print("\n" + "="*60)
    print("Testing Workflow")
    print("="*60 + "\n")

    # Create approach config using saved credentials
    approach_config = ApproachConfig(
        mode="ixbrowser",
        credentials={
            "base_url": config_handler.get_base_url(),
            "email": config_handler.get_email(),
            "password": config_handler.get_password(),
        },
        paths={
            "creators_root": Path.cwd() / "test_data" / "creators",
            "shortcuts_root": Path.cwd() / "test_data" / "shortcuts",
            "history_file": Path.cwd() / "test_data" / "history.json",
            "ix_data_root": Path.cwd() / "test_data" / "ix_data",
        },
        browser_type="ix"
    )

    # Create approach instance
    approach = IXBrowserApproach(approach_config)

    # Initialize
    if not approach.initialize():
        print("\n✗ Initialization failed!")
        exit(1)

    print("\n✓ Initialization successful!\n")

    # Create test work item
    work_item = WorkItem(
        account_name="Test Account",
        browser_type="ix",
        creators=[
            CreatorData(
                profile_name="Test Creator",
                email="test@example.com",
                password="test_password",
                page_name="Test Page"
            )
        ],
        config=approach_config
    )

    # Execute workflow
    print("Starting workflow...\n")
    result = approach.execute_workflow(work_item)

    print("\n" + "="*60)
    print("Workflow Result")
    print("="*60)
    print(f"Success: {result.success}")
    print(f"Creators Processed: {result.creators_processed}")
    if result.errors:
        print(f"Errors: {', '.join(result.errors)}")
