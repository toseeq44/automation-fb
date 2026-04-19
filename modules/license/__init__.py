"""License management module"""
from .hardware_id import generate_hardware_id, get_device_name
from .firebase_license_manager import (
    FirestoreLicenseManager,
    LegacyServerLicenseManager,
    LicenseManager,
)
from .plan_sync import (
    get_plan_from_license,
    sync_video_editor_plan,
    sync_metadata_remover_plan,
    sync_auto_uploader_plan,
    sync_all_plans,
    get_plan_display_info
)

__all__ = [
    'generate_hardware_id',
    'get_device_name',
    'LicenseManager',
    'FirestoreLicenseManager',
    'LegacyServerLicenseManager',
    'get_plan_from_license',
    'sync_video_editor_plan',
    'sync_metadata_remover_plan',
    'sync_auto_uploader_plan',
    'sync_all_plans',
    'get_plan_display_info'
]
