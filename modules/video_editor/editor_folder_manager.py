"""
modules/video_editor/editor_folder_manager.py
Editor Folder Mapping Manager - Core logic and persistence
Handles folder mapping for bulk video processing with intelligent detection
"""

import os
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from dataclasses import dataclass, field, asdict

from modules.logging.logger import get_logger

logger = get_logger(__name__)

# Supported video formats
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.mpeg', '.mpg'}


@dataclass
class SubfolderMapping:
    """Represents a single subfolder mapping"""
    source_subfolder: str
    destination_subfolder: str
    enabled: bool = True
    videos_processed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'SubfolderMapping':
        return SubfolderMapping(
            source_subfolder=data.get('source_subfolder', ''),
            destination_subfolder=data.get('destination_subfolder', ''),
            enabled=data.get('enabled', True),
            videos_processed=data.get('videos_processed', 0)
        )


@dataclass
class EditorMappingSettings:
    """Settings for editor mapping"""
    delete_source_after_edit: bool = False
    preset_id: Optional[str] = None
    output_format: str = 'mp4'
    quality: str = 'high'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'EditorMappingSettings':
        return EditorMappingSettings(
            delete_source_after_edit=data.get('delete_source_after_edit', False),
            preset_id=data.get('preset_id'),
            output_format=data.get('output_format', 'mp4'),
            quality=data.get('quality', 'high')
        )


@dataclass
class PlanInfo:
    """User plan information for daily limits"""
    user_plan: str = 'basic'  # 'basic' or 'pro'
    daily_limit: int = 200    # Basic: 200, Pro: unlimited (999999)
    videos_processed_today: int = 0
    last_reset_date: str = ''

    def __post_init__(self):
        if not self.last_reset_date:
            self.last_reset_date = date.today().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'PlanInfo':
        return PlanInfo(
            user_plan=data.get('user_plan', 'basic'),
            daily_limit=data.get('daily_limit', 200),
            videos_processed_today=data.get('videos_processed_today', 0),
            last_reset_date=data.get('last_reset_date', date.today().isoformat())
        )


@dataclass
class EditorFolderMapping:
    """Represents a complete folder mapping configuration"""
    mapping_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_folder: str = ''
    destination_folder: str = ''
    is_simple_mode: bool = True
    subfolder_mappings: List[SubfolderMapping] = field(default_factory=list)
    settings: EditorMappingSettings = field(default_factory=EditorMappingSettings)
    created_date: str = field(default_factory=lambda: datetime.now().isoformat())
    last_processed_date: str = ''
    total_processed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'mapping_id': self.mapping_id,
            'source_folder': self.source_folder,
            'destination_folder': self.destination_folder,
            'is_simple_mode': self.is_simple_mode,
            'subfolder_mappings': [sm.to_dict() for sm in self.subfolder_mappings],
            'settings': self.settings.to_dict(),
            'created_date': self.created_date,
            'last_processed_date': self.last_processed_date,
            'total_processed': self.total_processed
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'EditorFolderMapping':
        return EditorFolderMapping(
            mapping_id=data.get('mapping_id', str(uuid.uuid4())),
            source_folder=data.get('source_folder', ''),
            destination_folder=data.get('destination_folder', ''),
            is_simple_mode=data.get('is_simple_mode', True),
            subfolder_mappings=[
                SubfolderMapping.from_dict(sm)
                for sm in data.get('subfolder_mappings', [])
            ],
            settings=EditorMappingSettings.from_dict(data.get('settings', {})),
            created_date=data.get('created_date', datetime.now().isoformat()),
            last_processed_date=data.get('last_processed_date', ''),
            total_processed=data.get('total_processed', 0)
        )

    def validate(self) -> Tuple[bool, str]:
        """Validate the mapping configuration"""
        if not self.source_folder:
            return False, "Source folder is required"

        if not self.destination_folder:
            return False, "Destination folder is required"

        source_path = Path(self.source_folder).expanduser()
        if not source_path.exists():
            return False, f"Source folder does not exist: {self.source_folder}"

        if not source_path.is_dir():
            return False, f"Source path is not a directory: {self.source_folder}"

        # Destination can be created later
        return True, ""


class FolderScanner:
    """Scans folders and detects structure"""

    @staticmethod
    def get_subfolders(folder_path: str) -> List[str]:
        """Get list of subfolders in a folder"""
        try:
            path = Path(folder_path).expanduser()
            if not path.exists():
                return []

            subfolders = [
                f.name for f in path.iterdir()
                if f.is_dir() and not f.name.startswith('.')
            ]
            return sorted(subfolders)
        except Exception as e:
            logger.error(f"Error scanning folder {folder_path}: {e}")
            return []

    @staticmethod
    def get_video_files(folder_path: str) -> List[str]:
        """Get list of video files in a folder"""
        try:
            path = Path(folder_path).expanduser()
            if not path.exists():
                return []

            videos = [
                f.name for f in path.iterdir()
                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
            ]
            return sorted(videos)
        except Exception as e:
            logger.error(f"Error getting videos from {folder_path}: {e}")
            return []

    @staticmethod
    def count_videos_in_folder(folder_path: str, recursive: bool = False) -> int:
        """Count video files in a folder"""
        try:
            path = Path(folder_path).expanduser()
            if not path.exists():
                return 0

            if recursive:
                count = 0
                for root, dirs, files in os.walk(path):
                    for f in files:
                        if Path(f).suffix.lower() in VIDEO_EXTENSIONS:
                            count += 1
                return count
            else:
                return len([
                    f for f in path.iterdir()
                    if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
                ])
        except Exception as e:
            logger.error(f"Error counting videos in {folder_path}: {e}")
            return 0

    @staticmethod
    def has_subfolders(folder_path: str) -> bool:
        """Check if folder has subfolders"""
        return len(FolderScanner.get_subfolders(folder_path)) > 0

    @staticmethod
    def has_videos(folder_path: str) -> bool:
        """Check if folder has video files"""
        return len(FolderScanner.get_video_files(folder_path)) > 0

    @staticmethod
    def detect_folder_mode(source_folder: str, dest_folder: str) -> Tuple[str, Dict[str, Any]]:
        """
        Detect folder mode and return info

        Returns:
            Tuple of (mode, info_dict)
            mode: 'simple' or 'complex'
        """
        source_subfolders = FolderScanner.get_subfolders(source_folder)
        dest_subfolders = FolderScanner.get_subfolders(dest_folder)

        source_videos = FolderScanner.get_video_files(source_folder)

        info = {
            'source_subfolders': source_subfolders,
            'dest_subfolders': dest_subfolders,
            'source_video_count': len(source_videos),
            'source_has_subfolders': len(source_subfolders) > 0,
            'dest_has_subfolders': len(dest_subfolders) > 0
        }

        # Simple mode: No subfolders in source, or source has videos directly
        if not source_subfolders and source_videos:
            return 'simple', info

        # Complex mode: Source has subfolders
        if source_subfolders:
            return 'complex', info

        # Default to simple if no videos and no subfolders
        return 'simple', info

    @staticmethod
    def auto_match_subfolders(source_subfolders: List[str], dest_subfolders: List[str]) -> List[SubfolderMapping]:
        """Auto-match subfolders by name"""
        mappings = []

        dest_lower_map = {d.lower(): d for d in dest_subfolders}

        for source_sub in source_subfolders:
            source_lower = source_sub.lower()

            # Try exact match (case-insensitive)
            if source_lower in dest_lower_map:
                mappings.append(SubfolderMapping(
                    source_subfolder=source_sub,
                    destination_subfolder=dest_lower_map[source_lower],
                    enabled=True
                ))
            else:
                # No match found - destination same as source (will be created)
                mappings.append(SubfolderMapping(
                    source_subfolder=source_sub,
                    destination_subfolder=source_sub,
                    enabled=True
                ))

        return mappings


class PlanLimitChecker:
    """Manages daily limits based on user plan"""

    BASIC_LIMIT = 200
    PRO_LIMIT = 999999  # Effectively unlimited

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.expanduser('~'),
                '.onesoul',
                'editor_plan_info.json'
            )
        self.config_path = config_path
        self.plan_info = self._load_plan_info()

    def _load_plan_info(self) -> PlanInfo:
        """Load plan info from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return PlanInfo.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading plan info: {e}")

        return PlanInfo()

    def _save_plan_info(self):
        """Save plan info to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.plan_info.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving plan info: {e}")

    def _check_and_reset_daily(self):
        """Reset daily count if new day"""
        today = date.today().isoformat()
        if self.plan_info.last_reset_date != today:
            self.plan_info.videos_processed_today = 0
            self.plan_info.last_reset_date = today
            self._save_plan_info()
            logger.info("Daily video count reset for new day")

    def get_user_plan(self) -> str:
        """Get current user plan"""
        return self.plan_info.user_plan

    def set_user_plan(self, plan: str):
        """Set user plan ('basic' or 'pro')"""
        if plan not in ('basic', 'pro'):
            raise ValueError("Plan must be 'basic' or 'pro'")

        self.plan_info.user_plan = plan
        self.plan_info.daily_limit = self.BASIC_LIMIT if plan == 'basic' else self.PRO_LIMIT
        self._save_plan_info()
        logger.info(f"User plan set to: {plan}")

    def get_daily_limit(self) -> int:
        """Get daily limit based on plan"""
        if self.plan_info.user_plan == 'pro':
            return self.PRO_LIMIT
        return self.BASIC_LIMIT

    def get_videos_processed_today(self) -> int:
        """Get count of videos processed today"""
        self._check_and_reset_daily()
        return self.plan_info.videos_processed_today

    def get_remaining_today(self) -> int:
        """Get remaining videos that can be processed today"""
        self._check_and_reset_daily()
        limit = self.get_daily_limit()
        return max(0, limit - self.plan_info.videos_processed_today)

    def can_process_more(self) -> Tuple[bool, int]:
        """
        Check if more videos can be processed today

        Returns:
            Tuple of (can_process, remaining_count)
        """
        remaining = self.get_remaining_today()
        return remaining > 0, remaining

    def can_process_count(self, count: int) -> Tuple[bool, int]:
        """
        Check if a specific count of videos can be processed

        Returns:
            Tuple of (can_process_all, how_many_can_process)
        """
        remaining = self.get_remaining_today()
        can_process = min(count, remaining)
        return count <= remaining, can_process

    def increment_processed(self, count: int = 1):
        """Increment processed count"""
        self._check_and_reset_daily()
        self.plan_info.videos_processed_today += count
        self._save_plan_info()

    def get_plan_info_display(self) -> Dict[str, Any]:
        """Get plan info for display"""
        self._check_and_reset_daily()
        return {
            'plan': self.plan_info.user_plan,
            'plan_display': 'Pro (Unlimited)' if self.plan_info.user_plan == 'pro' else 'Basic (200/day)',
            'daily_limit': self.get_daily_limit(),
            'processed_today': self.plan_info.videos_processed_today,
            'remaining_today': self.get_remaining_today(),
            'is_unlimited': self.plan_info.user_plan == 'pro'
        }


class EditorFolderMappingManager:
    """Manages editor folder mappings"""

    def __init__(self, mappings_file: str = None):
        if mappings_file is None:
            mappings_file = os.path.join(
                os.path.expanduser('~'),
                '.onesoul',
                'editor_folder_mappings.json'
            )

        self.mappings_file = mappings_file
        self.mappings: List[EditorFolderMapping] = []
        self.plan_checker = PlanLimitChecker()

        self._ensure_directory()
        self.load()

    def _ensure_directory(self):
        """Ensure config directory exists"""
        os.makedirs(os.path.dirname(self.mappings_file), exist_ok=True)

    def load(self):
        """Load mappings from file"""
        try:
            if os.path.exists(self.mappings_file):
                with open(self.mappings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.mappings = [
                    EditorFolderMapping.from_dict(m)
                    for m in data.get('mappings', [])
                ]
                logger.info(f"Loaded {len(self.mappings)} editor mappings")
        except Exception as e:
            logger.error(f"Error loading mappings: {e}")
            self.mappings = []

    def save(self):
        """Save mappings to file"""
        try:
            data = {
                'mappings': [m.to_dict() for m in self.mappings],
                'last_updated': datetime.now().isoformat()
            }

            with open(self.mappings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(self.mappings)} editor mappings")
        except Exception as e:
            logger.error(f"Error saving mappings: {e}")

    def add_mapping(self, mapping: EditorFolderMapping) -> bool:
        """Add a new mapping"""
        is_valid, error = mapping.validate()
        if not is_valid:
            logger.error(f"Invalid mapping: {error}")
            return False

        self.mappings.append(mapping)
        self.save()
        logger.info(f"Added new mapping: {mapping.source_folder} -> {mapping.destination_folder}")
        return True

    def update_mapping(self, mapping_id: str, updated_mapping: EditorFolderMapping) -> bool:
        """Update an existing mapping"""
        for i, m in enumerate(self.mappings):
            if m.mapping_id == mapping_id:
                is_valid, error = updated_mapping.validate()
                if not is_valid:
                    logger.error(f"Invalid mapping update: {error}")
                    return False

                self.mappings[i] = updated_mapping
                self.save()
                logger.info(f"Updated mapping: {mapping_id}")
                return True

        logger.warning(f"Mapping not found: {mapping_id}")
        return False

    def delete_mapping(self, mapping_id: str) -> bool:
        """Delete a mapping"""
        for i, m in enumerate(self.mappings):
            if m.mapping_id == mapping_id:
                del self.mappings[i]
                self.save()
                logger.info(f"Deleted mapping: {mapping_id}")
                return True

        logger.warning(f"Mapping not found for deletion: {mapping_id}")
        return False

    def get_mapping(self, mapping_id: str) -> Optional[EditorFolderMapping]:
        """Get a mapping by ID"""
        for m in self.mappings:
            if m.mapping_id == mapping_id:
                return m
        return None

    def get_all_mappings(self) -> List[EditorFolderMapping]:
        """Get all mappings"""
        return self.mappings

    def update_processing_stats(self, mapping_id: str, videos_processed: int):
        """Update processing statistics for a mapping"""
        for m in self.mappings:
            if m.mapping_id == mapping_id:
                m.total_processed += videos_processed
                m.last_processed_date = datetime.now().isoformat()
                self.save()
                break

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        total_processed = sum(m.total_processed for m in self.mappings)

        return {
            'total_mappings': len(self.mappings),
            'total_videos_processed': total_processed,
            'plan_info': self.plan_checker.get_plan_info_display()
        }

    def create_destination_folders(self, mapping: EditorFolderMapping) -> bool:
        """Create destination folders if they don't exist"""
        try:
            dest_path = Path(mapping.destination_folder).expanduser()
            dest_path.mkdir(parents=True, exist_ok=True)

            if not mapping.is_simple_mode:
                for sm in mapping.subfolder_mappings:
                    if sm.enabled:
                        subfolder_path = dest_path / sm.destination_subfolder
                        subfolder_path.mkdir(parents=True, exist_ok=True)

            logger.info(f"Created destination folders for mapping")
            return True
        except Exception as e:
            logger.error(f"Error creating destination folders: {e}")
            return False
