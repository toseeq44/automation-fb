"""File Selector - Video file selection logic."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..tracking.upload_tracker import UploadTracker


class FileSelector:
    """Selects candidate videos for upload."""

    DEFAULT_EXTENSIONS: Tuple[str, ...] = (".mp4", ".mov", ".mkv", ".avi", ".wmv")

    def __init__(self) -> None:
        logging.debug("FileSelector initialized")

    def get_pending_videos(
        self,
        creator_path: Path,
        tracker: Optional[UploadTracker] = None,
        *,
        browser_account: Optional[str] = None,
        skip_uploaded: bool = True,
        extensions: Optional[Sequence[str]] = None,
        max_count: Optional[int] = None,
    ) -> List[Path]:
        """
        Return a list of videos that are pending upload for the given creator.

        Args:
            creator_path: Path to the creator's folder.
            tracker: UploadTracker instance for duplicate detection.
            browser_account: Optional browser account name (for logging only).
            skip_uploaded: Skip files already marked as completed in tracker.
            extensions: Allowed file extensions (defaults to common video formats).
            max_count: Optional limit on the number of files returned.
        """
        allowed_extensions = tuple(ext.lower() for ext in (extensions or self.DEFAULT_EXTENSIONS))

        if not creator_path.exists():
            logging.warning("Creator path does not exist: %s", creator_path)
            return []

        videos = [
            path
            for path in sorted(creator_path.iterdir())
            if path.is_file() and path.suffix.lower() in allowed_extensions
        ]

        logging.debug(
            "Found %d video(s) for creator '%s'%s",
            len(videos),
            creator_path.name,
            f" (account={browser_account})" if browser_account else "",
        )

        if skip_uploaded and tracker:
            videos = [path for path in videos if not tracker.was_uploaded(creator_path.name, path.name)]

        if max_count is not None and max_count > 0:
            videos = videos[:max_count]

        return videos

    def filter_by_criteria(self, videos: Iterable[Path], criteria: Dict[str, object]) -> List[Path]:
        """
        Apply simple filtering rules to a list of video paths.

        Supported criteria keys:
            - max_count (int): limit number of entries
            - extensions (Sequence[str]): override extensions filter
        """
        result = list(videos)

        max_count = criteria.get("max_count")
        if isinstance(max_count, int) and max_count > 0:
            result = result[:max_count]

        allowed_extensions = criteria.get("extensions")
        if allowed_extensions:
            allowed = {ext.lower() for ext in allowed_extensions if isinstance(ext, str)}
            result = [path for path in result if path.suffix.lower() in allowed]

        return result
