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
        logging.info(
            "Running workflow for account '%s' (browser=%s, creators=%d)",
            work_item.account_name,
            work_item.browser_type,
            len(work_item.login_entries),
        )

        launcher = BrowserLauncher(config=work_item.browser_config)
        if launcher.launch_generic(work_item.browser_type, show_popup=True):
            logging.info(
                "Browser '%s' launched for account '%s'.",
                work_item.browser_type,
                work_item.account_name,
            )
        else:
            logging.error(
                "Unable to launch browser '%s' for account '%s'.",
                work_item.browser_type,
                work_item.account_name,
            )
            return False

        if not work_item.login_entries:
            logging.info(
                "No login entries found for account '%s'; finishing after browser launch.",
                work_item.account_name,
            )
            return True

        tracker = UploadTracker(context.history_file)
        account_success = True

        for login in work_item.login_entries:
            creator_success = self._process_creator(login, work_item, tracker)
            account_success = account_success and creator_success

        try:
            tracker.flush()
        except Exception:  # pragma: no cover - IO guard
            logging.exception("Unable to persist upload history to %s", context.history_file)

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
