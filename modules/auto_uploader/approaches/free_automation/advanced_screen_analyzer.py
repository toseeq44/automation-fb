"""
Advanced Screen Analyzer
========================

Provides heuristic-driven screenshot analysis that can detect common layout
patterns without relying exclusively on template images.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - optional dependency
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

from PIL import Image


@dataclass
class AnalysisResult:
    page_type: str
    confidence: float
    details: Dict[str, object]


class AdvancedScreenAnalyzer:
    """Composite heuristics for understanding screenshot content."""

    def __init__(self) -> None:
        self.available = cv2 is not None and np is not None

    # ------------------------------------------------------------------ public API
    def detect_page_type(self, screenshot: Optional[object]) -> AnalysisResult:
        if not self.available:
            return AnalysisResult("unknown", 0.0, {"reason": "opencv-unavailable"})

        array = self._to_bgr_array(screenshot)
        if array is None:
            return AnalysisResult("unknown", 0.0, {"reason": "invalid-image"})

        text_density = self._text_density(array)
        color_profile = self._color_profile(array)
        layout_votes = self._layout_votes(array)

        votes = {"login_page": 0.0, "feed_page": 0.0, "profile_page": 0.0, "settings_page": 0.0}

        # Text density heuristics
        if text_density < 0.15:
            votes["login_page"] += 0.6
        elif text_density < 0.30:
            votes["feed_page"] += 0.4
            votes["profile_page"] += 0.2
        else:
            votes["settings_page"] += 0.5

        # Color palette
        if color_profile.get("dominant_blue", 0) > 0.25:
            votes["profile_page"] += 0.3
        if color_profile.get("dominant_white", 0) > 0.45:
            votes["login_page"] += 0.3

        # Layout cues
        for page_type, weight in layout_votes.items():
            votes[page_type] += weight

        page_type = max(votes, key=votes.get)
        total_vote = sum(votes.values()) or 1.0
        confidence = votes[page_type] / total_vote

        details = {
            "text_density": text_density,
            "color_profile": color_profile,
            "votes": votes,
        }
        return AnalysisResult(page_type=page_type, confidence=confidence, details=details)

    def find_clickable_elements(self, screenshot: Optional[object]) -> List[Dict[str, object]]:
        if not self.available:
            return []

        array = self._to_bgr_array(screenshot)
        if array is None:
            return []

        elements: List[Dict[str, object]] = []
        for coords in self._detect_buttons_by_shape(array):
            elements.append({"type": "button", "coords": coords})
        for coords in self._detect_input_fields(array):
            elements.append({"type": "field", "coords": coords})
        for coords in self._detect_links_by_color(array):
            elements.append({"type": "link", "coords": coords})
        return elements

    def find_element(self, element_type: str, screenshot: Optional[object]) -> Optional[Tuple[int, int]]:
        elements = self.find_clickable_elements(screenshot)
        candidates = [element for element in elements if element_type in element["type"]]
        if not candidates:
            return None
        if element_type.endswith("_field"):
            # Prefer elements closer to center for fields
            height, width = self._image_dimensions(screenshot)
            center = (width / 2, height / 2)
            candidates.sort(key=lambda item: self._distance(item["coords"], center))
        return candidates[0]["coords"]

    def smart_element_click(self, element_type: str, screenshot: Optional[object]) -> Optional[Tuple[int, int]]:
        if not self.available:
            return None

        array = self._to_bgr_array(screenshot)
        if array is None:
            return None

        height, width = array.shape[:2]
        elements = self.find_clickable_elements(array)

        if "submit" in element_type:
            # Prioritise buttons in bottom centre
            bottom_center = [
                el
                for el in elements
                if el["type"] == "button"
                and el["coords"][1] > height * 0.55
                and width * 0.25 < el["coords"][0] < width * 0.75
            ]
            if bottom_center:
                return bottom_center[0]["coords"]

        for el in elements:
            if element_type in el["type"]:
                return el["coords"]
        return None

    # ------------------------------------------------------------------ heuristics
    def _text_density(self, array) -> float:
        gray = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text_pixels = np.sum(binary == 0)
        return float(text_pixels) / float(binary.size)

    def _color_profile(self, array) -> Dict[str, float]:
        hsv = cv2.cvtColor(array, cv2.COLOR_BGR2HSV)
        total_pixels = array.shape[0] * array.shape[1]
        hue, sat, val = cv2.split(hsv)

        blue_mask = cv2.inRange(hsv, (90, 50, 50), (130, 255, 255))
        white_mask = cv2.inRange(hsv, (0, 0, 200), (180, 40, 255))

        dominant_blue = float(np.count_nonzero(blue_mask)) / total_pixels
        dominant_white = float(np.count_nonzero(white_mask)) / total_pixels
        avg_brightness = float(np.mean(val)) / 255.0

        return {
            "dominant_blue": dominant_blue,
            "dominant_white": dominant_white,
            "avg_brightness": avg_brightness,
        }

    def _layout_votes(self, array) -> Dict[str, float]:
        height, width = array.shape[:2]
        center_region = array[int(height * 0.25) : int(height * 0.75), int(width * 0.25) : int(width * 0.75)]
        edges = cv2.Canny(center_region, 80, 160)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        form_like = 0
        repeating = 0
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if 120 < w < width * 0.8 and 30 < h < height * 0.3:
                form_like += 1
            if h > 40 and h < 120 and w > width * 0.7:
                repeating += 1

        votes: Dict[str, float] = {"login_page": 0.0, "feed_page": 0.0, "profile_page": 0.0, "settings_page": 0.0}
        if form_like >= 2:
            votes["login_page"] += 0.4
        if repeating >= 3:
            votes["feed_page"] += 0.4
        return votes

    def _detect_buttons_by_shape(self, array) -> List[Tuple[int, int]]:
        height, width = array.shape[:2]
        gray = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 80, 160)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        coords: List[Tuple[int, int]] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if 50 < w < 350 and 25 < h < 90:
                aspect = w / float(h)
                if 1.6 <= aspect <= 5.5:
                    coords.append((x + w // 2, y + h // 2))
        return coords

    def _detect_input_fields(self, array) -> List[Tuple[int, int]]:
        gray = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        coords: List[Tuple[int, int]] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if 150 < w < 500 and 30 < h < 80:
                coords.append((x + w // 2, y + h // 2))
        return coords

    def _detect_links_by_color(self, array) -> List[Tuple[int, int]]:
        hsv = cv2.cvtColor(array, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (90, 40, 70), (130, 255, 255))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        coords: List[Tuple[int, int]] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w * h > 80:
                coords.append((x + w // 2, y + h // 2))
        return coords

    # ------------------------------------------------------------------ utils
    def _to_bgr_array(self, screenshot: Optional[object]):
        if isinstance(screenshot, np.ndarray):
            if screenshot.ndim == 2:
                return cv2.cvtColor(screenshot, cv2.COLOR_GRAY2BGR)
            if screenshot.shape[2] == 3:
                return screenshot
            if screenshot.shape[2] == 4:
                return cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
        if isinstance(screenshot, Image.Image):
            return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        return None

    def _image_dimensions(self, screenshot: Optional[object]) -> Tuple[int, int]:
        if isinstance(screenshot, np.ndarray):
            height, width = screenshot.shape[:2]
            return height, width
        if isinstance(screenshot, Image.Image):
            width, height = screenshot.size
            return height, width
        return (0, 0)

    def _distance(self, point: Tuple[int, int], center: Tuple[float, float]) -> float:
        return ((point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2) ** 0.5

