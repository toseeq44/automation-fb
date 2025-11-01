"""Detect the current Facebook session state."""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Optional

try:
    import pyautogui
except ImportError:  # pragma: no cover - handled at runtime
    pyautogui = None  # type: ignore


_HELPER_IMAGES_DIR = Path(__file__).resolve().parents[1] / "helper_images"
_PROFILE_ICON_IMAGE = _HELPER_IMAGES_DIR / "current_profile_cordinates.png"
_LOGIN_FORM_IMAGE = _HELPER_IMAGES_DIR / "new_login_cordinates.png"


class SessionState(Enum):
    """Possible session states detected on the Facebook page."""

    LOGGED_IN = "logged_in"
    LOGGED_OUT = "logged_out"
    UNKNOWN = "unknown"


def _locate(image_path: Path, confidence: float) -> Optional[object]:
    if not pyautogui or not image_path.is_file():
        return None

    try:
        return pyautogui.locateOnScreen(str(image_path), confidence=confidence)
    except TypeError:
        # Confidence parameter not supported (older pyautogui installs)
        return pyautogui.locateOnScreen(str(image_path))
    except Exception as exc:  # pragma: no cover - GUI interaction
        logging.debug("Image lookup failed (%s): %s", image_path.name, exc)
        return None


def detect_session_state(save_screenshot_to: Optional[Path] = None, confidence: float = 0.75) -> SessionState:
    """
    Attempt to determine whether a Facebook session is already logged in.

    Args:
        save_screenshot_to: Optional file path to store a reference screenshot.
        confidence: Image detection confidence (requires OpenCV for pyautogui).

    Returns:
        Detected ``SessionState`` value.
    """
    if not pyautogui:
        logging.warning("pyautogui is not available; session detection skipped.")
        return SessionState.UNKNOWN

    try:
        screenshot = pyautogui.screenshot()
        if save_screenshot_to:
            try:
                save_screenshot_to.parent.mkdir(parents=True, exist_ok=True)
                screenshot.save(save_screenshot_to)
                logging.info("Saved session screenshot for review: %s", save_screenshot_to)
            except Exception as exc:  # pragma: no cover - filesystem interaction
                logging.debug("Could not save session screenshot: %s", exc)
    except Exception as exc:  # pragma: no cover - GUI interaction
        logging.warning("Failed to take session screenshot: %s", exc)
        return SessionState.UNKNOWN

    if _locate(_PROFILE_ICON_IMAGE, confidence):
        logging.info("Detected active Facebook session (profile icon visible).")
        return SessionState.LOGGED_IN

    if _locate(_LOGIN_FORM_IMAGE, confidence):
        logging.info("Detected Facebook login form.")
        return SessionState.LOGGED_OUT

    logging.info("Session state could not be determined automatically.")
    return SessionState.UNKNOWN
