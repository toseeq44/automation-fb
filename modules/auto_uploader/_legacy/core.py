"""Core orchestration for the Facebook automation workflow."""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from .auth_handler import AuthHandler
from .browser_launcher import BrowserLauncher
from .configuration import AutomationMode, SettingsManager
from .history_manager import HistoryManager
from .upload_manager import UploadManager
from .utils import (
    get_video_files,
    load_tracking_data,
    parse_login_data,
    save_tracking_data,
)


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

        # Load configuration and resolve dynamic paths
        self.settings_manager = SettingsManager(self.base_dir / 'data' / 'settings.json', self.base_dir)
        self.config = self.settings_manager.config
        self.paths = self.settings_manager.paths
        self.mode = self.settings_manager.get_mode()

        # Initialize credential handler and history storage
        self.auth_handler = AuthHandler()
        self.history_manager = HistoryManager(self.paths.history_file)

        # Load tracking data (JSON-based)
        self.tracking_path = self.base_dir / 'data' / 'upload_tracking.json'
        self.tracking = load_tracking_data(self.tracking_path)

        # Initialize components
        self.browser_launcher = BrowserLauncher(self.settings_manager)
        self.upload_manager = UploadManager(
            self.config,
            self.tracking,
            self.save_tracking,
            creators_root=self.paths.creators_root,
            history_manager=self.history_manager,
        )

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
            self.tracking_path,
            self.tracking
        )

    def run(self):
        """Main execution flow"""
        try:
            logging.info("="*60)
            logging.info("Facebook Auto Uploader Started")
            logging.info("="*60)
            logging.info("Mode: %s", self.mode.value)
            logging.info("Creators root: %s", self.paths.creators_root)
            logging.info("Shortcuts root: %s", self.paths.shortcuts_root)

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
        shortcuts_path = self.paths.shortcuts_root

        if not shortcuts_path.exists():
            logging.warning(f"Shortcuts folder not found: {shortcuts_path}")
            return mapping

        for candidate in shortcuts_path.iterdir():
            if not candidate.is_dir():
                continue

            if (candidate / 'login_data.txt').exists():
                browser_type = self._infer_browser_type(candidate.name, candidate)
                creators = self._collect_creator_folders(candidate)
                if creators:
                    mapping.setdefault(browser_type, {})[candidate.name] = creators
            else:
                browser_type = candidate.name.lower()
                for account_dir in candidate.iterdir():
                    if not account_dir.is_dir():
                        continue
                    creators = self._collect_creator_folders(account_dir)
                    if creators:
                        mapping.setdefault(browser_type, {})[account_dir.name] = creators

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
            account_root = self._resolve_account_root(browser_type, account_name)
            if not account_root:
                logging.warning(f"Unable to locate shortcuts for {account_name}")
                return

            login_data_map = self._load_account_credentials(browser_type, account_name, account_root)

            if not login_data_map:
                logging.warning(f"No login data for {account_name}")
                return

            # Launch browser
            browser_window = self.browser_launcher.launch(browser_type)
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
                        login_data_map,
                        account_root
                    )
                except Exception as e:
                    logging.error(f"Error with {creator_name}: {e}")
                    continue

            # Close browser
            self.browser_launcher.close(browser_type)

        except Exception as e:
            logging.error(f"Error in process_browser_account: {e}", exc_info=True)

    def _process_creator(self, browser_type: str, account_name: str,
                        creator_name: str, login_data_map: Dict, account_root: Path):
        """Process single creator"""
        logging.info(f"\n--- Processing Creator: {creator_name} ---")

        # Get login data
        login_data = login_data_map.get(creator_name)
        if not login_data:
            logging.warning(f"No login data for {creator_name}")
            return

        # Try to open profile
        creator_shortcut_dir = account_root / creator_name
        bulk_shortcut = creator_shortcut_dir / 'bulk videos.lnk'
        single_shortcut = creator_shortcut_dir / 'single video.lnk'
        profile_shortcut = creator_shortcut_dir / 'profile.lnk'

        pending_videos = self._get_creator_videos(creator_name)

        shortcut_to_use = None
        upload_mode = 'auto'
        if bulk_shortcut.exists() and len(pending_videos) >= 2:
            shortcut_to_use = bulk_shortcut
            upload_mode = 'bulk'
        elif single_shortcut.exists():
            shortcut_to_use = single_shortcut
            upload_mode = 'single'
        elif profile_shortcut.exists():
            shortcut_to_use = profile_shortcut

        if shortcut_to_use:
            self.browser_launcher.open_profile_shortcut(browser_type, shortcut_to_use)

        # Connect Selenium
        driver = self.browser_launcher.connect(browser_type, creator_name)
        if not driver:
            logging.error("Failed to connect Selenium")
            return

        try:
            # Prepare creator data
            creator_data = {
                'name': creator_name,
                'browser_type': browser_type,
                'account_name': account_name,
                'upload_mode': upload_mode,
                **login_data
            }

            # Upload videos
            self.upload_manager.upload_creator_videos(driver, creator_data)

        finally:
            try:
                driver.quit()
            except:
                pass

    def _load_account_credentials(self, browser_type: str, account_name: str, account_root: Path) -> Dict:
        """Load login credentials for account"""
        login_file = account_root / 'login_data.txt'

        if not login_file.exists():
            return {}

        login_entries = parse_login_data(login_file)
        credentials = {}

        for entry in login_entries:
            identifier = f"{browser_type}:{account_name}:{entry['profile_name']}"
            entry = self.auth_handler.read_password(identifier, entry)
            credentials[entry['profile_name']] = entry

        return credentials

    def _get_creator_videos(self, creator_name: str) -> List[Path]:
        """Get videos for creator"""
        creator_path = self.paths.creators_root / creator_name
        if not creator_path.exists():
            return []
        return get_video_files(creator_path)

    def _collect_creator_folders(self, account_dir: Path) -> List[str]:
        return sorted(
            [item.name for item in account_dir.iterdir() if item.is_dir() and not item.name.startswith('_')]
        )

    def _resolve_account_root(self, browser_type: str, account_name: str) -> Optional[Path]:
        candidates = [
            self.paths.shortcuts_root / browser_type / account_name,
            self.paths.shortcuts_root / account_name,
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _infer_browser_type(self, account_name: str, account_dir: Path) -> str:
        lower_name = account_name.lower()
        if 'gologin' in lower_name or 'orbita' in lower_name:
            return 'gologin'
        if 'ix' in lower_name or 'incogniton' in lower_name:
            return 'ix'
        if 'vpn' in lower_name:
            return 'vpn'

        # check login data hints
        login_file = account_dir / 'login_data.txt'
        entries = parse_login_data(login_file)
        for entry in entries:
            if entry.get('browser_type'):
                return entry['browser_type']

        return self.mode.value

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
            self.browser_launcher.close_all()
            self.save_tracking()
        except Exception as e:
            logging.error(f"Cleanup error: {e}")


# Standalone execution
if __name__ == "__main__":
    uploader = FacebookAutoUploader()
    uploader.run()
