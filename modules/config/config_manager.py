"""
Configuration Manager for OneSoul
Handles application settings and preferences
"""
import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


class ConfigManager:
    """
    Manages application configuration and settings
    """

    DEFAULT_CONFIG = {
        "app": {
            "version": "1.0.0",
            "theme": "dark",
            "language": "en",
            "check_updates": True,
            "first_run": True
        },
        "license": {
            "server_url": "https://constant-myth-pens-courts.trycloudflare.com",
            "last_check": None,
            "grace_period_days": 30
        },
        "paths": {
            "downloads": str(Path.home() / "Downloads" / "OneSoul"),
            "edited_videos": str(Path.home() / "Videos" / "OneSoul"),
            "temp": str(Path.home() / ".onesoul" / "temp"),
            "cache": str(Path.home() / ".onesoul" / "cache")
        },
        "rate_limiting": {
            "enabled": True,
            "preset": "balanced",  # conservative, balanced, aggressive, custom
            "batch_size": 20,
            "delay_seconds": 2.0,
            "platform_specific": {
                "youtube": 2.0,
                "instagram": 3.0,
                "tiktok": 2.5,
                "facebook": 3.0,
                "twitter": 2.0
            }
        },
        "downloader": {
            "default_quality": "1080p",
            "concurrent_downloads": 3,
            "auto_retry": True,
            "max_retries": 3,
            "show_notifications": True
        },
        "editor": {
            "default_format": "mp4",
            "default_codec": "h264",
            "default_quality": "high",
            "preview_quality": "medium",
            "hardware_acceleration": True
        },
        "logging": {
            "enabled": True,
            "level": "INFO",  # DEBUG, INFO, WARNING, ERROR
            "keep_days": 30,
            "console_output": True
        },
        "link_grabber": {
            "max_videos": 0,  # 0 = unlimited
            "save_folder": str(Path.home() / "Desktop" / "Links Grabber"),
            "auto_save": False
        },
        "folder_mapping": {
            "enabled": True,
            "mappings_file": str(Path.home() / ".onesoul" / "folder_mappings.json"),
            "auto_move_after_download": False,
            "default_daily_limit": 5,
            "default_move_condition": "empty_only",  # empty_only or always
            "show_confirmation": True,
            "default_sort_by": "oldest"  # oldest or newest
        }
    }

    def __init__(self, config_path: Path = None):
        """
        Initialize Config Manager

        Args:
            config_path: Path to config file (default: ~/.onesoul/config.json)
        """
        if config_path:
            self.config_path = config_path
        else:
            # Determine application path (handles both frozen EXE and script)
            if getattr(sys, 'frozen', False):
                application_path = Path(sys.executable).parent
            else:
                application_path = Path.cwd()

            # Check for portable config next to the executable
            local_config = application_path / "config.json"
            
            if local_config.exists():
                self.config_path = local_config
            else:
                config_dir = Path.home() / ".onesoul"
                config_dir.mkdir(parents=True, exist_ok=True)
                self.config_path = config_dir / "config.json"

        self.config = self._load_or_create_config()

    def _load_or_create_config(self) -> Dict:
        """Load config from file or create default"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # Merge with defaults (in case new keys were added)
                config = self._merge_configs(self.DEFAULT_CONFIG, loaded_config)
                return config
            else:
                # Create default config
                self._save_config(self.DEFAULT_CONFIG)
                return self.DEFAULT_CONFIG.copy()

        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
            config = self.DEFAULT_CONFIG.copy()

        # Allow overriding license server via environment variable
        server_url_env = os.getenv("ONESOUL_LICENSE_URL")
        if server_url_env:
            config.setdefault("license", {})
            config["license"]["server_url"] = server_url_env

        return config

    def _merge_configs(self, default: Dict, loaded: Dict) -> Dict:
        """Merge loaded config with defaults (adds missing keys)"""
        merged = default.copy()

        for key, value in loaded.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value

        return merged

    def _save_config(self, config: Dict = None):
        """Save config to file"""
        try:
            if config is None:
                config = self.config

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

        except Exception as e:
            print(f"Error saving config: {e}")
            raise

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get config value by key path

        Args:
            key_path: Dot-separated path (e.g., 'app.theme')
            default: Default value if key not found

        Returns:
            Config value or default
        """
        try:
            keys = key_path.split('.')
            value = self.config

            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default

            return value

        except Exception:
            return default

    def set(self, key_path: str, value: Any, save: bool = True):
        """
        Set config value by key path

        Args:
            key_path: Dot-separated path (e.g., 'app.theme')
            value: Value to set
            save: Whether to save to file immediately
        """
        try:
            keys = key_path.split('.')
            config = self.config

            # Navigate to the parent dict
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]

            # Set the value
            config[keys[-1]] = value

            if save:
                self._save_config()

        except Exception as e:
            print(f"Error setting config value: {e}")
            raise

    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.config = self.DEFAULT_CONFIG.copy()
        self._save_config()

    def export_config(self, export_path: Path) -> bool:
        """
        Export config to a file

        Args:
            export_path: Where to save the config

        Returns:
            True if successful
        """
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error exporting config: {e}")
            return False

    def import_config(self, import_path: Path) -> bool:
        """
        Import config from a file

        Args:
            import_path: Path to config file to import

        Returns:
            True if successful
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)

            # Merge with defaults to ensure all keys exist
            self.config = self._merge_configs(self.DEFAULT_CONFIG, imported_config)
            self._save_config()
            return True

        except Exception as e:
            print(f"Error importing config: {e}")
            return False

    def ensure_directories_exist(self):
        """Ensure all configured directories exist"""
        try:
            dirs = [
                self.get('paths.downloads'),
                self.get('paths.edited_videos'),
                self.get('paths.temp'),
                self.get('paths.cache'),
                self.get('link_grabber.save_folder')
            ]

            for dir_path in dirs:
                if dir_path:
                    Path(dir_path).mkdir(parents=True, exist_ok=True)

        except Exception as e:
            print(f"Error creating directories: {e}")

    def get_rate_limit_config(self, platform: str = None) -> Dict:
        """
        Get rate limiting configuration

        Args:
            platform: Specific platform or None for general

        Returns:
            Rate limit config dict
        """
        if not self.get('rate_limiting.enabled'):
            return {
                'enabled': False,
                'batch_size': 1000,
                'delay_seconds': 0
            }

        preset = self.get('rate_limiting.preset')

        # Preset values
        presets = {
            'conservative': {'batch_size': 10, 'delay': 5.0},
            'balanced': {'batch_size': 20, 'delay': 2.0},
            'aggressive': {'batch_size': 50, 'delay': 0.5},
            'custom': {
                'batch_size': self.get('rate_limiting.batch_size'),
                'delay': self.get('rate_limiting.delay_seconds')
            }
        }

        config = presets.get(preset, presets['balanced'])

        # Platform-specific override
        if platform:
            platform_delay = self.get(f'rate_limiting.platform_specific.{platform}')
            if platform_delay:
                config['delay'] = platform_delay

        return {
            'enabled': True,
            'batch_size': config['batch_size'],
            'delay_seconds': config['delay']
        }


# Global config instance
_global_config = None


def get_config() -> ConfigManager:
    """
    Get or create global config instance

    Returns:
        ConfigManager instance
    """
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager()
        _global_config.ensure_directories_exist()
    return _global_config


# Test function
if __name__ == '__main__':
    config = get_config()

    print("Config Test")
    print("=" * 50)
    print(f"Config file: {config.config_path}")
    print(f"Theme: {config.get('app.theme')}")
    print(f"Downloads folder: {config.get('paths.downloads')}")
    print(f"Rate limiting enabled: {config.get('rate_limiting.enabled')}")
    print("=" * 50)

    # Test rate limit config
    rate_config = config.get_rate_limit_config('youtube')
    print(f"YouTube rate limit: {rate_config}")
    print("=" * 50)
