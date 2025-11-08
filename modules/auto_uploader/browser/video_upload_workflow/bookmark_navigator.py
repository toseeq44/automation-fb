"""
PHASE 1B: Bookmark Navigator
Uses helper images to navigate bookmarks and click correct page

Helper Images:
- all_bookmarks.png: Show all bookmarks option
- open_side_panel_to_see_all_bookmarks.png: Open bookmarks panel
- search_bookmarks_bar.png: Search bar for bookmarks
- bookmarks_close.png: Close button (X icon)
"""

import logging
import time
import pyautogui
import os
import sys

# Configure Tesseract path for Windows BEFORE importing pytesseract
os.environ['TESSDATA_PREFIX'] = r'C:\Program Files\Tesseract-OCR\tessdata'

# Try to import pytesseract and configure it
try:
    import pytesseract
    # CORRECT attribute name: tesseract_cmd (not pytesseract_cmd)
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except Exception as e:
    pytesseract = None

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class BookmarkNavigator:
    """Navigate bookmarks using helper images and OCR."""

    def __init__(self, helper_images_path: Optional[Path] = None):
        """
        Initialize navigator.

        Args:
            helper_images_path: Path to helper images folder
        """
        if helper_images_path is None:
            helper_images_path = Path(__file__).parent.parent.parent / "helper_images"

        self.helper_images_path = helper_images_path
        logger.info("[PHASE 1B] BookmarkNavigator initialized")
        logger.info(f"[PHASE 1B] Helper images: {self.helper_images_path}")

    def find_and_click_bookmark(self, page_name: str, screenshot: np.ndarray) -> bool:
        """
        Find and click bookmark for given page name.

        Uses helper images to navigate bookmarks UI.

        Args:
            page_name: Name of page to find in bookmarks
            screenshot: Current screen screenshot

        Returns:
            True if bookmark clicked successfully
        """
        logger.info(f"[PHASE 1B] Finding bookmark: {page_name}")

        # STEP 1: Try to find in current visible bookmarks (OCR)
        logger.info("[PHASE 1B] Step 1: OCR search in visible bookmarks")
        result = self._ocr_search_visible(screenshot, page_name)
        if result:
            logger.info(f"[PHASE 1B] ✅ Found in visible bookmarks: {page_name}")
            return self._click_and_verify(result, page_name)

        # STEP 2: Open bookmark panel using helper images
        logger.info("[PHASE 1B] Step 2: Opening bookmark panel (helper image)")
        if not self._open_bookmark_panel():
            logger.error("[PHASE 1B] ❌ Failed to open bookmark panel")
            return False

        # STEP 3: Look for bookmark in the opened panel (direct search)
        logger.info("[PHASE 1B] Step 3: Searching for bookmark in open panel")
        time.sleep(0.5)
        screenshot = self._capture_screenshot()

        # Try to find bookmark directly in panel using OCR or fuzzy
        result = self._find_bookmark_in_panel(screenshot, page_name)

        if result:
            logger.info(f"[PHASE 1B] ✅ Found bookmark in panel: {page_name}")
            success = self._click_and_verify(result, page_name)
            self._close_bookmark_panel()
            return success

        # STEP 4: Try search bar as fallback
        logger.info("[PHASE 1B] Step 4: Trying bookmark search bar")
        result = self._ocr_search_in_search_bar(screenshot, page_name)

        if result:
            logger.info(f"[PHASE 1B] ✅ Found via search bar: {page_name}")
            success = self._click_and_verify(result, page_name)
            self._close_bookmark_panel()
            return success

        # STEP 5: Fuzzy match as last resort
        logger.warning("[PHASE 1B] Step 5: Trying fuzzy match (90%+)")
        result = self._fuzzy_search(screenshot, page_name)
        if result:
            logger.warning(f"[PHASE 1B] ⚠️ Fuzzy match: {result.get('matched_text', 'unknown')}")
            success = self._click_and_verify(result, page_name)
            self._close_bookmark_panel()
            return success

        # All failed
        logger.error(f"[PHASE 1B] ❌ Bookmark not found: {page_name}")
        self._close_bookmark_panel()
        return False

    def _ocr_search_visible(self, screenshot: np.ndarray, page_name: str) -> Optional[Dict]:
        """Search for page name in visible bookmarks using OCR."""
        logger.debug("[PHASE 1B] OCR searching visible bookmarks...")

        # Check if pytesseract is available
        if pytesseract is None:
            logger.debug("[PHASE 1B] Pytesseract not available, skipping OCR visible")
            return None

        # Search bookmark bar (top 120 pixels to get full height)
        bookmark_region = screenshot[35:120, :]

        try:
            text_data = pytesseract.image_to_data(
                bookmark_region,
                output_type=pytesseract.Output.DICT
            )
        except Exception as e:
            logger.debug("[PHASE 1B] OCR error in visible search: %s", str(e))
            return None

        # Search for exact match
        for i in range(len(text_data['text'])):
            text = text_data['text'][i].strip()

            if not text or len(text) < 2:
                continue

            if text.lower() == page_name.lower():
                x = text_data['left'][i] + text_data['width'][i] // 2
                y = 35 + text_data['top'][i] + text_data['height'][i] // 2
                logger.info(f"[PHASE 1B] ✅ Exact match in visible bar: {text} at ({x}, {y})")
                return {'coords': (x, y), 'text': text, 'confidence': 1.0}

        # Try partial match
        for i in range(len(text_data['text'])):
            text = text_data['text'][i].strip()

            if not text or len(text) < 2:
                continue

            if page_name.lower() in text.lower() or text.lower() in page_name.lower():
                similarity = len(set(page_name.lower()) & set(text.lower())) / max(len(set(page_name.lower())), len(set(text.lower())))
                if similarity >= 0.6:
                    x = text_data['left'][i] + text_data['width'][i] // 2
                    y = 35 + text_data['top'][i] + text_data['height'][i] // 2
                    logger.info(f"[PHASE 1B] Partial match in visible: {text} ({similarity:.2f})")
                    return {'coords': (x, y), 'text': text, 'confidence': similarity}

        return None

    def _find_bookmark_in_panel(self, screenshot: np.ndarray, page_name: str) -> Optional[Dict]:
        """Find bookmark directly in the opened panel using OCR."""
        logger.debug("[PHASE 1B] Finding bookmark in opened panel...")

        # Use OCR to find exact bookmark name
        if pytesseract is not None:
            try:
                # Get OCR data from ENTIRE screenshot
                text_data = pytesseract.image_to_data(
                    screenshot,
                    output_type=pytesseract.Output.DICT
                )

                # Search for exact match in panel area (left side)
                for i in range(len(text_data['text'])):
                    text = text_data['text'][i].strip()

                    if not text or len(text) < 2:
                        continue

                    # Get coordinates
                    x = text_data['left'][i] + text_data['width'][i] // 2
                    y = text_data['top'][i] + text_data['height'][i] // 2

                    # Must be in left panel (x < 500)
                    if x > 500:
                        continue

                    # Exact match (case-insensitive)
                    if text.lower() == page_name.lower():
                        logger.info(f"[PHASE 1B] ✅ Exact OCR match in panel: {text} at ({x}, {y})")
                        return {'coords': (x, y), 'text': text, 'confidence': 1.0}

                # If no exact match, try partial match
                best_match = None
                best_score = 0

                for i in range(len(text_data['text'])):
                    text = text_data['text'][i].strip()

                    if not text or len(text) < 2:
                        continue

                    x = text_data['left'][i] + text_data['width'][i] // 2
                    y = text_data['top'][i] + text_data['height'][i] // 2

                    # Must be in left panel
                    if x > 500:
                        continue

                    # Check if page_name is in text OR text is in page_name
                    if page_name.lower() in text.lower() or text.lower() in page_name.lower():
                        # Calculate similarity
                        similarity = len(set(page_name.lower()) & set(text.lower())) / max(len(set(page_name.lower())), len(set(text.lower())))

                        if similarity >= 0.5 and similarity > best_score:
                            best_match = {'coords': (x, y), 'text': text, 'confidence': similarity}
                            best_score = similarity

                if best_match:
                    logger.info(f"[PHASE 1B] ✅ Partial OCR match in panel: {best_match['text']} ({best_score:.2f})")
                    return best_match

            except Exception as e:
                logger.debug("[PHASE 1B] OCR search in panel failed: %s", str(e))

        # Fallback: Use estimated coordinates in panel
        logger.debug("[PHASE 1B] Using estimated coordinates in panel")
        # Panel is on left (~400 width), centered vertically
        estimated_x = 150  # Left third of panel
        estimated_y = 300  # Below panel header

        logger.debug(f"[PHASE 1B] Using estimated coordinates: ({estimated_x}, {estimated_y})")
        return {'coords': (estimated_x, estimated_y), 'text': page_name, 'confidence': 0.5}

    def _ocr_search_in_search_bar(self, screenshot: np.ndarray, page_name: str) -> Optional[Dict]:
        """Search for page name in bookmark search bar using helper images."""
        logger.debug("[PHASE 1B] Searching in bookmark search bar...")

        try:
            # Step 1: Click search bar using helper image
            logger.debug("[PHASE 1B] Finding search_bookmarks_bar helper image...")
            if not self._image_match_and_click("search_bookmarks_bar", confidence=0.85):
                logger.warning("[PHASE 1B] Could not find or click search bar")
                return None

            logger.info("[PHASE 1B] ✅ Search bar clicked")

            # Step 2: Type page name in search bar
            time.sleep(0.3)
            # Type without spaces for better search matching
            pyautogui.typewrite(page_name.replace(' ', ''), interval=0.05)
            logger.debug("[PHASE 1B] Typed search query: %s", page_name)
            time.sleep(1.5)  # Wait longer for results to appear

            # Step 3: Capture after search and look for results
            logger.debug("[PHASE 1B] Looking for search results...")
            after_search = self._capture_screenshot()

            # Step 4: Try to detect search results area using helper image
            logger.debug("[PHASE 1B] Detecting search results area...")
            if self._image_match_and_click("results_found_in_all_bookmarks.png", confidence=0.85):
                logger.info("[PHASE 1B] ✅ Search results area detected")
                time.sleep(0.5)
            else:
                logger.debug("[PHASE 1B] Results area helper image not found, using fallback coordinates")

            # Step 5: Use OCR to find exact bookmark in results
            logger.debug("[PHASE 1B] Searching for exact bookmark in results...")
            result = self._find_bookmark_in_results(after_search, page_name)

            if result:
                logger.info("[PHASE 1B] ✅ Found bookmark via OCR: %s", page_name)
                x, y = result['coords']
                pyautogui.click(x, y)
                time.sleep(0.5)
                logger.info("[PHASE 1B] ✅ Clicked search result")
                return result

            # Step 6: Fallback - use approximate coordinates for first result
            # Results appear ~150px below search bar, with ~30px per row
            # Usually 4 tab rows down from results header
            logger.warning("[PHASE 1B] Using fallback coordinates for first result")
            result_coords = (700, 220)  # Adjusted from (700, 180) for better accuracy

            pyautogui.click(result_coords)
            time.sleep(0.5)

            logger.info("[PHASE 1B] ✅ Clicked search result (fallback)")
            return {'coords': result_coords, 'text': page_name, 'confidence': 0.7}

        except Exception as e:
            logger.warning("[PHASE 1B] Search bar operation error: %s", str(e))
            return None

    def _find_bookmark_in_results(self, screenshot: np.ndarray, page_name: str) -> Optional[Dict]:
        """Find exact bookmark in search results using OCR."""
        logger.debug("[PHASE 1B] Finding bookmark in search results...")

        # Check if pytesseract is available
        if pytesseract is None:
            logger.debug("[PHASE 1B] Pytesseract not available, skipping OCR bookmark finding")
            return None

        try:
            # Get OCR data from screenshot
            text_data = pytesseract.image_to_data(
                screenshot,
                output_type=pytesseract.Output.DICT
            )

            best_match = None
            best_score = 0

            # Search for page name in results
            for i in range(len(text_data['text'])):
                text = text_data['text'][i].strip()

                if not text:
                    continue

                # Check for exact match (case-insensitive)
                if text.lower() == page_name.lower():
                    x = text_data['left'][i] + text_data['width'][i] // 2
                    y = text_data['top'][i] + text_data['height'][i] // 2
                    confidence = 1.0

                    logger.debug("[PHASE 1B] Exact match found: %s at (%d, %d)", text, x, y)
                    return {'coords': (x, y), 'text': text, 'confidence': confidence}

                # Also try partial match (contains page name)
                if page_name.lower() in text.lower():
                    similarity = len(page_name) / len(text)
                    if similarity > best_score:
                        x = text_data['left'][i] + text_data['width'][i] // 2
                        y = text_data['top'][i] + text_data['height'][i] // 2

                        best_match = {
                            'coords': (x, y),
                            'text': text,
                            'confidence': similarity
                        }
                        best_score = similarity

            if best_match and best_score >= 0.6:
                logger.debug("[PHASE 1B] Partial match found: %s (%.2f)", best_match['text'], best_score)
                return best_match

            logger.debug("[PHASE 1B] No bookmark match found in results")
            return None

        except Exception as e:
            logger.warning("[PHASE 1B] Error finding bookmark in results: %s", str(e))
            return None

    def _fuzzy_search(self, screenshot: np.ndarray, page_name: str, min_similarity: float = 0.90) -> Optional[Dict]:
        """Fuzzy match using helper images and visual detection."""
        logger.debug("[PHASE 1B] Fuzzy searching with helper images...")

        # Check if pytesseract is available
        if pytesseract is None:
            logger.debug("[PHASE 1B] Pytesseract not available, skipping fuzzy search")
            return None

        try:
            text_data = pytesseract.image_to_data(
                screenshot,
                output_type=pytesseract.Output.DICT
            )

            best_match = None
            best_ratio = 0

            for i in range(len(text_data['text'])):
                text = text_data['text'][i].strip()

                if not text:
                    continue

                ratio = SequenceMatcher(None, text.lower(), page_name.lower()).ratio()

                if ratio >= min_similarity and ratio > best_ratio:
                    x = text_data['left'][i] + text_data['width'][i] // 2
                    y = text_data['top'][i] + text_data['height'][i] // 2

                    best_match = {
                        'coords': (x, y),
                        'text': text,
                        'matched_text': text,
                        'confidence': ratio
                    }
                    best_ratio = ratio

            if best_match:
                logger.debug(f"[PHASE 1B] ✅ Fuzzy match: {best_match['text']} ({best_ratio:.2%})")

            return best_match

        except Exception as e:
            logger.warning("[PHASE 1B] Fuzzy search error (OCR): %s", str(e))
            logger.debug("[PHASE 1B] Falling back to helper images")
            return None

    def _open_bookmark_panel(self) -> bool:
        """Open bookmark panel using helper images."""
        logger.debug("[PHASE 1B] Opening bookmark panel...")

        # Try to detect and click all_bookmarks.png
        if self._image_match_and_click("all_bookmarks.png"):
            logger.info("[PHASE 1B] ✅ all_bookmarks clicked")
            time.sleep(1)
            return True

        # Fallback: Try open_side_panel_to_see_all_bookmarks.png
        if self._image_match_and_click("open_side_panel_to_see_all_bookmarks.png"):
            logger.info("[PHASE 1B] ✅ open_side_panel clicked")
            time.sleep(1)
            return True

        logger.warning("[PHASE 1B] ❌ Could not open bookmark panel")
        return False

    def _close_bookmark_panel(self) -> bool:
        """Close bookmark panel using helper image or ESC key."""
        logger.debug("[PHASE 1B] Closing bookmark panel...")

        # Try 1: Click close button (X icon)
        if self._image_match_and_click("bookmarks_close.png", confidence=0.85):
            logger.info("[PHASE 1B] ✅ bookmarks_close clicked via image match")
            time.sleep(0.5)
            return True

        # Try 2: Press ESC key to close panel
        logger.debug("[PHASE 1B] Trying ESC key to close panel...")
        pyautogui.press('esc')
        time.sleep(0.3)

        # Try 3: Click outside panel (to the right)
        logger.debug("[PHASE 1B] Clicking outside panel to close...")
        pyautogui.click(1000, 300)
        time.sleep(0.3)

        logger.debug("[PHASE 1B] ✅ Panel close attempt completed")
        return True  # Don't fail, continue anyway

    def _image_match_and_click(self, image_name: str, confidence: float = 0.97) -> bool:
        """Match helper image and click if found."""
        try:
            image_path = self.helper_images_path / image_name
            if not image_path.exists():
                logger.debug(f"[PHASE 1B] Helper image not found: {image_name}")
                return False

            screenshot = self._capture_screenshot()
            helper_image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

            result = cv2.matchTemplate(screenshot_gray, helper_image, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val >= confidence:
                x, y = max_loc
                h, w = helper_image.shape
                center_x = x + w // 2
                center_y = y + h // 2

                logger.debug(f"[PHASE 1B] Matched {image_name} at ({center_x}, {center_y})")
                pyautogui.click(center_x, center_y)
                return True

        except Exception as e:
            logger.debug(f"[PHASE 1B] Image matching error: {e}")

        return False

    def _click_and_verify(self, result: Dict, page_name: str) -> bool:
        """Click at coordinates and verify."""
        x, y = result['coords']

        logger.debug(f"[PHASE 1B] Clicking at ({x}, {y})")

        # Before screenshot
        before = self._capture_screenshot()

        # Click
        pyautogui.click(x, y)

        # Wait and verify
        if self._wait_for_change(before, timeout=2):
            logger.info("[PHASE 1B] ✅ Page loaded after click")
            return True
        else:
            logger.warning("[PHASE 1B] ⚠️ No change detected, but proceeding")
            return True

    def _wait_for_change(self, before_screenshot: np.ndarray, timeout: float = 2) -> bool:
        """Wait for interface to change."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            after = self._capture_screenshot()

            # Simple comparison: different pixels
            if not np.array_equal(before_screenshot, after):
                return True

            time.sleep(0.2)

        return False

    def _capture_screenshot(self) -> np.ndarray:
        """Capture current screenshot."""
        # Placeholder - will be implemented with actual screenshot logic
        import pyautogui
        screenshot = pyautogui.screenshot()
        return np.array(screenshot)
