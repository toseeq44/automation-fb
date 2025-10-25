"""
modules/video_editor/core.py
Complete Video Editor Engine with MoviePy
Supports: Trim, Crop, Rotate, Flip, Text, Audio, Watermarks, Filters, Merge, Transitions
"""

import os
import json
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

try:
    from moviepy.editor import (
        VideoFileClip, AudioFileClip, ImageClip, TextClip,
        CompositeVideoClip, CompositeAudioClip, concatenate_videoclips,
        vfx, afx
    )
    from moviepy.video.fx.all import (
        crop, resize, rotate, mirror_x, mirror_y,
        fadein, fadeout, crossfadein, crossfadeout
    )
    from moviepy.audio.fx.all import volumex, audio_fadein, audio_fadeout
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("WARNING: MoviePy not installed. Install with: pip install moviepy")

from modules.logging.logger import get_logger

logger = get_logger(__name__)


class VideoProject:
    """
    Represents a video editing project with undo/redo support
    """
    def __init__(self, name: str = "Untitled"):
        self.name = name
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
        self.history = []  # Edit history for undo
        self.redo_stack = []  # Redo stack
        self.current_state = None

    def add_to_history(self, operation: Dict[str, Any]):
        """Add operation to history"""
        self.history.append(operation)
        self.redo_stack.clear()  # Clear redo when new operation added
        self.modified_at = datetime.now()

    def undo(self) -> Optional[Dict[str, Any]]:
        """Undo last operation"""
        if self.history:
            operation = self.history.pop()
            self.redo_stack.append(operation)
            return operation
        return None

    def redo(self) -> Optional[Dict[str, Any]]:
        """Redo last undone operation"""
        if self.redo_stack:
            operation = self.redo_stack.pop()
            self.history.append(operation)
            return operation
        return None

    def save_project(self, filepath: str):
        """Save project to JSON file"""
        data = {
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'history': self.history
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Project saved: {filepath}")

    @staticmethod
    def load_project(filepath: str) -> 'VideoProject':
        """Load project from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)

        project = VideoProject(data['name'])
        project.created_at = datetime.fromisoformat(data['created_at'])
        project.modified_at = datetime.fromisoformat(data['modified_at'])
        project.history = data['history']
        logger.info(f"Project loaded: {filepath}")
        return project


class VideoEditor:
    """
    Complete Video Editor with all features
    """

    def __init__(self, video_path: Optional[str] = None):
        if not MOVIEPY_AVAILABLE:
            raise ImportError("MoviePy is not installed. Install with: pip install moviepy")

        self.original_path = video_path
        self.video = None
        self.project = VideoProject()
        self.temp_files = []  # Track temporary files for cleanup

        if video_path:
            self.load_video(video_path)

    def load_video(self, video_path: str):
        """Load video from file"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        try:
            self.video = VideoFileClip(video_path)
            self.original_path = video_path
            logger.info(f"Video loaded: {video_path} (Duration: {self.video.duration}s, Size: {self.video.size})")
            return True
        except Exception as e:
            logger.error(f"Failed to load video: {e}")
            raise

    def get_info(self) -> Dict[str, Any]:
        """Get video information"""
        if not self.video:
            return {}

        return {
            'duration': self.video.duration,
            'fps': self.video.fps,
            'size': self.video.size,  # (width, height)
            'width': self.video.w,
            'height': self.video.h,
            'aspect_ratio': self.video.w / self.video.h if self.video.h > 0 else 0,
            'has_audio': self.video.audio is not None,
            'filename': os.path.basename(self.original_path) if self.original_path else None
        }

    # ==================== BASIC EDITING ====================

    def trim(self, start_time: float, end_time: float):
        """
        Trim video to specified time range

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
        """
        if not self.video:
            raise ValueError("No video loaded")

        if start_time < 0 or end_time > self.video.duration or start_time >= end_time:
            raise ValueError(f"Invalid time range: {start_time}s - {end_time}s (Duration: {self.video.duration}s)")

        self.video = self.video.subclip(start_time, end_time)
        self.project.add_to_history({
            'operation': 'trim',
            'params': {'start': start_time, 'end': end_time}
        })
        logger.info(f"Video trimmed: {start_time}s - {end_time}s")
        return self

    def crop(self, x1: int = None, y1: int = None, x2: int = None, y2: int = None,
             preset: str = None):
        """
        Crop video to specified region or use aspect ratio preset

        Args:
            x1, y1, x2, y2: Crop coordinates (pixels)
            preset: Aspect ratio preset ('9:16', '16:9', '1:1', '4:5', '4:3')
        """
        if not self.video:
            raise ValueError("No video loaded")

        w, h = self.video.size

        # Use preset if provided
        if preset:
            presets = {
                '9:16': (9, 16),    # TikTok, Instagram Reels, YouTube Shorts
                '16:9': (16, 9),    # YouTube, Facebook
                '1:1': (1, 1),      # Instagram Post
                '4:5': (4, 5),      # Instagram Portrait
                '4:3': (4, 3),      # Traditional
                '21:9': (21, 9)     # Cinematic
            }

            if preset not in presets:
                raise ValueError(f"Invalid preset: {preset}. Available: {list(presets.keys())}")

            target_w, target_h = presets[preset]

            # Calculate crop dimensions to match aspect ratio
            current_ratio = w / h
            target_ratio = target_w / target_h

            if current_ratio > target_ratio:
                # Video is wider - crop width
                new_w = int(h * target_ratio)
                new_h = h
                x1 = (w - new_w) // 2
                y1 = 0
                x2 = x1 + new_w
                y2 = h
            else:
                # Video is taller - crop height
                new_w = w
                new_h = int(w / target_ratio)
                x1 = 0
                y1 = (h - new_h) // 2
                x2 = w
                y2 = y1 + new_h

        # Validate coordinates
        if x1 is None or y1 is None or x2 is None or y2 is None:
            raise ValueError("Must provide either coordinates or preset")

        if x1 < 0 or y1 < 0 or x2 > w or y2 > h or x1 >= x2 or y1 >= y2:
            raise ValueError(f"Invalid crop coordinates: ({x1},{y1}) to ({x2},{y2})")

        self.video = crop(self.video, x1=x1, y1=y1, x2=x2, y2=y2)
        self.project.add_to_history({
            'operation': 'crop',
            'params': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'preset': preset}
        })
        logger.info(f"Video cropped: ({x1},{y1}) to ({x2},{y2}){' [' + preset + ']' if preset else ''}")
        return self

    def rotate(self, angle: float):
        """
        Rotate video by specified angle

        Args:
            angle: Rotation angle in degrees (90, 180, 270, or any value)
        """
        if not self.video:
            raise ValueError("No video loaded")

        self.video = rotate(self.video, angle)
        self.project.add_to_history({
            'operation': 'rotate',
            'params': {'angle': angle}
        })
        logger.info(f"Video rotated: {angle}°")
        return self

    def flip_horizontal(self):
        """Flip video horizontally (mirror)"""
        if not self.video:
            raise ValueError("No video loaded")

        self.video = mirror_x(self.video)
        self.project.add_to_history({
            'operation': 'flip_horizontal',
            'params': {}
        })
        logger.info("Video flipped horizontally")
        return self

    def flip_vertical(self):
        """Flip video vertically"""
        if not self.video:
            raise ValueError("No video loaded")

        self.video = mirror_y(self.video)
        self.project.add_to_history({
            'operation': 'flip_vertical',
            'params': {}
        })
        logger.info("Video flipped vertically")
        return self

    def resize_video(self, width: int = None, height: int = None, scale: float = None):
        """
        Resize video

        Args:
            width: Target width (maintains aspect ratio if height not specified)
            height: Target height (maintains aspect ratio if width not specified)
            scale: Scale factor (e.g., 0.5 for 50%, 2.0 for 200%)
        """
        if not self.video:
            raise ValueError("No video loaded")

        if scale:
            self.video = resize(self.video, scale)
            logger.info(f"Video resized by scale: {scale}")
        elif width or height:
            if width and height:
                self.video = resize(self.video, newsize=(width, height))
                logger.info(f"Video resized: {width}x{height}")
            elif width:
                self.video = resize(self.video, width=width)
                logger.info(f"Video resized: width={width}")
            elif height:
                self.video = resize(self.video, height=height)
                logger.info(f"Video resized: height={height}")
        else:
            raise ValueError("Must specify width, height, or scale")

        self.project.add_to_history({
            'operation': 'resize',
            'params': {'width': width, 'height': height, 'scale': scale}
        })
        return self

    def change_speed(self, factor: float):
        """
        Change video playback speed

        Args:
            factor: Speed factor (0.5 = half speed, 2.0 = double speed)
        """
        if not self.video:
            raise ValueError("No video loaded")

        if factor <= 0:
            raise ValueError("Speed factor must be positive")

        self.video = self.video.speedx(factor)
        self.project.add_to_history({
            'operation': 'speed',
            'params': {'factor': factor}
        })
        logger.info(f"Video speed changed: {factor}x")
        return self

    # ==================== TEXT OVERLAYS ====================

    def add_text(self, text: str, position: Tuple[str, str] = ('center', 'bottom'),
                 fontsize: int = 50, color: str = 'white', font: str = 'Arial-Bold',
                 duration: float = None, start_time: float = 0,
                 stroke_color: str = 'black', stroke_width: int = 2,
                 bg_color: str = None, method: str = 'caption'):
        """
        Add text overlay to video

        Args:
            text: Text to display
            position: Position tuple (x, y) or ('center', 'top'/'bottom')
            fontsize: Font size in pixels
            color: Text color
            font: Font name
            duration: Text duration in seconds (None = entire video)
            start_time: When to start showing text
            stroke_color: Outline color (None for no outline)
            stroke_width: Outline width
            bg_color: Background color (None for transparent)
            method: 'caption' for word wrap, 'label' for single line
        """
        if not self.video:
            raise ValueError("No video loaded")

        if duration is None:
            duration = self.video.duration - start_time

        try:
            # Create text clip
            txt_clip = TextClip(
                text,
                fontsize=fontsize,
                color=color,
                font=font,
                stroke_color=stroke_color if stroke_width > 0 else None,
                stroke_width=stroke_width,
                bg_color=bg_color,
                method=method,
                size=self.video.size if method == 'caption' else None
            )

            # Set position and duration
            txt_clip = txt_clip.set_position(position).set_duration(duration)

            # Set start time if specified
            if start_time > 0:
                txt_clip = txt_clip.set_start(start_time)

            # Compose with video
            self.video = CompositeVideoClip([self.video, txt_clip])

            self.project.add_to_history({
                'operation': 'add_text',
                'params': {
                    'text': text, 'position': position, 'fontsize': fontsize,
                    'color': color, 'font': font, 'duration': duration,
                    'start_time': start_time
                }
            })
            logger.info(f"Text added: '{text}' at {position}")

        except Exception as e:
            logger.error(f"Failed to add text: {e}")
            raise

        return self

    # ==================== AUDIO ====================

    def replace_audio(self, audio_path: str, start_time: float = 0):
        """
        Replace video audio with new audio file

        Args:
            audio_path: Path to audio file
            start_time: When to start the audio in the video
        """
        if not self.video:
            raise ValueError("No video loaded")

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            audio = AudioFileClip(audio_path)

            # Trim or loop audio to match video duration
            if audio.duration > self.video.duration:
                audio = audio.subclip(0, self.video.duration)
            elif audio.duration < self.video.duration:
                # Loop audio if shorter
                repeats = int(self.video.duration / audio.duration) + 1
                audio = concatenate_audioclips([audio] * repeats).subclip(0, self.video.duration)

            if start_time > 0:
                audio = audio.set_start(start_time)

            self.video = self.video.set_audio(audio)

            self.project.add_to_history({
                'operation': 'replace_audio',
                'params': {'audio_path': audio_path, 'start_time': start_time}
            })
            logger.info(f"Audio replaced: {audio_path}")

        except Exception as e:
            logger.error(f"Failed to replace audio: {e}")
            raise

        return self

    def mix_audio(self, audio_path: str, volume: float = 0.5, start_time: float = 0):
        """
        Mix additional audio with existing video audio

        Args:
            audio_path: Path to audio file to mix
            volume: Volume of new audio (0.0 to 1.0)
            start_time: When to start the new audio
        """
        if not self.video:
            raise ValueError("No video loaded")

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            new_audio = AudioFileClip(audio_path)

            # Adjust volume
            new_audio = volumex(new_audio, volume)

            # Match duration
            if new_audio.duration > self.video.duration:
                new_audio = new_audio.subclip(0, self.video.duration)

            if start_time > 0:
                new_audio = new_audio.set_start(start_time)

            # Mix with existing audio
            if self.video.audio:
                mixed_audio = CompositeAudioClip([self.video.audio, new_audio])
            else:
                mixed_audio = new_audio

            self.video = self.video.set_audio(mixed_audio)

            self.project.add_to_history({
                'operation': 'mix_audio',
                'params': {'audio_path': audio_path, 'volume': volume, 'start_time': start_time}
            })
            logger.info(f"Audio mixed: {audio_path} (volume: {volume})")

        except Exception as e:
            logger.error(f"Failed to mix audio: {e}")
            raise

        return self

    def adjust_volume(self, volume: float):
        """
        Adjust video audio volume

        Args:
            volume: Volume multiplier (1.0 = original, 0.5 = half, 2.0 = double)
        """
        if not self.video:
            raise ValueError("No video loaded")

        if not self.video.audio:
            logger.warning("Video has no audio to adjust")
            return self

        adjusted_audio = volumex(self.video.audio, volume)
        self.video = self.video.set_audio(adjusted_audio)

        self.project.add_to_history({
            'operation': 'adjust_volume',
            'params': {'volume': volume}
        })
        logger.info(f"Volume adjusted: {volume}x")
        return self

    def remove_audio(self):
        """Remove all audio from video"""
        if not self.video:
            raise ValueError("No video loaded")

        self.video = self.video.without_audio()
        self.project.add_to_history({
            'operation': 'remove_audio',
            'params': {}
        })
        logger.info("Audio removed")
        return self

    # ==================== WATERMARK / LOGO ====================

    def add_watermark(self, image_path: str, position: Tuple[str, str] = ('right', 'bottom'),
                     size: Tuple[int, int] = None, opacity: float = 1.0,
                     margin: int = 10):
        """
        Add watermark/logo to video

        Args:
            image_path: Path to watermark image (PNG with transparency recommended)
            position: Position tuple ('left'/'center'/'right', 'top'/'center'/'bottom')
            size: Resize watermark to (width, height). None = keep original
            opacity: Opacity (0.0 = invisible, 1.0 = fully visible)
            margin: Margin from edges in pixels
        """
        if not self.video:
            raise ValueError("No video loaded")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Watermark image not found: {image_path}")

        try:
            # Load watermark
            watermark = ImageClip(image_path).set_duration(self.video.duration)

            # Resize if specified
            if size:
                watermark = watermark.resize(newsize=size)

            # Set opacity
            if opacity < 1.0:
                watermark = watermark.set_opacity(opacity)

            # Calculate position with margin
            w, h = self.video.size
            wm_w, wm_h = watermark.size

            x_pos = position[0]
            y_pos = position[1]

            if x_pos == 'left':
                x = margin
            elif x_pos == 'center':
                x = (w - wm_w) // 2
            elif x_pos == 'right':
                x = w - wm_w - margin
            else:
                x = int(x_pos)

            if y_pos == 'top':
                y = margin
            elif y_pos == 'center':
                y = (h - wm_h) // 2
            elif y_pos == 'bottom':
                y = h - wm_h - margin
            else:
                y = int(y_pos)

            watermark = watermark.set_position((x, y))

            # Compose with video
            self.video = CompositeVideoClip([self.video, watermark])

            self.project.add_to_history({
                'operation': 'add_watermark',
                'params': {
                    'image_path': image_path, 'position': position,
                    'size': size, 'opacity': opacity, 'margin': margin
                }
            })
            logger.info(f"Watermark added: {image_path} at {position}")

        except Exception as e:
            logger.error(f"Failed to add watermark: {e}")
            raise

        return self

    # ==================== FILTERS & EFFECTS ====================

    def fade_in(self, duration: float = 1.0):
        """Add fade-in effect at the beginning"""
        if not self.video:
            raise ValueError("No video loaded")

        self.video = fadein(self.video, duration)

        # Fade in audio too if present
        if self.video.audio:
            self.video = self.video.set_audio(audio_fadein(self.video.audio, duration))

        self.project.add_to_history({
            'operation': 'fade_in',
            'params': {'duration': duration}
        })
        logger.info(f"Fade-in added: {duration}s")
        return self

    def fade_out(self, duration: float = 1.0):
        """Add fade-out effect at the end"""
        if not self.video:
            raise ValueError("No video loaded")

        self.video = fadeout(self.video, duration)

        # Fade out audio too if present
        if self.video.audio:
            self.video = self.video.set_audio(audio_fadeout(self.video.audio, duration))

        self.project.add_to_history({
            'operation': 'fade_out',
            'params': {'duration': duration}
        })
        logger.info(f"Fade-out added: {duration}s")
        return self

    def apply_filter(self, filter_name: str, **kwargs):
        """
        Apply filter to video

        Available filters:
            - 'brightness': kwargs: intensity (0.5 = darker, 2.0 = brighter)
            - 'contrast': kwargs: intensity (0.5 = less, 2.0 = more)
            - 'grayscale': No kwargs
            - 'invert': No kwargs
            - 'blur': kwargs: intensity (1-10)
        """
        if not self.video:
            raise ValueError("No video loaded")

        from modules.video_editor.filters import apply_custom_filter

        self.video = apply_custom_filter(self.video, filter_name, **kwargs)

        self.project.add_to_history({
            'operation': 'apply_filter',
            'params': {'filter_name': filter_name, 'kwargs': kwargs}
        })
        logger.info(f"Filter applied: {filter_name}")
        return self

    # ==================== EXPORT ====================

    def export(self, output_path: str, quality: str = 'high',
              codec: str = 'libx264', audio_codec: str = 'aac',
              fps: int = None, bitrate: str = None,
              preset: str = 'medium', threads: int = 4,
              progress_callback=None):
        """
        Export edited video

        Args:
            output_path: Output file path
            quality: Quality preset ('low', 'medium', 'high', 'ultra')
            codec: Video codec (default: libx264 for MP4)
            audio_codec: Audio codec (default: aac)
            fps: Output FPS (None = keep original)
            bitrate: Video bitrate (None = auto based on quality)
            preset: FFmpeg preset ('ultrafast', 'fast', 'medium', 'slow', 'veryslow')
            threads: Number of threads for encoding
            progress_callback: Callback function for progress updates
        """
        if not self.video:
            raise ValueError("No video loaded")

        # Quality presets
        quality_presets = {
            'low': {'bitrate': '500k', 'audio_bitrate': '96k'},
            'medium': {'bitrate': '1500k', 'audio_bitrate': '128k'},
            'high': {'bitrate': '5000k', 'audio_bitrate': '192k'},
            'ultra': {'bitrate': '15000k', 'audio_bitrate': '320k'}
        }

        if quality in quality_presets and not bitrate:
            bitrate = quality_presets[quality]['bitrate']
            audio_bitrate = quality_presets[quality]['audio_bitrate']
        else:
            audio_bitrate = '192k'

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        try:
            logger.info(f"Exporting video: {output_path} (quality: {quality}, codec: {codec})")

            # Build write parameters
            write_params = {
                'codec': codec,
                'audio_codec': audio_codec if self.video.audio else None,
                'preset': preset,
                'threads': threads,
                'logger': None  # Suppress MoviePy's default progress bar
            }

            if fps:
                write_params['fps'] = fps

            if bitrate:
                write_params['bitrate'] = bitrate

            if audio_codec and self.video.audio:
                write_params['audio_bitrate'] = audio_bitrate

            # Export video
            self.video.write_videofile(output_path, **write_params)

            logger.info(f"Video exported successfully: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to export video: {e}")
            raise

    def preview(self, fps: int = 15, audio: bool = True):
        """
        Preview video in a window (blocking)

        Args:
            fps: Preview FPS (lower = faster preview generation)
            audio: Whether to play audio
        """
        if not self.video:
            raise ValueError("No video loaded")

        try:
            self.video.preview(fps=fps, audio=audio)
        except Exception as e:
            logger.error(f"Failed to preview video: {e}")
            raise

    # ==================== UTILITY ====================

    def save_frame(self, time: float, output_path: str):
        """
        Save a single frame as image

        Args:
            time: Time in seconds
            output_path: Output image path
        """
        if not self.video:
            raise ValueError("No video loaded")

        if time < 0 or time > self.video.duration:
            raise ValueError(f"Invalid time: {time}s (duration: {self.video.duration}s)")

        frame = self.video.get_frame(time)
        from PIL import Image
        img = Image.fromarray(frame)
        img.save(output_path)
        logger.info(f"Frame saved: {output_path} at {time}s")

    def cleanup(self):
        """Clean up resources and temporary files"""
        if self.video:
            try:
                self.video.close()
            except:
                pass

        # Clean up temporary files
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

        self.temp_files.clear()
        logger.info("VideoEditor cleaned up")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()

    def __del__(self):
        """Destructor"""
        self.cleanup()


# ==================== BATCH OPERATIONS ====================

class BatchVideoEditor:
    """
    Process multiple videos with same operations
    """

    def __init__(self, video_paths: List[str]):
        self.video_paths = video_paths
        self.operations = []

    def add_operation(self, operation: str, **kwargs):
        """Add operation to batch queue"""
        self.operations.append({
            'operation': operation,
            'kwargs': kwargs
        })
        return self

    def process(self, output_dir: str, name_pattern: str = "{name}_edited{ext}",
                progress_callback=None):
        """
        Process all videos with queued operations

        Args:
            output_dir: Output directory
            name_pattern: Output filename pattern (supports {name}, {ext}, {index})
            progress_callback: Callback(current, total, current_file)
        """
        os.makedirs(output_dir, exist_ok=True)
        results = []

        for idx, video_path in enumerate(self.video_paths):
            try:
                if progress_callback:
                    progress_callback(idx, len(self.video_paths), video_path)

                # Load video
                editor = VideoEditor(video_path)

                # Apply all operations
                for op in self.operations:
                    operation = op['operation']
                    kwargs = op['kwargs']

                    # Call the operation method
                    if hasattr(editor, operation):
                        getattr(editor, operation)(**kwargs)

                # Generate output filename
                name, ext = os.path.splitext(os.path.basename(video_path))
                output_filename = name_pattern.format(
                    name=name,
                    ext=ext,
                    index=idx + 1
                )
                output_path = os.path.join(output_dir, output_filename)

                # Export
                editor.export(output_path)
                results.append({
                    'input': video_path,
                    'output': output_path,
                    'status': 'success'
                })

                editor.cleanup()

            except Exception as e:
                logger.error(f"Failed to process {video_path}: {e}")
                results.append({
                    'input': video_path,
                    'output': None,
                    'status': 'failed',
                    'error': str(e)
                })

        return results


# ==================== VIDEO MERGER ====================

def merge_videos(video_paths: List[str], output_path: str,
                transition: str = None, transition_duration: float = 1.0,
                method: str = 'concatenate'):
    """
    Merge multiple videos into one

    Args:
        video_paths: List of video file paths
        output_path: Output file path
        transition: Transition type ('crossfade', 'fade', None)
        transition_duration: Transition duration in seconds
        method: 'concatenate' or 'compose' (side-by-side)
    """
    if not video_paths:
        raise ValueError("No videos provided")

    logger.info(f"Merging {len(video_paths)} videos...")

    clips = [VideoFileClip(path) for path in video_paths]

    if method == 'concatenate':
        # Concatenate videos one after another
        if transition == 'crossfade':
            # Add crossfade transitions
            for i in range(len(clips) - 1):
                clips[i] = clips[i].crossfadeout(transition_duration)
                clips[i + 1] = clips[i + 1].crossfadein(transition_duration)

        final = concatenate_videoclips(clips, method='compose')

    elif method == 'compose':
        # Place videos side-by-side
        final = CompositeVideoClip(clips, size=(sum(c.w for c in clips), max(c.h for c in clips)))

    else:
        raise ValueError(f"Invalid method: {method}")

    # Export
    final.write_videofile(output_path, codec='libx264', audio_codec='aac')

    # Cleanup
    for clip in clips:
        clip.close()
    final.close()

    logger.info(f"Videos merged: {output_path}")
    return output_path
