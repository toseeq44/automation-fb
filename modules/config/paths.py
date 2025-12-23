"""
Centralized Path Management for OneSoul Application

Handles path resolution for both development and PyInstaller EXE modes.
Ensures persistent storage locations for cookies, configs, and user data.
"""

from pathlib import Path
import sys
import os


def get_application_root() -> Path:
    """
    Get the application root directory.

    Returns:
        Path: Application root directory
            - In development: project root folder
            - In EXE mode: directory where .exe is located (not _internal)
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE
        # sys.executable = C:/Users/User/Desktop/OneSoul/OneSoul.exe
        # We want: C:/Users/User/Desktop/OneSoul/
        exe_dir = Path(sys.executable).parent
        return exe_dir
    else:
        # Running as Python script
        # __file__ = C:/project/automation-fb/modules/config/paths.py
        # We want: C:/project/automation-fb/
        return Path(__file__).parent.parent.parent


def get_cookies_dir() -> Path:
    """
    Get persistent cookies directory.

    Returns:
        Path: Cookies directory
            - Development: project_root/cookies/
            - EXE mode: OneSoul.exe_folder/cookies/

    Note:
        Directory is automatically created if it doesn't exist.
        This is a persistent location (not in _internal temp folder).
    """
    app_root = get_application_root()
    cookies_dir = app_root / "cookies"
    cookies_dir.mkdir(parents=True, exist_ok=True)
    return cookies_dir


def get_config_dir() -> Path:
    """
    Get persistent config directory.

    Returns:
        Path: Config directory for storing application settings
    """
    app_root = get_application_root()
    config_dir = app_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_dir() -> Path:
    """
    Get persistent data directory.

    Returns:
        Path: Data directory for storing application data
    """
    app_root = get_application_root()
    data_dir = app_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_bundled_resource_path(relative_path: str) -> Path:
    """
    Get path to bundled resource (works in both dev and EXE mode).

    Args:
        relative_path: Relative path from application root (e.g., 'ffmpeg/ffmpeg.exe')

    Returns:
        Path: Full path to the resource
            - Development: project_root/relative_path
            - EXE mode: OneSoul/_internal/relative_path
    """
    if getattr(sys, 'frozen', False):
        # Running as EXE - resources are in _internal folder
        # sys._MEIPASS = C:/Users/User/AppData/Local/Temp/_MEI12345/
        base_path = Path(sys._MEIPASS)
    else:
        # Running as script
        base_path = Path(__file__).parent.parent.parent

    return base_path / relative_path


def find_ytdlp_executable() -> str:
    """
    Find yt-dlp executable with smart fallback logic.

    Priority:
        1. Bundled with EXE: OneSoul/_internal/yt-dlp.exe
        2. System PATH: yt-dlp or yt-dlp.exe
        3. Common install locations (Windows)
        4. None (will use Python library API as final fallback)

    Returns:
        str: Path to yt-dlp executable or 'yt-dlp' for system command
        None: If not found (caller should use Python API)
    """
    # Priority 1: Bundled with application
    if getattr(sys, 'frozen', False):
        bundled_ytdlp = get_bundled_resource_path('yt-dlp.exe')
        if bundled_ytdlp.exists():
            return str(bundled_ytdlp)

    # Priority 2: System PATH (try command directly)
    import shutil
    system_ytdlp = shutil.which('yt-dlp')
    if system_ytdlp:
        return system_ytdlp

    # Also try with .exe extension (Windows)
    system_ytdlp_exe = shutil.which('yt-dlp.exe')
    if system_ytdlp_exe:
        return system_ytdlp_exe

    # Priority 3: Common Windows install locations
    if sys.platform == 'win32':
        common_locations = [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Python' / 'Python312' / 'Scripts' / 'yt-dlp.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Python' / 'Python311' / 'Scripts' / 'yt-dlp.exe',
            Path(os.environ.get('APPDATA', '')) / 'Python' / 'Scripts' / 'yt-dlp.exe',
            Path('C:/') / 'Python312' / 'Scripts' / 'yt-dlp.exe',
            Path('C:/') / 'Python311' / 'Scripts' / 'yt-dlp.exe',
            Path('C:/') / 'Program Files' / 'Python312' / 'Scripts' / 'yt-dlp.exe',
            Path('C:/') / 'Program Files' / 'Python311' / 'Scripts' / 'yt-dlp.exe',
        ]

        for location in common_locations:
            if location.exists():
                return str(location)

    # Not found - caller should use Python yt_dlp library
    return None


# Export main functions
__all__ = [
    'get_application_root',
    'get_cookies_dir',
    'get_config_dir',
    'get_data_dir',
    'get_bundled_resource_path',
    'find_ytdlp_executable',
]
