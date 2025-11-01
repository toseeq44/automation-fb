"""
Image Matcher - Template matching for UI element detection
Uses structural similarity (SSIM) for reliable template matching
"""

import logging
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, List

try:
    import pyautogui
    from PIL import Image
    import numpy as np
    from skimage.metrics import structural_similarity as ssim
    MATCHER_AVAILABLE = True
except ImportError:
    MATCHER_AVAILABLE = False
    logging.warning("Image matching tools not available. Install with: pip install pillow scikit-image")


class ImageMatcher:
    """Match templates in screenshots using structural similarity"""

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
        self.threshold = 0.85  # SSIM threshold for match (0-1)
        self.templates = {}

        logging.debug(f"ImageMatcher using template directory: {self.template_dir}")

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
            logging.warning(f"Template not found: {template_path}")
            return None

        try:
            template = Image.open(template_path).convert('RGB')
            template_array = np.array(template)
            self.templates[template_name] = template_array
            logging.debug(f"Loaded template: {template_name} ({template_array.shape})")
            return template_array
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
        Find template in screenshot using structural similarity

        Args:
            screenshot: NumPy array of screenshot
            template: NumPy array of template
            threshold: SSIM threshold (default: self.threshold)

        Returns:
            Tuple of (x, y, similarity_score) or None if not found
        """
        if threshold is None:
            threshold = self.threshold

        try:
            # Convert to grayscale for SSIM calculation
            gray_screenshot = self._to_grayscale(screenshot)
            gray_template = self._to_grayscale(template)

            # Ensure template is smaller than screenshot
            if (gray_template.shape[0] > gray_screenshot.shape[0] or
                gray_template.shape[1] > gray_screenshot.shape[1]):
                logging.debug("Template larger than screenshot")
                return None

            # Use OpenCV-like sliding window with SSIM
            best_match = None
            best_score = -1

            template_h, template_w = gray_template.shape
            screenshot_h, screenshot_w = gray_screenshot.shape

            # Search with step size (faster but less accurate)
            step = max(1, min(template_h, template_w) // 4)

            for y in range(0, screenshot_h - template_h, step):
                for x in range(0, screenshot_w - template_w, step):
                    window = gray_screenshot[y:y+template_h, x:x+template_w]

                    # Calculate SSIM
                    score = ssim(window, gray_template, data_range=255)

                    if score > best_score:
                        best_score = score
                        best_match = (x, y)

            if best_match and best_score >= threshold:
                x, y = best_match
                # Return center of template
                center_x = x + template_w // 2
                center_y = y + template_h // 2
                logging.debug(f"Found template match at ({center_x}, {center_y}) with score {best_score:.2f}")
                return (center_x, center_y, best_score)

            logging.debug(f"No template match found (best score: {best_score:.2f}, threshold: {threshold})")
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
            # Check for logged-in indicators
            profile_template = self.load_template('current_profile_cordinates')
            if profile_template is not None:
                result = self.find_template(screenshot, profile_template, threshold=0.80)
                if result:
                    logging.info("✓ Detected logged-in status (profile icon visible)")
                    return 'LOGGED_IN'

            # Check for not-logged-in indicators (login form)
            login_template = self.load_template('new_login_cordinates')
            if login_template is not None:
                result = self.find_template(screenshot, login_template, threshold=0.80)
                if result:
                    logging.info("✓ Detected not-logged-in status (login form visible)")
                    return 'NOT_LOGGED_IN'

            logging.warning("⚠ Could not determine login status")
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
                logging.debug(f"Found {element_name} at ({x}, {y})")
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

    def _to_grayscale(self, image_array: np.ndarray) -> np.ndarray:
        """
        Convert RGB image to grayscale

        Args:
            image_array: RGB image array

        Returns:
            Grayscale image array
        """
        if len(image_array.shape) == 2:
            return image_array  # Already grayscale

        # Convert RGB to grayscale using standard formula
        r, g, b = image_array[:,:,0], image_array[:,:,1], image_array[:,:,2]
        gray = 0.299 * r + 0.587 * g + 0.114 * b
        return gray.astype(np.uint8)

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
