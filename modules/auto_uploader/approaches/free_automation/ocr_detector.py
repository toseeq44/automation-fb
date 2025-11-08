"""
OCR Detector
============

Provides lightweight OCR helpers built on top of pytesseract so the automation
layer can fall back to text-based element detection when template matching is
unreliable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

from PIL import Image

try:
    import pytesseract
    from pytesseract import Output
except ImportError:  # pragma: no cover - optional dependency
    pytesseract = None  # type: ignore[assignment]
    Output = None  # type: ignore[assignment]

try:
    import pyautogui
except ImportError:  # pragma: no cover - optional dependency
    pyautogui = None  # type: ignore[assignment]


@dataclass
class OCRMatch:
    """Represents a single OCR detection result."""

    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    center: Tuple[int, int]


class OCRDetector:
    """High-level OCR utilities with graceful degradation when dependencies are missing."""

    def __init__(self, languages: str = "eng"):
        self.languages = languages
        self.available = pytesseract is not None
        if not self.available:
            logging.debug("pytesseract not installed; OCR fallback disabled.")

    def capture_screenshot(self) -> Optional[Image.Image]:
        """Capture a screenshot using pyautogui if available."""
        if pyautogui is None:
            logging.debug("pyautogui not available; cannot capture screenshot for OCR.")
            return None

        try:
            return pyautogui.screenshot()
        except Exception as exc:  # pragma: no cover - defensive logging
            logging.debug("Screenshot capture for OCR failed: %s", exc)
            return None

    def _prepare_image(self, screenshot: Optional[object]) -> Optional[Image.Image]:
        if screenshot is None:
            return self.capture_screenshot()

        if isinstance(screenshot, Image.Image):
            return screenshot

        try:
            return Image.fromarray(screenshot)  # type: ignore[arg-type]
        except Exception as exc:
            logging.debug("Unsupported screenshot type for OCR (%s): %s", type(screenshot), exc)
            return None

    def extract_text(
        self,
        *,
        screenshot: Optional[object] = None,
        min_confidence: int = 0,
    ) -> Sequence[OCRMatch]:
        """Extract all text fragments that satisfy the confidence threshold."""
        if not self.available:
            return []

        image = self._prepare_image(screenshot)
        if image is None:
            return []

        try:
            data = pytesseract.image_to_data(
                image,
                output_type=Output.DICT,  # type: ignore[attr-defined]
                lang=self.languages,
            )
        except Exception as exc:  # pragma: no cover - OCR failure logged
            logging.debug("OCR processing failed: %s", exc)
            return []

        matches: list[OCRMatch] = []
        for idx, text in enumerate(data.get("text", [])):
            if not text.strip():
                continue

            confidence_str = data.get("conf", ["0"])[idx]
            try:
                confidence = float(confidence_str)
            except (TypeError, ValueError):
                confidence = 0.0

            if confidence < min_confidence:
                continue

            left = int(data.get("left", [0])[idx])
            top = int(data.get("top", [0])[idx])
            width = int(data.get("width", [0])[idx])
            height = int(data.get("height", [0])[idx])

            match = OCRMatch(
                text=text,
                confidence=confidence,
                bbox=(left, top, width, height),
                center=(left + width // 2, top + height // 2),
            )
            matches.append(match)

        return matches

    def find_text(
        self,
        query: str,
        *,
        screenshot: Optional[object] = None,
        case_sensitive: bool = False,
        allow_partial: bool = True,
        min_confidence: int = 60,
        alternatives: Optional[Iterable[str]] = None,
    ) -> Optional[OCRMatch]:
        """
        Locate the first occurrence of the supplied text.

        Args:
            query: Primary text to search for.
            screenshot: Optional screenshot object (PIL Image or numpy array).
            case_sensitive: Require case-sensitive match.
            allow_partial: Allow matches that merely contain the query.
            min_confidence: Minimum OCR confidence (0-100).
            alternatives: Additional strings to consider.
        """
        if not self.available:
            return None

        candidates = [query.strip()]
        if alternatives:
            candidates.extend(a.strip() for a in alternatives if a.strip())

        reference = candidates if case_sensitive else [c.lower() for c in candidates]

        for match in self.extract_text(screenshot=screenshot, min_confidence=min_confidence):
            text_value = match.text if case_sensitive else match.text.lower()

            for idx, expected in enumerate(reference):
                if not expected:
                    continue

                if text_value == expected or (allow_partial and expected in text_value):
                    return OCRMatch(
                        text=candidates[idx],
                        confidence=match.confidence,
                        bbox=match.bbox,
                        center=match.center,
                    )

        return None

    def find_any(
        self,
        queries: Sequence[str],
        *,
        screenshot: Optional[object] = None,
        min_confidence: int = 60,
    ) -> Optional[OCRMatch]:
        """Try multiple labels and return the first match."""
        for query in queries:
            match = self.find_text(
                query,
                screenshot=screenshot,
                min_confidence=min_confidence,
                allow_partial=True,
            )
            if match:
                return match
        return None

