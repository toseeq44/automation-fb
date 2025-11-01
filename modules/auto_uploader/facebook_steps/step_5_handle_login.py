"""Step 5: Handle logout (if already logged in) or login (if logged out)."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional, Tuple

from .step_1_load_credentials import Credentials
from .utils_mouse_feedback import human_delay

try:
    import pyautogui
except ImportError:
    pyautogui = None  # type: ignore


# Paths to reference images for UI interaction
_HELPER_IMAGES_DIR = Path(__file__).resolve().parent.parent / "helper_images"
_PROFILE_ICON_IMAGE = _HELPER_IMAGES_DIR / "current_profile_cordinates.png"
_LOGOUT_BUTTON_IMAGE = _HELPER_IMAGES_DIR / "current_profile_relatdOption_cordinates.png"
_LOGIN_FORM_IMAGE = _HELPER_IMAGES_DIR / "new_login_cordinates.png"


def _locate_image_center(
    image_path: Path,
    confidence: float = 0.75,
) -> Optional[Tuple[int, int]]:
    """
    Find an image on screen and return its center coordinates.

    Args:
        image_path: Path to the reference image file.
        confidence: Image matching confidence threshold.

    Returns:
        Tuple of (x, y) coordinates at the center of the image, or None if not found.
    """
    if not pyautogui or not image_path.is_file():
        return None

    try:
        region = pyautogui.locateOnScreen(str(image_path), confidence=confidence)
    except TypeError:
        # Older pyautogui versions don't support confidence parameter
        try:
            region = pyautogui.locateOnScreen(str(image_path))
        except Exception as exc:
            logging.debug("Image lookup failed (%s): %s", image_path.name, exc)
            return None
    except Exception as exc:
        logging.debug("Image lookup failed (%s): %s", image_path.name, exc)
        return None

    if region:
        return region.left + region.width // 2, region.top + region.height // 2

    return None


def logout() -> bool:
    """
    Attempt to log out of the current Facebook session.

    Looks for the profile icon and logout option, then clicks them.

    Returns:
        True if logout was performed, False if not possible.
    """
    if not pyautogui:
        logging.warning("pyautogui not available; cannot perform logout")
        return False

    logging.info("Checking for active session to log out...")

    profile_center = _locate_image_center(_PROFILE_ICON_IMAGE)
    if not profile_center:
        logging.info("No active session found (profile icon not visible)")
        return False

    logging.info("Opening profile menu...")
    pyautogui.click(*profile_center)
    human_delay(2, "Waiting for profile menu to appear...")

    logout_center = _locate_image_center(_LOGOUT_BUTTON_IMAGE)
    if not logout_center:
        logging.warning("Logout option not found in menu")
        return False

    logging.info("Clicking logout option...")
    pyautogui.click(*logout_center)
    human_delay(4, "Waiting for logout to complete...")
    return True


def login(credentials: Credentials, typing_interval: float = 0.05) -> bool:
    """
    Fill out the Facebook login form with credentials.

    Args:
        credentials: Credentials object with email and password.
        typing_interval: Delay between keystrokes (in seconds) for human-like typing.

    Returns:
        True if login was performed, False otherwise.
    """
    if not pyautogui:
        logging.warning("pyautogui not available; cannot perform login")
        return False

    logging.info("Starting login process...")

    # Try to locate the login form and focus it
    form_center = _locate_image_center(_LOGIN_FORM_IMAGE)
    if form_center:
        logging.info("Focusing login form...")
        pyautogui.click(*form_center)
    else:
        logging.info("Login form not located; clicking screen center as fallback")
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)

    time.sleep(0.5)

    # Enter email
    logging.info("Entering email address...")
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyautogui.typewrite(credentials.email, interval=typing_interval)

    # Move to password field
    logging.info("Moving to password field...")
    pyautogui.press("tab")
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)

    # Enter password
    logging.info("Entering password...")
    pyautogui.typewrite(credentials.password, interval=typing_interval)

    # Submit form
    logging.info("Submitting login form...")
    pyautogui.press("enter")
    human_delay(6, "Waiting for Facebook to process login...")

    return True
