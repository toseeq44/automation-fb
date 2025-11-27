"""
Folder Mapping Manager
Manages configuration for mapping source folders (Links Grabber) to destination folders (Creators Data)
"""

import json
import uuid
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple


class FolderMapping:
    """Represents a single folder mapping configuration"""

    def __init__(self,
                 source_folder: str,
                 destination_folder: str,
                 daily_limit: int = 5,
                 move_only_if_empty: bool = True,
                 enabled: bool = True,
                 mapping_id: Optional[str] = None,
                 last_move_date: Optional[str] = None,
                 total_moved: int = 0):

        self.id = mapping_id or str(uuid.uuid4())
        self.source_folder = source_folder
        self.destination_folder = destination_folder
        self.daily_limit = daily_limit
        self.move_only_if_empty = move_only_if_empty
        self.enabled = enabled
        self.last_move_date = last_move_date
        self.total_moved = total_moved

    def to_dict(self) -> Dict:
        """Convert mapping to dictionary"""
        return {
            "id": self.id,
            "source_folder": self.source_folder,
            "destination_folder": self.destination_folder,
            "daily_limit": self.daily_limit,
            "move_only_if_empty": self.move_only_if_empty,
            "enabled": self.enabled,
            "last_move_date": self.last_move_date,
            "total_moved": self.total_moved
        }

    @staticmethod
    def from_dict(data: Dict) -> 'FolderMapping':
        """Create mapping from dictionary"""
        return FolderMapping(
            mapping_id=data.get("id"),
            source_folder=data.get("source_folder", ""),
            destination_folder=data.get("destination_folder", ""),
            daily_limit=data.get("daily_limit", 5),
            move_only_if_empty=data.get("move_only_if_empty", True),
            enabled=data.get("enabled", True),
            last_move_date=data.get("last_move_date"),
            total_moved=data.get("total_moved", 0)
        )

    def validate(self) -> Tuple[bool, str]:
        """
        Validate the mapping configuration
        Returns: (is_valid, error_message)
        """
        if not self.source_folder:
            return False, "Source folder is required"

        if not self.destination_folder:
            return False, "Destination folder is required"

        source_path = Path(self.source_folder)
        if not source_path.exists():
            return False, f"Source folder does not exist: {self.source_folder}"

        if not source_path.is_dir():
            return False, f"Source path is not a directory: {self.source_folder}"

        # Destination folder will be created if it doesn't exist, so just check parent
        dest_path = Path(self.destination_folder)
        if dest_path.exists() and not dest_path.is_dir():
            return False, f"Destination path exists but is not a directory: {self.destination_folder}"

        if self.daily_limit < 1:
            return False, "Daily limit must be at least 1"

        return True, ""

    def can_move_today(self) -> bool:
        """Check if videos can be moved today based on last move date"""
        if not self.last_move_date:
            return True

        try:
            last_move = datetime.fromisoformat(self.last_move_date).date()
            today = date.today()
            return today > last_move
        except (ValueError, TypeError):
            return True

    def get_source_path(self) -> Path:
        """Get source folder as Path object"""
        return Path(self.source_folder).expanduser()

    def get_destination_path(self) -> Path:
        """Get destination folder as Path object"""
        return Path(self.destination_folder).expanduser()


class FolderMappingManager:
    """Manages all folder mappings"""

    DEFAULT_CONFIG_PATH = Path.home() / ".onesoul" / "folder_mappings.json"

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.mappings: List[FolderMapping] = []
        self.global_settings = {
            "auto_move_after_download": False,
            "show_confirmation": True,
            "default_daily_limit": 5,
            "default_move_condition": "empty_only"
        }

        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing configuration
        self.load()

    def load(self) -> bool:
        """Load mappings from configuration file"""
        if not self.config_path.exists():
            return False

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Load mappings
            self.mappings = [
                FolderMapping.from_dict(m)
                for m in data.get("mappings", [])
            ]

            # Load global settings
            if "global_settings" in data:
                self.global_settings.update(data["global_settings"])

            return True
        except Exception as e:
            print(f"Error loading folder mappings: {e}")
            return False

    def save(self) -> bool:
        """Save mappings to configuration file"""
        try:
            data = {
                "mappings": [m.to_dict() for m in self.mappings],
                "global_settings": self.global_settings
            }

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"Error saving folder mappings: {e}")
            return False

    def add_mapping(self, mapping: FolderMapping) -> bool:
        """Add a new mapping"""
        is_valid, error = mapping.validate()
        if not is_valid:
            print(f"Invalid mapping: {error}")
            return False

        # Check for duplicate source folder
        if any(m.source_folder == mapping.source_folder for m in self.mappings):
            print(f"Mapping already exists for source folder: {mapping.source_folder}")
            return False

        self.mappings.append(mapping)
        return self.save()

    def update_mapping(self, mapping_id: str, updated_mapping: FolderMapping) -> bool:
        """Update an existing mapping"""
        is_valid, error = updated_mapping.validate()
        if not is_valid:
            print(f"Invalid mapping: {error}")
            return False

        for i, mapping in enumerate(self.mappings):
            if mapping.id == mapping_id:
                updated_mapping.id = mapping_id  # Preserve ID
                self.mappings[i] = updated_mapping
                return self.save()

        print(f"Mapping not found: {mapping_id}")
        return False

    def delete_mapping(self, mapping_id: str) -> bool:
        """Delete a mapping by ID"""
        original_count = len(self.mappings)
        self.mappings = [m for m in self.mappings if m.id != mapping_id]

        if len(self.mappings) < original_count:
            return self.save()

        return False

    def get_mapping(self, mapping_id: str) -> Optional[FolderMapping]:
        """Get a mapping by ID"""
        for mapping in self.mappings:
            if mapping.id == mapping_id:
                return mapping
        return None

    def get_mapping_by_source(self, source_folder: str) -> Optional[FolderMapping]:
        """Get a mapping by source folder path"""
        for mapping in self.mappings:
            if mapping.source_folder == source_folder:
                return mapping
        return None

    def get_all_mappings(self) -> List[FolderMapping]:
        """Get all mappings"""
        return self.mappings

    def get_active_mappings(self) -> List[FolderMapping]:
        """Get only enabled mappings"""
        return [m for m in self.mappings if m.enabled]

    def update_move_stats(self, mapping_id: str, videos_moved: int) -> bool:
        """Update statistics after moving videos"""
        mapping = self.get_mapping(mapping_id)
        if not mapping:
            return False

        mapping.last_move_date = datetime.now().isoformat()
        mapping.total_moved += videos_moved

        return self.save()

    def clear_all_mappings(self) -> bool:
        """Clear all mappings"""
        self.mappings = []
        return self.save()

    def get_setting(self, key: str, default=None):
        """Get a global setting value"""
        return self.global_settings.get(key, default)

    def set_setting(self, key: str, value) -> bool:
        """Set a global setting value"""
        self.global_settings[key] = value
        return self.save()

    def export_config(self, export_path: Path) -> bool:
        """Export configuration to a file"""
        try:
            data = {
                "mappings": [m.to_dict() for m in self.mappings],
                "global_settings": self.global_settings,
                "exported_at": datetime.now().isoformat()
            }

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"Error exporting config: {e}")
            return False

    def import_config(self, import_path: Path, merge: bool = False) -> bool:
        """Import configuration from a file"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            imported_mappings = [
                FolderMapping.from_dict(m)
                for m in data.get("mappings", [])
            ]

            if merge:
                # Merge with existing mappings (avoid duplicates by source folder)
                existing_sources = {m.source_folder for m in self.mappings}
                for mapping in imported_mappings:
                    if mapping.source_folder not in existing_sources:
                        self.mappings.append(mapping)
            else:
                # Replace all mappings
                self.mappings = imported_mappings

            # Update global settings
            if "global_settings" in data:
                self.global_settings.update(data["global_settings"])

            return self.save()
        except Exception as e:
            print(f"Error importing config: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get overall statistics"""
        return {
            "total_mappings": len(self.mappings),
            "active_mappings": len(self.get_active_mappings()),
            "total_videos_moved": sum(m.total_moved for m in self.mappings),
            "mappings_with_moves_today": len([
                m for m in self.mappings
                if m.last_move_date and not m.can_move_today()
            ])
        }
