"""
Workflow Controller
===================
Orchestrates complete browser automation workflow.

This module provides end-to-end workflow coordination:
1. Desktop browser search
2. Browser launch
3. Fullscreen activation
4. User status detection
5. Logout if needed
6. Login with credentials
7. Verification and post-login actions
"""

import logging
import time
from typing import Optional, Dict, Any
from pathlib import Path

from .launcher import BrowserLauncher
from .screen_detector import ScreenDetector
from .mouse_controller import MouseController
from .login_manager import LoginManager
from .fullscreen_manager import FullscreenManager


class WorkflowController:
    """Orchestrates complete browser automation workflow."""

    def __init__(self, browser_type: str = 'gologin', config: Optional[Dict] = None):
        """
        Initialize workflow controller.

        Args:
            browser_type: Type of browser ('gologin', 'ix', etc.)
            config: Configuration dictionary
        """
        self.browser_type = browser_type
        self.config = config or {}

        # Initialize components
        self.launcher = BrowserLauncher(config)
        self.screen_detector = ScreenDetector()
        self.mouse = MouseController()
        self.fullscreen_mgr = FullscreenManager()
        self.login_mgr = None  # Will be initialized with driver

        # Workflow state
        self.workflow_state = {
            'browser_launched': False,
            'fullscreen_enabled': False,
            'user_logged_out': False,
            'user_logged_in': False,
            'workflow_completed': False
        }

        logging.info("WorkflowController initialized for browser: %s", browser_type)

    def execute_complete_workflow(self, email: str, password: str, **kwargs) -> bool:
        """
        Execute complete browser automation workflow.

        Workflow Steps:
        1. Search for browser on desktop
        2. Launch browser
        3. Enable fullscreen (F11)
        4. Check user login status
        5. Logout current user if logged in
        6. Login with provided credentials
        7. Verify login success

        Args:
            email: Facebook email/username
            password: Facebook password
            **kwargs: Additional workflow options
                - skip_fullscreen: Skip fullscreen step
                - skip_logout: Skip logout step
                - startup_wait: Wait time after browser launch
                - show_animations: Show trust-building animations

        Returns:
            True if workflow completed successfully

        Example:
            >>> controller = WorkflowController('gologin')
            >>> controller.execute_complete_workflow('user@email.com', 'password123')
        """
        logging.info("="*60)
        logging.info("STARTING COMPLETE BROWSER AUTOMATION WORKFLOW")
        logging.info("="*60)

        try:
            # Step 1: Desktop browser search
            logging.info("\n[STEP 1/7] Searching for browser on desktop...")
            if not self._step_search_browser():
                logging.error("Step 1 FAILED: Browser not found")
                return False

            # Step 2: Launch browser
            logging.info("\n[STEP 2/7] Launching browser...")
            startup_wait = kwargs.get('startup_wait', 15)
            if not self._step_launch_browser(startup_wait=startup_wait):
                logging.error("Step 2 FAILED: Browser launch failed")
                return False

            # Show trust-building animation
            if kwargs.get('show_animations', True):
                logging.info("Showing trust-building animation...")
                self.mouse.circular_idle_movement(duration=2.0, radius=40)

            # Step 3: Enable fullscreen
            if not kwargs.get('skip_fullscreen', False):
                logging.info("\n[STEP 3/7] Enabling fullscreen mode...")
                if not self._step_enable_fullscreen():
                    logging.warning("Step 3 WARNING: Fullscreen may have failed, continuing...")
            else:
                logging.info("\n[STEP 3/7] Fullscreen skipped")
                self.workflow_state['fullscreen_enabled'] = True

            # Step 4: Check user status
            logging.info("\n[STEP 4/7] Checking user login status...")
            user_status = self._step_check_user_status()

            # Step 5: Logout if needed
            if not kwargs.get('skip_logout', False) and user_status['logged_in']:
                logging.info("\n[STEP 5/7] Logging out current user...")
                if not self._step_logout_user():
                    logging.warning("Step 5 WARNING: Logout may have failed, attempting login anyway...")
            else:
                logging.info("\n[STEP 5/7] Logout not needed or skipped")
                self.workflow_state['user_logged_out'] = True

            # Step 6: Login with credentials
            logging.info("\n[STEP 6/7] Logging in with provided credentials...")
            if not self._step_login_user(email, password):
                logging.error("Step 6 FAILED: Login failed")
                return False

            # Show success animation
            if kwargs.get('show_animations', True):
                logging.info("Showing success animation...")
                self.mouse.circular_idle_movement(duration=2.0, radius=50)

            # Step 7: Verify and complete
            logging.info("\n[STEP 7/7] Verifying workflow completion...")
            if not self._step_verify_completion():
                logging.error("Step 7 FAILED: Verification failed")
                return False

            # Mark workflow as completed
            self.workflow_state['workflow_completed'] = True

            logging.info("="*60)
            logging.info("WORKFLOW COMPLETED SUCCESSFULLY!")
            logging.info("="*60)

            return True

        except Exception as e:
            logging.error("WORKFLOW FAILED with exception: %s", e, exc_info=True)
            return False

    def _step_search_browser(self) -> bool:
        """Step 1: Search for browser on desktop."""
        shortcut_path = self.launcher.find_browser_on_desktop(self.browser_type)

        if shortcut_path:
            logging.info("✓ Browser shortcut found: %s", shortcut_path)
            return True
        else:
            logging.error("✗ Browser shortcut not found")
            # Show download popup
            self.launcher.show_download_popup(self.browser_type)
            return False

    def _step_launch_browser(self, startup_wait: int = 15) -> bool:
        """Step 2: Launch browser."""
        success = self.launcher.launch_generic(
            self.browser_type,
            startup_wait=startup_wait,
            show_popup=True
        )

        if success:
            logging.info("✓ Browser launched successfully")
            self.workflow_state['browser_launched'] = True

            # Show circular animation during startup wait
            logging.info("Waiting for browser to fully initialize...")
            self.mouse.circular_idle_movement(duration=5.0, radius=40)

            return True
        else:
            logging.error("✗ Browser launch failed")
            return False

    def _step_enable_fullscreen(self) -> bool:
        """Step 3: Enable fullscreen mode."""
        # Focus browser window first
        self.fullscreen_mgr.focus_browser_window()
        time.sleep(1)

        # Enable fullscreen
        success = self.fullscreen_mgr.enable_fullscreen(verify=True, retry_count=3)

        if success:
            logging.info("✓ Fullscreen mode enabled")
            self.workflow_state['fullscreen_enabled'] = True
            return True
        else:
            logging.warning("✗ Fullscreen mode may not be enabled")
            return False

    def _step_check_user_status(self) -> Dict[str, Any]:
        """Step 4: Check user login status."""
        user_status = self.screen_detector.detect_user_status()

        if user_status['logged_in']:
            logging.info("✓ User is currently LOGGED IN (confidence: %.2f)", user_status.get('confidence', 0))
        else:
            logging.info("✓ User is currently LOGGED OUT")

        return user_status

    def _step_logout_user(self) -> bool:
        """Step 5: Logout current user."""
        # Initialize login manager if not already done
        if not self.login_mgr:
            self.login_mgr = LoginManager()

        success = self.login_mgr.logout_current_user(timeout=30)

        if success:
            logging.info("✓ User logged out successfully")
            self.workflow_state['user_logged_out'] = True
            return True
        else:
            logging.error("✗ Logout failed")
            return False

    def _step_login_user(self, email: str, password: str) -> bool:
        """Step 6: Login with credentials."""
        # Initialize login manager if not already done
        if not self.login_mgr:
            self.login_mgr = LoginManager()

        # Show trust-building animation before login
        logging.info("Preparing to login...")
        self.mouse.circular_idle_movement(duration=2.0, radius=35)

        success = self.login_mgr.login_user(email, password, timeout=30)

        if success:
            logging.info("✓ User logged in successfully")
            self.workflow_state['user_logged_in'] = True
            return True
        else:
            logging.error("✗ Login failed")
            return False

    def _step_verify_completion(self) -> bool:
        """Step 7: Verify workflow completion."""
        # Check all critical steps completed
        critical_steps = [
            'browser_launched',
            'user_logged_in'
        ]

        all_completed = all(self.workflow_state.get(step, False) for step in critical_steps)

        if all_completed:
            logging.info("✓ All critical steps completed")

            # Final verification with image recognition
            final_status = self.screen_detector.detect_user_status()

            if final_status['logged_in']:
                logging.info("✓ Final verification: User is logged in")
                return True
            else:
                logging.warning("✗ Final verification: User may not be logged in")
                return False
        else:
            logging.error("✗ Not all critical steps completed")
            logging.error("Workflow state: %s", self.workflow_state)
            return False

    def set_driver(self, driver: Any) -> None:
        """
        Set Selenium WebDriver instance for login operations.

        Args:
            driver: Selenium WebDriver instance
        """
        if not self.login_mgr:
            self.login_mgr = LoginManager(driver)
        else:
            self.login_mgr.set_driver(driver)

        logging.info("WebDriver instance set for workflow")

    def get_workflow_state(self) -> Dict[str, Any]:
        """
        Get current workflow state.

        Returns:
            Dictionary with workflow state information
        """
        return self.workflow_state.copy()

    def reset_workflow(self) -> None:
        """Reset workflow state."""
        self.workflow_state = {
            'browser_launched': False,
            'fullscreen_enabled': False,
            'user_logged_out': False,
            'user_logged_in': False,
            'workflow_completed': False
        }

        logging.info("Workflow state reset")

    def execute_browser_launch_only(self, **kwargs) -> bool:
        """
        Execute only browser launch steps (search + launch + fullscreen).

        Args:
            **kwargs: Launch options

        Returns:
            True if browser launched successfully
        """
        logging.info("Executing browser launch workflow...")

        try:
            # Step 1: Search
            if not self._step_search_browser():
                return False

            # Step 2: Launch
            startup_wait = kwargs.get('startup_wait', 15)
            if not self._step_launch_browser(startup_wait=startup_wait):
                return False

            # Step 3: Fullscreen
            if not kwargs.get('skip_fullscreen', False):
                self._step_enable_fullscreen()

            logging.info("Browser launch workflow completed")
            return True

        except Exception as e:
            logging.error("Browser launch workflow failed: %s", e, exc_info=True)
            return False

    def execute_login_workflow(self, email: str, password: str, **kwargs) -> bool:
        """
        Execute only login workflow (assumes browser already running).

        Args:
            email: Facebook email
            password: Facebook password
            **kwargs: Login options

        Returns:
            True if login successful
        """
        logging.info("Executing login workflow...")

        try:
            # Check status
            user_status = self._step_check_user_status()

            # Logout if needed
            if user_status['logged_in'] and not kwargs.get('skip_logout', False):
                self._step_logout_user()

            # Login
            if self._step_login_user(email, password):
                logging.info("Login workflow completed")
                return True
            else:
                return False

        except Exception as e:
            logging.error("Login workflow failed: %s", e, exc_info=True)
            return False

    def cleanup(self) -> None:
        """
        Cleanup resources and close browser if needed.
        """
        logging.info("Cleaning up workflow controller...")

        # Optionally kill browser
        if self.config.get('cleanup_kill_browser', False):
            logging.info("Killing browser as part of cleanup...")
            self.launcher.kill_browser(self.browser_type, force=True)

        logging.info("Cleanup completed")
