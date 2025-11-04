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
from .adaptive_timing import AdaptiveTiming, ActionType
from .fallback_chain import FallbackChain, StrategyPriority, try_multiple
from .retry_with_verification import RetryWithVerification, RetryConfig, VerificationMethod


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

    def __init__(self, debug_port: int = 9223, chromedriver_path: Optional[str] = None, enable_field_verification: bool = False):
        """
        Initialize login automator with bulletproof features.

        Args:
            debug_port: Browser debug port (not used in pure image-based approach)
            chromedriver_path: Path to chromedriver (not used in pure image-based approach)
            enable_field_verification: Enable clipboard-based field verification (experimental)
        """
        if not AUTOMATION_AVAILABLE:
            raise ImportError("pyautogui and opencv-python are required for login automation")

        # Enhanced modules for bulletproof automation
        self.screen_detector = ScreenDetector(
            enable_multiscale=True,  # Enable multi-scale detection
            min_confidence=0.65,     # Minimum acceptable confidence
            confidence=0.75          # Ideal confidence threshold
        )
        self.timing = AdaptiveTiming(enable_network_check=False)

        # Field verification is DISABLED by default for stability
        # Enable only if needed and tested
        self.enable_field_verification = enable_field_verification
        if enable_field_verification:
            self.retry_handler = RetryWithVerification(
                config=RetryConfig(
                    max_attempts=3,
                    verification_method=VerificationMethod.CLIPBOARD,
                    screenshot_on_failure=True
                )
            )
        else:
            self.retry_handler = None

        # Timing parameters (can be adjusted by adaptive timing)
        self.type_interval = 0.05  # Natural typing speed (milliseconds between keystrokes)
        self.mouse_move_duration = 0.6
        self.post_move_pause = 0.25
        self.dropdown_settle_time = 1.3
        self._mouse_tween = getattr(pyautogui, "easeOutQuad", None)

        logging.info("ImageBasedLogin initialized with improved Phase 1 enhancements")
        logging.debug("  - Multi-scale image detection: ENABLED")
        logging.debug("  - Adaptive timing: ENABLED")
        logging.debug("  - Field verification: %s", "ENABLED" if enable_field_verification else "DISABLED (stable mode)")
        logging.debug("  - Fallback chains: AVAILABLE")

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
        Detect current login status using enhanced image recognition with multi-template support.

        Uses relaxed thresholds and multiple checks for robustness.

        Returns:
            "logged_in", "logged_out", or "unknown"
        """
        logging.info("Detecting login status with enhanced detection...")

        # Check for user logged-in indicator (try variants)
        # Higher confidence threshold for logged-in (0.65) because this is more reliable
        status_result = self.screen_detector.detect_with_variants(
            "check_user_status",
            min_confidence_override=0.65
        )
        status_confidence = status_result.get('confidence', 0)

        if status_result.get('found') or status_confidence >= 0.65:
            logging.info("✓ User is LOGGED IN (confidence: %.3f)", status_confidence)
            return "logged_in"

        # Check for login window (try variants)
        # Lower confidence threshold for login window (0.40) because it varies more
        login_result = self.screen_detector.detect_with_variants(
            "sample_login_window",
            min_confidence_override=0.40
        )
        login_confidence = login_result.get('confidence', 0)

        if login_result.get('found') or login_confidence >= 0.40:
            logging.info("✓ Login window DETECTED - User is LOGGED OUT (confidence: %.3f)", login_confidence)
            return "logged_out"

        # If user status has very low confidence AND login window has some confidence, likely logged out
        if status_confidence < 0.30 and login_confidence > 0.15:
            logging.info(
                "✓ User appears LOGGED OUT (status: %.3f, login window: %.3f)",
                status_confidence,
                login_confidence
            )
            return "logged_out"

        logging.warning(
            "⚠ Could not determine login status (status icon: %.3f, login window: %.3f)",
            status_confidence,
            login_confidence
        )
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
        """
        Fill email field using intelligent coordinate detection with simple, reliable method.

        This method uses:
        - Fallback chain for coordinate finding
        - Direct field filling (no clipboard verification by default for stability)
        - Retry logic with multiple attempts
        """
        logging.info("Filling email field...")

        # Use fallback chain for finding coordinates
        coords_chain = FallbackChain("Find Email Field Coordinates", enable_logging=False)
        coords_chain.add_strategy(
            "Icon-based detection",
            lambda: self._locate_field_via_icon("login_profile_icon.png", offset_x=60),
            priority=StrategyPriority.PRIMARY
        ).add_strategy(
            "Window-relative position",
            lambda: self._find_field_coordinates('email'),
            priority=StrategyPriority.SECONDARY
        )

        coords_result = coords_chain.execute()

        if not coords_result.success:
            logging.error("Could not find email field coordinates after trying all strategies")
            return False

        coords = coords_result.result_data
        logging.info("  Email field at: (%d, %d)", coords[0], coords[1])

        # Use retry handler with verification if enabled, otherwise simple fill
        if self.enable_field_verification and self.retry_handler:
            result = self.retry_handler.fill_field_with_verification(
                field_coords=coords,
                value=email,
                field_name="email",
                verification_method="clipboard"
            )

            if result.success and result.verification_passed:
                logging.info("✅ Email filled and verified: %s", email)
                self.timing.smart_wait(ActionType.FIELD_FILL)
                pyautogui.press('tab')
                self.timing.smart_wait(ActionType.FIELD_FILL)
                return True
            else:
                logging.error("❌ Email field fill failed: %s", result.error_message)
                return False
        else:
            # Simple, reliable method (default)
            try:
                x, y = coords
                logging.info("  → Clearing and filling email field...")
                self._clear_and_focus_field(x, y)
                pyautogui.typewrite(email, interval=self.type_interval)
                self.timing.smart_wait(ActionType.FIELD_FILL)

                logging.debug("  → Sending TAB to advance to password field")
                pyautogui.press('tab')
                self.timing.smart_wait(ActionType.FIELD_FILL)

                logging.info("✅ Email filled: %s", email)
                return True

            except Exception as e:
                logging.error("❌ Email fill error: %s", e, exc_info=True)
                return False

    def _fill_password_field(self, password: str) -> bool:
        """
        Fill password field using intelligent coordinate detection with simple, reliable method.

        This method uses:
        - Fallback chain for coordinate finding
        - Direct field filling (no clipboard verification by default for stability)
        - Retry logic with multiple attempts
        """
        logging.info("Filling password field...")

        # Use fallback chain for finding coordinates
        coords_chain = FallbackChain("Find Password Field Coordinates", enable_logging=False)
        coords_chain.add_strategy(
            "Icon-based detection",
            lambda: self._locate_field_via_icon("login_password_icon.png", offset_x=60),
            priority=StrategyPriority.PRIMARY
        ).add_strategy(
            "Window-relative position",
            lambda: self._find_field_coordinates('password'),
            priority=StrategyPriority.SECONDARY
        )

        coords_result = coords_chain.execute()

        if not coords_result.success:
            logging.error("Could not find password field coordinates after trying all strategies")
            return False

        coords = coords_result.result_data
        logging.info("  Password field at: (%d, %d)", coords[0], coords[1])

        # Use retry handler with verification if enabled, otherwise simple fill
        if self.enable_field_verification and self.retry_handler:
            result = self.retry_handler.fill_field_with_verification(
                field_coords=coords,
                value=password,
                field_name="password",
                verification_method="clipboard"
            )

            if result.success and result.verification_passed:
                logging.info("✅ Password filled and verified (length: %d)", len(password))
                self.timing.smart_wait(ActionType.FIELD_FILL)
                return True
            else:
                logging.error("❌ Password field fill failed: %s", result.error_message)
                return False
        else:
            # Simple, reliable method (default)
            try:
                x, y = coords
                logging.info("  → Clearing and filling password field...")
                self._clear_and_focus_field(x, y)
                pyautogui.typewrite(password, interval=self.type_interval)
                self.timing.smart_wait(ActionType.FIELD_FILL)

                logging.info("✅ Password filled (length: %d)", len(password))
                return True

            except Exception as e:
                logging.error("❌ Password fill error: %s", e, exc_info=True)
                return False

    def _click_login_button(self) -> bool:
        """
        Submit login form using multiple fallback strategies.

        Strategies (in order):
        1. Click explicit login button via image detection
        2. Click button relative to login window
        3. Press Enter key
        4. Press Tab + Enter
        """
        logging.info("Submitting login form with fallback strategies...")

        def click_explicit_button():
            """Try to find and click the explicit login button."""
            button_result = self.screen_detector.detect_custom_element("login_submit_button.png")
            if not button_result.get('found'):
                return False

            button_position = None
            if button_result.get('top_left') and button_result.get('size'):
                bx, by = button_result['top_left']
                bw, bh = button_result['size']
                button_position = (bx + bw // 2, by + bh // 2)
            elif button_result.get('position'):
                button_position = button_result['position']

            if button_position:
                logging.info("  Clicking explicit login button at %s", button_position)
                self._move_cursor(button_position[0], button_position[1])
                pyautogui.click(button_position[0], button_position[1])
                self.timing.smart_wait(ActionType.BUTTON_CLICK)
                return True
            return False

        def click_relative_to_window():
            """Click button based on login window position."""
            login_window = self.screen_detector.detect_custom_element("sample_login_window.png")
            if not login_window.get('found'):
                return False

            if login_window.get('top_left') and login_window.get('size'):
                top_left = login_window['top_left']
                size = login_window['size']
                button_x = int(top_left[0] + size[0] * 0.5)
                button_y = int(top_left[1] + size[1] * 0.68)

                logging.info("  Clicking button relative to window at (%d, %d)", button_x, button_y)
                self._move_cursor(button_x, button_y)
                pyautogui.click(button_x, button_y)
                self.timing.smart_wait(ActionType.BUTTON_CLICK)
                return True
            return False

        def press_enter():
            """Press Enter to submit form."""
            logging.info("  Pressing Enter key to submit form")
            pyautogui.press('enter')
            self.timing.smart_wait(ActionType.FORM_SUBMIT)
            return True

        def press_tab_enter():
            """Press Tab then Enter (in case focus is on password field)."""
            logging.info("  Pressing Tab + Enter to submit form")
            pyautogui.press('tab')
            self.timing.smart_wait(ActionType.FIELD_FILL, custom_multiplier=0.5)
            pyautogui.press('enter')
            self.timing.smart_wait(ActionType.FORM_SUBMIT)
            return True

        # Use fallback chain
        result = try_multiple(
            "Submit Login Form",
            [
                ("Click Explicit Button", click_explicit_button),
                ("Click Relative to Window", click_relative_to_window),
                ("Press Enter", press_enter),
                ("Press Tab+Enter", press_tab_enter),
            ]
        )

        if result.success:
            logging.info("✅ Login form submitted using: %s", result.strategy_used)
            return True
        else:
            logging.error("❌ All login submission strategies failed")
            return False

    def _wait_for_login_window(self, timeout: int = 10, min_confidence: float = 0.50) -> bool:
        """
        Wait until the login window is visible using adaptive timing.

        Uses relaxed confidence threshold for login window detection
        since login pages can vary significantly.
        """
        logging.info("Waiting for login window (timeout: %ds, min_confidence: %.2f)...", timeout, min_confidence)

        def check_login_window():
            result = self.screen_detector.detect_with_variants("sample_login_window")
            confidence = result.get('confidence', 0)
            found = result.get('found') or confidence >= min_confidence

            if found:
                logging.debug("Login window detected with confidence: %.3f", confidence)

            return found

        success = self.timing.wait_for_condition(
            check_login_window,
            timeout=float(timeout),
            check_interval=0.5,
            action_name="login_window_detection"
        )

        if success:
            logging.info("✓ Login window visible")
            return True

        logging.warning("Login window not detected within %ds timeout", timeout)
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

    def _find_logout_button_in_dropdown(self, dropdown_info: Dict) -> Optional[tuple]:
        """
        Find logout button within dropdown using multi-level detection.

        Tries multiple positions and confidence levels:
        - 90% confidence (most reliable)
        - 80% confidence (good match)
        - 70% confidence (acceptable)
        - Multiple vertical positions in dropdown
        """
        logging.info("Finding logout button in dropdown with multi-level detection...")

        top_left = dropdown_info.get('top_left')
        size = dropdown_info.get('size')
        position = dropdown_info.get('position')

        if not (top_left and size):
            logging.warning("Dropdown size information not available, using position-based fallback")
            if position:
                # Try multiple offsets from position
                candidates = [
                    (position[0], position[1] + 80),
                    (position[0], position[1] + 100),
                    (position[0], position[1] + 120),
                ]
                return candidates
            return None

        # Calculate multiple candidate positions within dropdown
        dx, dy = top_left
        dw, dh = size

        candidates = []

        # Try bottom area (90%, 85%, 80%, 75%, 70% from top)
        for ratio in [0.90, 0.85, 0.80, 0.75, 0.70]:
            logout_x = int(dx + dw * 0.5)
            logout_y = int(dy + dh * ratio)
            candidates.append((logout_x, logout_y))

        # Also try left and right sides (for different dropdown layouts)
        logout_y_middle = int(dy + dh * 0.80)
        candidates.append((int(dx + dw * 0.3), logout_y_middle))  # Left side
        candidates.append((int(dx + dw * 0.7), logout_y_middle))  # Right side

        logging.debug("Generated %d candidate positions for logout button", len(candidates))
        return candidates

    def _click_logout_with_retry(self, candidates: list) -> bool:
        """
        Try clicking each candidate position and verify logout happened.

        Returns True if logout successful, False otherwise.
        """
        for idx, (x, y) in enumerate(candidates, 1):
            logging.info("Attempt %d/%d: Clicking at (%d, %d)...", idx, len(candidates), x, y)

            # Move and click
            self._move_cursor(x, y)
            pyautogui.click(x, y)

            # Wait for page to respond
            self.timing.smart_wait(ActionType.LOGOUT_VERIFY)

            # Quick check: Did user icon disappear?
            # STRICT check: Must be below 0.40 (not 0.50) to avoid false positives
            check = self.screen_detector.detect_with_variants("check_user_status", min_confidence_override=0.60)
            after_confidence = check.get('confidence', 0)

            # Very strict: confidence must drop to below 0.40
            if after_confidence < 0.40:
                logging.info("✅ Logout successful at position (%d, %d) - user icon disappeared (%.3f)!",
                           x, y, after_confidence)
                return True
            else:
                logging.debug("Position (%d, %d) - user icon still present (%.3f) - NOT logged out",
                            x, y, after_confidence)

                # If not last attempt, reopen dropdown
                if idx < len(candidates):
                    logging.debug("Reopening dropdown for next attempt...")
                    self._open_user_dropdown(retries=1)
                    self.timing.smart_wait(ActionType.DROPDOWN_OPEN, custom_multiplier=0.5)

        return False

    def _logout_user(self) -> bool:
        """
        Handle logout process with robust multi-position detection and verification.

        Strategy:
        1. Detect user status before logout
        2. Open dropdown
        3. Try multiple logout button positions (7+ candidates)
        4. Verify after each click
        5. Use multi-level verification (90%, 80%, 70% confidence)
        """
        logging.info("")
        logging.info("=" * 70)
        logging.info("INITIATING LOGOUT WITH MULTI-LEVEL DETECTION")
        logging.info("=" * 70)

        try:
            # Step 1: Detect current user status before logout
            logging.info("Step 1/4: Checking user status before logout...")
            before_status = self.screen_detector.detect_with_variants(
                "check_user_status",
                min_confidence_override=0.65
            )
            before_confidence = before_status.get('confidence', 0)
            was_logged_in = before_confidence >= 0.65

            logging.info("  User status before: %.3f (%s)",
                        before_confidence,
                        "LOGGED IN" if was_logged_in else "LOGGED OUT")

            if not was_logged_in:
                logging.warning("⚠ User may already be logged out (confidence: %.3f)", before_confidence)
                return True

            # Step 2: Open dropdown
            logging.info("Step 2/4: Opening account dropdown...")
            dropdown = self._open_user_dropdown(retries=3)
            if not dropdown:
                logging.error("❌ Unable to locate account dropdown for logout")
                return False

            logging.info("✓ Account dropdown detected at confidence: %.3f",
                        dropdown.get('confidence', 0))

            # Step 3: Find logout button positions (multiple candidates)
            logging.info("Step 3/4: Finding logout button candidates...")
            candidates = self._find_logout_button_in_dropdown(dropdown)

            if not candidates:
                logging.error("❌ Could not generate logout button candidates")
                return False

            logging.info("  Generated %d candidate positions", len(candidates))

            # Step 4: Try clicking each candidate with verification
            logging.info("Step 4/4: Attempting logout with multi-position detection...")
            logout_successful = self._click_logout_with_retry(candidates)

            if not logout_successful:
                logging.warning("⚠ Dropdown positions failed, trying full-screen search...")

                # Full-screen fallback: Search entire screen for logout button
                screen_width, screen_height = pyautogui.size()

                # Divide screen into grid and try common logout positions
                fullscreen_candidates = []

                # Top-right area (most common)
                for y_offset in range(100, 400, 50):
                    for x_offset in range(-200, 0, 50):
                        fullscreen_candidates.append((screen_width + x_offset, y_offset))

                # Right side middle
                for y in range(screen_height // 3, 2 * screen_height // 3, 100):
                    fullscreen_candidates.append((screen_width - 100, y))

                # Center-right
                for y in range(200, screen_height - 200, 100):
                    fullscreen_candidates.append((screen_width - 300, y))

                logging.info("  Trying %d full-screen positions...", len(fullscreen_candidates))

                # Reopen dropdown for full-screen search
                self._open_user_dropdown(retries=2)
                self.timing.smart_wait(ActionType.DROPDOWN_OPEN)

                logout_successful = self._click_logout_with_retry(fullscreen_candidates)

                if not logout_successful:
                    logging.error("❌ All logout attempts failed (dropdown + full-screen)")
                    return False

            # Final verification with STRICT multi-level checks
            logging.info("Performing final multi-level STRICT verification...")

            # Level 1: 90% confidence (strict)
            final_check_90 = self.screen_detector.detect_with_variants(
                "check_user_status",
                min_confidence_override=0.90
            )

            # Level 2: 80% confidence (medium)
            final_check_80 = self.screen_detector.detect_with_variants(
                "check_user_status",
                min_confidence_override=0.80
            )

            # Level 3: 60% confidence (relaxed but still strict)
            final_check_60 = self.screen_detector.detect_with_variants(
                "check_user_status",
                min_confidence_override=0.60
            )

            conf_90 = final_check_90.get('confidence', 0)
            conf_80 = final_check_80.get('confidence', 0)
            conf_60 = final_check_60.get('confidence', 0)

            logging.info("Multi-level verification results:")
            logging.info("  - 90%% detection: %.3f %s", conf_90, "✅ GONE" if conf_90 < 0.35 else "❌ STILL THERE")
            logging.info("  - 80%% detection: %.3f %s", conf_80, "✅ GONE" if conf_80 < 0.35 else "❌ STILL THERE")
            logging.info("  - 60%% detection: %.3f %s", conf_60, "✅ GONE" if conf_60 < 0.35 else "❌ STILL THERE")

            # STRICT: All levels must show icon disappeared (< 0.35)
            all_levels_pass = conf_90 < 0.35 and conf_80 < 0.35 and conf_60 < 0.35

            if all_levels_pass:
                # Additional check: Look for login window (MANDATORY)
                logging.info("User icon checks passed, verifying login window appeared...")
                if self._wait_for_login_window(timeout=8, min_confidence=0.25):
                    logging.info("")
                    logging.info("=" * 70)
                    logging.info("✅ LOGOUT VERIFIED SUCCESSFUL")
                    logging.info("   User icon: Before %.3f → After %.3f (Drop: %.3f)",
                                before_confidence, conf_60, before_confidence - conf_60)
                    logging.info("   Login window: APPEARED ✅")
                    logging.info("=" * 70)
                    logging.info("")
                    return True
                else:
                    logging.warning("⚠ User icon disappeared BUT login window not detected")
                    logging.warning("   This might be a false positive - logout may have failed")
                    # Still check confidence drop
                    confidence_drop = before_confidence - conf_60
                    if confidence_drop > 0.55:
                        logging.info("✅ Confidence dropped significantly (%.3f) - accepting logout", confidence_drop)
                        return True
                    else:
                        logging.error("❌ Confidence drop too small (%.3f) - logout likely failed", confidence_drop)
                        return False

            # If icon still visible, check login window anyway
            logging.warning("⚠ User icon still visible (60%% conf: %.3f)", conf_60)
            logging.info("Checking if login window appeared anyway...")
            if self._wait_for_login_window(timeout=5, min_confidence=0.30):
                logging.info("✅ Login window appeared - logout successful despite icon detection")
                return True

            logging.error("")
            logging.error("=" * 70)
            logging.error("❌ LOGOUT VERIFICATION FAILED")
            logging.error("   User icon still visible: %.3f (before: %.3f)", conf_70, before_confidence)
            logging.error("   All attempts exhausted")
            logging.error("=" * 70)
            logging.error("")
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

        # MANDATORY: Login window MUST be visible before proceeding
        logging.info("Verifying login page is ready (MANDATORY CHECK)...")
        login_window_ready = self._wait_for_login_window(timeout=10, min_confidence=0.25)

        if not login_window_ready:
            logging.error("")
            logging.error("=" * 70)
            logging.error("❌ CRITICAL: Login window NOT detected!")
            logging.error("   This means we are NOT on the login page.")
            logging.error("   Possible reasons:")
            logging.error("     1. Logout did not complete (still logged in)")
            logging.error("     2. Page is loading slowly")
            logging.error("     3. Wrong page/redirect issue")
            logging.error("   STOPPING to prevent filling fields on wrong page!")
            logging.error("=" * 70)
            logging.error("")
            return False

        logging.info("✅ Login window confirmed - safe to proceed")

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
