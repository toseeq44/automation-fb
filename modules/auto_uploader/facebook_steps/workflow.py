"""Orchestrate the streamlined Facebook automation workflow."""

from __future__ import annotations

import logging
from pathlib import Path

from .browser_opener import BrowserLaunchError, open_browser
from .login_data_reader import LoginDataError, load_login_data
from .mouse_feedback import human_delay
from .session_actions import login_with_credentials, logout_current_session
from .session_status import SessionState, detect_session_state
from .shortcut_locator import ShortcutNotFoundError, find_browser_shortcut
from .window_preparer import BrowserWindowNotFoundError, focus_and_prepare_window


class FacebookAutomationWorkflow:
    """High-level runner that composes the individual automation steps."""

    def __init__(self, data_folder: Path):
        self.data_folder = Path(data_folder).expanduser().resolve()
        self.session_screenshot = self.data_folder / "facebook_session.png"

    def run(self) -> None:
        """Execute the requested automation sequence."""
        logging.info("=" * 60)
        logging.info("Starting Facebook automation workflow.")
        logging.info("=" * 60)

        login_data = load_login_data(self.data_folder)
        human_delay(2, "Preparing to launch browser...")

        shortcut = find_browser_shortcut(login_data.browser)
        human_delay(1, f"Shortcut located for {login_data.browser}. Launching...")

        open_browser(shortcut)

        focus_and_prepare_window(login_data.browser)

        human_delay(3, "Browser ready. Checking session state...")
        session_state = detect_session_state(save_screenshot_to=self.session_screenshot)

        if session_state == SessionState.LOGGED_IN:
            logging.info("Existing session detected. Attempting logout before continuing.")
            if logout_current_session():
                human_delay(4, "Logout sequence triggered. Waiting briefly...")
                session_state = SessionState.LOGGED_OUT
            else:
                logging.warning("Logout attempt did not succeed. Proceeding with caution.")

        if session_state in {SessionState.LOGGED_OUT, SessionState.UNKNOWN}:
            logging.info("Logging into Facebook with provided credentials.")
            login_with_credentials(login_data)
            human_delay(5, "Waiting for login to settle...")

        logging.info("=" * 60)
        logging.info("Facebook automation workflow completed.")
        logging.info("=" * 60)


def run_from_folder(data_folder: Path) -> None:
    """
    Convenience function mirroring the previous script-style entry point.

    Args:
        data_folder: Directory containing ``login_data.txt``.
    """
    workflow = FacebookAutomationWorkflow(data_folder)
    workflow.run()
