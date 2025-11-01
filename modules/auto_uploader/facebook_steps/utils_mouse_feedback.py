"""Utility: Provide human-like pauses with visible mouse movement feedback."""

from __future__ import annotations

import logging
import math
import random
import time
from typing import Optional

try:
    import pyautogui
except ImportError:
    pyautogui = None  # type: ignore


def _move_mouse_in_circle(
    center_x: int,
    center_y: int,
    radius: int,
    steps: int,
    speed: float,
) -> None:
    """
    Move the mouse cursor in a smooth circular pattern.

    Args:
        center_x: X coordinate of circle center.
        center_y: Y coordinate of circle center.
        radius: Radius of the circle in pixels.
        steps: Number of steps to divide the circle into.
        speed: Duration (in seconds) for each step's movement.
    """
    if not pyautogui:
        return

    for index in range(steps):
        angle = (2 * math.pi * index) / steps
        x_pos = center_x + int(radius * math.cos(angle))
        y_pos = center_y + int(radius * math.sin(angle))

        try:
            pyautogui.moveTo(x_pos, y_pos, duration=speed)
        except Exception as exc:
            logging.debug("Mouse movement failed: %s", exc)
            break


def human_delay(seconds: int, status: Optional[str] = None) -> None:
    """
    Pause automation while moving the mouse in random circular patterns.

    This creates the appearance of human activity during wait periods,
    helping to avoid detection by monitoring systems.

    Args:
        seconds: Duration of the pause in seconds.
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

        # Random circle parameters
        radius = random.randint(40, 120)
        max_x = max(radius + 10, screen_width - radius - 10)
        max_y = max(radius + 10, screen_height - radius - 10)
        center_x = random.randint(radius + 10, max_x)
        center_y = random.randint(radius + 10, max_y)

        # Random motion parameters
        steps = random.randint(16, 32)
        speed = random.uniform(0.02, 0.06)

        # Adjust speed if time is running out
        loop_duration = steps * speed
        if loop_duration > remaining:
            speed = max(0.01, remaining / max(steps, 1))

        _move_mouse_in_circle(center_x, center_y, radius, steps, speed)
        time.sleep(random.uniform(0.05, 0.2))

    logging.info("Wait period completed")
