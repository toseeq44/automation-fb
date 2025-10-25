"""
modules/video_editor/video_utils.py
Helper functions for video thumbnail generation and preview
"""

import os
import tempfile
from typing import Optional, Tuple
from pathlib import Path

try:
    from moviepy import VideoFileClip
    from PIL import Image
    import numpy as np
    LIBS_AVAILABLE = True
except ImportError:
    LIBS_AVAILABLE = False


def extract_video_thumbnail(video_path: str, time: float = 1.0, max_size: Tuple[int, int] = (640, 360)) -> Optional[str]:
    """
    Extract thumbnail from video at specified time

    Args:
        video_path: Path to video file
        time: Time in seconds to extract frame (default: 1.0)
        max_size: Maximum thumbnail size (width, height)

    Returns:
        Path to saved thumbnail image, or None if failed
    """
    if not LIBS_AVAILABLE:
        return None

    try:
        # Load video
        clip = VideoFileClip(video_path)

        # Get frame at specified time (or middle if time > duration)
        if time > clip.duration:
            time = clip.duration / 2

        frame = clip.get_frame(time)

        # Convert to PIL Image
        image = Image.fromarray(frame)

        # Resize to max_size maintaining aspect ratio
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save to temp file
        temp_dir = tempfile.gettempdir()
        thumbnail_path = os.path.join(temp_dir, f"video_thumb_{os.getpid()}.jpg")
        image.save(thumbnail_path, "JPEG", quality=85)

        # Cleanup
        clip.close()

        return thumbnail_path

    except Exception as e:
        print(f"Error extracting thumbnail: {e}")
        return None


def get_video_first_frame(video_path: str, output_size: Tuple[int, int] = (800, 450)) -> Optional[str]:
    """
    Get first frame of video as thumbnail

    Args:
        video_path: Path to video file
        output_size: Size of output thumbnail

    Returns:
        Path to thumbnail or None
    """
    return extract_video_thumbnail(video_path, time=0.1, max_size=output_size)
