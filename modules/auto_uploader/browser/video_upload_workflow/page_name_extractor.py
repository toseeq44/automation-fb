"""
PHASE 2: Page Name Extractor
Extracts page names from local folder structure (preparation step)

Folder Structure:
Profiles/[ProfileID]/Pages/[PageName]/
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class PageNameExtractor:
    """Extract page names from Profiles/[ID]/Pages/ folders."""

    def __init__(self, profiles_root: Optional[Path] = None):
        """
        Initialize extractor.

        Args:
            profiles_root: Path to Profiles folder (default: cwd/Profiles)
        """
        if profiles_root is None:
            profiles_root = Path.cwd() / "Profiles"

        self.profiles_root = profiles_root
        logger.info("[PHASE 2] PageNameExtractor initialized")
        logger.info(f"[PHASE 2] Profiles root: {self.profiles_root}")

    def extract_page_names(self, profile_id: str) -> List[str]:
        """
        Extract page names for a profile.

        Args:
            profile_id: Profile folder name

        Returns:
            Sorted list of page names
        """
        logger.info(f"[PHASE 2] Extracting pages for: {profile_id}")

        pages_path = self.profiles_root / profile_id / "Pages"

        if not pages_path.exists():
            logger.error(f"[PHASE 2] ❌ Pages folder not found: {pages_path}")
            return []

        page_names = []

        try:
            for item in pages_path.iterdir():
                if item.is_dir():
                    page_name = item.name.strip()
                    if page_name:
                        page_names.append(page_name)
                        logger.debug(f"[PHASE 2]   ✅ Found: {page_name}")

        except Exception as e:
            logger.error(f"[PHASE 2] ❌ Error: {e}")
            return []

        page_names.sort()

        if page_names:
            logger.info(f"[PHASE 2] ✅ Found {len(page_names)} pages")
            for pname in page_names:
                logger.info(f"[PHASE 2]    - {pname}")
        else:
            logger.warning(f"[PHASE 2] ⚠️  No pages found")

        return page_names

    def extract_all_profiles(self) -> Dict[str, List[str]]:
        """Extract all profiles with their pages."""
        logger.info("[PHASE 2] Extracting all profiles...")

        if not self.profiles_root.exists():
            logger.error(f"[PHASE 2] ❌ Profiles root not found: {self.profiles_root}")
            return {}

        all_profiles = {}

        try:
            for profile_folder in self.profiles_root.iterdir():
                if profile_folder.is_dir():
                    profile_id = profile_folder.name
                    pages = self.extract_page_names(profile_id)
                    if pages:
                        all_profiles[profile_id] = pages

        except Exception as e:
            logger.error(f"[PHASE 2] ❌ Error: {e}")

        logger.info(f"[PHASE 2] ✅ Total profiles: {len(all_profiles)}")
        return all_profiles
