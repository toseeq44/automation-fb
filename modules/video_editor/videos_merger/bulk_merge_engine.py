"""
modules/video_editor/videos_merger/bulk_merge_engine.py
Intelligent bulk folder merging with round-robin batching
"""

from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from .merge_engine import merge_videos, MergeSettings
from .utils import get_videos_from_folder, generate_batch_filename
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class BatchInfo:
    """Information about a merge batch"""

    def __init__(self, batch_number: int, video_paths: List[str]):
        self.batch_number = batch_number
        self.video_paths = video_paths
        self.status = 'pending'  # 'pending', 'processing', 'completed', 'failed', 'skipped'
        self.output_path: Optional[str] = None
        self.error_message: Optional[str] = None

    def __repr__(self):
        return f"Batch {self.batch_number}: {len(self.video_paths)} videos ({self.status})"


class BulkMergeEngine:
    """Engine for bulk folder merging with intelligent batching"""

    def __init__(self):
        self.folder_paths: List[str] = []
        self.folder_videos: List[List[str]] = []
        self.batches: List[BatchInfo] = []
        self.settings: Optional[MergeSettings] = None

    def load_folders(self, folder_paths: List[str]) -> bool:
        """
        Load video files from multiple folders

        Args:
            folder_paths: List of folder paths

        Returns:
            True if at least 2 folders with videos loaded
        """
        try:
            self.folder_paths = []
            self.folder_videos = []

            for folder_path in folder_paths:
                if not Path(folder_path).exists():
                    logger.warning(f"Folder not found: {folder_path}")
                    continue

                videos = get_videos_from_folder(folder_path)
                if not videos:
                    logger.warning(f"No videos found in: {folder_path}")
                    continue

                self.folder_paths.append(folder_path)
                self.folder_videos.append(videos)
                logger.info(f"Loaded folder: {folder_path} ({len(videos)} videos)")

            # Validate: Need at least 2 folders
            if len(self.folder_paths) < 2:
                logger.error("Need at least 2 folders with videos for bulk merging")
                return False

            logger.info(f"Loaded {len(self.folder_paths)} folders with videos")
            return True

        except Exception as e:
            logger.error(f"Error loading folders: {e}")
            return False

    def create_batches(self) -> List[BatchInfo]:
        """
        Create merge batches using round-robin algorithm
        Skip batches with only 1 video

        Returns:
            List of BatchInfo objects

        Example:
            Folder 1: [v1, v2, v3, v4, v5]  (5 videos)
            Folder 2: [v1, v2, v3]          (3 videos)
            Folder 3: [v1, v2, v3, v4]      (4 videos)
            Folder 4: [v1, v2]              (2 videos)

            Batches:
            1. [F1v1, F2v1, F3v1, F4v1] → 4 videos ✓ MERGE
            2. [F1v2, F2v2, F3v2, F4v2] → 4 videos ✓ MERGE
            3. [F1v3, F2v3, F3v3]       → 3 videos ✓ MERGE (F4 exhausted)
            4. [F1v4, F3v4]             → 2 videos ✓ MERGE (F2 exhausted)
            5. [F1v5]                   → 1 video  ✗ SKIP (only 1 video)

            Result: 4 merged videos
        """
        self.batches = []

        if not self.folder_videos:
            return []

        batch_number = 1
        batch_index = 0

        while True:
            current_batch_videos = []

            # Try to take 1 video from each folder
            for folder_vids in self.folder_videos:
                if batch_index < len(folder_vids):
                    current_batch_videos.append(folder_vids[batch_index])

            # If no videos left, we're done
            if not current_batch_videos:
                break

            # Skip batches with only 1 video (can't merge single video)
            if len(current_batch_videos) < 2:
                logger.info(f"Skipping batch {batch_number}: Only {len(current_batch_videos)} video(s) - need at least 2")
                batch_info = BatchInfo(batch_number, current_batch_videos)
                batch_info.status = 'skipped'
                self.batches.append(batch_info)
                break

            # Create batch
            batch_info = BatchInfo(batch_number, current_batch_videos)
            self.batches.append(batch_info)
            logger.info(f"Created batch {batch_number}: {len(current_batch_videos)} videos")

            batch_number += 1
            batch_index += 1

        # Filter out skipped batches for actual processing
        active_batches = [b for b in self.batches if b.status != 'skipped']
        logger.info(f"Created {len(active_batches)} active batches ({len(self.batches)} total including skipped)")

        return self.batches

    def get_batch_summary(self) -> Dict[str, Any]:
        """
        Get summary of batches

        Returns:
            Dictionary with batch statistics
        """
        active_batches = [b for b in self.batches if b.status != 'skipped']

        return {
            'total_batches': len(self.batches),
            'active_batches': len(active_batches),
            'skipped_batches': len(self.batches) - len(active_batches),
            'total_videos': sum(len(b.video_paths) for b in active_batches),
            'folder_counts': [len(videos) for videos in self.folder_videos]
        }

    def process_batches(self, output_folder: str, settings: MergeSettings,
                        progress_callback: Optional[Callable[[int, int, str, float], None]] = None,
                        should_pause: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        Process all batches and create merged videos

        Args:
            output_folder: Output folder path
            settings: Merge settings
            progress_callback: Callback(current_batch, total_batches, status, percentage)
            should_pause: Function that returns True if processing should pause

        Returns:
            Dictionary with results
        """
        self.settings = settings
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)

        # Get only active batches (skip batches with 1 video)
        active_batches = [b for b in self.batches if b.status != 'skipped']
        total_active = len(active_batches)

        results = {
            'total_batches': len(self.batches),
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': len(self.batches) - total_active,
            'output_files': [],
            'errors': []
        }

        for i, batch in enumerate(active_batches, 1):
            # Check if should pause
            if should_pause and should_pause():
                logger.info("Processing paused")
                break

            batch.status = 'processing'

            if progress_callback:
                progress_callback(i, total_active, f"Processing batch {batch.batch_number}", 0)

            # Generate output filename
            output_filename = generate_batch_filename(batch.batch_number, settings.output_format)
            output_path = output_folder / output_filename
            batch.output_path = str(output_path)

            # Merge videos
            logger.info(f"Merging batch {batch.batch_number}: {len(batch.video_paths)} videos")

            def batch_progress(msg, pct):
                if progress_callback:
                    progress_callback(i, total_active, msg, pct)

            success = merge_videos(
                batch.video_paths,
                str(output_path),
                settings,
                batch_progress
            )

            if success:
                batch.status = 'completed'
                results['successful'] += 1
                results['output_files'].append(str(output_path))
                logger.info(f"Batch {batch.batch_number} completed: {output_path}")
            else:
                batch.status = 'failed'
                batch.error_message = "Merge failed"
                results['failed'] += 1
                results['errors'].append(f"Batch {batch.batch_number} failed")
                logger.error(f"Batch {batch.batch_number} failed")

            results['processed'] += 1

        logger.info(f"Bulk processing complete: {results['successful']} successful, "
                    f"{results['failed']} failed, {results['skipped']} skipped")

        return results

    def get_folder_info(self) -> List[Dict[str, Any]]:
        """
        Get information about loaded folders

        Returns:
            List of folder info dictionaries
        """
        info = []
        for i, (path, videos) in enumerate(zip(self.folder_paths, self.folder_videos)):
            info.append({
                'index': i,
                'path': path,
                'name': Path(path).name,
                'video_count': len(videos),
                'video_paths': videos
            })
        return info

    def estimate_total_duration(self) -> float:
        """
        Estimate total duration of all videos to be merged

        Returns:
            Total duration in seconds (rough estimate)
        """
        # This is a rough estimate without loading all videos
        # In practice, would need to load each video to get exact duration
        return 0.0  # Placeholder

    def validate_folders(self) -> tuple[bool, List[str]]:
        """
        Validate folders for bulk merging

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        if len(self.folder_paths) < 2:
            errors.append("Need at least 2 folders for bulk merging")

        for path in self.folder_paths:
            if not Path(path).exists():
                errors.append(f"Folder not found: {path}")
            elif not Path(path).is_dir():
                errors.append(f"Not a directory: {path}")

        for i, videos in enumerate(self.folder_videos):
            if not videos:
                errors.append(f"Folder {i + 1} has no videos")

        # Check if we'll have at least 1 batch with 2+ videos
        if self.folder_videos:
            max_batches = max(len(videos) for videos in self.folder_videos)
            has_valid_batch = False

            for batch_idx in range(max_batches):
                batch_count = sum(1 for videos in self.folder_videos if batch_idx < len(videos))
                if batch_count >= 2:
                    has_valid_batch = True
                    break

            if not has_valid_batch:
                errors.append("No valid batches possible (each batch needs at least 2 videos)")

        return len(errors) == 0, errors


def bulk_merge_folders(folder_paths: List[str], output_folder: str,
                       settings: MergeSettings = None,
                       progress_callback: Optional[Callable[[int, int, str, float], None]] = None) -> Dict[str, Any]:
    """
    Convenience function for bulk folder merging

    Args:
        folder_paths: List of folder paths
        output_folder: Output folder path
        settings: Merge settings (default if None)
        progress_callback: Callback(current, total, status, percentage)

    Returns:
        Results dictionary
    """
    if settings is None:
        settings = MergeSettings()

    engine = BulkMergeEngine()

    # Load folders
    if not engine.load_folders(folder_paths):
        return {
            'total_batches': 0,
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'output_files': [],
            'errors': ['Failed to load folders']
        }

    # Create batches
    engine.create_batches()

    # Process batches
    return engine.process_batches(output_folder, settings, progress_callback)
