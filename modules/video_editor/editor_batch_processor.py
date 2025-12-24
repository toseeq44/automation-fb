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
        logger.info("🧵 EditorBatchWorker.__init__ called")
        logger.info(f"   Config keys: {list(config.keys()) if config else 'None'}")

        self.config = config
        self.videos = config.get('videos', [])
        self.settings: EditorMappingSettings = config.get('settings')
        self.mapping: EditorFolderMapping = config.get('mapping')
        self.plan_checker: PlanLimitChecker = config.get('plan_checker')

        logger.info(f"   Videos to process: {len(self.videos)}")
        logger.info(f"   Settings: {self.settings is not None}")
        logger.info(f"   Mapping: {self.mapping is not None}")

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
        logger.info("🏃 EditorBatchWorker.run() - Thread started")

        total = len(self.videos)
        logger.info(f"   Total videos to process: {total}")

        if total == 0:
            logger.warning("   No videos to process!")
            self.log_message.emit("No videos to process", "warning")
            self.processing_finished.emit(self._get_summary())
            return

        self.log_message.emit(f"Starting batch processing of {total} videos", "info")
        logger.info(f"   Processing loop starting...")

        # Load preset if specified
        preset = None
        logger.info(f"   Checking for preset...")
        logger.info(f"   Settings: {self.settings is not None}")
        if self.settings:
            logger.info(f"   Preset ID: {self.settings.preset_id}")

        if self.settings and self.settings.preset_id:
            logger.info(f"   Loading preset: {self.settings.preset_id}")
            preset = self._load_preset(self.settings.preset_id)
            if preset:
                logger.info(f"   ✅ Preset loaded successfully")
                self.log_message.emit(f"Loaded preset: {self.settings.preset_id}", "info")
            else:
                logger.warning(f"   ⚠️  Preset not found or failed to load")
                self.log_message.emit(f"Preset not found: {self.settings.preset_id}", "warning")
        else:
            logger.info(f"   No preset specified, will process without preset")

        for idx, video_info in enumerate(self.videos):
            logger.info(f"   📹 Processing video {idx + 1}/{total}")
            logger.info(f"      Video info: {video_info}")

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

            logger.info(f"      Source path: {source_path}")
            logger.info(f"      Dest path: {dest_path}")

            # Emit progress
            self.progress.emit(idx + 1, total)
            self.video_started.emit(source_path, idx + 1, total)
            # Show full path for better tracking
            self.log_message.emit(f"Processing [{idx + 1}/{total}]: {source_path}", "info")

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

            # Log result with full path
            if result.status == ProcessingStatus.SUCCESS:
                self.log_message.emit(
                    f"✅ SUCCESS: {source_path}\n   → Saved to: {dest_path} ({result.processing_time:.1f}s)",
                    "success"
                )
            else:
                self.log_message.emit(
                    f"❌ FAILED: {source_path}\n   → Error: {result.error_message}",
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
        logger.info(f"🎥 _process_single_video() called")
        logger.info(f"   Source: {source_path}")
        logger.info(f"   Destination: {dest_path}")
        logger.info(f"   Preset: {preset is not None}")

        result = VideoProcessResult(
            source_path=source_path,
            destination_path=dest_path,
            status=ProcessingStatus.PENDING
        )

        try:
            # Validate source exists
            logger.info(f"   Checking if source exists...")
            if not os.path.exists(source_path):
                logger.error(f"   ❌ Source file not found: {source_path}")
                result.status = ProcessingStatus.FAILED
                result.error_message = "Source file not found"
                return result
            logger.info(f"   ✅ Source file exists")

            # Ensure destination directory exists
            dest_dir = os.path.dirname(dest_path)
            logger.info(f"   Creating destination directory: {dest_dir}")
            os.makedirs(dest_dir, exist_ok=True)

            result.status = ProcessingStatus.PROCESSING

            if preset:
                # Try processing with preset using VideoEditor
                logger.info(f"   Processing WITH preset...")
                success = self._process_with_preset(source_path, dest_path, preset)

                # If preset fails, fallback to simple processing
                if not success:
                    logger.warning(f"   Preset processing failed, falling back to simple processing...")
                    self.log_message.emit(f"⚠️  Preset failed, using default processing (110% zoom + metadata removal)", "warning")
                    success = self._process_with_simple_edit(source_path, dest_path)
            else:
                # No preset - use simple processing
                logger.info(f"   Processing WITHOUT preset...")
                success = self._process_with_simple_edit(source_path, dest_path)

            logger.info(f"   Processing result: {'SUCCESS' if success else 'FAILED'}")

            if success:
                result.status = ProcessingStatus.SUCCESS

                # Delete source if requested (but only if NOT in-place editing)
                # In-place editing means source == destination, so no separate source to delete
                is_inplace = os.path.normpath(source_path) == os.path.normpath(dest_path)

                if self.settings and self.settings.delete_source_after_edit and not is_inplace:
                    logger.info(f"   Deleting source file (not in-place editing)...")
                    try:
                        os.remove(source_path)
                        result.source_deleted = True
                        self.log_message.emit(f"🗑️  Deleted original: {source_path}", "info")
                        logger.info(f"   ✅ Source deleted successfully")
                    except Exception as e:
                        logger.warning(f"   ⚠️  Failed to delete source: {e}")
                        self.log_message.emit(f"⚠️  Failed to delete: {source_path}\n   → {e}", "warning")
                elif is_inplace:
                    logger.info(f"   In-place editing - source already replaced, no separate deletion needed")
                    # Mark as deleted for statistics since the original was replaced
                    if self.settings and self.settings.delete_source_after_edit:
                        result.source_deleted = True
            else:
                result.status = ProcessingStatus.FAILED
                if not result.error_message:
                    result.error_message = "Video processing failed - no detailed error available"

        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.error_message = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Error processing {source_path}: {e}", exc_info=True)
            self.log_message.emit(f"💥 Exception: {type(e).__name__}: {str(e)}", "error")

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
        temp_file = None
        try:
            logger.info(f"   🎨 _process_with_preset() starting")
            from modules.video_editor.preset_manager import PresetManager

            preset_manager = PresetManager()
            logger.info(f"      PresetManager created")

            # Check if in-place editing
            is_inplace = os.path.normpath(source_path) == os.path.normpath(dest_path)
            logger.info(f"      In-place editing: {is_inplace}")

            # For in-place editing, use temporary file
            if is_inplace:
                import tempfile
                dest_dir = os.path.dirname(dest_path)
                output_format = 'mp4'
                if self.settings and self.settings.output_format:
                    output_format = self.settings.output_format
                temp_fd, temp_file = tempfile.mkstemp(suffix=f'.{output_format}', dir=dest_dir)
                os.close(temp_fd)
                actual_output = temp_file
                logger.info(f"      Using temporary file: {temp_file}")
                self.log_message.emit(f"📝 In-place editing - using temporary file", "info")
            else:
                actual_output = dest_path

            # Get quality setting
            quality = 'high'
            if self.settings:
                quality = self.settings.quality
            logger.info(f"      Quality: {quality}")

            # Apply preset
            logger.info(f"      Applying preset to video...")
            success = preset_manager.apply_preset_to_video(
                preset=preset,
                video_path=source_path,
                output_path=actual_output,
                quality=quality,
                progress_callback=lambda msg: self.log_message.emit(msg, "info")
            )

            logger.info(f"      Preset apply result: {success}")

            # If successful and in-place editing, replace original
            if success and is_inplace:
                logger.info(f"      Replacing original file with processed version...")
                self.log_message.emit(f"🔄 Replacing original file...", "info")
                try:
                    os.remove(source_path)
                    shutil.move(temp_file, dest_path)
                    temp_file = None  # Mark as moved
                    logger.info(f"      ✅ Original file replaced successfully")
                except Exception as replace_err:
                    logger.error(f"      ❌ Failed to replace original: {replace_err}")
                    self.log_message.emit(f"❌ Failed to replace original: {replace_err}", "error")
                    return False

            return success

        except Exception as e:
            logger.error(f"   ❌ Error applying preset: {e}", exc_info=True)
            self.log_message.emit(f"💥 Preset error: {type(e).__name__}: {str(e)}", "error")
            return False
        finally:
            # Clean up temp file if it still exists
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    logger.info(f"      Cleaned up temporary file")
                except:
                    pass

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
            logger.info(f"   📦 _process_without_preset() starting")
            logger.info(f"      Source: {source_path}")
            logger.info(f"      Dest: {dest_path}")

            # Validate source exists
            logger.info(f"      Validating source exists...")
            if not os.path.exists(source_path):
                logger.error(f"      ❌ Source file not found!")
                self.log_message.emit(f"⚠️  Source file not found: {source_path}", "warning")
                return False
            logger.info(f"      ✅ Source validated")

            # Create destination directory if it doesn't exist
            dest_dir = os.path.dirname(dest_path)
            if dest_dir and not os.path.exists(dest_dir):
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                    self.log_message.emit(f"📁 Created destination directory: {dest_dir}", "info")
                except Exception as e:
                    self.log_message.emit(f"❌ Failed to create directory: {dest_dir}\n   → {e}", "error")
                    return False

            source_ext = Path(source_path).suffix.lower()
            dest_ext = Path(dest_path).suffix.lower()

            # Get output format from settings
            output_format = 'mp4'
            if self.settings and self.settings.output_format:
                output_format = self.settings.output_format

            # Update destination extension if needed
            if dest_ext != f'.{output_format}':
                dest_path = str(Path(dest_path).with_suffix(f'.{output_format}'))

            self.log_message.emit(f"📋 Copy/Convert: {source_ext} → .{output_format}", "info")
            self.log_message.emit(f"📤 Source: {source_path}", "info")
            self.log_message.emit(f"📥 Destination: {dest_path}", "info")

            # If same format and no processing needed, just copy
            if source_ext == f'.{output_format}':
                try:
                    shutil.copy2(source_path, dest_path)
                    self.log_message.emit(f"📄 Direct copy completed successfully", "info")

                    # Verify destination file exists
                    if os.path.exists(dest_path):
                        file_size = os.path.getsize(dest_path)
                        self.log_message.emit(f"✅ Verified: Destination file created ({file_size} bytes)", "success")
                        return True
                    else:
                        self.log_message.emit(f"❌ Copy failed: Destination file not created", "error")
                        return False

                except Exception as copy_err:
                    self.log_message.emit(f"❌ Copy error: {type(copy_err).__name__}: {str(copy_err)}", "error")
                    return False

            # Convert using FFmpeg
            self.log_message.emit(f"🔄 Converting using FFmpeg...", "info")
            return self._convert_video(source_path, dest_path, output_format)

        except Exception as e:
            logger.error(f"Error processing without preset: {e}", exc_info=True)
            self.log_message.emit(f"💥 Processing error: {type(e).__name__}: {str(e)}", "error")
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

            # Ensure destination directory exists
            dest_dir = os.path.dirname(dest_path)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
                self.log_message.emit(f"📁 Created destination directory: {dest_dir}", "info")

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

            self.log_message.emit(f"🎬 Running FFmpeg (quality: {quality})...", "info")

            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr[-500:] if result.stderr else "Unknown FFmpeg error"
                logger.error(f"FFmpeg error: {error_msg}")
                self.log_message.emit(f"⚠️  FFmpeg failed (return code: {result.returncode}), falling back to direct copy", "warning")
                # Try simple copy as fallback
                try:
                    shutil.copy2(source_path, dest_path)
                    self.log_message.emit(f"📄 Fallback copy completed", "info")
                except Exception as copy_err:
                    self.log_message.emit(f"❌ Fallback copy also failed: {copy_err}", "error")
                    return False

            # Verify output file exists
            if os.path.exists(dest_path):
                file_size = os.path.getsize(dest_path)
                self.log_message.emit(f"✅ Conversion successful ({file_size} bytes)", "success")
                return True
            else:
                self.log_message.emit(f"❌ Output file not created after conversion", "error")
                return False

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout")
            self.log_message.emit(f"⏱️  FFmpeg timeout (>10 min), skipping conversion", "error")
            return False
        except FileNotFoundError:
            # FFmpeg not found, fall back to copy
            logger.warning("FFmpeg not found, copying file instead")
            self.log_message.emit(f"ℹ️  FFmpeg not installed - using direct copy", "info")
            try:
                shutil.copy2(source_path, dest_path)
                if os.path.exists(dest_path):
                    file_size = os.path.getsize(dest_path)
                    self.log_message.emit(f"✅ Direct copy completed ({file_size} bytes)", "success")
                    return True
                else:
                    self.log_message.emit(f"❌ Copy failed: File not created", "error")
                    return False
            except Exception as copy_err:
                self.log_message.emit(f"❌ Copy failed: {copy_err}", "error")
                return False
        except Exception as e:
            logger.error(f"Error converting video: {e}", exc_info=True)
            self.log_message.emit(f"💥 Conversion error: {type(e).__name__}: {str(e)}", "error")
            return False

    def _process_with_simple_edit(self, source_path: str, dest_path: str) -> bool:
        """
        Process video with simple default edits using FFmpeg:
        - 110% zoom (scale)
        - Remove metadata

        Args:
            source_path: Source video path
            dest_path: Destination path

        Returns:
            True if successful
        """
        try:
            import subprocess

            logger.info(f"   🎬 _process_with_simple_edit() starting")
            logger.info(f"      Source: {source_path}")
            logger.info(f"      Dest: {dest_path}")
            logger.info(f"      Applying: Mirror + Edge blur + 110% zoom + Voice preservation + Metadata removal")
            self.log_message.emit(f"🎨 Professional edits: Mirror, Edge blur, 110% zoom, Voice preserved", "info")

            # Check if in-place editing (source == destination)
            is_inplace = os.path.normpath(source_path) == os.path.normpath(dest_path)
            logger.info(f"      In-place editing: {is_inplace}")

            # Ensure destination directory exists
            dest_dir = os.path.dirname(dest_path)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
                self.log_message.emit(f"📁 Created destination directory: {dest_dir}", "info")

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

            # Get output format
            output_format = 'mp4'
            if self.settings and self.settings.output_format:
                output_format = self.settings.output_format

            # For in-place editing, use temporary file
            if is_inplace:
                import tempfile
                temp_fd, temp_path = tempfile.mkstemp(suffix=f'.{output_format}', dir=dest_dir)
                os.close(temp_fd)  # Close file descriptor
                actual_output = temp_path
                logger.info(f"      Using temporary file: {temp_path}")
                self.log_message.emit(f"📝 In-place editing - using temporary file", "info")
            else:
                # Update destination extension if needed
                dest_ext = Path(dest_path).suffix.lower()
                if dest_ext != f'.{output_format}':
                    dest_path = str(Path(dest_path).with_suffix(f'.{output_format}'))
                actual_output = dest_path

            # Build FFmpeg command with PROFESSIONAL FILTERS:
            #
            # VIDEO FILTERS (Complex filter graph):
            # 1. Horizontal flip (MIRROR - left to right)
            # 2. Create blurred background layer (heavily blurred full video)
            # 3. Scale main video to 97% (creates 3% border space on all sides)
            # 4. Overlay sharp video on blurred background = TRANSPARENT BLUR EDGES
            # 5. Final 110% zoom with even dimensions
            #
            # AUDIO FILTERS (VOICE PRESERVATION):
            # 1. Gentle highpass (60Hz) - ONLY removes deep bass/rumble, PRESERVES VOICE
            # 2. Mild volume reduction (keeps voice audible)
            # 3. Audio normalization (maintains voice clarity)
            #
            # Voice frequencies: 85-300Hz (MUST PRESERVE)
            # Background music bass: 20-80Hz (can remove)

            # Complex filter for MIRROR + EDGE BLUR effect
            video_filter_complex = (
                "[0:v]split=2[main][bg];"  # Split input into 2 streams
                "[bg]scale=iw:ih,gblur=sigma=20[blurred];"  # Heavy blur for background
                "[main]hflip,scale=iw*0.97:ih*0.97[scaled];"  # MIRROR (hflip) + Scale to 97%
                "[blurred][scaled]overlay=(W-w)/2:(H-h)/2[overlay];"  # Overlay centered
                "[overlay]scale='trunc(iw*1.1/2)*2:trunc(ih*1.1/2)*2'[out]"  # 110% zoom, even dimensions
            )

            # Audio filter - VOICE PRESERVATION (gentle filtering only)
            audio_filters = (
                "highpass=f=60,"  # Remove ONLY deep bass/rumble (60Hz), PRESERVES voice (85-300Hz)
                "volume=0.85,"  # Mild reduction (15% only) - KEEPS VOICE AUDIBLE
                "loudnorm=I=-16:TP=-1.5:LRA=11"  # Normalize loudness (voice clarity)
            )

            cmd = [
                'ffmpeg',
                '-i', source_path,
                '-filter_complex', video_filter_complex,  # Mirror + Edge blur + Zoom
                '-map', '[out]',  # Map output video from complex filter
                '-af', audio_filters,  # VOICE-SAFE audio filters
                '-c:v', 'libx264',
                '-c:a', 'aac',
                *crf_preset,
                '-map_metadata', '-1',  # Remove all metadata
                '-y',  # Overwrite output
                actual_output
            ]

            logger.info(f"      Video filter: Mirror + Edge blur (4 sides) + 110% zoom")
            logger.info(f"      Audio filter: Voice-safe (gentle bass removal only)")
            self.log_message.emit(f"🎬 Professional filters: Mirror + Edge blur + Voice preserved...", "info")

            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr[-500:] if result.stderr else "Unknown FFmpeg error"
                logger.error(f"FFmpeg error: {error_msg}")
                self.log_message.emit(f"❌ FFmpeg failed: {error_msg[:200]}", "error")
                # Clean up temp file if it exists
                if is_inplace and os.path.exists(actual_output):
                    os.remove(actual_output)
                return False

            # Verify output file exists
            if os.path.exists(actual_output):
                file_size = os.path.getsize(actual_output)

                # If in-place editing, replace original with temp file
                if is_inplace:
                    logger.info(f"      Replacing original file with processed version...")
                    self.log_message.emit(f"🔄 Replacing original file...", "info")
                    try:
                        # Remove original and rename temp file
                        os.remove(source_path)
                        shutil.move(actual_output, dest_path)
                        logger.info(f"      ✅ Original file replaced successfully")
                        self.log_message.emit(f"✅ Simple edit completed ({file_size} bytes)", "success")
                    except Exception as replace_err:
                        logger.error(f"      ❌ Failed to replace original: {replace_err}")
                        self.log_message.emit(f"❌ Failed to replace original: {replace_err}", "error")
                        # Clean up temp file
                        if os.path.exists(actual_output):
                            os.remove(actual_output)
                        return False
                else:
                    self.log_message.emit(f"✅ Simple edit completed ({file_size} bytes)", "success")
                    logger.info(f"      ✅ Simple edit successful")

                return True
            else:
                self.log_message.emit(f"❌ Output file not created", "error")
                logger.error(f"      ❌ Output file not created")
                return False

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout")
            self.log_message.emit(f"⏱️  FFmpeg timeout (>10 min)", "error")
            # Clean up temp file if it exists
            if 'is_inplace' in locals() and is_inplace and 'actual_output' in locals() and os.path.exists(actual_output):
                os.remove(actual_output)
            return False
        except FileNotFoundError:
            logger.error("FFmpeg not found")
            self.log_message.emit(f"❌ FFmpeg not installed", "error")
            # Clean up temp file if it exists
            if 'is_inplace' in locals() and is_inplace and 'actual_output' in locals() and os.path.exists(actual_output):
                os.remove(actual_output)
            return False
        except Exception as e:
            logger.error(f"Error in simple edit: {e}", exc_info=True)
            self.log_message.emit(f"💥 Simple edit error: {type(e).__name__}: {str(e)}", "error")
            # Clean up temp file if it exists
            if 'is_inplace' in locals() and is_inplace and 'actual_output' in locals() and os.path.exists(actual_output):
                os.remove(actual_output)
            return False

    def _load_preset(self, preset_name: str):
        """Load preset by name"""
        try:
            logger.info(f"      _load_preset() called for: {preset_name}")
            from modules.video_editor.preset_manager import PresetManager

            preset_manager = PresetManager()
            logger.info(f"      PresetManager created")

            preset = preset_manager.load_preset(preset_name)
            logger.info(f"      Preset loaded: {preset is not None}")
            return preset
        except Exception as e:
            logger.error(f"      ❌ Error loading preset {preset_name}: {e}", exc_info=True)
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
        logger.info("🔧 BatchProcessor.start_processing() called")
        logger.info(f"   Config: {list(config.keys()) if config else 'None'}")
        logger.info(f"   Videos: {len(config.get('videos', []))}")

        self.worker = EditorBatchWorker(config)
        logger.info(f"   Worker created: {self.worker is not None}")

        self.worker.start()
        logger.info(f"   Worker.start() called, is running: {self.worker.isRunning()}")
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
