"""Settings Manager - Manage settings for the modular auto uploader.

NOTE: Uses persistent paths that work with PyInstaller EXE
"""

import json
import logging
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

from .defaults import DEFAULT_CONFIG


def _get_persistent_settings_dir() -> Path:
    """
    Get persistent settings directory for auto uploader.
    Works both in development and PyInstaller EXE.

    Returns:
        Path to persistent settings directory
    """
    settings_dir = Path.home() / ".onesoul" / "auto_uploader" / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir


class SettingsManager:
    """High level helper around the shared settings.json file."""

    def __init__(self, settings_path: Optional[Path] = None):
        # Use persistent directory for settings (survives EXE restarts)
        self._base_dir = _get_persistent_settings_dir().parent
        self._settings_path = Path(settings_path or (_get_persistent_settings_dir() / "settings.json"))
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)

        logging.debug("SettingsManager initialized (path=%s)", self._settings_path)

        self._settings: Dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    @property
    def settings_path(self) -> Path:
        return self._settings_path

    def get_settings(self) -> Dict[str, Any]:
        """Return a deep copy of the current settings."""
        return deepcopy(self._settings)

    def get(self, dotted_key: str, default: Optional[Any] = None) -> Any:
        """Fetch a value using dotted key notation."""
        current = self._settings
        for segment in dotted_key.split("."):
            if not isinstance(current, dict) or segment not in current:
                return default
            current = current[segment]
        return deepcopy(current)

    def set(self, dotted_key: str, value: Any) -> None:
        """Persist a value using dotted key notation."""
        parts = dotted_key.split(".")
        target = self._settings
        for segment in parts[:-1]:
            target = target.setdefault(segment, {})
        target[parts[-1]] = value
        self._save()

    def get_automation_mode(self) -> str:
        return self.get("automation.mode", "free_automation")

    def set_automation_mode(self, mode: str) -> None:
        self.set("automation.mode", mode)

    def is_setup_completed(self) -> bool:
        return bool(self.get("automation.setup_completed", False))

    def mark_setup_completed(self) -> None:
        self.set("automation.setup_completed", True)

    def get_automation_paths(self) -> Dict[str, str]:
        return self.get("automation.paths", {})

    def update_automation_paths(self, creators_root: str, shortcuts_root: str, history_file: str = "") -> None:
        existing = self.get_automation_paths() or {}
        ix_data_root = existing.get("ix_data_root") or str(
            (self._base_dir / "ix_data").resolve()
        )

        self.set(
            "automation.paths",
            {
                "creators_root": creators_root,
                "shortcuts_root": shortcuts_root,
                "history_file": history_file,
                "ix_data_root": ix_data_root,
            },
        )

    def get_credentials(self, mode: str) -> Dict[str, Any]:
        return self.get(f"automation.credentials.{mode}", {})

    def update_credentials(self, mode: str, payload: Dict[str, Any]) -> None:
        self.set(f"automation.credentials.{mode}", payload)

    def get_delete_after_publish(self) -> bool:
        """Get user preference for deleting videos after publish (default: False - move to folder)."""
        return bool(self.get("automation.delete_after_publish", False))

    def set_delete_after_publish(self, delete: bool) -> None:
        """Set user preference for deleting videos after publish."""
        self.set("automation.delete_after_publish", delete)

    # ------------------------------------------------------------------ #
    # Private helpers                                                    #
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        """Load settings from disk and merge defaults."""
        data: Dict[str, Any] = {}
        if self._settings_path.exists():
            try:
                data = json.loads(self._settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                logging.error("Failed to decode settings file %s: %s", self._settings_path, exc)
        else:
            logging.info("Settings file not found, generating new one at %s", self._settings_path)

        merged = self._deep_merge(DEFAULT_CONFIG, data)
        self._settings = merged
        self._save()

    def _save(self) -> None:
        """Write current settings to disk."""
        try:
            self._settings_path.write_text(json.dumps(self._settings, indent=2), encoding="utf-8")
        except OSError as exc:
            logging.error("Unable to write settings file %s: %s", self._settings_path, exc)

    @staticmethod
    def _deep_merge(defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries without mutating the inputs."""
        result = deepcopy(defaults)
        if not overrides:
            return result

        def merge(source: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
            for key, value in update.items():
                if isinstance(value, dict) and isinstance(source.get(key), dict):
                    source[key] = merge(source.get(key, {}), value)
                else:
                    source[key] = value
            return source

        return merge(result, overrides)
