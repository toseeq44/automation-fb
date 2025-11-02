"""
Mouse Controller
================
Provides human-like mouse movement using bezier curves and animations.

This module implements:
- Smooth mouse movements with bezier curves
- Circular idle animations during delays
- Random movement patterns for trust-building
- Click operations with natural timing
"""

import logging
import time
import random
import math
from typing import Tuple, Optional

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logging.warning("pyautogui not available. Mouse control will not work.")


class MouseController:
    """Controls mouse with human-like movements."""

    def __init__(self, speed_factor: float = 1.0):
        """
        Initialize mouse controller.

        Args:
            speed_factor: Speed multiplier (1.0 = normal, 2.0 = twice as fast, 0.5 = half speed)
        """
        if not PYAUTOGUI_AVAILABLE:
            raise ImportError("pyautogui is required for mouse control")

        self.speed_factor = speed_factor
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
        pyautogui.PAUSE = 0.01  # Small pause between pyautogui calls

        logging.debug("MouseController initialized with speed_factor: %.2f", speed_factor)

    def move_to_position(self, x: int, y: int, duration: Optional[float] = None) -> bool:
        """
        Move mouse to position using bezier curve for natural movement.

        Args:
            x: Target X coordinate
            y: Target Y coordinate
            duration: Movement duration in seconds (auto-calculated if None)

        Returns:
            True if movement successful

        Example:
            >>> mouse = MouseController()
            >>> mouse.move_to_position(500, 300, duration=1.5)
        """
        try:
            current_x, current_y = pyautogui.position()

            # Calculate distance
            distance = math.sqrt((x - current_x)**2 + (y - current_y)**2)

            # Auto-calculate duration based on distance if not provided
            if duration is None:
                duration = max(0.5, min(2.0, distance / 1000)) / self.speed_factor

            # Apply speed factor
            duration = duration / self.speed_factor

            logging.debug("Moving mouse from (%d, %d) to (%d, %d) in %.2fs",
                        current_x, current_y, x, y, duration)

            # Calculate bezier curve control point (with randomness)
            control_x = (current_x + x) / 2 + random.randint(-100, 100)
            control_y = (current_y + y) / 2 + random.randint(-100, 100)

            # Number of steps for smooth movement
            steps = int(duration * 100)  # 100 steps per second
            steps = max(10, steps)  # Minimum 10 steps

            # Move along bezier curve
            for i in range(steps + 1):
                t = i / steps

                # Quadratic bezier curve formula
                # B(t) = (1-t)² * P0 + 2(1-t)t * P1 + t² * P2
                bx = (1 - t)**2 * current_x + 2 * (1 - t) * t * control_x + t**2 * x
                by = (1 - t)**2 * current_y + 2 * (1 - t) * t * control_y + t**2 * y

                pyautogui.moveTo(int(bx), int(by))
                time.sleep(duration / steps)

            # Ensure we end exactly at target
            pyautogui.moveTo(x, y)

            logging.debug("Mouse movement completed")
            return True

        except Exception as e:
            logging.error("Error moving mouse: %s", e, exc_info=True)
            return False

    def move_to_element(self, position: Tuple[int, int], duration: Optional[float] = None,
                       offset: Optional[Tuple[int, int]] = None) -> bool:
        """
        Move mouse to detected element position with optional offset.

        Args:
            position: (x, y) tuple of element position
            duration: Movement duration (auto-calculated if None)
            offset: Optional (x_offset, y_offset) to add randomness

        Returns:
            True if movement successful
        """
        x, y = position

        # Add random offset if specified
        if offset:
            x += random.randint(-offset[0], offset[0])
            y += random.randint(-offset[1], offset[1])

        return self.move_to_position(x, y, duration)

    def circular_idle_movement(self, duration: float = 5.0, radius: int = 50) -> None:
        """
        Perform circular mouse movement for trust-building during delays.

        This creates visible mouse activity so user knows the bot is working.

        Args:
            duration: How long to perform circular movement (seconds)
            radius: Radius of circular movement in pixels

        Example:
            >>> mouse = MouseController()
            >>> print("Processing... (watch the mouse)")
            >>> mouse.circular_idle_movement(duration=3.0, radius=30)
        """
        logging.info("Starting circular idle movement for %.1fs", duration)

        try:
            # Get starting position
            center_x, center_y = pyautogui.position()

            start_time = time.time()
            angle = 0

            # Perform circular movement until duration expires
            while time.time() - start_time < duration:
                # Calculate position on circle
                x = center_x + int(radius * math.cos(angle))
                y = center_y + int(radius * math.sin(angle))

                pyautogui.moveTo(x, y)

                # Increment angle for next position
                angle += 0.1  # Adjust for speed of circular movement
                if angle >= 2 * math.pi:
                    angle = 0

                time.sleep(0.02)  # Small delay for smooth animation

            # Return to center
            pyautogui.moveTo(center_x, center_y)

            logging.debug("Circular idle movement completed")

        except Exception as e:
            logging.error("Error during circular idle movement: %s", e, exc_info=True)

    def random_idle_movement(self, duration: float = 3.0, max_distance: int = 100) -> None:
        """
        Perform random small mouse movements during delays.

        Args:
            duration: How long to perform random movements (seconds)
            max_distance: Maximum distance for each random move

        Example:
            >>> mouse = MouseController()
            >>> mouse.random_idle_movement(duration=2.0)
        """
        logging.info("Starting random idle movement for %.1fs", duration)

        try:
            start_time = time.time()

            while time.time() - start_time < duration:
                # Get current position
                current_x, current_y = pyautogui.position()

                # Calculate random offset
                offset_x = random.randint(-max_distance, max_distance)
                offset_y = random.randint(-max_distance, max_distance)

                # Move to new position
                new_x = current_x + offset_x
                new_y = current_y + offset_y

                self.move_to_position(new_x, new_y, duration=0.5)

                time.sleep(random.uniform(0.3, 0.7))

            logging.debug("Random idle movement completed")

        except Exception as e:
            logging.error("Error during random idle movement: %s", e, exc_info=True)

    def click_at_position(self, x: int, y: int, button: str = 'left',
                         clicks: int = 1, interval: float = 0.1) -> bool:
        """
        Click at specific position after moving mouse there.

        Args:
            x: X coordinate to click
            y: Y coordinate to click
            button: Mouse button ('left', 'right', 'middle')
            clicks: Number of clicks
            interval: Interval between clicks

        Returns:
            True if click successful

        Example:
            >>> mouse = MouseController()
            >>> mouse.click_at_position(500, 300)  # Single left click
            >>> mouse.click_at_position(600, 400, button='right')  # Right click
        """
        try:
            # Move to position first
            self.move_to_position(x, y)

            # Small delay before clicking
            time.sleep(random.uniform(0.1, 0.3))

            # Perform click(s)
            pyautogui.click(x, y, clicks=clicks, interval=interval, button=button)

            logging.debug("Clicked at (%d, %d) with %s button (%d times)", x, y, button, clicks)
            return True

        except Exception as e:
            logging.error("Error clicking at position: %s", e, exc_info=True)
            return False

    def click_element(self, position: Tuple[int, int], button: str = 'left',
                     offset: Optional[Tuple[int, int]] = None) -> bool:
        """
        Click on detected element with optional random offset.

        Args:
            position: (x, y) tuple of element position
            button: Mouse button to use
            offset: Optional (x_offset, y_offset) range for randomness

        Returns:
            True if click successful
        """
        x, y = position

        # Add random offset if specified
        if offset:
            x += random.randint(-offset[0], offset[0])
            y += random.randint(-offset[1], offset[1])

        return self.click_at_position(x, y, button=button)

    def double_click_at_position(self, x: int, y: int) -> bool:
        """
        Double-click at specific position.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            True if double-click successful
        """
        return self.click_at_position(x, y, clicks=2, interval=0.1)

    def hover_over_position(self, x: int, y: int, hover_duration: float = 0.5) -> bool:
        """
        Move to position and hover for specified duration.

        Args:
            x: X coordinate
            y: Y coordinate
            hover_duration: How long to hover in seconds

        Returns:
            True if hover successful

        Example:
            >>> mouse = MouseController()
            >>> mouse.hover_over_position(500, 300, hover_duration=2.0)
        """
        try:
            # Move to position
            self.move_to_position(x, y)

            # Hover with small circular movement
            if hover_duration > 0:
                self.circular_idle_movement(duration=hover_duration, radius=5)

            logging.debug("Hovered at (%d, %d) for %.1fs", x, y, hover_duration)
            return True

        except Exception as e:
            logging.error("Error hovering at position: %s", e, exc_info=True)
            return False

    def drag_to_position(self, start_x: int, start_y: int, end_x: int, end_y: int,
                        duration: float = 1.0, button: str = 'left') -> bool:
        """
        Drag mouse from start to end position.

        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            end_x: Ending X coordinate
            end_y: Ending Y coordinate
            duration: Duration of drag operation
            button: Mouse button to hold during drag

        Returns:
            True if drag successful
        """
        try:
            # Move to start position
            self.move_to_position(start_x, start_y, duration=0.5)

            # Small delay before starting drag
            time.sleep(0.2)

            # Perform drag with bezier curve
            pyautogui.mouseDown(button=button)

            # Move to end position while holding button
            self.move_to_position(end_x, end_y, duration=duration)

            # Release button
            pyautogui.mouseUp(button=button)

            logging.debug("Dragged from (%d, %d) to (%d, %d)", start_x, start_y, end_x, end_y)
            return True

        except Exception as e:
            logging.error("Error during drag operation: %s", e, exc_info=True)
            # Ensure mouse button is released
            pyautogui.mouseUp(button=button)
            return False

    def scroll(self, clicks: int, direction: str = 'down') -> bool:
        """
        Scroll mouse wheel.

        Args:
            clicks: Number of scroll clicks
            direction: 'up' or 'down'

        Returns:
            True if scroll successful
        """
        try:
            scroll_amount = clicks if direction == 'down' else -clicks
            pyautogui.scroll(scroll_amount)

            logging.debug("Scrolled %s by %d clicks", direction, clicks)
            return True

        except Exception as e:
            logging.error("Error scrolling: %s", e, exc_info=True)
            return False

    def get_current_position(self) -> Tuple[int, int]:
        """
        Get current mouse position.

        Returns:
            (x, y) tuple of current position
        """
        return pyautogui.position()

    def type_text(self, text: str, interval: Optional[float] = None) -> bool:
        """
        Type text with human-like timing.

        Args:
            text: Text to type
            interval: Interval between keystrokes (random if None)

        Returns:
            True if typing successful
        """
        try:
            if interval is None:
                # Random interval between 0.05 and 0.15 seconds
                for char in text:
                    pyautogui.typewrite(char, interval=random.uniform(0.05, 0.15))
            else:
                pyautogui.typewrite(text, interval=interval)

            logging.debug("Typed text of length %d", len(text))
            return True

        except Exception as e:
            logging.error("Error typing text: %s", e, exc_info=True)
            return False

    def press_key(self, key: str, presses: int = 1, interval: float = 0.1) -> bool:
        """
        Press a keyboard key.

        Args:
            key: Key name (e.g., 'enter', 'f11', 'ctrl', 'a')
            presses: Number of times to press
            interval: Interval between presses

        Returns:
            True if key press successful
        """
        try:
            pyautogui.press(key, presses=presses, interval=interval)

            logging.debug("Pressed key '%s' %d times", key, presses)
            return True

        except Exception as e:
            logging.error("Error pressing key: %s", e, exc_info=True)
            return False

    def hotkey(self, *keys: str) -> bool:
        """
        Press a combination of keys (hotkey).

        Args:
            *keys: Keys to press together (e.g., 'ctrl', 'a' for Ctrl+A)

        Returns:
            True if hotkey successful

        Example:
            >>> mouse = MouseController()
            >>> mouse.hotkey('ctrl', 'a')  # Select all
            >>> mouse.hotkey('ctrl', 'c')  # Copy
        """
        try:
            pyautogui.hotkey(*keys)

            logging.debug("Pressed hotkey: %s", '+'.join(keys))
            return True

        except Exception as e:
            logging.error("Error pressing hotkey: %s", e, exc_info=True)
            return False
