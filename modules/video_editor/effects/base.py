"""Common effect interfaces used by the integrated video editor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import numpy as np


@dataclass
class EffectResult:
    """Container describing how an effect modified a frame."""

    frame: np.ndarray
    label: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EffectBase:
    """Base class for preview effects."""

    name: str = "effect"

    def apply(self, frame: np.ndarray) -> EffectResult:
        """Apply the effect to the given frame."""
        raise NotImplementedError

    def reset(self) -> None:
        """Clear any internal state."""
        return

    def is_active(self) -> bool:
        """Return True if the effect is currently modifying frames."""
        return False

    def current_label(self) -> str | None:
        """Optional label to display in the preview badges."""
        return None
