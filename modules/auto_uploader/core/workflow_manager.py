"""Workflow Manager - Upload workflow logic for the modular uploader."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Sequence

from ..browser.launcher import BrowserLauncher
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
        logging.info("⚙ Step 1/3: Launching browser...")
        logging.info("  → Browser type: %s", work_item.browser_type)

        launcher = BrowserLauncher(config=work_item.browser_config)

        # Pass browser_config as kwargs to launcher (includes browser_name if specified)
        launch_kwargs = {'show_popup': True}
        launch_kwargs.update(work_item.browser_config)

        if 'browser_name' in launch_kwargs:
            logging.info("  → Browser name: %s", launch_kwargs['browser_name'])

        logging.info("  → Searching for browser shortcut on desktop...")

        if launcher.launch_generic(work_item.browser_type, **launch_kwargs):
            logging.info("  ✓ Browser launched successfully")
            logging.info("")
        else:
            logging.error("  ✗ Failed to launch browser")
            logging.error("")
            logging.error("BROWSER LAUNCH FAILED - Possible reasons:")
            logging.error("1. Browser shortcut not found on Desktop")
            logging.error("2. Browser not installed")
            logging.error("3. Incorrect browser name in login_data.txt")
            logging.error("")
            logging.error("What to check:")
            logging.error("  • Desktop should have browser shortcut (.lnk file)")
            logging.error("  • Browser name: %s", work_item.browser_config.get('browser_name', 'chrome'))
            logging.error("  • Available browsers: chrome, firefox, edge, brave, opera")
            return False

        if not work_item.login_entries:
            logging.info("⚠ No login entries - browser launched but no creators to process")
            return True

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

        creator_folder = work_item.creators_root / login.profile_name
        if not creator_folder.exists():
            logging.info("Creator folder not found for '%s'; skipping uploads.", login.profile_name)
            return True

        videos = self._file_selector.get_pending_videos(
            creator_folder,
            tracker=tracker,
            browser_account=work_item.account_name,
        )

        if not videos:
            logging.info("No pending videos for creator '%s'; nothing to upload.", login.profile_name)
            return True

        creator_success = True

        for video_path in videos:
            metadata = self._metadata_handler.load_metadata(creator_folder, video_path.name)
            logging.debug(
                "Uploading %s for creator '%s' with metadata keys: %s",
                video_path.name,
                login.profile_name,
                ", ".join(sorted(metadata.keys())) or "none",
            )

            upload_ok = self._uploader.upload_single_video(
                driver=None,  # Driver wiring handled in upload module implementation
                video_path=video_path,
                metadata=metadata,
            )

            status = "completed" if upload_ok else "failed"
            tracker.record_upload(
                creator=login.profile_name,
                video=video_path.name,
                status=status,
                account=work_item.account_name,
                browser_type=work_item.browser_type,
                metadata={
                    "page_name": login.page_name,
                    "page_id": login.page_id,
                },
            )

            if not upload_ok:
                creator_success = False
                logging.error(
                    "Upload failed for %s/%s",
                    login.profile_name,
                    video_path.name,
                )

        return creator_success
