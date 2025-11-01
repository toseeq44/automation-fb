# Development Configuration
# Set to True during development to skip license checks
# Set to False for production

DEV_MODE = True  # 🔧 Change to False for production

# Development settings
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
