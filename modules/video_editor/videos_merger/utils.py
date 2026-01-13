"""
modules/video_editor/videos_merger/utils.py
Utility functions for video merging
"""

import os
from pathlib import Path
from typing import List
from datetime import datetime

VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.webm'}


def get_videos_from_folder(folder_path: str) -> List[str]:
    """
    Get all video files from a folder (sorted by name)

    Args:
        folder_path: Path to folder

    Returns:
        List of video file paths (sorted)
    """
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return []

    videos = []
    for file in folder.iterdir():
        if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS:
            videos.append(str(file.absolute()))

    # Sort by filename
    videos.sort()
    return videos


def get_default_output_folder() -> str:
    """
    Get default output folder (Desktop/merging final/)
    Creates folder if it doesn't exist

    Returns:
        Path to output folder
    """
    desktop = Path.home() / "Desktop"
    output_folder = desktop / "merging final"

    # Create if doesn't exist
    output_folder.mkdir(parents=True, exist_ok=True)

    return str(output_folder)


def generate_output_filename(prefix: str = "merged", extension: str = "mp4") -> str:
    """
    Generate unique output filename with timestamp

    Args:
        prefix: Filename prefix
        extension: File extension (without dot)

    Returns:
        Filename like: merged_20260113_143052.mp4
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"


def generate_batch_filename(batch_number: int, extension: str = "mp4") -> str:
    """
    Generate batch filename

    Args:
        batch_number: Batch number (1-based)
        extension: File extension (without dot)

    Returns:
        Filename like: batch_001.mp4
    """
    return f"batch_{batch_number:03d}.{extension}"


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to MM:SS or HH:MM:SS

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string
    """
    if seconds < 0:
        return "00:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def format_filesize(bytes_size: int) -> str:
    """
    Format file size in bytes to human readable format

    Args:
        bytes_size: Size in bytes

    Returns:
        Formatted string like: 250MB, 1.5GB
    """
    if bytes_size < 1024:
        return f"{bytes_size}B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f}KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.1f}MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.2f}GB"


def estimate_output_size(input_sizes: List[int], quality: str = "high") -> int:
    """
    Estimate output file size based on input sizes and quality

    Args:
        input_sizes: List of input file sizes in bytes
        quality: Quality preset (low, medium, high, ultra)

    Returns:
        Estimated size in bytes
    """
    total_input = sum(input_sizes)

    # Compression ratios based on quality
    ratios = {
        'low': 0.3,
        'medium': 0.5,
        'high': 0.7,
        'ultra': 0.9
    }

    ratio = ratios.get(quality, 0.7)
    return int(total_input * ratio)


def validate_video_file(filepath: str) -> bool:
    """
    Check if file exists and is a valid video file

    Args:
        filepath: Path to video file

    Returns:
        True if valid, False otherwise
    """
    path = Path(filepath)
    return path.exists() and path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def safe_delete_file(filepath: str) -> bool:
    """
    Safely delete a file (with error handling)

    Args:
        filepath: Path to file

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    except Exception as e:
        print(f"Error deleting {filepath}: {e}")
        return False
