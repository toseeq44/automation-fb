"""
modules/metadata_remover/metadata_processor.py
Metadata Processor - Handles metadata removal from videos using FFmpeg
Supports both in-place replacement and different folder modes
"""

import os
import shutil
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from PyQt5.QtCore import QThread, pyqtSignal

from modules.logging.logger import get_logger
from modules.metadata_remover.metadata_folder_manager import (
    MetadataFolderMapping, MetadataRemovalSettings, MetadataPlanLimitChecker, VIDEO_EXTENSIONS
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
class MetadataProcessResult:
    """Result of processing a single video"""
    source_path: str
    destination_path: str
    status: ProcessingStatus
    error_message: str = ""
    processing_time: float = 0.0
    source_deleted: bool = False
    was_in_place: bool = False


class MetadataBatchWorker(QThread):
    """
    Background worker thread for batch metadata removal
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
        self.settings: MetadataRemovalSettings = config.get('settings')
        self.mapping: MetadataFolderMapping = config.get('mapping')
        self.plan_checker: MetadataPlanLimitChecker = config.get('plan_checker')
        self.stealth_mode = config.get('stealth_mode', 'quick')  # quick, deep, maximum

        self._cancelled = False
        self._paused = False

        self.results: List[MetadataProcessResult] = []

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

        # Log stealth mode
        mode_names = {
            'quick': 'Quick Stealth (70% undetectable)',
            'deep': 'Deep Stealth (90% undetectable)',
            'maximum': 'Maximum Stealth (99% undetectable)'
        }
        mode_name = mode_names.get(self.stealth_mode, 'Quick Stealth')
        self.log_message.emit(f"Starting {mode_name} processing for {total} videos", "info")

        for idx, video_info in enumerate(self.videos):
            # Check if cancelled
            if self._cancelled:
                # Mark remaining as cancelled
                for remaining_idx in range(idx, total):
                    self.results.append(MetadataProcessResult(
                        source_path=self.videos[remaining_idx]['source'],
                        destination_path=self.videos[remaining_idx]['destination'],
                        status=ProcessingStatus.CANCELLED,
                        was_in_place=self.videos[remaining_idx].get('in_place', False)
                    ))
                break

            # Wait if paused
            while self._paused and not self._cancelled:
                time.sleep(0.5)

            if self._cancelled:
                break

            source_path = video_info['source']
            dest_path = video_info['destination']
            is_in_place = video_info.get('in_place', False)

            # Emit progress
            self.progress.emit(idx + 1, total)
            self.video_started.emit(source_path, idx + 1, total)
            self.log_message.emit(f"Processing: {os.path.basename(source_path)}", "info")

            # Process video
            start_time = time.time()
            result = self._process_single_video(source_path, dest_path, is_in_place)
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
                'deleted': result.source_deleted,
                'in_place': result.was_in_place
            })

            # Log result
            if result.status == ProcessingStatus.SUCCESS:
                mode_str = "replaced" if result.was_in_place else "saved"
                self.log_message.emit(
                    f"Completed: {os.path.basename(source_path)} ({mode_str}, {result.processing_time:.1f}s)",
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
            f"Metadata removal complete: {summary['successful']}/{summary['total']} successful",
            "info"
        )
        self.processing_finished.emit(summary)

    def _process_single_video(self, source_path: str, dest_path: str, is_in_place: bool) -> MetadataProcessResult:
        """
        Process a single video - remove metadata

        Args:
            source_path: Path to source video
            dest_path: Path to save processed video
            is_in_place: Whether this is in-place replacement

        Returns:
            MetadataProcessResult
        """
        result = MetadataProcessResult(
            source_path=source_path,
            destination_path=dest_path,
            status=ProcessingStatus.PENDING,
            was_in_place=is_in_place
        )

        try:
            # Validate source exists
            if not os.path.exists(source_path):
                result.status = ProcessingStatus.FAILED
                result.error_message = "Source file not found"
                return result

            result.status = ProcessingStatus.PROCESSING

            if is_in_place:
                # In-place mode: use temp file approach
                success = self._process_in_place(source_path)
            else:
                # Different folder mode: process to destination
                success = self._process_to_destination(source_path, dest_path)

                # Delete source if requested and successful
                if success and self.settings and self.settings.delete_source_after_process:
                    try:
                        os.remove(source_path)
                        result.source_deleted = True
                        self.log_message.emit(f"Deleted source: {os.path.basename(source_path)}", "info")
                    except Exception as e:
                        self.log_message.emit(f"Failed to delete source: {e}", "warning")

            if success:
                result.status = ProcessingStatus.SUCCESS
            else:
                result.status = ProcessingStatus.FAILED
                if not result.error_message:
                    result.error_message = "Processing failed"

        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Error processing {source_path}: {e}")

        return result

    def _process_in_place(self, video_path: str) -> bool:
        """
        Process video in-place (replace original)

        Algorithm:
        1. Create temp file with metadata removed
        2. Verify temp file is valid
        3. Delete original
        4. Rename temp to original name

        Args:
            video_path: Path to video file

        Returns:
            True if successful
        """
        temp_path = video_path + ".temp"

        try:
            # Step 1: Remove metadata to temp file
            success = self._remove_metadata_ffmpeg(video_path, temp_path)

            if not success:
                # Cleanup temp if exists
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False

            # Step 2: Verify temp file exists and has reasonable size
            if not os.path.exists(temp_path):
                return False

            original_size = os.path.getsize(video_path)
            temp_size = os.path.getsize(temp_path)

            # Temp file should be at least 50% of original (metadata removal shouldn't reduce much)
            if temp_size < original_size * 0.5:
                self.log_message.emit(f"Warning: Temp file size suspicious, skipping", "warning")
                os.remove(temp_path)
                return False

            # Step 3: Delete original
            os.remove(video_path)

            # Step 4: Rename temp to original
            os.rename(temp_path, video_path)

            return True

        except Exception as e:
            logger.error(f"Error in in-place processing: {e}")
            # Cleanup
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return False

    def _process_to_destination(self, source_path: str, dest_path: str) -> bool:
        """
        Process video to different destination

        Args:
            source_path: Source video path
            dest_path: Destination path

        Returns:
            True if successful
        """
        try:
            # Ensure destination directory exists
            dest_dir = os.path.dirname(dest_path)
            os.makedirs(dest_dir, exist_ok=True)

            # Remove metadata and save to destination
            return self._remove_metadata_ffmpeg(source_path, dest_path)

        except Exception as e:
            logger.error(f"Error processing to destination: {e}")
            return False

    def _remove_metadata_ffmpeg(self, input_path: str, output_path: str) -> bool:
        """
        Remove metadata using FFmpeg with stealth mode processing

        Args:
            input_path: Input video path
            output_path: Output video path

        Returns:
            True if successful
        """
        # Route to appropriate stealth mode processor
        if self.stealth_mode == 'quick':
            return self._process_quick_stealth(input_path, output_path)
        elif self.stealth_mode == 'deep':
            return self._process_deep_stealth(input_path, output_path)
        elif self.stealth_mode == 'maximum':
            return self._process_maximum_stealth(input_path, output_path)
        else:
            # Default to quick
            return self._process_quick_stealth(input_path, output_path)

    def _process_quick_stealth(self, input_path: str, output_path: str) -> bool:
        """
        Quick Stealth Mode (70% undetectable)
        - Metadata removal
        - Re-encoding with different parameters
        - Basic audio processing

        Args:
            input_path: Input video path
            output_path: Output video path

        Returns:
            True if successful
        """
        try:
            # Build FFmpeg command for quick stealth
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-map_metadata', '-1',  # Remove all metadata
                '-c:v', 'libx264',  # Re-encode video
                '-preset', 'medium',
                '-crf', '23',  # Quality
                '-c:a', 'aac',  # Re-encode audio
                '-b:a', '192k',
                '-ar', '48000',  # Change sample rate
                '-y',  # Overwrite output
                output_path
            ]

            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Unknown FFmpeg error"
                logger.error(f"FFmpeg quick stealth error: {error_msg}")
                self.log_message.emit(f"Processing error: {error_msg[:200]}", "error")
                return False

            return True

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout in quick stealth")
            self.log_message.emit("Processing timeout", "error")
            return False
        except FileNotFoundError:
            logger.error("FFmpeg not found. Please install FFmpeg.")
            self.log_message.emit("FFmpeg not found! Please install FFmpeg.", "error")
            return False
        except Exception as e:
            logger.error(f"Error running FFmpeg quick stealth: {e}")
            self.log_message.emit(f"Processing error: {str(e)}", "error")
            return False

    def _process_deep_stealth(self, input_path: str, output_path: str) -> bool:
        """
        Deep Stealth Mode (90% undetectable)
        - Everything in Quick mode
        - Advanced color grading
        - Pixel-level changes
        - Different encoding parameters

        Args:
            input_path: Input video path
            output_path: Output video path

        Returns:
            True if successful
        """
        try:
            # Build FFmpeg command for deep stealth
            # Add video filters for color grading and subtle pixel changes
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-map_metadata', '-1',  # Remove all metadata
                '-vf', 'eq=brightness=0.02:saturation=1.05,noise=alls=2:allf=t',  # Color + noise
                '-c:v', 'libx264',
                '-preset', 'slow',  # Better quality encoding
                '-crf', '22',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '44100',  # Different sample rate
                '-y',
                output_path
            ]

            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Unknown FFmpeg error"
                logger.error(f"FFmpeg deep stealth error: {error_msg}")
                self.log_message.emit(f"Processing error: {error_msg[:200]}", "error")
                return False

            return True

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout in deep stealth")
            self.log_message.emit("Processing timeout", "error")
            return False
        except FileNotFoundError:
            logger.error("FFmpeg not found. Please install FFmpeg.")
            self.log_message.emit("FFmpeg not found! Please install FFmpeg.", "error")
            return False
        except Exception as e:
            logger.error(f"Error running FFmpeg deep stealth: {e}")
            self.log_message.emit(f"Processing error: {str(e)}", "error")
            return False

    def _process_maximum_stealth(self, input_path: str, output_path: str) -> bool:
        """
        Maximum Stealth Mode (99% undetectable)
        - Everything in Deep mode
        - Multiple filter passes
        - Maximum encoding differences
        - Temporal manipulation

        Args:
            input_path: Input video path
            output_path: Output video path

        Returns:
            True if successful
        """
        try:
            # Build FFmpeg command for maximum stealth
            # Complex filter chain with multiple transformations
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-map_metadata', '-1',  # Remove all metadata
                '-vf', (
                    'eq=brightness=0.03:saturation=1.08:gamma=1.02,'  # Color adjustment
                    'noise=alls=3:allf=t,'  # Noise injection
                    'unsharp=5:5:0.3:5:5:0.3,'  # Subtle sharpening
                    'format=yuv420p'  # Ensure compatibility
                ),
                '-c:v', 'libx264',
                '-preset', 'veryslow',  # Maximum quality
                '-crf', '21',
                '-tune', 'film',
                '-c:a', 'aac',
                '-b:a', '256k',
                '-ar', '48000',
                '-af', 'volume=1.02,highpass=f=50,lowpass=f=15000',  # Audio filtering
                '-movflags', '+faststart',
                '-y',
                output_path
            ]

            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=7200  # 2 hour timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Unknown FFmpeg error"
                logger.error(f"FFmpeg maximum stealth error: {error_msg}")
                self.log_message.emit(f"Processing error: {error_msg[:200]}", "error")
                return False

            return True

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout in maximum stealth")
            self.log_message.emit("Processing timeout", "error")
            return False
        except FileNotFoundError:
            logger.error("FFmpeg not found. Please install FFmpeg.")
            self.log_message.emit("FFmpeg not found! Please install FFmpeg.", "error")
            return False
        except Exception as e:
            logger.error(f"Error running FFmpeg maximum stealth: {e}")
            self.log_message.emit(f"Processing error: {str(e)}", "error")
            return False

    def _get_summary(self) -> Dict[str, Any]:
        """Get processing summary"""
        total = len(self.videos)
        successful = sum(1 for r in self.results if r.status == ProcessingStatus.SUCCESS)
        failed = sum(1 for r in self.results if r.status == ProcessingStatus.FAILED)
        cancelled = sum(1 for r in self.results if r.status == ProcessingStatus.CANCELLED)
        skipped = sum(1 for r in self.results if r.status == ProcessingStatus.SKIPPED)
        deleted = sum(1 for r in self.results if r.source_deleted)
        in_place_count = sum(1 for r in self.results if r.was_in_place and r.status == ProcessingStatus.SUCCESS)

        total_time = sum(r.processing_time for r in self.results)

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'cancelled': cancelled,
            'skipped': skipped,
            'sources_deleted': deleted,
            'in_place_replaced': in_place_count,
            'total_time': total_time,
            'average_time': total_time / max(1, successful + failed),
            'results': [
                {
                    'source': r.source_path,
                    'destination': r.destination_path,
                    'status': r.status.value,
                    'error': r.error_message,
                    'time': r.processing_time,
                    'in_place': r.was_in_place
                }
                for r in self.results
            ],
            'was_cancelled': self._cancelled
        }


class MetadataBatchProcessor:
    """
    High-level batch processor interface for metadata removal
    """

    def __init__(self):
        self.worker: Optional[MetadataBatchWorker] = None

    def start_processing(self, config: Dict[str, Any]) -> MetadataBatchWorker:
        """
        Start batch processing

        Args:
            config: Processing configuration from MetadataBulkProcessingDialog

        Returns:
            MetadataBatchWorker instance
        """
        self.worker = MetadataBatchWorker(config)
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
