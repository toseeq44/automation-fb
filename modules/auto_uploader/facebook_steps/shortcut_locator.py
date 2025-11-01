"""Locate browser shortcuts on the desktop."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List, Optional


class ShortcutNotFoundError(Exception):
    """Raised when the requested browser shortcut cannot be located."""


_BROWSER_SHORTCUTS = {
    "ix": ["ixBrowser.lnk", "IX Browser.lnk", "IX.lnk"],
    "gologin": ["GoLogin.lnk", "gologin.lnk"],
    "incogniton": ["Incogniton.lnk", "incogniton.lnk"],
    "orbita": ["Orbita.lnk", "orbita.lnk"],
    "chrome": ["Google Chrome.lnk", "Chrome.lnk"],
    "edge": ["Microsoft Edge.lnk", "Edge.lnk"],
}


def _candidate_names(browser_name: str) -> Iterable[str]:
    browser_key = browser_name.strip().lower()

    # If a direct filename (with extension) was provided, check it first.
    if browser_key.endswith(".lnk"):
        yield browser_name

    yield from _BROWSER_SHORTCUTS.get(browser_key, [])

    # Fallback: also try the raw browser name with .lnk
    if not browser_key.endswith(".lnk"):
        yield f"{browser_name}.lnk"
        yield f"{browser_key}.lnk"


def find_browser_shortcut(browser_name: str, desktop_path: Optional[Path] = None) -> Path:
    """
    Locate the shortcut for the requested browser on the desktop.

    Args:
        browser_name: Name of the browser profile to open.
        desktop_path: Optional override for the desktop directory.

    Returns:
        Path to the found shortcut.

    Raises:
        ShortcutNotFoundError: If no matching shortcut can be located.
    """
    if not browser_name:
        raise ShortcutNotFoundError("Browser name is empty.")

    desktop = Path(desktop_path) if desktop_path else Path.home() / "Desktop"
    desktop = desktop.expanduser().resolve()

    if not desktop.exists():
        raise ShortcutNotFoundError(f"Desktop path does not exist: {desktop}")

    logging.info("Searching for %s shortcut on desktop: %s", browser_name, desktop)

    candidates: List[Path] = []

    for name in _candidate_names(browser_name):
        shortcut_path = desktop / name
        if shortcut_path.is_file():
            logging.info("Found browser shortcut: %s", shortcut_path)
            return shortcut_path
        candidates.append(shortcut_path)

    candidate_str = ", ".join(str(path.name) for path in candidates)
    raise ShortcutNotFoundError(
        f"Could not locate shortcut for browser '{browser_name}'. Tried: {candidate_str}"
    )
