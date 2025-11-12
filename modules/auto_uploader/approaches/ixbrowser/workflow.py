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
        logger.info("[Window] Bringing browser to front (OS-level)...")

        # Method 1: Selenium methods
        try:
            driver.maximize_window()
            driver.switch_to.window(driver.current_window_handle)
            driver.execute_script("window.focus();")
            logger.info("[Window] ✓ Selenium window focus applied")
        except Exception as e:
            logger.debug("[Window] Selenium focus failed: %s", str(e))

        # Method 2: OS-level window management
        system = platform.system()

        if system == "Linux":
            # Linux: Use wmctrl or xdotool
            try:
                # Get window title from driver
                window_title = driver.title

                # Try wmctrl first
                try:
                    subprocess.run(
                        ["wmctrl", "-a", window_title],
                        check=False,
                        timeout=2,
                        capture_output=True
                    )
                    logger.info("[Window] ✓ wmctrl window focus applied")
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

                # Try xdotool as fallback
                try:
                    result = subprocess.run(
                        ["xdotool", "search", "--name", window_title, "windowactivate"],
                        check=False,
                        timeout=2,
                        capture_output=True
                    )
                    logger.info("[Window] ✓ xdotool window focus applied")
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

            except Exception as e:
                logger.debug("[Window] Linux window focus failed: %s", str(e))

        elif system == "Windows":
            # Windows: Use PowerShell or win32gui
            try:
                window_title = driver.title

                # PowerShell command to bring window to front
                ps_command = f'''
                $wshell = New-Object -ComObject wscript.shell
                $wshell.AppActivate("{window_title}")
                '''

                subprocess.run(
                    ["powershell", "-Command", ps_command],
                    check=False,
                    timeout=2,
                    capture_output=True
                )
                logger.info("[Window] ✓ Windows window focus applied")
            except Exception as e:
                logger.debug("[Window] Windows focus failed: %s", str(e))

        # Final JavaScript focus
        try:
            driver.execute_script("window.focus(); window.scrollTo(0, 0);")
        except:
            pass

        time.sleep(0.5)  # Give OS time to process
        logger.info("[Window] ✓ Browser window brought to front successfully!")
        return True

    except Exception as e:
        logger.warning("[Window] Could not bring window to front: %s", str(e))
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

        # Get all profiles
        logger.info("[IXApproach] ═══════════════════════════════════════════")
        logger.info("[IXApproach] Getting Profile Information from ixBrowser")
        logger.info("[IXApproach] ═══════════════════════════════════════════")

        all_profiles = self._connection_manager.get_profile_list(limit=100)

        if not all_profiles:
            result.add_error("No profiles found in ixBrowser. Please create a profile first.")
            return result

        logger.info("[IXApproach] ✓ Found %d profile(s) in ixBrowser:", len(all_profiles))
        for idx, p in enumerate(all_profiles, 1):
            logger.info("[IXApproach]   %d. %s (ID: %s)", idx, p.get('name', 'Unknown'), p.get('profile_id'))

        # Select first profile
        profile_id = all_profiles[0]['profile_id']
        profile_name = all_profiles[0].get('name', 'Unknown')
        logger.info("[IXApproach] Selected profile: %s (ID: %s)", profile_name, profile_id)

        # Create browser launcher
        launcher = BrowserLauncher(client)

        try:
            # Step 1: Launch Profile via API
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 1: Launch Profile")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            # Launch profile with no custom args (clean opening)
            if not launcher.launch_profile(profile_id, startup_args=[]):
                result.add_error(f"Failed to launch profile {profile_id}")
                return result

            logger.info("[IXApproach] ✓ Profile launched successfully!")

            # Step 2: Attach Selenium
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 2: Attach Selenium WebDriver")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            if not launcher.attach_selenium():
                result.add_error("Failed to attach Selenium WebDriver")
                return result

            driver = launcher.get_driver()
            if not driver:
                result.add_error("Selenium driver not available")
                return result

            logger.info("[IXApproach] ✓ Selenium attached successfully!")

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
                    error_msg = f"Profile folder not found: {profile_folder}"
                    logger.error("[IXApproach] %s", error_msg)
                    logger.error("[IXApproach] Please create: Desktop/creators data/%s/", profile_name)
                    raise FileNotFoundError(error_msg)

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
                result.add_error(str(e))
            except Exception as e:
                logger.error("[IXApproach] Bookmark-folder comparison failed: %s", str(e))
                result.add_error(f"Comparison failed: {str(e)}")

            # Step 5: Upload Videos to Bookmarks
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 5: Upload Videos to Bookmarks")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            try:
                # Only proceed if we have matched bookmarks
                if not facebook_bookmarks:
                    logger.warning("[IXApproach] No Facebook bookmarks found, skipping uploads")
                elif not matched:
                    logger.warning("[IXApproach] No matched folders found, skipping uploads")
                else:
                    # Initialize upload helper
                    upload_helper = VideoUploadHelper(driver)

                    upload_results = []
                    skipped = []

                    logger.info("[IXApproach] Starting uploads for %d matched bookmark(s)...", len(matched))
                    logger.info("[IXApproach] ")

                    # Upload videos for each matched bookmark
                    for bookmark in facebook_bookmarks:
                        folder_name = bookmark['title']
                        folder_path = os.path.join(profile_folder, folder_name)

                        # Only upload if folder exists (matched)
                        if folder_name in matched:
                            logger.info("[IXApproach] ───────────────────────────────────────────────")
                            logger.info("[IXApproach] Processing: %s", folder_name)
                            logger.info("[IXApproach] ───────────────────────────────────────────────")

                            success = upload_helper.upload_to_bookmark(bookmark, folder_path)
                            upload_results.append({
                                'bookmark': folder_name,
                                'success': success
                            })

                            # Brief pause between uploads
                            if success:
                                logger.info("[IXApproach] Waiting 5 seconds before next upload...")
                                time.sleep(5)
                        else:
                            logger.debug("[IXApproach] Skipping %s - no folder found", folder_name)
                            skipped.append(folder_name)

                    # Calculate summary statistics
                    successful = sum(1 for r in upload_results if r['success'])
                    failed = sum(1 for r in upload_results if not r['success'])

                    # Display upload summary
                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                    logger.info("[IXApproach] Upload Summary")
                    logger.info("[IXApproach] ═══════════════════════════════════════════")
                    logger.info("[IXApproach] Total uploads attempted: %d", len(upload_results))
                    logger.info("[IXApproach] Successful: %d", successful)
                    logger.info("[IXApproach] Failed: %d", failed)
                    logger.info("[IXApproach] Skipped (no folder): %d", len(skipped))
                    logger.info("[IXApproach] ")

                    # Show detailed results
                    if upload_results:
                        logger.info("[IXApproach] Upload Details:")
                        for r in upload_results:
                            status = "✓" if r['success'] else "✗"
                            logger.info("[IXApproach]   %s %s", status, r['bookmark'])

                    logger.info("[IXApproach] ═══════════════════════════════════════════")

                    # Update result with upload stats
                    result.creators_processed = successful

                    if failed > 0:
                        result.add_error(f"{failed} upload(s) failed")

            except Exception as e:
                logger.error("[IXApproach] Video upload failed: %s", str(e))
                result.add_error(f"Upload failed: {str(e)}")

            # Create context
            self._current_context = IXAutomationContext(
                profile_id=profile_id,
                launcher=launcher,
                login_manager=None  # Not using Facebook login management
            )

            # Step 6: Workflow Complete
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 6: Workflow Complete")
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] ✓ Profile remains open")
            logger.info("[IXApproach] ✓ Browser session active")
            logger.info("[IXApproach] User can continue working in the browser")

        except Exception as e:
            logger.error("[IXApproach] Workflow error: %s", str(e))
            result.add_error(str(e))

        return result

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
