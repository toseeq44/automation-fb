"""
Browser Monitor - Intelligent browser detection and state management
Handles browser window detection, state checking, and screen analysis
"""

import logging
import time
import socket
from pathlib import Path
from typing import Optional, Tuple

try:
    import pygetwindow as gw
    import pyautogui
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    logging.warning("Browser monitoring tools not available")


class BrowserMonitor:
    """Monitor and manage browser state intelligently"""

    def __init__(self, browser_type: str = 'ix'):
        """
        Initialize browser monitor

        Args:
            browser_type: Type of browser ('ix', 'gologin', etc.)
        """
        self.browser_type = browser_type
        self.window = None
        self.load_check_interval = 2  # seconds
        self.max_wait_time = 120  # max 2 minutes for full load

    def check_network_connectivity(self) -> bool:
        """
        Check if internet connection is available

        Returns:
            True if connected, False otherwise
        """
        try:
            # Try to connect to Google DNS
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            logging.info("✓ Network connectivity: OK")
            return True
        except (socket.timeout, socket.error):
            logging.error("✗ Network connectivity: FAILED")
            return False

    def wait_for_network(self, max_retries: int = 3) -> bool:
        """
        Wait for network to be available

        Args:
            max_retries: Number of retry attempts

        Returns:
            True if network available, False if max retries exceeded
        """
        for attempt in range(max_retries):
            if self.check_network_connectivity():
                return True

            if attempt < max_retries - 1:
                wait_time = 5
                logging.warning(f"⚠ Network not available. Retrying in {wait_time}s... ({attempt + 1}/{max_retries})")
                time.sleep(wait_time)

        logging.error(f"✗ Network unavailable after {max_retries} attempts")
        return False

    def find_browser_window(self, title_patterns: list, timeout: int = 30) -> Optional[object]:
        """
        Find browser window with timeout and retry logic

        Args:
            title_patterns: List of possible window title patterns
            timeout: Maximum time to wait

        Returns:
            Window object if found, None otherwise
        """
        start_time = time.time()
        attempt = 0

        while (time.time() - start_time) < timeout:
            attempt += 1

            for pattern in title_patterns:
                try:
                    windows = gw.getWindowsWithTitle(pattern)
                    if windows:
                        window = windows[0]
                        logging.info(f"✓ Found browser window: '{window.title}'")
                        self.window = window
                        return window
                except Exception as e:
                    logging.debug(f"Error searching for '{pattern}': {e}")

            elapsed = time.time() - start_time
            if elapsed < timeout:
                remaining = timeout - elapsed
                if attempt % 5 == 0:  # Log every 5 attempts
                    logging.debug(f"  Still searching... ({int(elapsed)}/{timeout}s)")
                time.sleep(2)

        logging.warning(f"⚠ Browser window not found after {timeout}s")
        return None

    def is_browser_responsive(self) -> bool:
        """
        Check if browser window is responsive

        Returns:
            True if responsive, False otherwise
        """
        if not self.window:
            return False

        try:
            # Try to activate window - if it works, it's responsive
            self.window.activate()
            time.sleep(0.5)
            return True
        except Exception as e:
            logging.debug(f"Browser not responsive: {e}")
            return False

    def wait_for_browser_load(self, timeout: int = 15, show_activity: bool = True) -> bool:
        """
        Wait for browser window to be responsive and ready

        Note: For desktop apps (like ixBrowser), this just waits for responsiveness.
        For web apps, use screenshot comparison or other techniques.

        Args:
            timeout: Maximum time to wait (seconds)
            show_activity: Show mouse activity indicator during wait

        Returns:
            True if window is responsive, False if timeout
        """
        if not self.window:
            logging.error("No browser window found")
            return False

        start_time = time.time()

        logging.info(f"⏳ Waiting for browser to be responsive (max {timeout}s)...")

        # Optional: Show activity indicator
        activity = None
        if show_activity:
            try:
                from .mouse_activity import MouseActivityIndicator
                activity = MouseActivityIndicator()
                activity.start()
            except Exception as e:
                logging.debug(f"Could not start activity indicator: {e}")

        try:
            while (time.time() - start_time) < timeout:
                elapsed = int(time.time() - start_time)

                # Check if window is responsive
                if self.is_browser_responsive():
                    logging.info(f"✓ Browser ready ({elapsed}s)")
                    return True

                remaining = timeout - elapsed
                if remaining > 0 and elapsed % 5 == 0:
                    logging.debug(f"  Waiting for browser... ({remaining}s remaining)")

                time.sleep(1)

            logging.warning(f"⚠ Browser responsiveness timeout after {timeout}s")
            return False

        finally:
            if activity:
                activity.stop()

    def maximize_window(self) -> bool:
        """
        Maximize browser window for better visibility

        Returns:
            True if successful, False otherwise
        """
        if not self.window:
            logging.error("No browser window to maximize")
            return False

        try:
            self.window.maximize()
            time.sleep(1)
            logging.info("✓ Browser window maximized")
            return True
        except Exception as e:
            logging.warning(f"⚠ Could not maximize window: {e}")
            return False

    def get_browser_status_summary(self) -> dict:
        """
        Get comprehensive browser status

        Returns:
            Dictionary with status information
        """
        return {
            'browser_type': self.browser_type,
            'window_found': self.window is not None,
            'window_title': self.window.title if self.window else None,
            'window_responsive': self.is_browser_responsive(),
            'network_connected': self.check_network_connectivity()
        }
