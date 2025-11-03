"""Upload Orchestrator - Main entry point for the modular workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..auth.credential_manager import CredentialManager
from ..config.settings_manager import SettingsManager
from .workflow_manager import (
    AccountWorkItem,
    CreatorLogin,
    WorkflowContext,
    WorkflowManager,
)


@dataclass(slots=True)
class AutomationPaths:
    """Resolved filesystem paths required for automation."""

    creators_root: Path
    shortcuts_root: Path
    history_file: Path


BROWSER_ALIASES = {
    "gologin": "gologin",
    "orbita": "gologin",
    "gologinbrowser": "gologin",
    "orbita_browser": "gologin",
    "ix": "ix",
    "ixbrowser": "ix",
    "incogniton": "ix",
    "incognitonbrowser": "ix",
    "chrome": "chrome",
}


class UploadOrchestrator:
    """Main orchestrator for upload workflow."""

    def __init__(
        self,
        settings: Optional[SettingsManager] = None,
        credentials: Optional[CredentialManager] = None,
    ) -> None:
        self.settings = settings or SettingsManager()
        self.credentials = credentials or CredentialManager()
        self.workflow_manager = WorkflowManager()
        logging.debug("UploadOrchestrator initialized")

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    def run(self, mode: Optional[str] = None) -> bool:
        """Run the main upload workflow."""
        automation_mode = (mode or self.settings.get_automation_mode() or "free_automation").strip().lower()
        logging.info("Starting upload orchestrator (mode=%s)...", automation_mode)

        if mode and mode != self.settings.get_automation_mode():
            self.settings.set_automation_mode(automation_mode)

        try:
            paths = self._resolve_paths()
        except ValueError as exc:
            logging.error("%s", exc)
            return False

        work_items = self._build_work_items(paths, automation_mode)
        if not work_items:
            logging.warning(
                "No automation accounts discovered in %s. Add shortcut folders with login_data.txt to continue.",
                paths.shortcuts_root,
            )
            return False

        logging.info("Prepared %d automation account(s) for processing.", len(work_items))

        context = WorkflowContext(history_file=paths.history_file)
        overall_success = True

        for work_item in work_items:
            result = self.workflow_manager.execute_account(work_item, context)
            overall_success = overall_success and result

        return overall_success

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _resolve_paths(self) -> AutomationPaths:
        """Resolve and validate filesystem paths used by the workflow."""
        path_config = self.settings.get_automation_paths() or {}

        creators_root = Path(path_config.get("creators_root", "")).expanduser().resolve()
        shortcuts_root = Path(path_config.get("shortcuts_root", "")).expanduser().resolve()

        default_history = Path(__file__).resolve().parents[1] / "data" / "upload_tracking.json"
        history_value = path_config.get("history_file")
        history_file = Path(history_value).expanduser().resolve() if history_value else default_history

        missing: List[str] = []
        if not creators_root.exists():
            missing.append(f"Creators folder not found: {creators_root}")
        if not shortcuts_root.exists():
            missing.append(f"Shortcuts folder not found: {shortcuts_root}")

        if missing:
            raise ValueError("; ".join(missing))

        history_file.parent.mkdir(parents=True, exist_ok=True)

        logging.debug(
            "Resolved paths | creators: %s | shortcuts: %s | history: %s",
            creators_root,
            shortcuts_root,
            history_file,
        )

        return AutomationPaths(
            creators_root=creators_root,
            shortcuts_root=shortcuts_root,
            history_file=history_file,
        )

    def _build_work_items(self, paths: AutomationPaths, automation_mode: str) -> List[AccountWorkItem]:
        """Scan shortcut folders and prepare account work items."""
        work_items: List[AccountWorkItem] = []

        for account_dir in sorted(p for p in paths.shortcuts_root.iterdir() if p.is_dir()):
            login_data_path = account_dir / "login_data.txt"
            if not login_data_path.is_file():
                logging.debug("Skipping %s (missing login_data.txt)", account_dir)
                continue

            entries, meta = self._parse_login_file(login_data_path, account_dir.name)
            if not entries:
                logging.warning("No valid creator entries found in %s", login_data_path)
                continue

            browser_hint = meta.get("browser") or meta.get("browser_type")
            browser_type = self._determine_browser_type(
                account_dir.name,
                automation_mode,
                explicit=browser_hint,
            )
            browser_config = self._get_browser_config(browser_type)

            work_items.append(
                AccountWorkItem(
                    account_name=account_dir.name,
                    browser_type=browser_type,
                    login_entries=tuple(entries),
                    login_data_path=login_data_path,
                    creators_root=paths.creators_root,
                    shortcuts_root=paths.shortcuts_root,
                    browser_config=browser_config,
                    automation_mode=automation_mode,
                )
            )

        return work_items

    def _parse_login_file(self, login_path: Path, account_name: str) -> Tuple[List[CreatorLogin], Dict[str, str]]:
        """Parse login_data.txt into creator login entries and raw metadata."""
        entries: List[CreatorLogin] = []
        kv_pairs: Dict[str, str] = {}

        try:
            lines = login_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            logging.error("Unable to read %s: %s", login_path, exc)
            return entries, kv_pairs

        for idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if "|" in line:
                parts = [segment.strip() for segment in line.split("|")]
                if len(parts) < 3:
                    logging.warning("Skipping malformed line %d in %s", idx, login_path)
                    continue

                extras: Dict[str, str] = {}
                if len(parts) > 5:
                    for extra_index, value in enumerate(parts[5:], start=1):
                        extras[f"extra_{extra_index}"] = value

                entries.append(
                    CreatorLogin(
                        profile_name=parts[0],
                        email=parts[1],
                        password=parts[2],
                        page_name=parts[3] if len(parts) > 3 else "",
                        page_id=parts[4] if len(parts) > 4 else "",
                        extras=extras,
                    )
                )
                continue

            if ":" in line:
                key, value = line.split(":", 1)
                kv_pairs[key.strip().lower().replace(" ", "_")] = value.strip()
                continue

            logging.warning("Skipping unrecognised line %d in %s", idx, login_path)

        if not entries and kv_pairs:
            profile_name = kv_pairs.get("profile_name") or account_name
            extras = {
                key: value
                for key, value in kv_pairs.items()
                if key
                not in {
                    "profile_name",
                    "email",
                    "password",
                    "page_name",
                    "page_id",
                    "browser",
                    "browser_type",
                }
            }

            entries.append(
                CreatorLogin(
                    profile_name=profile_name,
                    email=kv_pairs.get("email", ""),
                    password=kv_pairs.get("password", ""),
                    page_name=kv_pairs.get("page_name", ""),
                    page_id=kv_pairs.get("page_id", ""),
                    extras=extras,
                )
            )

        return entries, kv_pairs

    def _determine_browser_type(
        self,
        folder_name: str,
        automation_mode: str,
        *,
        explicit: Optional[str] = None,
    ) -> str:
        """Determine which browser configuration should be used."""
        if explicit:
            normalized = self._normalize_browser_name(explicit)
            if normalized:
                return normalized

        if automation_mode and automation_mode not in {"", "free_automation"}:
            return automation_mode

        name_lower = folder_name.lower()
        if "gologin" in name_lower or "orbita" in name_lower:
            return "gologin"
        if "ix" in name_lower or "incogniton" in name_lower:
            return "ix"
        if "vpn" in name_lower:
            return "vpn"

        return "free_automation"

    def _get_browser_config(self, browser_type: str) -> Dict[str, object]:
        """Fetch browser configuration block from settings."""
        config = self.settings.get(f"browsers.{browser_type}", {})
        if not isinstance(config, dict):
            return {}
        return config

    @staticmethod
    def _normalize_browser_name(name: str) -> Optional[str]:
        """Normalise free-form browser names to known identifiers."""
        candidate = (name or "").strip().lower().replace(" ", "")
        if not candidate:
            return None

        mapped = BROWSER_ALIASES.get(candidate)
        if mapped:
            return mapped

        for alias, target in BROWSER_ALIASES.items():
            if candidate.startswith(alias):
                return target

        if candidate in {"vpn", "free_automation"}:
            return candidate

        return candidate
