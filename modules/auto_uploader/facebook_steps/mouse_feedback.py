"""Provide human-like pauses with visible mouse movement."""

from __future__ import annotations

import logging
import math
import random
import time
from typing import Optional

try:
    import pyautogui
except ImportError:  # pragma: no cover - handled gracefully at runtime
    pyautogui = None  # type: ignore


def _move_in_circle(center_x: int, center_y: int, radius: int, steps: int, speed: float) -> None:
    """Move the mouse cursor in a single circular loop."""
    if not pyautogui:
        return

    for index in range(steps):
        angle = (2 * math.pi * index) / steps
        x_pos = center_x + int(radius * math.cos(angle))
        y_pos = center_y + int(radius * math.sin(angle))

        try:
            pyautogui.moveTo(x_pos, y_pos, duration=speed)
        except Exception as exc:  # pragma: no cover - GUI interaction
            logging.debug("Mouse movement failed: %s", exc)
            break


def human_delay(seconds: int, status: Optional[str] = None) -> None:
    """
    Pause automation while moving the mouse in gentle random circles.

    Args:
        seconds: Duration of the pause.
        status: Optional status message to log.
    """
    if status:
        logging.info(status)

    if seconds <= 0:
        return

    if not pyautogui:
        time.sleep(seconds)
        return

    screen_width, screen_height = pyautogui.size()
    end_time = time.time() + seconds

    while time.time() < end_time:
        remaining = end_time - time.time()

        radius = random.randint(40, 120)
        max_x = max(radius + 10, screen_width - radius - 10)
        max_y = max(radius + 10, screen_height - radius - 10)
        center_x = random.randint(radius + 10, max_x)
        center_y = random.randint(radius + 10, max_y)

        steps = random.randint(16, 32)
        speed = random.uniform(0.02, 0.06)

        loop_duration = steps * speed
        if loop_duration > remaining:
            speed = max(0.01, remaining / max(steps, 1))

        _move_in_circle(center_x, center_y, radius, steps, speed)
        time.sleep(random.uniform(0.05, 0.2))
