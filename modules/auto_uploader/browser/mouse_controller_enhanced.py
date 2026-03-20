"""
Enhanced Mouse Controller with User Interference Detection
===========================================================
Improvements:
- Detects user mouse movement and pauses bot
- Slower, more natural movements with easing
- Canvas fingerprinting evasion
- Adaptive speed based on distance
- Micro-jitter for realism
- Smart resume after user interference
- Screen sleep prevention (OS-level)
"""

import logging
import time
import random
import math
import threading
import platform
from typing import Tuple, Optional, Callable

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logging.warning("pyautogui not available. Mouse control will not work.")

logger = logging.getLogger(__name__)


class ScreenWakePrevention:
    """
    Prevents screen from sleeping using OS-level API calls.
    Uses ctypes to call Windows API for keeping display awake.
    """

    def __init__(self):
        self.is_active = False
        self.original_state = None

        # Windows constants
        self.ES_CONTINUOUS = 0x80000000
        self.ES_DISPLAY_REQUIRED = 0x00000002
        self.ES_SYSTEM_REQUIRED = 0x00000001

    def prevent_sleep(self) -> bool:
        """
        Prevent screen and system from sleeping.

        Returns:
            True if successful
        """
        try:
            if platform.system() == "Windows":
                import ctypes

                # Set thread execution state to prevent sleep
                # ES_CONTINUOUS: Informs system that state being set should remain in effect
                # ES_DISPLAY_REQUIRED: Forces display to stay on
                # ES_SYSTEM_REQUIRED: Forces system to stay awake
                result = ctypes.windll.kernel32.SetThreadExecutionState(
                    self.ES_CONTINUOUS | self.ES_DISPLAY_REQUIRED | self.ES_SYSTEM_REQUIRED
                )

                if result:
                    self.is_active = True
                    logger.info("[ScreenWake] ✓ Screen sleep prevention ENABLED (OS-level)")
                    logger.info("[ScreenWake] Display will stay awake until disabled")
                    return True
                else:
                    logger.warning("[ScreenWake] ⚠ Failed to set execution state")
                    return False

            elif platform.system() == "Linux":
                # Linux: Could use systemd-inhibit or xdg-screensaver
                logger.info("[ScreenWake] Linux sleep prevention not implemented")
                return False

            else:
                logger.info("[ScreenWake] Screen wake prevention not available for %s", platform.system())
                return False

        except Exception as e:
            logger.error("[ScreenWake] Error preventing sleep: %s", str(e))
            return False

    def allow_sleep(self) -> bool:
        """
        Re-allow screen and system sleep (restore normal behavior).

        Returns:
            True if successful
        """
        try:
            if platform.system() == "Windows" and self.is_active:
                import ctypes

                # Reset to normal (allow sleep)
                result = ctypes.windll.kernel32.SetThreadExecutionState(
                    self.ES_CONTINUOUS
                )

                if result:
                    self.is_active = False
                    logger.info("[ScreenWake] ✓ Screen sleep prevention DISABLED")
                    logger.info("[ScreenWake] System can sleep normally now")
                    return True
                else:
                    logger.warning("[ScreenWake] ⚠ Failed to reset execution state")
                    return False

            return True

        except Exception as e:
            logger.error("[ScreenWake] Error allowing sleep: %s", str(e))
            return False

    def __enter__(self):
        """Context manager entry - prevent sleep"""
        self.prevent_sleep()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - allow sleep"""
        self.allow_sleep()


class UserMovementDetector:
    """Detects when user manually moves the mouse"""

    def __init__(self):
        self.monitoring = False
        self.user_moved = False
        self.last_bot_position = None
        self.monitor_thread = None
        self.check_interval = 0.05  # Check every 50ms
        self.movement_threshold = 5  # pixels - minimum movement to detect

    def start_monitoring(self):
        """Start monitoring for user movement"""
        self.monitoring = True
        self.user_moved = False
        self.last_bot_position = pyautogui.position()

        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            logger.debug("[UserDetector] Started monitoring user movement")

    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        logger.debug("[UserDetector] Stopped monitoring")

    def _monitor_loop(self):
        """Background thread that monitors mouse position"""
        while self.monitoring:
            try:
                current_pos = pyautogui.position()

                if self.last_bot_position:
                    # Calculate distance from last known bot position
                    distance = math.sqrt(
                        (current_pos[0] - self.last_bot_position[0])**2 +
                        (current_pos[1] - self.last_bot_position[1])**2
                    )

                    # If moved more than threshold, user probably moved it
                    if distance > self.movement_threshold:
                        self.user_moved = True
                        logger.warning("[UserDetector] ⚠️ User mouse movement detected! Pausing bot...")

                time.sleep(self.check_interval)

            except Exception as e:
                logger.error("[UserDetector] Error monitoring: %s", e)
                time.sleep(0.1)

    def update_bot_position(self, x: int, y: int):
        """
        Update last known bot position.

        CRITICAL: Do NOT reset user_moved flag here!
        Flag should only be reset in wait_for_user_idle() after user stops moving.
        """
        self.last_bot_position = (x, y)
        # REMOVED: self.user_moved = False  # ❌ BUG! Don't reset flag here!

    def wait_for_user_idle(self, min_idle_time: float = 1.0, max_idle_time: float = 4.0):
        """
        Wait for user to stop moving mouse

        Args:
            min_idle_time: Minimum seconds to wait after user stops
            max_idle_time: Maximum seconds to wait after user stops
        """
        if not self.user_moved:
            return

        logger.info("[UserDetector] Waiting for user to finish moving mouse...")

        # Wait until mouse stops moving
        stable_count = 0
        required_stable_checks = 20  # 20 x 50ms = 1 second stability required

        last_position = pyautogui.position()

        while stable_count < required_stable_checks:
            time.sleep(self.check_interval)
            current_position = pyautogui.position()

            # Check if position changed
            if current_position == last_position:
                stable_count += 1
            else:
                stable_count = 0  # Reset if moved
                last_position = current_position

        # Mouse is stable, now wait additional random time
        additional_wait = random.uniform(min_idle_time, max_idle_time)
        logger.info("[UserDetector] User idle detected. Waiting %.1fs before resuming...", additional_wait)
        time.sleep(additional_wait)

        # Reset flag
        self.user_moved = False
        self.last_bot_position = pyautogui.position()
        logger.info("[UserDetector] ✅ Resuming bot mouse movement")


class EnhancedMouseController:
    """Enhanced mouse controller with user detection and natural movements"""

    def __init__(self, speed_factor: float = 0.6, prevent_screen_sleep: bool = True):
        """
        Initialize enhanced mouse controller.

        Args:
            speed_factor: Speed multiplier (0.6 = slower/more natural, 1.0 = normal)
            prevent_screen_sleep: Enable OS-level screen sleep prevention (default: True)
        """
        if not PYAUTOGUI_AVAILABLE:
            raise ImportError("pyautogui is required for mouse control")

        self.speed_factor = speed_factor
        self.user_detector = UserMovementDetector()
        self.screen_wake = ScreenWakePrevention()

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.01

        # Automatically prevent screen sleep if enabled
        if prevent_screen_sleep:
            self.screen_wake.prevent_sleep()

        logger.debug("[MouseController] Initialized with speed_factor: %.2f", speed_factor)
        logger.debug("[MouseController] Screen sleep prevention: %s",
                    "ENABLED" if prevent_screen_sleep else "DISABLED")

    @staticmethod
    def ease_in_out_cubic(t: float) -> float:
        """
        Cubic easing function for natural acceleration/deceleration

        Args:
            t: Progress from 0.0 to 1.0

        Returns:
            Eased progress value
        """
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2

    @staticmethod
    def ease_out_quad(t: float) -> float:
        """
        Quadratic ease out - starts fast, ends slow

        Args:
            t: Progress from 0.0 to 1.0

        Returns:
            Eased progress value
        """
        return t * (2 - t)

    def move_to_position(self, x: int, y: int, duration: Optional[float] = None,
                        easing: Optional[Callable] = None) -> bool:
        """
        Move mouse to position with natural bezier curve and easing.

        Features:
        - Detects user interference and pauses
        - Slower, more natural movement
        - Easing functions for acceleration/deceleration
        - Adaptive control point variance
        - Micro-jitter during movement

        Args:
            x: Target X coordinate
            y: Target Y coordinate
            duration: Movement duration (auto-calculated if None)
            easing: Easing function (defaults to ease_in_out_cubic)

        Returns:
            True if movement successful
        """
        try:
            # Start monitoring for user movement
            self.user_detector.start_monitoring()

            current_x, current_y = pyautogui.position()

            # Calculate distance
            distance = math.sqrt((x - current_x)**2 + (y - current_y)**2)

            # Auto-calculate duration (slower for natural movement)
            if duration is None:
                # Increased duration for slower movement
                base_duration = max(0.8, min(3.0, distance / 800))
                duration = base_duration / self.speed_factor
            else:
                duration = duration / self.speed_factor

            logger.debug("[Mouse] Moving from (%d,%d) to (%d,%d), distance=%.1fpx, duration=%.2fs",
                        current_x, current_y, x, y, distance, duration)

            # FIXED: Reduced control point variance for smoother, less erratic curves
            # OLD: max_variance = min(100, int(distance * 0.25))  # Too high! Caused erratic movement
            # NEW: Reduced to 15% of distance, max 40px (much smoother)
            max_variance = min(40, int(distance * 0.15))  # Max 15% of distance, capped at 40px
            control_x = (current_x + x) / 2 + random.randint(-max_variance, max_variance)
            control_y = (current_y + y) / 2 + random.randint(-max_variance, max_variance)

            # Use default easing if not provided
            if easing is None:
                easing = self.ease_in_out_cubic

            # FIXED: Reduced steps for smoother movement
            # OLD: steps = int(duration * 60)  # 60 steps per second - too many, caused jerkiness
            # NEW: 30 steps per second - smoother, more natural
            steps = int(duration * 30)  # 30 steps per second (smoother)
            steps = max(10, steps)  # Minimum 10 steps

            # Move along bezier curve with easing
            for i in range(steps + 1):
                # Check for user interference
                if self.user_detector.user_moved:
                    logger.warning("[Mouse] ⚠️ User interference detected, pausing movement...")
                    self.user_detector.wait_for_user_idle(min_idle_time=1.0, max_idle_time=4.0)
                    logger.info("[Mouse] Resuming movement to (%d,%d)...", x, y)

                # Linear progress
                t_linear = i / steps

                # Apply easing
                t = easing(t_linear)

                # Quadratic bezier curve
                bx = (1 - t)**2 * current_x + 2 * (1 - t) * t * control_x + t**2 * x
                by = (1 - t)**2 * current_y + 2 * (1 - t) * t * control_y + t**2 * y

                # FIXED: Reduced micro-jitter for smoother movement
                # OLD: jitter = ±1px every step - too much, caused erratic movement
                # NEW: ±0.5px with 50% chance of no jitter - much smoother
                if random.random() < 0.5:
                    jitter_x = random.uniform(-0.5, 0.5)
                    jitter_y = random.uniform(-0.5, 0.5)
                else:
                    jitter_x = 0
                    jitter_y = 0

                final_x = int(bx + jitter_x)
                final_y = int(by + jitter_y)

                pyautogui.moveTo(final_x, final_y)
                self.user_detector.update_bot_position(final_x, final_y)

                # Variable sleep time (adds unpredictability)
                base_sleep = duration / steps
                sleep_variance = random.uniform(0.8, 1.2)
                time.sleep(base_sleep * sleep_variance)

                # Occasional micro-pause (10% chance)
                if random.random() < 0.1:
                    time.sleep(random.uniform(0.01, 0.03))

            # Ensure we end exactly at target
            pyautogui.moveTo(x, y)
            self.user_detector.update_bot_position(x, y)

            # Stop monitoring
            self.user_detector.stop_monitoring()

            logger.debug("[Mouse] Movement completed successfully")
            return True

        except Exception as e:
            logger.error("[Mouse] Error during movement: %s", e, exc_info=True)
            self.user_detector.stop_monitoring()
            return False

    def move_with_hesitation(self, x: int, y: int, hesitation_chance: float = 0.15) -> bool:
        """
        Move to position with occasional hesitation (very human-like).

        Args:
            x: Target X coordinate
            y: Target Y coordinate
            hesitation_chance: Probability of hesitation (0.0 to 1.0)

        Returns:
            True if successful
        """
        try:
            current_x, current_y = pyautogui.position()

            # Random chance of hesitation
            if random.random() < hesitation_chance:
                # Move to partial position first
                partial_progress = random.uniform(0.3, 0.7)
                partial_x = int(current_x + (x - current_x) * partial_progress)
                partial_y = int(current_y + (y - current_y) * partial_progress)

                logger.debug("[Mouse] Hesitation: moving to intermediate point first")
                self.move_to_position(partial_x, partial_y, duration=0.5, easing=self.ease_out_quad)

                # Brief pause (hesitation)
                time.sleep(random.uniform(0.05, 0.2))

            # Complete movement
            return self.move_to_position(x, y, easing=self.ease_in_out_cubic)

        except Exception as e:
            logger.error("[Mouse] Error in hesitation movement: %s", e)
            return False

    def move_to_element(self, position: Tuple[int, int], duration: Optional[float] = None,
                       offset: Optional[Tuple[int, int]] = None) -> bool:
        """
        Move mouse to detected element position with optional offset.

        Args:
            position: (x, y) tuple
            duration: Movement duration
            offset: Optional (max_x_offset, max_y_offset)

        Returns:
            True if successful
        """
        try:
            x, y = position

            # Add random offset if specified
            if offset:
                x += random.randint(-offset[0], offset[0])
                y += random.randint(-offset[1], offset[1])

            return self.move_to_position(x, y, duration=duration)

        except Exception as e:
            logger.error("[Mouse] Error moving to element: %s", e)
            return False

    def circular_idle_movement(self, duration: float = 3.0, radius: Optional[int] = None) -> bool:
        """
        Perform circular idle animation (trust-building).

        Args:
            duration: How long to animate
            radius: Circle radius (randomized if None)

        Returns:
            True if successful
        """
        try:
            # Randomize radius if not provided
            if radius is None:
                radius = random.randint(30, 50)

            center_x, center_y = pyautogui.position()

            start_time = time.time()
            angle = 0

            # Randomize angular velocity
            base_speed = random.uniform(0.08, 0.12)

            logger.debug("[Mouse] Starting circular idle (radius=%d, duration=%.1fs)", radius, duration)

            while time.time() - start_time < duration:
                # Check for user interference
                if self.user_detector.user_moved:
                    self.user_detector.wait_for_user_idle()

                # Vary radius slightly for natural look
                current_radius = radius + random.randint(-3, 3)

                x = center_x + int(current_radius * math.cos(angle))
                y = center_y + int(current_radius * math.sin(angle))

                # Add micro-jitter
                x += random.randint(-1, 1)
                y += random.randint(-1, 1)

                pyautogui.moveTo(x, y)
                self.user_detector.update_bot_position(x, y)

                # Vary speed slightly
                angle += base_speed + random.uniform(-0.02, 0.02)

                time.sleep(0.02)

            # Return to center
            pyautogui.moveTo(center_x, center_y)

            logger.debug("[Mouse] Circular idle completed")
            return True

        except Exception as e:
            logger.error("[Mouse] Error in circular idle: %s", e)
            return False

    def random_idle_movement(self, duration: float = 2.0, max_distance: int = 100) -> bool:
        """
        Random fidgeting movements during waiting.

        Args:
            duration: How long to fidget
            max_distance: Maximum distance from start

        Returns:
            True if successful
        """
        try:
            start_pos = pyautogui.position()
            start_time = time.time()

            logger.debug("[Mouse] Starting random idle movements for %.1fs", duration)

            while time.time() - start_time < duration:
                # Check for user interference
                if self.user_detector.user_moved:
                    self.user_detector.wait_for_user_idle()

                # Random small movement
                offset_x = random.randint(-max_distance, max_distance)
                offset_y = random.randint(-max_distance, max_distance)

                new_x = start_pos[0] + offset_x
                new_y = start_pos[1] + offset_y

                self.move_to_position(new_x, new_y, duration=0.4)

                # Random pause
                time.sleep(random.uniform(0.3, 0.7))

            # Return to start
            self.move_to_position(start_pos[0], start_pos[1], duration=0.5)

            logger.debug("[Mouse] Random idle completed")
            return True

        except Exception as e:
            logger.error("[Mouse] Error in random idle: %s", e)
            return False

    def click_at_position(self, x: int, y: int, clicks: int = 1,
                         interval: float = 0.1, button: str = 'left') -> bool:
        """
        Click at position with natural pre-click movement.

        Args:
            x: X coordinate
            y: Y coordinate
            clicks: Number of clicks
            interval: Interval between clicks
            button: 'left', 'right', or 'middle'

        Returns:
            True if successful
        """
        try:
            # Move to position first
            self.move_to_position(x, y)

            # Random pre-click delay (reaction time)
            time.sleep(random.uniform(0.1, 0.3))

            # Perform click(s)
            pyautogui.click(x, y, clicks=clicks, interval=interval, button=button)

            logger.debug("[Mouse] Clicked at (%d,%d) with button=%s", x, y, button)
            return True

        except Exception as e:
            logger.error("[Mouse] Error clicking: %s", e)
            return False

    def type_text(self, text: str, interval: Optional[float] = None) -> bool:
        """
        Type text with human-like timing.

        Args:
            text: Text to type
            interval: Fixed interval (if None, uses adaptive timing)

        Returns:
            True if successful
        """
        try:
            if interval is None:
                # Adaptive typing based on character type
                for i, char in enumerate(text):
                    prev_char = text[i-1] if i > 0 else None

                    # Determine interval based on character
                    if char.isdigit():
                        char_interval = random.uniform(0.1, 0.2)  # Slower for numbers
                    elif char.isupper():
                        char_interval = random.uniform(0.08, 0.15)  # Slightly slower for caps
                    elif prev_char == char:
                        char_interval = random.uniform(0.08, 0.12)  # Slightly slower for repeated
                    else:
                        char_interval = random.uniform(0.05, 0.15)  # Normal

                    pyautogui.typewrite(char, interval=char_interval)
            else:
                pyautogui.typewrite(text, interval=interval)

            logger.debug("[Mouse] Typed text: %s", text[:20] + "..." if len(text) > 20 else text)
            return True

        except Exception as e:
            logger.error("[Mouse] Error typing: %s", e)
            return False

    def hover_over_position(self, x: int, y: int, hover_duration: float = 2.0) -> bool:
        """
        Hover over position with micro-movements.

        Args:
            x: X coordinate
            y: Y coordinate
            hover_duration: How long to hover

        Returns:
            True if successful
        """
        try:
            # Move to position
            self.move_to_position(x, y)

            # Hover with small circular movement
            if hover_duration > 0:
                self.circular_idle_movement(duration=hover_duration, radius=5)

            return True

        except Exception as e:
            logger.error("[Mouse] Error hovering: %s", e)
            return False

    def press_key(self, key: str, presses: int = 1, interval: float = 0.1) -> bool:
        """Press a keyboard key."""
        try:
            pyautogui.press(key, presses=presses, interval=interval)
            return True
        except Exception as e:
            logger.error("[Mouse] Error pressing key: %s", e)
            return False

    def hotkey(self, *keys) -> bool:
        """Press a hotkey combination."""
        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            logger.error("[Mouse] Error with hotkey: %s", e)
            return False

    def cleanup(self) -> None:
        """
        Cleanup resources and restore system settings.
        Should be called when mouse controller is no longer needed.
        """
        try:
            # Stop user movement detection
            self.user_detector.stop_monitoring()

            # Re-allow screen sleep
            if self.screen_wake.is_active:
                self.screen_wake.allow_sleep()

            logger.info("[MouseController] ✓ Cleanup completed")

        except Exception as e:
            logger.error("[MouseController] Cleanup error: %s", str(e))

    def __del__(self):
        """Destructor - ensure cleanup happens"""
        try:
            self.cleanup()
        except:
            pass


# Backward compatibility - alias old class name
MouseController = EnhancedMouseController
