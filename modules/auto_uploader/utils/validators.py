"""Validators - Input validation"""
import re

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def validate_path(path: str) -> bool:
    """Validate file path."""
    from pathlib import Path
    return Path(path).exists()
