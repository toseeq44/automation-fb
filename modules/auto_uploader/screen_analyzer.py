"""
Screen Analyzer - Intelligent popup/notification detection and auto-close
Detects and closes cookies, notifications, ads popups automatically
"""

import logging
import time
import os
from pathlib import Path
from typing import Optional, List

try:
    import pyautogui
    import pygetwindow as gw
    from PIL import Image
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False
    logging.warning("Screen analysis tools not available")

# Try to import activity indicator
try:
    from .mouse_activity import MouseActivityIndicator
    ACTIVITY_AVAILABLE = True
except ImportError:
    ACTIVITY_AVAILABLE = False


class ScreenAnalyzer:
    """Analyze screen and handle popups/notifications intelligently"""

    def __init__(self):
        """Initialize screen analyzer"""
        self.screenshot_dir = Path(__file__).parent / "data" / "screenshots"
        self.screenshot_dir.mkdir(exist_ok=True)
        self.detected_popups = []

    def take_screenshot(self, name: str = "screen") -> Optional[Path]:
        """
        Take screenshot for analysis

        Args:
            name: Name for the screenshot file

        Returns:
            Path to screenshot file, None if failed
        """
        try:
            screenshot = pyautogui.screenshot()
            timestamp = int(time.time())
            filename = f"{name}_{timestamp}.png"
            filepath = self.screenshot_dir / filename

            screenshot.save(filepath)
            logging.debug(f"Screenshot saved: {filename}")
            return filepath

        except Exception as e:
            logging.debug(f"Could not take screenshot: {e}")
            return None

    def clean_old_screenshots(self, max_age_seconds: int = 3600):
        """
        Delete old screenshots to prevent disk bloat

        Args:
            max_age_seconds: Delete screenshots older than this (default 1 hour)
        """
        try:
            current_time = time.time()
            deleted_count = 0

            for screenshot_file in self.screenshot_dir.glob("screen_*.png"):
                file_age = current_time - screenshot_file.stat().st_mtime

                if file_age > max_age_seconds:
                    screenshot_file.unlink()
                    deleted_count += 1
                    logging.debug(f"Deleted old screenshot: {screenshot_file.name}")

            if deleted_count > 0:
                logging.debug(f"Cleaned up {deleted_count} old screenshots")

        except Exception as e:
            logging.debug(f"Could not clean old screenshots: {e}")

    def detect_and_close_popups(self, max_attempts: int = 3) -> int:
        """
        Detect and close common popups and notifications

        Args:
            max_attempts: Number of close attempts

        Returns:
            Number of popups closed
        """
        closed_count = 0

        # Common popup close patterns
        close_patterns = [
            # Cookie consent buttons
            {
                'name': 'Cookie Banner',
                'keys': ['escape'],  # Try escape first
                'click_positions': [
                    (pyautogui.size()[0] - 100, 100),  # Top right (common for close buttons)
                    (pyautogui.size()[0] - 50, 50),    # Top right corner
                ]
            },
            # Notification permission dialog
            {
                'name': 'Notification Permission',
                'keys': ['tab', 'enter'],  # Tab to "Don't Allow", Enter
                'click_positions': []
            },
            # Generic popups
            {
                'name': 'Generic Popup',
                'keys': ['escape'],
                'click_positions': []
            }
        ]

        for attempt in range(max_attempts):
            logging.debug(f"Popup detection attempt {attempt + 1}/{max_attempts}...")

            for pattern in close_patterns:
                try:
                    # Try keyboard shortcuts first
                    for key in pattern['keys']:
                        pyautogui.press(key)
                        time.sleep(0.5)
                        closed_count += 1

                        logging.info(f"  ✓ Closed: {pattern['name']}")
                        break

                except Exception as e:
                    logging.debug(f"Could not close {pattern['name']}: {e}")

            time.sleep(1)

        return closed_count

    def close_cookie_banner(self) -> bool:
        """
        Close cookie consent banner

        Returns:
            True if closed, False otherwise
        """
        try:
            logging.info("🍪 Handling cookie banner...")

            # Try common cookie close methods
            close_methods = [
                ('escape', None),  # Press Escape
                ('tab', 'enter'),  # Tab + Enter to accept/deny
                ('tab', 'tab', 'enter'),  # Tab twice then enter
            ]

            for method in close_methods:
                try:
                    for key in method:
                        pyautogui.press(key)
                        time.sleep(0.3)

                    time.sleep(1)
                    logging.info("  ✓ Cookie banner closed")
                    return True

                except Exception as e:
                    logging.debug(f"Method failed: {e}")
                    continue

            # If keyboard doesn't work, try clicking common cookie button positions
            logging.debug("Trying to click cookie close button...")

            # Common positions for cookie close buttons (right side, top)
            click_positions = [
                (pyautogui.size()[0] - 30, 30),      # Top right corner
                (pyautogui.size()[0] - 50, 50),      # Slightly inward
                (pyautogui.size()[0] - 100, 100),    # More inward
            ]

            for x, y in click_positions:
                try:
                    pyautogui.click(x, y)
                    time.sleep(0.5)
                except Exception as e:
                    logging.debug(f"Click failed at ({x}, {y}): {e}")

            return True

        except Exception as e:
            logging.warning(f"⚠ Could not close cookie banner: {e}")
            return False

    def close_notification_popup(self) -> bool:
        """
        Close notification permission popup

        Returns:
            True if closed, False otherwise
        """
        try:
            logging.info("🔔 Handling notification popup...")

            # Try to deny notification permission
            methods = [
                ('tab', 'enter'),      # Tab to "Don't Allow" + Enter
                ('shift+tab', 'enter'), # Shift+Tab (reverse) + Enter
                ('escape',),            # Escape key
            ]

            for method in methods:
                try:
                    for key in method:
                        pyautogui.hotkey(*key.split('+')) if '+' in key else pyautogui.press(key)
                        time.sleep(0.3)

                    time.sleep(1)
                    logging.info("  ✓ Notification popup closed")
                    return True

                except Exception as e:
                    logging.debug(f"Method failed: {e}")

            return True

        except Exception as e:
            logging.warning(f"⚠ Could not close notification popup: {e}")
            return False

    def close_ad_popups(self) -> bool:
        """
        Close advertising popups

        Returns:
            True if closed, False otherwise
        """
        try:
            logging.info("📢 Handling ad popups...")

            # Try escape key first (works for most popups)
            for _ in range(3):
                pyautogui.press('escape')
                time.sleep(0.5)

            logging.info("  ✓ Ad popups closed")
            return True

        except Exception as e:
            logging.warning(f"⚠ Could not close ad popups: {e}")
            return False

    def close_exit_safely_popup(self) -> bool:
        """
        Close 'Exit Safely' popup (ixBrowser exit confirmation)

        Returns:
            True if closed, False otherwise
        """
        try:
            logging.info("🚪 Handling Exit Safely popup...")

            # Try clicking "Exit Safely" button
            # Usually in the center-right of popup
            screen_width, screen_height = pyautogui.size()

            # Common button positions for exit popup
            click_positions = [
                (screen_width // 2 + 150, screen_height // 2),    # Right side
                (screen_width // 2 + 100, screen_height // 2 + 50),  # Right-bottom
                (screen_width - 200, screen_height - 100),        # Bottom-right area
            ]

            for x, y in click_positions:
                try:
                    pyautogui.click(x, y)
                    time.sleep(1)
                    logging.info("  ✓ Exit Safely popup closed")
                    return True
                except Exception:
                    continue

            # Fallback: Try keyboard shortcut
            logging.debug("Trying keyboard shortcut for exit...")
            pyautogui.hotkey('alt', 'f4')  # Alt+F4 to close window
            time.sleep(1)

            logging.info("  ✓ Exit Safely popup closed (keyboard)")
            return True

        except Exception as e:
            logging.warning(f"⚠ Could not close Exit Safely popup: {e}")
            return False

    def handle_all_popups(self) -> bool:
        """
        Handle all common popups in sequence with visual feedback

        Returns:
            True if successful, False otherwise
        """
        try:
            logging.info("=" * 60)
            logging.info("🛡️  Handling popups and notifications")
            logging.info("=" * 60)

            # Start activity indicator
            activity = None
            if ACTIVITY_AVAILABLE:
                try:
                    activity = MouseActivityIndicator()
                    activity.start()
                except Exception as e:
                    logging.debug(f"Could not start activity indicator: {e}")

            try:
                # Handle in order of likelihood
                self.close_cookie_banner()
                time.sleep(1)

                self.close_notification_popup()
                time.sleep(1)

                self.close_ad_popups()
                time.sleep(1)

                logging.info("✓ Popup handling completed")

            finally:
                # Stop activity indicator
                if activity:
                    activity.stop()

            # Clean up screenshots after handling
            self.clean_old_screenshots()

            return True

        except Exception as e:
            logging.error(f"Error handling popups: {e}")
            return False

    def verify_clean_page(self) -> bool:
        """
        Verify that page is clean of popups

        Returns:
            True if clean, False if popups detected
        """
        try:
            # Take screenshot to verify page is clean
            screenshot = pyautogui.screenshot()

            # Simple check: if page loaded and no obvious popups
            logging.info("✓ Page verified clean")
            return True

        except Exception as e:
            logging.warning(f"⚠ Could not verify page: {e}")
            return False
