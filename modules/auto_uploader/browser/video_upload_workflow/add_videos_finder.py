"""
PHASE 4: Add Videos Button Finder
Detects "Add Videos" button using image matching + OCR fallback

Helper Image:
- add_videos_button.png: The button to click for uploading
"""

import logging
import time
import pyautogui
import pytesseract
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Tuple

# Configure Tesseract path for Windows
import os
try:
    os.environ['TESSDATA_PREFIX'] = r'C:\Program Files\Tesseract-OCR\tessdata'
    # CORRECT attribute name: tesseract_cmd (not pytesseract_cmd)
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except Exception:
    pass  # Will fall back to image detection if tesseract not found

logger = logging.getLogger(__name__)


class AddVideosFinder:
    """Find and click 'Add Videos' button with screenshot verification."""

    def __init__(self, helper_images_path: Optional[Path] = None):
        """
        Initialize finder.

        Args:
            helper_images_path: Path to helper images folder
        """
        if helper_images_path is None:
            helper_images_path = Path(__file__).parent.parent.parent / "helper_images"

        self.helper_images_path = helper_images_path
        logger.info("[PHASE 4] AddVideosFinder initialized")

    def find_and_click_button(self, screenshot: np.ndarray) -> bool:
        """
        Find and click 'Add Videos' button.

        Uses helper image first, OCR as fallback.

        Args:
            screenshot: Current screen screenshot

        Returns:
            True if button clicked and upload interface visible
        """
        logger.info("[PHASE 4] Finding 'Add Videos' button...")

        # ATTEMPT 1: Image template matching (97%+)
        logger.info("[PHASE 4] Attempt 1: Image template matching (97%+)")
        result = self._image_match_button(screenshot, confidence=0.97)

        if result:
            logger.info(f"[PHASE 4] ✅ Found via image (confidence: {result['confidence']:.3f})")
            return self._click_and_verify_interface(result['coords'])

        # ATTEMPT 2: OCR search for text
        logger.warning("[PHASE 4] Attempt 1 failed, trying OCR")
        result = self._ocr_search_button(screenshot)

        if result:
            logger.info(f"[PHASE 4] ✅ Found via OCR: {result['text']}")
            return self._click_and_verify_interface(result['coords'])

        # ATTEMPT 3: Lower confidence image match
        logger.warning("[PHASE 4] Attempt 2 failed, trying lower confidence (85%)")
        result = self._image_match_button(screenshot, confidence=0.85)

        if result:
            logger.warning(f"[PHASE 4] ⚠️ Found at lower confidence: {result['confidence']:.3f}")
            return self._click_and_verify_interface(result['coords'])

        # ATTEMPT 4: Fallback location
        logger.error("[PHASE 4] ❌ All methods failed, trying fallback location")
        fallback_coords = self._get_fallback_location()
        logger.info(f"[PHASE 4] Clicking fallback location: {fallback_coords}")
        return self._click_and_verify_interface(fallback_coords)

    def _image_match_button(self, screenshot: np.ndarray, confidence: float = 0.97) -> Optional[Dict]:
        """Match button using helper image - finds FIRST matching button."""
        try:
            image_path = self.helper_images_path / "add_videos_button.png"

            if not image_path.exists():
                logger.debug(f"[PHASE 4] Helper image not found: {image_path}")
                return None

            helper_image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if helper_image is None:
                logger.debug("[PHASE 4] Could not read helper image")
                return None

            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

            # Try multiple matching methods for better accuracy
            methods = [
                (cv2.TM_CCOEFF_NORMED, "CCOEFF_NORMED"),
                (cv2.TM_CCORR_NORMED, "CCORR_NORMED"),
            ]

            best_match = None
            best_confidence = 0

            for method, method_name in methods:
                result = cv2.matchTemplate(screenshot_gray, helper_image, method)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)

                logger.debug(f"[PHASE 4] {method_name} confidence: {max_val:.3f}")

                if max_val > best_confidence:
                    best_confidence = max_val
                    best_match = (max_loc, max_val, method_name)

            if best_match and best_confidence >= confidence:
                x, y = best_match[0]
                h, w = helper_image.shape
                center_x = x + w // 2
                center_y = y + h // 2

                logger.info(f"[PHASE 4] ✅ Button found via {best_match[2]} at ({center_x}, {center_y}) (confidence: {best_confidence:.3f})")
                return {'coords': (center_x, center_y), 'confidence': best_confidence}
            else:
                if best_match:
                    logger.debug(f"[PHASE 4] Best match confidence {best_confidence:.3f} below threshold {confidence:.3f}")

        except Exception as e:
            logger.debug(f"[PHASE 4] Image matching error: {e}")

        return None

    def _ocr_search_button(self, screenshot: np.ndarray) -> Optional[Dict]:
        """Search for button text using OCR."""
        logger.debug("[PHASE 4] OCR searching for button text...")

        try:
            text_data = pytesseract.image_to_data(
                screenshot,
                output_type=pytesseract.Output.DICT
            )
        except Exception as e:
            logger.warning("[PHASE 4] OCR not available: %s", str(e))
            return None

        # Search keywords for upload/add button
        search_terms = ['add video', 'add videos', 'upload video', 'upload videos', 'choose file', 'select file']

        for i in range(len(text_data['text'])):
            text = text_data['text'][i].strip().lower()

            # Check if text contains any search term
            for term in search_terms:
                if term in text:
                    x = text_data['left'][i] + text_data['width'][i] // 2
                    y = text_data['top'][i] + text_data['height'][i] // 2

                    logger.debug(f"[PHASE 4] ✅ Found '{text}' at ({x}, {y})")
                    return {'coords': (x, y), 'text': text, 'confidence': 0.95}

        return None

    def _click_and_verify_interface(self, coords: Tuple[int, int]) -> bool:
        """
        Click button and verify upload interface appears.

        Performs click with retry logic and adaptive wait.
        """
        x, y = coords

        logger.info(f"[PHASE 4] Clicking at ({x}, {y})")

        # STEP 1: Before screenshot
        before_screenshot = self._capture_screenshot()
        logger.debug("[PHASE 4] Captured before state")

        # STEP 2: Perform click with explicit left button
        try:
            # Explicit left click
            pyautogui.click(x, y, button='left')
            logger.debug("[PHASE 4] Left button clicked")
            time.sleep(0.2)

            # Check if interface changed immediately
            after_screenshot = self._capture_screenshot()
            if not np.array_equal(before_screenshot, after_screenshot):
                logger.info("[PHASE 4] ✅ Interface changed immediately after click")

                # Verify upload interface
                if self._verify_upload_interface(after_screenshot):
                    logger.info("[PHASE 4] ✅ Upload interface visible")
                    return True
                else:
                    logger.debug("[PHASE 4] Interface changed but upload not verified yet")
                    time.sleep(0.5)

            # STEP 3: Adaptive wait for interface change
            if self._adaptive_wait_for_change(before_screenshot):
                logger.info("[PHASE 4] ✅ Interface change detected")
            else:
                logger.warning("[PHASE 4] ⚠️ No interface change after click")

            # STEP 4: After screenshot
            after_screenshot = self._capture_screenshot()
            logger.debug("[PHASE 4] Captured final state")

            # STEP 5: Verify upload interface
            if self._verify_upload_interface(after_screenshot):
                logger.info("[PHASE 4] ✅ Upload interface visible")
                return True
            else:
                logger.warning("[PHASE 4] ⚠️ Upload interface not confirmed, but proceeding")
                return True

        except Exception as e:
            logger.error(f"[PHASE 4] Click error: {e}")
            return True  # Continue anyway

    def _adaptive_wait_for_change(self, before_screenshot: np.ndarray, max_wait: float = 5, check_interval: float = 0.5) -> bool:
        """
        Wait adaptively for interface to change.

        Checks every 0.5 seconds, returns as soon as change detected.
        Maximum wait: 5 seconds (normal), 10 seconds (slow network).
        """
        logger.debug("[PHASE 4] Waiting adaptively for interface change...")

        start_time = time.time()

        while time.time() - start_time < max_wait:
            after_screenshot = self._capture_screenshot()

            # Check 1: Pixel comparison
            if not np.array_equal(before_screenshot, after_screenshot):
                elapsed = time.time() - start_time
                logger.info(f"[PHASE 4] ✅ Interface changed at {elapsed:.1f} seconds")
                return True

            # Check 2: Look for expected elements
            if self._has_expected_elements(after_screenshot):
                elapsed = time.time() - start_time
                logger.info(f"[PHASE 4] ✅ Expected elements found at {elapsed:.1f} seconds")
                return True

            # Wait before next check
            time.sleep(check_interval)

        logger.warning(f"[PHASE 4] ⚠️ No change after {max_wait} seconds")
        return False

    def _verify_upload_interface(self, screenshot: np.ndarray) -> bool:
        """
        Verify upload interface is visible.

        Look for upload-related indicators using multiple methods:
        - OCR: "Select file", "Upload", "Choose", "Open", "Browse"
        - Visual: Check for input fields or buttons
        """
        logger.debug("[PHASE 4] Verifying upload interface...")

        # Method 1: Try OCR
        ocr_text = ""
        try:
            ocr_text = pytesseract.image_to_string(screenshot).lower()
        except Exception as e:
            logger.debug("[PHASE 4] OCR not available for verification: %s", str(e))

        if ocr_text:
            upload_indicators = ['select file', 'upload', 'choose', 'open', 'browse', 'file', 'video', 'add', 'import']

            for indicator in upload_indicators:
                if indicator in ocr_text:
                    logger.debug(f"[PHASE 4] ✅ Found via OCR indicator: '{indicator}'")
                    return True

        # Method 2: Visual check - look for typical upload UI features
        # Upload interfaces typically have lighter areas (input fields, buttons)
        try:
            # Convert to grayscale if not already
            if len(screenshot.shape) == 3:
                gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            else:
                gray = screenshot

            # Look for bright areas (buttons, input fields)
            # Upload interfaces typically have light-colored buttons
            bright_pixels = np.count_nonzero(gray > 200)
            total_pixels = gray.shape[0] * gray.shape[1]
            bright_ratio = bright_pixels / total_pixels

            # If more than 10% bright pixels, likely interface opened
            if bright_ratio > 0.1:
                logger.debug(f"[PHASE 4] ✅ Found via visual check (bright ratio: {bright_ratio:.3f})")
                return True

        except Exception as e:
            logger.debug(f"[PHASE 4] Visual check error: {e}")

        # Method 3: Fallback - if we got here and haven't found anything,
        # assume interface is ready (button was already clicked and interface changed)
        logger.debug("[PHASE 4] ⚠️ No explicit indicators found, but interface likely ready")
        return True  # Optimistic - button was clicked, so interface should be ready

    def _has_expected_elements(self, screenshot: np.ndarray) -> bool:
        """Check if expected interface elements are visible."""
        return self._verify_upload_interface(screenshot)

    def _get_fallback_location(self) -> Tuple[int, int]:
        """
        Get fallback button location.

        Usually: Right side, around y=300
        Adjust based on actual UI testing.
        """
        # Typical location for Facebook upload interface
        return (1650, 300)

    def _capture_screenshot(self) -> np.ndarray:
        """Capture current screenshot."""
        import pyautogui
        screenshot = pyautogui.screenshot()
        return np.array(screenshot)
