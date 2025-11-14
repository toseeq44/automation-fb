"""
State Manager for ixBrowser Approach

Handles bot state persistence and recovery:
- Saves/loads bot_state.json (current runtime state)
- Saves/loads folder_progress.json (folder tracking)
- Saves/loads uploaded_videos.json (upload history)
- Provides thread-safe operations
- Atomic file writes (prevents corruption)
- Auto-backup functionality

Usage:
    state_mgr = StateManager()
    state_mgr.save_current_upload(video_file, progress=45)
    state = state_mgr.load_state()
"""

import logging
import os
import json
import time
import threading
import platform
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Detect platform for Windows-specific workarounds
IS_WINDOWS = platform.system() == "Windows"


class StateManager:
    """Manages all bot state persistence and recovery."""

    def __init__(self, data_dir: str = None):
        """
        Initialize State Manager.

        Args:
            data_dir: Directory for state files (default: ixbrowser/data/)
        """
        if data_dir is None:
            # Default to ixbrowser/data/ folder
            current_dir = Path(__file__).parent.parent
            data_dir = current_dir / "data"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # State file paths
        self.bot_state_file = self.data_dir / "bot_state.json"
        self.folder_progress_file = self.data_dir / "folder_progress.json"
        self.uploaded_videos_file = self.data_dir / "uploaded_videos.json"

        # Thread lock for thread-safe operations
        self.lock = threading.Lock()

        logger.info("[StateManager] Initialized with data_dir: %s", self.data_dir)

    def _load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Load JSON file with error handling.

        Args:
            file_path: Path to JSON file

        Returns:
            Loaded JSON data or empty dict if file doesn't exist
        """
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.debug("[StateManager] File not found: %s (returning empty)", file_path.name)
                return {}
        except json.JSONDecodeError as e:
            logger.error("[StateManager] JSON decode error in %s: %s", file_path.name, str(e))
            return {}
        except Exception as e:
            logger.error("[StateManager] Error loading %s: %s", file_path.name, str(e))
            return {}

    def _save_json_file(self, file_path: Path, data: Dict[str, Any], backup: bool = True):
        """
        Save JSON file with atomic write and optional backup.

        Windows-compatible with retry logic for file locking issues.

        Args:
            file_path: Path to JSON file
            data: Data to save
            backup: Create backup before overwriting
        """
        max_retries = 5
        retry_delay = 0.1  # 100ms

        for attempt in range(max_retries):
            try:
                with self.lock:
                    # Create backup if file exists
                    if backup and file_path.exists():
                        backup_path = file_path.with_suffix('.json.bak')
                        import shutil
                        try:
                            shutil.copy2(file_path, backup_path)
                        except Exception as e:
                            logger.debug("[StateManager] Backup failed (non-critical): %s", str(e))

                    # Atomic write: write to temp file first
                    temp_path = file_path.with_suffix('.json.tmp')
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)

                    # Windows-specific workaround for file locking
                    if IS_WINDOWS:
                        # On Windows, delete target file first if it exists
                        # This avoids "Access denied" errors when replacing
                        if file_path.exists():
                            try:
                                file_path.unlink()
                            except PermissionError:
                                # File is locked, wait and retry
                                if attempt < max_retries - 1:
                                    logger.debug("[StateManager] File locked, retrying in %dms (attempt %d/%d)",
                                               int(retry_delay * 1000), attempt + 1, max_retries)
                                    time.sleep(retry_delay)
                                    retry_delay *= 2  # Exponential backoff
                                    continue
                                else:
                                    raise

                        # Rename temp to actual
                        os.replace(str(temp_path), str(file_path))
                    else:
                        # On POSIX, use atomic replace
                        os.replace(str(temp_path), str(file_path))

                    logger.debug("[StateManager] Saved %s successfully", file_path.name)
                    return  # Success!

            except Exception as e:
                # Clean up temp file if it exists
                temp_path = file_path.with_suffix('.json.tmp')
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except:
                        pass

                # If this is the last attempt, re-raise the exception
                if attempt >= max_retries - 1:
                    logger.error("[StateManager] Error saving %s after %d attempts: %s",
                               file_path.name, max_retries, str(e))
                    raise
                else:
                    # Log warning and retry
                    logger.debug("[StateManager] Save attempt %d/%d failed: %s, retrying...",
                               attempt + 1, max_retries, str(e))
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

    def load_state(self) -> Dict[str, Any]:
        """
        Load complete bot state.

        Returns:
            Dict with bot state data
        """
        return self._load_json_file(self.bot_state_file)

    def save_state(self, state: Dict[str, Any]):
        """
        Save complete bot state.

        Args:
            state: State data to save
        """
        # Update timestamp
        state['last_updated'] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save_json_file(self.bot_state_file, state)

    def load_folder_progress(self) -> Dict[str, Any]:
        """
        Load folder progress data.

        Returns:
            Dict with folder progress
        """
        return self._load_json_file(self.folder_progress_file)

    def save_folder_progress(self, progress: Dict[str, Any]):
        """
        Save folder progress data.

        Args:
            progress: Folder progress data
        """
        self._save_json_file(self.folder_progress_file, progress)

    def load_uploaded_videos(self) -> Dict[str, Any]:
        """
        Load uploaded videos history.

        Returns:
            Dict with uploaded videos list
        """
        return self._load_json_file(self.uploaded_videos_file)

    def save_uploaded_videos(self, videos_data: Dict[str, Any]):
        """
        Save uploaded videos history.

        Args:
            videos_data: Uploaded videos data
        """
        self._save_json_file(self.uploaded_videos_file, videos_data)

    def update_current_upload(self, video_file: str = None, video_name: str = None,
                             bookmark: str = None, status: str = None,
                             progress: int = None, attempt: int = None):
        """
        Update current upload information in state.

        Args:
            video_file: Video file path
            video_name: Video name
            bookmark: Bookmark name
            status: Upload status (idle, uploading, completed, failed)
            progress: Upload progress (0-100)
            attempt: Current attempt number
        """
        state = self.load_state()

        if 'current_upload' not in state:
            state['current_upload'] = {}

        # Update provided fields
        if video_file is not None:
            state['current_upload']['video_file'] = video_file
        if video_name is not None:
            state['current_upload']['video_name'] = video_name
        if bookmark is not None:
            state['current_upload']['bookmark'] = bookmark
        if status is not None:
            state['current_upload']['status'] = status
        if progress is not None:
            state['current_upload']['progress_last_seen'] = progress
            state['current_upload']['last_progress_update'] = time.strftime("%Y-%m-%d %H:%M:%S")
        if attempt is not None:
            state['current_upload']['attempt'] = attempt

        # Set started_at if uploading and not set
        if status == 'uploading' and not state['current_upload'].get('started_at'):
            state['current_upload']['started_at'] = time.strftime("%Y-%m-%d %H:%M:%S")

        self.save_state(state)
        logger.debug("[StateManager] Updated current upload: %s @ %d%%",
                    video_name or 'unknown', progress or 0)

    def clear_current_upload(self):
        """Clear current upload information (after completion or failure)."""
        state = self.load_state()
        state['current_upload'] = {
            "video_file": None,
            "video_name": None,
            "bookmark": None,
            "bookmark_index": None,
            "status": "idle",
            "progress_last_seen": 0,
            "started_at": None,
            "last_progress_update": None,
            "attempt": 0,
            "network_drops": 0
        }
        self.save_state(state)
        logger.debug("[StateManager] Cleared current upload")

    def update_queue_position(self, folder_index: int = None, folder_path: str = None,
                             total_folders: int = None, cycle: int = None):
        """
        Update folder queue position.

        Args:
            folder_index: Current folder index (0-based)
            folder_path: Current folder path
            total_folders: Total number of folders
            cycle: Current cycle number
        """
        state = self.load_state()

        if 'queue' not in state:
            state['queue'] = {}

        if folder_index is not None:
            state['queue']['current_folder_index'] = folder_index
        if folder_path is not None:
            state['queue']['current_folder_path'] = folder_path
        if total_folders is not None:
            state['queue']['total_folders'] = total_folders
        if cycle is not None:
            state['queue']['current_cycle'] = cycle

        self.save_state(state)
        logger.debug("[StateManager] Updated queue: folder #%d, cycle #%d",
                    folder_index or 0, cycle or 1)

    def mark_folder_completed(self, folder_path: str):
        """
        Mark a folder as completed.

        Args:
            folder_path: Path to completed folder
        """
        progress = self.load_folder_progress()

        if 'folders' not in progress:
            progress['folders'] = {}

        folder_name = os.path.basename(folder_path)
        progress['folders'][folder_name] = {
            "status": "completed",
            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "folder_path": folder_path
        }

        self.save_folder_progress(progress)
        logger.info("[StateManager] ✓ Marked folder as completed: %s", folder_name)

    def is_folder_completed(self, folder_path: str) -> bool:
        """
        Check if folder is already completed.

        Args:
            folder_path: Path to folder

        Returns:
            True if completed, False otherwise
        """
        progress = self.load_folder_progress()
        folder_name = os.path.basename(folder_path)

        if 'folders' not in progress:
            return False

        folder_info = progress['folders'].get(folder_name, {})
        return folder_info.get('status') == 'completed'

    def mark_video_uploaded(self, video_file: str, bookmark: str, session_id: str = None,
                           moved_to: str = None):
        """
        Add video to uploaded history.

        Args:
            video_file: Original video file path
            bookmark: Bookmark name
            session_id: Session ID
            moved_to: New location after moving
        """
        videos_data = self.load_uploaded_videos()

        if 'videos' not in videos_data:
            videos_data['videos'] = []

        upload_record = {
            "file_path": video_file,
            "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "bookmark": bookmark,
            "session_id": session_id,
            "moved_to": moved_to
        }

        videos_data['videos'].append(upload_record)
        videos_data['total_uploads'] = len(videos_data['videos'])
        videos_data['last_upload'] = time.strftime("%Y-%m-%d %H:%M:%S")

        self.save_uploaded_videos(videos_data)
        logger.info("[StateManager] ✓ Recorded uploaded video: %s", os.path.basename(video_file))

    def is_video_uploaded(self, video_file: str) -> bool:
        """
        Check if video has already been uploaded.

        Args:
            video_file: Video file path

        Returns:
            True if already uploaded, False otherwise
        """
        videos_data = self.load_uploaded_videos()

        if 'videos' not in videos_data:
            return False

        # Check if video file path exists in upload history
        for record in videos_data['videos']:
            if record.get('file_path') == video_file:
                return True

        return False

    def get_current_position(self) -> Dict[str, Any]:
        """
        Get current bot position (folder, video, upload state).

        Returns:
            Dict with current position information
        """
        state = self.load_state()

        return {
            'folder_index': state.get('queue', {}).get('current_folder_index', 0),
            'folder_path': state.get('queue', {}).get('current_folder_path'),
            'cycle': state.get('queue', {}).get('current_cycle', 1),
            'current_upload': state.get('current_upload', {}),
            'network_status': state.get('network', {}).get('status', 'unknown'),
            'last_updated': state.get('last_updated')
        }

    def update_network_status(self, status: str, consecutive_failures: int = None):
        """
        Update network status in state.

        Args:
            status: Network status (stable, unstable, disconnected)
            consecutive_failures: Number of consecutive failures
        """
        state = self.load_state()

        if 'network' not in state:
            state['network'] = {}

        state['network']['status'] = status
        state['network']['last_check'] = time.strftime("%Y-%m-%d %H:%M:%S")

        if consecutive_failures is not None:
            state['network']['consecutive_failures'] = consecutive_failures

        if status == 'disconnected':
            state['network']['last_drop_time'] = time.strftime("%Y-%m-%d %H:%M:%S")

        self.save_state(state)

    # ═══════════════════════════════════════════════════════════
    # Daily Limit Tracking (Basic vs Pro users)
    # ═══════════════════════════════════════════════════════════

    def get_daily_stats(self) -> Dict[str, Any]:
        """
        Get today's upload statistics.

        Returns:
            Dict with today's stats: {date, bookmarks_uploaded, videos_uploaded, started_at}
        """
        from datetime import datetime

        state = self.load_state()

        # Get daily stats (initialize if not present)
        if 'daily_stats' not in state:
            state['daily_stats'] = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'bookmarks_uploaded': 0,
                'videos_uploaded': 0,
                'started_at': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.save_state(state)

        daily_stats = state['daily_stats']

        # Check if date changed (new day) - reset counter
        today = datetime.now().strftime("%Y-%m-%d")
        if daily_stats.get('date') != today:
            logger.info("[StateManager] New day detected - resetting daily counters")
            daily_stats = {
                'date': today,
                'bookmarks_uploaded': 0,
                'videos_uploaded': 0,
                'started_at': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            state['daily_stats'] = daily_stats
            self.save_state(state)

        return daily_stats

    def increment_daily_bookmarks(self, count: int = 1):
        """
        Increment daily bookmark counter.

        Args:
            count: Number of bookmarks to add (default: 1)
        """
        state = self.load_state()

        # Get current stats (will auto-reset if new day)
        daily_stats = self.get_daily_stats()

        # Increment counter
        daily_stats['bookmarks_uploaded'] += count
        daily_stats['videos_uploaded'] += count  # Assuming 1 video per bookmark
        daily_stats['last_updated'] = time.strftime("%Y-%m-%d %H:%M:%S")

        state['daily_stats'] = daily_stats
        self.save_state(state)

        logger.debug("[StateManager] Daily stats updated: %d bookmarks today",
                    daily_stats['bookmarks_uploaded'])

    def check_daily_limit(self, user_type: str = "basic", limit: int = 200) -> Dict[str, Any]:
        """
        Check if daily limit has been reached.

        Args:
            user_type: "basic" or "pro"
            limit: Daily limit for basic users

        Returns:
            Dict with: {
                'limit_reached': bool,
                'current_count': int,
                'limit': int or None,
                'remaining': int or None,
                'user_type': str
            }
        """
        daily_stats = self.get_daily_stats()
        current_count = daily_stats.get('bookmarks_uploaded', 0)

        # Pro users have no limit
        if user_type.lower() == "pro":
            return {
                'limit_reached': False,
                'current_count': current_count,
                'limit': None,
                'remaining': None,
                'user_type': 'pro',
                'message': 'Pro user - unlimited uploads'
            }

        # Basic users have daily limit
        limit_reached = current_count >= limit
        remaining = max(0, limit - current_count)

        result = {
            'limit_reached': limit_reached,
            'current_count': current_count,
            'limit': limit,
            'remaining': remaining,
            'user_type': 'basic'
        }

        if limit_reached:
            result['message'] = f'Daily limit reached: {current_count}/{limit} bookmarks uploaded today'
        else:
            result['message'] = f'Daily usage: {current_count}/{limit} bookmarks ({remaining} remaining)'

        return result

    # ═══════════════════════════════════════════════════════════
    # Multi-Profile State Management
    # ═══════════════════════════════════════════════════════════

    def load_profile_state(self) -> Dict[str, Any]:
        """
        Load multi-profile state.

        Returns:
            Dict with profile state: {current_profile_index, total_profiles, last_updated}
        """
        try:
            state = self.load_state()

            if 'profile_state' not in state:
                return {}

            return state['profile_state']

        except Exception as e:
            logger.error("[StateManager] Failed to load profile state: %s", str(e))
            return {}

    def save_profile_state(self, profile_state: Dict[str, Any]):
        """
        Save multi-profile state.

        Args:
            profile_state: Profile state to save
        """
        try:
            state = self.load_state()
            state['profile_state'] = profile_state
            state['profile_state']['last_updated'] = time.strftime("%Y-%m-%d %H:%M:%S")
            self.save_state(state)

            logger.debug("[StateManager] Saved profile state: index %d",
                        profile_state.get('current_profile_index', 0))

        except Exception as e:
            logger.error("[StateManager] Failed to save profile state: %s", str(e))
