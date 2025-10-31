"""Configuration helpers for the Facebook automation bot."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Any

from .auth_handler import AuthHandler
from .utils import (
    expand_path,
    get_config_value,
    load_config,
    merge_dicts,
    save_config,
)
from .ui_configurator import InitialSetupUI


class AutomationMode(str, Enum):
    """Supported automation modes."""

    GOLOGIN = "gologin"
    IX = "ix"
    VPN = "vpn"
    FREE = "free_automation"

    @classmethod
    def from_value(cls, value: str) -> "AutomationMode":
        try:
            return cls(value.lower())
        except ValueError:
            logging.warning("Unknown automation mode '%s', defaulting to free automation", value)
            return cls.FREE


@dataclass
class AutomationPaths:
    """Resolved filesystem paths for automation."""

    creators_root: Path
    shortcuts_root: Path
    history_file: Path


class SettingsManager:
    """Central access point for automation configuration."""

    def __init__(self, settings_path: Path, base_dir: Path, skip_setup: bool = False):
        """
        Initialize settings manager.

        Args:
            settings_path: Path to settings.json
            base_dir: Base directory for module
            skip_setup: If True, skip initial setup wizard (useful for GUI)
        """
        self.settings_path = settings_path
        self.base_dir = base_dir
        self._config = load_config(settings_path)
        self._ensure_structure()

        # Run initial setup only if:
        # 1. Setup not completed yet
        # 2. skip_setup is False (not running from GUI)
        # 3. Interactive terminal available
        if not skip_setup and not self._config.get("automation", {}).get("setup_completed"):
            self._run_initial_setup()

        self.paths = self._build_paths()

    # ------------------------------------------------------------------
    # public helpers
    # ------------------------------------------------------------------
    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    def get(self, dotted_key: str, default: Optional[Any] = None) -> Any:
        """Retrieve configuration using dotted notation."""
        return get_config_value(self._config, dotted_key, default)

    def get_mode(self) -> AutomationMode:
        mode = self.get("automation.mode", AutomationMode.FREE.value)
        return AutomationMode.from_value(mode)

    def save(self):
        save_config(self.settings_path, self._config)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _ensure_structure(self):
        """Guarantee new configuration sections exist."""
        from .utils import get_default_config

        defaults = get_default_config(self.base_dir)
        self._config = merge_dicts(defaults, self._config)
        self.save()

    def _build_paths(self) -> AutomationPaths:
        automation = self._config.get("automation", {})
        paths_cfg = automation.get("paths", {})

        creators_root = expand_path(paths_cfg.get("creators_root"), self.base_dir / "creators")
        shortcuts_root = expand_path(paths_cfg.get("shortcuts_root"), self.base_dir / "creator_shortcuts")
        history_file = expand_path(paths_cfg.get("history_file"), self.base_dir / "data" / "history.json")

        # Persist resolved absolute paths for transparency
        self._config.setdefault("automation", {}).setdefault("paths", {})
        self._config["automation"]["paths"].update(
            {
                "creators_root": str(creators_root),
                "shortcuts_root": str(shortcuts_root),
                "history_file": str(history_file),
            }
        )
        self.save()

        return AutomationPaths(creators_root=creators_root, shortcuts_root=shortcuts_root, history_file=history_file)

    def _run_initial_setup(self):
        if not sys.stdin or not sys.stdin.isatty():
            logging.info("Non-interactive environment detected; using default automation settings")
            self._config.setdefault("automation", {}).update({"setup_completed": False})
            return

        ui = InitialSetupUI(self.base_dir)
        updated = ui.collect(self._config)
        credentials = updated.get("automation", {}).get("credentials", {})
        if credentials:
            auth = AuthHandler()
            secured_credentials = {}
            for key, payload in credentials.items():
                secured_credentials[key] = auth.save_credentials(f"setup:{key}", payload)
            updated["automation"]["credentials"] = secured_credentials
        self._config = merge_dicts(self._config, updated)
        self._config.setdefault("automation", {})["setup_completed"] = True
        self.save()

