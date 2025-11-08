"""
Base Approach Interface
=======================
All automation approaches must implement this interface.

This defines the contract that every approach (free_automation, ixbrowser, etc.)
must follow for consistent behavior.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging


@dataclass
class ApproachConfig:
    """
    Configuration for an approach

    Attributes:
        mode: Approach mode ('free_automation', 'ixbrowser', 'gologin', etc.)
        credentials: User credentials (email, password, API key, etc.)
        paths: Filesystem paths (creators_root, shortcuts_root)
        browser_type: Browser type ('chrome', 'ix', 'gologin')
        settings: Additional approach-specific settings
    """
    mode: str
    credentials: Dict[str, str]
    paths: Dict[str, Path]
    browser_type: str = 'chrome'
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CreatorData:
    """
    Data for a single creator account

    Attributes:
        profile_name: Creator profile name
        email: Login email
        password: Login password
        page_name: Facebook page name (optional)
        page_id: Facebook page ID (optional)
        extras: Additional metadata
    """
    profile_name: str
    email: str
    password: str
    page_name: str = ""
    page_id: str = ""
    extras: Dict[str, str] = field(default_factory=dict)


@dataclass
class WorkItem:
    """
    Work item for processing a single account

    Attributes:
        account_name: Name of the account (folder name)
        browser_type: Browser to use
        creators: List of creator accounts to process
        config: Approach configuration
        metadata: Additional per-account context (paths, raw configs, etc.)
    """
    account_name: str
    browser_type: str
    creators: List[CreatorData]
    config: ApproachConfig
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """
    Result of workflow execution

    Attributes:
        success: Whether workflow succeeded
        account_name: Account that was processed
        videos_uploaded: Number of videos uploaded
        creators_processed: Number of creators processed
        errors: List of error messages
    """
    success: bool
    account_name: str
    videos_uploaded: int = 0
    creators_processed: int = 0
    errors: List[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """Add an error message"""
        self.errors.append(error)
        logging.error(f"[{self.account_name}] {error}")


class BaseApproach(ABC):
    """
    Base class for all automation approaches

    Each approach must implement:
    1. Browser opening/closing
    2. Login/logout
    3. Video upload (or delegate to shared uploader)

    Example:
        >>> config = ApproachConfig(
        ...     mode='free_automation',
        ...     credentials={'email': 'user@example.com', 'password': 'xxx'},
        ...     paths={'creators_root': Path('/path/to/creators')},
        ...     browser_type='chrome'
        ... )
        >>> approach = FreeAutomationApproach(config)
        >>> result = approach.execute_workflow(work_item)
        >>> print(result.success)
    """

    def __init__(self, config: ApproachConfig):
        """
        Initialize approach

        Args:
            config: Approach configuration
        """
        self.config = config
        self._initialized = False

        logging.info(f"BaseApproach created: {self.__class__.__name__}")
        logging.debug(f"  Mode: {config.mode}")
        logging.debug(f"  Browser: {config.browser_type}")

    # ------------------------------------------------------------------ #
    # Abstract methods - MUST be implemented by subclasses               #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the approach components

        This is called once before any other operations.
        Use this to set up browser launchers, API clients, etc.

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    def open_browser(self, account_name: str) -> bool:
        """
        Open browser for the account

        This could be:
        - Desktop-based: Launch via .lnk shortcut
        - API-based: Open profile via API

        Args:
            account_name: Account folder name

        Returns:
            True if browser opened successfully
        """
        pass

    @abstractmethod
    def login(self, email: str, password: str) -> bool:
        """
        Login to Facebook with credentials

        This could be:
        - Image-based: Use screen detection and mouse automation
        - Selenium-based: Use direct element interaction

        Args:
            email: Login email
            password: Login password

        Returns:
            True if login successful
        """
        pass

    @abstractmethod
    def logout(self) -> bool:
        """
        Logout from current Facebook session

        Returns:
            True if logout successful
        """
        pass

    @abstractmethod
    def close_browser(self) -> bool:
        """
        Close the browser

        This could be:
        - Kill process (desktop-based)
        - Close via API (API-based)

        Returns:
            True if browser closed successfully
        """
        pass

    # ------------------------------------------------------------------ #
    # Optional methods - Can be overridden by subclasses                 #
    # ------------------------------------------------------------------ #

    def upload_video(self, video_path: Path, metadata: Dict) -> bool:
        """
        Upload a video with metadata

        Default implementation logs a warning.
        Override this in subclass for actual upload logic.

        Args:
            video_path: Path to video file
            metadata: Video metadata (title, description, etc.)

        Returns:
            True if upload successful
        """
        logging.warning(f"upload_video() not implemented in {self.__class__.__name__}")
        logging.info(f"Would upload: {video_path}")
        return False

    def cleanup(self) -> None:
        """
        Cleanup resources

        Called after workflow completes (success or failure).
        Override to add cleanup logic.
        """
        logging.debug(f"Cleanup called for {self.__class__.__name__}")

    # ------------------------------------------------------------------ #
    # Concrete methods - Provided by base class                          #
    # ------------------------------------------------------------------ #

    def execute_workflow(self, work_item: WorkItem) -> WorkflowResult:
        """
        Execute complete workflow for an account

        This is the main entry point. It orchestrates the workflow:
        1. Initialize
        2. Open browser
        3. For each creator: login → upload → logout
        4. Close browser
        5. Cleanup

        Args:
            work_item: Work item containing account and creators

        Returns:
            WorkflowResult with success status and details
        """
        result = WorkflowResult(
            success=False,
            account_name=work_item.account_name
        )

        logging.info("")
        logging.info("="*60)
        logging.info(f"EXECUTING WORKFLOW: {work_item.account_name}")
        logging.info(f"Approach: {self.__class__.__name__}")
        logging.info(f"Creators: {len(work_item.creators)}")
        logging.info("="*60)
        logging.info("")

        try:
            # Step 1: Initialize
            if not self._initialized:
                logging.info("📋 Step 1/5: Initializing approach...")
                if not self.initialize():
                    result.add_error("Initialization failed")
                    return result
                self._initialized = True
                logging.info("✅ Initialization successful")

            # Step 2: Open browser
            logging.info("")
            logging.info("📋 Step 2/5: Opening browser...")
            if not self.open_browser(work_item.account_name):
                result.add_error("Failed to open browser")
                return result
            logging.info("✅ Browser opened successfully")

            # Step 3: Process each creator
            logging.info("")
            logging.info(f"📋 Step 3/5: Processing {len(work_item.creators)} creator(s)...")

            for idx, creator in enumerate(work_item.creators, 1):
                logging.info("")
                logging.info("-"*60)
                logging.info(f"Creator {idx}/{len(work_item.creators)}: {creator.profile_name}")
                logging.info("-"*60)

                # Login
                logging.info(f"🔐 Logging in as: {creator.email}")
                if not self.login(creator.email, creator.password):
                    result.add_error(f"Login failed for {creator.email}")
                    continue  # Try next creator

                logging.info("✅ Login successful")

                # Upload videos (placeholder for now)
                # TODO: Implement video selection and upload
                logging.info("📤 Video upload (not implemented yet)")

                # Logout
                logging.info("🔓 Logging out...")
                if not self.logout():
                    result.add_error(f"Logout failed for {creator.email}")
                    # Continue anyway
                else:
                    logging.info("✅ Logout successful")

                result.creators_processed += 1

            # Step 4: Close browser
            logging.info("")
            logging.info("📋 Step 4/5: Closing browser...")
            if not self.close_browser():
                result.add_error("Failed to close browser")
                # Don't return, continue to cleanup
            else:
                logging.info("✅ Browser closed")

            # Step 5: Cleanup
            logging.info("")
            logging.info("📋 Step 5/5: Cleanup...")
            self.cleanup()
            logging.info("✅ Cleanup complete")

            # Determine success
            result.success = len(result.errors) == 0

            logging.info("")
            logging.info("="*60)
            if result.success:
                logging.info("✅ WORKFLOW COMPLETED SUCCESSFULLY")
            else:
                logging.warning(f"⚠️  WORKFLOW COMPLETED WITH {len(result.errors)} ERROR(S)")
                for error in result.errors:
                    logging.warning(f"   - {error}")
            logging.info(f"Creators processed: {result.creators_processed}/{len(work_item.creators)}")
            logging.info("="*60)
            logging.info("")

            return result

        except Exception as e:
            logging.error(f"❌ Unexpected error in workflow: {e}", exc_info=True)
            result.add_error(f"Unexpected error: {e}")

            # Attempt cleanup
            try:
                self.cleanup()
            except Exception as cleanup_error:
                logging.error(f"Cleanup error: {cleanup_error}")

            return result

    def __str__(self) -> str:
        """String representation"""
        return f"{self.__class__.__name__}(mode={self.config.mode}, browser={self.config.browser_type})"

    def __repr__(self) -> str:
        """Debug representation"""
        return self.__str__()
