"""
ixBrowser Configuration Handler
Manages user inputs: base_url, email, password
Saves configuration in persistent user folder (works with PyInstaller EXE)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def get_persistent_data_dir() -> Path:
    """
    Get persistent data directory that works both in development and EXE.

    Returns:
        Path to persistent data directory (~/.onesoul/config/)
    """
    # Always use user's home directory for persistent storage
    # This ensures data survives between EXE runs
    data_dir = Path.home() / ".onesoul" / "config"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


class IXBrowserConfig:
    """Handles ixBrowser configuration storage and retrieval."""

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize config handler.

        Args:
            config_file: Path to config file. If None, uses persistent location.
        """
        if config_file is None:
            # Use persistent directory (survives EXE restarts)
            config_file = get_persistent_data_dir() / "ix_config.json"

        self.config_file = config_file
        self._config: Dict[str, str] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file if exists."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                logger.info("[IXConfig] Configuration loaded from: %s", self.config_file)
            except Exception as e:
                logger.error("[IXConfig] Failed to load config: %s", e)
                self._config = {}
        else:
            logger.info("[IXConfig] No existing configuration found. Using defaults.")
            self._config = {}

    def _save_config(self) -> bool:
        """Save configuration to file."""
        try:
            # Create parent directory if not exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)

            logger.info("[IXConfig] Configuration saved to: %s", self.config_file)
            return True
        except Exception as e:
            logger.error("[IXConfig] Failed to save config: %s", e)
            return False

    def set_credentials(self, base_url: str, email: str, password: str) -> bool:
        """
        Set ixBrowser credentials.

        Args:
            base_url: ixBrowser API base URL (e.g., http://127.0.0.1:53200)
            email: User email for login
            password: User password for login

        Returns:
            True if saved successfully
        """
        logger.info("[IXConfig] Setting credentials...")
        logger.info("[IXConfig]   Base URL: %s", base_url)
        logger.info("[IXConfig]   Email: %s", email)

        # Validate inputs
        if not base_url or not base_url.strip():
            logger.error("[IXConfig] Base URL cannot be empty")
            return False

        if not email or not email.strip():
            logger.error("[IXConfig] Email cannot be empty")
            return False

        if not password or not password.strip():
            logger.error("[IXConfig] Password cannot be empty")
            return False

        # Normalize base_url
        base_url = base_url.strip()
        if not base_url.startswith("http"):
            base_url = f"http://{base_url}"

        # Remove trailing slashes
        base_url = base_url.rstrip("/")

        # Store credentials
        self._config["base_url"] = base_url
        self._config["email"] = email.strip()
        self._config["password"] = password.strip()

        # Save to file
        return self._save_config()

    def get_base_url(self) -> str:
        """
        Get configured base URL.

        Returns:
            Base URL or default value
        """
        return self._config.get("base_url", "http://127.0.0.1:53200")

    def get_email(self) -> str:
        """
        Get configured email.

        Returns:
            Email or empty string
        """
        return self._config.get("email", "")

    def get_password(self) -> str:
        """
        Get configured password.

        Returns:
            Password or empty string
        """
        return self._config.get("password", "")

    def is_configured(self) -> bool:
        """
        Check if configuration is complete.

        Returns:
            True if all required fields are set
        """
        has_base_url = bool(self._config.get("base_url"))
        has_email = bool(self._config.get("email"))
        has_password = bool(self._config.get("password"))

        is_complete = has_base_url and has_email and has_password

        if not is_complete:
            logger.warning("[IXConfig] Configuration incomplete!")
            if not has_base_url:
                logger.warning("[IXConfig]   Missing: base_url")
            if not has_email:
                logger.warning("[IXConfig]   Missing: email")
            if not has_password:
                logger.warning("[IXConfig]   Missing: password")

        return is_complete

    def clear_config(self) -> bool:
        """
        Clear all configuration.

        Returns:
            True if cleared successfully
        """
        logger.info("[IXConfig] Clearing configuration...")
        self._config = {}
        return self._save_config()

    def get_all_config(self) -> Dict[str, str]:
        """
        Get all configuration as dictionary.

        Returns:
            Configuration dictionary (password masked)
        """
        config_copy = self._config.copy()
        if "password" in config_copy:
            config_copy["password"] = "***MASKED***"
        return config_copy


def prompt_user_for_credentials() -> Optional[IXBrowserConfig]:
    """
    Interactive prompt for user credentials.
    Use this when running standalone.

    Returns:
        IXBrowserConfig instance or None if cancelled
    """
    print("\n" + "="*60)
    print("ixBrowser Approach - Configuration Setup")
    print("="*60 + "\n")

    base_url = input("Enter ixBrowser API Base URL [http://127.0.0.1:53200]: ").strip()
    if not base_url:
        base_url = "http://127.0.0.1:53200"

    email = input("Enter your email: ").strip()
    if not email:
        print("Error: Email is required!")
        return None

    password = input("Enter your password: ").strip()
    if not password:
        print("Error: Password is required!")
        return None

    # Create config and save
    config = IXBrowserConfig()
    if config.set_credentials(base_url, email, password):
        print("\n✓ Configuration saved successfully!")
        print(f"  Base URL: {base_url}")
        print(f"  Email: {email}")
        return config
    else:
        print("\n✗ Failed to save configuration!")
        return None


if __name__ == "__main__":
    # Test mode - prompt user for credentials
    config = prompt_user_for_credentials()
    if config and config.is_configured():
        print("\n✓ Configuration is complete and ready to use!")
    else:
        print("\n✗ Configuration incomplete!")
