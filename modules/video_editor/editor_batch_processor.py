"""
modules/video_editor/editor_batch_processor.py
Editor Batch Processor - Handles batch video processing in background thread
Applies presets and exports videos with progress tracking
"""

import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from PyQt5.QtCore import QThread, pyqtSignal

from modules.logging.logger import get_logger
from modules.video_editor.editor_folder_manager import (
    EditorFolderMapping, EditorMappingSettings, PlanLimitChecker, VIDEO_EXTENSIONS
)

logger = get_logger(__name__)


class ProcessingStatus(Enum):
    """Processing status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class VideoProcessResult:
    """Result of processing a single video"""
    source_path: str
    destination_path: str
    status: ProcessingStatus
    error_message: str = ""
    processing_time: float = 0.0
    source_deleted: bool = False


class EditorBatchWorker(QThread):
    """
    Background worker thread for batch video processing
    """

    # Signals
    progress = pyqtSignal(int, int)  # current, total
    video_started = pyqtSignal(str, int, int)  # video_path, current, total
    video_completed = pyqtSignal(dict)  # result dict
    log_message = pyqtSignal(str, str)  # message, level (info, warning, error, success)
    processing_finished = pyqtSignal(dict)  # final summary

    def __init__(self, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config = config
        self.videos = config.get('videos', [])
        self.settings: EditorMappingSettings = config.get('settings')
        self.mapping: EditorFolderMapping = config.get('mapping')
        self.plan_checker: PlanLimitChecker = config.get('plan_checker')

        self._cancelled = False
        self._paused = False

        self.results: List[VideoProcessResult] = []

    def cancel(self):
        """Cancel processing"""
        self._cancelled = True
        self.log_message.emit("Processing cancelled by user", "warning")

    def pause(self):
        """Pause processing"""
        self._paused = True
        self.log_message.emit("Processing paused", "info")

    def resume(self):
        """Resume processing"""
        self._paused = False
        self.log_message.emit("Processing resumed", "info")

    def run(self):
        """Main processing loop"""
        total = len(self.videos)

        if total == 0:
            self.log_message.emit("No videos to process", "warning")
            self.processing_finished.emit(self._get_summary())
            return

        self.log_message.emit(f"Starting batch processing of {total} videos", "info")

        # Load preset if specified
        preset = None
        if self.settings and self.settings.preset_id:
            preset = self._load_preset(self.settings.preset_id)
            if preset:
                self.log_message.emit(f"Loaded preset: {self.settings.preset_id}", "info")
            else:
                self.log_message.emit(f"Preset not found: {self.settings.preset_id}", "warning")

        for idx, video_info in enumerate(self.videos):
            # Check if cancelled
            if self._cancelled:
                # Mark remaining as cancelled
                for remaining_idx in range(idx, total):
                    self.results.append(VideoProcessResult(
                        source_path=self.videos[remaining_idx]['source'],
                        destination_path=self.videos[remaining_idx]['destination'],
                        status=ProcessingStatus.CANCELLED
                    ))
                break

            # Wait if paused
            while self._paused and not self._cancelled:
                time.sleep(0.5)

            if self._cancelled:
                break

            source_path = video_info['source']
            dest_path = video_info['destination']

            # Emit progress
            self.progress.emit(idx + 1, total)
            self.video_started.emit(source_path, idx + 1, total)
            self.log_message.emit(f"Processing: {os.path.basename(source_path)}", "info")

            # Process video
            start_time = time.time()
            result = self._process_single_video(source_path, dest_path, preset)
            result.processing_time = time.time() - start_time

            self.results.append(result)

            # Update plan counter on success
            if result.status == ProcessingStatus.SUCCESS and self.plan_checker:
                self.plan_checker.increment_processed(1)

            # Emit result
            self.video_completed.emit({
                'source': result.source_path,
                'destination': result.destination_path,
                'status': result.status.value,
                'error': result.error_message,
                'time': result.processing_time,
                'deleted': result.source_deleted
            })

            # Log result
            if result.status == ProcessingStatus.SUCCESS:
                self.log_message.emit(
                    f"Completed: {os.path.basename(source_path)} ({result.processing_time:.1f}s)",
                    "success"
                )
            else:
                self.log_message.emit(
                    f"Failed: {os.path.basename(source_path)} - {result.error_message}",
                    "error"
                )

        # Emit final summary
        summary = self._get_summary()
        self.log_message.emit(
            f"Batch processing complete: {summary['successful']}/{summary['total']} successful",
            "info"
        )
        self.processing_finished.emit(summary)

    def _process_single_video(self, source_path: str, dest_path: str, preset=None) -> VideoProcessResult:
        """
        Process a single video

        Args:
            source_path: Path to source video
            dest_path: Path to save processed video
            preset: Optional preset to apply

        Returns:
            VideoProcessResult
        """
        result = VideoProcessResult(
            source_path=source_path,
            destination_path=dest_path,
            status=ProcessingStatus.PENDING
        )

        try:
            # Validate source exists
            if not os.path.exists(source_path):
                result.status = ProcessingStatus.FAILED
                result.error_message = "Source file not found"
                return result

            # Ensure destination directory exists
            dest_dir = os.path.dirname(dest_path)
            os.makedirs(dest_dir, exist_ok=True)

            result.status = ProcessingStatus.PROCESSING

            if preset:
                # Process with preset using VideoEditor
                success = self._process_with_preset(source_path, dest_path, preset)
            else:
                # Just copy/convert without effects
                success = self._process_without_preset(source_path, dest_path)

            if success:
                result.status = ProcessingStatus.SUCCESS

                # Delete source if requested
                if self.settings and self.settings.delete_source_after_edit:
                    try:
                        os.remove(source_path)
                        result.source_deleted = True
                        self.log_message.emit(f"Deleted source: {os.path.basename(source_path)}", "info")
                    except Exception as e:
                        self.log_message.emit(f"Failed to delete source: {e}", "warning")
            else:
                result.status = ProcessingStatus.FAILED
                result.error_message = "Processing failed"

        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Error processing {source_path}: {e}")

        return result

    def _process_with_preset(self, source_path: str, dest_path: str, preset) -> bool:
        """
        Process video with preset

        Args:
            source_path: Source video path
            dest_path: Destination path
            preset: EditingPreset to apply

        Returns:
            True if successful
        """
        try:
            from modules.video_editor.preset_manager import PresetManager

            preset_manager = PresetManager()

            # Get quality setting
            quality = 'high'
            if self.settings:
                quality = self.settings.quality

            # Apply preset
            success = preset_manager.apply_preset_to_video(
                preset=preset,
                video_path=source_path,
                output_path=dest_path,
                quality=quality,
                progress_callback=lambda msg: self.log_message.emit(msg, "info")
            )

            return success

        except Exception as e:
            logger.error(f"Error applying preset: {e}")
            return False

    def _process_without_preset(self, source_path: str, dest_path: str) -> bool:
        """
        Process video without preset (simple copy/convert)
        Keeps original filename

        Args:
            source_path: Source video path
            dest_path: Destination path

        Returns:
            True if successful
        """
        try:
            source_ext = Path(source_path).suffix.lower()
            dest_ext = Path(dest_path).suffix.lower()

            # Get output format from settings
            output_format = 'mp4'
            if self.settings and self.settings.output_format:
                output_format = self.settings.output_format

            # Update destination extension if needed
            if dest_ext != f'.{output_format}':
                dest_path = str(Path(dest_path).with_suffix(f'.{output_format}'))

            # If same format and no processing needed, just copy
            if source_ext == f'.{output_format}':
                shutil.copy2(source_path, dest_path)
                return True

            # Convert using FFmpeg
            return self._convert_video(source_path, dest_path, output_format)

        except Exception as e:
            logger.error(f"Error processing without preset: {e}")
            return False

    def _convert_video(self, source_path: str, dest_path: str, output_format: str) -> bool:
        """
        Convert video using FFmpeg

        Args:
            source_path: Source video path
            dest_path: Destination path
            output_format: Output format (mp4, mkv, etc.)

        Returns:
            True if successful
        """
        try:
            import subprocess

            # Get quality settings
            quality = 'high'
            if self.settings:
                quality = self.settings.quality

            # Quality presets for FFmpeg
            quality_settings = {
                'high': ['-crf', '18', '-preset', 'slow'],
                'medium': ['-crf', '23', '-preset', 'medium'],
                'low': ['-crf', '28', '-preset', 'fast']
            }

            crf_preset = quality_settings.get(quality, quality_settings['medium'])

            # Build FFmpeg command
            cmd = [
                'ffmpeg',
                '-i', source_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                *crf_preset,
                '-y',  # Overwrite output
                dest_path
            ]

            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                # Try simple copy as fallback
                shutil.copy2(source_path, dest_path)

            return True

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout")
            return False
        except FileNotFoundError:
            # FFmpeg not found, fall back to copy
            logger.warning("FFmpeg not found, copying file instead")
            shutil.copy2(source_path, dest_path)
            return True
        except Exception as e:
            logger.error(f"Error converting video: {e}")
            return False

    def _load_preset(self, preset_name: str):
        """Load preset by name"""
        try:
            from modules.video_editor.preset_manager import PresetManager

            preset_manager = PresetManager()
            return preset_manager.load_preset(preset_name)
        except Exception as e:
            logger.error(f"Error loading preset {preset_name}: {e}")
            return None

    def _get_summary(self) -> Dict[str, Any]:
        """Get processing summary"""
        total = len(self.videos)
        successful = sum(1 for r in self.results if r.status == ProcessingStatus.SUCCESS)
        failed = sum(1 for r in self.results if r.status == ProcessingStatus.FAILED)
        cancelled = sum(1 for r in self.results if r.status == ProcessingStatus.CANCELLED)
        skipped = sum(1 for r in self.results if r.status == ProcessingStatus.SKIPPED)
        deleted = sum(1 for r in self.results if r.source_deleted)

        total_time = sum(r.processing_time for r in self.results)

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'cancelled': cancelled,
            'skipped': skipped,
            'sources_deleted': deleted,
            'total_time': total_time,
            'average_time': total_time / max(1, successful + failed),
            'results': [
                {
                    'source': r.source_path,
                    'destination': r.destination_path,
                    'status': r.status.value,
                    'error': r.error_message,
                    'time': r.processing_time
                }
                for r in self.results
            ],
            'was_cancelled': self._cancelled
        }


class BatchProcessor:
    """
    High-level batch processor interface
    """

    def __init__(self):
        self.worker: Optional[EditorBatchWorker] = None

    def start_processing(self, config: Dict[str, Any]) -> EditorBatchWorker:
        """
        Start batch processing

        Args:
            config: Processing configuration from BulkProcessingDialog

        Returns:
            EditorBatchWorker instance
        """
        self.worker = EditorBatchWorker(config)
        self.worker.start()
        return self.worker

    def cancel(self):
        """Cancel current processing"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()

    def pause(self):
        """Pause current processing"""
        if self.worker and self.worker.isRunning():
            self.worker.pause()

    def resume(self):
        """Resume current processing"""
        if self.worker:
            self.worker.resume()

    def is_running(self) -> bool:
        """Check if processing is running"""
        return self.worker is not None and self.worker.isRunning()

    def wait_for_completion(self, timeout: int = None):
        """Wait for processing to complete"""
        if self.worker:
            self.worker.wait(timeout)
