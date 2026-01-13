"""
modules/video_editor/videos_merger/merge_processor.py
Background worker thread for video merging with pause/resume support
"""

import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from PyQt5.QtCore import QThread, pyqtSignal
from .merge_engine import merge_videos, MergeSettings
from .bulk_merge_engine import BulkMergeEngine
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class MergeProcessor(QThread):
    """Background worker for video merging operations"""

    # Signals
    progress_updated = pyqtSignal(str, float)  # (status_message, percentage)
    batch_progress_updated = pyqtSignal(int, int, str, float)  # (current, total, status, percentage)
    merge_completed = pyqtSignal(bool, dict)  # (success, results)
    error_occurred = pyqtSignal(str)  # (error_message)
    log_message = pyqtSignal(str)  # (log_message)

    def __init__(self):
        super().__init__()

        # Control flags
        self._is_paused = False
        self._is_cancelled = False
        self._is_running = False

        # Mode: 'simple' or 'bulk'
        self.mode = 'simple'

        # Simple merge data
        self.video_paths: List[str] = []
        self.output_path: str = ""

        # Bulk merge data
        self.folder_paths: List[str] = []
        self.output_folder: str = ""

        # Settings
        self.settings: Optional[MergeSettings] = None

        # State persistence
        self.state_file = Path.home() / ".video_merger_state.json"

    def set_simple_merge(self, video_paths: List[str], output_path: str, settings: MergeSettings):
        """
        Configure for simple merge mode

        Args:
            video_paths: List of video paths to merge
            output_path: Output file path
            settings: Merge settings
        """
        self.mode = 'simple'
        self.video_paths = video_paths
        self.output_path = output_path
        self.settings = settings

    def set_bulk_merge(self, folder_paths: List[str], output_folder: str, settings: MergeSettings):
        """
        Configure for bulk folder merge mode

        Args:
            folder_paths: List of folder paths
            output_folder: Output folder path
            settings: Merge settings
        """
        self.mode = 'bulk'
        self.folder_paths = folder_paths
        self.output_folder = output_folder
        self.settings = settings

    def run(self):
        """Main processing loop"""
        self._is_running = True
        self._is_cancelled = False
        self._is_paused = False

        try:
            if self.mode == 'simple':
                self._process_simple_merge()
            elif self.mode == 'bulk':
                self._process_bulk_merge()
            else:
                self.error_occurred.emit(f"Unknown mode: {self.mode}")
                self.merge_completed.emit(False, {})

        except Exception as e:
            logger.error(f"Error in merge processor: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
            self.merge_completed.emit(False, {'error': str(e)})

        finally:
            self._is_running = False

    def _process_simple_merge(self):
        """Process simple video merge"""
        try:
            self.log_message.emit(f"Starting simple merge: {len(self.video_paths)} videos")

            def progress_callback(msg, pct):
                if self._check_pause_cancel():
                    return
                self.progress_updated.emit(msg, pct)
                self.log_message.emit(f"[{pct:.1f}%] {msg}")

            success = merge_videos(
                self.video_paths,
                self.output_path,
                self.settings,
                progress_callback
            )

            if self._is_cancelled:
                self.log_message.emit("Merge cancelled")
                self.merge_completed.emit(False, {'cancelled': True})
            elif success:
                self.log_message.emit(f"Merge completed: {self.output_path}")
                self.merge_completed.emit(True, {
                    'output_path': self.output_path,
                    'video_count': len(self.video_paths)
                })
            else:
                self.log_message.emit("Merge failed")
                self.merge_completed.emit(False, {'error': 'Merge failed'})

        except Exception as e:
            logger.error(f"Error in simple merge: {e}")
            self.error_occurred.emit(str(e))
            self.merge_completed.emit(False, {'error': str(e)})

    def _process_bulk_merge(self):
        """Process bulk folder merge"""
        try:
            self.log_message.emit(f"Starting bulk merge: {len(self.folder_paths)} folders")

            engine = BulkMergeEngine()

            # Load folders
            self.progress_updated.emit("Loading folders...", 0)
            if not engine.load_folders(self.folder_paths):
                self.error_occurred.emit("Failed to load folders")
                self.merge_completed.emit(False, {'error': 'Failed to load folders'})
                return

            # Create batches
            self.progress_updated.emit("Creating batches...", 5)
            engine.create_batches()

            summary = engine.get_batch_summary()
            self.log_message.emit(f"Created {summary['active_batches']} active batches "
                                  f"({summary['skipped_batches']} skipped)")

            # Process batches
            def batch_progress(current, total, status, pct):
                if self._check_pause_cancel():
                    return
                self.batch_progress_updated.emit(current, total, status, pct)
                self.log_message.emit(f"Batch {current}/{total}: {status} ({pct:.1f}%)")

            results = engine.process_batches(
                self.output_folder,
                self.settings,
                batch_progress,
                lambda: self._is_paused or self._is_cancelled
            )

            if self._is_cancelled:
                self.log_message.emit("Bulk merge cancelled")
                results['cancelled'] = True
                self.merge_completed.emit(False, results)
            else:
                self.log_message.emit(f"Bulk merge completed: {results['successful']} successful, "
                                      f"{results['failed']} failed, {results['skipped']} skipped")
                self.merge_completed.emit(True, results)

        except Exception as e:
            logger.error(f"Error in bulk merge: {e}")
            self.error_occurred.emit(str(e))
            self.merge_completed.emit(False, {'error': str(e)})

    def _check_pause_cancel(self) -> bool:
        """
        Check if processing should pause or cancel

        Returns:
            True if cancelled
        """
        # Check for cancel
        if self._is_cancelled:
            return True

        # Check for pause
        while self._is_paused and not self._is_cancelled:
            time.sleep(0.1)

        return self._is_cancelled

    def pause(self):
        """Pause processing"""
        if self._is_running and not self._is_paused:
            self._is_paused = True
            self.log_message.emit("Processing paused")
            self.save_state()
            logger.info("Merge processor paused")

    def resume(self):
        """Resume processing"""
        if self._is_running and self._is_paused:
            self._is_paused = False
            self.log_message.emit("Processing resumed")
            logger.info("Merge processor resumed")

    def cancel(self):
        """Cancel processing"""
        if self._is_running:
            self._is_cancelled = True
            self._is_paused = False
            self.log_message.emit("Cancelling...")
            logger.info("Merge processor cancelled")

    def is_paused(self) -> bool:
        """Check if paused"""
        return self._is_paused

    def is_running(self) -> bool:
        """Check if running"""
        return self._is_running

    def is_cancelled(self) -> bool:
        """Check if cancelled"""
        return self._is_cancelled

    def save_state(self):
        """Save current state to file for resume capability"""
        try:
            state = {
                'mode': self.mode,
                'video_paths': self.video_paths,
                'output_path': self.output_path,
                'folder_paths': self.folder_paths,
                'output_folder': self.output_folder,
                'settings': self.settings.to_dict() if self.settings else None,
                'timestamp': time.time()
            }

            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

            logger.info(f"State saved to: {self.state_file}")

        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def load_state(self) -> bool:
        """
        Load saved state from file

        Returns:
            True if state loaded successfully
        """
        try:
            if not self.state_file.exists():
                return False

            with open(self.state_file, 'r') as f:
                state = json.load(f)

            self.mode = state.get('mode', 'simple')
            self.video_paths = state.get('video_paths', [])
            self.output_path = state.get('output_path', '')
            self.folder_paths = state.get('folder_paths', [])
            self.output_folder = state.get('output_folder', '')

            settings_dict = state.get('settings')
            if settings_dict:
                self.settings = MergeSettings.from_dict(settings_dict)

            logger.info(f"State loaded from: {self.state_file}")
            return True

        except Exception as e:
            logger.error(f"Error loading state: {e}")
            return False

    def clear_state(self):
        """Clear saved state file"""
        try:
            if self.state_file.exists():
                self.state_file.unlink()
                logger.info("State file cleared")
        except Exception as e:
            logger.error(f"Error clearing state: {e}")


class SimpleMergeProcessor(MergeProcessor):
    """Specialized processor for simple merging"""

    def __init__(self, video_paths: List[str], output_path: str, settings: MergeSettings):
        super().__init__()
        self.set_simple_merge(video_paths, output_path, settings)


class BulkMergeProcessor(MergeProcessor):
    """Specialized processor for bulk folder merging"""

    def __init__(self, folder_paths: List[str], output_folder: str, settings: MergeSettings):
        super().__init__()
        self.set_bulk_merge(folder_paths, output_folder, settings)
