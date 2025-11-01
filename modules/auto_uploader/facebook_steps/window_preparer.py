"""Find and maximize the launched browser window."""

from __future__ import annotations

import logging
from typing import List, Sequence

try:
    import pygetwindow as gw
except ImportError:  # pragma: no cover - optional dependency
    gw = None  # type: ignore

from .mouse_feedback import human_delay


class BrowserWindowNotFoundError(Exception):
    """Raised when the expected browser window cannot be located."""


_WINDOW_TITLE_PATTERNS = {
    "ix": ["ixBrowser", "IX Browser", "Incogniton", "IX"],
    "gologin": ["GoLogin", "Orbita", "gologin"],
    "incogniton": ["Incogniton", "ixBrowser"],
    "orbita": ["Orbita", "GoLogin"],
}


def _title_candidates(browser_name: str) -> Sequence[str]:
    browser_key = browser_name.strip().lower()
    titles: List[str] = []
    titles.extend(_WINDOW_TITLE_PATTERNS.get(browser_key, []))

    if browser_name not in titles:
        titles.append(browser_name)
    if browser_key not in titles:
        titles.append(browser_key)

    return [title for title in titles if title]


def focus_and_prepare_window(browser_name: str, retries: int = 3, wait_seconds: int = 4):
    """
    Locate the browser window and make sure it is maximized.

    Args:
        browser_name: Browser identifier.
        retries: Number of attempts before giving up.
        wait_seconds: Delay between retries with mouse feedback.

    Returns:
        A pygetwindow window instance.

    Raises:
        BrowserWindowNotFoundError: If no matching window is found.
    """
    if gw is None:
        raise BrowserWindowNotFoundError("pygetwindow is required to manage browser windows.")

    candidates = _title_candidates(browser_name)
    logging.info("Looking for browser window titles: %s", candidates)

    for attempt in range(1, retries + 1):
        for title in candidates:
            windows = gw.getWindowsWithTitle(title)
            if not windows:
                continue

            window = windows[0]

            logging.info("Found browser window: %s", window.title)

            try:
                window.activate()
            except Exception as exc:  # pragma: no cover - GUI interaction
                logging.debug("Could not activate window: %s", exc)

            try:
                window.maximize()
                logging.info("Browser window maximized.")
            except Exception as exc:  # pragma: no cover - GUI interaction
                logging.debug("Could not maximize window: %s", exc)

            human_delay(2, "Allowing browser window to stabilize...")
            return window

        logging.info("Browser window not found (attempt %s/%s). Retrying...", attempt, retries)
        human_delay(wait_seconds, "Waiting before next window search...")

    raise BrowserWindowNotFoundError(f"Could not locate window for browser '{browser_name}'.")
