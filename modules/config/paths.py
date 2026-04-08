"""
Centralized Path Management for OneSoul Application

Handles path resolution for both development and PyInstaller EXE modes.
Ensures persistent storage locations for cookies, configs, and user data.
"""

from pathlib import Path
import sys
import os

import sys
import os

if getattr(sys, 'frozen', False):
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = os.path.join(sys._MEIPASS, 'playwright_browsers')



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


def _ytdlp_is_usable(exe_path: str) -> bool:
    """Quick check: can this yt-dlp exe run --version successfully?"""
    import subprocess
    try:
        r = subprocess.run(
            [exe_path, "--version"],
            capture_output=True, text=True, timeout=8,
            encoding="utf-8", errors="replace",
        )
        return r.returncode == 0 and bool((r.stdout or "").strip())
    except Exception:
        return False


def _ytdlp_version_tuple(exe_path: str):
    """Return (year, month, day) version tuple, or (0,0,0) on failure."""
    import subprocess
    try:
        r = subprocess.run(
            [exe_path, "--version"],
            capture_output=True, text=True, timeout=8,
            encoding="utf-8", errors="replace",
        )
        if r.returncode == 0 and r.stdout:
            parts = r.stdout.strip().split(".")
            return tuple(int(p) for p in parts[:3])
    except Exception:
        pass
    return (0, 0, 0)


def find_ytdlp_executable() -> str:
    """
    Find yt-dlp executable with enhanced smart fallback logic.

    Priority:
        1. Bundled with EXE: OneSoul/_internal/yt-dlp.exe (MOST RELIABLE)
           - If bundled exe exists but fails to run, fall through to C drive.
           - If C drive has a NEWER version, prefer C drive over bundled.
        2. User's C Drive: C:\\yt-dlp\\ (USER MANAGED)
        3. System PATH: yt-dlp or yt-dlp.exe
        4. Common install locations (Windows)
        5. None (will use Python library API as final fallback)

    Returns:
        str: Path to yt-dlp executable or 'yt-dlp' for system command
        None: If not found (caller should use Python API)
    """
    bundled_path = None

    # Priority 1: Bundled with application (EXE mode)
    if getattr(sys, 'frozen', False):
        bundled_ytdlp = get_bundled_resource_path('yt-dlp.exe')
        if bundled_ytdlp.exists():
            if _ytdlp_is_usable(str(bundled_ytdlp)):
                bundled_path = str(bundled_ytdlp)
            # If not usable, fall through to C drive

    # Priority 2: User's C Drive locations
    c_drive_path = None
    if sys.platform == 'win32':
        c_drive_locations = [
            Path('C:/yt-dlp/yt-dlp.exe'),          # Primary C drive location
            Path('C:/yt-dlp/bin/yt-dlp.exe'),      # Alternative bin folder
            Path('C:/yt-dlp.exe'),                 # Root C drive
        ]

        for location in c_drive_locations:
            try:
                if location.exists() and location.is_file():
                    c_drive_path = str(location)
                    break
            except Exception:
                continue

    # Decide between bundled and C drive
    if bundled_path and c_drive_path:
        # Both exist — prefer the newer version
        bundled_ver = _ytdlp_version_tuple(bundled_path)
        cdrive_ver = _ytdlp_version_tuple(c_drive_path)
        if cdrive_ver > bundled_ver:
            return c_drive_path
        return bundled_path
    if bundled_path:
        return bundled_path
    if c_drive_path:
        return c_drive_path

    # Priority 3: System PATH (try command directly)
    import shutil
    system_ytdlp = shutil.which('yt-dlp')
    if system_ytdlp:
        return system_ytdlp

    # Also try with .exe extension (Windows)
    system_ytdlp_exe = shutil.which('yt-dlp.exe')
    if system_ytdlp_exe:
        return system_ytdlp_exe

    # Priority 4: Common Windows install locations
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
            try:
                if location.exists():
                    return str(location)
            except Exception:
                continue

    # Not found - caller should use Python yt_dlp library
    return None


def ensure_deno_in_path() -> bool:
    """
    Ensure the Deno JS runtime is discoverable by yt-dlp for YouTube
    signature/n-challenge solving (EJS).

    Checks bundled locations (EXE mode) and common install paths,
    then adds to PATH if found but missing.
    Returns True if deno is available after the call.
    """
    import shutil

    if shutil.which("deno"):
        return True

    deno_name = "deno.exe" if sys.platform == "win32" else "deno"
    candidates = []

    # Priority 1: Bundled with EXE (_internal/third_party/deno_runtime/)
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys._MEIPASS) / "third_party" / "deno_runtime")

    # Priority 2: Dev-mode project folder
    candidates.append(get_application_root() / "third_party" / "deno_runtime")

    # Priority 3: User-installed Deno
    if sys.platform == "win32":
        home = Path.home()
        candidates.extend([
            home / ".deno" / "bin",
            Path(os.environ.get("LOCALAPPDATA", "")) / "deno",
        ])

    for candidate in candidates:
        try:
            if (candidate / deno_name).is_file():
                os.environ["PATH"] = str(candidate) + os.pathsep + os.environ.get("PATH", "")
                return True
        except Exception:
            continue

    return False


# Export main functions
__all__ = [
    'get_application_root',
    'get_cookies_dir',
    'get_config_dir',
    'get_data_dir',
    'get_bundled_resource_path',
    'find_ytdlp_executable',
    'ensure_deno_in_path',
]
