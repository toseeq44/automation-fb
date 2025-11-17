"""
Video Mover Module
Handles moving videos from source folders to destination folders based on mappings
"""

import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from enum import Enum

from .folder_mapping_manager import FolderMappingManager, FolderMapping


class MoveResult(Enum):
    """Result status for video move operations"""
    SUCCESS = "success"
    SKIPPED_LIMIT_REACHED = "skipped_limit_reached"
    SKIPPED_NOT_EMPTY = "skipped_not_empty"
    SKIPPED_NO_VIDEOS = "skipped_no_videos"
    SKIPPED_DISABLED = "skipped_disabled"
    ERROR = "error"


class VideoMoveOperation:
    """Represents a single video move operation result"""

    def __init__(self,
                 source_file: str,
                 destination_file: str,
                 result: MoveResult,
                 error_message: str = ""):
        self.source_file = source_file
        self.destination_file = destination_file
        self.result = result
        self.error_message = error_message
        self.timestamp = datetime.now().isoformat()


class MappingMoveResult:
    """Result for all operations on a single mapping"""

    def __init__(self, mapping: FolderMapping):
        self.mapping = mapping
        self.operations: List[VideoMoveOperation] = []
        self.videos_moved = 0
        self.videos_skipped = 0
        self.videos_failed = 0
        self.status = MoveResult.SUCCESS
        self.message = ""

    def add_operation(self, operation: VideoMoveOperation):
        """Add an operation result"""
        self.operations.append(operation)
        if operation.result == MoveResult.SUCCESS:
            self.videos_moved += 1
        elif operation.result == MoveResult.ERROR:
            self.videos_failed += 1
        else:
            self.videos_skipped += 1


class VideoMover:
    """Handles video moving operations based on folder mappings"""

    # Video file extensions to move
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.mpeg', '.mpg'}

    def __init__(self, mapping_manager: Optional[FolderMappingManager] = None):
        self.mapping_manager = mapping_manager or FolderMappingManager()

    def get_video_files(self, folder_path: Path, sort_by: str = "oldest") -> List[Path]:
        """
        Get all video files from a folder

        Args:
            folder_path: Path to the folder
            sort_by: "oldest" or "newest" - how to sort files by modification time

        Returns:
            List of video file paths
        """
        if not folder_path.exists() or not folder_path.is_dir():
            return []

        video_files = []
        for file_path in folder_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.VIDEO_EXTENSIONS:
                video_files.append(file_path)

        # Sort by modification time
        if sort_by == "oldest":
            video_files.sort(key=lambda f: f.stat().st_mtime)
        elif sort_by == "newest":
            video_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        return video_files

    def is_destination_empty(self, folder_path: Path) -> bool:
        """
        Check if destination folder is empty (no video files)

        Args:
            folder_path: Path to check

        Returns:
            True if folder doesn't exist or has no video files
        """
        if not folder_path.exists():
            return True

        video_files = self.get_video_files(folder_path)
        return len(video_files) == 0

    def move_video_file(self, source: Path, destination_folder: Path) -> Tuple[bool, str, Optional[Path]]:
        """
        Move a single video file to destination folder

        Args:
            source: Source video file path
            destination_folder: Destination folder path

        Returns:
            Tuple of (success, error_message, destination_file_path)
        """
        try:
            # Create destination folder if it doesn't exist
            destination_folder.mkdir(parents=True, exist_ok=True)

            # Construct destination file path
            destination_file = destination_folder / source.name

            # Handle file name conflicts
            if destination_file.exists():
                # Add timestamp to filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = destination_file.stem
                suffix = destination_file.suffix
                destination_file = destination_folder / f"{stem}_{timestamp}{suffix}"

            # Move the file
            shutil.move(str(source), str(destination_file))

            return True, "", destination_file

        except PermissionError:
            return False, f"Permission denied: {source.name}", None
        except Exception as e:
            return False, f"Error moving {source.name}: {str(e)}", None

    def process_mapping(self, mapping: FolderMapping, sort_by: str = "oldest") -> MappingMoveResult:
        """
        Process a single folder mapping

        Args:
            mapping: The folder mapping to process
            sort_by: How to sort videos ("oldest" or "newest")

        Returns:
            MappingMoveResult with operation details
        """
        result = MappingMoveResult(mapping)

        # Check if mapping is enabled
        if not mapping.enabled:
            result.status = MoveResult.SKIPPED_DISABLED
            result.message = "Mapping is disabled"
            return result

        # Check if we can move today (daily limit check)
        if not mapping.can_move_today():
            result.status = MoveResult.SKIPPED_LIMIT_REACHED
            result.message = "Daily limit already reached for today"
            return result

        # Validate mapping
        is_valid, error = mapping.validate()
        if not is_valid:
            result.status = MoveResult.ERROR
            result.message = f"Invalid mapping: {error}"
            return result

        source_path = mapping.get_source_path()
        destination_path = mapping.get_destination_path()

        # Check destination folder condition
        if mapping.move_only_if_empty and not self.is_destination_empty(destination_path):
            result.status = MoveResult.SKIPPED_NOT_EMPTY
            result.message = "Destination folder is not empty (condition: move_only_if_empty=True)"
            return result

        # Get video files from source
        video_files = self.get_video_files(source_path, sort_by=sort_by)

        if not video_files:
            result.status = MoveResult.SKIPPED_NO_VIDEOS
            result.message = "No video files found in source folder"
            return result

        # Limit to daily_limit number of videos
        videos_to_move = video_files[:mapping.daily_limit]

        # Move each video
        for video_file in videos_to_move:
            success, error_msg, dest_file = self.move_video_file(video_file, destination_path)

            if success:
                operation = VideoMoveOperation(
                    source_file=str(video_file),
                    destination_file=str(dest_file),
                    result=MoveResult.SUCCESS,
                    error_message=""
                )
            else:
                operation = VideoMoveOperation(
                    source_file=str(video_file),
                    destination_file="",
                    result=MoveResult.ERROR,
                    error_message=error_msg
                )

            result.add_operation(operation)

        # Update mapping statistics
        if result.videos_moved > 0:
            self.mapping_manager.update_move_stats(mapping.id, result.videos_moved)
            result.message = f"Successfully moved {result.videos_moved} video(s)"
        else:
            result.message = f"No videos moved. Failed: {result.videos_failed}"

        return result

    def process_all_active_mappings(self, sort_by: str = "oldest") -> List[MappingMoveResult]:
        """
        Process all active (enabled) mappings

        Args:
            sort_by: How to sort videos ("oldest" or "newest")

        Returns:
            List of MappingMoveResult for all processed mappings
        """
        active_mappings = self.mapping_manager.get_active_mappings()
        results = []

        for mapping in active_mappings:
            result = self.process_mapping(mapping, sort_by=sort_by)
            results.append(result)

        return results

    def get_move_summary(self, results: List[MappingMoveResult]) -> Dict:
        """
        Generate summary statistics from move results

        Args:
            results: List of mapping move results

        Returns:
            Dictionary with summary statistics
        """
        total_moved = sum(r.videos_moved for r in results)
        total_skipped = sum(r.videos_skipped for r in results)
        total_failed = sum(r.videos_failed for r in results)

        mappings_processed = len(results)
        mappings_successful = len([r for r in results if r.videos_moved > 0])
        mappings_skipped = len([
            r for r in results
            if r.status in [
                MoveResult.SKIPPED_LIMIT_REACHED,
                MoveResult.SKIPPED_NOT_EMPTY,
                MoveResult.SKIPPED_NO_VIDEOS,
                MoveResult.SKIPPED_DISABLED
            ]
        ])
        mappings_failed = len([r for r in results if r.videos_failed > 0])

        return {
            "total_videos_moved": total_moved,
            "total_videos_skipped": total_skipped,
            "total_videos_failed": total_failed,
            "mappings_processed": mappings_processed,
            "mappings_successful": mappings_successful,
            "mappings_skipped": mappings_skipped,
            "mappings_failed": mappings_failed,
            "timestamp": datetime.now().isoformat()
        }

    def dry_run(self, mapping: FolderMapping) -> Dict:
        """
        Simulate a move operation without actually moving files

        Args:
            mapping: The mapping to simulate

        Returns:
            Dictionary with simulation results
        """
        source_path = mapping.get_source_path()
        destination_path = mapping.get_destination_path()

        # Check conditions
        can_move = mapping.can_move_today()
        is_valid, error = mapping.validate()
        video_files = self.get_video_files(source_path)
        dest_empty = self.is_destination_empty(destination_path)

        videos_to_move = video_files[:mapping.daily_limit] if video_files else []

        return {
            "mapping_id": mapping.id,
            "source_folder": str(source_path),
            "destination_folder": str(destination_path),
            "is_valid": is_valid,
            "validation_error": error if not is_valid else "",
            "can_move_today": can_move,
            "destination_empty": dest_empty,
            "total_videos_in_source": len(video_files),
            "videos_that_would_move": len(videos_to_move),
            "video_files_to_move": [str(v) for v in videos_to_move],
            "will_move": (
                is_valid and
                can_move and
                mapping.enabled and
                len(videos_to_move) > 0 and
                (not mapping.move_only_if_empty or dest_empty)
            )
        }
