"""Launch the target browser shortcut and wait for it to start."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .mouse_feedback import human_delay


class BrowserLaunchError(Exception):
    """Raised when the browser fails to start."""


def open_browser(shortcut_path: Path, warmup_seconds: int = 12) -> None:
    """
    Launch the browser using the located shortcut.

    Args:
        shortcut_path: The shortcut (.lnk) file to open.
        warmup_seconds: Seconds to wait with human-like feedback.

    Raises:
        BrowserLaunchError: If the shortcut is invalid or cannot be opened.
    """
    shortcut_path = Path(shortcut_path)

    if not shortcut_path.is_file():
        raise BrowserLaunchError(f"Shortcut not found: {shortcut_path}")

    logging.info("Opening browser shortcut: %s", shortcut_path)

    try:
        os.startfile(str(shortcut_path))
    except OSError as exc:
        raise BrowserLaunchError(f"Failed to launch browser from shortcut: {shortcut_path}") from exc

    human_delay(warmup_seconds, "Waiting for browser to launch...")
