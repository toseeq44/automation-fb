"""Upload Orchestrator - Main entry point for the modular workflow."""

import logging
from typing import Optional

from ..auth.credential_manager import CredentialManager
from ..config.settings_manager import SettingsManager
from .workflow_manager import WorkflowManager


class UploadOrchestrator:
    """Main orchestrator for upload workflow."""

    def __init__(
        self,
        settings: Optional[SettingsManager] = None,
        credentials: Optional[CredentialManager] = None,
    ):
        self.settings = settings or SettingsManager()
        self.credentials = credentials or CredentialManager()
        self.workflow_manager = WorkflowManager()
        logging.debug("UploadOrchestrator initialized")

    def run(self, mode: Optional[str] = None) -> bool:
        """Run main upload workflow."""
        automation_mode = mode or self.settings.get_automation_mode()
        logging.info("Starting upload orchestrator (mode=%s)...", automation_mode)

        # Placeholder for the modular workflow until full integration is complete.
        # Log current settings and exit successfully so the GUI can progress.
        automation_settings = self.settings.get_settings().get("automation", {})
        logging.debug("Automation settings: %s", automation_settings)

        # TODO: Replace with real workflow integration.
        return True
