"""
NSTbrowser Configuration Handler
Manages API key, email, password, and connection settings
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class NSTBrowserConfig:
    """Manages NSTbrowser configuration including API credentials."""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize config handler.

        Args:
            config_file: Path to config JSON file (default: nst_config.json in data dir)
        """
        # Default config file location
        if config_file is None:
            data_dir = Path(__file__).parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            config_file = str(data_dir / "nst_config.json")

        self.config_file = Path(config_file)
        self._config: Dict[str, Any] = {}

        # Load existing config if available
        self.load_config()

    def load_config(self) -> bool:
        """
        Load configuration from file.

        Returns:
            True if config loaded successfully
        """
        if not self.config_file.exists():
            logger.info("[NSTConfig] No config file found, will create on first save")
            self._config = self._get_default_config()
            return False

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config = json.load(f)

            logger.info("[NSTConfig] ✓ Config loaded from: %s", self.config_file)
            return True

        except Exception as e:
            logger.error("[NSTConfig] Failed to load config: %s", str(e))
            self._config = self._get_default_config()
            return False

    def save_config(self) -> bool:
        """
        Save configuration to file.

        Returns:
            True if saved successfully
        """
        try:
            # Ensure parent directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2)

            logger.info("[NSTConfig] ✓ Config saved to: %s", self.config_file)
            return True

        except Exception as e:
            logger.error("[NSTConfig] Failed to save config: %s", str(e))
            return False

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration.

        Returns:
            Dictionary with default settings
        """
        return {
            "base_url": "http://127.0.0.1:8848",
            "email": "",
            "password": "",
            "api_key": "",
            "auto_launch": True,
            "timeout": 60
        }

    def set_credentials(self, email: str, password: str, api_key: str,
                       base_url: str = "http://127.0.0.1:8848") -> bool:
        """
        Set NSTbrowser credentials.

        Args:
            email: NSTbrowser account email
            password: NSTbrowser account password
            api_key: NSTbrowser API key (UUID format)
            base_url: API base URL

        Returns:
            True if credentials set successfully
        """
        logger.info("[NSTConfig] Setting credentials...")
        logger.info("[NSTConfig]   Email: %s", email)
        logger.info("[NSTConfig]   API Key: %s...%s", api_key[:8], api_key[-8:] if len(api_key) > 16 else "")
        logger.info("[NSTConfig]   Base URL: %s", base_url)

        self._config["email"] = email
        self._config["password"] = password
        self._config["api_key"] = api_key
        self._config["base_url"] = base_url

        # Auto-save
        if self.save_config():
            logger.info("[NSTConfig] ✓ Credentials saved successfully!")
            return True
        else:
            logger.error("[NSTConfig] ✗ Failed to save credentials!")
            return False

    def get_credentials(self) -> Dict[str, str]:
        """
        Get stored credentials.

        Returns:
            Dictionary with email, password, api_key, base_url
        """
        return {
            "email": self._config.get("email", ""),
            "password": self._config.get("password", ""),
            "api_key": self._config.get("api_key", ""),
            "base_url": self._config.get("base_url", "http://127.0.0.1:8848")
        }

    def validate_config(self) -> tuple[bool, str]:
        """
        Validate that required credentials are set.

        Returns:
            Tuple of (is_valid, error_message)
        """
        creds = self.get_credentials()

        if not creds["api_key"]:
            return False, "API key not set"

        if not creds["email"]:
            return False, "Email not set"

        if not creds["password"]:
            return False, "Password not set"

        if not creds["base_url"]:
            return False, "Base URL not set"

        logger.info("[NSTConfig] ✓ Configuration valid!")
        return True, "Configuration valid"

    def get_base_url(self) -> str:
        """Get API base URL."""
        return self._config.get("base_url", "http://127.0.0.1:8848")

    def get_api_key(self) -> str:
        """Get API key."""
        return self._config.get("api_key", "")

    def get_email(self) -> str:
        """Get email."""
        return self._config.get("email", "")

    def get_password(self) -> str:
        """Get password."""
        return self._config.get("password", "")

    def get_auto_launch(self) -> bool:
        """Get auto-launch setting."""
        return self._config.get("auto_launch", True)

    def get_timeout(self) -> int:
        """Get connection timeout."""
        return self._config.get("timeout", 60)

    def set_base_url(self, base_url: str) -> None:
        """Set API base URL."""
        self._config["base_url"] = base_url
        self.save_config()

    def set_auto_launch(self, enabled: bool) -> None:
        """Set auto-launch setting."""
        self._config["auto_launch"] = enabled
        self.save_config()

    def set_timeout(self, timeout: int) -> None:
        """Set connection timeout."""
        self._config["timeout"] = timeout
        self.save_config()

    def clear_config(self) -> bool:
        """
        Clear configuration and delete file.

        Returns:
            True if cleared successfully
        """
        try:
            if self.config_file.exists():
                self.config_file.unlink()
                logger.info("[NSTConfig] ✓ Config file deleted")

            self._config = self._get_default_config()
            logger.info("[NSTConfig] ✓ Config cleared")
            return True

        except Exception as e:
            logger.error("[NSTConfig] Failed to clear config: %s", str(e))
            return False

    def get_config_path(self) -> Path:
        """Get path to config file."""
        return self.config_file

    def __repr__(self) -> str:
        """String representation."""
        creds = self.get_credentials()
        has_api_key = bool(creds["api_key"])
        has_email = bool(creds["email"])

        return (f"NSTBrowserConfig("
                f"base_url={creds['base_url']}, "
                f"has_api_key={has_api_key}, "
                f"has_email={has_email})")


if __name__ == "__main__":
    # Test mode
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print("\n" + "="*60)
    print("Testing NSTbrowser Configuration Handler")
    print("="*60 + "\n")

    # Create config handler
    config = NSTBrowserConfig()
    print(f"Config: {config}\n")

    # Set credentials
    print("Setting test credentials...")
    config.set_credentials(
        email="test@example.com",
        password="test_password",
        api_key="d27f90bc-57ce-4bbe-9ab9-a3b7f99d616f"
    )

    # Validate
    print("\nValidating configuration...")
    is_valid, message = config.validate_config()
    print(f"Valid: {is_valid} - {message}")

    # Get credentials
    print("\nRetrieving credentials...")
    creds = config.get_credentials()
    print(f"Email: {creds['email']}")
    print(f"API Key: {creds['api_key'][:8]}...{creds['api_key'][-8:]}")
    print(f"Base URL: {creds['base_url']}")

    print("\n✓ Test complete!")
