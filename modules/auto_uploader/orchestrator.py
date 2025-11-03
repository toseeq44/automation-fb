"""Compatibility wrapper that routes to the new modular orchestrator."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .auth.credential_manager import CredentialManager
from .config.settings_manager import SettingsManager
from .core.orchestrator import UploadOrchestrator


class AutomationOrchestrator:
    """
    Backwards compatible orchestrator that delegates to the new modular workflow.

    Older code paths expected an object named ``AutomationOrchestrator`` that exposed
    a ``run()`` method. The new architecture centres around ``UploadOrchestrator`` in
    ``modules.auto_uploader.core``. This adapter preserves the previous entry point
    while exercising the modern pipeline.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        settings: Optional[SettingsManager] = None,
        credentials: Optional[CredentialManager] = None,
    ) -> None:
        self.base_dir = Path(base_dir or Path(__file__).parent)
        self.settings = settings or SettingsManager()
        self.credentials = credentials or CredentialManager()
        self._delegate = UploadOrchestrator(settings=self.settings, credentials=self.credentials)
        logging.debug("AutomationOrchestrator initialized (modular delegate enabled)")

    def run(self, mode: Optional[str] = None) -> bool:
        """Expose the legacy ``run`` API while delegating to the modular orchestrator."""
        return self._delegate.run(mode=mode)
