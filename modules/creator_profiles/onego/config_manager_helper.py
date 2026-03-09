"""
Helper to load uploading_target from a creator folder's config.
Avoids circular imports by keeping the import inside the function.
"""

from pathlib import Path


def load_uploading_target(folder: Path) -> int:
    """Load the uploading_target value from a creator folder's config."""
    from modules.creator_profiles.config_manager import CreatorConfig
    try:
        cfg = CreatorConfig(folder)
        return cfg.uploading_target
    except Exception:
        return 0
