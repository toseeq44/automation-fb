"""
Facebook Upload Bot - Main Entry Point
Automates video uploads to Facebook pages using anti-detect browsers
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from utils import ConfigLoader, DatabaseManager, parse_login_data
from browser_controller import BrowserController
from upload_manager import UploadManager


class FacebookUploadBot:
    """Main Facebook Upload Bot class"""

    def __init__(self, config_path: str = 'config/settings.json'):
        """
        Initialize Facebook Upload Bot

        Args:
            config_path: Path to configuration file
        """
        # Get the directory of this script
        self.base_dir = Path(__file__).parent

        # Initialize components
        config_full_path = self.base_dir / config_path
        self.config = ConfigLoader(str(config_full_path))

        db_path = self.base_dir / 'config' / 'upload_status.db'
        self.db = DatabaseManager(str(db_path))

        self.browser_controller = BrowserController(self.config)
        self.upload_manager = UploadManager(self.config, self.db)

        # Setup logging
        self.setup_logging()

        logging.info("=" * 60)
        logging.info("Facebook Upload Bot Initialized")
        logging.info("=" * 60)

    def setup_logging(self):
        """Configure logging system"""
        # Get log settings
        log_level = self.config.get('logging.level', 'INFO')
        log_format = self.config.get('logging.format', '%(asctime)s - %(levelname)s - %(message)s')

        # Create logs directory
        logs_dir = self.base_dir / self.config.get('paths.logs_folder', 'logs')
        logs_dir.mkdir(exist_ok=True)

        # Create log file name with timestamp
        log_file = logs_dir / f"upload_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        # Configure handlers
        handlers = []

        # File handler
        if self.config.get('logging.file_output', True):
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)

        # Console handler
        if self.config.get('logging.console_output', True):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(console_handler)

        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=log_format,
            handlers=handlers
        )

        logging.info(f"Logging initialized - Log file: {log_file}")

    def run(self):
        """Main bot execution flow"""
        try:
            logging.info("Starting Facebook Upload Bot...")

            # Step 1: Scan creator shortcuts and build mapping
            mapping = self.scan_creator_shortcuts()

            if not mapping:
                logging.warning("No creator shortcuts found!")
                logging.info("Please set up creator_shortcuts folder structure")
                return

            # Step 2: Display summary
            self.display_upload_summary(mapping)

            # Step 3: Process each browser account
            for browser_type, accounts in mapping.items():
                if not self.config.get(f'browsers.{browser_type}.enabled', True):
                    logging.info(f"Skipping {browser_type} (disabled in config)")
                    continue

                for account_name, creators in accounts.items():
                    try:
                        self.process_browser_account(browser_type, account_name, creators)
                    except Exception as e:
                        logging.error(f"Error processing {browser_type}/{account_name}: {e}")
                        continue

            logging.info("=" * 60)
            logging.info("Upload process completed!")
            logging.info("=" * 60)

        except KeyboardInterrupt:
            logging.info("\nBot interrupted by user")
        except Exception as e:
            logging.error(f"Fatal error: {e}", exc_info=True)
        finally:
            # Cleanup
            self.cleanup()

    def scan_creator_shortcuts(self) -> Dict:
        """
        Scan creator_shortcuts folder and build mapping

        Returns:
            Dictionary mapping: {browser_type: {account_name: [creator_names]}}
        """
        logging.info("Scanning creator shortcuts...")

        mapping = {}
        shortcuts_path = self.base_dir / self.config.get('paths.shortcuts_folder', 'creator_shortcuts')

        if not shortcuts_path.exists():
            logging.warning(f"Shortcuts folder not found: {shortcuts_path}")
            return mapping

        # Iterate through browser types (GoLogin, IX)
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
                creators = []
                for item in account_dir.iterdir():
                    if item.is_dir() and item.name != '__pycache__':
                        creators.append(item.name)

                if creators:
                    mapping[browser_type][account_name] = sorted(creators)

        logging.info(f"Found {sum(len(accounts) for accounts in mapping.values())} browser account(s)")

        return mapping

    def display_upload_summary(self, mapping: Dict):
        """
        Display summary of what will be uploaded

        Args:
            mapping: Scan mapping
        """
        logging.info("\n" + "=" * 60)
        logging.info("UPLOAD SUMMARY")
        logging.info("=" * 60)

        total_creators = 0
        total_videos = 0

        for browser_type, accounts in mapping.items():
            logging.info(f"\n{browser_type.upper()}:")

            for account_name, creators in accounts.items():
                logging.info(f"  Account: {account_name}")

                for creator_name in creators:
                    videos = self.upload_manager.get_creator_videos(creator_name)

                    # Filter uploaded videos
                    if self.config.get('upload_settings.skip_uploaded', True):
                        pending_videos = [v for v in videos if not self.db.is_video_uploaded(creator_name, v.name)]
                    else:
                        pending_videos = videos

                    logging.info(f"    {creator_name}: {len(pending_videos)} video(s) pending")

                    total_creators += 1
                    total_videos += len(pending_videos)

        logging.info("\n" + "=" * 60)
        logging.info(f"Total: {total_creators} creator(s), {total_videos} video(s) to upload")
        logging.info("=" * 60 + "\n")

    def process_browser_account(self, browser_type: str, account_name: str, creators: List[str]):
        """
        Process all creators for a specific browser account

        Args:
            browser_type: Browser type (gologin/ix)
            account_name: Account identifier
            creators: List of creator names
        """
        logging.info("\n" + "=" * 60)
        logging.info(f"Processing {browser_type.upper()} Account: {account_name}")
        logging.info("=" * 60)

        try:
            # 1. Get or create browser account in database
            browser_account_id = self.db.get_or_create_browser_account(browser_type, account_name)

            # 2. Load login data for this account
            login_data_map = self.load_account_credentials(browser_type, account_name)

            if not login_data_map:
                logging.warning(f"No login data found for {account_name}")
                return

            # 3. Launch browser
            browser_window = self.browser_controller.launch_browser(browser_type)

            if not browser_window:
                logging.error(f"Failed to launch {browser_type}")
                return

            # 4. Process each creator
            for creator_name in creators:
                try:
                    self.process_creator(
                        browser_type,
                        browser_account_id,
                        account_name,
                        creator_name,
                        login_data_map
                    )
                except Exception as e:
                    logging.error(f"Error processing creator {creator_name}: {e}")
                    continue

            # 5. Close browser
            logging.info(f"Closing {browser_type} browser...")
            self.browser_controller.close_browser(browser_type)

        except Exception as e:
            logging.error(f"Error in process_browser_account: {e}", exc_info=True)
            raise

    def process_creator(self, browser_type: str, browser_account_id: int,
                       account_name: str, creator_name: str, login_data_map: Dict):
        """
        Process a single creator (upload their videos)

        Args:
            browser_type: Browser type
            browser_account_id: Browser account ID in database
            account_name: Account name
            creator_name: Creator name
            login_data_map: Map of profile_name -> login_data
        """
        logging.info("\n" + "-" * 60)
        logging.info(f"Processing Creator: {creator_name}")
        logging.info("-" * 60)

        # Find matching login data for this creator
        # Assumption: creator_name matches profile_name in login_data.txt
        login_data = login_data_map.get(creator_name)

        if not login_data:
            logging.warning(f"No login data found for creator: {creator_name}")
            logging.info(f"Available profiles: {', '.join(login_data_map.keys())}")
            return

        # Get or create profile in database
        profile_id = self.db.get_or_create_profile(browser_account_id, {
            'profile_name': login_data['profile_name'],
            'facebook_email': login_data['facebook_email'],
            'page_id': login_data.get('page_id', ''),
            'page_name': login_data.get('page_name', ''),
            'creator_name': creator_name
        })

        # Try to open profile using shortcut
        shortcuts_path = self.base_dir / self.config.get('paths.shortcuts_folder')
        profile_shortcut = shortcuts_path / browser_type / account_name / creator_name / 'profile.lnk'

        if profile_shortcut.exists():
            logging.info(f"Opening profile via shortcut: {profile_shortcut.name}")
            self.browser_controller.open_profile_via_shortcut(browser_type, profile_shortcut)
        else:
            logging.info("No profile shortcut found, using manual profile opening")

        # Connect Selenium to browser
        driver = self.browser_controller.connect_selenium(browser_type, creator_name)

        if not driver:
            logging.error("Failed to connect Selenium")
            return

        try:
            # Prepare creator data
            creator_data = {
                'name': creator_name,
                'profile_name': login_data['profile_name'],
                'facebook_email': login_data['facebook_email'],
                'facebook_password': login_data['facebook_password'],
                'page_name': login_data.get('page_name', ''),
                'page_id': login_data.get('page_id', '')
            }

            # Upload videos for this creator
            self.upload_manager.upload_creator_videos(driver, creator_data, profile_id)

            logging.info(f"Completed processing creator: {creator_name}")

        except Exception as e:
            logging.error(f"Error uploading for {creator_name}: {e}", exc_info=True)

        finally:
            # Close this profile's driver (but keep browser open)
            try:
                driver.quit()
            except:
                pass

    def load_account_credentials(self, browser_type: str, account_name: str) -> Dict:
        """
        Load login credentials for a browser account

        Args:
            browser_type: Browser type
            account_name: Account name

        Returns:
            Dictionary mapping profile_name -> login_data
        """
        shortcuts_path = self.base_dir / self.config.get('paths.shortcuts_folder')
        login_file = shortcuts_path / browser_type / account_name / 'login_data.txt'

        if not login_file.exists():
            logging.warning(f"Login data file not found: {login_file}")
            return {}

        # Parse login data file
        login_entries = parse_login_data(login_file)

        # Create mapping by profile name
        login_map = {entry['profile_name']: entry for entry in login_entries}

        logging.info(f"Loaded {len(login_map)} login credential(s) from {login_file.name}")

        return login_map

    def cleanup(self):
        """Cleanup resources"""
        logging.info("Cleaning up...")

        try:
            # Close all browsers
            self.browser_controller.close_all()

            # Close database
            self.db.close()

        except Exception as e:
            logging.error(f"Error during cleanup: {e}")


def main():
    """Main entry point"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║          Facebook Video Upload Bot v1.0                  ║
    ║          Free API-less Automation                        ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    # Check if running from correct directory
    if not Path('config/settings.json').exists():
        print("\n⚠️  ERROR: Please run this script from FB_Upload_Bot directory")
        print("   Example: cd FB_Upload_Bot && python fb_upload_bot.py")
        sys.exit(1)

    # Initialize and run bot
    bot = FacebookUploadBot()
    bot.run()


if __name__ == "__main__":
    main()
