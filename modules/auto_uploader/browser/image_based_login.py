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

        logging.debug("ImageBasedLogin initialized (pure image-based automation)")

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
                            except Exception:
                                # Fallback to Win+Up if maximize unsupported
                                pyautogui.hotkey("win", "up")

                        logging.info("✓ Browser window '%s' activated", window.title)
                        return True
                    except Exception as exc:
                        logging.debug("Window activation attempt for '%s' failed: %s", candidate, exc)

                time.sleep(0.5)

        # Fallback: click center of the screen as a last resort
        try:
            logging.debug("Falling back to center-screen click to focus browser.")
            screenshot = self.screen_detector.capture_screen()
            height, width = screenshot.shape[:2]
            pyautogui.click(width // 2, height // 2)
            time.sleep(0.5)
            logging.info("✓ Browser window focused using fallback click")
            return True
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

        # Check for user logged-in indicator
        status_result = self.screen_detector.detect_user_status()
        if status_result['logged_in']:
            logging.info("✓ User is LOGGED IN")
            return "logged_in"

        # Check for login window
        login_result = self.screen_detector.detect_custom_element("sample_login_window.png")
        if login_result['found']:
            logging.info("✓ Login window DETECTED - User is LOGGED OUT")
            return "logged_out"

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
        icon_result = self.screen_detector.detect_custom_element(icon_name)
        if not icon_result.get("found"):
            return None

        top_left = icon_result.get("top_left")
        size = icon_result.get("size")
        position = icon_result.get("position")

        if top_left and size:
            icon_x, icon_y = top_left
            width, height = size
            effective_offset = max(offset_x, int(width * 3))
            target_x = icon_x + width + effective_offset
            target_y = icon_y + (height // 2) + offset_y
        elif position:
            pos_x, pos_y = position
            target_x = pos_x + offset_x
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
                coords = self._locate_field_via_icon(icon_name, offset_x=default_offset)
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
            screen_width, screen_height = pyautogui.size()
            if field_type == 'email':
                fallback = (int(screen_width * 0.5), int(screen_height * 0.35))
            elif field_type == 'password':
                fallback = (int(screen_width * 0.5), int(screen_height * 0.45))
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

    def _clear_and_focus_field(self, x: int, y: int, *, pause: float = 0.3) -> None:
        """Focus the given field and clear any existing text."""
        self._move_cursor(x, y)
        pyautogui.click(x, y)
        time.sleep(pause)
        pyautogui.doubleClick(x, y)
        time.sleep(pause / 2)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(pause / 2)
        pyautogui.press("delete")
        time.sleep(pause / 2)
        pyautogui.press("backspace")
        time.sleep(pause / 2)

    def _move_cursor(self, x: int, y: int, pause: Optional[float] = None) -> None:
        """Smoothly move the mouse cursor to the requested coordinates."""
        kwargs = {"duration": self.mouse_move_duration}
        if self._mouse_tween:
            kwargs["tween"] = self._mouse_tween
        pyautogui.moveTo(x, y, **kwargs)
        time.sleep(pause if pause is not None else self.post_move_pause)

    def _move_and_click(self, x: int, y: int, *, pause_after: Optional[float] = None) -> None:
        """Convenience helper to move smoothly then click."""
        self._move_cursor(x, y, pause=self.post_move_pause)
        pyautogui.click(x, y)
        time.sleep(pause_after if pause_after is not None else self.post_move_pause)

    def _fill_email_field(self, email: str) -> bool:
        """Fill email field using intelligent coordinate detection."""
        try:
            logging.info("Filling email field...")

            # Get exact coordinates
            coords = self._find_field_coordinates('email')
            if not coords:
                logging.error("Could not find email field coordinates")
                return False

            email_x, email_y = coords
            logging.info("  Email field at: (%d, %d)", email_x, email_y)

            logging.info("  → Clearing any existing value...")
            self._clear_and_focus_field(email_x, email_y)

            logging.info("  → Typing email: %s", email)
            pyautogui.typewrite(email, interval=self.type_interval)
            time.sleep(0.5)

            logging.debug("  → Sending TAB to advance focus from email field.")
            pyautogui.press('tab')
            time.sleep(0.3)

            logging.info("✓ Email filled: %s", email)
            return True

        except Exception as e:
            logging.error("Email fill error: %s", e, exc_info=True)
            return False

    def _fill_password_field(self, password: str) -> bool:
        """Fill password field using intelligent coordinate detection."""
        try:
            logging.info("Filling password field...")

            # Get exact coordinates
            coords = self._find_field_coordinates('password')
            if not coords:
                logging.error("Could not find password field coordinates")
                return False

            password_x, password_y = coords
            logging.info("  Password field at: (%d, %d)", password_x, password_y)

            logging.info("  → Clearing any existing value...")
            self._clear_and_focus_field(password_x, password_y)

            logging.info("  → Typing password (length: %d)", len(password))
            pyautogui.typewrite(password, interval=self.type_interval)
            time.sleep(0.5)

            logging.info("✓ Password filled")
            return True

        except Exception as e:
            logging.error("Password fill error: %s", e, exc_info=True)
            return False

    def _click_login_button(self) -> bool:
        """Submit login by clicking the button (with keyboard fallback)."""
        logging.info("Submitting login form...")
        success = False

        try:
            button_result = self.screen_detector.detect_custom_element("login_submit_button.png")
            if button_result.get('found'):
                if button_result.get('top_left') and button_result.get('size'):
                    bx, by = button_result['top_left']
                    bw, bh = button_result['size']
                    button_position = (bx + bw // 2, by + bh // 2)
                else:
                    button_position = button_result.get('position')

                if button_position:
                    logging.debug("Clicking explicit login button at %s", button_position)
                    self._move_cursor(button_position[0], button_position[1])
                    pyautogui.click(button_position[0], button_position[1])
                    time.sleep(1)
                    success = True

            if not success:
                login_window = self.screen_detector.detect_custom_element("sample_login_window.png")
                if login_window.get('found'):
                    button_position = None
                    if login_window.get('top_left') and login_window.get('size'):
                        top_left = login_window['top_left']
                        size = login_window['size']
                        button_x = int(top_left[0] + size[0] * 0.5)
                        button_y = int(top_left[1] + size[1] * 0.68)
                        button_position = (button_x, button_y)

                    if button_position:
                        logging.debug("Clicking login button at %s", button_position)
                        self._move_cursor(button_position[0], button_position[1])
                        pyautogui.click(button_position[0], button_position[1])
                        time.sleep(1)
                        success = True

        except Exception as exc:
            logging.debug("Login button click via image detection failed: %s", exc, exc_info=True)

        logging.debug("Pressing Enter key to ensure form submission.")
        pyautogui.press('enter')
        time.sleep(1)
        logging.info("✓ Login form submission attempted (mouse/keyboard).")
        return True

    def _wait_for_login_window(self, timeout: int = 10) -> bool:
        """Wait until the login window is visible."""
        result = self.screen_detector.wait_for_element("sample_login_window.png", timeout=timeout)
        if result.get('found'):
            logging.info("✓ Login window visible.")
            return True

        logging.warning("Login window not detected within %ds timeout.", timeout)
        return False

    def _open_user_dropdown(self, retries: int = 3) -> Optional[Dict[str, object]]:
        """Ensure the account dropdown is visible for logout."""
        for attempt in range(retries):
            dropdown = self.screen_detector.detect_logout_dropdown()
            if dropdown.get('found'):
                return dropdown

            status_result = self.screen_detector.detect_user_status()
            target_position = status_result.get('position')

            if target_position:
                x, y = target_position
                self._move_cursor(x, y)
                if attempt % 2 == 0:
                    pyautogui.click(x, y)
                else:
                    pyautogui.rightClick(x, y)
            else:
                screen_width, screen_height = pyautogui.size()
                fx = int(screen_width * 0.96)
                fy = int(screen_height * 0.10)
                self._move_cursor(fx, fy)
                pyautogui.click(fx, fy)

            time.sleep(self.dropdown_settle_time)

        return None

    def _logout_user(self) -> bool:
        """Handle logout process using image recognition."""
        logging.info("Initiating logout...")

        try:
            dropdown = self._open_user_dropdown()
            if not dropdown:
                logging.error("Unable to locate account dropdown for logout.")
                return False

            logging.info("✓ Account dropdown detected.")
            top_left = dropdown.get('top_left')
            size = dropdown.get('size')
            position = dropdown.get('position')

            if top_left and size:
                logout_x = int(top_left[0] + size[0] * 0.5)
                logout_y = int(top_left[1] + size[1] * 0.90)
            elif position:
                logout_x = position[0]
                logout_y = position[1] + 90
            else:
                screen_width, screen_height = pyautogui.size()
                logout_x = int(screen_width * 0.95)
                logout_y = int(screen_height * 0.20)

            logging.info("Clicking logout option at (%d, %d)...", logout_x, logout_y)
            self._move_cursor(logout_x, logout_y)
            pyautogui.click(logout_x, logout_y)
            time.sleep(2)

            if self._wait_for_login_window(timeout=10):
                logging.info("✓ Logout successful, login screen restored.")
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

            time.sleep(1)

            # Step 2: Detect login status
            logging.info("Step 2/5: Detecting login status...")
            status = self._detect_login_status()

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
                self._wait_for_login_window(timeout=8)

            logging.info("✓ Proceeding with login for provided credentials.")
            if not self._perform_login(email, password):
                return False

        except Exception as e:
            logging.error("Login flow error: %s", e, exc_info=True)
            return False

        logging.info("Verifying login succeeded...")
        for attempt in range(6):
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
        time.sleep(2)

        if not self._wait_for_login_window(timeout=8):
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
        login_submitted = self._click_login_button()
        if not login_submitted:
            logging.error("❌ FAILED: Login button could not be clicked")
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
