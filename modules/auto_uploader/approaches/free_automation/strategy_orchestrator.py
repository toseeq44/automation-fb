"""
Strategy Orchestrator
=====================

Combines multiple detection strategies (ML, advanced analysis, OCR, templates)
and exposes a unified API for the login workflow.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Sequence, Tuple

from PIL import Image

from .advanced_screen_analyzer import AdvancedScreenAnalyzer
from .health_checker import HealthChecker, CheckResult
from .ml_coordinate_predictor import CoordinatePredictor, Prediction
from .ocr_detector import OCRDetector, OCRMatch

try:
    import pyautogui
except ImportError:  # pragma: no cover - optional dependency
    pyautogui = None  # type: ignore[assignment]


ScreenshotProvider = Callable[[], Optional[Image.Image]]
TemplateFallback = Callable[[], Optional[Tuple[int, int]]]


@dataclass
class StrategyResult:
    coords: Optional[Tuple[int, int]]
    strategy: str
    confidence: float = 0.0
    metadata: Dict[str, object] = field(default_factory=dict)

    def succeeded(self) -> bool:
        return self.coords is not None


class StrategyOrchestrator:
    """Coordinates the different detection strategies."""

    def __init__(
        self,
        *,
        ocr: OCRDetector,
        health_checker: HealthChecker,
        predictor: CoordinatePredictor,
        analyzer: AdvancedScreenAnalyzer,
        screenshot_provider: Optional[ScreenshotProvider] = None,
    ) -> None:
        self.ocr = ocr
        self.health_checker = health_checker
        self.predictor = predictor
        self.analyzer = analyzer
        self.screenshot_provider = screenshot_provider

    # ------------------------------------------------------------------ lifecycle
    def run_preflight(self) -> Dict[str, CheckResult]:
        """Execute health checks before beginning a workflow."""
        results = self.health_checker.run_checks()
        summary = self.health_checker.summarize(results)
        logging.info("Health check summary: %s", summary)
        return results

    def capture_screenshot(self) -> Optional[Image.Image]:
        if self.screenshot_provider:
            try:
                shot = self.screenshot_provider()
                if shot is not None:
                    return shot
            except Exception as exc:  # pragma: no cover - guard
                logging.debug("Custom screenshot provider failed: %s", exc)

        if pyautogui is None:
            return None

        try:
            return pyautogui.screenshot()
        except Exception as exc:  # pragma: no cover - guard
            logging.debug("pyautogui.screenshot failed: %s", exc)
            return None

    # ------------------------------------------------------------------ strategy execution
    def locate_element(
        self,
        element_type: str,
        *,
        labels: Optional[Sequence[str]] = None,
        template_fallback: Optional[TemplateFallback] = None,
        use_analyzer: bool = True,
        screenshot: Optional[Image.Image] = None,
    ) -> StrategyResult:
        """Attempt to locate an element using every available strategy."""
        screenshot = screenshot or self.capture_screenshot()
        meta: Dict[str, object] = {}

        prediction = self._predict_with_model(element_type, screenshot)
        if prediction:
            logging.debug("ML predictor located %s at %s (confidence %.2f)", element_type, prediction.coords, prediction.confidence)
            return StrategyResult(
                coords=prediction.coords,
                strategy="ml_predictor",
                confidence=prediction.confidence,
                metadata={"samples": prediction.samples},
            )

        if use_analyzer:
            analyzer_coords = self.analyzer.smart_element_click(element_type, screenshot)
            if analyzer_coords:
                logging.debug("Advanced analyzer located %s at %s", element_type, analyzer_coords)
                return StrategyResult(
                    coords=analyzer_coords,
                    strategy="advanced_analyzer",
                    confidence=0.65,
                )

        if labels:
            ocr_match = self._locate_via_ocr(labels, screenshot)
            if ocr_match:
                logging.debug("OCR located %s via '%s' at %s", element_type, ocr_match.text, ocr_match.center)
                # For form fields we assume the input is slightly below the label.
                if element_type.endswith("_field"):
                    adjusted = (ocr_match.center[0], ocr_match.center[1] + 40)
                else:
                    adjusted = ocr_match.center
                return StrategyResult(
                    coords=adjusted,
                    strategy="ocr",
                    confidence=ocr_match.confidence / 100.0,
                    metadata={"label": ocr_match.text},
                )

        if template_fallback:
            coords = template_fallback()
            if coords:
                logging.debug("Template fallback located %s at %s", element_type, coords)
                return StrategyResult(coords=coords, strategy="template", confidence=0.5)

        return StrategyResult(coords=None, strategy="unresolved", confidence=0.0, metadata=meta)

    def record_success(self, element_type: str, coords: Tuple[int, int], screenshot: Optional[Image.Image]) -> None:
        """Record a successful element detection for future ML predictions."""
        try:
            self.predictor.record_click(element_type, coords, screenshot)
        except Exception as exc:  # pragma: no cover - guard
            logging.debug("Failed to record ML training data for %s: %s", element_type, exc)

    # ------------------------------------------------------------------ internals
    def _predict_with_model(
        self,
        element_type: str,
        screenshot: Optional[Image.Image],
    ) -> Optional[Prediction]:
        try:
            return self.predictor.predict_coords(element_type, screenshot)
        except Exception as exc:  # pragma: no cover - guard
            logging.debug("Coordinate predictor failed for %s: %s", element_type, exc)
            return None

    def _locate_via_ocr(
        self,
        labels: Sequence[str],
        screenshot: Optional[Image.Image],
    ) -> Optional[OCRMatch]:
        try:
            return self.ocr.find_any(labels, screenshot=screenshot)
        except Exception as exc:  # pragma: no cover
            logging.debug("OCR lookup failed for %s: %s", labels, exc)
            return None

