"""
Video Scanner for Title Generator
Recursively scans folders to find all video files
"""

import os
from pathlib import Path
from typing import List, Dict
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class VideoScanner:
    """Scan folders and find video files"""

    # Supported video extensions
    VIDEO_EXTENSIONS = {
        '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv',
        '.m4v', '.mpg', '.mpeg', '.3gp', '.webm'
    }

    def __init__(self):
        """Initialize video scanner"""
        self.videos = []

    def scan_folder(self, folder_path: str, recursive: bool = True) -> List[Dict]:
        """
        Scan folder for video files

        Args:
            folder_path: Path to folder to scan
            recursive: Whether to scan nested folders

        Returns:
            List of video info dictionaries
        """
        self.videos = []
        folder = Path(folder_path)

        if not folder.exists():
            logger.error(f"Folder not found: {folder_path}")
            return []

        if not folder.is_dir():
            logger.error(f"Not a directory: {folder_path}")
            return []

        logger.info(f"Scanning folder: {folder_path} (recursive={recursive})")

        try:
            if recursive:
                # Recursive scan (nested folders)
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        self._process_file(root, file)
            else:
                # Non-recursive scan (current folder only)
                for file in folder.iterdir():
                    if file.is_file():
                        self._process_file(folder, file.name)

            logger.info(f"Found {len(self.videos)} videos")
            return self.videos

        except Exception as e:
            logger.error(f"Error scanning folder: {e}")
            return []

    def _process_file(self, root, filename):
        """
        Process single file and add to videos list if valid

        Args:
            root: Parent directory path
            filename: File name
        """
        file_path = Path(root) / filename
        file_ext = file_path.suffix.lower()

        # Check if video file
        if file_ext in self.VIDEO_EXTENSIONS:
            try:
                # Get file info
                file_size = file_path.stat().st_size
                parent_folder = file_path.parent.name

                # Create video info object
                video_info = {
                    'path': str(file_path),
                    'filename': filename,
                    'name_without_ext': file_path.stem,
                    'extension': file_ext,
                    'folder': parent_folder,
                    'size': file_size,
                    'size_mb': round(file_size / (1024 * 1024), 2)
                }

                # Try to get duration
                try:
                    duration = self._get_video_duration(str(file_path))
                    video_info['duration'] = duration
                except:
                    video_info['duration'] = 0

                self.videos.append(video_info)
                logger.debug(f"Found video: {filename}")

            except Exception as e:
                logger.warning(f"Error processing file {filename}: {e}")

    def _get_video_duration(self, video_path: str) -> float:
        """
        Get video duration in seconds

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds (0 if failed)
        """
        try:
            from moviepy import VideoFileClip

            with VideoFileClip(video_path) as clip:
                duration = clip.duration

            return duration if duration else 0

        except Exception as e:
            logger.debug(f"Could not get duration: {e}")
            return 0

    def get_statistics(self) -> Dict:
        """
        Get scanning statistics

        Returns:
            Dictionary with statistics
        """
        if not self.videos:
            return {
                'total_videos': 0,
                'total_size_mb': 0,
                'total_duration': 0
            }

        total_size = sum(v['size'] for v in self.videos)
        total_duration = sum(v.get('duration', 0) for v in self.videos)

        return {
            'total_videos': len(self.videos),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'total_duration': round(total_duration, 2),
            'folders': len(set(v['folder'] for v in self.videos))
        }
