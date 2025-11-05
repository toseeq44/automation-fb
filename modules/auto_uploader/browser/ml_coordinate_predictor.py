"""
Coordinate Predictor
====================

Captures historic click coordinates and derives resolution-independent ratios
that can be used to predict UI element locations on future runs.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import pyautogui
except ImportError:  # pragma: no cover - optional dependency
    pyautogui = None  # type: ignore[assignment]

from PIL import Image


@dataclass
class Prediction:
    """Represents a coordinate prediction attempted by the model."""

    coords: Tuple[int, int]
    confidence: float
    samples: int


class CoordinatePredictor:
    """
    Lightweight coordinate predictor that learns from recorded clicks.

    Rather than depending on heavy ML frameworks, this class stores ratios of
    element positions relative to the screen resolution and uses those ratios
    to propose future coordinates.
    """

    def __init__(
        self,
        storage_path: Path,
        *,
        min_samples: int = 5,
        autosave_interval: int = 10,
        max_samples_per_element: int = 200,
    ) -> None:
        self.storage_path = Path(storage_path)
        self.min_samples = min_samples
        self.autosave_interval = max(1, autosave_interval)
        self.max_samples_per_element = max(10, max_samples_per_element)

        self._samples_recorded_since_save = 0
        self._dataset: Dict[str, List[Dict[str, float]]] = {}
        self._load_dataset()

    # ------------------------------------------------------------------ public API
    def record_click(self, element_type: str, coords: Tuple[int, int], screenshot: Optional[Image.Image]) -> None:
        """
        Record a click event for later learning.

        Args:
            element_type: Logical name for the UI element (e.g. 'email_field').
            coords: (x, y) coordinates that were clicked.
            screenshot: Screenshot captured near the time of the click.
        """
        width, height = self._determine_dimensions(screenshot)
        if width <= 0 or height <= 0:
            logging.debug("CoordinatePredictor skipped recording; screen dimensions unavailable.")
            return

        x_ratio = coords[0] / width
        y_ratio = coords[1] / height

        samples = self._dataset.setdefault(element_type, [])
        samples.append(
            {
                "x_ratio": x_ratio,
                "y_ratio": y_ratio,
                "timestamp": time.time(),
                "width": width,
                "height": height,
            }
        )

        # Drop oldest samples to keep dataset bounded.
        if len(samples) > self.max_samples_per_element:
            del samples[: len(samples) - self.max_samples_per_element]

        self._samples_recorded_since_save += 1
        if self._samples_recorded_since_save >= self.autosave_interval:
            self.save()

    def predict_coords(self, element_type: str, screenshot: Optional[Image.Image]) -> Optional[Prediction]:
        """Predict coordinates for the requested element type."""
        samples = self._dataset.get(element_type)
        if not samples or len(samples) < self.min_samples:
            return None

        width, height = self._determine_dimensions(screenshot)
        if width <= 0 or height <= 0:
            logging.debug("CoordinatePredictor prediction skipped; screen dimensions unavailable.")
            return None

        avg_x_ratio = sum(sample["x_ratio"] for sample in samples) / len(samples)
        avg_y_ratio = sum(sample["y_ratio"] for sample in samples) / len(samples)

        predicted_x = int(avg_x_ratio * width)
        predicted_y = int(avg_y_ratio * height)

        # Confidence grows with the logarithm of the sample count to avoid overconfidence.
        confidence = min(0.99, 0.5 + 0.1 * (len(samples) - self.min_samples))
        return Prediction(coords=(predicted_x, predicted_y), confidence=confidence, samples=len(samples))

    def get_statistics(self) -> Dict[str, Dict[str, float]]:
        """Return aggregate statistics for each tracked element."""
        stats: Dict[str, Dict[str, float]] = {}
        for element, samples in self._dataset.items():
            if not samples:
                continue
            count = len(samples)
            avg_x_ratio = sum(sample["x_ratio"] for sample in samples) / count
            avg_y_ratio = sum(sample["y_ratio"] for sample in samples) / count
            stats[element] = {
                "samples": count,
                "avg_x_ratio": avg_x_ratio,
                "avg_y_ratio": avg_y_ratio,
            }
        return stats

    def save(self) -> None:
        """Persist the dataset to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with self.storage_path.open("w", encoding="utf-8") as fh:
                json.dump(self._dataset, fh, indent=2)
            self._samples_recorded_since_save = 0
        except Exception as exc:  # pragma: no cover - logging only
            logging.warning("Failed to save coordinate predictor dataset: %s", exc)

    # ------------------------------------------------------------------ helpers
    def _load_dataset(self) -> None:
        if not self.storage_path.exists():
            return

        try:
            with self.storage_path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception as exc:
            logging.warning("Failed to load coordinate predictor dataset: %s", exc)
            return

        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, list):
                    self._dataset[key] = [
                        sample for sample in value if isinstance(sample, dict) and "x_ratio" in sample and "y_ratio" in sample
                    ]

    def _determine_dimensions(self, screenshot: Optional[Image.Image]) -> Tuple[int, int]:
        if isinstance(screenshot, Image.Image):
            width, height = screenshot.size
            if width and height:
                return width, height

        if pyautogui is not None:
            try:
                size = pyautogui.size()  # type: ignore[call-arg]
                return int(size.width), int(size.height)
            except Exception as exc:
                logging.debug("pyautogui.size() failed: %s", exc)

        return (0, 0)
