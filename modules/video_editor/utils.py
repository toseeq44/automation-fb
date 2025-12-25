"""
modules/video_editor/utils.py
Utility Functions for Video Editing - FIXED IMPORTS
"""
import subprocess
import sys
import importlib
import os
import json
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from modules.logging.logger import get_logger

logger = get_logger(__name__)


# ==================== DEPENDENCY MANAGEMENT ====================

def check_moviepy_dependencies():
    """Check if MoviePy and required dependencies are installed"""
    required_packages = [
        "moviepy",
        "numpy", 
        "Pillow",
        "decorator",
        "tqdm"
    ]
    
    missing = []
    for package in required_packages:
        try:
            importlib.import_module(package)
        except ImportError:
            missing.append(package)
    
    return missing

def install_moviepy_dependencies():
    """Install MoviePy dependencies"""
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "moviepy", "numpy", "Pillow", "decorator", "tqdm"
        ])
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        return False

def ensure_moviepy_available():
    """Ensure MoviePy is available, install if not"""
    missing = check_moviepy_dependencies()
    if missing:
        print(f"Missing dependencies: {missing}")
        print("Installing MoviePy dependencies...")
        return install_moviepy_dependencies()
    return True


# ==================== VIDEO INFO ====================

def get_video_info(video_path: str) -> Dict[str, Any]:
    """
    Get comprehensive video information using FFprobe

    Args:
        video_path: Path to video file

    Returns:
        Dictionary with video metadata
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    try:
        # Try using ffprobe if available
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            data = json.loads(result.stdout)

            # Parse video stream
            video_stream = None
            audio_stream = None

            for stream in data.get('streams', []):
                if stream['codec_type'] == 'video' and not video_stream:
                    video_stream = stream
                elif stream['codec_type'] == 'audio' and not audio_stream:
                    audio_stream = stream

            info = {
                'filename': os.path.basename(video_path),
                'filepath': video_path,
                'filesize': os.path.getsize(video_path),
                'filesize_mb': round(os.path.getsize(video_path) / (1024 * 1024), 2),
            }

            if video_stream:
                info.update({
                    'width': int(video_stream.get('width', 0)),
                    'height': int(video_stream.get('height', 0)),
                    'codec': video_stream.get('codec_name', 'unknown'),
                    'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                    'bitrate': int(video_stream.get('bit_rate', 0)),
                    'pixel_format': video_stream.get('pix_fmt', 'unknown'),
                })

            if audio_stream:
                info.update({
                    'has_audio': True,
                    'audio_codec': audio_stream.get('codec_name', 'unknown'),
                    'audio_sample_rate': int(audio_stream.get('sample_rate', 0)),
                    'audio_channels': int(audio_stream.get('channels', 0)),
                })
            else:
                info['has_audio'] = False

            format_info = data.get('format', {})
            if 'duration' in format_info:
                info['duration'] = float(format_info['duration'])

            if 'bit_rate' in format_info:
                info['overall_bitrate'] = int(format_info['bit_rate'])

            return info

    except Exception as e:
        logger.warning(f"FFprobe failed, using fallback: {e}")

    # Fallback to MoviePy
    try:
        # Try multiple import methods for MoviePy
        try:
            from moviepy.editor import VideoFileClip
        except ImportError:
            try:
                from moviepy import VideoFileClip
            except ImportError:
                from moviepy.video.io.VideoFileClip import VideoFileClip

        video = VideoFileClip(video_path)
        info = {
            'filename': os.path.basename(video_path),
            'filepath': video_path,
            'filesize': os.path.getsize(video_path),
            'filesize_mb': round(os.path.getsize(video_path) / (1024 * 1024), 2),
            'duration': video.duration,
            'width': video.w,
            'height': video.h,
            'fps': video.fps,
            'has_audio': video.audio is not None,
            'aspect_ratio': round(video.w / video.h, 2) if video.h > 0 else 0
        }
        video.close()
        return info

    except Exception as e:
        logger.error(f"Failed to get video info: {e}")
        return {
            'filename': os.path.basename(video_path),
            'filepath': video_path,
            'filesize': os.path.getsize(video_path),
            'error': str(e)
        }


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1:23:45" or "12:34")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_filesize(bytes: int) -> str:
    """
    Format file size in bytes to human-readable string

    Args:
        bytes: File size in bytes

    Returns:
        Formatted string (e.g., "1.23 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} PB"


# ==================== FILE OPERATIONS ====================

def ensure_output_dir(output_path: str) -> str:
    """
    Ensure output directory exists

    Args:
        output_path: Output file path

    Returns:
        Absolute output path
    """
    output_path = os.path.abspath(output_path)
    output_dir = os.path.dirname(output_path)

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")

    return output_path


def get_unique_filename(filepath: str) -> str:
    """
    Get unique filename by adding counter if file exists

    Args:
        filepath: Desired file path

    Returns:
        Unique file path
    """
    if not os.path.exists(filepath):
        return filepath

    path = Path(filepath)
    directory = path.parent
    name = path.stem
    extension = path.suffix

    counter = 1
    while True:
        new_path = directory / f"{name}_{counter}{extension}"
        if not os.path.exists(new_path):
            return str(new_path)
        counter += 1


def cleanup_temp_files(temp_dir: str = None):
    """
    Clean up temporary files

    Args:
        temp_dir: Temporary directory path (None = system temp)
    """
    import tempfile
    import shutil

    if temp_dir is None:
        temp_dir = tempfile.gettempdir()

    # Clean up MoviePy temp files
    pattern = "TEMP_MPY_*"
    temp_path = Path(temp_dir)

    deleted_count = 0
    for temp_file in temp_path.glob(pattern):
        try:
            if temp_file.is_file():
                temp_file.unlink()
                deleted_count += 1
            elif temp_file.is_dir():
                shutil.rmtree(temp_file)
                deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete temp file {temp_file}: {e}")

    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} temporary files")


# ==================== ASPECT RATIO ====================

def calculate_aspect_ratio(width: int, height: int) -> Tuple[int, int]:
    """
    Calculate simplified aspect ratio

    Args:
        width: Video width
        height: Video height

    Returns:
        Tuple of (ratio_width, ratio_height)
    """
    from math import gcd

    divisor = gcd(width, height)
    return (width // divisor, height // divisor)


def get_aspect_ratio_name(width: int, height: int) -> str:
    """
    Get aspect ratio name

    Args:
        width: Video width
        height: Video height

    Returns:
        Aspect ratio name (e.g., "16:9", "9:16", "1:1")
    """
    ratio = calculate_aspect_ratio(width, height)
    return f"{ratio[0]}:{ratio[1]}"


def calculate_dimensions_for_aspect_ratio(
        current_width: int,
        current_height: int,
        target_ratio: str
) -> Tuple[int, int, int, int]:
    """
    Calculate crop dimensions to achieve target aspect ratio

    Args:
        current_width: Current video width
        current_height: Current video height
        target_ratio: Target aspect ratio (e.g., "16:9", "9:16")

    Returns:
        Tuple of (x1, y1, x2, y2) for cropping
    """
    # Parse target ratio
    parts = target_ratio.split(':')
    if len(parts) != 2:
        raise ValueError(f"Invalid aspect ratio format: {target_ratio}")

    target_w, target_h = int(parts[0]), int(parts[1])
    target_ratio_value = target_w / target_h
    current_ratio_value = current_width / current_height

    if current_ratio_value > target_ratio_value:
        # Current is wider - crop width
        new_width = int(current_height * target_ratio_value)
        new_height = current_height
        x1 = (current_width - new_width) // 2
        y1 = 0
        x2 = x1 + new_width
        y2 = current_height
    else:
        # Current is taller - crop height
        new_width = current_width
        new_height = int(current_width / target_ratio_value)
        x1 = 0
        y1 = (current_height - new_height) // 2
        x2 = current_width
        y2 = y1 + new_height

    return (x1, y1, x2, y2)


# ==================== FFMPEG UTILITIES ====================

def get_ffmpeg_path() -> str:
    """
    Get FFmpeg executable path
    Handles both development and PyInstaller bundled modes

    Returns:
        Path to ffmpeg executable
    """
    import sys
    import os

    # Check if running as PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # Running as exe - check bundled ffmpeg
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller temp folder
            bundled_ffmpeg = os.path.join(sys._MEIPASS, 'ffmpeg', 'ffmpeg.exe')
            if os.path.exists(bundled_ffmpeg):
                logger.info(f"Using bundled FFmpeg (temp): {bundled_ffmpeg}")
                return bundled_ffmpeg

        # Check in exe directory
        exe_dir = os.path.dirname(sys.executable)

        # Check ffmpeg subfolder
        exe_ffmpeg = os.path.join(exe_dir, 'ffmpeg', 'ffmpeg.exe')
        if os.path.exists(exe_ffmpeg):
            logger.info(f"Using exe directory FFmpeg: {exe_ffmpeg}")
            return exe_ffmpeg

        # Check dist folder structure (OneSoul/ffmpeg/ffmpeg.exe)
        dist_ffmpeg = os.path.join(exe_dir, 'ffmpeg.exe')
        if os.path.exists(dist_ffmpeg):
            logger.info(f"Using dist FFmpeg: {dist_ffmpeg}")
            return dist_ffmpeg

    # Development mode or system PATH
    # Check if ffmpeg is in PATH
    try:
        result = subprocess.run(['ffmpeg', '-version'],
                              capture_output=True,
                              timeout=3)
        if result.returncode == 0:
            logger.info("Using system PATH FFmpeg")
            return 'ffmpeg'
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Last resort: check common locations
    common_paths = [
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        os.path.join(os.getcwd(), 'ffmpeg', 'ffmpeg.exe'),
    ]

    for path in common_paths:
        if os.path.exists(path):
            logger.info(f"Using FFmpeg from common location: {path}")
            return path

    # Fallback to 'ffmpeg' and hope it's in PATH
    logger.warning("FFmpeg not found in bundle or PATH, using 'ffmpeg' as fallback")
    return 'ffmpeg'


def check_ffmpeg() -> bool:
    """
    Check if FFmpeg is installed

    Returns:
        True if FFmpeg is available
    """
    try:
        ffmpeg_path = get_ffmpeg_path()
        subprocess.run([ffmpeg_path, '-version'], capture_output=True, timeout=5)
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_ffmpeg_version() -> Optional[str]:
    """
    Get FFmpeg version

    Returns:
        Version string or None if not installed
    """
    try:
        ffmpeg_path = get_ffmpeg_path()
        result = subprocess.run(
            [ffmpeg_path, '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Parse first line
            first_line = result.stdout.split('\n')[0]
            # Extract version number
            parts = first_line.split(' ')
            for part in parts:
                if part[0].isdigit():
                    return part
        return None
    except Exception:
        return None


def check_dependencies() -> Dict[str, bool]:
    """
    Check all required dependencies

    Returns:
        Dictionary of dependency status
    """
    deps = {}

    # Check FFmpeg
    deps['ffmpeg'] = check_ffmpeg()

    # Check MoviePy
    try:
        # Try multiple import methods for MoviePy
        try:
            from moviepy.editor import VideoFileClip
            deps['moviepy'] = True
        except ImportError:
            try:
                from moviepy import VideoFileClip
                deps['moviepy'] = True
            except ImportError:
                from moviepy.video.io.VideoFileClip import VideoFileClip
                deps['moviepy'] = True
    except ImportError:
        deps['moviepy'] = False

    # Check PIL/Pillow
    try:
        from PIL import Image
        deps['pillow'] = True
    except ImportError:
        deps['pillow'] = False

    # Check NumPy
    try:
        import numpy
        deps['numpy'] = True
    except ImportError:
        deps['numpy'] = False

    # Check SciPy (optional)
    try:
        import scipy
        deps['scipy'] = True
    except ImportError:
        deps['scipy'] = False

    return deps


def print_dependencies_status():
    """Print status of all dependencies"""
    deps = check_dependencies()

    print("\n=== DEPENDENCIES STATUS ===\n")

    status_icon = {True: '✅', False: '❌'}

    print(f"{status_icon[deps.get('ffmpeg', False)]} FFmpeg")
    if deps.get('ffmpeg'):
        version = get_ffmpeg_version()
        if version:
            print(f"   Version: {version}")

    print(f"{status_icon[deps.get('moviepy', False)]} MoviePy")
    print(f"{status_icon[deps.get('pillow', False)]} Pillow")
    print(f"{status_icon[deps.get('numpy', False)]} NumPy")
    print(f"{status_icon[deps.get('scipy', False)]} SciPy (optional)")

    print("\nRequired: FFmpeg, MoviePy, Pillow, NumPy")
    print("Optional: SciPy (for advanced filters)\n")

    all_required = all([
        deps.get('ffmpeg', False),
        deps.get('moviepy', False),
        deps.get('pillow', False),
        deps.get('numpy', False)
    ])

    if all_required:
        print("✅ All required dependencies are installed!\n")
    else:
        print("❌ Some required dependencies are missing.\n")
        print("Installation:")
        if not deps.get('moviepy'):
            print("  pip install moviepy")
        if not deps.get('pillow'):
            print("  pip install pillow")
        if not deps.get('numpy'):
            print("  pip install numpy")
        if not deps.get('ffmpeg'):
            print("  Install FFmpeg: https://ffmpeg.org/download.html")
        print()


# ==================== VALIDATION ====================

def validate_video_file(filepath: str) -> bool:
    """
    Validate if file is a valid video

    Args:
        filepath: Path to video file

    Returns:
        True if valid video file
    """
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return False

    # Check extension
    valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v']
    ext = os.path.splitext(filepath)[1].lower()

    if ext not in valid_extensions:
        logger.warning(f"Unusual video extension: {ext}")

    # Try to get video info
    try:
        info = get_video_info(filepath)
        if 'error' in info:
            return False

        # Check for required fields
        if info.get('width', 0) > 0 and info.get('height', 0) > 0:
            return True

        return False

    except Exception as e:
        logger.error(f"Video validation failed: {e}")
        return False


def validate_output_format(output_path: str) -> bool:
    """
    Validate output format is supported

    Args:
        output_path: Output file path

    Returns:
        True if format is supported
    """
    supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.gif']
    ext = os.path.splitext(output_path)[1].lower()

    if ext not in supported_formats:
        logger.error(f"Unsupported output format: {ext}")
        logger.info(f"Supported formats: {', '.join(supported_formats)}")
        return False

    return True


# ==================== PROGRESS TRACKING ====================

class ProgressTracker:
    """Track video processing progress"""

    def __init__(self, total_frames: int = 0):
        self.total_frames = total_frames
        self.current_frame = 0
        self.start_time = None
        self.callbacks = []

    def start(self):
        """Start tracking"""
        from datetime import datetime
        self.start_time = datetime.now()
        self.current_frame = 0

    def update(self, frame: int):
        """Update progress"""
        self.current_frame = frame

        # Call callbacks
        for callback in self.callbacks:
            try:
                callback(self.get_progress())
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    def add_callback(self, callback):
        """Add progress callback"""
        self.callbacks.append(callback)

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress"""
        from datetime import datetime

        if self.total_frames == 0:
            percentage = 0
        else:
            percentage = (self.current_frame / self.total_frames) * 100

        elapsed = None
        eta = None

        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()

            if self.current_frame > 0:
                rate = self.current_frame / elapsed
                remaining_frames = self.total_frames - self.current_frame
                eta = remaining_frames / rate if rate > 0 else 0

        return {
            'current_frame': self.current_frame,
            'total_frames': self.total_frames,
            'percentage': round(percentage, 1),
            'elapsed': elapsed,
            'eta': eta
        }


# ==================== BATCH UTILITIES ====================

def find_videos_in_directory(directory: str, recursive: bool = False) -> List[str]:
    """
    Find all video files in directory

    Args:
        directory: Directory path
        recursive: Search recursively

    Returns:
        List of video file paths
    """
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}

    video_files = []

    if recursive:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if os.path.splitext(file)[1].lower() in video_extensions:
                    video_files.append(os.path.join(root, file))
    else:
        for file in os.listdir(directory):
            filepath = os.path.join(directory, file)
            if os.path.isfile(filepath):
                if os.path.splitext(file)[1].lower() in video_extensions:
                    video_files.append(filepath)

    return sorted(video_files)


def estimate_output_size(input_path: str, target_bitrate: str) -> float:
    """
    Estimate output file size

    Args:
        input_path: Input video path
        target_bitrate: Target bitrate (e.g., "5000k")

    Returns:
        Estimated size in MB
    """
    info = get_video_info(input_path)

    if 'duration' not in info:
        return 0

    # Parse bitrate
    bitrate_num = int(target_bitrate.replace('k', '000').replace('M', '000000'))

    # Calculate size: (bitrate in bits/s * duration in seconds) / 8 / 1024 / 1024
    size_mb = (bitrate_num * info['duration']) / 8 / 1024 / 1024

    return round(size_mb, 2)


# ==================== COLOR UTILITIES ====================

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """
    Convert hex color to RGB

    Args:
        hex_color: Hex color string (e.g., "#FF5733" or "FF5733")

    Returns:
        Tuple of (r, g, b)
    """
    hex_color = hex_color.lstrip('#')

    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])

    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """
    Convert RGB to hex color

    Args:
        r, g, b: RGB values (0-255)

    Returns:
        Hex color string (e.g., "#FF5733")
    """
    return f"#{r:02x}{g:02x}{b:02x}"