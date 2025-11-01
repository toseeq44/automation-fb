"""Blur border effect for the AFTER preview."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .base import EffectBase, EffectResult


@dataclass
class BlurState:
    intensity: float = 0.0
    target: str = "all"
    label: Optional[str] = None


class BlurEffect(EffectBase):
    """Creates blurred borders behind the foreground content."""

    name = "blur"

    def __init__(self, cv2_module=None) -> None:
        self._cv2 = cv2_module
        self.state = BlurState()

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    def update_intensity(self, intensity: float, *, label: Optional[str] = None, target: Optional[str] = None) -> None:
        value = max(0.0, float(intensity))
        target = (target or "all").lower()
        if label is None:
            label = f"Blur {value:.0f}%"
        self.state = BlurState(intensity=value, target=target, label=label)

    def reset(self) -> None:
        self.state = BlurState()

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    def apply(self, frame: np.ndarray) -> EffectResult:
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            return EffectResult(frame)

        if not self.is_active() or self._cv2 is None:
            return EffectResult(frame)

        processed = self._apply_blur(frame)
        return EffectResult(processed, label=self.state.label)

    def is_active(self) -> bool:
        return self.state.intensity > 1e-3

    def current_label(self) -> Optional[str]:
        return self.state.label if self.is_active() else None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _apply_blur(self, frame: np.ndarray) -> np.ndarray:
        cv2 = self._cv2
        if cv2 is None:
            return frame

        working = np.ascontiguousarray(frame.copy())
        height, width = working.shape[:2]
        if height == 0 or width == 0:
            return working

        sigma = max(0.2, self.state.intensity * 0.35)
        background = cv2.GaussianBlur(working, (0, 0), sigmaX=sigma, sigmaY=sigma)

        overlay = background.copy()
        scale_x, scale_y = self._compute_scales()

        scaled_w = max(1, min(width, int(round(width * scale_x))))
        scaled_h = max(1, min(height, int(round(height * scale_y))))
        resized = cv2.resize(working, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)

        x_offset = max(0, (width - scaled_w) // 2)
        y_offset = max(0, (height - scaled_h) // 2)
        overlay[y_offset:y_offset + scaled_h, x_offset:x_offset + scaled_w] = resized

        return overlay

    def _compute_scales(self) -> tuple[float, float]:
        """Return X/Y scaling factors based on intensity and target."""
        intensity = max(0.0, min(self.state.intensity, 100.0))
        reduction = min(0.45, intensity * 0.006)  # up to ~45% shrink at 75% intensity
        scale_value = max(0.55, 1.0 - reduction)

        target = self.state.target
        if target in {"top_bottom", "vertical"}:
            return 1.0, scale_value
        if target in {"left_right", "horizontal"}:
            return scale_value, 1.0
        return scale_value, scale_value
