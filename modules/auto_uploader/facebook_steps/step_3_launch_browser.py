"""Step 3: Open browser shortcut and maximize the window."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Sequence

from .utils_mouse_feedback import human_delay

try:
    import pygetwindow as gw
except ImportError:
    gw = None  # type: ignore


class BrowserLaunchError(Exception):
    """Raised when browser cannot be launched or window cannot be found."""


# Known window title patterns for different browsers
_WINDOW_TITLE_PATTERNS = {
    "ix": ["ixBrowser", "IX Browser", "IX"],
    "gologin": ["GoLogin"],
    "incogniton": ["Incogniton"],
    "orbita": ["Orbita"],
    "chrome": ["Chrome", "Google Chrome"],
    "edge": ["Edge", "Microsoft Edge"],
    "firefox": ["Firefox", "Mozilla Firefox"],
}


def _get_window_title_candidates(browser_name: str) -> Sequence[str]:
    """
    Generate list of possible window title patterns for the browser.

    Args:
        browser_name: Name of the browser.

    Returns:
        List of window title patterns to search for.
    """
    browser_key = browser_name.strip().lower()
    titles: List[str] = []

    # Add known patterns for this browser
    titles.extend(_WINDOW_TITLE_PATTERNS.get(browser_key, []))

    # Add generic patterns
    if browser_name not in titles:
        titles.append(browser_name)
    if browser_key not in titles:
        titles.append(browser_key)

    return [t for t in titles if t]


def open_shortcut(shortcut_path: Path, wait_seconds: int = 12) -> None:
    """
    Launch the browser using the shortcut file.

    Args:
        shortcut_path: Path to the .lnk shortcut file.
        wait_seconds: Seconds to wait for browser to launch.

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
        raise BrowserLaunchError(f"Failed to launch browser: {exc}") from exc

    human_delay(wait_seconds, f"Waiting {wait_seconds}s for browser to launch...")


def maximize_window(browser_name: str, max_retries: int = 3, retry_wait_seconds: int = 4) -> None:
    """
    Find and maximize the browser window.

    Args:
        browser_name: Name of the browser to find.
        max_retries: Number of attempts to find the window.
        retry_wait_seconds: Seconds to wait between retry attempts.

    Raises:
        BrowserLaunchError: If the window cannot be found or maximized.
    """
    if gw is None:
        raise BrowserLaunchError("pygetwindow is required to manage windows")

    candidates = _get_window_title_candidates(browser_name)
    logging.info("Looking for browser window with titles: %s", candidates)

    for attempt in range(1, max_retries + 1):
        for title in candidates:
            windows = gw.getWindowsWithTitle(title)
            if not windows:
                continue

            window = windows[0]
            logging.info("Found browser window: %s", window.title)

            try:
                window.activate()
                logging.info("Activated window: %s", window.title)
            except Exception as exc:
                logging.debug("Could not activate window: %s", exc)

            try:
                window.maximize()
                logging.info("Window maximized")
            except Exception as exc:
                logging.debug("Could not maximize window: %s", exc)

            human_delay(2, "Allowing window to stabilize...")
            return

        logging.info("Window not found (attempt %d/%d). Retrying...", attempt, max_retries)
        human_delay(retry_wait_seconds, f"Waiting {retry_wait_seconds}s before retry...")

    raise BrowserLaunchError(
        f"Could not find window for '{browser_name}' after {max_retries} attempts.\n"
        f"Searched for window titles: {', '.join(candidates)}"
    )
