# Development Configuration
# Set to True during development to skip license checks
# Automatically set to False when running as PyInstaller EXE

import sys

def _is_running_as_exe() -> bool:
    """Check if running as PyInstaller EXE."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

# 🔧 DEV_MODE is automatically disabled for EXE builds
# Manual override: change DEV_MODE_OVERRIDE to True/False
DEV_MODE_OVERRIDE = None  # Set to True/False to override auto-detection

if DEV_MODE_OVERRIDE is not None:
    DEV_MODE = DEV_MODE_OVERRIDE
elif _is_running_as_exe():
    # Running as EXE - disable dev mode
    DEV_MODE = False
else:
    # Running as Python script - enable dev mode
    DEV_MODE = True

# Development settings (only used when DEV_MODE = True)
DEV_CONFIG = {
    'skip_license': True,        # Skip license validation
    'auto_activate': True,       # Auto-activate with fake license
    'mock_license_info': {       # Mock license data for development
        'license_key': 'DEV-MODE-TEST-KEY',
        'plan_type': 'yearly',
        'days_remaining': 999,
        'device_name': 'Development Device'
    }
}
