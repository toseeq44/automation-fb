"""
Main orchestrator that routes between Legacy and Intelligent automation approaches.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any
import json


class AutomationOrchestrator:
    """
    Main orchestrator that determines which approach to use based on settings.

    This class acts as a router between:
    - Legacy approach: Original code from _legacy folder
    - Intelligent approach: New modular code with browser, auth, upload modules
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the orchestrator.

        Args:
            base_dir: Base directory (defaults to auto_uploader module directory)
        """
        if base_dir is None:
            self.base_dir = Path(__file__).parent
        else:
            self.base_dir = Path(base_dir)

        # Load settings to determine approach
        self.settings_path = self.base_dir / 'data_files' / 'settings.json'
        self.settings = self._load_settings()
        self.approach = self.settings.get('automation', {}).get('approach', 'legacy')

        logging.info(f"Orchestrator initialized with approach: {self.approach}")

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from settings.json"""
        try:
            if self.settings_path.exists():
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logging.warning(f"Settings file not found: {self.settings_path}")
                return {}
        except Exception as e:
            logging.error(f"Error loading settings: {e}")
            return {}

    def run(self) -> bool:
        """
        Execute the automation workflow based on selected approach.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.approach == 'intelligent':
                return self._run_intelligent_approach()
            else:
                return self._run_legacy_approach()
        except Exception as e:
            logging.error(f"Error in orchestrator.run(): {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def _run_legacy_approach(self) -> bool:
        """
        Run the legacy approach using original code.

        Returns:
            bool: True if successful, False otherwise
        """
        logging.info("="*60)
        logging.info("🔧 Using LEGACY Approach")
        logging.info("="*60)

        try:
            from _legacy.core import FacebookAutoUploader

            uploader = FacebookAutoUploader(base_dir=self.base_dir)
            success = uploader.run()

            return success
        except Exception as e:
            logging.error(f"Error in legacy approach: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def _run_intelligent_approach(self) -> bool:
        """
        Run the intelligent approach using new modular code.

        This uses:
        - browser/ module for browser automation
        - auth/ module for authentication
        - upload/ module for video uploads

        Returns:
            bool: True if successful, False otherwise
        """
        logging.info("="*60)
        logging.info("🤖 Using INTELLIGENT Approach")
        logging.info("="*60)

        try:
            # Import intelligent modules
            from browser.launcher import BrowserLauncher
            from auth.login_manager import LoginManager
            from auth.session_validator import SessionValidator
            from core.screen_detector import ScreenDetector
            from utils.mouse_controller import MouseController

            # Get paths from settings
            paths = self.settings.get('automation', {}).get('paths', {})
            creators_root = Path(paths.get('creators_root', ''))
            shortcuts_root = Path(paths.get('shortcuts_root', ''))

            if not creators_root.exists() or not shortcuts_root.exists():
                logging.error("Creators or shortcuts folder not found!")
                logging.error(f"Creators: {creators_root}")
                logging.error(f"Shortcuts: {shortcuts_root}")
                return False

            logging.info(f"Creators folder: {creators_root}")
            logging.info(f"Shortcuts folder: {shortcuts_root}")

            # Scan shortcuts folder for login_data.txt files
            mapping = self._scan_shortcuts(shortcuts_root)

            if not mapping:
                logging.warning("No browser accounts found with login_data.txt!")
                return False

            logging.info(f"Found {len(mapping)} browser account(s)")

            # Process each browser account
            for account_info in mapping:
                try:
                    success = self._process_account_intelligent(
                        account_info,
                        creators_root
                    )
                    if not success:
                        logging.warning(f"Failed to process account: {account_info['account_name']}")
                except Exception as e:
                    logging.error(f"Error processing account {account_info['account_name']}: {e}")
                    continue

            logging.info("="*60)
            logging.info("🤖 Intelligent Approach Completed!")
            logging.info("="*60)
            return True

        except ImportError as e:
            logging.error(f"Failed to import intelligent modules: {e}")
            logging.error("Make sure browser, auth, upload modules are properly implemented.")
            return False
        except Exception as e:
            logging.error(f"Error in intelligent approach: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False

    def _scan_shortcuts(self, shortcuts_root: Path) -> list:
        """
        Scan shortcuts folder for browser accounts with login_data.txt

        Args:
            shortcuts_root: Path to shortcuts folder

        Returns:
            List of account info dicts with keys: account_name, login_data_path, browser_type
        """
        accounts = []

        # Check for login_data.txt directly in shortcuts_root subfolders
        for folder in shortcuts_root.iterdir():
            if not folder.is_dir():
                continue

            login_data = folder / 'login_data.txt'
            if login_data.exists():
                accounts.append({
                    'account_name': folder.name,
                    'login_data_path': login_data,
                    'browser_type': self._infer_browser_type(folder.name)
                })
                logging.info(f"Found account: {folder.name}")

        return accounts

    def _infer_browser_type(self, folder_name: str) -> str:
        """Infer browser type from folder name"""
        name_lower = folder_name.lower()
        if 'gologin' in name_lower:
            return 'gologin'
        elif 'ix' in name_lower or 'incogniton' in name_lower:
            return 'ix'
        else:
            return 'free_automation'

    def _process_account_intelligent(
        self,
        account_info: Dict[str, Any],
        creators_root: Path
    ) -> bool:
        """
        Process a single browser account using intelligent approach.

        Args:
            account_info: Dict with account details
            creators_root: Path to creators folder

        Returns:
            bool: True if successful
        """
        logging.info("="*60)
        logging.info(f"Processing account: {account_info['account_name']}")
        logging.info(f"Browser type: {account_info['browser_type']}")
        logging.info("="*60)

        # Parse login_data.txt
        login_data = self._parse_login_data(account_info['login_data_path'])

        if not login_data:
            logging.error("No login data found!")
            return False

        logging.info(f"Found {len(login_data)} creator account(s) in login_data.txt")

        # TODO: Implement the actual workflow:
        # 1. Launch browser using browser/launcher.py
        # 2. For each creator in login_data:
        #    a. Login using auth/login_manager.py
        #    b. Validate session using auth/session_validator.py
        #    c. Find videos in creators_root/{creator_name}/
        #    d. Upload videos using upload module
        #    e. Logout using auth/logout_handler.py

        logging.info("⚠️ Intelligent approach workflow not yet fully implemented")
        logging.info("This will be completed in next phase")

        return True

    def _parse_login_data(self, login_data_path: Path) -> list:
        """
        Parse login_data.txt file.

        Format: profile_name|facebook_email|facebook_password|page_name|page_id

        Args:
            login_data_path: Path to login_data.txt

        Returns:
            List of dicts with parsed login data
        """
        accounts = []

        try:
            with open(login_data_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Parse pipe-separated format
                    parts = line.split('|')
                    if len(parts) >= 5:
                        accounts.append({
                            'profile_name': parts[0].strip(),
                            'email': parts[1].strip(),
                            'password': parts[2].strip(),
                            'page_name': parts[3].strip(),
                            'page_id': parts[4].strip()
                        })
        except Exception as e:
            logging.error(f"Error parsing login_data.txt: {e}")

        return accounts
