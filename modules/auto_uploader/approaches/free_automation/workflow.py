"""Concrete implementation of the Free Automation approach."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from ..base_approach import ApproachConfig, BaseApproach, WorkItem, WorkflowResult
from ...core.workflow_manager import (
    AccountWorkItem,
    CreatorLogin,
    WorkflowContext,
    WorkflowManager,
)

logger = logging.getLogger(__name__)


class FreeAutomationApproach(BaseApproach):
    """Delegates account processing to the legacy WorkflowManager."""

    def __init__(self, config: ApproachConfig) -> None:
        super().__init__(config)
        self._workflow_manager = WorkflowManager()
        self._context = WorkflowContext(history_file=self._resolve_history_path())
        logger.debug(
            "[FreeAutomationApproach] Initialized (history=%s)",
            self._context.history_file,
        )

    # ------------------------------------------------------------------ #
    # BaseApproach requirements (unused in delegated mode)               #
    # ------------------------------------------------------------------ #
    def initialize(self) -> bool:  # pragma: no cover - not used yet
        return True

    def open_browser(self, account_name: str) -> bool:  # pragma: no cover - not used yet
        logger.debug("[FreeAutomationApproach] open_browser called for %s", account_name)
        return True

    def login(self, email: str, password: str) -> bool:  # pragma: no cover - not used yet
        logger.debug("[FreeAutomationApproach] login called for %s", email)
        return True

    def logout(self) -> bool:  # pragma: no cover - not used yet
        return True

    def close_browser(self) -> bool:  # pragma: no cover - not used yet
        return True

    # ------------------------------------------------------------------ #
    # Delegated workflow                                                 #
    # ------------------------------------------------------------------ #
    def execute_workflow(self, work_item: WorkItem) -> WorkflowResult:
        """Run the legacy workflow manager for the given account."""
        result = WorkflowResult(success=False, account_name=work_item.account_name)

        account_item = self._resolve_account_work_item(work_item)
        if account_item is None:
            result.add_error("Missing account context for free automation workflow.")
            return result

        logger.info(
            "[FreeAutomationApproach] Delegating account '%s' (browser=%s)",
            account_item.account_name,
            account_item.browser_type,
        )

        success = self._workflow_manager.execute_account(account_item, self._context)
        result.success = success
        result.creators_processed = len(account_item.login_entries)

        if not success:
            result.add_error(
                "Free automation workflow reported failure for this account. "
                "Check detailed logs above for the root cause."
            )

        return result

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #
    def _resolve_history_path(self) -> Path:
        path_value = self.config.paths.get("history_file")
        if path_value:
            return Path(path_value).resolve()
        # Fallback to module-relative default
        return Path(__file__).resolve().parents[3] / "data" / "upload_tracking.json"

    def _resolve_account_work_item(self, work_item: WorkItem) -> Optional[AccountWorkItem]:
        metadata = work_item.metadata or {}
        cached = metadata.get("account_work_item")
        if isinstance(cached, AccountWorkItem):
            return cached

        logger.debug(
            "[FreeAutomationApproach] Rebuilding AccountWorkItem for %s",
            work_item.account_name,
        )
        return self._rebuild_account_work_item(work_item, metadata)

    def _rebuild_account_work_item(
        self,
        work_item: WorkItem,
        metadata: Dict[str, object],
    ) -> Optional[AccountWorkItem]:
        creators_root = self.config.paths.get("creators_root")
        shortcuts_root = self.config.paths.get("shortcuts_root")
        if creators_root is None or shortcuts_root is None:
            logger.error(
                "[FreeAutomationApproach] creators_root/shortcuts_root missing from config."
            )
            return None

        creators_root_path = Path(creators_root).resolve()
        shortcuts_root_path = Path(shortcuts_root).resolve()

        login_entries = tuple(
            CreatorLogin(
                profile_name=creator.profile_name,
                email=creator.email,
                password=creator.password,
                page_name=creator.page_name,
                page_id=creator.page_id,
                extras=dict(creator.extras),
            )
            for creator in work_item.creators
        )

        login_data_path = metadata.get("login_data_path")
        if login_data_path:
            login_path = Path(login_data_path).resolve()
        else:
            login_path = shortcuts_root_path / work_item.account_name / "login_data.txt"

        browser_config = metadata.get("browser_config", {})
        if isinstance(browser_config, dict):
            browser_payload = dict(browser_config)
        else:
            browser_payload = {}

        account_metadata = metadata.get("login_metadata")
        if isinstance(account_metadata, dict):
            meta_payload = dict(account_metadata)
        else:
            meta_payload = {}

        return AccountWorkItem(
            account_name=work_item.account_name,
            browser_type=work_item.browser_type,
            login_entries=login_entries,
            login_data_path=login_path,
            creators_root=creators_root_path,
            shortcuts_root=shortcuts_root_path,
            browser_config=browser_payload,
            automation_mode=self.config.mode,
            metadata=meta_payload,
        )
