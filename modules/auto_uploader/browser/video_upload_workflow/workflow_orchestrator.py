"""
Complete Workflow Orchestrator
Coordinates all phases: 2 → 1 → 4

Flow:
Phase 2: Extract page names (preparation)
Phase 1: Open fresh tab + navigate bookmarks
Phase 4: Find and click Add Videos button
"""

import logging
from pathlib import Path
from typing import List, Optional
import numpy as np

from .page_name_extractor import PageNameExtractor
from .fresh_tab_manager import FreshTabManager
from .bookmark_navigator import BookmarkNavigator
from .add_videos_finder import AddVideosFinder

logger = logging.getLogger(__name__)


class UploadWorkflowOrchestrator:
    """
    Complete bulletproof workflow orchestration.

    Phases:
    2. Extract page names from folders
    1. Open fresh tab + navigate bookmarks
    4. Find and click Add Videos button
    """

    def __init__(self, profiles_root: Optional[Path] = None, helper_images_path: Optional[Path] = None):
        """
        Initialize orchestrator.

        Args:
            profiles_root: Path to Profiles folder
            helper_images_path: Path to helper images folder
        """
        logger.info("╔════════════════════════════════════════╗")
        logger.info("║  BULLETPROOF UPLOAD WORKFLOW START     ║")
        logger.info("╚════════════════════════════════════════╝")

        self.page_extractor = PageNameExtractor(profiles_root)
        self.tab_manager = FreshTabManager()
        self.bookmark_navigator = BookmarkNavigator(helper_images_path)
        self.videos_finder = AddVideosFinder(helper_images_path)

        logger.info("[ORCHESTRATOR] All components initialized")

    def execute_workflow(self, profile_id: str) -> bool:
        """
        Execute complete workflow for a profile.

        Steps:
        1. Extract page names
        2. Open fresh tab
        3. For each page: navigate bookmark → find Add Videos button

        Args:
            profile_id: Profile identifier

        Returns:
            True if workflow completed successfully
        """
        logger.info(f"\n[ORCHESTRATOR] Starting workflow for: {profile_id}")

        # PHASE 2: Extract page names
        logger.info("\n[ORCHESTRATOR] ═════════════════════════════════════════════")
        logger.info("[ORCHESTRATOR] PHASE 2: Extract Page Names")
        logger.info("[ORCHESTRATOR] ═════════════════════════════════════════════")

        page_names = self.page_extractor.extract_page_names(profile_id)

        if not page_names:
            logger.error("[ORCHESTRATOR] ❌ No pages found for profile")
            return False

        logger.info(f"[ORCHESTRATOR] ✅ Found {len(page_names)} pages:")
        for pname in page_names:
            logger.info(f"[ORCHESTRATOR]    - {pname}")

        # PHASE 1: Open fresh tab
        logger.info("\n[ORCHESTRATOR] ═════════════════════════════════════════════")
        logger.info("[ORCHESTRATOR] PHASE 1: Fresh Tab Setup")
        logger.info("[ORCHESTRATOR] ═════════════════════════════════════════════")

        if not self.tab_manager.open_fresh_tab():
            logger.error("[ORCHESTRATOR] ❌ Failed to open fresh tab")
            return False

        if not self.tab_manager.ensure_bookmark_bar_visible():
            logger.error("[ORCHESTRATOR] ❌ Failed to show bookmark bar")
            return False

        if not self.tab_manager.verify_ready():
            logger.error("[ORCHESTRATOR] ❌ Tab not ready")
            return False

        logger.info("[ORCHESTRATOR] ✅ Fresh tab ready")

        # Process each page
        success_count = 0
        failure_count = 0

        for page_name in page_names:
            logger.info(f"\n[ORCHESTRATOR] ─────────────────────────────────────────────")
            logger.info(f"[ORCHESTRATOR] Processing: {page_name}")
            logger.info(f"[ORCHESTRATOR] ─────────────────────────────────────────────")

            # PHASE 1B: Navigate bookmark
            logger.info(f"[ORCHESTRATOR] PHASE 1B: Navigate to page")

            screenshot = self._capture_screenshot()

            if not self.bookmark_navigator.find_and_click_bookmark(page_name, screenshot):
                logger.warning(f"[ORCHESTRATOR] ⚠️ Failed to click bookmark: {page_name}")
                failure_count += 1
                continue  # Try next page

            logger.info(f"[ORCHESTRATOR] ✅ Bookmark clicked")

            # PHASE 4: Find Add Videos button
            logger.info(f"[ORCHESTRATOR] PHASE 4: Find Add Videos button")

            screenshot = self._capture_screenshot()

            if self.videos_finder.find_and_click_button(screenshot):
                logger.info(f"[ORCHESTRATOR] ✅ SUCCESS: {page_name} ready for upload")
                success_count += 1
            else:
                logger.warning(f"[ORCHESTRATOR] ❌ Failed to find Add Videos for: {page_name}")
                failure_count += 1

        # Final summary
        logger.info(f"\n[ORCHESTRATOR] ═════════════════════════════════════════════")
        logger.info(f"[ORCHESTRATOR] WORKFLOW SUMMARY")
        logger.info(f"[ORCHESTRATOR] ═════════════════════════════════════════════")
        logger.info(f"[ORCHESTRATOR] Total pages: {len(page_names)}")
        logger.info(f"[ORCHESTRATOR] ✅ Success: {success_count}")
        logger.info(f"[ORCHESTRATOR] ❌ Failed: {failure_count}")
        logger.info(f"[ORCHESTRATOR] Success rate: {success_count}/{len(page_names)} ({100*success_count//len(page_names)}%)")
        logger.info(f"[ORCHESTRATOR] ═════════════════════════════════════════════\n")

        return success_count > 0

    def _capture_screenshot(self) -> np.ndarray:
        """Capture current screenshot."""
        import pyautogui
        screenshot = pyautogui.screenshot()
        return np.array(screenshot)


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s"
    )

    # Run workflow
    orchestrator = UploadWorkflowOrchestrator()

    profile_id = "Nathaniel Cobb coocking"
    success = orchestrator.execute_workflow(profile_id)

    if success:
        print("\n✅ Workflow completed successfully!")
    else:
        print("\n❌ Workflow failed")
