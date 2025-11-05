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
        logging.info("="*60)
        logging.info("UPLOAD ORCHESTRATOR STARTED")
        logging.info("="*60)
        logging.info("Step 1/5: Initializing orchestrator (mode=%s)", automation_mode)

        if mode and mode != self.settings.get_automation_mode():
            self.settings.set_automation_mode(automation_mode)
            logging.info("→ Automation mode updated to: %s", automation_mode)

        # Step 1: Resolve paths
        logging.info("Step 2/5: Resolving folder paths from settings...")
        try:
            paths = self._resolve_paths()
            logging.info("✓ Paths resolved successfully:")
            logging.info("  → Creators root: %s", paths.creators_root)
            logging.info("  → Shortcuts root: %s", paths.shortcuts_root)
            logging.info("  → History file: %s", paths.history_file)
        except ValueError as exc:
            logging.error("✗ Path resolution failed: %s", exc)
            logging.error("Please check your folder paths in Approaches dialog")
            return False

        # Step 2: Build work items
        logging.info("Step 3/5: Scanning shortcuts folder for accounts...")
        logging.info("→ Scanning: %s", paths.shortcuts_root)
        work_items = self._build_work_items(paths, automation_mode)

        if not work_items:
            logging.error("="*60)
            logging.error("✗ NO ACCOUNTS FOUND!")
            logging.error("="*60)
            logging.error("Reason: No folders with login_data.txt found in shortcuts folder")
            logging.error("Location checked: %s", paths.shortcuts_root)
            logging.error("")
            logging.error("HOW TO FIX:")
            logging.error("1. Create a folder inside shortcuts_root (e.g., 'Account1')")
            logging.error("2. Inside that folder, create 'login_data.txt' file")
            logging.error("3. Format: Creator1|email@gmail.com|password|PageName|PageID")
            logging.error("4. Optional: Add 'browser: chrome' at top of file")
            logging.error("="*60)
            return False

        logging.info("✓ Found %d account(s) to process:", len(work_items))
        for idx, item in enumerate(work_items, 1):
            logging.info("  %d. Account: %s | Browser: %s | Creators: %d",
                        idx, item.account_name, item.browser_type, len(item.login_entries))

        # Step 3: Execute workflow
        logging.info("Step 4/5: Starting account processing...")
        context = WorkflowContext(history_file=paths.history_file)
        overall_success = True

        for idx, work_item in enumerate(work_items, 1):
            logging.info("-"*60)
            logging.info("Processing account %d/%d: %s", idx, len(work_items), work_item.account_name)
            logging.info("-"*60)
            result = self.workflow_manager.execute_account(work_item, context)
            overall_success = overall_success and result

            if result:
                logging.info("✓ Account '%s' processed successfully", work_item.account_name)
            else:
                logging.error("✗ Account '%s' processing failed", work_item.account_name)

        # Step 4: Summary
        logging.info("="*60)
        logging.info("Step 5/5: Workflow completed")
        if overall_success:
            logging.info("✓ ALL ACCOUNTS PROCESSED SUCCESSFULLY")
        else:
            logging.warning("⚠ SOME ACCOUNTS FAILED - Check logs above")
        logging.info("="*60)

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

        # List all directories in shortcuts folder
        all_dirs = [p for p in paths.shortcuts_root.iterdir() if p.is_dir()]
        logging.info("  → Found %d folder(s) in shortcuts directory", len(all_dirs))

        for account_dir in sorted(all_dirs):
            logging.info("  → Checking folder: %s", account_dir.name)

            login_data_path = account_dir / "login_data.txt"
            if not login_data_path.is_file():
                logging.warning("    ✗ Skipped: No login_data.txt found in '%s'", account_dir.name)
                continue

            logging.info("    ✓ Found login_data.txt")

            # Parse login file
            entries, meta = self._parse_login_file(login_data_path, account_dir.name)

            if not entries:
                logging.warning("    ✗ Skipped: No valid creator entries in login_data.txt")
                continue

            logging.info("    ✓ Parsed %d creator account(s) from login_data.txt", len(entries))

            # Determine browser type
            browser_hint = meta.get("browser") or meta.get("browser_type")
            browser_type = self._determine_browser_type(
                account_dir.name,
                automation_mode,
                explicit=browser_hint,
            )

            if browser_hint:
                logging.info("    → Browser specified in file: %s", browser_hint)

            logging.info("    → Browser type determined: %s", browser_type)

            browser_config = self._get_browser_config(browser_type)

            # If browser_hint is specified, pass it to launcher for desktop shortcut search
            # This allows searching for the exact shortcut name from login_data.txt
            # instead of using hardcoded paths like ~/Desktop/Incogniton.lnk
            if browser_hint:
                browser_config['browser_name'] = browser_hint
                logging.info("    → Browser name for shortcut search: %s", browser_hint)

            # Log creator names
            creator_names = [entry.profile_name for entry in entries]
            logging.info("    → Creators: %s", ", ".join(creator_names))

            profile_names_value = meta.get("profile_names")
            if profile_names_value:
                browser_config["ix_profile_names_raw"] = profile_names_value

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
                    metadata=meta,
                )
            )

            logging.info("    ✓ Account '%s' added to processing queue", account_dir.name)

        if not work_items:
            logging.error("  → No valid accounts found with login_data.txt")

        return work_items

    def _parse_login_file(self, login_path: Path, account_name: str) -> Tuple[List[CreatorLogin], Dict[str, str]]:
        """Parse login_data.txt into creator login entries and raw metadata."""
        entries: List[CreatorLogin] = []
        kv_pairs: Dict[str, str] = {}

        try:
            content = login_path.read_text(encoding="utf-8")
        except OSError as exc:
            logging.error("Unable to read %s: %s", login_path, exc)
            return entries, kv_pairs

        # First pass: handle multi-line values (like profile_names: { ... })
        current_key: Optional[str] = None
        current_value_lines: List[str] = []
        in_multiline_block = False

        lines = content.splitlines()
        for raw_line in lines:
            line = raw_line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Check if this line starts with a letter (actual key) vs a number/symbol (continuation)
            # A key should start with a letter/word character
            is_top_level_key = (
                ":" in line
                and not raw_line.startswith(" ")
                and not raw_line.startswith("\t")
                and line[0].isalpha()  # Key must start with a letter
            )

            if is_top_level_key:
                # Save previous key-value pair if exists
                if current_key and current_value_lines:
                    combined_value = " ".join(v.strip() for v in current_value_lines if v.strip())
                    kv_pairs[current_key] = combined_value
                    current_value_lines = []

                # Start new key-value pair
                key_part, value_part = line.split(":", 1)
                current_key = key_part.strip().lower().replace(" ", "_")
                current_value_lines = [value_part.strip()]
                # Track if we've just started a multi-line block (ends with "{")
                in_multiline_block = value_part.strip().endswith("{") or value_part.strip() == "{"
            elif current_key is not None:
                # Continuation of previous value
                if line:  # Only add non-empty lines
                    current_value_lines.append(line)
                # Check if this line ends the multi-line block
                if line.endswith("}"):
                    in_multiline_block = False
            elif "|" in line:
                # Handle pipe-separated entries (only if not in a multi-line block)
                parts = [segment.strip() for segment in line.split("|")]
                if len(parts) < 3:
                    logging.warning("Skipping malformed pipe line: %s", line)
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

        # Save last key-value pair
        if current_key and current_value_lines:
            combined_value = " ".join(v.strip() for v in current_value_lines if v.strip())
            kv_pairs[current_key] = combined_value

        if not entries and kv_pairs:
            # No pipe-separated entries found, use account-based discovery
            # First, check if profile_names are defined in login_data.txt
            profile_names_raw = kv_pairs.get("profile_names", "")

            if profile_names_raw:
                # Parse profile_names from login_data.txt
                from ..browser.profile_selector import IXProfileSelector
                profile_names = IXProfileSelector.parse_profile_names(profile_names_raw)

                if profile_names:
                    logging.info(
                        "Found %d profile name(s) from login_data.txt: %s",
                        len(profile_names),
                        ", ".join(profile_names)
                    )

                    # Create CreatorLogin entries from profile_names in login_data.txt
                    extras = {
                        key: value
                        for key, value in kv_pairs.items()
                        if key
                        not in {
                            "profile_name",
                            "profile_names",
                            "email",
                            "password",
                            "page_name",
                            "page_id",
                            "browser",
                            "browser_type",
                        }
                    }

                    for profile_name in profile_names:
                        entries.append(
                            CreatorLogin(
                                profile_name=profile_name,  # Use profile name from login_data.txt
                                email=kv_pairs.get("email", ""),
                                password=kv_pairs.get("password", ""),
                                page_name=kv_pairs.get("page_name", ""),
                                page_id=kv_pairs.get("page_id", ""),
                                extras=extras,
                            )
                        )

            # If no profile_names defined, fall back to Creators subfolder discovery
            if not entries:
                account_dir = login_path.parent
                creators_subfolder = account_dir / "Creators"

                if creators_subfolder.exists():
                    # Discover creator folders from Creators subfolder
                    creator_dirs = [d for d in creators_subfolder.iterdir() if d.is_dir()]
                    logging.debug(
                        "Found %d creator folder(s) in %s: %s",
                        len(creator_dirs),
                        creators_subfolder,
                        ", ".join(d.name for d in creator_dirs)
                    )

                    # Create CreatorLogin entries for each discovered creator
                    for creator_dir in creator_dirs:
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
                                profile_name=creator_dir.name,  # Use actual creator folder name
                                email=kv_pairs.get("email", ""),
                                password=kv_pairs.get("password", ""),
                                page_name=kv_pairs.get("page_name", ""),
                                page_id=kv_pairs.get("page_id", ""),
                                extras=extras,
                            )
                        )

            # If still no entries and no profile_names, fallback to single account entry
            if not entries:
                logging.debug("No profile_names or Creators subfolder found, using account name as profile")
                profile_name = kv_pairs.get("profile_name") or account_name
                extras = {
                    key: value
                    for key, value in kv_pairs.items()
                    if key
                    not in {
                        "profile_name",
                        "profile_names",
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
