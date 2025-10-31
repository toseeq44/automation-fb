"""
Facebook Upload Bot - Browser Controller
Handles browser launching, profile management, and Selenium connection
"""

import os
import time
import logging
import subprocess
import platform
from pathlib import Path
from typing import Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

from .configuration import SettingsManager

# Try to import Windows-specific automation tools
try:
    import pyautogui
    import pygetwindow as gw
    WINDOWS_AUTOMATION_AVAILABLE = True
except ImportError:
    WINDOWS_AUTOMATION_AVAILABLE = False
    logging.warning("Windows automation tools not available (pyautogui/pygetwindow)")


class BrowserController:
    """Controls anti-detect browser launching and profile management"""

    def __init__(self, config: SettingsManager):
        """Initialize browser controller."""
        self.config = config
        self.active_browsers = {}
        self.active_drivers = {}
        self.platform = platform.system()

        if self.platform == 'Windows' and not WINDOWS_AUTOMATION_AVAILABLE:
            logging.warning("Running on Windows but automation tools not installed")

    def launch_browser(self, browser_type: str) -> Optional[Any]:
        """
        Launch GoLogin or Incogniton browser

        Args:
            browser_type: 'gologin' or 'ix'

        Returns:
            Browser window object or None
        """
        browser_type = browser_type.lower()
        logging.info(f"Launching {browser_type} browser...")

        # Check if browser is enabled
        if not self.config.get(f'browsers.{browser_type}.enabled', True):
            logging.warning(f"{browser_type} is disabled in config")
            return None

        browser_config = self.config.get(f'browsers.{browser_type}')
        if not browser_config:
            logging.error(f"No configuration found for {browser_type}")
            return None

        # Try different launch methods
        launched = False

        # Method 1: Desktop shortcut
        desktop_shortcut = os.path.expanduser(browser_config.get('desktop_shortcut', ''))
        if desktop_shortcut and os.path.exists(desktop_shortcut):
            try:
                if self.platform == 'Windows':
                    os.startfile(desktop_shortcut)
                    launched = True
                    logging.info(f"Launched {browser_type} from desktop shortcut")
            except Exception as e:
                logging.warning(f"Failed to launch from shortcut: {e}")

        # Method 2: Executable path
        if not launched:
            exe_path = browser_config.get('exe_path', '').replace('{user}', os.environ.get('USERNAME', os.environ.get('USER', '')))

            if exe_path and os.path.exists(exe_path):
                try:
                    subprocess.Popen(exe_path)
                    launched = True
                    logging.info(f"Launched {browser_type} from exe path")
                except Exception as e:
                    logging.error(f"Failed to launch from exe: {e}")

        if not launched:
            logging.error(f"Could not launch {browser_type}")
            return None

        # Wait for browser to start
        startup_wait = browser_config.get('startup_wait', 15)
        logging.info(f"Waiting {startup_wait} seconds for browser to start...")
        time.sleep(startup_wait)

        # Find browser window (if Windows automation available)
        browser_window = None
        if WINDOWS_AUTOMATION_AVAILABLE and self.platform == 'Windows':
            browser_window = self.find_browser_window(browser_type)
            if browser_window:
                self.active_browsers[browser_type] = browser_window
                logging.info(f"Found {browser_type} window")

        return browser_window if browser_window else True

    def find_browser_window(self, browser_type: str) -> Optional[Any]:
        """
        Find browser window by title

        Args:
            browser_type: Browser type

        Returns:
            Window object or None
        """
        if not WINDOWS_AUTOMATION_AVAILABLE:
            return None

        # Possible window titles for each browser
        title_patterns = {
            'gologin': ['GoLogin', 'Orbita'],
            'ix': ['Incogniton', 'IX Browser']
        }

        patterns = title_patterns.get(browser_type, [browser_type])

        for pattern in patterns:
            try:
                windows = gw.getWindowsWithTitle(pattern)
                if windows:
                    window = windows[0]
                    window.activate()  # Bring to front
                    time.sleep(1)
                    return window
            except Exception as e:
                logging.debug(f"Error finding window with title '{pattern}': {e}")

        logging.warning(f"Could not find window for {browser_type}")
        return None

    def open_profile_via_shortcut(self, browser_type: str, shortcut_path: Path) -> bool:
        """
        Open browser profile using shortcut file

        Args:
            browser_type: Browser type
            shortcut_path: Path to profile shortcut

        Returns:
            True if successful
        """
        logging.info(f"Opening profile via shortcut: {shortcut_path}")

        if not shortcut_path.exists():
            logging.error(f"Shortcut not found: {shortcut_path}")
            return False

        try:
            if self.platform == 'Windows':
                os.startfile(str(shortcut_path))
            else:
                subprocess.Popen(['xdg-open', str(shortcut_path)])

            # Wait for profile to open
            profile_wait = self.config.get(f'browsers.{browser_type}.profile_startup_wait', 10)
            logging.info(f"Waiting {profile_wait} seconds for profile to open...")
            time.sleep(profile_wait)

            return True

        except Exception as e:
            logging.error(f"Failed to open profile shortcut: {e}")
            return False

    def open_profile_via_gui(self, browser_window: Any, profile_name: str) -> bool:
        """
        Open profile using GUI automation (keyboard/mouse)

        Args:
            browser_window: Browser window object
            profile_name: Profile name to open

        Returns:
            True if successful
        """
        if not WINDOWS_AUTOMATION_AVAILABLE:
            logging.error("GUI automation not available")
            return False

        logging.info(f"Opening profile via GUI: {profile_name}")

        try:
            # Bring browser to front
            if browser_window:
                browser_window.activate()
                time.sleep(2)

            # Try common keyboard shortcuts to open profile manager
            # GoLogin: Ctrl+Shift+P
            pyautogui.hotkey('ctrl', 'shift', 'p')
            time.sleep(3)

            # Type profile name to search
            pyautogui.write(profile_name, interval=0.1)
            time.sleep(2)

            # Press Enter to select and open
            pyautogui.press('enter')
            time.sleep(5)

            logging.info("Profile opened via GUI automation")
            return True

        except Exception as e:
            logging.error(f"GUI automation failed: {e}")
            return False

    def connect_selenium(self, browser_type: str, profile_name: Optional[str] = None) -> Optional[webdriver.Chrome]:
        """
        Connect Selenium to running browser via debugging port

        Args:
            browser_type: Browser type
            profile_name: Profile name (for tracking)

        Returns:
            WebDriver instance or None
        """
        browser_config = self.config.get(f'browsers.{browser_type}')
        debug_port = browser_config.get('debug_port', 9222)

        logging.info(f"Connecting Selenium to {browser_type} on port {debug_port}...")

        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")

        # Anti-detection measures
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Additional options
        window_size = self.config.get('automation.window_size', '1920,1080')
        options.add_argument(f'--window-size={window_size}')

        if self.config.get('automation.headless', False):
            options.add_argument('--headless')

        if self.config.get('automation.disable_images', False):
            prefs = {"profile.managed_default_content_settings.images": 2}
            options.add_experimental_option("prefs", prefs)

        try:
            # Try to connect to browser
            driver = webdriver.Chrome(options=options)

            # Set page load timeout
            driver.set_page_load_timeout(120)

            # Store driver reference
            key = f"{browser_type}_{profile_name}" if profile_name else browser_type
            self.active_drivers[key] = driver

            logging.info(f"Selenium connected successfully to {browser_type}")
            return driver

        except WebDriverException as e:
            logging.error(f"Failed to connect Selenium: {e}")
            logging.info("Make sure:")
            logging.info(f"1. {browser_type} is running")
            logging.info(f"2. Remote debugging is enabled on port {debug_port}")
            logging.info("3. ChromeDriver is installed and in PATH")
            return None

        except Exception as e:
            logging.error(f"Unexpected error connecting Selenium: {e}")
            return None

    def find_profile_window(self, profile_name: str) -> Optional[Any]:
        """
        Find opened profile browser window

        Args:
            profile_name: Profile name

        Returns:
            Window object or None
        """
        if not WINDOWS_AUTOMATION_AVAILABLE:
            return None

        time.sleep(3)  # Give time for window to open

        # Look for browser windows
        window_titles = ['Chrome', 'Browser', 'Facebook', profile_name]

        for title in window_titles:
            try:
                windows = gw.getWindowsWithTitle(title)
                if windows:
                    # Return most recent window
                    return windows[-1]
            except Exception as e:
                logging.debug(f"Error finding window '{title}': {e}")

        return None

    def close_browser(self, browser_type: str):
        """
        Close browser and cleanup

        Args:
            browser_type: Browser type to close
        """
        logging.info(f"Closing {browser_type} browser...")

        # Close Selenium drivers
        drivers_to_close = [key for key in self.active_drivers.keys() if key.startswith(browser_type)]

        for key in drivers_to_close:
            try:
                self.active_drivers[key].quit()
                del self.active_drivers[key]
                logging.info(f"Closed driver: {key}")
            except Exception as e:
                logging.warning(f"Error closing driver {key}: {e}")

        # Close browser window
        if browser_type in self.active_browsers:
            try:
                if WINDOWS_AUTOMATION_AVAILABLE:
                    window = self.active_browsers[browser_type]
                    if hasattr(window, 'close'):
                        window.close()
                del self.active_browsers[browser_type]
            except Exception as e:
                logging.warning(f"Error closing browser window: {e}")

    def close_all(self):
        """Close all active browsers and drivers"""
        logging.info("Closing all browsers...")

        # Close all drivers
        for key, driver in list(self.active_drivers.items()):
            try:
                driver.quit()
                logging.info(f"Closed driver: {key}")
            except Exception as e:
                logging.warning(f"Error closing driver {key}: {e}")

        self.active_drivers.clear()
        self.active_browsers.clear()

    def is_browser_running(self, browser_type: str) -> bool:
        """
        Check if browser is running

        Args:
            browser_type: Browser type

        Returns:
            True if running
        """
        if not WINDOWS_AUTOMATION_AVAILABLE:
            return False

        browser_window = self.find_browser_window(browser_type)
        return browser_window is not None

    def restart_browser(self, browser_type: str) -> Optional[Any]:
        """
        Restart browser

        Args:
            browser_type: Browser type

        Returns:
            Browser window object or None
        """
        logging.info(f"Restarting {browser_type}...")

        self.close_browser(browser_type)
        time.sleep(3)

        return self.launch_browser(browser_type)
