"""
Mouse Activity Indicator - Visual feedback during waits
Shows circular mouse movement to indicate activity
"""

import logging
import time
import threading
import math
from typing import Optional

try:
    import pyautogui
    MOUSE_AVAILABLE = True
except ImportError:
    MOUSE_AVAILABLE = False
    logging.warning("pyautogui not available for mouse movement feedback")


class MouseActivityIndicator:
    """Shows circular mouse movement as visual feedback"""

    def __init__(self):
        """Initialize mouse activity indicator"""
        self.active = False
        self.thread = None
        self.center_x = 960  # Default center (1920x1080 center)
        self.center_y = 540

    def start(self, center_x: Optional[int] = None, center_y: Optional[int] = None):
        """
        Start circular mouse movement

        Args:
            center_x: X coordinate for center (default: screen center)
            center_y: Y coordinate for center (default: screen center)
        """
        if not MOUSE_AVAILABLE:
            return

        if self.active:
            logging.debug("Mouse activity already running")
            return

        # Get screen size and set center
        screen_width, screen_height = pyautogui.size()

        if center_x is None:
            center_x = screen_width // 2
        if center_y is None:
            center_y = screen_height // 2

        self.center_x = center_x
        self.center_y = center_y

        self.active = True
        self.thread = threading.Thread(target=self._circle_movement, daemon=True)
        self.thread.start()

        logging.debug(f"Started mouse activity indicator (center: {center_x}, {center_y})")

    def stop(self):
        """Stop circular mouse movement"""
        if not self.active:
            return

        self.active = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

        logging.debug("Stopped mouse activity indicator")

    def _circle_movement(self):
        """Execute circular mouse movement pattern"""
        try:
            # Movement parameters
            max_radius = 100  # pixels
            num_points = 40   # points around circle
            speed = 0.05      # seconds per point

            iteration = 0

            while self.active:
                iteration += 1

                # First half: expand from center to max radius
                for i in range(num_points):
                    if not self.active:
                        break

                    # Calculate radius (expanding)
                    radius = (max_radius * i) // num_points

                    # Calculate angle
                    angle = (2 * math.pi * i) / num_points

                    # Calculate position
                    x = self.center_x + int(radius * math.cos(angle))
                    y = self.center_y + int(radius * math.sin(angle))

                    # Constrain to screen
                    screen_width, screen_height = pyautogui.size()
                    x = max(0, min(x, screen_width - 1))
                    y = max(0, min(y, screen_height - 1))

                    try:
                        pyautogui.moveTo(x, y, duration=speed)
                    except Exception as e:
                        logging.debug(f"Mouse movement failed: {e}")
                        break

                # Second half: contract back to center
                for i in range(num_points):
                    if not self.active:
                        break

                    # Calculate radius (contracting)
                    radius = (max_radius * (num_points - i)) // num_points

                    # Calculate angle (reverse direction)
                    angle = (2 * math.pi * (num_points - i)) / num_points

                    # Calculate position
                    x = self.center_x + int(radius * math.cos(angle))
                    y = self.center_y + int(radius * math.sin(angle))

                    # Constrain to screen
                    screen_width, screen_height = pyautogui.size()
                    x = max(0, min(x, screen_width - 1))
                    y = max(0, min(y, screen_height - 1))

                    try:
                        pyautogui.moveTo(x, y, duration=speed)
                    except Exception as e:
                        logging.debug(f"Mouse movement failed: {e}")
                        break

                # Return to center
                try:
                    pyautogui.moveTo(self.center_x, self.center_y, duration=0.1)
                except Exception as e:
                    logging.debug(f"Mouse movement failed: {e}")

        except Exception as e:
            logging.warning(f"Mouse activity error: {e}")
            self.active = False

    def show_progress(self, message: str, duration: int = 5):
        """
        Show progress with activity indicator

        Args:
            message: Status message to log
            duration: How long to show activity (seconds)
        """
        logging.info(message)
        self.start()

        try:
            time.sleep(duration)
        finally:
            self.stop()

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
        return False


class ActivityContext:
    """Context manager for mouse activity during operations"""

    def __init__(self, message: str = "", show_activity: bool = True):
        """
        Initialize activity context

        Args:
            message: Status message to display
            show_activity: Whether to show mouse activity
        """
        self.message = message
        self.show_activity = show_activity
        self.indicator = MouseActivityIndicator() if show_activity else None
        self.start_time = None

    def __enter__(self):
        """Start activity indicator"""
        self.start_time = time.time()
        if self.message:
            logging.info(self.message)

        if self.indicator:
            self.indicator.start()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop activity indicator"""
        if self.indicator:
            self.indicator.stop()

        if self.start_time:
            elapsed = int(time.time() - self.start_time)
            if self.message:
                logging.debug(f"Completed in {elapsed}s")

        return False

    def update(self, message: str = ""):
        """Update status message"""
        if message:
            logging.info(message)
