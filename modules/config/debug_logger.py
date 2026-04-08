import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_debug_logger_initialized = False

def get_log_file_path() -> Path:
    if getattr(sys, 'frozen', False):
        # We are running in a PyInstaller bundle
        base_dir = Path(sys.executable).parent
    else:
        # We are running in a normal Python environment
        base_dir = Path(__file__).resolve().parents[2] # Adjust if needed to point to project root

    log_path = base_dir / "debug_creator_profile.log"
    
    # Simple write check
    try:
        with open(log_path, 'a'): pass
        return log_path
    except Exception:
        # Fallback to desktop if permission denied
        return Path.home() / "Desktop" / "debug_creator_profile.log"

def setup_debug_logger():
    global _debug_logger_initialized
    if _debug_logger_initialized:
        return
        
    log_file_path = get_log_file_path()
    
    # We hook into the root python logger to capture everything
    # (yt-dlp, playwright, selenium, our own code)
    root_logger = logging.getLogger()
    
    # Optional: we don't change the level if it's already set to something specific,
    # but normally we want at least INFO, catching ERROR and WARNING too.
    if root_logger.level == logging.NOTSET:
        root_logger.setLevel(logging.INFO)
        
    # Prevent duplicate handlers
    for handler in root_logger.handlers:
        if hasattr(handler, 'baseFilename') and str(handler.baseFilename) == str(log_file_path):
            return

    # Use a rotating file handler: 10 MB per file, keep 3 backups
    handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8',
        delay=True  # Don't create file until first log is written
    )
    
    # Create a detailed format
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)
    _debug_logger_initialized = True
    
    # Log the startup boundary
    root_logger.info("=" * 60)
    root_logger.info("OneSoul Automation Session Started")
    root_logger.info(f"Log path: {log_file_path}")
    root_logger.info("=" * 60)
