"""
Facebook Auto Uploader - Core Module
Main upload orchestration and logic
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from .utils import (
    load_config,
    load_tracking_data,
    save_tracking_data,
    parse_login_data,
    get_video_files,
    format_file_size
)
from .browser_controller import BrowserController
from .upload_manager import UploadManager


class FacebookAutoUploader:
    """Main Facebook Auto Uploader class"""

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize Facebook Auto Uploader

        Args:
            base_dir: Base directory (defaults to module directory)
        """
        # Get module directory
        if base_dir is None:
            self.base_dir = Path(__file__).parent
        else:
            self.base_dir = Path(base_dir)

        # Load configuration
        self.config = load_config(self.base_dir / 'data' / 'settings.json')

        # Load tracking data (JSON-based)
        self.tracking = load_tracking_data(self.base_dir / 'data' / 'upload_tracking.json')

        # Initialize components
        self.browser_controller = BrowserController(self.config)
        self.upload_manager = UploadManager(self.config, self.tracking, self.save_tracking)

        # Setup logging
        self.setup_logging()

    def setup_logging(self, log_level: str = 'INFO'):
        """Configure logging system"""
        logs_dir = self.base_dir / 'data' / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)

        log_file = logs_dir / f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

    def save_tracking(self):
        """Save tracking data to JSON file"""
        save_tracking_data(
            self.base_dir / 'data' / 'upload_tracking.json',
            self.tracking
        )

    def run(self):
        """Main execution flow"""
        try:
            logging.info("="*60)
            logging.info("Facebook Auto Uploader Started")
            logging.info("="*60)

            # Scan creators and shortcuts
            mapping = self.scan_creator_shortcuts()

            if not mapping:
                logging.warning("No creator shortcuts found!")
                return False

            # Display summary
            self.display_summary(mapping)

            # Process each browser account
            for browser_type, accounts in mapping.items():
                if not self.config.get('browsers', {}).get(browser_type, {}).get('enabled', True):
                    logging.info(f"Skipping {browser_type} (disabled)")
                    continue

                for account_name, creators in accounts.items():
                    try:
                        self.process_browser_account(browser_type, account_name, creators)
                    except Exception as e:
                        logging.error(f"Error processing {browser_type}/{account_name}: {e}")
                        continue

            logging.info("="*60)
            logging.info("Upload Process Completed!")
            logging.info("="*60)
            return True

        except KeyboardInterrupt:
            logging.info("\nProcess interrupted by user")
            return False
        except Exception as e:
            logging.error(f"Fatal error: {e}", exc_info=True)
            return False
        finally:
            self.cleanup()

    def scan_creator_shortcuts(self) -> Dict:
        """
        Scan creator_shortcuts folder and build mapping

        Returns:
            Dictionary: {browser_type: {account_name: [creator_names]}}
        """
        logging.info("Scanning creator shortcuts...")

        mapping = {}
        shortcuts_path = self.base_dir / 'creator_shortcuts'

        if not shortcuts_path.exists():
            logging.warning(f"Shortcuts folder not found: {shortcuts_path}")
            return mapping

        # Iterate through browser types
        for browser_dir in shortcuts_path.iterdir():
            if not browser_dir.is_dir():
                continue

            browser_type = browser_dir.name.lower()
            mapping[browser_type] = {}

            # Iterate through accounts
            for account_dir in browser_dir.iterdir():
                if not account_dir.is_dir():
                    continue

                account_name = account_dir.name

                # Find creator folders
                creators = [
                    item.name for item in account_dir.iterdir()
                    if item.is_dir() and not item.name.startswith('_')
                ]

                if creators:
                    mapping[browser_type][account_name] = sorted(creators)

        return mapping

    def display_summary(self, mapping: Dict):
        """Display upload summary"""
        logging.info("\n" + "="*60)
        logging.info("UPLOAD SUMMARY")
        logging.info("="*60)

        total_creators = 0
        total_videos = 0

        for browser_type, accounts in mapping.items():
            logging.info(f"\n{browser_type.upper()}:")

            for account_name, creators in accounts.items():
                logging.info(f"  Account: {account_name}")

                for creator_name in creators:
                    videos = self._get_creator_videos(creator_name)
                    pending = [v for v in videos if not self._is_uploaded(creator_name, v.name)]

                    logging.info(f"    {creator_name}: {len(pending)} video(s) pending")
                    total_creators += 1
                    total_videos += len(pending)

        logging.info("\n" + "="*60)
        logging.info(f"Total: {total_creators} creator(s), {total_videos} video(s)")
        logging.info("="*60 + "\n")

    def process_browser_account(self, browser_type: str, account_name: str, creators: List[str]):
        """Process all creators for a browser account"""
        logging.info(f"\nProcessing {browser_type.upper()} - {account_name}")

        try:
            # Load login data
            login_data_map = self._load_account_credentials(browser_type, account_name)

            if not login_data_map:
                logging.warning(f"No login data for {account_name}")
                return

            # Launch browser
            browser_window = self.browser_controller.launch_browser(browser_type)
            if not browser_window:
                logging.error(f"Failed to launch {browser_type}")
                return

            # Process each creator
            for creator_name in creators:
                try:
                    self._process_creator(
                        browser_type,
                        account_name,
                        creator_name,
                        login_data_map
                    )
                except Exception as e:
                    logging.error(f"Error with {creator_name}: {e}")
                    continue

            # Close browser
            self.browser_controller.close_browser(browser_type)

        except Exception as e:
            logging.error(f"Error in process_browser_account: {e}", exc_info=True)

    def _process_creator(self, browser_type: str, account_name: str,
                        creator_name: str, login_data_map: Dict):
        """Process single creator"""
        logging.info(f"\n--- Processing Creator: {creator_name} ---")

        # Get login data
        login_data = login_data_map.get(creator_name)
        if not login_data:
            logging.warning(f"No login data for {creator_name}")
            return

        # Try to open profile
        profile_shortcut = (
            self.base_dir / 'creator_shortcuts' / browser_type /
            account_name / creator_name / 'profile.lnk'
        )

        if profile_shortcut.exists():
            self.browser_controller.open_profile_via_shortcut(browser_type, profile_shortcut)

        # Connect Selenium
        driver = self.browser_controller.connect_selenium(browser_type, creator_name)
        if not driver:
            logging.error("Failed to connect Selenium")
            return

        try:
            # Prepare creator data
            creator_data = {
                'name': creator_name,
                'browser_type': browser_type,
                'account_name': account_name,
                **login_data
            }

            # Upload videos
            self.upload_manager.upload_creator_videos(driver, creator_data)

        finally:
            try:
                driver.quit()
            except:
                pass

    def _load_account_credentials(self, browser_type: str, account_name: str) -> Dict:
        """Load login credentials for account"""
        login_file = (
            self.base_dir / 'creator_shortcuts' /
            browser_type / account_name / 'login_data.txt'
        )

        if not login_file.exists():
            return {}

        login_entries = parse_login_data(login_file)
        return {entry['profile_name']: entry for entry in login_entries}

    def _get_creator_videos(self, creator_name: str) -> List[Path]:
        """Get videos for creator"""
        creator_path = self.base_dir / 'creators' / creator_name
        if not creator_path.exists():
            return []
        return get_video_files(creator_path)

    def _is_uploaded(self, creator_name: str, video_name: str) -> bool:
        """Check if video was uploaded"""
        history = self.tracking.get('upload_history', [])

        for entry in history:
            if (entry.get('creator_name') == creator_name and
                entry.get('video_file') == video_name and
                entry.get('status') == 'completed'):
                return True

        return False

    def cleanup(self):
        """Cleanup resources"""
        logging.info("Cleaning up...")
        try:
            self.browser_controller.close_all()
            self.save_tracking()
        except Exception as e:
            logging.error(f"Cleanup error: {e}")


# Standalone execution
if __name__ == "__main__":
    uploader = FacebookAutoUploader()
    uploader.run()
