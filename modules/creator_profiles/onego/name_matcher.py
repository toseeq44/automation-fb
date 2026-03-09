"""
OneGo name matcher — normalize bookmark/folder names for matching.

Rules:
- Case-insensitive
- Trim whitespace
- Normalize separators: space, underscore, hyphen treated as equivalent
- No fuzzy/partial matching beyond normalization
"""

import re
from typing import Dict, Optional


_SEP_RE = re.compile(r"[\s_\-]+")


def normalize_name(name: str) -> str:
    """Normalize a name for matching: lowercase, strip, collapse separators to single space."""
    return _SEP_RE.sub(" ", (name or "").strip().lower()).strip()


def match_bookmark_to_folder(
    bookmark_name: str,
    folder_map: Dict[str, str],
) -> Optional[str]:
    """
    Match a bookmark name to a creator folder.

    Parameters
    ----------
    bookmark_name : str
        The IX browser bookmark name.
    folder_map : dict
        Mapping of normalized folder name -> original folder path.

    Returns
    -------
    str or None
        The original folder path if matched, else None.
    """
    norm_bm = normalize_name(bookmark_name)
    if not norm_bm:
        return None
    return folder_map.get(norm_bm)


def build_folder_map(folder_names: list) -> Dict[str, str]:
    """
    Build a normalized-name -> original-name mapping.

    Parameters
    ----------
    folder_names : list of str
        Original folder names (not full paths).

    Returns
    -------
    dict
        {normalized_name: original_name}
    """
    result: Dict[str, str] = {}
    for name in folder_names:
        norm = normalize_name(name)
        if norm:
            result[norm] = name
    return result
