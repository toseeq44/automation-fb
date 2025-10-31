"""
Facebook Upload Bot - Utility Functions
Contains configuration management, database operations, and helper functions
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any


class ConfigLoader:
    """Handles loading and accessing configuration settings"""

    def __init__(self, config_path: str):
        """
        Initialize config loader

        Args:
            config_path: Path to settings.json file
        """
        self.config_path = Path(config_path)
        self.config_data = {}
        self.load_config()

    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Config file not found: {self.config_path}")

            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)

            logging.info(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            raise

    def get(self, key_path: str, default=None):
        """
        Get configuration value using dot notation

        Args:
            key_path: Dot-separated path (e.g., 'browsers.gologin.exe_path')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config_data

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def reload(self):
        """Reload configuration from file"""
        self.load_config()


class DatabaseManager:
    """Manages SQLite database operations for upload tracking"""

    def __init__(self, db_path: str):
        """
        Initialize database manager

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.connection = None
        self.initialize_database()

    def initialize_database(self):
        """Create database tables if they don't exist"""
        try:
            # Ensure config directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Connect to database
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row  # Enable dict-like access

            cursor = self.connection.cursor()

            # Create browser_accounts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS browser_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    browser_type TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    last_used TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    UNIQUE(browser_type, account_name)
                )
            ''')

            # Create profiles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    browser_account_id INTEGER,
                    profile_name TEXT NOT NULL,
                    facebook_email TEXT,
                    facebook_page_id TEXT,
                    page_name TEXT,
                    creator_name TEXT,
                    last_login TIMESTAMP,
                    FOREIGN KEY (browser_account_id) REFERENCES browser_accounts(id),
                    UNIQUE(browser_account_id, profile_name)
                )
            ''')

            # Create upload_queue table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS upload_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_name TEXT NOT NULL,
                    video_file TEXT NOT NULL,
                    profile_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    uploaded_at TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id)
                )
            ''')

            # Create upload_history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS upload_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_file TEXT NOT NULL,
                    creator_name TEXT NOT NULL,
                    profile_id INTEGER,
                    page_name TEXT,
                    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_size INTEGER,
                    deleted_after_upload BOOLEAN,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id)
                )
            ''')

            self.connection.commit()
            logging.info(f"Database initialized: {self.db_path}")

        except Exception as e:
            logging.error(f"Database initialization failed: {e}")
            raise

    def get_or_create_browser_account(self, browser_type: str, account_name: str) -> int:
        """
        Get or create browser account entry

        Args:
            browser_type: Type of browser (GoLogin, IX)
            account_name: Account identifier

        Returns:
            Browser account ID
        """
        cursor = self.connection.cursor()

        # Try to get existing
        cursor.execute('''
            SELECT id FROM browser_accounts
            WHERE browser_type = ? AND account_name = ?
        ''', (browser_type, account_name))

        result = cursor.fetchone()

        if result:
            return result['id']

        # Create new
        cursor.execute('''
            INSERT INTO browser_accounts (browser_type, account_name, last_used)
            VALUES (?, ?, ?)
        ''', (browser_type, account_name, datetime.now()))

        self.connection.commit()
        return cursor.lastrowid

    def get_or_create_profile(self, browser_account_id: int, profile_data: Dict) -> int:
        """
        Get or create profile entry

        Args:
            browser_account_id: Browser account ID
            profile_data: Profile information dict

        Returns:
            Profile ID
        """
        cursor = self.connection.cursor()

        # Try to get existing
        cursor.execute('''
            SELECT id FROM profiles
            WHERE browser_account_id = ? AND profile_name = ?
        ''', (browser_account_id, profile_data.get('profile_name')))

        result = cursor.fetchone()

        if result:
            # Update existing profile
            cursor.execute('''
                UPDATE profiles
                SET facebook_email = ?, facebook_page_id = ?,
                    page_name = ?, creator_name = ?
                WHERE id = ?
            ''', (
                profile_data.get('facebook_email'),
                profile_data.get('page_id'),
                profile_data.get('page_name'),
                profile_data.get('creator_name'),
                result['id']
            ))
            self.connection.commit()
            return result['id']

        # Create new
        cursor.execute('''
            INSERT INTO profiles
            (browser_account_id, profile_name, facebook_email, facebook_page_id,
             page_name, creator_name, last_login)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            browser_account_id,
            profile_data.get('profile_name'),
            profile_data.get('facebook_email'),
            profile_data.get('page_id'),
            profile_data.get('page_name'),
            profile_data.get('creator_name'),
            datetime.now()
        ))

        self.connection.commit()
        return cursor.lastrowid

    def record_upload(self, creator_name: str, video_file: str, status: str,
                     profile_id: Optional[int] = None, error_message: Optional[str] = None):
        """
        Record upload attempt

        Args:
            creator_name: Creator folder name
            video_file: Video filename
            status: Upload status (pending, uploading, completed, failed)
            profile_id: Profile ID
            error_message: Error message if failed
        """
        cursor = self.connection.cursor()

        cursor.execute('''
            INSERT INTO upload_queue
            (creator_name, video_file, profile_id, status, error_message, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            creator_name,
            video_file,
            profile_id,
            status,
            error_message,
            datetime.now() if status == 'completed' else None
        ))

        self.connection.commit()

    def add_to_history(self, video_file: str, creator_name: str, profile_id: int,
                      page_name: str, file_size: int, deleted: bool):
        """
        Add successful upload to history

        Args:
            video_file: Video filename
            creator_name: Creator folder name
            profile_id: Profile ID
            page_name: Facebook page name
            file_size: File size in bytes
            deleted: Whether file was deleted after upload
        """
        cursor = self.connection.cursor()

        cursor.execute('''
            INSERT INTO upload_history
            (video_file, creator_name, profile_id, page_name, file_size, deleted_after_upload)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (video_file, creator_name, profile_id, page_name, file_size, deleted))

        self.connection.commit()

    def get_pending_uploads(self) -> List[Dict]:
        """Get all pending uploads from queue"""
        cursor = self.connection.cursor()

        cursor.execute('''
            SELECT * FROM upload_queue
            WHERE status = 'pending'
            ORDER BY created_at ASC
        ''')

        return [dict(row) for row in cursor.fetchall()]

    def is_video_uploaded(self, creator_name: str, video_file: str) -> bool:
        """
        Check if video has been uploaded before

        Args:
            creator_name: Creator folder name
            video_file: Video filename

        Returns:
            True if video was previously uploaded
        """
        cursor = self.connection.cursor()

        cursor.execute('''
            SELECT COUNT(*) as count FROM upload_history
            WHERE creator_name = ? AND video_file = ?
        ''', (creator_name, video_file))

        result = cursor.fetchone()
        return result['count'] > 0

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logging.info("Database connection closed")


def parse_login_data(file_path: Path) -> List[Dict[str, str]]:
    """
    Parse login_data.txt file

    Format: profile_name|facebook_email|facebook_password|page_name|page_id

    Args:
        file_path: Path to login_data.txt

    Returns:
        List of login data dictionaries
    """
    login_entries = []

    if not file_path.exists():
        logging.warning(f"Login data file not found: {file_path}")
        return login_entries

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Parse line
                parts = line.split('|')

                if len(parts) != 5:
                    logging.warning(f"Invalid format in {file_path} line {line_num}: {line}")
                    continue

                login_entries.append({
                    'profile_name': parts[0].strip(),
                    'facebook_email': parts[1].strip(),
                    'facebook_password': parts[2].strip(),
                    'page_name': parts[3].strip(),
                    'page_id': parts[4].strip()
                })

        logging.info(f"Loaded {len(login_entries)} login entries from {file_path}")

    except Exception as e:
        logging.error(f"Error parsing login data: {e}")

    return login_entries


def get_video_files(directory: Path, extensions: List[str] = None) -> List[Path]:
    """
    Get all video files from directory

    Args:
        directory: Directory to search
        extensions: List of video extensions (default: common video formats)

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


def ensure_directory(path: Path) -> Path:
    """
    Ensure directory exists, create if not

    Args:
        path: Directory path

    Returns:
        Path object
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


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
