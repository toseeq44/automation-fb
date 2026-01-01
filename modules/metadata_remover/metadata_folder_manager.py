"""
modules/metadata_remover/metadata_folder_manager.py
Metadata Remover Folder Manager - Core logic and persistence
Handles folder mapping for bulk metadata removal with intelligent detection
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
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.mpeg', '.mpg', '.3gp'}


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
class MetadataRemovalSettings:
    """Settings for metadata removal"""
    remove_all_metadata: bool = True
    remove_exif: bool = True
    remove_xmp: bool = True
    remove_iptc: bool = True
    remove_gps: bool = True
    remove_id3: bool = True
    delete_source_after_process: bool = False  # Only for different folder mode

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'MetadataRemovalSettings':
        return MetadataRemovalSettings(
            remove_all_metadata=data.get('remove_all_metadata', True),
            remove_exif=data.get('remove_exif', True),
            remove_xmp=data.get('remove_xmp', True),
            remove_iptc=data.get('remove_iptc', True),
            remove_gps=data.get('remove_gps', True),
            remove_id3=data.get('remove_id3', True),
            delete_source_after_process=data.get('delete_source_after_process', False)
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
class MetadataFolderMapping:
    """Represents a complete folder mapping configuration for metadata removal"""
    mapping_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_folder: str = ''
    destination_folder: str = ''
    same_as_source: bool = False  # NEW: In-place replacement mode
    is_simple_mode: bool = True
    subfolder_mappings: List[SubfolderMapping] = field(default_factory=list)
    process_root_videos: bool = True  # For mixed mode
    settings: MetadataRemovalSettings = field(default_factory=MetadataRemovalSettings)
    created_date: str = field(default_factory=lambda: datetime.now().isoformat())
    last_processed_date: str = ''
    total_processed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'mapping_id': self.mapping_id,
            'source_folder': self.source_folder,
            'destination_folder': self.destination_folder,
            'same_as_source': self.same_as_source,
            'is_simple_mode': self.is_simple_mode,
            'subfolder_mappings': [sm.to_dict() for sm in self.subfolder_mappings],
            'process_root_videos': self.process_root_videos,
            'settings': self.settings.to_dict(),
            'created_date': self.created_date,
            'last_processed_date': self.last_processed_date,
            'total_processed': self.total_processed
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'MetadataFolderMapping':
        return MetadataFolderMapping(
            mapping_id=data.get('mapping_id', str(uuid.uuid4())),
            source_folder=data.get('source_folder', ''),
            destination_folder=data.get('destination_folder', ''),
            same_as_source=data.get('same_as_source', False),
            is_simple_mode=data.get('is_simple_mode', True),
            subfolder_mappings=[
                SubfolderMapping.from_dict(sm)
                for sm in data.get('subfolder_mappings', [])
            ],
            process_root_videos=data.get('process_root_videos', True),
            settings=MetadataRemovalSettings.from_dict(data.get('settings', {})),
            created_date=data.get('created_date', datetime.now().isoformat()),
            last_processed_date=data.get('last_processed_date', ''),
            total_processed=data.get('total_processed', 0)
        )

    def validate(self) -> Tuple[bool, str]:
        """Validate the mapping configuration"""
        if not self.source_folder:
            return False, "Source folder is required"

        source_path = Path(self.source_folder).expanduser()
        if not source_path.exists():
            return False, f"Source folder does not exist: {self.source_folder}"

        if not source_path.is_dir():
            return False, f"Source path is not a directory: {self.source_folder}"

        # If not same_as_source, destination is required
        if not self.same_as_source and not self.destination_folder:
            return False, "Destination folder is required when not using same folder"

        return True, ""


class MetadataFolderScanner:
    """Scans folders and detects structure for metadata removal"""

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
        return len(MetadataFolderScanner.get_subfolders(folder_path)) > 0

    @staticmethod
    def has_videos(folder_path: str) -> bool:
        """Check if folder has video files"""
        return len(MetadataFolderScanner.get_video_files(folder_path)) > 0

    @staticmethod
    def detect_folder_structure(folder_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Detect folder structure

        Returns:
            Tuple of (mode, info_dict)
            mode: 'SIMPLE' | 'SUBFOLDERS_ONLY' | 'MIXED' | 'EMPTY'
        """
        subfolders = MetadataFolderScanner.get_subfolders(folder_path)
        root_videos = MetadataFolderScanner.get_video_files(folder_path)

        # Count videos in each subfolder
        subfolder_counts = {}
        for sf in subfolders:
            sf_path = os.path.join(folder_path, sf)
            subfolder_counts[sf] = MetadataFolderScanner.count_videos_in_folder(sf_path)

        info = {
            'subfolders': subfolders,
            'root_videos': root_videos,
            'root_video_count': len(root_videos),
            'subfolder_counts': subfolder_counts,
            'total_in_subfolders': sum(subfolder_counts.values())
        }

        if len(subfolders) == 0 and len(root_videos) > 0:
            # Case A: Only videos (no subfolders)
            return 'SIMPLE', info

        elif len(subfolders) > 0 and len(root_videos) == 0:
            # Case B: Only subfolders (no root videos)
            return 'SUBFOLDERS_ONLY', info

        elif len(subfolders) > 0 and len(root_videos) > 0:
            # Case C: Mixed (both subfolders and root videos)
            return 'MIXED', info

        else:
            # Empty folder
            return 'EMPTY', info

    @staticmethod
    def detect_folder_mode(source_folder: str, dest_folder: str) -> Tuple[str, Dict[str, Any]]:
        """
        Detect folder mode for source and destination (like video editor)

        Returns:
            Tuple of (mode, info_dict)
            mode: 'simple' or 'complex'
        """
        source_subfolders = MetadataFolderScanner.get_subfolders(source_folder)
        dest_subfolders = MetadataFolderScanner.get_subfolders(dest_folder) if dest_folder else []

        source_videos = MetadataFolderScanner.get_video_files(source_folder)

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


class MetadataPlanLimitChecker:
    """Manages daily limits based on user plan for metadata remover"""

    BASIC_LIMIT = 200
    PRO_LIMIT = 999999  # Effectively unlimited

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.expanduser('~'),
                '.onesoul',
                'metadata_plan_info.json'
            )
        self.config_path = config_path
        self.plan_info = self._load_plan_info()
        self._sync_with_license()  # Auto-sync with license on init

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

    def _sync_with_license(self):
        """Sync plan with license manager (auto-sync on init)"""
        try:
            # Try to load license data from local storage
            license_path = os.path.join(os.path.expanduser('~'), '.onesoul', 'license.dat')

            if not os.path.exists(license_path):
                # No license file, keep current plan (default: basic)
                return

            # Import here to avoid circular dependencies
            from modules.license import LicenseManager

            # Create temporary license manager to get plan
            license_manager = LicenseManager()
            license_info = license_manager.get_license_info()

            if not license_info:
                return

            # Get plan type from license
            plan_type = license_info.get('plan_type', 'basic').lower()

            # Map license plan types to basic/pro
            if plan_type in ['pro', 'yearly', 'premium']:
                new_plan = 'pro'
            else:
                new_plan = 'basic'

            # Update plan if different
            if self.plan_info.user_plan != new_plan:
                logger.info(f"[Metadata Remover] Syncing plan from license: {new_plan}")
                self.set_user_plan(new_plan)

        except Exception as e:
            logger.debug(f"Could not sync with license (not critical): {e}")
            # Silent fail - not critical, will use default/saved plan

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


class MetadataFolderMappingManager:
    """Manages metadata folder mappings"""

    def __init__(self, mappings_file: str = None):
        if mappings_file is None:
            mappings_file = os.path.join(
                os.path.expanduser('~'),
                '.onesoul',
                'metadata_folder_mappings.json'
            )

        self.mappings_file = mappings_file
        self.mappings: List[MetadataFolderMapping] = []
        self.plan_checker = MetadataPlanLimitChecker()

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
                    MetadataFolderMapping.from_dict(m)
                    for m in data.get('mappings', [])
                ]
                logger.info(f"Loaded {len(self.mappings)} metadata mappings")
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

            logger.info(f"Saved {len(self.mappings)} metadata mappings")
        except Exception as e:
            logger.error(f"Error saving mappings: {e}")

    def add_mapping(self, mapping: MetadataFolderMapping) -> bool:
        """Add a new mapping"""
        is_valid, error = mapping.validate()
        if not is_valid:
            logger.error(f"Invalid mapping: {error}")
            return False

        self.mappings.append(mapping)
        self.save()
        logger.info(f"Added new mapping: {mapping.source_folder}")
        return True

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

    def create_destination_folders(self, mapping: MetadataFolderMapping) -> bool:
        """Create destination folders if they don't exist"""
        try:
            if mapping.same_as_source:
                # No need to create folders for in-place mode
                return True

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
