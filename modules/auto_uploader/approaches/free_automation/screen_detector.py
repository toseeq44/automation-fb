"""
Screen Detector
===============
Uses OpenCV image recognition to detect UI elements on screen.

This module provides intelligent detection for:
- User login status
- Logout dropdown menus
- Browser close/exit popups
- Login page elements
- Various UI states
"""

import logging
import time
from pathlib import Path
from typing import Optional, Dict, Tuple, Any
import numpy as np

try:
    import cv2
    import pyautogui
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("OpenCV or pyautogui not available. Screen detection will not work.")


class ScreenDetector:
    """Detects UI elements using image recognition."""

    def __init__(self, images_dir: Optional[Path] = None, confidence: float = 0.8):
        """
        Initialize screen detector.

        Args:
            images_dir: Directory containing reference images
            confidence: Minimum confidence threshold for matching (0.0 to 1.0)
        """
        if not CV2_AVAILABLE:
            raise ImportError("OpenCV and pyautogui are required for screen detection")

        self.images_dir = images_dir or Path(__file__).parent.parent / "helper_images"
        self.confidence = confidence

        # Ensure images directory exists
        self.images_dir.mkdir(parents=True, exist_ok=True)

        logging.debug("ScreenDetector initialized with images_dir: %s", self.images_dir)

    def detect_user_status(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Detect if user is logged in by matching check_user_status.png.

        Args:
            region: Optional (x, y, width, height) to search within

        Returns:
            Dictionary with:
                - logged_in (bool): True if user detected as logged in
                - position (tuple): (x, y) coordinates of match if found
                - confidence (float): Match confidence score

        Example:
            >>> detector = ScreenDetector()
            >>> result = detector.detect_user_status()
            >>> if result['logged_in']:
            >>>     print(f"User logged in at {result['position']}")
        """
        logging.info("Detecting user login status...")

        template_path = self.images_dir / "check_user_status.png"
        result = self._match_template(template_path, region=region)

        if result['found']:
            logging.info("User detected as LOGGED IN (confidence: %.2f)", result['confidence'])
            return {
                'logged_in': True,
                'position': result['position'],
                'confidence': result['confidence']
            }
        else:
            logging.info("User detected as LOGGED OUT")
            return {
                'logged_in': False,
                'position': None,
                'confidence': 0.0
            }

    def detect_logout_dropdown(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Detect logout dropdown menu by matching user_status_dropdown.png.

        Args:
            region: Optional search region

        Returns:
            Dictionary with detection results
        """
        logging.info("Detecting logout dropdown...")

        template_path = self.images_dir / "user_status_dropdown.png"
        result = self._match_template(template_path, region=region)

        if result['found']:
            logging.info("Logout dropdown DETECTED at %s", result['position'])
        else:
            logging.debug("Logout dropdown NOT detected")

        payload = {
            'found': result['found'],
            'position': result['position'],
            'confidence': result['confidence'],
        }
        if 'top_left' in result:
            payload['top_left'] = result['top_left']
        if 'size' in result:
            payload['size'] = result['size']
        return payload

    def detect_browser_close_popup(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Detect browser close/exit popup by matching browser_close_popup.png.

        This detects the "Safe and Exit" or similar browser close confirmation dialogs.

        Args:
            region: Optional search region

        Returns:
            Dictionary with detection results
        """
        logging.info("Detecting browser close popup...")

        template_path = self.images_dir / "browser_close_popup.png"
        result = self._match_template(template_path, region=region)

        if result['found']:
            logging.info("Browser close popup DETECTED at %s", result['position'])
        else:
            logging.debug("Browser close popup NOT detected")

        payload = {
            'found': result['found'],
            'position': result['position'],
            'confidence': result['confidence'],
        }
        if 'top_left' in result:
            payload['top_left'] = result['top_left']
        if 'size' in result:
            payload['size'] = result['size']
        return payload

    def detect_login_page(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Detect Facebook login page elements.

        Args:
            region: Optional search region

        Returns:
            Dictionary with detection results
        """
        logging.info("Detecting login page...")

        # Try to detect common login page elements
        # User can add login_page.png to helper_images for specific detection
        template_path = self.images_dir / "login_page.png"

        if not template_path.exists():
            logging.debug("login_page.png not found, skipping specific detection")
            return {'found': False, 'position': None, 'confidence': 0.0}

        result = self._match_template(template_path, region=region)

        if result['found']:
            logging.info("Login page DETECTED at %s", result['position'])
        else:
            logging.debug("Login page NOT detected")

        return {
            'found': result['found'],
            'position': result['position'],
            'confidence': result['confidence']
        }

    def detect_custom_element(self, template_name: str, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Detect a custom UI element by template image name.

        Args:
            template_name: Name of template image file (with or without .png extension)
            region: Optional search region

        Returns:
            Dictionary with detection results

        Example:
            >>> detector = ScreenDetector()
            >>> result = detector.detect_custom_element("upload_button.png")
        """
        logging.info("Detecting custom element: %s", template_name)

        # Add .png extension if not present
        if not template_name.endswith('.png'):
            template_name += '.png'

        template_path = self.images_dir / template_name
        result = self._match_template(template_path, region=region)

        return {
            'found': result['found'],
            'position': result['position'],
            'confidence': result['confidence']
        }

    def wait_for_element(self, template_name: str, timeout: int = 10,
                        region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Wait for an element to appear on screen.

        Args:
            template_name: Template image name
            timeout: Maximum wait time in seconds
            region: Optional search region

        Returns:
            Dictionary with detection results
        """
        logging.info("Waiting for element '%s' (timeout: %ds)", template_name, timeout)

        start_time = time.time()
        last_result = None

        while time.time() - start_time < timeout:
            result = self.detect_custom_element(template_name, region=region)
            last_result = result

            if result['found']:
                elapsed = time.time() - start_time
                logging.info("Element '%s' found after %.1fs", template_name, elapsed)
                return result

            time.sleep(0.5)  # Check every 0.5 seconds

        logging.warning("Element '%s' not found within %ds timeout", template_name, timeout)
        return last_result or {'found': False, 'position': None, 'confidence': 0.0}

    def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
        """
        Capture screenshot and convert to OpenCV format.

        Args:
            region: Optional (x, y, width, height) to capture specific region

        Returns:
            Screenshot as OpenCV BGR image array
        """
        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()

        # Convert PIL Image to OpenCV format (RGB -> BGR)
        screenshot_np = np.array(screenshot)
        screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)

        return screenshot_cv

    def _match_template(self, template_path: Path, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Internal method to perform template matching.

        Args:
            template_path: Path to template image
            region: Optional search region

        Returns:
            Dictionary with match results
        """
        if not template_path.exists():
            logging.warning("Template image not found: %s", template_path)
            return {'found': False, 'position': None, 'confidence': 0.0}

        try:
            # Capture screenshot
            screenshot = self.capture_screen(region=region)

            # Load template
            template = cv2.imread(str(template_path))
            if template is None:
                logging.error("Failed to load template image: %s", template_path)
                return {'found': False, 'position': None, 'confidence': 0.0}

            # Perform template matching
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # Check if match confidence exceeds threshold
            if max_val >= self.confidence:
                # Get center of matched region
                template_h, template_w = template.shape[:2]
                center_x = max_loc[0] + template_w // 2
                center_y = max_loc[1] + template_h // 2

                # If region was specified, adjust coordinates
                if region:
                    center_x += region[0]
                    center_y += region[1]

                logging.debug("Template match found: position=(%d, %d), confidence=%.2f",
                            center_x, center_y, max_val)

                return {
                    'found': True,
                    'position': (center_x, center_y),
                    'confidence': float(max_val),
                    'top_left': max_loc,
                    'size': (template_w, template_h)
                }
            else:
                logging.debug("Template match below threshold: %.2f < %.2f", max_val, self.confidence)
                return {'found': False, 'position': None, 'confidence': float(max_val)}

        except Exception as e:
            logging.error("Error during template matching: %s", e, exc_info=True)
            return {'found': False, 'position': None, 'confidence': 0.0}

    def save_screenshot(self, filename: str, region: Optional[Tuple[int, int, int, int]] = None) -> Path:
        """
        Save a screenshot for debugging or creating new templates.

        Args:
            filename: Output filename (will be saved to images_dir)
            region: Optional region to capture

        Returns:
            Path to saved screenshot
        """
        screenshot = self.capture_screen(region=region)
        output_path = self.images_dir / filename

        cv2.imwrite(str(output_path), screenshot)
        logging.info("Screenshot saved to: %s", output_path)

        return output_path
