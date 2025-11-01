"""Perform login and logout actions on Facebook."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional, Tuple

try:
    import pyautogui
except ImportError:  # pragma: no cover - handled at runtime
    pyautogui = None  # type: ignore

from .login_data_reader import LoginData
from .mouse_feedback import human_delay

_HELPER_IMAGES_DIR = Path(__file__).resolve().parents[1] / "helper_images"
_PROFILE_ICON_IMAGE = _HELPER_IMAGES_DIR / "current_profile_cordinates.png"
_LOGOUT_BUTTON_IMAGE = _HELPER_IMAGES_DIR / "current_profile_relatdOption_cordinates.png"
_LOGIN_FORM_IMAGE = _HELPER_IMAGES_DIR / "new_login_cordinates.png"


def _locate_center(image_path: Path, confidence: float = 0.75) -> Optional[Tuple[int, int]]:
    if not pyautogui or not image_path.is_file():
        return None

    try:
        region = pyautogui.locateOnScreen(str(image_path), confidence=confidence)
    except TypeError:
        region = pyautogui.locateOnScreen(str(image_path))
    except Exception as exc:  # pragma: no cover - GUI interaction
        logging.debug("Image lookup failed (%s): %s", image_path.name, exc)
        region = None

    if region:
        return region.left + region.width // 2, region.top + region.height // 2

    return None


def logout_current_session(confidence: float = 0.75) -> bool:
    """
    Attempt to log out of the current Facebook session.

    Args:
        confidence: Confidence level for image matching.

    Returns:
        True if a logout sequence was attempted, False otherwise.
    """
    if not pyautogui:
        logging.warning("pyautogui not available; cannot perform logout.")
        return False

    profile_center = _locate_center(_PROFILE_ICON_IMAGE, confidence)
    if not profile_center:
        logging.info("Profile icon not detected; skipping logout.")
        return False

    logging.info("Opening profile menu to log out.")
    pyautogui.click(*profile_center)
    human_delay(2, "Waiting for profile menu to appear...")

    logout_center = _locate_center(_LOGOUT_BUTTON_IMAGE, confidence)
    if not logout_center:
        logging.warning("Logout option not detected after opening profile menu.")
        return False

    pyautogui.click(*logout_center)
    human_delay(4, "Waiting for logout to complete...")
    return True


def login_with_credentials(login_data: LoginData, confidence: float = 0.75, typing_interval: float = 0.05) -> bool:
    """
    Fill out the Facebook login form with the provided credentials.

    Args:
        login_data: Credentials loaded from ``login_data.txt``.
        confidence: Confidence level for image matching.
        typing_interval: Delay between keystrokes for human-like typing.

    Returns:
        True if the login sequence was executed.
    """
    if not pyautogui:
        logging.warning("pyautogui not available; cannot perform login.")
        return False

    form_center = _locate_center(_LOGIN_FORM_IMAGE, confidence)

    if form_center:
        logging.info("Focusing Facebook login form.")
        pyautogui.click(*form_center)
    else:
        logging.info("Login form image not detected; clicking screen center.")
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)

    time.sleep(0.5)

    logging.info("Typing email address.")
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyautogui.typewrite(login_data.email, interval=typing_interval)

    logging.info("Switching to password field.")
    pyautogui.press("tab")
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)

    logging.info("Typing password.")
    pyautogui.typewrite(login_data.password, interval=typing_interval)

    logging.info("Submitting login form.")
    pyautogui.press("enter")
    human_delay(6, "Waiting for Facebook to process login...")
    return True
