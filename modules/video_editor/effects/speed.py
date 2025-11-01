"""Playback speed effect metadata for preview badges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .base import EffectBase, EffectResult


def _format_speed_label(value: float) -> str:
    """Return a human readable speed label like '1.5x' without trailing zeros."""
    rounded = round(value, 2)
    if abs(rounded - round(rounded)) < 1e-6:
        return f"{int(round(rounded))}x"
    return f"{rounded:.2f}".rstrip("0").rstrip(".") + "x"


@dataclass
class SpeedState:
    factor: float = 1.0
    label: Optional[str] = None


class SpeedEffect(EffectBase):
    """Tracks playback speed so the AFTER preview can display an active badge."""

    name = "speed"

    def __init__(self) -> None:
        self.state = SpeedState()

    # ------------------------------------------------------------------ #
    # Configuration helpers
    # ------------------------------------------------------------------ #
    def update_factor(self, factor: float, *, label: Optional[str] = None) -> None:
        sanitized = max(0.1, min(float(factor), 8.0))
        if abs(sanitized - 1.0) < 1e-3:
            self.state = SpeedState()
            return
        display = label or _format_speed_label(sanitized)
        self.state = SpeedState(factor=sanitized, label=display)

    def reset(self) -> None:
        self.state = SpeedState()

    def factor(self) -> float:
        return self.state.factor

    # ------------------------------------------------------------------ #
    # EffectBase implementation
    # ------------------------------------------------------------------ #
    def apply(self, frame: np.ndarray) -> EffectResult:
        # Speed does not change pixels; we just propagate metadata/labels.
        label = self.current_label()
        metadata = {"speed_factor": self.state.factor}
        return EffectResult(frame, label=label, metadata=metadata)

    def is_active(self) -> bool:
        return abs(self.state.factor - 1.0) > 1e-3

    def current_label(self) -> Optional[str]:
        return self.state.label if self.is_active() else None
