"""Workflow Manager - Upload workflow logic for the modular uploader."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ..browser.launcher import BrowserLauncher
from ..browser.image_based_login import ImageBasedLogin
from ..browser.profile_selector import IXProfileSelector
from ..browser.screen_detector import ScreenDetector
from ..browser.video_upload_workflow import UploadWorkflowOrchestrator
from ..upload.file_selector import FileSelector
from ..upload.metadata_handler import MetadataHandler
from ..upload.video_uploader import VideoUploader
from ..tracking.upload_tracker import UploadTracker


@dataclass(slots=True)
class CreatorLogin:
    """Represents a single creator entry parsed from login_data.txt."""

    profile_name: str
    email: str
    password: str
    page_name: str = ""
    page_id: str = ""
    extras: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AccountWorkItem:
    """Unit of work describing one browser account and its creators."""

    account_name: str
    browser_type: str
    login_entries: Sequence[CreatorLogin]
    login_data_path: Path
    creators_root: Path
    shortcuts_root: Path
    browser_config: Dict[str, object]
    automation_mode: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowContext:
    """Shared execution context passed to each workflow run."""

    history_file: Path


class WorkflowManager:
    """Coordinates creator processing for the modular auto uploader."""

    def __init__(
        self,
        file_selector: Optional[FileSelector] = None,
        metadata_handler: Optional[MetadataHandler] = None,
        uploader: Optional[VideoUploader] = None,
    ) -> None:
        self._file_selector = file_selector or FileSelector()
        self._metadata_handler = metadata_handler or MetadataHandler()
        self._uploader = uploader or VideoUploader()
        self._ix_selector_cached: Optional[IXProfileSelector | bool] = None
        logging.debug("WorkflowManager initialized")

    def execute_account(self, work_item: AccountWorkItem, context: WorkflowContext) -> bool:
        """Process all creators that belong to a single browser account."""
        logging.info("")
        logging.info("┌" + "─"*58 + "┐")
        logging.info("│ PROCESSING ACCOUNT: %-40s │" % work_item.account_name[:40])
        logging.info("├" + "─"*58 + "┤")
        logging.info("│ Browser Type: %-44s │" % work_item.browser_type[:44])
        logging.info("│ Creator Accounts: %-40d │" % len(work_item.login_entries))
        logging.info("└" + "─"*58 + "┘")
        logging.info("")

        # Step 1: Browser Launch
        logging.info("")
        logging.info("▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓")
        logging.info("⚙️  STEP 1/3: LAUNCHING BROWSER")
        logging.info("▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓")
        logging.info("")

        logging.info("📋 Configuration:")
        logging.info("   → Browser type: %s", work_item.browser_type.upper())
        logging.info("   → Automation mode: %s", work_item.automation_mode)

        if 'browser_name' in work_item.browser_config:
            logging.info("   → Custom browser name: %s", work_item.browser_config['browser_name'])

        logging.info("")
        logging.info("🔧 Initializing BrowserLauncher...")
        launcher = BrowserLauncher(config=work_item.browser_config)

        # Pass browser_config as kwargs to launcher (includes browser_name if specified)
        launch_kwargs = {'show_popup': True}
        launch_kwargs.update(work_item.browser_config)

        account_shortcut_dir = work_item.shortcuts_root / work_item.account_name
        launch_kwargs['account_shortcut_dir'] = account_shortcut_dir

        def _append_path(accumulator: List[Path], candidate: Optional[object]) -> None:
            if not candidate:
                return
            if isinstance(candidate, Path):
                path_candidate = candidate
            else:
                text = str(candidate).strip()
                if not text:
                    return
                path_candidate = Path(text).expanduser()
            try:
                resolved = path_candidate.resolve(strict=False)
            except OSError:
                resolved = path_candidate
            if resolved not in accumulator:
                accumulator.append(resolved)

        search_paths: List[Path] = []
        _append_path(search_paths, account_shortcut_dir)
        _append_path(search_paths, account_shortcut_dir / "Creators")
        _append_path(search_paths, work_item.shortcuts_root)

        existing_search = launch_kwargs.pop('shortcut_search_paths', None)
        if isinstance(existing_search, (list, tuple, set)):
            for entry in existing_search:
                _append_path(search_paths, entry)
        else:
            _append_path(search_paths, existing_search)

        launch_kwargs['shortcut_search_paths'] = search_paths

        logging.info("   ✓ BrowserLauncher initialized")
        logging.info("")
        logging.info("🚀 Calling launcher.launch_generic('%s')...", work_item.browser_type)

        launch_result = launcher.launch_generic(work_item.browser_type, **launch_kwargs)

        if launch_result:
            logging.info("")
            logging.info("✅ BROWSER LAUNCH SUCCESSFUL!")
            logging.info("   Process is running and ready for automation")
            logging.info("")
        else:
            logging.error("")
            logging.error("╔════════════════════════════════════════════════════════╗")
            logging.error("║ ❌ BROWSER LAUNCH FAILED                               ║")
            logging.error("╚════════════════════════════════════════════════════════╝")
            logging.error("")
            logging.error("🔍 POSSIBLE REASONS:")
            logging.error("   1. Browser shortcut not found on Desktop (.lnk file)")
            logging.error("   2. Browser not installed on system")
            logging.error("   3. Incorrect browser name in login_data.txt")
            logging.error("   4. Browser shortcut is broken or inaccessible")
            logging.error("")
            logging.error("📋 WHAT TO CHECK:")
            logging.error("   • Open: C:\\Users\\Fast Computers\\Desktop")
            logging.error("   • Look for: *.lnk files (shortcuts)")
            logging.error("   • Browser type configured: %s", work_item.browser_type)
            logging.error("   • Custom browser name: %s", work_item.browser_config.get('browser_name', 'default (chrome)'))
            logging.error("   • Available browsers: chrome, firefox, edge, brave, opera")
            logging.error("")
            logging.error("💡 QUICK FIX:")
            logging.error("   1. Check if browser is installed on your system")
            logging.error("   2. Create a desktop shortcut to the browser")
            logging.error("   3. Ensure shortcut name contains browser name (e.g., 'Google Chrome.lnk')")
            logging.error("")
            return False

        if not work_item.login_entries:
            logging.info("⚠ No login entries - browser launched but no creators to process")
            return True

        # Step 1.5: Browser Login System
        logging.info("")
        logging.info("╔════════════════════════════════════════════════════════╗")
        logging.info("║ 🔐 BROWSER LOGIN SYSTEM                               ║")
        logging.info("╚════════════════════════════════════════════════════════╝")
        logging.info("")
        logging.info("📋 ACCOUNT CREDENTIALS (from login_data.txt):")
        logging.info("   → Account: %s", work_item.account_name)

        primary_login = work_item.login_entries[0] if work_item.login_entries else None
        account_email = primary_login.email if primary_login else "N/A"
        account_password = primary_login.password if primary_login else "N/A"
        window_title_hint = (
            self._resolve_window_title_hint(work_item, primary_login) if primary_login else None
        )

        logging.info("   → Email: %s", account_email)
        logging.info("")
        logging.info("🔑 LOGIN PROCESS:")
        logging.info("   Step 1: Browser is running")
        logging.info("   Step 2: Detecting login status...")
        logging.info("   Step 3: Auto-filling account credentials")
        logging.info("   Step 4: Clicking login button")
        logging.info("   Step 5: Waiting for login completion")
        logging.info("")

        # Image-based automated login
        import time

        logging.info("[LOGIN] Browser is open and ready for login")
        logging.info("   Using image-based intelligent login automation...")
        logging.info("")

        try:
            # Initialize image-based login
            logging.info("[LOGIN] Initializing image-based login system...")
            image_login = ImageBasedLogin()

            # Run login flow
            logging.info("[LOGIN] Running login flow...")
            login_success = image_login.run_login_flow(
                email=account_email,
                password=account_password,
                window_title=window_title_hint,
                browser_type=work_item.browser_type,
                force_relogin=True,
            )

            if login_success:
                logging.info("[LOGIN] ✓ Login completed successfully")
            else:
                logging.warning("[LOGIN] ✗ Login flow did not complete")

        except ImportError as e:
            logging.error("[LOGIN] Image-based login not available: %s", str(e))
            logging.warning("[LOGIN] Missing dependencies: pip install opencv-python pyautogui")
            logging.info("[LOGIN] Falling back to manual login (waiting 60 seconds)...")
            time.sleep(60)
            login_success = True

        except Exception as e:
            logging.error("[LOGIN] Login error: %s", str(e))
            logging.warning("[LOGIN] Falling back to manual login (waiting 60 seconds)...")
            import traceback
            logging.debug("[LOGIN] Traceback: %s", traceback.format_exc())
            time.sleep(60)
            login_success = True

        logging.info("")
        logging.info("[OK] LOGIN PROCESS COMPLETED")
        logging.info("[OK] Browser is ready for creator automation")

        logging.info("")

        # Step 2: Process creators
        logging.info("⚙ Step 2/3: Processing creators...")
        tracker = UploadTracker(context.history_file)
        account_success = True

        ix_profile_names: Sequence[str] = ()
        last_ix_profile: Optional[str] = None
        if work_item.browser_type == "ix":
            ix_profile_names = self._get_ix_profile_names(work_item)
            if ix_profile_names:
                logging.info("[IX] Profile order for this account: %s", ", ".join(ix_profile_names))

        for idx, login in enumerate(work_item.login_entries, 1):
            logging.info("")
            logging.info("  → Creator %d/%d: %s", idx, len(work_item.login_entries), login.profile_name)

            if work_item.browser_type == "ix":
                target_profile: Optional[str] = None
                if ix_profile_names and idx - 1 < len(ix_profile_names):
                    target_profile = ix_profile_names[idx - 1]
                if not target_profile:
                    target_profile = login.profile_name

                if target_profile and target_profile != last_ix_profile:
                    logging.info(
                        "[IX] Preparing to open profile '%s' for creator '%s'",
                        target_profile,
                        login.profile_name,
                    )
                    if self._open_ix_profile(target_profile):
                        last_ix_profile = target_profile

                        # Run video upload workflow after profile opens
                        logging.info("")
                        logging.info("[WORKFLOW] Starting video upload workflow for profile: %s", target_profile)
                        self._run_upload_workflow(target_profile, work_item)
                    else:
                        logging.warning(
                            "[IX] Unable to switch to profile '%s'; continuing anyway.",
                            target_profile,
                        )

            creator_success = self._process_creator(login, work_item, tracker)
            account_success = account_success and creator_success

            if creator_success:
                logging.info("  ✓ Creator '%s' processed", login.profile_name)
            else:
                logging.error("  ✗ Creator '%s' failed", login.profile_name)

        # Step 3: Save tracking
        logging.info("")
        logging.info("⚙ Step 3/3: Saving upload history...")
        try:
            tracker.flush()
            logging.info("  ✓ Upload history saved to: %s", context.history_file)
        except Exception as exc:
            logging.error("  ✗ Failed to save upload history: %s", exc)

        logging.info("")
        if account_success:
            logging.info("✓ Account '%s' completed successfully", work_item.account_name)
        else:
            logging.error("✗ Account '%s' had errors", work_item.account_name)

        return account_success

    # ------------------------------------------------------------------ #
    # ixBrowser profile selection                                       #
    # ------------------------------------------------------------------ #
    def _get_ix_selector(self) -> Optional[IXProfileSelector]:
        if self._ix_selector_cached is False:
            return None
        if self._ix_selector_cached is None:
            try:
                screen_detector = ScreenDetector()
                self._ix_selector_cached = IXProfileSelector(screen_detector)
            except Exception as exc:  # pragma: no cover
                logging.warning("[IX] Unable to initialise profile selector: %s", exc)
                self._ix_selector_cached = False
        if self._ix_selector_cached is False:
            return None
        return self._ix_selector_cached  # type: ignore[return-value]

    def _open_ix_profile(self, profile_name: str) -> bool:
        selector = self._get_ix_selector()
        if not selector:
            logging.warning("[IX] Profile selector unavailable; skipping ixBrowser profile selection.")
            return False

        if not profile_name:
            logging.info("[IX] Empty profile name supplied; skipping.")
            return False

        logging.info("[IX] Attempting to open ixBrowser profile: %s", profile_name)
        success = selector.open_profile(profile_name)
        if success:
            logging.info("[IX] Profile '%s' opened successfully.", profile_name)
        else:
            logging.warning("[IX] Failed to automate profile opening for '%s'.", profile_name)
        return success

    def _get_ix_profile_names(self, work_item: AccountWorkItem) -> Sequence[str]:
        raw_value = (
            work_item.browser_config.get("ix_profile_names_raw")
            or work_item.metadata.get("profile_names")
        )

        if isinstance(raw_value, str):
            names = IXProfileSelector.parse_profile_names(raw_value)
            if names:
                return names

        return [entry.profile_name for entry in work_item.login_entries]


    def _process_creator(
        self,
        login: CreatorLogin,
        work_item: AccountWorkItem,
        tracker: UploadTracker,
    ) -> bool:
        """Handle upload operations for a single creator/profile."""
        logging.info(
            "Preparing creator '%s' (page=%s)",
            login.profile_name,
            login.page_name or "N/A",
        )

        # Step 1: Check if creator has shortcuts in the account's Creators folder
        # The correct path is: shortcuts_root/account_name/Creators/creator_name/
        account_creators_folder = work_item.shortcuts_root / work_item.account_name / "Creators"
        creator_shortcut_folder = account_creators_folder / login.profile_name

        logging.debug("Looking for creator shortcuts at: %s", creator_shortcut_folder)

        if not creator_shortcut_folder.exists():
            logging.info("Creator shortcut folder not found for '%s'; skipping uploads.", login.profile_name)
            logging.debug("Expected path: %s", creator_shortcut_folder)
            return True

        logging.info("✓ Found creator shortcut folder: %s", creator_shortcut_folder)

        # List available shortcuts for this creator
        shortcut_files = list(creator_shortcut_folder.glob("*.lnk"))
        if shortcut_files:
            logging.info("  → Found %d shortcut(s) for creator '%s':", len(shortcut_files), login.profile_name)
            for shortcut in shortcut_files:
                logging.info("    • %s", shortcut.name)
        else:
            logging.warning("  → No shortcuts found in creator folder: %s", creator_shortcut_folder)

        # Step 2: TODO - Open shortcuts and perform uploads
        # For now, just log that we found the creator and its shortcuts
        logging.info("")
        logging.info("✓ Creator '%s' is ready for automation", login.profile_name)
        logging.info("  Shortcuts will be opened in browser when upload feature is implemented")
        logging.info("")

        # For now, return True since we're only logging shortcut discovery
        # Actual upload functionality will be added in next phase
        return True

    def _run_upload_workflow(self, profile_id: str, work_item: AccountWorkItem) -> None:
        """
        Run video upload workflow after profile opens.

        Coordinates:
        - Phase 2: Extract page names from folders
        - Phase 1: Open fresh tab and navigate bookmarks
        - Phase 4: Find and click Add Videos button
        """
        try:
            logging.info("")
            logging.info("[WORKFLOW] ═════════════════════════════════════════════")
            logging.info("[WORKFLOW] VIDEO UPLOAD WORKFLOW")
            logging.info("[WORKFLOW] ═════════════════════════════════════════════")
            logging.info("")

            # Build profiles root from creators_root with intelligent path detection
            # Actual folder structure (real):
            # .../creator_shortcuts/IX/email@domain.com/Creators/Profiles/[ProfileName]/Pages/[PageName]/

            profiles_root = None

            # Try multiple path configurations in order of likelihood
            candidates = [
                # Option 1: creators_root/Profiles (if creators_root points to Creators folder)
                work_item.creators_root / "Profiles",
                # Option 2: creators_root/Creators/Profiles (if creators_root points to email folder)
                work_item.creators_root / "Creators" / "Profiles",
                # Option 3: parent/Creators/Profiles (if creators_root is inside Creators)
                work_item.creators_root.parent / "Creators" / "Profiles",
            ]

            for i, candidate in enumerate([c for c in candidates if c], 1):
                if candidate and candidate.exists():
                    profiles_root = candidate
                    logging.info("[WORKFLOW] Found Profiles at attempt %d: %s", i, profiles_root)
                    break

            # Last resort: try to find the actual creator_shortcuts structure
            if not profiles_root or not profiles_root.exists():
                try:
                    # If creators_root is in Desktop/Toseeq, look for creator_shortcuts instead
                    if "Toseeq" in str(work_item.creators_root):
                        desktop = Path(work_item.creators_root).resolve().parents[1]  # go up to Desktop
                        creator_shortcuts = desktop / "creator_shortcuts" / "IX"

                        # Find the email folder
                        if creator_shortcuts.exists():
                            email_folders = list(creator_shortcuts.iterdir())
                            if email_folders:
                                profiles_root = email_folders[0] / "Creators" / "Profiles"
                                if profiles_root.exists():
                                    logging.info("[WORKFLOW] Found Profiles in creator_shortcuts: %s", profiles_root)
                except Exception as e:
                    logging.warning("[WORKFLOW] Error searching creator_shortcuts: %s", str(e))

            if not profiles_root or not profiles_root.exists():
                logging.error("[WORKFLOW] Could not find Profiles folder")
                logging.error("[WORKFLOW] Checked locations:")
                for candidate in [c for c in candidates if c]:
                    logging.error("[WORKFLOW]   - %s", candidate)
                return

            logging.info("[WORKFLOW] Using profiles root: %s", profiles_root)
            logging.info("[WORKFLOW] Profiles folder verified: %s", profiles_root.exists())

            # Initialize orchestrator with correct path
            orchestrator = UploadWorkflowOrchestrator(profiles_root=profiles_root)

            # Execute workflow
            success = orchestrator.execute_workflow(profile_id)

            if success:
                logging.info("")
                logging.info("[WORKFLOW] ✅ Workflow completed successfully")
                logging.info("[WORKFLOW] Ready to proceed with uploads")
            else:
                logging.warning("")
                logging.warning("[WORKFLOW] ⚠️ Workflow encountered issues")
                logging.warning("[WORKFLOW] Check logs for details")

            logging.info("[WORKFLOW] ═════════════════════════════════════════════")
            logging.info("")

        except Exception as e:
            logging.error("[WORKFLOW] ❌ Unexpected error in upload workflow: %s", str(e))
            import traceback
            logging.debug("[WORKFLOW] Traceback: %s", traceback.format_exc())

    @staticmethod
    def _resolve_window_title_hint(work_item: AccountWorkItem, login: CreatorLogin) -> Optional[str]:
        """Derive a sensible window-title hint for browser activation."""
        extras = login.extras or {}
        for key in ("window_title", "window_name", "window", "browser_window", "profile_window"):
            value = extras.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        config = work_item.browser_config or {}
        for key in ("window_title", "window_name", "browser_name"):
            value = config.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        shortcut_hint = config.get("desktop_shortcut")
        if isinstance(shortcut_hint, str) and shortcut_hint.strip():
            try:
                return Path(shortcut_hint).expanduser().stem
            except Exception:
                return shortcut_hint

        if login.profile_name:
            return login.profile_name

        if work_item.account_name:
            return work_item.account_name

        return work_item.browser_type

        # NOTE: Below is the old logic for direct file uploads - will be replaced with shortcut-based approach
        # videos = self._file_selector.get_pending_videos(
        #     creator_folder,
        #     tracker=tracker,
        #     browser_account=work_item.account_name,
        # )
        #
        # if not videos:
        #     logging.info("No pending videos for creator '%s'; nothing to upload.", login.profile_name)
        #     return True
        #
        # creator_success = True
        #
        # for video_path in videos:
        #     metadata = self._metadata_handler.load_metadata(creator_folder, video_path.name)
        #     logging.debug(
        #         "Uploading %s for creator '%s' with metadata keys: %s",
        #         video_path.name,
        #         login.profile_name,
        #         ", ".join(sorted(metadata.keys())) or "none",
        #     )
        #
        #     upload_ok = self._uploader.upload_single_video(
        #         driver=None,  # Driver wiring handled in upload module implementation
        #         video_path=video_path,
        #         metadata=metadata,
        #     )
        #
        #     status = "completed" if upload_ok else "failed"
        #     tracker.record_upload(
        #         creator=login.profile_name,
        #         video=video_path.name,
        #         status=status,
        #         account=work_item.account_name,
        #         browser_type=work_item.browser_type,
        #         metadata={
        #             "page_name": login.page_name,
        #             "page_id": login.page_id,
        #         },
        #     )
        #
        #     if not upload_ok:
        #         creator_success = False
        #         logging.error(
        #             "Upload failed for %s/%s",
        #             login.profile_name,
        #             video_path.name,
        #         )
        #
        # return creator_success
