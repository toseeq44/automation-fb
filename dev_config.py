# Development Configuration
# Set to True during development to skip license checks
# Set to False for production

DEV_MODE = False  # Change to True only for local debugging

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
