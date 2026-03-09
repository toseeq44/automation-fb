import os
import sys
from pathlib import Path

def get_chromium_executable_path() -> str:
    """
    Returns the path to the bundled Chromium executable.
    Prioritizes the bundled version in 'bin/chromium' for both 
    development and PyInstaller frozen modes.
    """
    # 1. Determine base application directory
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        # sys.executable is the location of the EXE
        base_dir = Path(sys.executable).parent
    else:
        # Running in development mode
        base_dir = Path(__file__).resolve().parents[2]

    # 2. Check for System Google Chrome (BEST for video codecs and reliability)
    # Common Windows installation paths
    system_paths = [
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LocalAppData", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    for path in system_paths:
        if path.exists():
            return str(path)

    # 3. Fallback: Check candidates in bundled 'bin/chromium' subfolder
    candidates = [
        base_dir / "bin" / "chromium" / "chrome.exe",     # Windows (bundled name)
        base_dir / "bin" / "chromium" / "chromium.exe",   # Windows alternate
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # 4. Final Fallback: return None (Playwright will use its default system path)
    return None

def delete_browser_profile(profile_dir: str):
    """
    Safely delete the browser profile directory to recover from corruption/mismatch.
    """
    import shutil
    import time
    from pathlib import Path

    p_dir = Path(profile_dir)
    if not p_dir.exists():
        return

    # 1. Aggressively target lock files first
    lock_files = [
        p_dir / "SingletonLock",
        p_dir / "parent.lock",
        p_dir / "lock",
    ]
    for lf in lock_files:
        try:
            if lf.exists():
                lf.unlink(missing_ok=True)
        except Exception:
            pass

    # 2. Try to delete the whole directory
    for i in range(3):
        try:
            shutil.rmtree(p_dir, ignore_errors=True)
            if not p_dir.exists():
                break
            time.sleep(1.0)
        except Exception:
            pass
    
    # Ensure directory exists but is empty
    p_dir.mkdir(parents=True, exist_ok=True)
