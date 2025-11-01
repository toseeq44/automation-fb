"""Step 2: Extract browser name and locate desktop shortcut."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List, Optional


class ShortcutError(Exception):
    """Raised when browser shortcut cannot be found."""


# Known browser shortcut filename patterns
_BROWSER_SHORTCUTS = {
    "ix": ["ixBrowser.lnk", "IX Browser.lnk", "IX.lnk"],
    "gologin": ["GoLogin.lnk", "gologin.lnk"],
    "incogniton": ["Incogniton.lnk", "incogniton.lnk"],
    "orbita": ["Orbita.lnk", "orbita.lnk"],
    "chrome": ["Google Chrome.lnk", "Chrome.lnk"],
    "edge": ["Microsoft Edge.lnk", "Edge.lnk"],
    "firefox": ["Mozilla Firefox.lnk", "Firefox.lnk"],
}


def _get_candidate_names(browser_name: str) -> Iterable[str]:
    """
    Generate list of possible shortcut filenames for the browser.

    Args:
        browser_name: Name of the browser.

    Yields:
        Possible shortcut filenames in order of likelihood.
    """
    browser_key = browser_name.strip().lower()

    # If exact filename was provided, try it first
    if browser_key.endswith(".lnk"):
        yield browser_name

    # Try known shortcuts for this browser
    yield from _BROWSER_SHORTCUTS.get(browser_key, [])

    # Try generic patterns
    if not browser_key.endswith(".lnk"):
        yield f"{browser_name}.lnk"
        yield f"{browser_key}.lnk"


def find_shortcut(browser_name: str, desktop_path: Optional[Path] = None) -> Path:
    """
    Locate the browser shortcut on the desktop.

    Args:
        browser_name: Name of the browser to find (e.g., 'Chrome', 'Firefox', 'IX').
        desktop_path: Optional override for desktop directory. Defaults to ~/Desktop.

    Returns:
        Path to the found shortcut (.lnk) file.

    Raises:
        ShortcutError: If the shortcut cannot be located.
    """
    if not browser_name or not browser_name.strip():
        raise ShortcutError("Browser name is empty")

    desktop = Path(desktop_path) if desktop_path else Path.home() / "Desktop"
    desktop = desktop.expanduser().resolve()

    if not desktop.exists():
        raise ShortcutError(f"Desktop directory not found: {desktop}")

    logging.info("Searching for '%s' shortcut on desktop: %s", browser_name, desktop)

    candidates: List[Path] = []

    for filename in _get_candidate_names(browser_name):
        shortcut_path = desktop / filename
        if shortcut_path.is_file():
            logging.info("Found shortcut: %s", shortcut_path.name)
            return shortcut_path
        candidates.append(shortcut_path)

    candidate_names = ", ".join(path.name for path in candidates)
    raise ShortcutError(
        f"Could not find shortcut for '{browser_name}' on desktop.\n"
        f"Searched for: {candidate_names}\n"
        f"Desktop path: {desktop}"
    )
