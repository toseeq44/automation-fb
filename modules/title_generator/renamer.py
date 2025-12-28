"""
File Renamer for Title Generator
Safely renames video files in-place (same location)
"""

import os
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class VideoRenamer:
    """Rename video files safely in-place"""

    def __init__(self):
        """Initialize video renamer"""
        self.rename_log = []
        self.log_file = None

    def rename_video(self, video_path: str, new_title: str) -> Tuple[bool, str, str]:
        """
        Rename video file with new title

        Args:
            video_path: Full path to video file
            new_title: New title for video (without extension)

        Returns:
            Tuple of (success: bool, new_path: str, error_message: str)
        """
        try:
            old_path = Path(video_path)

            # Check if file exists
            if not old_path.exists():
                error = "File not found"
                logger.error(f"{error}: {video_path}")
                self._log_rename(video_path, "", "failed", error)
                return False, "", error

            # Get file extension
            extension = old_path.suffix

            # Create new filename
            new_filename = f"{new_title}{extension}"

            # Build new path (same directory)
            new_path = old_path.parent / new_filename

            # Check if file with same name already exists
            if new_path.exists() and new_path != old_path:
                # Add number suffix
                counter = 1
                while new_path.exists():
                    new_filename = f"{new_title}_{counter}{extension}"
                    new_path = old_path.parent / new_filename
                    counter += 1

                logger.warning(f"Duplicate name detected. Using: {new_filename}")

            # Check if file is locked
            if self._is_file_locked(video_path):
                error = "File is locked or in use"
                logger.error(f"{error}: {video_path}")
                self._log_rename(video_path, "", "failed", error)
                return False, "", error

            # Perform rename
            os.rename(old_path, new_path)

            logger.info(f"✅ Renamed: {old_path.name} → {new_path.name}")
            self._log_rename(str(old_path), str(new_path), "success", "")

            return True, str(new_path), ""

        except PermissionError as e:
            error = f"Permission denied: {e}"
            logger.error(error)
            self._log_rename(video_path, "", "failed", error)
            return False, "", error

        except Exception as e:
            error = f"Rename failed: {e}"
            logger.error(error)
            self._log_rename(video_path, "", "failed", error)
            return False, "", error

    def _is_file_locked(self, filepath: str) -> bool:
        """
        Check if file is locked (in use)

        Args:
            filepath: Path to file

        Returns:
            True if file is locked
        """
        try:
            # Try to open file in exclusive mode
            with open(filepath, 'r+b'):
                pass
            return False
        except (PermissionError, IOError):
            return True

    def _log_rename(self, old_path: str, new_path: str, status: str, error: str):
        """
        Log rename operation

        Args:
            old_path: Original file path
            new_path: New file path
            status: 'success' or 'failed'
            error: Error message if failed
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_entry = {
            'timestamp': timestamp,
            'original_path': old_path,
            'new_path': new_path,
            'status': status,
            'error': error
        }

        self.rename_log.append(log_entry)

    def save_log(self, output_dir: str) -> str:
        """
        Save rename log to CSV file (Disabled - not needed)

        Args:
            output_dir: Directory to save log file

        Returns:
            Empty string (logging disabled)
        """
        # CSV logging disabled per user request
        # Statistics are still tracked internally via rename_log
        logger.debug("CSV log file generation disabled")
        return ""

    def get_statistics(self) -> Dict:
        """
        Get rename statistics

        Returns:
            Dictionary with statistics
        """
        if not self.rename_log:
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0
            }

        total = len(self.rename_log)
        successful = sum(1 for entry in self.rename_log if entry['status'] == 'success')
        failed = total - successful
        success_rate = (successful / total * 100) if total > 0 else 0

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'success_rate': round(success_rate, 1)
        }
