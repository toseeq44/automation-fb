"""High level browser launcher facade."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .browser_controller import BrowserController
from .configuration import SettingsManager


class BrowserLauncher:
    """Delegates browser lifecycle operations to the controller."""

    def __init__(self, settings: SettingsManager):
        self.settings = settings
        self.controller = BrowserController(settings)

    def launch(self, browser_type: str):
        logging.debug("Launching browser type %s", browser_type)
        return self.controller.launch_browser(browser_type)

    def open_profile_shortcut(self, browser_type: str, shortcut: Path) -> bool:
        return self.controller.open_profile_via_shortcut(browser_type, shortcut)

    def connect(self, browser_type: str, profile_name: Optional[str] = None):
        return self.controller.connect_selenium(browser_type, profile_name)

    def close(self, browser_type: str):
        self.controller.close_browser(browser_type)

    def close_all(self):
        self.controller.close_all()

