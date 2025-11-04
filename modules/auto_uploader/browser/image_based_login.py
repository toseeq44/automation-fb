"""
Image-Based Login Automation
=============================

Uses image recognition and pyautogui to detect login status and automate Facebook login.

Workflow:
1. Activate browser window
2. Detect user's login status using reference images
3. If logged in: Proceed to creator automation
4. If logged out: Auto-fill login form
5. Handle logout and re-login requests

Reference Images:
- sample_login_window.png: Login form detection
- check_user_status.png: User logged-in status
- user_status_dropdown.png: Logout dropdown menu
- userprofile_icon_for_logout.png: User profile icon for logout
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import pyautogui
    import cv2
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False

try:
    import pygetwindow as gw
    WINDOW_AUTOMATION_AVAILABLE = True
except ImportError:
    WINDOW_AUTOMATION_AVAILABLE = False
    gw = None  # type: ignore
    logging.warning("pygetwindow not available. Install: pip install pygetwindow for window management.")

from .screen_detector import ScreenDetector


WINDOW_TITLE_FALLBACKS: Dict[str, Sequence[str]] = {
    "gologin": ("GoLogin", "Orbita", "gologin", "Orbita Browser"),
    "ix": ("Incogniton", "IX Browser", "ixBrowser", "Incogniton Browser"),
    "chrome": ("Google Chrome", "Chrome", "Facebook"),
    "free_automation": ("Google Chrome", "Chrome", "Microsoft Edge", "Mozilla Firefox", "Facebook"),
    "edge": ("Microsoft Edge", "Edge"),
    "firefox": ("Mozilla Firefox", "Firefox"),
    "brave": ("Brave", "Brave Browser"),
}


class ImageBasedLogin:
    """Automated login using pure image recognition and keyboard/mouse automation."""

    def __init__(self, debug_port: int = 9223, chromedriver_path: Optional[str] = None):
        """
        Initialize login automator.

        Args:
            debug_port: Browser debug port (not used in pure image-based approach)
            chromedriver_path: Path to chromedriver (not used in pure image-based approach)
        """
        if not AUTOMATION_AVAILABLE:
            raise ImportError("pyautogui and opencv-python are required for login automation")

        self.screen_detector = ScreenDetector()
        self.type_interval = 0.05  # Natural typing speed (milliseconds between keystrokes)
        self.mouse_move_duration = 0.6
        self.post_move_pause = 0.25
        self.dropdown_settle_time = 1.3
        self._mouse_tween = getattr(pyautogui, "easeOutQuad", None)
        
        # Get screen dimensions for resolution independence
        self.screen_width, self.screen_height = pyautogui.size()
        logging.debug(f"Screen resolution detected: {self.screen_width}x{self.screen_height}")

        logging.debug("ImageBasedLogin initialized (pure image-based automation)")

    def _get_scaled_coordinates(self, x: int, y: int, reference_res: Tuple[int, int] = (1920, 1080)) -> Tuple[int, int]:
        """Convert coordinates from reference resolution to current screen resolution."""
        ref_width, ref_height = reference_res
        scaled_x = int((x / ref_width) * self.screen_width)
        scaled_y = int((y / ref_height) * self.screen_height)
        return scaled_x, scaled_y

    def _get_relative_position(self, x_percent: float, y_percent: float) -> Tuple[int, int]:
        """Get coordinates based on percentage of screen dimensions."""
        return int(self.screen_width * x_percent), int(self.screen_height * y_percent)

    def _safe_click(self, x: int, y: int, clicks: int = 1, button: str = 'left') -> bool:
        """Safely click at coordinates with bounds checking."""
        try:
            if 0 <= x <= self.screen_width and 0 <= y <= self.screen_height:
                self._move_cursor(x, y)
                pyautogui.click(x, y, clicks=clicks, button=button)
                return True
            else:
                logging.warning(f"Coordinates out of bounds: ({x}, {y})")
                return False
        except Exception as e:
            logging.error(f"Click failed at ({x}, {y}): {e}")
            return False

    def _activate_browser_window(
        self,
        window_title: Optional[str],
        browser_type: Optional[str],
        maximize: bool = True,
    ) -> bool:
        """Activate and focus the target browser window."""
        logging.debug(
            "Activating browser window (title=%r, browser_type=%r)",
            window_title,
            browser_type,
        )

        # Compile candidate window title patterns
        candidates: List[str] = []
        if window_title:
            candidates.append(window_title)

        normalized_type = (browser_type or "").strip().lower()
        candidates.extend(WINDOW_TITLE_FALLBACKS.get(normalized_type, ()))

        # Ensure we always have at least one fallback (avoid empty search)
        if not candidates:
            candidates.extend(["Facebook", "Chrome", "Browser"])

        # Attempt to activate window via pygetwindow if available
        if WINDOW_AUTOMATION_AVAILABLE:
            logging.debug("Window automation available; attempting pygetwindow activation.")
            for attempt in range(3):
                for candidate in candidates:
                    try:
                        windows = gw.getWindowsWithTitle(candidate)  # type: ignore[attr-defined]
                    except Exception as exc:
                        logging.debug("pygetwindow lookup failed for %s: %s", candidate, exc)
                        continue

                    if not windows:
                        continue

                    window = windows[0]
                    try:
                        if window.isMinimized:
                            logging.debug("Window '%s' is minimized; restoring.", window.title)
                            window.restore()
                            time.sleep(0.5)

                        logging.debug("Bringing window '%s' to foreground.", window.title)
                        window.activate()
                        time.sleep(0.5)

                        if maximize:
                            try:
                                window.maximize()
                                time.sleep(1)  # Give time for maximize to complete
                            except Exception:
                                # Fallback to Win+Up if maximize unsupported
                                logging.debug("Window maximize failed, using keyboard fallback")
                                pyautogui.hotkey("win", "up")
                                time.sleep(1)

                        logging.info("✓ Browser window '%s' activated", window.title)
                        return True
                    except Exception as exc:
                        logging.debug("Window activation attempt for '%s' failed: %s", candidate, exc)

                time.sleep(0.5)

        # Fallback: try multiple click positions to activate browser
        try:
            logging.debug("Falling back to screen clicks to focus browser.")
            click_positions = [
                self._get_relative_position(0.5, 0.5),  # Center
                self._get_relative_position(0.1, 0.1),  # Top-left corner
                self._get_relative_position(0.9, 0.1),  # Top-right corner
            ]
            
            for pos_x, pos_y in click_positions:
                if self._safe_click(pos_x, pos_y):
                    time.sleep(0.5)
                    # Try to maximize with keyboard
                    pyautogui.hotkey("win", "up")
                    time.sleep(0.5)
                    logging.info("✓ Browser window focused using fallback click")
                    return True

            logging.error("All fallback click attempts failed")
            return False
        except Exception as exc:
            logging.error("Failed to activate browser window: %s", exc, exc_info=True)
            return False

    def _detect_login_status(self) -> str:
        """
        Detect current login status using image recognition.

        Returns:
            "logged_in", "logged_out", or "unknown"
        """
        logging.info("Detecting login status...")

        # Check for user logged-in indicator with multiple attempts
        for attempt in range(3):
            status_result = self.screen_detector.detect_user_status()
            if status_result['logged_in']:
                logging.info("✓ User is LOGGED IN")
                return "logged_in"
            time.sleep(0.5)

        # Check for login window with multiple attempts
        for attempt in range(3):
            login_result = self.screen_detector.detect_custom_element("sample_login_window.png")
            if login_result['found']:
                logging.info("✓ Login window DETECTED - User is LOGGED OUT")
                return "logged_out"
            time.sleep(0.5)

        logging.warning("⚠ Could not determine login status")
        return "unknown"

    def _locate_field_via_icon(
        self,
        icon_name: str,
        *,
        offset_x: int = 110,
        offset_y: int = 0,
    ) -> Optional[Tuple[int, int]]:
        """Locate a form field by detecting a reference icon and offsetting."""
        # Scale offset based on screen resolution
        scaled_offset_x = int(offset_x * (self.screen_width / 1920))
        
        icon_result = self.screen_detector.detect_custom_element(icon_name)
        if not icon_result.get("found"):
            return None

        top_left = icon_result.get("top_left")
        size = icon_result.get("size")
        position = icon_result.get("position")

        if top_left and size:
            icon_x, icon_y = top_left
            width, height = size
            effective_offset = max(scaled_offset_x, int(width * 3))
            target_x = icon_x + width + effective_offset
            target_y = icon_y + (height // 2) + offset_y
        elif position:
            pos_x, pos_y = position
            target_x = pos_x + scaled_offset_x
            target_y = pos_y + offset_y
        else:
            return None

        logging.debug(
            "Icon '%s' located; computed field point at (%d, %d)",
            icon_name,
            target_x,
            target_y,
        )
        return (target_x, target_y)

    def _find_field_coordinates(self, field_type: str) -> Optional[tuple]:
        """
        Find field coordinates using intelligent image-based detection.

        Args:
            field_type: 'email' or 'password'

        Returns:
            (x, y) coordinates if found, None otherwise
        """
        try:
            icon_map = {
                "email": ("login_profile_icon.png", 60),
                "password": ("login_password_icon.png", 60),
            }
            icon_entry = icon_map.get(field_type)
            if icon_entry:
                icon_name, default_offset = icon_entry
                # Scale default offset based on screen resolution
                scaled_offset = int(default_offset * (self.screen_width / 1920))
                coords = self._locate_field_via_icon(icon_name, offset_x=scaled_offset)
                if coords:
                    return coords

            login_window = self.screen_detector.detect_custom_element("sample_login_window.png")
            if login_window.get('found') and login_window.get('top_left') and login_window.get('size'):
                top_left = login_window['top_left']
                size = login_window['size']
                window_x, window_y = top_left
                window_w, window_h = size
                logging.debug(
                    "Login window located at %s with size %s",
                    top_left,
                    size,
                )

                offsets = {
                    'email': 0.30,
                    'password': 0.46,
                }

                if field_type in offsets:
                    target_x = int(window_x + window_w * 0.5)
                    target_y = int(window_y + window_h * offsets[field_type])
                    logging.debug(
                        "Computed %s field coordinates at (%d, %d) relative to login window.",
                        field_type,
                        target_x,
                        target_y,
                    )
                    return (target_x, target_y)

            # Fallback to screen-centered estimation if template detection fails
            if field_type == 'email':
                fallback = self._get_relative_position(0.5, 0.35)
            elif field_type == 'password':
                fallback = self._get_relative_position(0.5, 0.45)
            else:
                fallback = None

            if fallback:
                logging.debug(
                    "Using fallback coordinates for %s field: %s",
                    field_type,
                    fallback,
                )
            return fallback
        except Exception as e:
            logging.error("Error finding field coordinates: %s", e, exc_info=True)
            return None

    def _clear_and_focus_field(self, x: int, y: int, *, pause: float = 0.3) -> bool:
        """Focus the given field and clear any existing text."""
        try:
            if not self._safe_click(x, y):
                return False
                
            time.sleep(pause)
            
            # Multiple strategies to clear field
            clear_strategies = [
                lambda: pyautogui.hotkey("ctrl", "a"),  # Select all
                lambda: pyautogui.doubleClick(x, y),   # Double click
                lambda: pyautogui.click(x, y, clicks=3), # Triple click
            ]
            
            for strategy in clear_strategies:
                try:
                    strategy()
                    time.sleep(pause / 2)
                    pyautogui.press("delete")
                    time.sleep(pause / 2)
                    pyautogui.press("backspace")
                    time.sleep(pause / 2)
                    break
                except Exception:
                    continue
            
            return True
        except Exception as e:
            logging.error(f"Error clearing field at ({x}, {y}): {e}")
            return False

    def _move_cursor(self, x: int, y: int, pause: Optional[float] = None) -> bool:
        """Smoothly move the mouse cursor to the requested coordinates."""
        try:
            if not (0 <= x <= self.screen_width and 0 <= y <= self.screen_height):
                logging.warning(f"Coordinates out of bounds: ({x}, {y})")
                return False
                
            kwargs = {"duration": self.mouse_move_duration}
            if self._mouse_tween:
                kwargs["tween"] = self._mouse_tween
            pyautogui.moveTo(x, y, **kwargs)
            time.sleep(pause if pause is not None else self.post_move_pause)
            return True
        except Exception as e:
            logging.error(f"Error moving cursor to ({x}, {y}): {e}")
            return False

    def _move_and_click(self, x: int, y: int, *, pause_after: Optional[float] = None) -> bool:
        """Convenience helper to move smoothly then click."""
        if not self._move_cursor(x, y, pause=self.post_move_pause):
            return False
        return self._safe_click(x, y, pause_after=pause_after)

    def _fill_email_field(self, email: str) -> bool:
        """Fill email field using intelligent coordinate detection."""
        try:
            logging.info("Filling email field...")

            # Get exact coordinates with multiple attempts
            coords = None
            for attempt in range(3):
                coords = self._find_field_coordinates('email')
                if coords:
                    break
                time.sleep(0.5)

            if not coords:
                logging.error("Could not find email field coordinates after 3 attempts")
                return False

            email_x, email_y = coords
            logging.info("  Email field at: (%d, %d)", email_x, email_y)

            logging.info("  → Clearing any existing value...")
            if not self._clear_and_focus_field(email_x, email_y):
                logging.error("  Failed to clear email field")
                return False

            logging.info("  → Typing email: %s", email)
            pyautogui.typewrite(email, interval=self.type_interval)
            time.sleep(0.5)

            logging.info("✓ Email filled: %s", email)
            return True

        except Exception as e:
            logging.error("Email fill error: %s", e, exc_info=True)
            return False

    def _fill_password_field(self, password: str) -> bool:
        """Fill password field using intelligent coordinate detection."""
        try:
            logging.info("Filling password field...")

            # Get exact coordinates with multiple attempts
            coords = None
            for attempt in range(3):
                coords = self._find_field_coordinates('password')
                if coords:
                    break
                time.sleep(0.5)

            if not coords:
                logging.error("Could not find password field coordinates after 3 attempts")
                return False

            password_x, password_y = coords
            logging.info("  Password field at: (%d, %d)", password_x, password_y)

            logging.info("  → Clearing any existing value...")
            if not self._clear_and_focus_field(password_x, password_y):
                logging.error("  Failed to clear password field")
                return False

            logging.info("  → Typing password (length: %d)", len(password))
            pyautogui.typewrite(password, interval=self.type_interval)
            time.sleep(0.5)

            logging.info("✓ Password filled")
            return True

        except Exception as e:
            logging.error("Password fill error: %s", e, exc_info=True)
            return False

    def _find_login_button(self) -> Optional[Tuple[int, int]]:
        """Find login button using multiple strategies."""
        logging.info("Looking for login button...")
        
        # Strategy 1: Direct image detection
        button_result = self.screen_detector.detect_custom_element("login_submit_button.png")
        if button_result.get('found'):
            if button_result.get('top_left') and button_result.get('size'):
                bx, by = button_result['top_left']
                bw, bh = button_result['size']
                button_position = (bx + bw // 2, by + bh // 2)
                logging.info(f"✓ Login button found via image at {button_position}")
                return button_position
            elif button_result.get('position'):
                button_position = button_result.get('position')
                logging.info(f"✓ Login button found via image at {button_position}")
                return button_position

        # Strategy 2: Calculate from login window
        login_window = self.screen_detector.detect_custom_element("sample_login_window.png")
        if login_window.get('found') and login_window.get('top_left') and login_window.get('size'):
            top_left = login_window['top_left']
            size = login_window['size']
            button_x = int(top_left[0] + size[0] * 0.5)
            button_y = int(top_left[1] + size[1] * 0.68)
            button_position = (button_x, button_y)
            logging.info(f"✓ Login button calculated at {button_position}")
            return button_position

        # Strategy 3: Fallback positions
        fallback_positions = [
            self._get_relative_position(0.5, 0.6),   # Center-bottom
            self._get_relative_position(0.5, 0.55),  # Slightly higher
            self._get_relative_position(0.5, 0.65),  # Slightly lower
        ]
        
        logging.info("Using fallback login button positions")
        return fallback_positions[0]

    def _submit_login_form(self) -> bool:
        """Submit login form using multiple strategies."""
        logging.info("Submitting login form...")
        
        # Strategy 1: Press Enter key (simplest and most reliable)
        logging.info("  → Strategy 1: Pressing Enter key")
        pyautogui.press('enter')
        time.sleep(2)
        
        # Check if login was successful
        status = self._detect_login_status()
        if status == "logged_in":
            logging.info("✓ Login successful with Enter key")
            return True
        
        # Strategy 2: Find and click login button
        logging.info("  → Strategy 2: Looking for login button to click")
        button_position = self._find_login_button()
        
        if button_position:
            btn_x, btn_y = button_position
            logging.info(f"  → Clicking login button at ({btn_x}, {btn_y})")
            
            # Try left click first
            if self._safe_click(btn_x, btn_y):
                time.sleep(2)
                
                # Check if login was successful
                status = self._detect_login_status()
                if status == "logged_in":
                    logging.info("✓ Login successful with button click")
                    return True
                
                # If left click didn't work, try right click
                logging.info("  → Left click didn't work, trying right click")
                if self._safe_click(btn_x, btn_y, button='right'):
                    time.sleep(1)
                    # After right click, press Enter to select default option
                    pyautogui.press('enter')
                    time.sleep(2)
                    
                    status = self._detect_login_status()
                    if status == "logged_in":
                        logging.info("✓ Login successful with right click + Enter")
                        return True
        
        # Strategy 3: Try Tab + Enter combination
        logging.info("  → Strategy 3: Trying Tab + Enter combination")
        pyautogui.press('tab')  # Move to next field/button
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(2)
        
        status = self._detect_login_status()
        if status == "logged_in":
            logging.info("✓ Login successful with Tab + Enter")
            return True
        
        # Strategy 4: Final attempt with multiple Enter presses
        logging.info("  → Strategy 4: Final attempt with multiple Enter presses")
        for i in range(3):
            pyautogui.press('enter')
            time.sleep(1)
            
            status = self._detect_login_status()
            if status == "logged_in":
                logging.info(f"✓ Login successful with Enter press #{i+1}")
                return True
        
        logging.warning("All login submission strategies failed")
        return False

    def _wait_for_login_window(self, timeout: int = 10) -> bool:
        """Wait until the login window is visible."""
        result = self.screen_detector.wait_for_element("sample_login_window.png", timeout=timeout)
        if result.get('found'):
            logging.info("✓ Login window visible.")
            return True

        logging.warning("Login window not detected within %ds timeout.", timeout)
        return False

    def _find_user_profile_icon(self) -> Optional[Tuple[int, int]]:
        """Find user profile icon using the specific logout image."""
        logging.info("Looking for user profile icon for logout...")
        
        # Try multiple attempts to find the profile icon
        for attempt in range(5):
            result = self.screen_detector.detect_custom_element("userprofile_icon_for_logout.png")
            
            if result.get('found'):
                if result.get('top_left') and result.get('size'):
                    icon_x, icon_y = result['top_left']
                    width, height = result['size']
                    
                    # Calculate center of the icon
                    center_x = icon_x + width // 2
                    center_y = icon_y + height // 2
                    
                    logging.info(f"✓ User profile icon found at ({center_x}, {center_y})")
                    return center_x, center_y
                elif result.get('position'):
                    pos_x, pos_y = result['position']
                    logging.info(f"✓ User profile icon found at ({pos_x}, {pos_y})")
                    return pos_x, pos_y
            
            logging.debug(f"Profile icon not found in attempt {attempt + 1}, retrying...")
            time.sleep(0.5)
        
        logging.warning("User profile icon not found after multiple attempts")
        return None

    def _open_user_dropdown(self, retries: int = 3) -> Optional[Dict[str, object]]:
        """Ensure the account dropdown is visible for logout using profile icon detection."""
        logging.info("Opening user dropdown using profile icon...")

        for attempt in range(retries):
            # First, find the user profile icon
            profile_icon_coords = self._find_user_profile_icon()
            
            if profile_icon_coords:
                icon_x, icon_y = profile_icon_coords
                
                # Move 2 spaces (approximately 50-60 pixels) to the right and hover
                hover_x = icon_x + 60  # 2 spaces to the right
                hover_y = icon_y
                
                logging.info(f"Hovering at ({hover_x}, {hover_y}) to trigger dropdown")
                
                # Hover at the position to trigger dropdown
                if self._move_cursor(hover_x, hover_y):
                    time.sleep(self.dropdown_settle_time)
                    
                    # Check if dropdown appeared
                    dropdown = self.screen_detector.detect_logout_dropdown()
                    if dropdown.get("found"):
                        logging.info("✓ Dropdown detected after hover")
                        return dropdown
                    
                    # If hover didn't work, try right click
                    logging.info("Hover didn't work, trying right click...")
                    if self._safe_click(hover_x, hover_y, button='right'):
                        time.sleep(self.dropdown_settle_time)
                        
                        dropdown = self.screen_detector.detect_logout_dropdown()
                        if dropdown.get("found"):
                            logging.info("✓ Dropdown detected after right click")
                            return dropdown
            
            # Fallback: Try existing method if new method fails
            logging.info("Trying fallback method for dropdown...")
            dropdown = self.screen_detector.detect_logout_dropdown()
            if dropdown.get("found"):
                return dropdown

            # Alternative fallback: Try common profile icon positions
            fallback_positions = [
                self._get_relative_position(0.95, 0.05),  # Top-right
                self._get_relative_position(0.98, 0.08),  # Top-right slightly lower
                self._get_relative_position(0.92, 0.06),  # Top-right slightly left
            ]
            
            for pos_x, pos_y in fallback_positions:
                self._move_cursor(pos_x, pos_y, pause=self.dropdown_settle_time)
                self._safe_click(pos_x, pos_y, button='right')
                time.sleep(self.dropdown_settle_time)
                
                dropdown = self.screen_detector.detect_logout_dropdown()
                if dropdown.get("found"):
                    return dropdown

        logging.error("Failed to open user dropdown after all attempts")
        return None

    def _logout_user(self) -> bool:
        """Handle logout process using image recognition with profile icon."""
        logging.info("Initiating logout using profile icon method...")

        try:
            dropdown = self._open_user_dropdown()
            if not dropdown:
                logging.error("Unable to locate account dropdown for logout.")
                return False

            logging.info("✓ Account dropdown detected.")
            
            # Find logout button in the dropdown
            logout_button_result = self.screen_detector.detect_custom_element("logout_button.png")
            
            if logout_button_result.get('found'):
                # Click the logout button directly
                if logout_button_result.get('top_left') and logout_button_result.get('size'):
                    bx, by = logout_button_result['top_left']
                    bw, bh = logout_button_result['size']
                    logout_position = (bx + bw // 2, by + bh // 2)
                else:
                    logout_position = logout_button_result.get('position')
                
                if logout_position:
                    logging.info(f"Clicking logout button at {logout_position}")
                    if self._safe_click(logout_position[0], logout_position[1]):
                        time.sleep(3)
                        
                        # Verify logout was successful
                        if self._wait_for_login_window(timeout=8):
                            logging.info("✓ Logout successful, login screen restored.")
                            return True
                
            # Fallback: Calculate logout position from dropdown
            top_left = dropdown.get('top_left')
            size = dropdown.get('size')
            position = dropdown.get('position')

            # Try multiple logout positions
            logout_positions = []
            
            if top_left and size:
                # Bottom of dropdown (logout is usually at the bottom)
                logout_positions.append((int(top_left[0] + size[0] * 0.5), int(top_left[1] + size[1] * 0.90)))
                logout_positions.append((int(top_left[0] + size[0] * 0.5), int(top_left[1] + size[1] * 0.85)))
            elif position:
                logout_positions.append((position[0], position[1] + 90))
                logout_positions.append((position[0], position[1] + 120))
            else:
                # Screen-relative fallback
                logout_positions.extend([
                    self._get_relative_position(0.95, 0.20),
                    self._get_relative_position(0.95, 0.25),
                ])

            # Try all calculated positions
            for logout_x, logout_y in logout_positions:
                logging.info("Attempting logout at (%d, %d)...", logout_x, logout_y)
                if self._safe_click(logout_x, logout_y):
                    time.sleep(3)
                    
                    # Verify logout was successful
                    if self._wait_for_login_window(timeout=8):
                        logging.info("✓ Logout successful, login screen restored.")
                        return True
                    
                    # Check if we're still logged in
                    status = self._detect_login_status()
                    if status == "logged_out":
                        logging.info("✓ Logout successful (status check confirmed).")
                        return True

            logging.warning("Logout action triggered but login screen not detected.")
            return False

        except Exception as e:
            logging.error("Error during logout: %s", e, exc_info=True)
            return False

    def run_login_flow(
        self,
        email: str,
        password: str,
        *,
        window_title: Optional[str] = None,
        browser_type: Optional[str] = None,
        force_relogin: bool = True,
    ) -> bool:
        """
        Complete login flow with intelligent detection.

        Args:
            email: Email for login
            password: Password for login
            force_relogin: Force logout and re-login even if already logged in
            window_title: Preferred window title hint extracted from login data
            browser_type: Browser type identifier (gologin, ix, chrome, etc.)

        Returns:
            True if logged in successfully, False otherwise
        """
        logging.info("")
        logging.info("┌" + "─"*68 + "┐")
        logging.info("│ 🔐 IMAGE-BASED LOGIN FLOW - INTELLIGENT STATE DETECTION          │")
        logging.info("└" + "─"*68 + "┘")
        logging.info("")

        try:
            # Step 1: Activate browser window
            logging.info("Step 1/5: Activating browser window...")
            if not self._activate_browser_window(window_title, browser_type):
                logging.error("Failed to activate target browser window.")
                return False

            time.sleep(2)

            # Step 2: Detect login status with retries
            logging.info("Step 2/5: Detecting login status...")
            status = self._detect_login_status()
            
            # If status unknown, try to determine by checking multiple times
            if status == "unknown":
                logging.info("Ambiguous status, performing additional checks...")
                for check_attempt in range(3):
                    status = self._detect_login_status()
                    if status != "unknown":
                        break
                    time.sleep(1)

            if status == "logged_in":
                logging.info("✓ Existing session detected.")
                if force_relogin:
                    logging.info("  Logging out current session before continuing...")
                    if not self._logout_user():
                        logging.error("  ✗ Failed to log out existing session.")
                        return False
                    status = "logged_out"
                else:
                    logging.info("  Current session will be reused (force_relogin=False).")
                    return True

            if status != "logged_out":
                logging.info("⚠ Login status ambiguous; ensuring login form is visible.")
                if not self._wait_for_login_window(timeout=8):
                    logging.warning("Proceeding despite ambiguous status")

            logging.info("✓ Proceeding with login for provided credentials.")
            if not self._perform_login(email, password):
                return False

        except Exception as e:
            logging.error("Login flow error: %s", e, exc_info=True)
            return False

        logging.info("Verifying login succeeded...")
        for attempt in range(8):
            login_window_state = self.screen_detector.detect_custom_element("sample_login_window.png")
            if not login_window_state.get("found"):
                logging.info("✓ Login window dismissed after %d verification attempt(s).", attempt + 1)
                return True

            followup_status = self._detect_login_status()
            if followup_status == "logged_in":
                logging.info("✓ Login confirmed after %d verification attempt(s).", attempt + 1)
                return True
            time.sleep(1.5)

        logging.warning(
            "Login confirmation timed out; login window still detected. Manual verification recommended."
        )
        return False

    def _perform_login(self, email: str, password: str) -> bool:
        """Execute login process with intelligent field filling."""
        logging.info("Step 3/5: Preparing to fill credentials...")

        # Give browser time to load login page
        logging.info("Waiting for browser to be ready...")
        time.sleep(3)

        if not self._wait_for_login_window(timeout=10):
            logging.warning("Proceeding without visual confirmation of login form.")

        # Fill credentials
        logging.info("Step 4/5: Filling login credentials...")

        # Fill email - MUST succeed
        email_filled = self._fill_email_field(email)
        if not email_filled:
            logging.error("❌ FAILED: Email field could not be filled")
            return False

        time.sleep(0.5)

        # Fill password - MUST succeed
        password_filled = self._fill_password_field(password)
        if not password_filled:
            logging.error("❌ FAILED: Password field could not be filled")
            return False

        time.sleep(0.5)

        # Submit login form - MUST succeed
        logging.info("Step 5/5: Submitting login form...")
        login_submitted = self._submit_login_form()
        if not login_submitted:
            logging.error("❌ FAILED: Login form could not be submitted")
            return False

        # Wait for page to load after login
        logging.info("Waiting for login to process (5 seconds)...")
        time.sleep(5)

        logging.info("")
        logging.info("┌" + "─"*68 + "┐")
        logging.info("│ ✅ LOGIN PROCESS COMPLETED SUCCESSFULLY                          │")
        logging.info("└" + "─"*68 + "┘")
        logging.info("")

        return True