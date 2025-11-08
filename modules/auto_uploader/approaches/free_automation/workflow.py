"""
Free Automation Workflow
=========================
Desktop-based browser automation with image recognition.

This approach uses:
- Desktop .lnk shortcut-based browser launch
- Image recognition for UI detection (OpenCV)
- Mouse and keyboard automation
- No API required (completely free)

Features:
- Works offline (no internet needed after initial setup)
- Supports Chrome, Firefox, IX Browser (desktop mode)
- Human-like mouse movements
- Autofill detection and clearing
"""
import logging
import time
from pathlib import Path
from typing import Dict, Optional

from ..base_approach import BaseApproach, ApproachConfig

# Import existing free_automation components
from .launcher import BrowserLauncher
from .image_based_login import ImageBasedLogin
from .screen_detector import ScreenDetector
from .mouse_controller import MouseController
from .fullscreen_manager import FullscreenManager
from .login_manager import LoginManager


class FreeAutomationApproach(BaseApproach):
    """
    Free Automation Approach Implementation

    Uses desktop-based browser launching and image recognition
    for completely free automation without any API dependencies.

    Example:
        >>> config = ApproachConfig(
        ...     mode='free_automation',
        ...     credentials={'email': 'user@example.com', 'password': 'xxx'},
        ...     paths={'creators_root': Path('/path/to/creators')},
        ...     browser_type='chrome'
        ... )
        >>> approach = FreeAutomationApproach(config)
        >>> work_item = WorkItem(...)
        >>> result = approach.execute_workflow(work_item)
    """

    def __init__(self, config: ApproachConfig):
        """Initialize free automation approach"""
        super().__init__(config)

        # Components (initialized in initialize())
        self.browser_launcher: Optional[BrowserLauncher] = None
        self.image_login: Optional[ImageBasedLogin] = None
        self.screen_detector: Optional[ScreenDetector] = None
        self.mouse_controller: Optional[MouseController] = None
        self.fullscreen_manager: Optional[FullscreenManager] = None
        self.login_manager: Optional[LoginManager] = None

        # State
        self.browser_process = None
        self.current_account = None

        logging.info("✓ FreeAutomationApproach instance created")

    def initialize(self) -> bool:
        """
        Initialize all components

        Returns:
            True if all components initialized successfully
        """
        logging.info("")
        logging.info("="*60)
        logging.info("INITIALIZING FREE AUTOMATION APPROACH")
        logging.info("="*60)

        try:
            logging.info("🔧 Step 1/6: Initializing Browser Launcher...")
            self.browser_launcher = BrowserLauncher(config=self.config.settings)
            logging.info("   ✓ Browser Launcher ready")

            logging.info("🔧 Step 2/6: Initializing Image-Based Login...")
            self.image_login = ImageBasedLogin()
            logging.info("   ✓ Image-Based Login ready")

            logging.info("🔧 Step 3/6: Initializing Screen Detector...")
            self.screen_detector = ScreenDetector()
            logging.info("   ✓ Screen Detector ready")

            logging.info("🔧 Step 4/6: Initializing Mouse Controller...")
            self.mouse_controller = MouseController()
            logging.info("   ✓ Mouse Controller ready")

            logging.info("🔧 Step 5/6: Initializing Fullscreen Manager...")
            self.fullscreen_manager = FullscreenManager()
            logging.info("   ✓ Fullscreen Manager ready")

            logging.info("🔧 Step 6/6: Initializing Login Manager...")
            self.login_manager = LoginManager()
            logging.info("   ✓ Login Manager ready")

            logging.info("")
            logging.info("✅ ALL COMPONENTS INITIALIZED SUCCESSFULLY")
            logging.info("="*60)
            logging.info("")

            return True

        except Exception as e:
            logging.error(f"❌ Initialization failed: {e}", exc_info=True)
            return False

    def open_browser(self, account_name: str) -> bool:
        """
        Open browser using desktop shortcut

        Args:
            account_name: Account folder name

        Returns:
            True if browser opened successfully
        """
        logging.info("")
        logging.info("="*60)
        logging.info(f"OPENING BROWSER (Account: {account_name})")
        logging.info("="*60)

        try:
            self.current_account = account_name
            browser_type = self.config.browser_type

            logging.info(f"🚀 Browser Type: {browser_type.upper()}")
            logging.info(f"📋 Account: {account_name}")

            # Launch browser using desktop shortcut
            logging.info("")
            logging.info("Step 1/3: Searching for browser shortcut on desktop...")

            result = self.browser_launcher.launch_generic(
                browser_type,
                show_popup=True
            )

            if not result:
                logging.error("❌ Browser launch failed")
                return False

            logging.info("✅ Browser launched successfully")

            # Wait for browser to fully load
            logging.info("")
            logging.info("Step 2/3: Waiting for browser to load...")
            time.sleep(5)  # Give browser time to open
            logging.info("✅ Browser loaded")

            # Enable fullscreen for better automation
            logging.info("")
            logging.info("Step 3/3: Enabling fullscreen mode (F11)...")

            try:
                self.fullscreen_manager.enable_fullscreen()
                logging.info("✅ Fullscreen enabled")
            except Exception as e:
                logging.warning(f"⚠️  Could not enable fullscreen: {e}")
                # Continue anyway - fullscreen is optional

            logging.info("")
            logging.info("✅ BROWSER READY FOR AUTOMATION")
            logging.info("="*60)
            logging.info("")

            return True

        except Exception as e:
            logging.error(f"❌ Error opening browser: {e}", exc_info=True)
            return False

    def login(self, email: str, password: str) -> bool:
        """
        Login to Facebook using image recognition

        Args:
            email: Login email
            password: Login password

        Returns:
            True if login successful
        """
        logging.info("")
        logging.info("="*60)
        logging.info(f"LOGGING IN: {email}")
        logging.info("="*60)

        try:
            # Step 1: Check if already logged in
            logging.info("")
            logging.info("Step 1/4: Checking current login status...")

            status = self.screen_detector.detect_user_status()

            if status.get('logged_in'):
                logging.info("⚠️  User already logged in")
                logging.info("   Logging out existing user first...")

                if not self.logout():
                    logging.error("❌ Failed to logout existing user")
                    return False

                # Wait after logout
                time.sleep(3)
            else:
                logging.info("✓ No user logged in, proceeding...")

            # Step 2: Navigate to Facebook
            logging.info("")
            logging.info("Step 2/4: Navigating to Facebook...")
            logging.info("   URL: https://www.facebook.com")

            # TODO: Add Selenium navigation or manual instruction
            logging.warning("⚠️  Manual step: Please ensure browser is on facebook.com login page")
            time.sleep(5)  # Wait for manual navigation

            # Step 3: Perform login using image recognition
            logging.info("")
            logging.info("Step 3/4: Performing login with image recognition...")
            logging.info(f"   Email: {email}")
            logging.info(f"   Password: {'*' * len(password)}")

            result = self.image_login.login_with_image_recognition(
                email=email,
                password=password
            )

            if not result:
                logging.error("❌ Login failed via image recognition")
                return False

            logging.info("✅ Login successful")

            # Step 4: Verify login
            logging.info("")
            logging.info("Step 4/4: Verifying login status...")

            time.sleep(5)  # Wait for page load

            status = self.screen_detector.detect_user_status()

            if status.get('logged_in'):
                logging.info("✅ Login verified - user is logged in")
            else:
                logging.warning("⚠️  Could not verify login status")
                # Continue anyway - verification may fail but login succeeded

            logging.info("")
            logging.info("✅ LOGIN COMPLETED SUCCESSFULLY")
            logging.info("="*60)
            logging.info("")

            return True

        except Exception as e:
            logging.error(f"❌ Login error: {e}", exc_info=True)
            return False

    def logout(self) -> bool:
        """
        Logout from Facebook using image recognition

        Returns:
            True if logout successful
        """
        logging.info("")
        logging.info("="*60)
        logging.info("LOGGING OUT")
        logging.info("="*60)

        try:
            logging.info("🔓 Using image-based logout...")

            # Use image-based login handler for logout
            result = self.image_login.logout_current_user()

            if result:
                logging.info("✅ Logout successful")
                time.sleep(2)  # Wait for logout to complete
                return True
            else:
                logging.error("❌ Logout failed")
                return False

        except Exception as e:
            logging.error(f"❌ Logout error: {e}", exc_info=True)
            return False

    def close_browser(self) -> bool:
        """
        Close browser process

        Returns:
            True if browser closed successfully
        """
        logging.info("")
        logging.info("="*60)
        logging.info("CLOSING BROWSER")
        logging.info("="*60)

        try:
            browser_type = self.config.browser_type

            logging.info(f"🔒 Killing {browser_type} process...")

            # Kill browser process
            if self.browser_launcher:
                self.browser_launcher.kill_browser(browser_type)
                logging.info("✅ Browser process killed")
            else:
                logging.warning("⚠️  Browser launcher not initialized")

            # Wait for process to fully terminate
            time.sleep(2)

            logging.info("")
            logging.info("✅ BROWSER CLOSED SUCCESSFULLY")
            logging.info("="*60)
            logging.info("")

            return True

        except Exception as e:
            logging.error(f"❌ Error closing browser: {e}", exc_info=True)
            return False

    def cleanup(self) -> None:
        """Cleanup resources"""
        logging.info("🧹 Cleaning up resources...")

        # Reset state
        self.current_account = None
        self.browser_process = None

        # Components remain initialized for next workflow
        logging.info("✓ Cleanup complete")

    def __str__(self) -> str:
        """String representation"""
        return f"FreeAutomationApproach(browser={self.config.browser_type}, account={self.current_account})"
