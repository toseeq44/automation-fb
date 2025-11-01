"""Zoom effect implementation for the integrated video editor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .base import EffectBase, EffectResult


@dataclass
class ZoomState:
    factor: float = 1.0
    label: Optional[str] = None


class ZoomEffect(EffectBase):
    """Provides plain zooming (in/out) without blur blending."""

    name = "zoom"

    def __init__(self, cv2_module=None) -> None:
        self._cv2 = cv2_module
        self.state = ZoomState()

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    def update_from_percent(self, percent: float, *, mode: str = "preset", label: Optional[str] = None) -> None:
        factor = max(0.01, float(percent) / 100.0)
        if mode == "reset":
            factor = 1.0
        self.state = ZoomState(factor=factor, label=label or f"{percent:.0f}%")

    def reset(self) -> None:
        self.state = ZoomState()

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    def apply(self, frame: np.ndarray) -> EffectResult:
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            return EffectResult(frame)

        if not self.is_active() or self._cv2 is None:
            return EffectResult(frame)

        processed = self._apply_zoom(frame)
        return EffectResult(processed, label=self.state.label)

    def is_active(self) -> bool:
        return abs(self.state.factor - 1.0) > 1e-3

    def current_label(self) -> Optional[str]:
        return self.state.label if self.is_active() else None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _apply_zoom(self, frame: np.ndarray) -> np.ndarray:
        cv2 = self._cv2
        if cv2 is None:
            return frame

        working = np.ascontiguousarray(frame.copy())
        height, width = working.shape[:2]
        if height == 0 or width == 0:
            return working

        factor = self.state.factor

        if factor > 1.0:
            scaled_w = max(1, int(round(width * factor)))
            scaled_h = max(1, int(round(height * factor)))
            enlarged = cv2.resize(working, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
            x_offset = max(0, (scaled_w - width) // 2)
            y_offset = max(0, (scaled_h - height) // 2)
            return enlarged[y_offset:y_offset + height, x_offset:x_offset + width].copy()

        if factor < 1.0:
            canvas = np.zeros_like(frame)
            scaled_w = max(1, int(round(width * factor)))
            scaled_h = max(1, int(round(height * factor)))
            resized = cv2.resize(frame, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
            x_offset = max(0, (width - scaled_w) // 2)
            y_offset = max(0, (height - scaled_h) // 2)
            canvas[y_offset:y_offset + scaled_h, x_offset:x_offset + scaled_w] = resized
            return canvas

        return working
