"""
ixBrowser Automation Workflow
Complete integration using official ixbrowser-local-api library
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


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
        1. Initialize connection (auto-launch ixBrowser if needed)
        2. Get profiles from ixBrowser
        3. Launch profile programmatically
        4. Attach Selenium WebDriver
        5. Get session info (current URL, login status)
        6. Run upload workflow (placeholder for now)
        7. Close profile
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

        # Select first profile for now
        profile_id = all_profiles[0]['profile_id']
        profile_name = all_profiles[0].get('name', 'Unknown')

        logger.info("[IXApproach] Selected profile for launch: %s (ID: %s)", profile_name, profile_id)

        # Create browser launcher
        launcher = BrowserLauncher(client)

        try:
            # Step 1: Launch profile
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 1: Launch Profile")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            # Launch profile with minimal args to open normally
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

            # Create context
            self._current_context = IXAutomationContext(
                profile_id=profile_id,
                launcher=launcher,
                login_manager=None  # Not using Facebook login management
            )

            # Step 4: Run workflow (placeholder)
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 4: Run Upload Workflow")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            self._run_upload_workflow(work_item, self._current_context, result)

        finally:
            # Step 5: Cleanup
            logger.info("[IXApproach] ═══════════════════════════════════════════")
            logger.info("[IXApproach] STEP 5: Cleanup")
            logger.info("[IXApproach] ═══════════════════════════════════════════")

            if launcher.is_profile_open():
                launcher.close_profile()

            self._current_context = None

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
