"""
API Key Manager for Title Generator
Handles secure storage and validation of Groq API key
"""

import os
import json
from pathlib import Path
from typing import Optional
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class APIKeyManager:
    """Manage Groq API key storage and validation"""

    def __init__(self):
        """Initialize API key manager"""
        # Config file location (similar to AutoUploader)
        self.config_dir = Path.home() / '.automation-fb'
        self.config_file = self.config_dir / 'title_generator_config.json'

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def get_api_key(self) -> Optional[str]:
        """
        Get stored API key

        Returns:
            API key string or None if not set
        """
        try:
            if not self.config_file.exists():
                return None

            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            return config.get('groq_api_key')

        except Exception as e:
            logger.error(f"Failed to read API key: {e}")
            return None

    def set_api_key(self, api_key: str) -> bool:
        """
        Save API key to config file

        Args:
            api_key: Groq API key

        Returns:
            True if saved successfully
        """
        try:
            # Load existing config or create new
            config = {}
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

            # Update API key
            config['groq_api_key'] = api_key

            # Save config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)

            logger.info("API key saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save API key: {e}")
            return False

    def validate_api_key(self, api_key: str) -> tuple[bool, str]:
        """
        Validate Groq API key with test API call

        Args:
            api_key: Groq API key to validate

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            from groq import Groq

            # Create client
            client = Groq(api_key=api_key)

            # Test API call
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Say hello"}],
                max_tokens=10,
                timeout=10
            )

            # Check response
            if response and response.choices:
                logger.info("API key validation successful")
                return True, "✅ API key is valid!"
            else:
                return False, "❌ Invalid response from API"

        except ImportError:
            error_msg = "❌ Groq library not installed. Install with: pip install groq"
            logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"❌ Invalid API key: {str(e)}"
            logger.error(f"API key validation failed: {e}")
            return False, error_msg

    def clear_api_key(self) -> bool:
        """
        Clear stored API key

        Returns:
            True if cleared successfully
        """
        try:
            if self.config_file.exists():
                # Load config
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                # Remove API key
                if 'groq_api_key' in config:
                    del config['groq_api_key']

                # Save updated config
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)

            logger.info("API key cleared")
            return True

        except Exception as e:
            logger.error(f"Failed to clear API key: {e}")
            return False

    def has_api_key(self) -> bool:
        """
        Check if API key is stored

        Returns:
            True if API key exists
        """
        api_key = self.get_api_key()
        return api_key is not None and len(api_key) > 0
