"""
Folder Queue Manager for ixBrowser Approach

Handles folder queue management and infinite loop:
- Discovers all creator folders
- Tracks current position in queue
- Manages folder completion
- Implements infinite loop (cycle back to folder #1)
- Tracks cycle count

Usage:
    queue_mgr = FolderQueueManager(base_path="/path/to/creator_data")
    current_folder = queue_mgr.get_current_folder()
    videos = queue_mgr.get_videos_in_folder(current_folder)
    queue_mgr.mark_current_folder_complete()
    queue_mgr.move_to_next_folder()
"""

import logging
import os
import glob
from typing import List, Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class FolderQueueManager:
    """Manages folder queue and infinite loop logic."""

    def __init__(self, base_path: str, state_manager=None):
        """
        Initialize Folder Queue Manager.

        Args:
            base_path: Path to creator_data directory
            state_manager: StateManager instance for persistence
        """
        self.base_path = Path(base_path)
        self.state_manager = state_manager

        # Video file extensions
        self.video_extensions = ['*.mp4', '*.mov', '*.avi', '*.mkv', '*.wmv',
                                 '*.MP4', '*.MOV', '*.AVI', '*.MKV', '*.WMV']

        logger.info("[FolderQueue] Initialized with base_path: %s", self.base_path)

    def get_all_folders(self) -> List[str]:
        """
        Get all creator folders in base_path (sorted).

        Returns:
            List of folder paths (absolute)
        """
        try:
            if not self.base_path.exists():
                logger.error("[FolderQueue] Base path does not exist: %s", self.base_path)
                return []

            # Get all subdirectories
            folders = [
                str(folder) for folder in self.base_path.iterdir()
                if folder.is_dir() and not folder.name.startswith('.')
            ]

            # Sort for consistent ordering
            folders.sort()

            logger.info("[FolderQueue] Found %d creator folder(s)", len(folders))
            return folders

        except Exception as e:
            logger.error("[FolderQueue] Error getting folders: %s", str(e))
            return []

    def get_current_folder_index(self) -> int:
        """
        Get current folder index from state.

        Returns:
            Current folder index (0-based)
        """
        if self.state_manager:
            position = self.state_manager.get_current_position()
            return position.get('folder_index', 0)
        return 0

    def get_current_folder(self) -> Optional[str]:
        """
        Get current folder path based on state.

        Returns:
            Current folder path or None
        """
        folders = self.get_all_folders()
        if not folders:
            logger.warning("[FolderQueue] No folders found")
            return None

        index = self.get_current_folder_index()

        # Validate index
        if index >= len(folders):
            logger.warning("[FolderQueue] Index %d >= folder count %d, resetting to 0",
                         index, len(folders))
            index = 0
            if self.state_manager:
                self.state_manager.update_queue_position(folder_index=0)

        current = folders[index]
        logger.debug("[FolderQueue] Current folder: %s (index: %d)",
                    os.path.basename(current), index)
        return current

    def get_videos_in_folder(self, folder_path: str, exclude_uploaded: bool = True) -> List[str]:
        """
        Get all video files in folder.

        Args:
            folder_path: Path to folder
            exclude_uploaded: Skip 'uploaded videos' subfolder (default: True)

        Returns:
            List of video file paths
        """
        try:
            folder = Path(folder_path)
            if not folder.exists():
                logger.error("[FolderQueue] Folder not found: %s", folder_path)
                return []

            videos = []

            # Search for videos with each extension
            for ext in self.video_extensions:
                pattern = str(folder / ext)
                found = glob.glob(pattern)
                videos.extend(found)

            # Filter out 'uploaded videos' subfolder
            if exclude_uploaded:
                uploaded_folder = folder / "uploaded videos"
                videos = [
                    v for v in videos
                    if not v.startswith(str(uploaded_folder))
                ]

            # Sort for consistent ordering
            videos.sort()

            logger.info("[FolderQueue] Found %d video(s) in %s",
                       len(videos), os.path.basename(folder_path))

            return videos

        except Exception as e:
            logger.error("[FolderQueue] Error getting videos: %s", str(e))
            return []

    def mark_current_folder_complete(self):
        """Mark current folder as completed in state."""
        current = self.get_current_folder()
        if current and self.state_manager:
            self.state_manager.mark_folder_completed(current)
            logger.info("[FolderQueue] ✓ Marked folder complete: %s",
                       os.path.basename(current))

    def move_to_next_folder(self) -> bool:
        """
        Move to next folder in queue.
        Implements infinite loop (folder #N → folder #0).

        Returns:
            True if moved to next, False if error
        """
        try:
            folders = self.get_all_folders()
            if not folders:
                logger.error("[FolderQueue] No folders available")
                return False

            current_index = self.get_current_folder_index()
            total_folders = len(folders)

            # Increment index
            next_index = current_index + 1

            # Check if we need to loop back
            if next_index >= total_folders:
                logger.info("[FolderQueue] ═══════════════════════════════════════════")
                logger.info("[FolderQueue] Completed all %d folders!", total_folders)
                logger.info("[FolderQueue] Looping back to folder #1...")
                logger.info("[FolderQueue] ═══════════════════════════════════════════")

                next_index = 0

                # Increment cycle count
                if self.state_manager:
                    position = self.state_manager.get_current_position()
                    current_cycle = position.get('cycle', 1)
                    new_cycle = current_cycle + 1

                    logger.info("[FolderQueue] Starting cycle #%d", new_cycle)

                    self.state_manager.update_queue_position(
                        folder_index=next_index,
                        folder_path=folders[next_index],
                        total_folders=total_folders,
                        cycle=new_cycle
                    )
            else:
                # Normal progression
                if self.state_manager:
                    self.state_manager.update_queue_position(
                        folder_index=next_index,
                        folder_path=folders[next_index],
                        total_folders=total_folders
                    )

            logger.info("[FolderQueue] Moved to folder #%d: %s",
                       next_index + 1, os.path.basename(folders[next_index]))

            return True

        except Exception as e:
            logger.error("[FolderQueue] Error moving to next folder: %s", str(e))
            return False

    def is_folder_complete(self, folder_path: str) -> bool:
        """
        Check if folder is marked as complete.

        Args:
            folder_path: Path to folder

        Returns:
            True if completed, False otherwise
        """
        if self.state_manager:
            return self.state_manager.is_folder_completed(folder_path)
        return False

    def get_cycle_count(self) -> int:
        """
        Get current cycle count.

        Returns:
            Current cycle number (1-based)
        """
        if self.state_manager:
            position = self.state_manager.get_current_position()
            return position.get('cycle', 1)
        return 1

    def reset_queue(self):
        """
        Reset queue state to initial position.
        Call this when switching to a new profile.
        """
        if self.state_manager:
            logger.info("[FolderQueue] Resetting queue state")
            self.state_manager.update_queue_position(
                folder_index=0,
                folder_path=None,
                total_folders=0,
                cycle=1
            )
            logger.debug("[FolderQueue] ✓ Queue state reset")

    def initialize_queue(self, force_reset: bool = False):
        """
        Initialize queue with all folders.
        Call this on first run to set up state.

        Args:
            force_reset: Force reset even if already initialized (for profile switching)
        """
        folders = self.get_all_folders()

        if not folders:
            logger.error("[FolderQueue] Cannot initialize: no folders found")
            return

        if self.state_manager:
            # Check if already initialized
            position = self.state_manager.get_current_position()

            if position.get('folder_path') is None or force_reset:
                # First time initialization OR forced reset
                logger.info("[FolderQueue] Initializing queue with %d folders", len(folders))

                self.state_manager.update_queue_position(
                    folder_index=0,
                    folder_path=folders[0],
                    total_folders=len(folders),
                    cycle=1
                )

                logger.info("[FolderQueue] ✓ Queue initialized at folder #1: %s",
                           os.path.basename(folders[0]))
            else:
                logger.debug("[FolderQueue] Queue already initialized (resuming from previous state)")

    def get_queue_status(self) -> Dict[str, any]:
        """
        Get complete queue status.

        Returns:
            Dict with queue information
        """
        folders = self.get_all_folders()
        current_index = self.get_current_folder_index()
        cycle = self.get_cycle_count()

        return {
            'total_folders': len(folders),
            'current_index': current_index,
            'current_folder': folders[current_index] if folders else None,
            'cycle': cycle,
            'folders_completed_this_cycle': current_index,
            'folders_remaining': len(folders) - current_index if folders else 0
        }
