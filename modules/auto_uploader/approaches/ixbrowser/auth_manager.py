"""
IX Browser Authentication Manager
==================================
Manages loading and validating IX Browser credentials.

Features:
- Load credentials from settings and secure storage
- Validate required fields
- Detailed logging for debugging
- Integration with SettingsManager and CredentialManager

Credentials Required:
- API Key (optional - for Cloud API)
- Email (required)
- Password (required - stored securely)
- Profile Name (required)
"""
import logging
from typing import Dict, Optional


class IXAuthManager:
    """
    Manages ixBrowser authentication credentials

    Loads credentials from:
    1. settings.json - API key, email, profile name
    2. Keyring (secure) - Password

    Example:
        >>> from ...config.settings_manager import SettingsManager
        >>> from ...auth.credential_manager import CredentialManager
        >>>
        >>> settings = SettingsManager()
        >>> credentials = CredentialManager()
        >>> auth = IXAuthManager(settings, credentials)
        >>>
        >>> if auth.validate_credentials():
        ...     creds = auth.get_api_credentials()
        ...     print(creds['email'])
    """

    def __init__(self, settings_manager, credential_manager):
        """
        Initialize auth manager

        Args:
            settings_manager: SettingsManager instance
            credential_manager: CredentialManager instance
        """
        self.settings = settings_manager
        self.credentials = credential_manager

        logging.info("="*60)
        logging.info("IX AUTH MANAGER INITIALIZATION")
        logging.info("="*60)
        logging.info("✅ Auth manager initialized")
        logging.info("="*60)
        logging.info("")

    def get_api_credentials(self) -> Dict[str, str]:
        """
        Get API credentials from storage

        Returns:
            {
                'api_key': 'xxx',
                'email': 'user@example.com',
                'password': 'xxx',
                'profile_name': 'MyProfile1'
            }
        """
        logging.info("")
        logging.info("="*60)
        logging.info("LOADING IX BROWSER CREDENTIALS")
        logging.info("="*60)

        # Get from settings.json
        logging.info("📋 Step 1/2: Loading from settings.json...")

        ix_config = self.settings.get_credentials('ix') or {}

        api_key = ix_config.get('api_key', '')
        email = ix_config.get('email', '')
        profile_name = ix_config.get('profile_name', '')

        logging.info(f"   API Key: {'***' + api_key[-4:] if api_key else 'Not set'}")
        logging.info(f"   Email: {email if email else 'Not set'}")
        logging.info(f"   Profile Name: {profile_name if profile_name else 'Not set'}")

        # Get password from secure storage (keyring)
        logging.info("")
        logging.info("📋 Step 2/2: Loading password from secure keyring...")

        password_data = self.credentials.load_credentials('approach:ix')
        password = password_data.get('password', '') if password_data else ''

        if password:
            logging.info(f"   Password: {'*' * len(password)} (loaded securely)")
        else:
            logging.info("   Password: Not set")

        credentials = {
            'api_key': api_key,
            'email': email,
            'password': password,
            'profile_name': profile_name
        }

        logging.info("")
        logging.info("✅ CREDENTIALS LOADED")
        logging.info("="*60)
        logging.info("")

        return credentials

    def validate_credentials(self) -> bool:
        """
        Validate that all required credentials are present

        Returns:
            True if valid, False otherwise
        """
        logging.info("")
        logging.info("="*60)
        logging.info("VALIDATING IX BROWSER CREDENTIALS")
        logging.info("="*60)

        creds = self.get_api_credentials()

        required_fields = ['email', 'password', 'profile_name']
        optional_fields = ['api_key']

        logging.info("")
        logging.info("📋 Checking required fields...")

        all_valid = True

        for field in required_fields:
            value = creds.get(field, '')
            if value:
                logging.info(f"   ✅ {field}: Present")
            else:
                logging.error(f"   ❌ {field}: MISSING (Required)")
                all_valid = False

        logging.info("")
        logging.info("📋 Checking optional fields...")

        for field in optional_fields:
            value = creds.get(field, '')
            if value:
                logging.info(f"   ✅ {field}: Present (Cloud API mode)")
            else:
                logging.info(f"   ⚠️  {field}: Not provided (Local API mode)")

        logging.info("")

        if all_valid:
            logging.info("✅ VALIDATION PASSED - All required fields present")
        else:
            logging.error("❌ VALIDATION FAILED - Missing required fields")
            logging.error("")
            logging.error("HOW TO FIX:")
            logging.error("1. Open the application")
            logging.error("2. Click 'Auto Uploader' → 'Approaches' button")
            logging.error("3. Select 'IX Browser' approach")
            logging.error("4. Fill in all required fields:")
            logging.error("   - Email")
            logging.error("   - Password")
            logging.error("   - Profile Name")
            logging.error("5. Click 'Save'")

        logging.info("="*60)
        logging.info("")

        return all_valid

    def has_api_key(self) -> bool:
        """
        Check if API key is configured

        Returns:
            True if API key is present
        """
        creds = self.get_api_credentials()
        has_key = bool(creds.get('api_key'))

        if has_key:
            logging.info("🔑 API Key: PRESENT (Cloud API mode)")
        else:
            logging.info("🔑 API Key: NOT PRESENT (Local API mode)")

        return has_key

    def get_api_mode(self) -> str:
        """
        Get API mode (cloud or local)

        Returns:
            'cloud' if API key present, 'local' otherwise
        """
        return 'cloud' if self.has_api_key() else 'local'
