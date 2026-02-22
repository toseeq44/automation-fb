"""
modules/video_editor/videos_merger/smart_clip_processor.py
Background worker for Smart Clip Merge mode.
"""

import random
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QThread, pyqtSignal

from modules.logging.logger import get_logger
from .merge_engine import MergeSettings, merge_videos
from .utils import generate_batch_filename, generate_output_filename, safe_delete_file

logger = get_logger(__name__)

try:
    from moviepy import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


class SmartClipMergeProcessor(QThread):
    """Background processor for Smart Clip Merge."""

    progress_updated = pyqtSignal(str, float)
    batch_progress_updated = pyqtSignal(int, int, str, float)
    merge_completed = pyqtSignal(bool, dict)
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(
        self,
        mode: str,
        batches: List[List[Dict[str, Any]]],
        output_folder: str,
        clip_mode: str,
        global_seconds: int,
        output_format: str,
        output_quality: str,
        delete_source: bool,
        transition_type: str = "none",
        transition_duration: float = 1.0,
        merge_overrides: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.mode = mode
        self.batches = batches
        self.output_folder = output_folder
        self.clip_mode = clip_mode
        self.global_seconds = max(1, int(global_seconds))
        self.output_format = output_format.lower()
        self.output_quality = output_quality
        self.delete_source = delete_source
        self.transition_type = transition_type
        self.transition_duration = transition_duration
        self.merge_overrides = merge_overrides or {}

        self._is_paused = False
        self._is_cancelled = False
        self._is_running = False

    def run(self):
        self._is_running = True
        self._is_cancelled = False
        self._is_paused = False

        if not MOVIEPY_AVAILABLE:
            msg = "MoviePy is not available. Install with: pip install moviepy"
            self.error_occurred.emit(msg)
            self.merge_completed.emit(False, {"error": msg})
            self._is_running = False
            return

        try:
            output_dir = Path(self.output_folder)
            output_dir.mkdir(parents=True, exist_ok=True)

            total_batches = len(self.batches)
            if total_batches == 0:
                self.merge_completed.emit(False, {"error": "No valid batches to process"})
                return

            results = {
                "total_batches": total_batches,
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "output_files": [],
                "errors": [],
            }

            for idx, batch_items in enumerate(self.batches, start=1):
                if self._check_pause_cancel():
                    results["cancelled"] = True
                    break

                if len(batch_items) < 2:
                    results["skipped"] += 1
                    results["processed"] += 1
                    continue

                self.batch_progress_updated.emit(idx, total_batches, f"Preparing batch {idx}", 0.0)
                self.log_message.emit(f"Batch {idx}: extracting smart clips from {len(batch_items)} videos")

                with tempfile.TemporaryDirectory(prefix="smart_clip_") as tmp_dir:
                    extracted_paths: List[str] = []
                    source_paths: List[str] = []
                    extraction_failed = False

                    for item_index, item in enumerate(batch_items, start=1):
                        if self._check_pause_cancel():
                            extraction_failed = True
                            break

                        source_path = item["path"]
                        clip_seconds = int(item.get("clip_seconds") or self.global_seconds)
                        if clip_seconds <= 0:
                            clip_seconds = self.global_seconds

                        temp_name = f"clip_{item_index:03d}.mp4"
                        temp_path = str(Path(tmp_dir) / temp_name)

                        ok, err = self._extract_clip(source_path, clip_seconds, temp_path)
                        if not ok:
                            extraction_failed = True
                            results["errors"].append(f"Batch {idx}: {Path(source_path).name} - {err}")
                            self.log_message.emit(
                                f"Batch {idx}: failed to extract clip from {Path(source_path).name} ({err})"
                            )
                            break

                        extracted_paths.append(temp_path)
                        source_paths.append(source_path)
                        pct = (item_index / len(batch_items)) * 45.0
                        self.batch_progress_updated.emit(
                            idx, total_batches, f"Extracting {item_index}/{len(batch_items)}", pct
                        )

                    if self._is_cancelled:
                        results["cancelled"] = True
                        break

                    if extraction_failed or len(extracted_paths) < 2:
                        results["failed"] += 1
                        results["processed"] += 1
                        continue

                    if self.mode == "simple":
                        output_name = generate_output_filename("smart_clip_merged", self.output_format)
                    else:
                        output_name = generate_batch_filename(idx, self.output_format)
                    output_path = str(output_dir / output_name)

                    settings = MergeSettings()
                    settings.output_quality = self.output_quality
                    settings.output_format = self.output_format
                    settings.transition_type = self.transition_type
                    settings.transition_duration = self.transition_duration
                    settings.keep_audio = True
                    settings.delete_source = False
                    for key, value in self.merge_overrides.items():
                        if hasattr(settings, key):
                            setattr(settings, key, value)

                    def merge_progress(msg: str, pct: float):
                        if self._check_pause_cancel():
                            return
                        scaled = 45.0 + (pct / 100.0) * 55.0
                        self.batch_progress_updated.emit(idx, total_batches, msg, scaled)

                    success = merge_videos(
                        extracted_paths,
                        output_path,
                        settings,
                        merge_progress,
                        lambda: (self._is_paused, self._is_cancelled),
                    )

                    if success and self.delete_source:
                        for src in source_paths:
                            safe_delete_file(src)

                    if success:
                        results["successful"] += 1
                        results["output_files"].append(output_path)
                        self.log_message.emit(f"Batch {idx}: completed ({output_path})")
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Batch {idx}: merge failed")
                        self.log_message.emit(f"Batch {idx}: merge failed")

                    results["processed"] += 1

            if self._is_cancelled:
                self.log_message.emit("Smart Clip Merge cancelled")
                self.merge_completed.emit(False, results)
            elif results["successful"] > 0:
                self.log_message.emit(
                    f"Smart Clip Merge completed: {results['successful']} success, {results['failed']} failed"
                )
                self.merge_completed.emit(True, results)
            else:
                err = results["errors"][0] if results["errors"] else "No output generated"
                self.merge_completed.emit(False, {"error": err, **results})
        except Exception as e:
            logger.error(f"Error in SmartClipMergeProcessor: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
            self.merge_completed.emit(False, {"error": str(e)})
        finally:
            self._is_running = False

    def _effective_seconds(self, duration: float, requested_seconds: int) -> float:
        """Apply smart duration rule for short videos."""
        if duration <= 0:
            return 0.0
        req = max(1.0, float(requested_seconds))
        if duration < req:
            return max(0.5, duration / 2.0)
        return min(req, duration)

    def _extract_clip(self, source_path: str, requested_seconds: int, output_path: str) -> tuple[bool, str]:
        """Extract a smart clip from source video."""
        clip = None
        segment = None
        try:
            clip = VideoFileClip(source_path)
            duration = float(clip.duration or 0.0)
            if duration <= 0.0:
                return False, "invalid video duration"

            effective_seconds = self._effective_seconds(duration, requested_seconds)
            max_start = max(0.0, duration - effective_seconds)

            if self.clip_mode == "random":
                start_time = random.uniform(0.0, max_start) if max_start > 0 else 0.0
            else:
                start_time = max_start / 2.0

            end_time = min(duration, start_time + effective_seconds)
            if end_time <= start_time:
                return False, "failed to compute valid clip range"

            segment = clip.subclipped(start_time, end_time)
            segment.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                preset="medium",
                threads=2,
                logger=None,
            )
            return True, ""
        except Exception as e:
            return False, str(e)
        finally:
            if segment:
                try:
                    segment.close()
                except Exception:
                    pass
            if clip:
                try:
                    clip.close()
                except Exception:
                    pass

    def _check_pause_cancel(self) -> bool:
        if self._is_cancelled:
            return True
        while self._is_paused and not self._is_cancelled:
            time.sleep(0.1)
        return self._is_cancelled

    def pause(self):
        if self._is_running and not self._is_paused:
            self._is_paused = True
            self.log_message.emit("Processing paused")

    def resume(self):
        if self._is_running and self._is_paused:
            self._is_paused = False
            self.log_message.emit("Processing resumed")

    def cancel(self):
        if self._is_running:
            self._is_cancelled = True
            self._is_paused = False
            self.log_message.emit("Cancelling...")

    def is_paused(self) -> bool:
        return self._is_paused

    def is_running(self) -> bool:
        return self._is_running

    def is_cancelled(self) -> bool:
        return self._is_cancelled
