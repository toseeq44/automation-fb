# Development Configuration
# Note: production runtime enforces license checks in main.py.
# Keep DEV_MODE False to avoid accidental local bypass assumptions.

DEV_MODE = False

# Development settings
DEV_CONFIG = {
    'skip_license': False,        # Skip license validation
    'auto_activate': False,       # Auto-activate with fake license
    'mock_license_info': {        # Mock license data for development
        'license_key': 'DEV-MODE-TEST-KEY',
        'plan_type': 'yearly',
        'days_remaining': 999,
        'device_name': 'Development Device'
    }
}
