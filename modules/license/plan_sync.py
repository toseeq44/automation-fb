"""
modules/license/plan_sync.py
Centralized Plan Synchronization Utility
Syncs user plan across all modules from license manager
"""

import os
from typing import Optional, Dict, Any
from modules.logging.logger import get_logger

logger = get_logger(__name__)


def get_plan_from_license(license_manager) -> str:
    """
    Get current plan type from license manager

    Args:
        license_manager: LicenseManager instance

    Returns:
        'basic' or 'pro' - defaults to 'basic' if unable to determine
    """
    try:
        if not license_manager:
            logger.warning("No license manager provided, defaulting to basic plan")
            return 'basic'

        license_info = license_manager.get_license_info()

        if not license_info:
            logger.warning("No license info available, defaulting to basic plan")
            return 'basic'

        plan_type = license_info.get('plan_type', 'basic').lower()

        # Map various plan names to basic/pro
        # License can have 'monthly', 'yearly', 'trial' but we map to basic/pro
        if plan_type in ['pro', 'yearly', 'premium']:
            return 'pro'
        else:
            return 'basic'

    except Exception as e:
        logger.error(f"Error getting plan from license: {e}")
        return 'basic'


def sync_video_editor_plan(license_manager) -> bool:
    """
    Sync Video Editor plan with license manager

    Args:
        license_manager: LicenseManager instance

    Returns:
        True if sync successful, False otherwise
    """
    try:
        from modules.video_editor.editor_folder_manager import PlanLimitChecker

        plan = get_plan_from_license(license_manager)

        # Create plan checker instance and set plan
        plan_checker = PlanLimitChecker()
        plan_checker.set_user_plan(plan)

        logger.info(f"Video Editor plan synced to: {plan}")
        return True

    except Exception as e:
        logger.error(f"Error syncing Video Editor plan: {e}")
        return False


def sync_metadata_remover_plan(license_manager) -> bool:
    """
    Sync Metadata Remover plan with license manager

    Args:
        license_manager: LicenseManager instance

    Returns:
        True if sync successful, False otherwise
    """
    try:
        from modules.metadata_remover.metadata_folder_manager import MetadataPlanLimitChecker

        plan = get_plan_from_license(license_manager)

        # Create plan checker instance and set plan
        plan_checker = MetadataPlanLimitChecker()
        plan_checker.set_user_plan(plan)

        logger.info(f"Metadata Remover plan synced to: {plan}")
        return True

    except Exception as e:
        logger.error(f"Error syncing Metadata Remover plan: {e}")
        return False


def sync_auto_uploader_plan(license_manager) -> bool:
    """
    Sync Auto Uploader plan with license manager

    Args:
        license_manager: LicenseManager instance

    Returns:
        True if sync successful, False otherwise
    """
    try:
        from modules.auto_uploader.approaches.ixbrowser.config.upload_config import USER_CONFIG

        plan = get_plan_from_license(license_manager)

        # Update USER_CONFIG dictionary
        USER_CONFIG['user_type'] = plan

        logger.info(f"Auto Uploader plan synced to: {plan}")
        return True

    except Exception as e:
        logger.error(f"Error syncing Auto Uploader plan: {e}")
        return False


def sync_all_plans(license_manager) -> Dict[str, bool]:
    """
    Sync all module plans with license manager

    Args:
        license_manager: LicenseManager instance

    Returns:
        Dict with sync status for each module
    """
    results = {
        'video_editor': sync_video_editor_plan(license_manager),
        'metadata_remover': sync_metadata_remover_plan(license_manager),
        'auto_uploader': sync_auto_uploader_plan(license_manager)
    }

    plan = get_plan_from_license(license_manager)
    logger.info(f"✅ Plan sync completed. Current plan: {plan.upper()}")
    logger.info(f"   Video Editor: {'✓' if results['video_editor'] else '✗'}")
    logger.info(f"   Metadata Remover: {'✓' if results['metadata_remover'] else '✗'}")
    logger.info(f"   Auto Uploader: {'✓' if results['auto_uploader'] else '✗'}")

    return results


def get_plan_display_info(license_manager) -> Dict[str, Any]:
    """
    Get plan display information

    Args:
        license_manager: LicenseManager instance

    Returns:
        Dict with plan display info
    """
    plan = get_plan_from_license(license_manager)

    return {
        'plan': plan,
        'plan_display': 'Pro (Unlimited)' if plan == 'pro' else 'Basic (200/day)',
        'is_unlimited': plan == 'pro',
        'daily_limit': 999999 if plan == 'pro' else 200,
        'color': '#43B581' if plan == 'pro' else '#3498DB'
    }
