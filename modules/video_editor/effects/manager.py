"""Effect manager orchestrating preview transformations."""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from .base import EffectBase, EffectResult
from .blur import BlurEffect
from .speed import SpeedEffect
from .zoom import ZoomEffect


class EffectManager:
    """Keeps track of active preview effects and applies them to frames."""

    def __init__(self, cv2_module=None) -> None:
        self._effects: Dict[str, EffectBase] = {}
        self._order: List[str] = []
        self._cv2 = cv2_module
        self._init_effects()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_zoom_percent(self, percent: float, *, mode: str = "preset", label: Optional[str] = None) -> None:
        zoom = self._effects.get("zoom")
        if zoom:
            zoom.update_from_percent(percent, mode=mode, label=label)

    def reset_zoom(self) -> None:
        zoom = self._effects.get("zoom")
        if zoom:
            zoom.reset()

    def set_blur_intensity(self, intensity: float, *, label: Optional[str] = None, target: Optional[str] = None) -> None:
        blur = self._effects.get("blur")
        if blur:
            blur.update_intensity(intensity, label=label, target=target)

    def reset_blur(self) -> None:
        blur = self._effects.get("blur")
        if blur:
            blur.reset()

    def set_speed_factor(self, factor: float, *, label: Optional[str] = None) -> None:
        speed = self._effects.get("speed")
        if speed:
            speed.update_factor(factor, label=label)

    def reset_speed(self) -> None:
        speed = self._effects.get("speed")
        if speed:
            speed.reset()

    def speed_factor(self) -> float:
        speed = self._effects.get("speed")
        if speed:
            return speed.factor()
        return 1.0

    def apply_after_effects(self, frame: np.ndarray) -> EffectResult:
        """Run frame through all after-preview effects."""
        current = frame
        active_labels: List[str] = []

        for name in self._order:
            effect = self._effects.get(name)
            if not effect:
                continue
            result = effect.apply(current)
            current = result.frame
            label = result.label or effect.current_label()
            if label:
                active_labels.append(label)

        metadata = {"labels": active_labels[:]}
        return EffectResult(current, label=", ".join(active_labels) if active_labels else None, metadata=metadata)

    def active_labels(self) -> List[str]:
        labels: List[str] = []
        for name in self._order:
            effect = self._effects.get(name)
            if not effect:
                continue
            label = effect.current_label()
            if label:
                labels.append(label)
        return labels

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _init_effects(self) -> None:
        self._effects["speed"] = SpeedEffect()
        self._effects["blur"] = BlurEffect(self._cv2)
        self._effects["zoom"] = ZoomEffect(self._cv2)
        self._order = ["speed", "zoom", "blur"]
