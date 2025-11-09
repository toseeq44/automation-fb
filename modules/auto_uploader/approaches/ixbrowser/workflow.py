"""Automation approach that controls ixBrowser via its Local API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..base_approach import (
    ApproachConfig,
    BaseApproach,
    CreatorData,
    WorkItem,
    WorkflowResult,
)
from ...browser.profile_selector import IXProfileSelector
from ...browser.launcher import BrowserLauncher
from .api_client import IXBrowserAPI, IXBrowserAPIError, IXProfileInfo, IXProfileSession

try:
    import pygetwindow as gw

    HAS_PYGETWINDOW = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_PYGETWINDOW = False
    gw = None
    logging.warning("pygetwindow not available. Install: pip install pygetwindow to enable window focusing.")

logger = logging.getLogger(__name__)


@dataclass
class IXAutomationContext:
    """Holds state for a specific ixBrowser session."""

    profile: IXProfileInfo
    session: IXProfileSession


class IXBrowserApproach(BaseApproach):
    """Use ixBrowser Local API to open/close profiles instead of desktop automation."""

    def __init__(self, config: ApproachConfig) -> None:
        super().__init__(config)
        credentials = config.credentials or {}

        self._api_url = (
            credentials.get("api_url")
            or credentials.get("api_host")
            or credentials.get("api_base")
            or credentials.get("api_endpoint")
            or credentials.get("base_url")
            or "http://127.0.0.1:53200/v2"
        )

        self._api_key = (
            credentials.get("api_key")
            or credentials.get("token")
            or credentials.get("api_token")
            or ""
        )

        if not credentials.get("api_url") and self._api_key.startswith("http"):
            logger.info(
                "[IX] Detected legacy configuration where API key stored the base URL. "
                "Using it as api_url instead."
            )
            self._api_url = self._api_key
            self._api_key = ""

        self._client: Optional[IXBrowserAPI] = None

        try:
            self._client = IXBrowserAPI(base_url=self._api_url, api_key=self._api_key)
        except IXBrowserAPIError as exc:
            logger.error("Unable to initialize ixBrowser API client: %s", exc)
            self._client = None

    # ------------------------------------------------------------------ #
    # BaseApproach contract                                              #
    # ------------------------------------------------------------------ #
    def initialize(self) -> bool:
        return self._client is not None

    def open_browser(self, account_name: str) -> bool:
        # Browser lifecycle is handled inside execute_workflow for ixBrowser.
        return True

    def login(self, email: str, password: str) -> bool:
        return True

    def logout(self) -> bool:
        return True

    def close_browser(self) -> bool:
        return True

    # ------------------------------------------------------------------ #
    # Main workflow                                                      #
    # ------------------------------------------------------------------ #
    def execute_workflow(self, work_item: WorkItem) -> WorkflowResult:
        result = WorkflowResult(success=False, account_name=work_item.account_name)

        if not self._ensure_ix_browser_ready(work_item):
            result.add_error(
                "Unable to open ixBrowser via desktop shortcut. "
                "Please confirm the shortcut exists on your Desktop or shortcuts folder."
            )
            return result

        if not self._client:
            result.add_error(
                "ixBrowser API client is not initialized. Verify the API URL in Approaches settings."
            )
            return result

        profile_identifier, is_explicit = self._resolve_profile_identifier(work_item)
        profile = self._client.find_profile(profile_identifier)
        if not profile and is_explicit:
            logger.info("[IX] Using explicit profile identifier '%s' without API lookup.", profile_identifier)
            profile = IXProfileInfo(
                profile_id=profile_identifier,
                profile_name=profile_identifier,
                status="",
                raw={},
            )
        elif not profile:
            self._log_available_profiles()
            result.add_error(
                f"Unable to find ixBrowser profile matching '{profile_identifier}'. "
                "Open ixBrowser and confirm the profile exists."
            )
            return result

        logger.info(
            "[IX] Opening profile '%s' (%s) using ixBrowser Local API...",
            profile.profile_name,
            profile.profile_id,
        )

        try:
            session = self._client.open_profile(
                profile.profile_id,
                cookies_backup=False,
                load_profile_info_page=False,
            )
        except IXBrowserAPIError as exc:
            result.add_error(f"ixBrowser refused to open profile '{profile.profile_id}': {exc}")
            return result

        context = IXAutomationContext(profile=profile, session=session)
        logger.info("[IX] Profile opened successfully. Debugging address: %s", session.debugging_address)

        try:
            self._run_placeholder_workflow(work_item, context, result)
        finally:
            self._safe_close_profile(profile.profile_id)

        return result

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _ensure_ix_browser_ready(self, work_item: WorkItem) -> bool:
        """Ensure ixBrowser is running and visible."""
        launcher = BrowserLauncher()

        if launcher.is_browser_running("ix"):
            logging.info("[IX] Browser process detected. Bringing window to foreground...")
            self._maximize_ix_window()
            return True

        logging.error("[IX] ixBrowser is not running. Please open ixBrowser manually and try again.")
        return False

    def _run_placeholder_workflow(
        self,
        work_item: WorkItem,
        context: IXAutomationContext,
        result: WorkflowResult,
    ) -> None:
        """
        Placeholder automation logic.

        TODO(shipping soon): Attach Selenium to context.session, run the upload workflow,
        and mark success. For now we only prove that we can open/close profiles via API.
        """
        logger.warning(
            "[IX] Selenium automation not wired yet. "
            "Use the debugging address to attach your own scripts: %s",
            context.session.debugging_address or "N/A",
        )

        for creator in work_item.creators:
            self._log_creator_placeholder(creator)

        result.add_error(
            "ixBrowser profile opened successfully, but the Selenium upload workflow "
            "is not implemented yet. Attach to the debugging address and run your "
            "scripts manually, or switch back to Free Automation until the next update."
        )
        result.creators_processed = 0
        result.success = False

    @staticmethod
    def _log_creator_placeholder(creator: CreatorData) -> None:
        logger.info(
            "[IX] Placeholder: would now process creator '%s' (email=%s, page=%s)",
            creator.profile_name,
            creator.email,
            creator.page_name or "-",
        )

    def _safe_close_profile(self, profile_id: str) -> None:
        if not self._client:
            return
        try:
            self._client.close_profile(profile_id)
            logger.info("[IX] Profile '%s' closed.", profile_id)
        except IXBrowserAPIError as exc:
            logger.error("[IX] Failed to close profile '%s': %s", profile_id, exc)

    def _resolve_profile_identifier(self, work_item: WorkItem) -> tuple[str, bool]:
        credentials = self.config.credentials or {}
        explicit_candidates = [
            credentials.get("profile_id"),
            credentials.get("profile_name"),
        ]

        for candidate in explicit_candidates:
            if candidate:
                return candidate.strip(), True

        secondary_candidates = [
            credentials.get("email"),
            credentials.get("username"),
        ]

        for candidate in secondary_candidates:
            if candidate:
                return candidate.strip(), False

        metadata = work_item.metadata or {}
        login_meta: Dict[str, str] = metadata.get("login_metadata") or {}

        candidates = [
            login_meta.get("profile_id"),
            login_meta.get("ix_profile_id"),
            login_meta.get("profile_name"),
            login_meta.get("ix_profile_name"),
            metadata.get("profile_id"),
            metadata.get("profile_name"),
        ]

        for candidate in candidates:
            if candidate:
                return candidate.strip()

        names_raw = login_meta.get("profile_names") or metadata.get("profile_names")
        if names_raw:
            parsed = IXProfileSelector.parse_profile_names(names_raw)
            if parsed:
                return parsed[0], False

        fallback = self._default_profile_from_api()
        if fallback:
            logger.info(
                "[IX] No explicit profile specified; defaulting to '%s' (%s)",
                fallback.profile_name,
                fallback.profile_id,
            )
            return fallback.profile_id, False

        # Last resort: use account name.
        return work_item.account_name, False

    def _default_profile_from_api(self) -> Optional[IXProfileInfo]:
        if not self._client:
            return None
        try:
            profiles = self._client.list_profiles(use_cache=False)
        except IXBrowserAPIError as exc:
            logger.error("[IX] Unable to list ixBrowser profiles: %s", exc)
            return None
        return profiles[0] if profiles else None

    def _log_available_profiles(self) -> None:
        if not self._client:
            return
        try:
            profiles = self._client.list_profiles(use_cache=False)
        except IXBrowserAPIError as exc:
            logger.error("[IX] Unable to fetch profile list: %s", exc)
            return

        if not profiles:
            logger.warning("[IX] Local API reports no profiles. Create one inside ixBrowser first.")
            return

        logger.info("[IX] Available profiles from local API:")
        for profile in profiles:
            logger.info("    - %s (%s)", profile.profile_name, profile.profile_id)

    def _maximize_ix_window(self) -> bool:
        if not HAS_PYGETWINDOW or gw is None:
            logging.warning("[IX] pygetwindow not available; cannot focus ixBrowser window.")
            return False

        title_candidates = [
            "Incogniton",
            "IX Browser",
            "ixbrowser",
            "Incogniton Browser",
        ]

        for title in title_candidates:
            windows = gw.getWindowsWithTitle(title)
            for window in windows:
                try:
                    if window.isMinimized:
                        window.restore()
                    window.activate()
                    window.maximize()
                    logging.info("[IX] Activated window: %s", window.title)
                    return True
                except Exception as exc:  # pragma: no cover - pygetwindow specifics
                    logging.debug("[IX] Failed to activate window '%s': %s", window, exc)

        logging.warning("[IX] Unable to locate ixBrowser window to activate.")
        return False
