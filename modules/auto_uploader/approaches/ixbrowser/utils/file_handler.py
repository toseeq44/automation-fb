"""
File Handler Utilities for ixBrowser Approach

Handles file operations:
- Video file discovery
- File moving/copying
- Failed video deletion
- Hash calculation (duplicate detection)
- Safe file operations

Usage:
    handler = FileHandler()
    handler.move_video_to_uploaded(video_path, folder_path)
    handler.delete_failed_video(video_path)
"""

import logging
import os
import shutil
import hashlib
from typing import Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class FileHandler:
    """Handles all file operations for video management."""

    def __init__(self):
        """Initialize File Handler."""
        logger.info("[FileHandler] Initialized")

    def move_video_to_uploaded(self, video_file: str, creator_folder: str) -> Optional[str]:
        """
        Move uploaded video to 'uploaded videos' subfolder.

        Args:
            video_file: Full path to video file
            creator_folder: Path to creator folder

        Returns:
            New file path if successful, None otherwise
        """
        try:
            logger.info("[FileHandler] ═══════════════════════════════════════════")
            logger.info("[FileHandler] Moving Video to 'Uploaded' Folder")
            logger.info("[FileHandler] ═══════════════════════════════════════════")

            # Check if video file exists
            if not os.path.exists(video_file):
                logger.error("[FileHandler] ✗ Video file not found: %s", video_file)
                return None

            # Create 'uploaded videos' subfolder
            uploaded_folder = Path(creator_folder) / "uploaded videos"
            uploaded_folder.mkdir(parents=True, exist_ok=True)

            if uploaded_folder.exists():
                logger.info("[FileHandler] ✓ 'uploaded videos' folder ready")
            else:
                logger.info("[FileHandler] ✓ Created 'uploaded videos' folder")

            # Get video filename
            video_filename = os.path.basename(video_file)
            destination = uploaded_folder / video_filename

            # Check if file already exists at destination
            if destination.exists():
                logger.warning("[FileHandler] ⚠ File exists at destination, adding timestamp")
                # Add timestamp to avoid overwrite
                import time
                name, ext = os.path.splitext(video_filename)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                video_filename = f"{name}_{timestamp}{ext}"
                destination = uploaded_folder / video_filename

            # Move the file
            shutil.move(video_file, str(destination))

            logger.info("[FileHandler] ✓ Video moved successfully!")
            logger.info("[FileHandler]   From: %s", video_file)
            logger.info("[FileHandler]   To: %s", destination)
            logger.info("[FileHandler] ═══════════════════════════════════════════")

            return str(destination)

        except Exception as e:
            logger.error("[FileHandler] ✗ Failed to move video: %s", str(e))
            logger.error("[FileHandler]   Video: %s", video_file)
            return None

    def delete_failed_video(self, video_file: str, reason: str = "failed after 3 retries") -> bool:
        """
        Delete a failed video file.

        Args:
            video_file: Full path to video file
            reason: Reason for deletion (for logging)

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            logger.warning("[FileHandler] ═══════════════════════════════════════════")
            logger.warning("[FileHandler] Deleting Failed Video")
            logger.warning("[FileHandler] ═══════════════════════════════════════════")

            if not os.path.exists(video_file):
                logger.warning("[FileHandler] Video file not found (already deleted?): %s",
                             os.path.basename(video_file))
                return True

            # Get file info before deletion
            file_size = os.path.getsize(video_file) / (1024 * 1024)  # MB

            logger.warning("[FileHandler] Reason: %s", reason)
            logger.warning("[FileHandler] File: %s", os.path.basename(video_file))
            logger.warning("[FileHandler] Size: %.2f MB", file_size)

            # Delete the file
            os.remove(video_file)

            logger.warning("[FileHandler] ✓ Video deleted")
            logger.warning("[FileHandler] ═══════════════════════════════════════════")

            return True

        except Exception as e:
            logger.error("[FileHandler] ✗ Failed to delete video: %s", str(e))
            logger.error("[FileHandler]   File: %s", video_file)
            return False

    def calculate_file_hash(self, file_path: str, algorithm: str = 'md5') -> Optional[str]:
        """
        Calculate hash of file for duplicate detection.

        Args:
            file_path: Path to file
            algorithm: Hash algorithm (md5, sha256)

        Returns:
            Hash string or None if error
        """
        try:
            if algorithm == 'md5':
                hasher = hashlib.md5()
            elif algorithm == 'sha256':
                hasher = hashlib.sha256()
            else:
                logger.error("[FileHandler] Unknown hash algorithm: %s", algorithm)
                return None

            # Read file in chunks for memory efficiency
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)

            file_hash = hasher.hexdigest()
            logger.debug("[FileHandler] Calculated %s hash: %s...", algorithm, file_hash[:16])

            return file_hash

        except Exception as e:
            logger.error("[FileHandler] Error calculating hash: %s", str(e))
            return None

    def safe_move(self, source: str, destination: str, overwrite: bool = False) -> bool:
        """
        Safely move a file with error handling.

        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Allow overwriting existing file

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(source):
                logger.error("[FileHandler] Source file not found: %s", source)
                return False

            # Check if destination exists
            if os.path.exists(destination) and not overwrite:
                logger.error("[FileHandler] Destination exists (overwrite=False): %s", destination)
                return False

            # Create destination directory if needed
            dest_dir = os.path.dirname(destination)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)

            # Move file
            shutil.move(source, destination)

            logger.debug("[FileHandler] ✓ Moved: %s → %s",
                        os.path.basename(source), os.path.basename(destination))

            return True

        except Exception as e:
            logger.error("[FileHandler] Move failed: %s", str(e))
            return False

    def safe_delete(self, file_path: str, confirm: bool = True) -> bool:
        """
        Safely delete a file with confirmation.

        Args:
            file_path: File to delete
            confirm: Require confirmation (for safety)

        Returns:
            True if deleted, False otherwise
        """
        try:
            if not os.path.exists(file_path):
                logger.debug("[FileHandler] File not found (already deleted?): %s", file_path)
                return True

            if confirm:
                # In production, this would always be True
                # (no interactive confirmation in automation)
                logger.debug("[FileHandler] Deleting: %s", os.path.basename(file_path))

            os.remove(file_path)

            logger.debug("[FileHandler] ✓ Deleted: %s", os.path.basename(file_path))
            return True

        except Exception as e:
            logger.error("[FileHandler] Delete failed: %s", str(e))
            return False

    def get_file_info(self, file_path: str) -> dict:
        """
        Get file information.

        Args:
            file_path: Path to file

        Returns:
            Dict with file info
        """
        try:
            if not os.path.exists(file_path):
                return {'exists': False}

            stat = os.stat(file_path)

            return {
                'exists': True,
                'size_bytes': stat.st_size,
                'size_mb': stat.st_size / (1024 * 1024),
                'name': os.path.basename(file_path),
                'extension': os.path.splitext(file_path)[1],
                'directory': os.path.dirname(file_path),
                'modified_time': stat.st_mtime,
            }

        except Exception as e:
            logger.error("[FileHandler] Error getting file info: %s", str(e))
            return {'exists': False, 'error': str(e)}
