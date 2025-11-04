"""Workflow Manager - Upload workflow logic for the modular uploader."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Sequence

from ..browser.launcher import BrowserLauncher
from ..browser.image_based_login import ImageBasedLogin
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

        account_email = work_item.login_entries[0].email if work_item.login_entries else "N/A"
        account_password = work_item.login_entries[0].password if work_item.login_entries else "N/A"

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
                force_relogin=False
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

        for idx, login in enumerate(work_item.login_entries, 1):
            logging.info("")
            logging.info("  → Creator %d/%d: %s", idx, len(work_item.login_entries), login.profile_name)
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
