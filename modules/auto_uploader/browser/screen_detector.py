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
    """Detects UI elements using image recognition with multi-scale and multi-template support."""

    def __init__(
        self,
        images_dir: Optional[Path] = None,
        confidence: float = 0.75,
        min_confidence: float = 0.65,
        enable_multiscale: bool = True,
        scales: Optional[list] = None
    ):
        """
        Initialize screen detector with enhanced detection capabilities.

        Args:
            images_dir: Directory containing reference images
            confidence: Ideal confidence threshold for matching (0.0 to 1.0)
            min_confidence: Minimum acceptable confidence (for fallback)
            enable_multiscale: Enable multi-scale template matching
            scales: Custom scale factors (default: [0.8, 0.9, 1.0, 1.1, 1.2])
        """
        if not CV2_AVAILABLE:
            raise ImportError("OpenCV and pyautogui are required for screen detection")

        self.images_dir = images_dir or Path(__file__).parent.parent / "helper_images"
        self.confidence = confidence
        self.min_confidence = min_confidence
        self.enable_multiscale = enable_multiscale
        self.scales = scales or [0.8, 0.9, 1.0, 1.1, 1.2]

        # Ensure images directory exists
        self.images_dir.mkdir(parents=True, exist_ok=True)

        # Cache for loaded templates
        self._template_cache: Dict[str, np.ndarray] = {}

        logging.debug(
            "ScreenDetector initialized - dir: %s, confidence: %.2f-%.2f, multiscale: %s",
            self.images_dir,
            self.min_confidence,
            self.confidence,
            self.enable_multiscale
        )

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

    def _match_template_multiscale(
        self,
        template_path: Path,
        screenshot: np.ndarray,
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> Dict[str, Any]:
        """
        Perform multi-scale template matching for better detection.

        Args:
            template_path: Path to template image
            screenshot: Screenshot image
            region: Optional search region

        Returns:
            Best match result across all scales
        """
        # Load template (use cache if available)
        template_key = str(template_path)
        if template_key in self._template_cache:
            template = self._template_cache[template_key]
        else:
            template = cv2.imread(str(template_path))
            if template is None:
                return {'found': False, 'position': None, 'confidence': 0.0}
            self._template_cache[template_key] = template

        best_match = None
        best_confidence = 0.0

        template_h, template_w = template.shape[:2]

        for scale in self.scales:
            # Skip scales that make template larger than screenshot
            scaled_w = int(template_w * scale)
            scaled_h = int(template_h * scale)

            if scaled_w > screenshot.shape[1] or scaled_h > screenshot.shape[0]:
                continue

            # Resize template
            scaled_template = cv2.resize(template, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)

            # Perform matching
            try:
                result = cv2.matchTemplate(screenshot, scaled_template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                # Update best match if this is better
                if max_val > best_confidence:
                    best_confidence = max_val
                    center_x = max_loc[0] + scaled_w // 2
                    center_y = max_loc[1] + scaled_h // 2

                    # Adjust for region if specified
                    if region:
                        center_x += region[0]
                        center_y += region[1]

                    best_match = {
                        'found': max_val >= self.min_confidence,
                        'position': (center_x, center_y),
                        'confidence': float(max_val),
                        'top_left': max_loc,
                        'size': (scaled_w, scaled_h),
                        'scale': scale
                    }

                    logging.debug(
                        "Scale %.2f: confidence=%.3f at (%d, %d)",
                        scale, max_val, center_x, center_y
                    )

            except Exception as e:
                logging.debug("Error matching at scale %.2f: %s", scale, e)
                continue

        if best_match and best_match['confidence'] >= self.min_confidence:
            logging.debug(
                "Best multiscale match: confidence=%.3f, scale=%.2f",
                best_match['confidence'],
                best_match.get('scale', 1.0)
            )
            return best_match
        else:
            return {'found': False, 'position': None, 'confidence': best_confidence}

    def _find_template_variants(self, base_name: str) -> list:
        """
        Find all template variants for a base name.

        For example, if base_name is "check_user_status", this will find:
        - check_user_status.png
        - check_user_status_v2.png
        - check_user_status_light.png
        etc.

        Args:
            base_name: Base template name (without .png extension)

        Returns:
            List of Path objects for found variants
        """
        # Remove .png if present
        if base_name.endswith('.png'):
            base_name = base_name[:-4]

        variants = []

        # Exact match
        exact_path = self.images_dir / f"{base_name}.png"
        if exact_path.exists():
            variants.append(exact_path)

        # Find numbered variants (v1, v2, v3, etc.)
        for i in range(1, 10):
            variant_path = self.images_dir / f"{base_name}_v{i}.png"
            if variant_path.exists():
                variants.append(variant_path)

        # Find theme variants
        for theme in ['light', 'dark', 'default']:
            theme_path = self.images_dir / f"{base_name}_{theme}.png"
            if theme_path.exists():
                variants.append(theme_path)

        logging.debug("Found %d variant(s) for '%s'", len(variants), base_name)
        return variants

    def detect_with_variants(
        self,
        template_name: str,
        region: Optional[Tuple[int, int, int, int]] = None,
        min_confidence_override: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Detect element using multiple template variants.

        Tries all available variants of a template and returns the best match.

        Args:
            template_name: Base template name
            region: Optional search region
            min_confidence_override: Override minimum confidence for this detection

        Returns:
            Best match result across all variants with additional metadata
        """
        variants = self._find_template_variants(template_name)

        if not variants:
            logging.warning("No template variants found for '%s'", template_name)
            return {'found': False, 'position': None, 'confidence': 0.0}

        best_result = {'found': False, 'confidence': 0.0}
        min_conf = min_confidence_override if min_confidence_override is not None else self.min_confidence

        for variant_path in variants:
            result = self._match_template(variant_path, region=region)

            if result.get('confidence', 0) > best_result.get('confidence', 0):
                best_result = result
                best_result['template_used'] = variant_path.name

            # If we found a good match, no need to try more variants
            if result.get('found') and result.get('confidence', 0) >= self.confidence:
                logging.debug("Strong match found with variant: %s", variant_path.name)
                break

        # Re-evaluate 'found' status with override confidence if provided
        if min_confidence_override is not None:
            best_result['found'] = best_result.get('confidence', 0) >= min_conf

        if best_result.get('found') or best_result.get('confidence', 0) >= min_conf:
            logging.debug(
                "Best variant match: %s (confidence: %.3f, threshold: %.2f)",
                best_result.get('template_used', 'unknown'),
                best_result.get('confidence', 0),
                min_conf
            )

        return best_result

    def _match_template(self, template_path: Path, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Internal method to perform template matching with enhancements.

        Now supports multi-scale matching if enabled.

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

            # Use multi-scale if enabled
            if self.enable_multiscale:
                return self._match_template_multiscale(template_path, screenshot, region)

            # Standard single-scale matching
            # Load template
            template = cv2.imread(str(template_path))
            if template is None:
                logging.error("Failed to load template image: %s", template_path)
                return {'found': False, 'position': None, 'confidence': 0.0}

            # Perform template matching
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # Check if match confidence exceeds threshold
            if max_val >= self.min_confidence:
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
                    'found': max_val >= self.confidence,  # Use ideal confidence for 'found' flag
                    'position': (center_x, center_y),
                    'confidence': float(max_val),
                    'top_left': max_loc,
                    'size': (template_w, template_h)
                }
            else:
                logging.debug("Template match below threshold: %.2f < %.2f", max_val, self.min_confidence)
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
