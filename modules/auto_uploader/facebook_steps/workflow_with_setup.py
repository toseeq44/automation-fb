"""Main Workflow with Setup - Ask user for paths, then run automation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .setup_manager import SetupManager
from .step_1_load_credentials import Credentials, CredentialsError, load_credentials
from .step_2_find_shortcut import ShortcutError, find_shortcut
from .step_3_launch_browser import BrowserLaunchError, maximize_window, open_shortcut
from .step_4_check_session import SessionStatus, check_session
from .step_5_handle_login import login, logout
from .utils_mouse_feedback import human_delay
from .workflow_main import FacebookAutomationWorkflow


class WorkflowWithSetup:
    """
    مکمل workflow - پہلی بار user سے paths پوچھے، پھر automation چلائے۔
    Complete workflow - First time ask user for paths, then run automation.

    User flow:
    1. پہلی بار: Setup کریں - پوچھیں کہاں files ہیں
    2. اگلی بار: Saved paths استعمال کریں
    3. ہر بار: Automation چلائیں
    """

    def __init__(self, force_setup: bool = False):
        """
        شروع کریں۔
        Initialize workflow.

        Args:
            force_setup: دوبارہ سے setup پوچھو (اگر paths بدلنے ہوں)
        """
        self.force_setup = force_setup
        self.paths: Optional[dict] = None
        self.data_folder: Optional[Path] = None
        self.desktop_path: Optional[Path] = None

    def setup(self) -> bool:
        """
        سیٹ اپ کریں - paths لیں۔
        Setup - get paths from user or saved setup.

        Returns:
            True if setup successful
        """
        logging.info("=" * 70)
        logging.info("🚀 Facebook Automation Startup")
        logging.info("=" * 70)

        try:
            # Get paths (ask user if first time)
            self.paths = SetupManager.get_paths(force_setup=self.force_setup)

            if not self.paths:
                logging.error("❌ Setup failed - could not get paths")
                return False

            # Parse paths
            self.data_folder = Path(self.paths.get("login_data_path", "")).expanduser().resolve()
            self.desktop_path = Path(self.paths.get("desktop_path", "")).expanduser().resolve()

            # Validate paths
            if not self.data_folder.exists():
                logging.error(f"❌ Data folder does not exist: {self.data_folder}")
                return False

            logging.info(f"✓ Setup Complete")
            logging.info(f"  Data folder: {self.data_folder}")
            logging.info(f"  Desktop path: {self.desktop_path}")

            return True

        except Exception as e:
            logging.error(f"❌ Setup error: {e}")
            return False

    def run(self) -> bool:
        """
        چلائیں automation۔
        Run the complete automation workflow.

        Returns:
            True if successful
        """
        # First: Setup if not done
        if not self.paths:
            if not self.setup():
                return False

        logging.info("\n" + "=" * 70)
        logging.info("🔄 Starting Automation")
        logging.info("=" * 70)

        try:
            # Run the main workflow
            workflow = FacebookAutomationWorkflow(self.data_folder)
            workflow.run()

            logging.info("\n" + "=" * 70)
            logging.info("✅ Automation Complete!")
            logging.info("=" * 70)
            return True

        except Exception as e:
            logging.error(f"❌ Automation failed: {e}")
            return False

    def reset_setup(self) -> None:
        """
        سیٹ اپ reset کریں تاکہ دوبارہ پوچھے۔
        Reset setup so it asks again next time.
        """
        SetupManager.reset_setup()
        self.paths = None
        logging.info("✓ Setup reset - will ask for paths next time")


def start_automation(force_setup: bool = False) -> bool:
    """
    شروع کریں automation - سب کچھ خود ہو جائے۔
    Start automation - everything automatic.

    یہ function آپ کے GUI/main code سے کال کریں۔
    Call this function from your GUI or main code.

    Args:
        force_setup: دوبارہ سے setup پوچھو

    Returns:
        True if successful, False otherwise

    Example:
        from modules.auto_uploader.facebook_steps import start_automation

        if start_automation():
            print("✓ Success!")
        else:
            print("❌ Failed")
    """
    workflow = WorkflowWithSetup(force_setup=force_setup)

    # Step 1: Setup (ask for paths)
    if not workflow.setup():
        logging.error("Setup failed")
        return False

    # Step 2: Run automation
    if not workflow.run():
        logging.error("Automation failed")
        return False

    return True


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s'
    )

    print("\n" + "=" * 70)
    print("Testing WorkflowWithSetup")
    print("=" * 70 + "\n")

    # First time: Will ask for paths
    workflow = WorkflowWithSetup()

    if workflow.setup():
        print("\n✓ Setup successful\n")
        if workflow.run():
            print("\n✅ Automation successful!")
        else:
            print("\n❌ Automation failed")
    else:
        print("\n❌ Setup failed")

    # To reset and ask again next time:
    # workflow.reset_setup()
