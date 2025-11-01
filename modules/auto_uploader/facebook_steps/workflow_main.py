"""Main Workflow: Orchestrate all 5 steps for Facebook automation."""

from __future__ import annotations

import logging
from pathlib import Path

from .step_1_load_credentials import Credentials, CredentialsError, load_credentials
from .step_2_find_shortcut import ShortcutError, find_shortcut
from .step_3_launch_browser import BrowserLaunchError, maximize_window, open_shortcut
from .step_4_check_session import SessionStatus, check_session
from .step_5_handle_login import login, logout
from .utils_mouse_feedback import human_delay


class WorkflowError(Exception):
    """Raised when the workflow encounters a critical error."""


class FacebookAutomationWorkflow:
    """
    Complete Facebook automation workflow with 5 sequential steps:

    1. Load credentials from login_data.txt
    2. Find browser shortcut on desktop
    3. Open browser and maximize window
    4. Check if user is already logged in
    5. Handle login/logout based on current state
    """

    def __init__(self, data_folder: Path):
        """
        Initialize the workflow.

        Args:
            data_folder: Directory containing login_data.txt.
        """
        self.data_folder = Path(data_folder).expanduser().resolve()
        self.session_screenshot = self.data_folder / "facebook_session_check.png"

    def run(self) -> None:
        """
        Execute the complete workflow with all 5 steps.

        Raises:
            WorkflowError: If any step fails critically.
        """
        try:
            self._print_section("STEP 1: Load Credentials")
            credentials = self._step_1_load_credentials()

            self._print_section("STEP 2: Find Browser Shortcut")
            shortcut = self._step_2_find_shortcut(credentials)

            self._print_section("STEP 3: Launch Browser and Maximize")
            self._step_3_launch_browser(credentials, shortcut)

            self._print_section("STEP 4: Check Session Status")
            session_status = self._step_4_check_session()

            self._print_section("STEP 5: Handle Login/Logout")
            self._step_5_handle_login(credentials, session_status)

            self._print_section("WORKFLOW COMPLETED SUCCESSFULLY")

        except (CredentialsError, ShortcutError, BrowserLaunchError) as exc:
            raise WorkflowError(f"Workflow failed: {exc}") from exc

    def _print_section(self, title: str) -> None:
        """Print a formatted section header."""
        logging.info("=" * 70)
        logging.info(title)
        logging.info("=" * 70)

    def _step_1_load_credentials(self) -> Credentials:
        """
        Step 1: Load credentials from login_data.txt.

        Returns:
            Credentials object.

        Raises:
            CredentialsError: If credentials cannot be loaded.
        """
        logging.info("Loading credentials from: %s", self.data_folder)
        credentials = load_credentials(self.data_folder)
        logging.info("✓ Credentials loaded successfully")
        logging.info("  Browser: %s", credentials.browser)
        logging.info("  Email: %s", credentials.email)
        return credentials

    def _step_2_find_shortcut(self, credentials: Credentials) -> Path:
        """
        Step 2: Find browser shortcut on desktop.

        Args:
            credentials: Credentials object with browser name.

        Returns:
            Path to the shortcut file.

        Raises:
            ShortcutError: If shortcut cannot be found.
        """
        logging.info("Searching for '%s' shortcut on desktop...", credentials.browser)
        shortcut = find_shortcut(credentials.browser)
        logging.info("✓ Shortcut found: %s", shortcut.name)
        return shortcut

    def _step_3_launch_browser(self, credentials: Credentials, shortcut: Path) -> None:
        """
        Step 3: Open browser shortcut and maximize window.

        Args:
            credentials: Credentials object with browser name.
            shortcut: Path to the shortcut file.

        Raises:
            BrowserLaunchError: If browser cannot be launched.
        """
        logging.info("Opening browser shortcut...")
        open_shortcut(shortcut, wait_seconds=12)
        logging.info("✓ Browser launched")

        logging.info("Finding and maximizing browser window...")
        maximize_window(credentials.browser, max_retries=3, retry_wait_seconds=4)
        logging.info("✓ Browser window maximized")

    def _step_4_check_session(self) -> SessionStatus:
        """
        Step 4: Check if user is logged into Facebook.

        Returns:
            SessionStatus enum indicating login state.
        """
        logging.info("Checking session state...")
        status = check_session(save_screenshot_to=self.session_screenshot)
        logging.info("✓ Session status: %s", status.value)
        return status

    def _step_5_handle_login(self, credentials: Credentials, session_status: SessionStatus) -> None:
        """
        Step 5: Handle login/logout based on current session status.

        Args:
            credentials: Credentials for login if needed.
            session_status: Current session state from Step 4.
        """
        if session_status == SessionStatus.LOGGED_IN:
            logging.info("Active session detected - logging out first...")
            if logout():
                logging.info("✓ Logout completed")
                human_delay(2, "Waiting briefly after logout...")
            else:
                logging.warning("⚠ Logout may have failed, but continuing...")

            # After logout, attempt login with provided credentials
            logging.info("Now logging in with provided credentials...")
            if login(credentials):
                logging.info("✓ Login completed")
            else:
                logging.warning("⚠ Login may have failed")

        elif session_status == SessionStatus.LOGGED_OUT:
            logging.info("No active session detected - logging in...")
            if login(credentials):
                logging.info("✓ Login completed")
            else:
                logging.warning("⚠ Login may have failed")

        else:  # UNKNOWN
            logging.info("Session state unknown - attempting login as precaution...")
            if login(credentials):
                logging.info("✓ Login attempted")
            else:
                logging.warning("⚠ Login may have failed")


def run_workflow(data_folder: Path) -> None:
    """
    Convenience function to run the complete Facebook automation workflow.

    Args:
        data_folder: Directory containing login_data.txt.

    Raises:
        WorkflowError: If the workflow encounters a critical error.
    """
    workflow = FacebookAutomationWorkflow(data_folder)
    workflow.run()
