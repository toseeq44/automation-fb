"""IX Browser specific approach (placeholder implementation)."""

from __future__ import annotations

import logging

from ..base_approach import ApproachConfig, BaseApproach, WorkItem, WorkflowResult

logger = logging.getLogger(__name__)


class IXBrowserApproach(BaseApproach):
    """
    Placeholder implementation for ixBrowser automation.

    The class wires into the approach factory so that selecting the IX mode
    no longer falls back to the Free Automation workflow. Future updates
    should replace the placeholder logic with the actual ixBrowser pipeline.
    """

    def __init__(self, config: ApproachConfig) -> None:
        super().__init__(config)
        logger.info("[IXBrowserApproach] Initialized (mode=%s)", config.mode)

    def initialize(self) -> bool:  # pragma: no cover - not used yet
        return True

    def open_browser(self, account_name: str) -> bool:  # pragma: no cover - not used yet
        return False

    def login(self, email: str, password: str) -> bool:  # pragma: no cover - not used yet
        return False

    def logout(self) -> bool:  # pragma: no cover - not used yet
        return True

    def close_browser(self) -> bool:  # pragma: no cover - not used yet
        return True

    def execute_workflow(self, work_item: WorkItem) -> WorkflowResult:
        """Stop-gap implementation that informs the user about missing workflow."""
        result = WorkflowResult(success=False, account_name=work_item.account_name)
        message = (
            "IX Browser workflow is not implemented yet. "
            "Please keep using Free Automation or complete the upcoming IX workflow tasks."
        )
        logger.warning("[IXBrowserApproach] %s", message)
        result.add_error(message)
        return result
