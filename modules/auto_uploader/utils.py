"""
Facebook Auto Uploader - Utility Functions
Configuration, JSON tracking, and helper functions
"""

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


def load_config(config_path: Path) -> Dict:
    """
    Load configuration from JSON file

    Args:
        config_path: Path to settings.json

    Returns:
        Configuration dictionary
    """
    default_config = get_default_config(base_dir=config_path.parent.parent)

    if not config_path.exists():
        logging.warning(f"Config not found: {config_path}")
        return default_config

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logging.info(f"Configuration loaded from {config_path}")
        return merge_dicts(default_config, config)
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        return default_config


def get_default_config(base_dir: Optional[Path] = None) -> Dict:
    """Get default configuration"""
    if base_dir is None:
        base_dir = Path(__file__).parent

    creators_root = (base_dir / 'creators').resolve()
    shortcuts_root = (base_dir / 'creator_shortcuts').resolve()
    history_file = (base_dir / 'data' / 'history.json').resolve()

    return {
        'automation': {
            'mode': 'free_automation',
            'setup_completed': False,
            'paths': {
                'creators_root': str(creators_root),
                'shortcuts_root': str(shortcuts_root),
                'history_file': str(history_file)
            },
            'credentials': {
                'gologin': {},
                'ix': {},
                'vpn': {},
                'free_automation': {}
            }
        },
        'browsers': {
            'gologin': {
                'exe_path': 'C:\\Users\\{user}\\AppData\\Local\\Programs\\GoLogin\\GoLogin.exe',
                'desktop_shortcut': '~/Desktop/GoLogin.lnk',
                'debug_port': 9222,
                'startup_wait': 15,
                'profile_startup_wait': 10,
                'enabled': True
            },
            'ix': {
                'exe_path': 'C:\\Users\\{user}\\AppData\\Local\\Programs\\Incogniton\\Incogniton.exe',
                'desktop_shortcut': '~/Desktop/Incogniton.lnk',
                'debug_port': 9223,
                'startup_wait': 15,
                'profile_startup_wait': 10,
                'enabled': True
            }
        },
        'upload_settings': {
            'wait_after_upload': 30,
            'wait_between_videos': 120,
            'retry_attempts': 3,
            'retry_delay': 60,
            'delete_after_upload': True,
            'skip_uploaded': True,
            'upload_timeout': 600
        },
        'facebook': {
            'upload_url': 'https://www.facebook.com/',
            'video_upload_url': 'https://www.facebook.com/video/upload',
            'wait_for_login': 20,
            'wait_for_video_processing': 30
        }
    }


def save_config(config_path: Path, config: Dict):
    """Persist configuration to disk"""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logging.debug(f"Configuration saved to {config_path}")
    except Exception as exc:
        logging.error(f"Failed to save config: {exc}")


def merge_dicts(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries"""
    result = deepcopy(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def load_tracking_data(tracking_path: Path) -> Dict:
    """
    Load upload tracking data from JSON file

    Args:
        tracking_path: Path to upload_tracking.json

    Returns:
        Tracking data dictionary
    """
    if not tracking_path.exists():
        logging.info("Creating new tracking file")
        return get_empty_tracking()

    try:
        with open(tracking_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.info(f"Tracking data loaded from {tracking_path}")
        return data
    except Exception as e:
        logging.error(f"Failed to load tracking data: {e}")
        return get_empty_tracking()


def get_empty_tracking() -> Dict:
    """Get empty tracking structure"""
    return {
        'upload_history': [],
        'failed_uploads': [],
        'browser_accounts': {},
        'last_updated': datetime.now().isoformat()
    }


def save_tracking_data(tracking_path: Path, data: Dict):
    """
    Save tracking data to JSON file

    Args:
        tracking_path: Path to upload_tracking.json
        data: Tracking data to save
    """
    try:
        # Ensure directory exists
        tracking_path.parent.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        data['last_updated'] = datetime.now().isoformat()

        # Save with pretty formatting
        with open(tracking_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logging.debug(f"Tracking data saved to {tracking_path}")
    except Exception as e:
        logging.error(f"Failed to save tracking data: {e}")


def record_upload(tracking_data: Dict, creator_name: str, video_file: str,
                 status: str, profile_name: str = '', error_message: str = ''):
    """
    Record upload attempt in tracking data

    Args:
        tracking_data: Tracking data dictionary
        creator_name: Creator name
        video_file: Video filename
        status: Upload status (completed/failed)
        profile_name: Facebook profile name
        error_message: Error message if failed
    """
    entry = {
        'creator_name': creator_name,
        'video_file': video_file,
        'profile_name': profile_name,
        'status': status,
        'timestamp': datetime.now().isoformat(),
        'error_message': error_message
    }

    if status == 'completed':
        tracking_data['upload_history'].append(entry)
    elif status == 'failed':
        tracking_data['failed_uploads'].append(entry)


def is_video_uploaded(tracking_data: Dict, creator_name: str, video_file: str) -> bool:
    """
    Check if video was already uploaded

    Args:
        tracking_data: Tracking data dictionary
        creator_name: Creator name
        video_file: Video filename

    Returns:
        True if uploaded
    """
    history = tracking_data.get('upload_history', [])

    for entry in history:
        if (entry.get('creator_name') == creator_name and
            entry.get('video_file') == video_file and
            entry.get('status') == 'completed'):
            return True

    return False


def parse_login_data(file_path: Path) -> List[Dict[str, str]]:
    """
    Parse login_data.txt file

    Supports two formats:
    1. Pipe-separated (legacy): profile_name|facebook_email|facebook_password|page_name|page_id|browser_type
    2. Key-value (new):
       browser: ix
       email: user@example.com
       password: pass123
       page_name: My Page
       page_id: 12345
       ---

    Args:
        file_path: Path to login_data.txt

    Returns:
        List of login data dictionaries
    """
    login_entries = []

    if not file_path.exists():
        logging.warning(f"Login data not found: {file_path}")
        return login_entries

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Detect format
        if '|' in content:
            # Pipe-separated format
            login_entries = _parse_pipe_format(content, file_path)
        else:
            # Key-value format
            login_entries = _parse_key_value_format(content, file_path)

        logging.info(f"Loaded {len(login_entries)} login entries from {file_path.name}")

    except Exception as e:
        logging.error(f"Error parsing login data: {e}")

    return login_entries


def _parse_pipe_format(content: str, file_path: Path) -> List[Dict[str, str]]:
    """Parse pipe-separated format"""
    login_entries = []

    for line_num, line in enumerate(content.splitlines(), 1):
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue

        # Parse line
        parts = line.split('|')

        if len(parts) not in (5, 6):
            logging.warning(f"Invalid pipe format at line {line_num}: {line}")
            continue

        login_entries.append({
            'profile_name': parts[0].strip(),
            'facebook_email': parts[1].strip(),
            'facebook_password': parts[2].strip(),
            'page_name': parts[3].strip(),
            'page_id': parts[4].strip(),
            'browser_type': parts[5].strip().lower() if len(parts) == 6 else ''
        })

    return login_entries


def _parse_key_value_format(content: str, file_path: Path) -> List[Dict[str, str]]:
    """Parse key-value format (multiple entries separated by ---)"""
    login_entries = []

    # Split by --- separator for multiple entries
    entry_blocks = content.split('---')

    for block_num, block in enumerate(entry_blocks, 1):
        entry = {
            'profile_name': '',
            'facebook_email': '',
            'facebook_password': '',
            'page_name': '',
            'page_id': '',
            'browser_type': ''
        }

        for line in block.splitlines():
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse key:value
            if ':' not in line:
                continue

            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()

            # Map keys to entry fields
            if key in ('browser', 'browser_type'):
                entry['browser_type'] = value.lower()
            elif key in ('email', 'facebook_email'):
                entry['facebook_email'] = value
            elif key in ('password', 'facebook_password'):
                entry['facebook_password'] = value
            elif key in ('page', 'page_name'):
                entry['page_name'] = value
            elif key in ('page_id', 'pageid'):
                entry['page_id'] = value
            elif key in ('profile', 'profile_name'):
                entry['profile_name'] = value

        # Set defaults for missing fields
        # Use email as default page_name if not provided
        if not entry['page_name'] and entry['facebook_email']:
            entry['page_name'] = entry['facebook_email'].split('@')[0]  # Use email username

        # Use page_name as profile_name if not set
        if not entry['profile_name'] and entry['page_name']:
            entry['profile_name'] = entry['page_name']

        # Default page_id if not provided
        if not entry['page_id']:
            entry['page_id'] = '0'

        # Only add if we have minimum required fields (email and password)
        if entry['facebook_email'] and entry['facebook_password']:
            login_entries.append(entry)
            logging.debug(f"Loaded entry: {entry['page_name']} ({entry['facebook_email']})")
        elif entry['facebook_email'] or entry['facebook_password']:
            logging.warning(f"Incomplete entry in block {block_num}, skipping. Need: email, password")

    return login_entries


def get_video_files(directory: Path, extensions: List[str] = None) -> List[Path]:
    """
    Get all video files from directory

    Args:
        directory: Directory to search
        extensions: Video extensions to search for

    Returns:
        List of video file paths
    """
    if extensions is None:
        extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']

    if not directory.exists():
        return []

    video_files = []

    for ext in extensions:
        video_files.extend(directory.glob(f'*{ext}'))
        video_files.extend(directory.glob(f'*{ext.upper()}'))

    return sorted(video_files, key=lambda x: x.name)


def expand_path(path_value: Optional[str], fallback: Optional[Path] = None) -> Path:
    """Resolve a user provided path string to absolute Path"""
    if path_value:
        expanded = Path(os.path.expandvars(os.path.expanduser(path_value))).resolve()
        return expanded
    return fallback.resolve() if fallback else Path.cwd()


def load_video_metadata(creator_path: Path, video_name: str) -> Dict:
    """
    Load metadata for a video from videos_description.json

    Args:
        creator_path: Path to creator folder
        video_name: Video filename

    Returns:
        Metadata dictionary
    """
    metadata_file = creator_path / 'videos_description.json'

    if not metadata_file.exists():
        return {}

    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            all_metadata = json.load(f)

        return all_metadata.get(video_name, {})

    except Exception as e:
        logging.error(f"Error loading metadata: {e}")
        return {}


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0

    return f"{size_bytes:.2f} PB"


def safe_filename(filename: str) -> str:
    """
    Remove invalid characters from filename

    Args:
        filename: Original filename

    Returns:
        Safe filename
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def get_config_value(config: Dict, key_path: str, default=None):
    """
    Get configuration value using dot notation

    Args:
        config: Configuration dictionary
        key_path: Dot-separated path (e.g., 'browsers.gologin.debug_port')
        default: Default value if not found

    Returns:
        Configuration value or default
    """
    keys = key_path.split('.')
    value = config

    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default
