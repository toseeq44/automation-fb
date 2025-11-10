"""
ixBrowser Auto-Login Helper
Uses image recognition to automatically login to ixBrowser desktop application
"""

import logging
import time
from pathlib import Path
from typing import Optional, Tuple
import pyautogui
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Helper images directory
HELPER_IMAGES_DIR = Path(__file__).parents[2] / "helper_images"


class IXBrowserLoginHelper:
    """Automatically logs into ixBrowser using image recognition."""

    def __init__(self, email: str, password: str):
        """
        Initialize login helper.

        Args:
            email: ixBrowser login email
            password: ixBrowser login password
        """
        self.email = email
        self.password = password

        # Image paths
        self.login_window_img = HELPER_IMAGES_DIR / "sample_login_window.png"
        self.profile_icon_img = HELPER_IMAGES_DIR / "login_profile_icon.png"
        self.password_icon_img = HELPER_IMAGES_DIR / "login_password_icon.png"

        # Verify images exist
        self._verify_images()

        logger.info("[IXLogin] Auto-login helper initialized")
        logger.info("[IXLogin]   Email: %s", email)
        logger.info("[IXLogin]   Helper images: %s", HELPER_IMAGES_DIR)

    def _verify_images(self) -> None:
        """Verify all required images exist."""
        missing = []

        if not self.login_window_img.exists():
            missing.append(str(self.login_window_img))
        if not self.profile_icon_img.exists():
            missing.append(str(self.profile_icon_img))
        if not self.password_icon_img.exists():
            missing.append(str(self.password_icon_img))

        if missing:
            logger.error("[IXLogin] Missing helper images:")
            for img in missing:
                logger.error("[IXLogin]   - %s", img)
            raise FileNotFoundError(f"Missing helper images: {missing}")

        logger.debug("[IXLogin] All helper images found")

    def detect_login_window(self, confidence: float = 0.4) -> bool:
        """
        Detect if ixBrowser login window is visible.

        Args:
            confidence: Minimum confidence threshold (0.0-1.0)

        Returns:
            True if login window detected
        """
        logger.info("[IXLogin] Detecting login window...")
        logger.info("[IXLogin]   Confidence threshold: %.0f%%", confidence * 100)

        # Try PyAutoGUI first
        try:
            location = pyautogui.locateOnScreen(
                str(self.login_window_img),
                confidence=confidence
            )
            if location:
                logger.info("[IXLogin] ✓ Login window detected (PyAutoGUI)")
                logger.info("[IXLogin]   Location: %s", location)
                return True
        except Exception as e:
            logger.debug("[IXLogin] PyAutoGUI detection failed: %s", str(e))

        # Fallback to OpenCV
        try:
            if self._detect_with_opencv(self.login_window_img, confidence):
                logger.info("[IXLogin] ✓ Login window detected (OpenCV)")
                return True
        except Exception as e:
            logger.debug("[IXLogin] OpenCV detection failed: %s", str(e))

        logger.info("[IXLogin] ✗ Login window not detected")
        return False

    def _detect_with_opencv(self, template_path: Path, confidence: float) -> bool:
        """
        Detect image using OpenCV template matching.

        Args:
            template_path: Path to template image
            confidence: Minimum confidence threshold

        Returns:
            True if detected with sufficient confidence
        """
        # Take screenshot
        screenshot = pyautogui.screenshot()
        screenshot_np = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)

        # Load template
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            logger.error("[IXLogin] Failed to load template: %s", template_path)
            return False

        # Template matching
        result = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        logger.debug("[IXLogin] OpenCV match confidence: %.2f", max_val)

        return max_val >= confidence

    def find_and_click_field(self, icon_img: Path, offset_x: int = 5) -> bool:
        """
        Find icon and click to the right of it.

        Args:
            icon_img: Path to icon image
            offset_x: Pixels to offset right from icon (default 5)

        Returns:
            True if found and clicked
        """
        logger.info("[IXLogin] Looking for: %s", icon_img.name)

        # Try PyAutoGUI first
        try:
            location = pyautogui.locateOnScreen(str(icon_img), confidence=0.7)
            if location:
                # Click to the right of the icon
                click_x = location.left + location.width + offset_x
                click_y = location.top + (location.height // 2)

                logger.info("[IXLogin] ✓ Found icon (PyAutoGUI)")
                logger.info("[IXLogin]   Clicking at: (%d, %d)", click_x, click_y)

                pyautogui.click(click_x, click_y)
                time.sleep(0.5)  # Wait for field to activate
                return True
        except Exception as e:
            logger.debug("[IXLogin] PyAutoGUI failed: %s", str(e))

        # Fallback to OpenCV
        try:
            location = self._find_with_opencv(icon_img)
            if location:
                x, y, w, h = location
                click_x = x + w + offset_x
                click_y = y + (h // 2)

                logger.info("[IXLogin] ✓ Found icon (OpenCV)")
                logger.info("[IXLogin]   Clicking at: (%d, %d)", click_x, click_y)

                pyautogui.click(click_x, click_y)
                time.sleep(0.5)
                return True
        except Exception as e:
            logger.debug("[IXLogin] OpenCV failed: %s", str(e))

        logger.error("[IXLogin] ✗ Could not find: %s", icon_img.name)
        return False

    def _find_with_opencv(self, template_path: Path) -> Optional[Tuple[int, int, int, int]]:
        """
        Find image location using OpenCV.

        Args:
            template_path: Path to template image

        Returns:
            Tuple of (x, y, width, height) or None
        """
        # Take screenshot
        screenshot = pyautogui.screenshot()
        screenshot_np = np.array(screenshot)
        screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)

        # Load template
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            return None

        # Template matching
        result = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.7:
            h, w = template.shape
            x, y = max_loc
            return (x, y, w, h)

        return None

    def perform_login(self, retry_count: int = 3) -> bool:
        """
        Perform complete login sequence.

        Args:
            retry_count: Number of retries if login fails

        Returns:
            True if login successful
        """
        for attempt in range(1, retry_count + 1):
            logger.info("[IXLogin] ═══════════════════════════════════════════")
            logger.info("[IXLogin] Login Attempt %d/%d", attempt, retry_count)
            logger.info("[IXLogin] ═══════════════════════════════════════════")

            try:
                # Step 1: Detect login window
                if not self.detect_login_window():
                    logger.warning("[IXLogin] Login window not visible, waiting...")
                    time.sleep(2)
                    continue

                # Step 2: Click email field
                logger.info("[IXLogin] Step 1: Activating email field...")
                if not self.find_and_click_field(self.profile_icon_img, offset_x=5):
                    logger.error("[IXLogin] Failed to find email field")
                    time.sleep(2)
                    continue

                # Step 3: Type email
                logger.info("[IXLogin] Step 2: Typing email...")
                pyautogui.write(self.email, interval=0.05)
                time.sleep(0.5)

                # Step 4: Click password field
                logger.info("[IXLogin] Step 3: Activating password field...")
                if not self.find_and_click_field(self.password_icon_img, offset_x=5):
                    logger.error("[IXLogin] Failed to find password field")
                    time.sleep(2)
                    continue

                # Step 5: Type password
                logger.info("[IXLogin] Step 4: Typing password...")
                pyautogui.write(self.password, interval=0.05)
                time.sleep(0.5)

                # Step 6: Press Enter
                logger.info("[IXLogin] Step 5: Submitting login...")
                pyautogui.press('enter')

                logger.info("[IXLogin] ✓ Login sequence completed!")
                logger.info("[IXLogin] Waiting for ixBrowser to process login...")
                return True

            except Exception as e:
                logger.error("[IXLogin] Login attempt %d failed: %s", attempt, str(e))
                if attempt < retry_count:
                    logger.info("[IXLogin] Retrying in 2 seconds...")
                    time.sleep(2)

        logger.error("[IXLogin] ✗ All login attempts failed!")
        return False


def test_login_helper():
    """Test the login helper."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print("\n" + "="*60)
    print("ixBrowser Auto-Login Helper - Test Mode")
    print("="*60 + "\n")

    # Test email/password (dummy)
    email = "test@example.com"
    password = "test_password"

    helper = IXBrowserLoginHelper(email, password)

    print("\n1. Testing login window detection...")
    if helper.detect_login_window(confidence=0.4):
        print("✓ Login window detected!")

        print("\n2. Testing login sequence...")
        if helper.perform_login():
            print("✓ Login sequence completed!")
        else:
            print("✗ Login sequence failed!")
    else:
        print("✗ Login window not detected")
        print("\nNote: Make sure ixBrowser is running and login window is visible")


if __name__ == "__main__":
    test_login_helper()
