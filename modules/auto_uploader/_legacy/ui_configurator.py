"""Simple CLI driven configuration wizard for the automation bot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from .utils import expand_path


class InitialSetupUI:
    """Collects minimal information required to start the bot."""

    MODES = {
        "1": ("GoLogin", "gologin"),
        "2": ("IX Browser", "ix"),
        "3": ("VPN", "vpn"),
        "4": ("Free Automation", "free_automation"),
    }

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def collect(self, current_config: Dict) -> Dict:
        logging.info("Starting initial configuration wizard for Facebook Auto Uploader")
        automation_cfg = current_config.get("automation", {})
        mode_choice = self._ask_mode(automation_cfg.get("mode", "free_automation"))

        updated = {
            "automation": {
                "mode": mode_choice,
                "setup_completed": True,
                "paths": {},
            }
        }

        if mode_choice == "free_automation":
            updated["automation"]["paths"].update(self._collect_free_paths(automation_cfg.get("paths", {})))
        elif mode_choice in {"gologin", "ix"}:
            updated["automation"]["credentials"] = self._collect_browser_credentials(mode_choice, automation_cfg.get("credentials", {}))
        elif mode_choice == "vpn":
            updated["automation"]["credentials"] = self._collect_vpn_credentials(automation_cfg.get("credentials", {}))

        logging.info("Initial configuration captured")
        return updated

    # ------------------------------------------------------------------
    def _ask_mode(self, default_mode: str) -> str:
        print("\nSelect automation mode:")
        for key, (label, _) in self.MODES.items():
            print(f"  {key}. {label}")

        default_key = next((key for key, (_, value) in self.MODES.items() if value == default_mode), "4")
        selection = input(f"Enter choice [{default_key}]: ").strip() or default_key
        return self.MODES.get(selection, self.MODES[default_key])[1]

    def _collect_free_paths(self, existing_paths: Dict) -> Dict:
        creators_default = existing_paths.get("creators_root") or str((self.base_dir / "creators").resolve())
        shortcuts_default = existing_paths.get("shortcuts_root") or str((self.base_dir / "creator_shortcuts").resolve())

        creators_root = input(f"Creators folder path [{creators_default}]: ").strip() or creators_default
        shortcuts_root = input(f"Creator shortcuts folder path [{shortcuts_default}]: ").strip() or shortcuts_default

        creators_path = expand_path(creators_root, self.base_dir / "creators")
        shortcuts_path = expand_path(shortcuts_root, self.base_dir / "creator_shortcuts")

        return {
            "creators_root": str(creators_path),
            "shortcuts_root": str(shortcuts_path),
        }

    def _collect_browser_credentials(self, mode: str, existing_credentials: Dict) -> Dict:
        print("\nProvide access information for the browser automation service.")
        print("You can leave fields blank to keep existing values.")

        api_key = input("API Key (optional): ").strip() or existing_credentials.get(mode, {}).get("api_key", "")
        email = input("Account email: ").strip() or existing_credentials.get(mode, {}).get("email", "")
        password = input("Account password: ").strip() or existing_credentials.get(mode, {}).get("password", "")

        return {
            mode: {
                "api_key": api_key,
                "email": email,
                "password": password,
            }
        }

    def _collect_vpn_credentials(self, existing_credentials: Dict) -> Dict:
        print("\nEnter VPN credentials and preferred location.")
        vpn_cfg = existing_credentials.get("vpn", {})

        username = input("VPN username: ").strip() or vpn_cfg.get("username", "")
        password = input("VPN password: ").strip() or vpn_cfg.get("password", "")
        location = input("Preferred city/country: ").strip() or vpn_cfg.get("location", "")

        return {
            "vpn": {
                "username": username,
                "password": password,
                "location": location,
            }
        }

