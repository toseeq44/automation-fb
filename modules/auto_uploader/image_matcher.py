"""
Image Matcher - Simple and reliable template matching for UI detection
Uses OpenCV for fast, robust template matching
"""

import logging
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, List

try:
    import pyautogui
    from PIL import Image
    import numpy as np
    MATCHER_AVAILABLE = True
except ImportError:
    MATCHER_AVAILABLE = False
    logging.warning("Image matching tools not available. Install with: pip install pillow pyautogui")

# Try to import OpenCV for template matching
try:
    import cv2
    OPENCV_AVAILABLE = True
    logging.debug("OpenCV available for template matching")
except ImportError:
    OPENCV_AVAILABLE = False
    logging.warning("OpenCV not available. Install with: pip install opencv-python")


class ImageMatcher:
    """Match templates in screenshots using OpenCV template matching"""

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize image matcher

        Args:
            template_dir: Directory containing template images
        """
        if template_dir is None:
            # Check both locations for backward compatibility
            helper_dir = Path(__file__).parent / "helper_images"
            templates_dir = Path(__file__).parent / "data" / "templates"

            # Prefer helper_images if it exists
            if helper_dir.exists():
                template_dir = helper_dir
            else:
                template_dir = templates_dir

        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(parents=True, exist_ok=True)
        self.threshold = 0.70  # Matching threshold (0-1) - lower = more forgiving
        self.templates = {}  # Cache loaded templates

        logging.debug(f"ImageMatcher using template directory: {self.template_dir}")
        logging.debug(f"OpenCV available: {OPENCV_AVAILABLE}")

    def load_template(self, template_name: str) -> Optional[np.ndarray]:
        """
        Load and cache template image

        Args:
            template_name: Name of template file (without .png)

        Returns:
            NumPy array of template or None if not found
        """
        if template_name in self.templates:
            return self.templates[template_name]

        template_path = self.template_dir / f"{template_name}.png"

        if not template_path.exists():
            logging.debug(f"Template not found: {template_path}")
            return None

        try:
            if OPENCV_AVAILABLE:
                # Use OpenCV to load (better for matching)
                template = cv2.imread(str(template_path))
                if template is None:
                    logging.warning(f"Failed to load template with OpenCV: {template_name}")
                    return None
                # Convert BGR to RGB
                template = cv2.cvtColor(template, cv2.COLOR_BGR2RGB)
            else:
                # Fallback to PIL
                template = Image.open(template_path).convert('RGB')
                template = np.array(template)

            self.templates[template_name] = template
            logging.debug(f"Loaded template: {template_name} (shape: {template.shape})")
            return template

        except Exception as e:
            logging.error(f"Failed to load template {template_name}: {e}")
            return None

    def take_screenshot(self) -> Optional[np.ndarray]:
        """
        Take current screenshot

        Returns:
            NumPy array of screenshot or None if failed
        """
        try:
            screenshot = pyautogui.screenshot()
            screenshot_array = np.array(screenshot.convert('RGB'))
            return screenshot_array
        except Exception as e:
            logging.error(f"Failed to take screenshot: {e}")
            return None

    def find_template(self, screenshot: np.ndarray, template: np.ndarray,
                     threshold: Optional[float] = None) -> Optional[Tuple[int, int, float]]:
        """
        Find template in screenshot using OpenCV template matching

        Args:
            screenshot: NumPy array of screenshot (RGB)
            template: NumPy array of template (RGB)
            threshold: Matching threshold (default: self.threshold)

        Returns:
            Tuple of (x, y, match_score) or None if not found
        """
        if threshold is None:
            threshold = self.threshold

        try:
            if not OPENCV_AVAILABLE:
                logging.warning("OpenCV not available, cannot do template matching")
                return None

            # Convert to grayscale for matching (faster and more reliable)
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
            gray_template = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)

            # Check dimensions
            if (gray_template.shape[0] > gray_screenshot.shape[0] or
                gray_template.shape[1] > gray_screenshot.shape[1]):
                logging.debug("Template larger than screenshot")
                return None

            # Use TM_CCOEFF_NORMED for correlation (best for this use case)
            result = cv2.matchTemplate(gray_screenshot, gray_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # max_val is the match score (0-1)
            match_score = float(max_val)

            if match_score >= threshold:
                x, y = max_loc
                # Return center of matched template
                center_x = x + gray_template.shape[1] // 2
                center_y = y + gray_template.shape[0] // 2

                logging.debug(f"Found template at ({center_x}, {center_y}) with score {match_score:.2f}")
                return (center_x, center_y, match_score)

            logging.debug(f"Template not found (best score: {match_score:.2f}, threshold: {threshold})")
            return None

        except Exception as e:
            logging.error(f"Error finding template: {e}")
            return None

    def detect_login_status(self, screenshot: Optional[np.ndarray] = None) -> str:
        """
        Determine if user is logged in or not based on UI elements

        Args:
            screenshot: NumPy array of screenshot (takes new one if None)

        Returns:
            'LOGGED_IN', 'NOT_LOGGED_IN', or 'UNCLEAR'
        """
        if screenshot is None:
            screenshot = self.take_screenshot()
            if screenshot is None:
                return 'UNCLEAR'

        try:
            # Check for logged-in indicators (profile icon)
            profile_template = self.load_template('current_profile_cordinates')
            if profile_template is not None:
                result = self.find_template(screenshot, profile_template, threshold=0.65)
                if result:
                    logging.info("✓ Detected logged-in status (profile icon visible)")
                    return 'LOGGED_IN'

            # Check for not-logged-in indicators (login form)
            login_template = self.load_template('new_login_cordinates')
            if login_template is not None:
                result = self.find_template(screenshot, login_template, threshold=0.65)
                if result:
                    logging.info("✓ Detected not-logged-in status (login form visible)")
                    return 'NOT_LOGGED_IN'

            logging.warning("⚠ Could not determine login status (no matching templates)")
            return 'UNCLEAR'

        except Exception as e:
            logging.error(f"Error detecting login status: {e}")
            return 'UNCLEAR'

    def find_ui_element(self, element_name: str, screenshot: Optional[np.ndarray] = None) -> Optional[Tuple[int, int]]:
        """
        Find UI element coordinates in screenshot

        Args:
            element_name: Template name of UI element
            screenshot: NumPy array of screenshot (takes new one if None)

        Returns:
            Tuple of (x, y) coordinates or None if not found
        """
        if screenshot is None:
            screenshot = self.take_screenshot()
            if screenshot is None:
                return None

        try:
            template = self.load_template(element_name)
            if template is None:
                return None

            result = self.find_template(screenshot, template)
            if result:
                x, y, score = result
                logging.debug(f"Found {element_name} at ({x}, {y}) with score {score:.2f}")
                return (x, y)

            return None

        except Exception as e:
            logging.error(f"Error finding UI element {element_name}: {e}")
            return None

    def find_multiple_elements(self, element_names: List[str],
                              screenshot: Optional[np.ndarray] = None) -> Dict[str, Optional[Tuple[int, int]]]:
        """
        Find multiple UI elements in screenshot

        Args:
            element_names: List of template names
            screenshot: NumPy array of screenshot (takes new one if None)

        Returns:
            Dictionary mapping element names to (x, y) coordinates
        """
        if screenshot is None:
            screenshot = self.take_screenshot()
            if screenshot is None:
                return {name: None for name in element_names}

        results = {}
        for element_name in element_names:
            results[element_name] = self.find_ui_element(element_name, screenshot)

        return results

    def save_screenshot(self, filename: str = "debug") -> Optional[Path]:
        """
        Save current screenshot for debugging

        Args:
            filename: Name for debug screenshot

        Returns:
            Path to saved screenshot
        """
        try:
            screenshot = self.take_screenshot()
            if screenshot is None:
                return None

            debug_dir = self.template_dir.parent / "debug_screenshots"
            debug_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time())
            filepath = debug_dir / f"{filename}_{timestamp}.png"

            image = Image.fromarray(screenshot.astype('uint8'), 'RGB')
            image.save(filepath)
            logging.debug(f"Saved debug screenshot: {filepath}")
            return filepath

        except Exception as e:
            logging.error(f"Failed to save debug screenshot: {e}")
            return None
