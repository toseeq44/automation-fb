"""Helpers - Helper functions"""
import time
from typing import Callable, Any

def retry(func: Callable, max_attempts: int = 3, delay: int = 2) -> Any:
    """Retry function on failure."""
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise e
            time.sleep(delay * (attempt + 1))
    return None

def safe_filename(filename: str) -> str:
    """Remove invalid characters from filename."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename
