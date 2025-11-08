"""
Fullscreen Manager
==================
Manages browser fullscreen operations using F11 key and window detection.

This module provides:
- F11 fullscreen toggle
- Fullscreen state verification
- Window size detection
- Cross-platform fullscreen support
"""

import logging
import time
import platform
from typing import Optional, Tuple, Dict, Any

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logging.warning("pyautogui not available. Fullscreen management may not work.")

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False
    logging.warning("pygetwindow not available. Window detection limited.")

from .mouse_controller import MouseController


class FullscreenManager:
    """Manages browser fullscreen operations."""

    def __init__(self):
        """Initialize fullscreen manager."""
        self.platform = platform.system()
        self.mouse = MouseController()
        self.screen_size = self._get_screen_size()

        logging.debug("FullscreenManager initialized for platform: %s", self.platform)
        logging.debug("Screen size: %dx%d", *self.screen_size)

    def enable_fullscreen(self, verify: bool = True, retry_count: int = 3) -> bool:
        """
        Enable fullscreen mode using F11 key.

        Args:
            verify: Verify fullscreen was enabled
            retry_count: Number of retry attempts if verification fails

        Returns:
            True if fullscreen enabled successfully

        Example:
            >>> fs_mgr = FullscreenManager()
            >>> fs_mgr.enable_fullscreen()
        """
        logging.info("Enabling fullscreen mode...")

        if not PYAUTOGUI_AVAILABLE:
            logging.error("pyautogui not available, cannot enable fullscreen")
            return False

        try:
            for attempt in range(retry_count):
                # Press F11 key
                logging.debug("Pressing F11 key (attempt %d/%d)", attempt + 1, retry_count)
                self.mouse.press_key('f11')

                # Wait for transition
                time.sleep(1.5)

                # Verify if requested
                if verify:
                    if self.is_fullscreen():
                        logging.info("Fullscreen mode ENABLED successfully")
                        return True
                    else:
                        logging.warning("Fullscreen verification failed on attempt %d", attempt + 1)
                        if attempt < retry_count - 1:
                            time.sleep(1)
                            continue
                else:
                    logging.info("Fullscreen mode enabled (verification skipped)")
                    return True

            logging.error("Failed to enable fullscreen after %d attempts", retry_count)
            return False

        except Exception as e:
            logging.error("Error enabling fullscreen: %s", e, exc_info=True)
            return False

    def disable_fullscreen(self, verify: bool = True) -> bool:
        """
        Disable fullscreen mode using F11 key.

        Args:
            verify: Verify fullscreen was disabled

        Returns:
            True if fullscreen disabled successfully
        """
        logging.info("Disabling fullscreen mode...")

        if not PYAUTOGUI_AVAILABLE:
            logging.error("pyautogui not available, cannot disable fullscreen")
            return False

        try:
            # Press F11 key
            self.mouse.press_key('f11')

            # Wait for transition
            time.sleep(1.5)

            # Verify if requested
            if verify:
                if not self.is_fullscreen():
                    logging.info("Fullscreen mode DISABLED successfully")
                    return True
                else:
                    logging.warning("Fullscreen still appears to be active")
                    return False
            else:
                logging.info("Fullscreen mode disabled (verification skipped)")
                return True

        except Exception as e:
            logging.error("Error disabling fullscreen: %s", e, exc_info=True)
            return False

    def toggle_fullscreen(self) -> bool:
        """
        Toggle fullscreen mode (F11 key press).

        Returns:
            True if toggle successful
        """
        logging.info("Toggling fullscreen mode...")

        try:
            self.mouse.press_key('f11')
            time.sleep(1.5)

            logging.info("Fullscreen toggled")
            return True

        except Exception as e:
            logging.error("Error toggling fullscreen: %s", e, exc_info=True)
            return False

    def is_fullscreen(self, window_title: Optional[str] = None) -> bool:
        """
        Check if browser is in fullscreen mode.

        Args:
            window_title: Optional window title to check (searches for title if None)

        Returns:
            True if in fullscreen mode

        Example:
            >>> fs_mgr = FullscreenManager()
            >>> if fs_mgr.is_fullscreen():
            >>>     print("Browser is fullscreen")
        """
        logging.debug("Checking fullscreen status...")

        try:
            # Method 1: Compare window size to screen size
            screen_width, screen_height = self.screen_size

            if PYGETWINDOW_AVAILABLE:
                # Try to find browser window
                windows = self._find_browser_windows(window_title)

                if windows:
                    window = windows[0]  # Use first match

                    # Get window dimensions
                    win_width = window.width
                    win_height = window.height

                    # Check if window size matches screen size (with small tolerance)
                    tolerance = 50  # pixels
                    width_match = abs(win_width - screen_width) <= tolerance
                    height_match = abs(win_height - screen_height) <= tolerance

                    is_fullscreen = width_match and height_match

                    logging.debug("Window size: %dx%d, Screen size: %dx%d, Fullscreen: %s",
                                win_width, win_height, screen_width, screen_height, is_fullscreen)

                    return is_fullscreen
                else:
                    logging.warning("Browser window not found for fullscreen check")
                    return False
            else:
                # Fallback: Assume fullscreen if pygetwindow not available
                logging.debug("pygetwindow not available, cannot verify fullscreen")
                return True

        except Exception as e:
            logging.error("Error checking fullscreen status: %s", e, exc_info=True)
            return False

    def get_window_info(self, window_title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get information about browser window.

        Args:
            window_title: Optional window title to search for

        Returns:
            Dictionary with window information or None
        """
        logging.debug("Getting window information...")

        if not PYGETWINDOW_AVAILABLE:
            logging.warning("pygetwindow not available")
            return None

        try:
            windows = self._find_browser_windows(window_title)

            if not windows:
                logging.warning("No browser windows found")
                return None

            window = windows[0]

            info = {
                'title': window.title,
                'x': window.left,
                'y': window.top,
                'width': window.width,
                'height': window.height,
                'is_active': window.isActive,
                'is_maximized': window.isMaximized,
                'is_minimized': window.isMinimized,
                'is_fullscreen': self.is_fullscreen(window.title)
            }

            logging.debug("Window info: %s", info)
            return info

        except Exception as e:
            logging.error("Error getting window info: %s", e, exc_info=True)
            return None

    def focus_browser_window(self, window_title: Optional[str] = None) -> bool:
        """
        Bring browser window to focus.

        Args:
            window_title: Optional window title to focus

        Returns:
            True if window focused successfully
        """
        logging.info("Focusing browser window...")

        if not PYGETWINDOW_AVAILABLE:
            logging.warning("pygetwindow not available")
            return False

        try:
            windows = self._find_browser_windows(window_title)

            if not windows:
                logging.warning("No browser windows found to focus")
                return False

            window = windows[0]

            # Activate/focus window
            window.activate()

            # Small delay for window to come to foreground
            time.sleep(0.5)

            logging.info("Browser window focused: %s", window.title)
            return True

        except Exception as e:
            logging.error("Error focusing browser window: %s", e, exc_info=True)
            return False

    def maximize_window(self, window_title: Optional[str] = None) -> bool:
        """
        Maximize browser window (not fullscreen).

        Args:
            window_title: Optional window title to maximize

        Returns:
            True if window maximized successfully
        """
        logging.info("Maximizing browser window...")

        if not PYGETWINDOW_AVAILABLE:
            logging.warning("pygetwindow not available")
            return False

        try:
            windows = self._find_browser_windows(window_title)

            if not windows:
                logging.warning("No browser windows found to maximize")
                return False

            window = windows[0]

            # Maximize window
            window.maximize()

            time.sleep(0.5)

            logging.info("Browser window maximized")
            return True

        except Exception as e:
            logging.error("Error maximizing window: %s", e, exc_info=True)
            return False

    def minimize_window(self, window_title: Optional[str] = None) -> bool:
        """
        Minimize browser window.

        Args:
            window_title: Optional window title to minimize

        Returns:
            True if window minimized successfully
        """
        logging.info("Minimizing browser window...")

        if not PYGETWINDOW_AVAILABLE:
            logging.warning("pygetwindow not available")
            return False

        try:
            windows = self._find_browser_windows(window_title)

            if not windows:
                logging.warning("No browser windows found to minimize")
                return False

            window = windows[0]

            # Minimize window
            window.minimize()

            time.sleep(0.5)

            logging.info("Browser window minimized")
            return True

        except Exception as e:
            logging.error("Error minimizing window: %s", e, exc_info=True)
            return False

    def _find_browser_windows(self, window_title: Optional[str] = None):
        """
        Find browser windows by title.

        Args:
            window_title: Optional title to search for (searches common browser titles if None)

        Returns:
            List of matching windows
        """
        if not PYGETWINDOW_AVAILABLE:
            return []

        try:
            all_windows = gw.getAllWindows()

            if window_title:
                # Search for specific title
                matching = [w for w in all_windows if window_title.lower() in w.title.lower()]
            else:
                # Search for common browser window titles
                browser_keywords = [
                    'facebook',
                    'chrome',
                    'orbita',  # GoLogin
                    'incogniton',
                    'mozilla',
                    'firefox',
                    'edge',
                    'browser'
                ]

                matching = [w for w in all_windows
                           if any(keyword in w.title.lower() for keyword in browser_keywords)]

            logging.debug("Found %d matching browser window(s)", len(matching))
            return matching

        except Exception as e:
            logging.error("Error finding browser windows: %s", e)
            return []

    def _get_screen_size(self) -> Tuple[int, int]:
        """
        Get screen resolution.

        Returns:
            Tuple of (width, height)
        """
        try:
            if PYAUTOGUI_AVAILABLE:
                size = pyautogui.size()
                return (size.width, size.height)
            else:
                # Default fallback resolution
                return (1920, 1080)

        except Exception as e:
            logging.error("Error getting screen size: %s", e)
            return (1920, 1080)

    def wait_for_fullscreen(self, timeout: int = 10) -> bool:
        """
        Wait for browser to enter fullscreen mode.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if fullscreen mode detected within timeout
        """
        logging.info("Waiting for fullscreen mode (timeout: %ds)", timeout)

        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.is_fullscreen():
                elapsed = time.time() - start_time
                logging.info("Fullscreen mode detected after %.1fs", elapsed)
                return True

            time.sleep(0.5)

        logging.warning("Fullscreen mode not detected within timeout")
        return False
