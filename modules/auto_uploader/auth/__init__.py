"""
Auth Module
===========
Handles authentication, login, and credential management.

This module is HIGHLY REUSABLE and can be imported by other modules.

Submodules:
-----------
- credential_manager: Secure credential storage/retrieval
- login_handler: Facebook login automation
- session_validator: Session validation
- two_factor_handler: 2FA handling
- logout_handler: Logout operations

Example Usage:
--------------
from modules.auto_uploader.auth.credential_manager import CredentialManager
from modules.auto_uploader.auth.login_handler import LoginHandler

creds = CredentialManager()
creds.save_credentials("profile1", {"email": "...", "password": "..."})

login = LoginHandler()
login.login(driver, "email@example.com", "password")
"""

__version__ = "2.0.0"
__all__ = [
    "CredentialManager",
    "LoginHandler",
    "SessionValidator",
    "TwoFactorHandler",
    "LogoutHandler",
]
