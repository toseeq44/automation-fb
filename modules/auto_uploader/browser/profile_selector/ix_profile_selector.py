"""
Utilities for interacting with the ixBrowser profile list UI.
"""

from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pyautogui
except ImportError:  # pragma: no cover - optional dependency
    pyautogui = None  # type: ignore[assignment]

try:
    import pygetwindow as gw
    WINDOW_AUTOMATION_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    gw = None  # type: ignore[assignment]
    WINDOW_AUTOMATION_AVAILABLE = False

from PIL import Image

from ..screen_detector import ScreenDetector


class IXProfileSelector:
    """Automates profile selection within the ixBrowser profile list."""

    SEARCH_TEMPLATE = "ix_search_input.png"
    SEARCH_ACTIVE_TEMPLATE = "ix_search_input_active.png"
    OPEN_BUTTON_TEMPLATE = "profile_open_button.png"

    def __init__(self, screen_detector: Optional[ScreenDetector] = None) -> None:
        if screen_detector is None:
            screen_detector = ScreenDetector()
        self.screen = screen_detector

        if pyautogui is None:
            logging.warning("pyautogui not available; IXProfileSelector will be disabled.")

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_profile_names(raw_value: str) -> Sequence[str]:
        """
        Parse the `profile names` map stored inside login_data.txt metadata.

        Expected format example:
            profile names:{
                1:Nathaniel Cobb coocking ,
                2:Gloria Valenzuela ,
            }
        """
        if not raw_value:
            return []

        cleaned = raw_value.strip()
        if cleaned.startswith("{") and cleaned.endswith("}"):
            cleaned = cleaned[1:-1]

        cleaned = cleaned.replace("\n", " ").replace("\r", " ")
        pattern = re.compile(r"(\d+)\s*:\s*([^,}]+)")
        matches = pattern.findall(cleaned)
        if not matches:
            # Fall back to splitting by comma if regex fails
            candidates = []
            for chunk in cleaned.split(","):
                chunk = chunk.strip()
                if not chunk or ":" not in chunk:
                    continue
                key, value = chunk.split(":", 1)
                candidates.append((key.strip(), value.strip()))
        else:
            candidates = [(key, value.strip()) for key, value in matches]

        ordered: "OrderedDict[int, str]" = OrderedDict()
        for key, value in candidates:
            try:
                index = int(key)
            except ValueError:
                index = len(ordered) + 1
            name = value.rstrip(",").strip()
            if name:
                ordered[index] = name

        # Sort by the numeric key to preserve intended order
        return [ordered[k] for k in sorted(ordered)]

    def open_profile(self, profile_name: str, *, wait_for_window: bool = True) -> bool:
        """
        Open a profile by name inside the ixBrowser dashboard UI.

        Returns:
            True if the automation sequence completed without errors.
        """
        if not pyautogui:
            logging.error("[IX] pyautogui not available; cannot automate ixBrowser UI.")
            return False

        if not profile_name:
            logging.error("[IX] Empty profile name supplied to IXProfileSelector.open_profile()")
            return False

        logging.info("[IX] Selecting profile '%s' via ixBrowser UI", profile_name)

        if not self._focus_search_input():
            logging.error("[IX] Unable to focus ixBrowser search input.")
            return False

        if not self._verify_search_active():
            logging.debug("[IX] Search input active template not detected; proceeding anyway.")

        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)
        pyautogui.typewrite(profile_name, interval=0.05)
        pyautogui.press("enter")
        logging.info("[IX] Search submitted for profile '%s'", profile_name)
        time.sleep(1.2)

        baseline_windows = self._snapshot_window_titles() if wait_for_window else set()

        if not self._click_open_button():
            logging.error("[IX] Unable to locate 'Open' button for profile '%s'", profile_name)
            return False

        logging.info("[IX] 'Open' command issued for profile '%s'", profile_name)

        if wait_for_window:
            self._handle_new_window(baseline_windows)

        return True

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _focus_search_input(self) -> bool:
        location = self._locate_template(self.SEARCH_TEMPLATE, confidence=0.85)
        if not location:
            logging.debug("[IX] Search input template not found; attempting heuristic fallback.")
            location = self._heuristic_search_input()
            if not location:
                return False

        x, y = self._center(location)
        pyautogui.rightClick(x, y)
        time.sleep(0.3)
        return True

    def _verify_search_active(self) -> bool:
        location = self._locate_template(self.SEARCH_ACTIVE_TEMPLATE, confidence=0.80)
        if not location:
            return False
        logging.debug("[IX] Search input active state confirmed.")
        return True

    def _click_open_button(self) -> bool:
        # Try with lower confidence threshold for profile_open_button
        location = self._locate_template(self.OPEN_BUTTON_TEMPLATE, confidence=0.50)
        if not location:
            logging.debug("[IX] Primary 'Open' button template not found.")
            return False

        x, y = self._center(location)
        logging.info("[IX] Found 'Open' button at position: (%d, %d)", x, y)
        # Use left-click instead of right-click to open the profile
        pyautogui.click(x, y)
        logging.info("[IX] Left-clicked 'Open' button")
        time.sleep(2.0)  # Wait for profile window to start opening
        return True

    def _handle_new_window(self, baseline_titles: Sequence[str]) -> None:
        logging.info("[IX] Waiting for new window to open (up to 15 seconds)...")
        start = time.time()
        new_window = None

        while time.time() - start < 15:
            candidate = self._detect_new_window(baseline_titles)
            if candidate:
                new_window = candidate
                break
            time.sleep(0.5)

        if not new_window:
            logging.warning("[IX] No new window detected after issuing 'Open' command.")
            logging.info("[IX] Attempting to maximize currently active window as fallback...")
            # Attempt to maximise currently active window as fallback
            self._maximize_active_window()
            logging.info("[IX] Active window maximized (fallback)")
            return

        logging.info("[IX] ✓ Detected new window: '%s'", new_window.title)
        logging.info("[IX] Activating and maximizing window...")
        self._activate_and_maximize(new_window)
        logging.info("[IX] ✓ Window activated and maximized")
        self._report_window(new_window)

    def _locate_template(
        self,
        template_name: str,
        *,
        confidence: float = 0.85,
    ) -> Optional[Dict[str, Tuple[int, int]]]:
        # Temporarily set the screen detector's confidence level
        original_confidence = self.screen.confidence
        self.screen.confidence = confidence
        try:
            result = self.screen.detect_custom_element(template_name)
            if not result.get("found"):
                return None
            if result.get("top_left") and result.get("size"):
                return {
                    "top_left": result["top_left"],
                    "size": result["size"],
                }
            if result.get("position"):
                x, y = result["position"]
                return {"top_left": (x, y), "size": (1, 1)}
            return None
        finally:
            # Restore original confidence
            self.screen.confidence = original_confidence

    def _heuristic_search_input(self) -> Optional[Dict[str, Tuple[int, int]]]:
        """
        Estimate search input location by detecting the "Profile Nam" label
        and offsetting to the right.
        """
        try:
            from ..ocr_detector import OCRDetector  # type: ignore
        except ImportError:
            OCRDetector = None  # type: ignore

        if not OCRDetector:
            return None

        detector = OCRDetector(languages="eng")
        screenshot = self._capture_screenshot()
        match = detector.find_text(
            "Profile Nam",
            screenshot=screenshot,
            allow_partial=True,
            min_confidence=40,
        )
        if not match:
            return None

        x, y = match.center
        estimated = {"top_left": (x + 200, y - 10), "size": (250, 40)}
        logging.debug("[IX] Search input approximated heuristically near %s", estimated)
        return estimated

    @staticmethod
    def _center(location: Dict[str, Tuple[int, int]]) -> Tuple[int, int]:
        top_left = location["top_left"]
        size = location["size"]
        return top_left[0] + size[0] // 2, top_left[1] + size[1] // 2

    @staticmethod
    def _capture_screenshot() -> Image.Image:
        if not pyautogui:
            raise RuntimeError("pyautogui unavailable; cannot capture screenshot.")
        return pyautogui.screenshot()

    @staticmethod
    def _snapshot_window_titles() -> Sequence[str]:
        if not WINDOW_AUTOMATION_AVAILABLE:
            return []
        return [window.title for window in gw.getAllWindows()]  # type: ignore[attr-defined]

    def _detect_new_window(self, baseline_titles: Sequence[str]):
        if not WINDOW_AUTOMATION_AVAILABLE:
            return None
        baseline = set(baseline_titles)
        for window in gw.getAllWindows():  # type: ignore[attr-defined]
            if window.title and window.title not in baseline:
                return window
        return None

    def _activate_and_maximize(self, window) -> None:
        try:
            window.activate()
            time.sleep(0.4)
            if window.isMinimized:
                window.restore()
                time.sleep(0.4)
            window.maximize()
        except Exception as exc:
            logging.debug("[IX] pygetwindow maximise failed: %s", exc)
            self._maximize_active_window()

    @staticmethod
    def _maximize_active_window() -> None:
        if not pyautogui:
            return
        pyautogui.hotkey("alt", "space")
        time.sleep(0.2)
        pyautogui.press("x")

    @staticmethod
    def _report_window(window) -> None:
        title = (window.title or "").strip()
        if not title:
            logging.info("[IX] New window detected but title is empty.")
            return
        lowered = title.lower()
        if "facebook" in lowered:
            logging.info("[IX] Facebook window detected: %s", title)
        elif "business" in lowered:
            logging.info("[IX] Business-related window detected: %s", title)
        else:
            logging.info("[IX] Active window after opening profile: %s", title)
