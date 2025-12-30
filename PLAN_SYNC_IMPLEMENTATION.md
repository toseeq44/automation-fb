# Plan Synchronization Implementation

## Overview

This document describes the implementation of centralized plan synchronization across all modules (Video Editor, Metadata Remover, and Auto Uploader) to ensure Pro users get unlimited access and Basic users get proper daily limits.

## Problem Statement

Previously, all three modules had separate plan/limit systems that were NOT synchronized with the license manager's plan_type:

1. **Video Editor**: Used `PlanLimitChecker` class (default: 'basic')
2. **Metadata Remover**: Used `MetadataPlanLimitChecker` class (default: 'basic')
3. **Auto Uploader**: Used `USER_CONFIG` dictionary (default: 'basic')

**Result**: Even if a user had a 'pro' license, they were still getting 'basic' plan limitations (200/day) because modules never synced with the license manager.

## Solution Architecture

### 1. Centralized Plan Sync Utility

**File**: `modules/license/plan_sync.py`

**Key Functions**:

- `get_plan_from_license(license_manager)` - Extracts plan from license manager
- `sync_video_editor_plan(license_manager)` - Syncs Video Editor plan
- `sync_metadata_remover_plan(license_manager)` - Syncs Metadata Remover plan
- `sync_auto_uploader_plan(license_manager)` - Syncs Auto Uploader plan
- `sync_all_plans(license_manager)` - Syncs all modules at once
- `get_plan_display_info(license_manager)` - Gets formatted plan info for UI

**Plan Mapping**:
- License plans: 'pro', 'yearly', 'premium' → Map to: 'pro'
- License plans: 'basic', 'monthly', 'trial' → Map to: 'basic'

### 2. Auto-Sync on Initialization

Each module's plan checker now automatically syncs with license on initialization:

#### Video Editor (`modules/video_editor/editor_folder_manager.py`)

```python
class PlanLimitChecker:
    def __init__(self, config_path: str = None):
        ...
        self.plan_info = self._load_plan_info()
        self._sync_with_license()  # ✅ Auto-sync on init

    def _sync_with_license(self):
        # Loads license locally and syncs plan
        # Maps plan_type to 'basic' or 'pro'
        # Updates plan if different
```

#### Metadata Remover (`modules/metadata_remover/metadata_folder_manager.py`)

```python
class MetadataPlanLimitChecker:
    def __init__(self, config_path: str = None):
        ...
        self.plan_info = self._load_plan_info()
        self._sync_with_license()  # ✅ Auto-sync on init

    def _sync_with_license(self):
        # Same logic as Video Editor
```

#### Auto Uploader (`modules/auto_uploader/approaches/ixbrowser/config/upload_config.py`)

```python
def sync_user_type_with_license():
    # Syncs USER_CONFIG['user_type'] with license
    # Maps plan_type to 'basic' or 'pro'
    ...

# ✅ Auto-sync on module import
sync_user_type_with_license()
```

### 3. Application-Level Sync

**File**: `main.py`

After license validation (successful or in dev mode), sync all plans:

```python
# Sync user plan across all modules
logger.info("Syncing user plan across modules...", "App")
sync_all_plans(license_manager)
```

This ensures:
- Plans are synced immediately on app startup
- All modules have consistent plan
- Works in both production and DEV_MODE

## Plan Limits

### Basic Plan
- **Daily Limit**: 200 videos/day
- **Video Editor**: 200 videos/day
- **Metadata Remover**: 200 videos/day
- **Auto Uploader**: 200 bookmarks/day

### Pro Plan
- **Daily Limit**: Unlimited (999999)
- **Video Editor**: Unlimited
- **Metadata Remover**: Unlimited
- **Auto Uploader**: Unlimited (None)

## Files Modified

1. **`modules/license/plan_sync.py`** (NEW)
   - Centralized plan synchronization utility

2. **`modules/license/__init__.py`**
   - Export plan_sync functions

3. **`main.py`**
   - Import sync_all_plans
   - Call sync_all_plans after license validation

4. **`modules/video_editor/editor_folder_manager.py`**
   - Add `_sync_with_license()` method to PlanLimitChecker
   - Call in `__init__`

5. **`modules/metadata_remover/metadata_folder_manager.py`**
   - Add `_sync_with_license()` method to MetadataPlanLimitChecker
   - Call in `__init__`

6. **`modules/auto_uploader/approaches/ixbrowser/config/upload_config.py`**
   - Add `sync_user_type_with_license()` function
   - Call on module import

## How It Works

### Startup Flow

1. **App Starts** (`main.py`)
2. **License Validation** → Gets license info (including plan_type)
3. **Plan Sync** → `sync_all_plans(license_manager)` called
   - Video Editor plan updated
   - Metadata Remover plan updated
   - Auto Uploader user_type updated
4. **Modules Used** → Each module's plan checker auto-syncs on creation
   - Checks local license file
   - Loads plan_type
   - Updates internal plan if different

### Runtime Flow

1. **User Opens Dialog** (e.g., Video Editor bulk processing)
2. **Plan Checker Created** → `PlanLimitChecker()`
3. **Auto-Sync Triggered** → `_sync_with_license()` called
4. **Plan Checked**:
   - If 'pro': Returns unlimited (999999)
   - If 'basic': Returns 200/day limit
5. **Limit Enforced**:
   - Pro users: No restrictions
   - Basic users: Limited to daily quota

## Benefits

✅ **Centralized Management**: Single source of truth for plan logic
✅ **Auto-Sync**: No manual intervention needed
✅ **Robust**: Multiple sync points ensure consistency
✅ **Backward Compatible**: Works with existing code
✅ **Fail-Safe**: Silent failures with defaults
✅ **No Breaking Changes**: Existing functionality preserved

## Testing

### Verify Plan Sync

1. **Check logs on startup**:
   ```
   [App] Syncing user plan across modules...
   [License] ✅ Plan sync completed. Current plan: PRO
   ```

2. **Check module-specific logs**:
   ```
   [Video Editor] Syncing plan from license: pro
   [Metadata Remover] Syncing plan from license: pro
   [Auto Uploader] Syncing user_type from license: pro
   ```

3. **Verify limits in UI**:
   - Video Editor: Shows "Plan: Pro (Unlimited)"
   - Metadata Remover: Shows "Plan: Pro (Unlimited)"
   - Auto Uploader: Shows "Unlimited ∞"

### Test Cases

#### Pro User
1. Activate pro license
2. Open Video Editor → Check unlimited
3. Open Metadata Remover → Check unlimited
4. Start Auto Uploader → Check unlimited
5. Process >200 videos → Should succeed

#### Basic User
1. Activate basic license
2. Open Video Editor → Check 200/day limit
3. Open Metadata Remover → Check 200/day limit
4. Start Auto Uploader → Check 200/day limit
5. Process >200 videos → Should block after 200

## Future Improvements

1. **Real-time Updates**: Add license change listeners
2. **Plan Features**: Different features per plan (not just limits)
3. **Custom Plans**: Support for custom plan types
4. **Usage Analytics**: Track plan-based usage statistics
5. **Grace Period**: Allow brief overages for pro users

## Notes

- Plan sync is **non-critical**: If sync fails, defaults to 'basic' plan
- License file location: `~/.onesoul/license.dat`
- Plan info stored separately per module:
  - Video Editor: `~/.onesoul/editor_plan_info.json`
  - Metadata Remover: `~/.onesoul/metadata_plan_info.json`
  - Auto Uploader: In-memory (USER_CONFIG dict)
