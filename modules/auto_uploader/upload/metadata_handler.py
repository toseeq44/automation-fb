"""Metadata Handler - Video metadata management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional


class MetadataHandler:
    """Handles video metadata loading and form filling helpers."""

    def __init__(self, metadata_filename: str = "videos_description.json") -> None:
        self._metadata_filename = metadata_filename
        self._cache: Dict[Path, Dict[str, Any]] = {}
        logging.debug("MetadataHandler initialized")

    def load_metadata(self, creator_path: Path, video_name: str) -> Dict[str, Any]:
        """Load metadata for a specific video from the creator's metadata file."""
        metadata_map = self._load_metadata_map(creator_path)
        metadata = metadata_map.get(video_name) or {}
        if metadata:
            logging.debug("Loaded metadata for %s/%s", creator_path.name, video_name)
        return metadata

    # ------------------------------------------------------------------ #
    # Form helpers (placeholders for future Selenium integration)        #
    # ------------------------------------------------------------------ #
    def fill_title(self, driver: Any, title: str) -> bool:
        """Fill the title field on the upload page (placeholder)."""
        logging.debug("fill_title called (placeholder implementation)")
        return False

    def fill_description(self, driver: Any, description: str) -> bool:
        """Fill the description field on the upload page (placeholder)."""
        logging.debug("fill_description called (placeholder implementation)")
        return False

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _load_metadata_map(self, creator_path: Path) -> Dict[str, Any]:
        """Load and cache the metadata mapping for a creator folder."""
        metadata_path = creator_path / self._metadata_filename
        if metadata_path in self._cache:
            return self._cache[metadata_path]

        if not metadata_path.is_file():
            logging.debug("Metadata file not found for %s", creator_path)
            self._cache[metadata_path] = {}
            return self._cache[metadata_path]

        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._cache[metadata_path] = data
            else:
                logging.warning("Unexpected metadata format in %s. Expected JSON object.", metadata_path)
                self._cache[metadata_path] = {}
        except (OSError, json.JSONDecodeError) as exc:
            logging.error("Failed to read metadata file %s: %s", metadata_path, exc)
            self._cache[metadata_path] = {}

        return self._cache[metadata_path]
