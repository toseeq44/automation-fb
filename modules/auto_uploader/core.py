"""Core orchestration for the Facebook automation workflow."""

import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from .auth_handler import AuthHandler
from .browser_launcher import BrowserLauncher
from .configuration import SettingsManager
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

        logging.debug(f"Scanning directory: {shortcuts_path}")

        for candidate in shortcuts_path.iterdir():
            if not candidate.is_dir():
                logging.debug(f"Skipping non-directory: {candidate.name}")
                continue

            login_data_file = candidate / 'login_data.txt'
            logging.debug(f"Checking: {candidate.name}")

            if login_data_file.exists():
                logging.debug(f"Found login_data.txt in: {candidate.name}")
                browser_type = self._infer_browser_type(candidate.name, candidate)
                creators = self._collect_creator_folders(candidate)
                logging.debug(f"Found {len(creators)} creators in {candidate.name}: {creators}")
                # Add to mapping even if no creators (for browser-only launch)
                mapping.setdefault(browser_type, {})[candidate.name] = creators
                if not creators:
                    logging.info(f"No creator folders found in {candidate.name}, will launch browser only")
            else:
                logging.debug(f"No login_data.txt in {candidate.name}, checking as browser folder")
                browser_type = candidate.name.lower()
                for account_dir in candidate.iterdir():
                    if not account_dir.is_dir():
                        continue
                    logging.debug(f"Checking account folder: {account_dir.name}")
                    creators = self._collect_creator_folders(account_dir)
                    if creators:
                        mapping.setdefault(browser_type, {})[account_dir.name] = creators

        logging.info(f"Scan complete. Found {sum(len(accounts) for accounts in mapping.values())} account(s)")
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

            logging.debug(f"Account root: {account_root}")

            login_data_map = self._load_account_credentials(browser_type, account_name, account_root)

            if not login_data_map:
                logging.warning(f"No login credentials loaded for account: {account_name}")
                logging.warning(f"Expected login_data.txt at: {account_root / 'login_data.txt'}")
                logging.warning(f"Make sure login_data.txt exists and has valid entries")
                return

            # Launch browser
            browser_window = self.browser_launcher.launch(browser_type)
            if not browser_window:
                logging.error(f"Failed to launch {browser_type}")
                return

            # Handle Facebook login with credentials
            logging.info(f"\n{'='*60}")
            logging.info(f"🔐 Preparing to login to Facebook")
            logging.info(f"{'='*60}")

            # Get the first login data entry (use the page_name as the account identifier)
            first_entry = next(iter(login_data_map.values())) if login_data_map else None
            if first_entry:
                email = first_entry.get('facebook_email', '')
                password = first_entry.get('facebook_password', '')

                if email and password:
                    logging.info(f"📧 Account: {email}")
                    time.sleep(2)
                    # Call login handler
                    login_success = self.browser_launcher.handle_facebook_login(email, password)
                    if not login_success:
                        logging.warning("⚠ Could not complete automated login")
                        logging.info("📌 Please login manually in the browser window")
                        time.sleep(5)
                else:
                    logging.warning("⚠ Email or password missing in login data")
            else:
                logging.warning("⚠ No login credentials available")

            # Check if we have creators to process
            if not creators:
                logging.info(f"\nNo creators found for {account_name}.")
                logging.info("✓ Browser launched and ready for use.")
                logging.info("📌 You can now manually use the browser to upload videos.")
                # Keep browser open - don't close it
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

        # Locate creator shortcut directory (check for Creators subfolder)
        creator_shortcut_dir = self._resolve_creator_shortcut_dir(account_root, creator_name)
        if not creator_shortcut_dir:
            logging.warning(f"Creator shortcut directory not found for {creator_name}")
            return

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
        """
        Load login credentials for account.

        Maps creator folder names to their login credentials using page_name.
        """
        login_file = account_root / 'login_data.txt'

        if not login_file.exists():
            logging.warning(f"login_data.txt not found: {login_file}")
            return {}

        login_entries = parse_login_data(login_file)
        if not login_entries:
            logging.warning(f"No entries found in login_data.txt: {login_file}")
            return {}

        credentials = {}

        for entry in login_entries:
            identifier = f"{browser_type}:{account_name}:{entry['profile_name']}"
            entry = self.auth_handler.read_password(identifier, entry)

            # Use page_name as key (matches creator folder names)
            page_name = entry.get('page_name', '').strip()
            if page_name:
                credentials[page_name] = entry
                logging.debug(f"Loaded credentials for page: {page_name}")
            else:
                logging.warning(f"Empty page_name in login_data.txt for profile: {entry.get('profile_name')}")

        logging.info(f"Loaded {len(credentials)} credential entries from {login_file.name}")
        return credentials

    def _get_creator_videos(self, creator_name: str) -> List[Path]:
        """Get videos for creator"""
        creator_path = self.paths.creators_root / creator_name
        if not creator_path.exists():
            return []
        return get_video_files(creator_path)

    def _collect_creator_folders(self, account_dir: Path) -> List[str]:
        """
        Collect creator folders from account directory.

        Checks for 'Creators' subfolder first (new structure),
        then falls back to direct subfolders (legacy).

        Structure:
            account_dir/
            ├── login_data.txt
            └── Creators/          <- Check here first
                ├── Creator1/
                ├── Creator2/
                └── ...
        """
        # Check for Creators subfolder first (new structure)
        creators_subfolder = account_dir / 'Creators'
        if creators_subfolder.exists() and creators_subfolder.is_dir():
            logging.debug(f"Found Creators subfolder in {account_dir.name}")
            return sorted(
                [item.name for item in creators_subfolder.iterdir()
                 if item.is_dir() and not item.name.startswith('_')]
            )

        # Fall back to direct subfolders (legacy structure)
        logging.debug(f"Using direct subfolders for {account_dir.name}")
        return sorted(
            [item.name for item in account_dir.iterdir()
             if item.is_dir() and not item.name.startswith('_') and item.name != 'Creators']
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

    def _resolve_creator_shortcut_dir(self, account_root: Path, creator_name: str) -> Optional[Path]:
        """
        Resolve creator shortcut directory, checking for Creators subfolder.

        Args:
            account_root: Account root directory (email folder)
            creator_name: Creator/page name

        Returns:
            Path to creator shortcut directory, or None if not found
        """
        # Check for new structure: account_root/Creators/creator_name
        creators_subdir = account_root / 'Creators' / creator_name
        if creators_subdir.exists() and creators_subdir.is_dir():
            logging.debug(f"Found creator shortcuts in Creators subfolder: {creators_subdir}")
            return creators_subdir

        # Fall back to legacy structure: account_root/creator_name
        direct_dir = account_root / creator_name
        if direct_dir.exists() and direct_dir.is_dir():
            logging.debug(f"Found creator shortcuts in direct path: {direct_dir}")
            return direct_dir

        logging.warning(f"Creator shortcut directory not found for {creator_name}")
        return None

    def _infer_browser_type(self, account_name: str, account_dir: Path) -> str:
        """
        Infer browser type for an account folder.

        Priority:
        1. Check login_data.txt for browser_type field (highest priority)
        2. Check account folder name for browser hints
        3. Fall back to configured automation mode
        """
        # First priority: Check login_data.txt
        login_file = account_dir / 'login_data.txt'
        if login_file.exists():
            entries = parse_login_data(login_file)
            for entry in entries:
                browser_type = entry.get('browser_type', '').strip().lower()
                if browser_type:
                    logging.debug(f"Browser type from login_data.txt: {browser_type}")
                    return browser_type

        # Second priority: Check folder name
        lower_name = account_name.lower()
        if 'gologin' in lower_name or 'orbita' in lower_name:
            return 'gologin'
        if 'ix' in lower_name or 'incogniton' in lower_name:
            return 'ix'
        if 'vpn' in lower_name:
            return 'vpn'

        # Fall back to configured mode
        logging.debug(f"Using default automation mode: {self.mode.value}")
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
