"""
Shared configuration utilities
Ensures all config files use consistent paths
"""
import sys
from pathlib import Path


def get_config_directory() -> Path:
    """
    Get the configuration directory for OneSoul app
    
    Logic:
    - When running as EXE (frozen): Config files go next to the executable
    - When running as script: Config files go to ~/.onesoul/ directory
    
    Returns:
        Path to config directory
    """
    if getattr(sys, 'frozen', False):
        # Running as frozen EXE - use executable directory
        config_dir = Path(sys.executable).parent
    else:
        # Running as script - use home directory/.onesoul
        config_dir = Path.home() / ".onesoul"
        config_dir.mkdir(parents=True, exist_ok=True)
    
    return config_dir


def get_config_path(filename: str = "config.json") -> Path:
    """
    Get full path for a config file
    
    Args:
        filename: Name of the config file (default: config.json)
    
    Returns:
        Full path to the config file
    """
    return get_config_directory() / filename
