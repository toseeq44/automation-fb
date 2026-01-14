"""
modules/video_editor/videos_merger/merge_engine.py
Core video merging engine with trim, crop, zoom, flip, and transitions
"""

from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from modules.logging.logger import get_logger
from modules.video_editor.transitions import TransitionManager

logger = get_logger(__name__)

# Try to import MoviePy (MoviePy 2.x structure)
try:
    from moviepy import VideoFileClip, concatenate_videoclips, vfx
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    logger.warning("MoviePy not available. Install with: pip install moviepy")


class MergeSettings:
    """Settings for video merging"""

    def __init__(self):
        # Trim settings
        self.trim_start: float = 0.0  # Seconds to trim from start
        self.trim_end: float = 0.0  # Seconds to trim from end

        # Crop settings
        self.crop_enabled: bool = False
        self.crop_preset: Optional[str] = None  # '9:16', '16:9', '1:1', '4:3', '4:5'
        self.crop_coords: Optional[tuple] = None  # (x1, y1, x2, y2)

        # Zoom settings
        self.zoom_enabled: bool = False
        self.zoom_factor: float = 1.0  # 1.0 = no zoom, 1.1 = 110%

        # Flip settings
        self.flip_horizontal: bool = False  # Mirror (left-right)
        self.flip_vertical: bool = False  # Upside down

        # Transition settings
        self.transition_type: str = 'crossfade'  # 'crossfade', 'fade', 'slide_left', etc.
        self.transition_duration: float = 1.0  # Seconds

        # Output settings
        self.output_quality: str = 'high'  # 'source', 'low', 'medium', 'high', 'ultra'
        self.output_format: str = 'mp4'
        self.keep_audio: bool = True
        self.fade_audio: bool = False

        # Deletion settings
        self.delete_source: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary"""
        return {
            'trim_start': self.trim_start,
            'trim_end': self.trim_end,
            'crop_enabled': self.crop_enabled,
            'crop_preset': self.crop_preset,
            'crop_coords': self.crop_coords,
            'zoom_enabled': self.zoom_enabled,
            'zoom_factor': self.zoom_factor,
            'flip_horizontal': self.flip_horizontal,
            'flip_vertical': self.flip_vertical,
            'transition_type': self.transition_type,
            'transition_duration': self.transition_duration,
            'output_quality': self.output_quality,
            'output_format': self.output_format,
            'keep_audio': self.keep_audio,
            'fade_audio': self.fade_audio,
            'delete_source': self.delete_source
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MergeSettings':
        """Create settings from dictionary"""
        settings = cls()
        for key, value in data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        return settings


class VideoMergeEngine:
    """Core engine for merging videos with various effects"""

    # Aspect ratio presets
    ASPECT_PRESETS = {
        '9:16': (9, 16),  # TikTok, Reels vertical
        '16:9': (16, 9),  # YouTube horizontal
        '1:1': (1, 1),  # Instagram square
        '4:3': (4, 3),  # Classic TV
        '4:5': (4, 5),  # Instagram portrait
        '21:9': (21, 9)  # Ultrawide
    }

    # Quality presets (bitrate in kbps)
    QUALITY_PRESETS = {
        'low': {'video_bitrate': '500k', 'audio_bitrate': '96k'},
        'medium': {'video_bitrate': '1500k', 'audio_bitrate': '128k'},
        'high': {'video_bitrate': '5000k', 'audio_bitrate': '192k'},
        'ultra': {'video_bitrate': '15000k', 'audio_bitrate': '320k'}
    }

    def __init__(self):
        if not MOVIEPY_AVAILABLE:
            raise ImportError("MoviePy is not installed. Install with: pip install moviepy")
        self.clips: List[VideoFileClip] = []
        self.processed_clips: List[VideoFileClip] = []

    def load_videos(self, video_paths: List[str]) -> bool:
        """
        Load video files

        Args:
            video_paths: List of video file paths

        Returns:
            True if all loaded successfully
        """
        try:
            self.cleanup()  # Clean up any existing clips

            for path in video_paths:
                if not Path(path).exists():
                    logger.error(f"Video file not found: {path}")
                    return False

                clip = VideoFileClip(path)
                self.clips.append(clip)
                logger.info(f"Loaded video: {path} ({clip.duration:.2f}s)")

            return True
        except Exception as e:
            logger.error(f"Error loading videos: {e}")
            self.cleanup()
            return False

    def apply_trim(self, clip: VideoFileClip, start_trim: float, end_trim: float) -> VideoFileClip:
        """
        Trim video from start and end

        Args:
            clip: Video clip
            start_trim: Seconds to trim from start
            end_trim: Seconds to trim from end

        Returns:
            Trimmed clip
        """
        duration = clip.duration
        new_start = start_trim
        new_end = duration - end_trim

        if new_end <= new_start:
            logger.warning(f"Video too short after trimming (duration: {duration}s)")
            # Return minimal clip (1 second)
            new_end = min(new_start + 1.0, duration)

        logger.info(f"Trimming: {new_start:.2f}s to {new_end:.2f}s (original: {duration:.2f}s)")
        return clip.subclipped(new_start, new_end)

    def apply_crop(self, clip: VideoFileClip, preset: str = None, coords: tuple = None) -> VideoFileClip:
        """
        Crop video to aspect ratio or coordinates

        Args:
            clip: Video clip
            preset: Aspect ratio preset ('9:16', '16:9', etc.)
            coords: Custom coordinates (x1, y1, x2, y2)

        Returns:
            Cropped clip
        """
        if coords:
            x1, y1, x2, y2 = coords
            logger.info(f"Cropping to coordinates: ({x1}, {y1}, {x2}, {y2})")
            return clip.cropped(x1=x1, y1=y1, x2=x2, y2=y2)

        if preset and preset in self.ASPECT_PRESETS:
            width, height = clip.size
            target_w, target_h = self.ASPECT_PRESETS[preset]
            target_ratio = target_w / target_h
            current_ratio = width / height

            if abs(current_ratio - target_ratio) < 0.01:
                logger.info(f"Video already in {preset} aspect ratio")
                return clip

            # Calculate crop dimensions
            if current_ratio > target_ratio:
                # Video is wider, crop width
                new_width = int(height * target_ratio)
                new_height = height
                x1 = (width - new_width) // 2
                y1 = 0
            else:
                # Video is taller, crop height
                new_width = width
                new_height = int(width / target_ratio)
                x1 = 0
                y1 = (height - new_height) // 2

            x2 = x1 + new_width
            y2 = y1 + new_height

            logger.info(f"Cropping to {preset} ({new_width}x{new_height})")
            return clip.cropped(x1=x1, y1=y1, x2=x2, y2=y2)

        return clip

    def apply_zoom(self, clip: VideoFileClip, zoom_factor: float) -> VideoFileClip:
        """
        Apply zoom to video

        Args:
            clip: Video clip
            zoom_factor: Zoom factor (1.0 = no zoom, 1.1 = 110%)

        Returns:
            Zoomed clip
        """
        if abs(zoom_factor - 1.0) < 0.01:
            return clip

        width, height = clip.size
        new_width = int(width * zoom_factor)
        new_height = int(height * zoom_factor)

        # Resize and crop to original size (center)
        resized = clip.resized(width=new_width, height=new_height)

        x1 = (new_width - width) // 2
        y1 = (new_height - height) // 2
        x2 = x1 + width
        y2 = y1 + height

        logger.info(f"Applying zoom: {zoom_factor}x")
        return resized.cropped(x1=x1, y1=y1, x2=x2, y2=y2)

    def apply_flip(self, clip: VideoFileClip, horizontal: bool = False, vertical: bool = False) -> VideoFileClip:
        """
        Flip video horizontally or vertically

        Args:
            clip: Video clip
            horizontal: Flip horizontal (mirror, left-right)
            vertical: Flip vertical (upside down)

        Returns:
            Flipped clip
        """
        if horizontal:
            logger.info("Applying horizontal flip (mirror)")
            # MoviePy 2.x: Use vfx.MirrorX() for horizontal flip
            clip = clip.with_effects([vfx.MirrorX()])

        if vertical:
            logger.info("Applying vertical flip")
            # MoviePy 2.x: Use vfx.MirrorY() for vertical flip
            clip = clip.with_effects([vfx.MirrorY()])

        return clip

    def _parse_bitrate(self, value: Any) -> Optional[int]:
        """Normalize bitrate value to bits per second."""
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip().lower()
            try:
                if text.endswith('k'):
                    return int(float(text[:-1]) * 1000)
                if text.endswith('m'):
                    return int(float(text[:-1]) * 1_000_000)
                return int(float(text))
            except ValueError:
                return None
        if isinstance(value, (int, float)):
            if value <= 0:
                return None
            # Heuristic: values under 100k are likely in kbps
            if value < 100000:
                return int(value * 1000)
            return int(value)
        return None

    def _estimate_total_bitrate(self, clip: VideoFileClip) -> Optional[int]:
        """Estimate total bitrate using file size and duration."""
        try:
            if not hasattr(clip, 'filename'):
                return None
            file_path = Path(clip.filename)
            if not file_path.exists() or clip.duration <= 0:
                return None
            total_bits = file_path.stat().st_size * 8
            return int(total_bits / clip.duration)
        except Exception:
            return None

    def _get_source_bitrates(self, settings: MergeSettings) -> tuple:
        """Return max source video/audio bitrates (bps) if available."""
        video_bitrates = []
        audio_bitrates = []

        for clip in self.clips:
            infos = getattr(clip.reader, 'infos', {}) or {}
            video_bps = self._parse_bitrate(infos.get('video_bitrate'))
            audio_bps = self._parse_bitrate(infos.get('audio_bitrate'))

            if video_bps is None:
                total_bps = self._parse_bitrate(infos.get('bitrate'))
                if total_bps is None:
                    total_bps = self._estimate_total_bitrate(clip)
                if total_bps:
                    if settings.keep_audio and audio_bps and total_bps > audio_bps:
                        video_bps = total_bps - audio_bps
                    else:
                        video_bps = total_bps

            if video_bps:
                video_bitrates.append(video_bps)
            if audio_bps:
                audio_bitrates.append(audio_bps)

        max_video = max(video_bitrates) if video_bitrates else None
        max_audio = max(audio_bitrates) if audio_bitrates else None
        return max_video, max_audio

    def _pad_to_size(self, clip: VideoFileClip, target_w: int, target_h: int) -> VideoFileClip:
        """Pad clip to target size without scaling."""
        width, height = clip.size
        if width == target_w and height == target_h:
            return clip

        pad_left = max(0, (target_w - width) // 2)
        pad_right = max(0, target_w - width - pad_left)
        pad_top = max(0, (target_h - height) // 2)
        pad_bottom = max(0, target_h - height - pad_top)

        logger.info(f"Padding clip from {width}x{height} to {target_w}x{target_h}")
        return clip.with_effects([
            vfx.Margin(
                left=pad_left,
                right=pad_right,
                top=pad_top,
                bottom=pad_bottom,
                color=(0, 0, 0)
            )
        ])

    def process_clips(self, settings: MergeSettings,
                      progress_callback: Optional[Callable[[int, int, str], None]] = None) -> bool:
        """
        Process all clips with settings

        Args:
            settings: Merge settings
            progress_callback: Callback(current, total, status_msg)

        Returns:
            True if successful
        """
        try:
            self.processed_clips = []
            total = len(self.clips)

            for i, clip in enumerate(self.clips):
                if progress_callback:
                    progress_callback(i, total, f"Processing video {i + 1}/{total}")

                processed = clip

                # Apply trim
                if settings.trim_start > 0 or settings.trim_end > 0:
                    processed = self.apply_trim(processed, settings.trim_start, settings.trim_end)

                # Apply crop
                if settings.crop_enabled:
                    processed = self.apply_crop(processed, settings.crop_preset, settings.crop_coords)

                # Apply zoom
                if settings.zoom_enabled:
                    processed = self.apply_zoom(processed, settings.zoom_factor)

                # Apply flip
                if settings.flip_horizontal or settings.flip_vertical:
                    processed = self.apply_flip(processed, settings.flip_horizontal, settings.flip_vertical)

                # Remove audio if needed
                if not settings.keep_audio:
                    processed = processed.without_audio()

                self.processed_clips.append(processed)

            if len(self.processed_clips) > 1:
                target_w = max(c.size[0] for c in self.processed_clips)
                target_h = max(c.size[1] for c in self.processed_clips)
                if any(c.size != (target_w, target_h) for c in self.processed_clips):
                    self.processed_clips = [
                        self._pad_to_size(clip, target_w, target_h)
                        for clip in self.processed_clips
                    ]
                    logger.info(f"Normalized clip sizes to {target_w}x{target_h}")

            logger.info(f"Processed {len(self.processed_clips)} clips")
            return True

        except Exception as e:
            logger.error(f"Error processing clips: {e}")
            return False

    def merge_clips(self, settings: MergeSettings) -> Optional[VideoFileClip]:
        """
        Merge processed clips with transitions

        Args:
            settings: Merge settings

        Returns:
            Merged clip or None if failed
        """
        try:
            if len(self.processed_clips) < 2:
                logger.error("Need at least 2 clips to merge")
                return None

            logger.info(f"Merging {len(self.processed_clips)} clips with {settings.transition_type} transition")

            # Use TransitionManager if transition is specified
            if settings.transition_type and settings.transition_type != 'none':
                transitions = [settings.transition_type] * (len(self.processed_clips) - 1)
                merged = TransitionManager.merge_with_transitions(
                    self.processed_clips,
                    transitions,
                    settings.transition_duration
                )
            else:
                # No transition, direct concatenation
                merged = concatenate_videoclips(self.processed_clips, method='compose')

            logger.info(f"Merge complete. Duration: {merged.duration:.2f}s")
            return merged

        except Exception as e:
            logger.error(f"Error merging clips: {e}")
            return None

    def export(self, merged_clip: VideoFileClip, output_path: str,
               settings: MergeSettings,
               progress_callback: Optional[Callable[[float], None]] = None) -> bool:
        """
        Export merged video to file

        Args:
            merged_clip: Merged video clip
            output_path: Output file path
            settings: Merge settings
            progress_callback: Callback(percentage)

        Returns:
            True if successful
        """
        try:
            quality = dict(self.QUALITY_PRESETS.get(settings.output_quality, self.QUALITY_PRESETS['high']))

            # Try to preserve original quality if no transformations were applied
            # Check if any transformations are enabled
            has_transformations = (
                settings.trim_start > 0 or settings.trim_end > 0 or
                settings.crop_enabled or settings.zoom_enabled or
                settings.flip_horizontal or settings.flip_vertical
            )

            source_video_bps = None
            source_audio_bps = None
            if self.clips:
                source_video_bps, source_audio_bps = self._get_source_bitrates(settings)

            if settings.output_quality == 'source':
                if source_video_bps:
                    quality['video_bitrate'] = f"{max(source_video_bps // 1000, 250)}k"
                else:
                    logger.warning("Could not detect source bitrate; using high preset.")
                    quality = dict(self.QUALITY_PRESETS['high'])

                if settings.keep_audio:
                    if source_audio_bps:
                        quality['audio_bitrate'] = f"{max(source_audio_bps // 1000, 64)}k"
                else:
                    quality['audio_bitrate'] = None

                if source_video_bps:
                    logger.info(f"Using source bitrate: {quality['video_bitrate']}")
            # If no transformations and we have original clips, try to get original bitrate
            elif not has_transformations and source_video_bps:
                preset_bitrate_num = int(quality['video_bitrate'].replace('k', '')) * 1000
                if source_video_bps > preset_bitrate_num:
                    quality['video_bitrate'] = f"{source_video_bps // 1000}k"
                    logger.info(f"Using source bitrate: {quality['video_bitrate']}")

            quality_label = settings.output_quality
            if settings.output_quality == 'source' and not source_video_bps:
                quality_label = 'high'

            logger.info(f"Exporting to: {output_path}")
            logger.info(f"Quality: {quality_label} ({quality['video_bitrate']} video, {quality['audio_bitrate']} audio)")

            # Progress callback wrapper
            def progress_wrapper(t):
                if progress_callback:
                    percentage = (t / merged_clip.duration) * 100
                    progress_callback(percentage)

            merged_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac' if settings.keep_audio else None,
                bitrate=quality['video_bitrate'],
                audio_bitrate=quality['audio_bitrate'],
                preset='medium',
                threads=4,
                logger=None  # Suppress MoviePy progress bar
            )

            logger.info(f"Export complete: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting video: {e}")
            return False

    def cleanup(self):
        """Clean up loaded clips"""
        for clip in self.clips:
            try:
                clip.close()
            except:
                pass

        for clip in self.processed_clips:
            try:
                clip.close()
            except:
                pass

        self.clips = []
        self.processed_clips = []
        logger.info("Cleanup complete")


def merge_videos(video_paths: List[str], output_path: str,
                 settings: MergeSettings = None,
                 progress_callback: Optional[Callable[[str, float], None]] = None) -> bool:
    """
    Convenience function to merge videos

    Args:
        video_paths: List of video file paths
        output_path: Output file path
        settings: Merge settings (default if None)
        progress_callback: Callback(status_msg, percentage)

    Returns:
        True if successful
    """
    if settings is None:
        settings = MergeSettings()

    engine = VideoMergeEngine()

    try:
        # Load videos
        if progress_callback:
            progress_callback("Loading videos...", 0)

        if not engine.load_videos(video_paths):
            return False

        # Process clips
        if progress_callback:
            progress_callback("Processing videos...", 20)

        def process_progress(current, total, msg):
            if progress_callback:
                pct = 20 + (current / total) * 30
                progress_callback(msg, pct)

        if not engine.process_clips(settings, process_progress):
            return False

        # Merge clips
        if progress_callback:
            progress_callback("Merging clips...", 50)

        merged = engine.merge_clips(settings)
        if not merged:
            return False

        # Export
        if progress_callback:
            progress_callback("Exporting video...", 60)

        def export_progress(pct):
            if progress_callback:
                progress_callback(f"Exporting... {pct:.1f}%", 60 + (pct / 100) * 40)

        success = engine.export(merged, output_path, settings, export_progress)

        # Cleanup
        engine.cleanup()
        merged.close()

        # Delete source files if requested
        if success and settings.delete_source:
            if progress_callback:
                progress_callback("Deleting source files...", 100)

            from .utils import safe_delete_file
            for path in video_paths:
                safe_delete_file(path)
                logger.info(f"Deleted source file: {path}")

        return success

    except Exception as e:
        logger.error(f"Error in merge_videos: {e}")
        engine.cleanup()
        return False
