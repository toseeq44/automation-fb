"""Step 4: Check if a user is currently logged into Facebook."""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Optional

try:
    import pyautogui
except ImportError:
    pyautogui = None  # type: ignore


class SessionStatus(Enum):
    """Possible session states on the Facebook page."""

    LOGGED_IN = "logged_in"
    LOGGED_OUT = "logged_out"
    UNKNOWN = "unknown"


# Paths to reference images for detecting login state
_HELPER_IMAGES_DIR = Path(__file__).resolve().parent.parent / "helper_images"
_PROFILE_ICON_IMAGE = _HELPER_IMAGES_DIR / "current_profile_cordinates.png"
_LOGIN_FORM_IMAGE = _HELPER_IMAGES_DIR / "new_login_cordinates.png"


def _image_found_on_screen(image_path: Path, confidence: float = 0.75) -> bool:
    """
    Check if an image is visible on the current screen.

    Args:
        image_path: Path to the reference image file.
        confidence: Image matching confidence threshold (0.0-1.0).

    Returns:
        True if the image is found on screen, False otherwise.
    """
    if not pyautogui or not image_path.is_file():
        return False

    try:
        result = pyautogui.locateOnScreen(str(image_path), confidence=confidence)
        return result is not None
    except TypeError:
        # Older pyautogui versions don't support confidence parameter
        try:
            result = pyautogui.locateOnScreen(str(image_path))
            return result is not None
        except Exception as exc:
            logging.debug("Image lookup failed (%s): %s", image_path.name, exc)
            return False
    except Exception as exc:
        logging.debug("Image lookup failed (%s): %s", image_path.name, exc)
        return False


def check_session(
    save_screenshot_to: Optional[Path] = None,
    confidence: float = 0.75,
) -> SessionStatus:
    """
    Detect whether a user is currently logged into Facebook.

    Uses image recognition to detect profile icons (logged in) or login forms (logged out).

    Args:
        save_screenshot_to: Optional file path to save a reference screenshot.
        confidence: Image matching confidence threshold.

    Returns:
        SessionStatus enum indicating the login state.
    """
    if not pyautogui:
        logging.warning("pyautogui is not available; cannot check session state")
        return SessionStatus.UNKNOWN

    # Try to capture and save a screenshot for debugging
    if save_screenshot_to:
        try:
            screenshot = pyautogui.screenshot()
            save_screenshot_to.parent.mkdir(parents=True, exist_ok=True)
            screenshot.save(save_screenshot_to)
            logging.info("Saved session screenshot: %s", save_screenshot_to)
        except Exception as exc:
            logging.debug("Could not save screenshot: %s", exc)

    # Check for logged-in state (profile icon visible)
    if _image_found_on_screen(_PROFILE_ICON_IMAGE, confidence):
        logging.info("Detected logged-in state (profile icon found)")
        return SessionStatus.LOGGED_IN

    # Check for logged-out state (login form visible)
    if _image_found_on_screen(_LOGIN_FORM_IMAGE, confidence):
        logging.info("Detected logged-out state (login form found)")
        return SessionStatus.LOGGED_OUT

    logging.info("Session state could not be determined")
    return SessionStatus.UNKNOWN
