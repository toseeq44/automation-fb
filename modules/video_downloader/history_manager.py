"""
Centralized history management for video downloader.
Tracks downloads, timestamps, statistics per creator.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional


class HistoryManager:
    """Manages download history with history.json"""

    def __init__(self, root_folder: Path):
        """
        Args:
            root_folder: Root folder containing creator subfolders
        """
        self.root_folder = Path(root_folder)
        self.history_file = self.root_folder / "history.json"
        self.history_data = self._load_history()

    def _load_history(self) -> Dict:
        """Load history.json or create empty structure"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_history(self):
        """Save history.json atomically"""
        try:
            # Ensure root folder exists
            self.root_folder.mkdir(parents=True, exist_ok=True)

            # Write atomically using temp file
            temp_file = self.history_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.history_data, f, indent=2, ensure_ascii=False)

            # Atomic replace
            temp_file.replace(self.history_file)
        except Exception as e:
            print(f"⚠️ Failed to save history: {e}")

    def ensure_exists(self):
        """Ensure history.json exists (create empty if needed)"""
        if not self.history_file.exists():
            self._save_history()

    def should_skip_creator(self, creator_name: str, window_hours: int = 24) -> bool:
        """
        Check if creator was downloaded within time window

        Args:
            creator_name: Name of creator folder
            window_hours: Time window in hours (default 24)

        Returns:
            True if should skip (recently downloaded)
        """
        if creator_name not in self.history_data:
            return False

        creator_info = self.history_data[creator_name]
        last_download = creator_info.get('last_download')

        if not last_download:
            return False

        try:
            last_time = datetime.fromisoformat(last_download)
            now = datetime.now()
            elapsed = now - last_time

            return elapsed < timedelta(hours=window_hours)
        except Exception:
            return False

    def get_creator_info(self, creator_name: str) -> Dict:
        """Get creator statistics"""
        return self.history_data.get(creator_name, {
            'total_downloaded': 0,
            'last_batch_count': 0,
            'total_failed': 0,
            'last_download': None,
            'last_status': 'never'
        })

    def update_creator(
        self,
        creator_name: str,
        downloaded_count: int = 0,
        failed_count: int = 0,
        status: str = 'success'
    ):
        """
        Update creator statistics after download session

        Args:
            creator_name: Name of creator
            downloaded_count: Number of videos successfully downloaded
            failed_count: Number of failed downloads
            status: Status of session ('success', 'partial', 'failed')
        """
        if creator_name not in self.history_data:
            self.history_data[creator_name] = {
                'total_downloaded': 0,
                'last_batch_count': 0,
                'total_failed': 0,
                'last_download': None,
                'last_status': 'never'
            }

        creator = self.history_data[creator_name]
        creator['total_downloaded'] = creator.get('total_downloaded', 0) + downloaded_count
        creator['last_batch_count'] = downloaded_count
        creator['total_failed'] = creator.get('total_failed', 0) + failed_count
        creator['last_download'] = datetime.now().isoformat()
        creator['last_status'] = status

        self._save_history()

    def get_all_creators(self) -> Dict[str, Dict]:
        """Get all creator history"""
        return self.history_data.copy()

    def clear_creator(self, creator_name: str):
        """Remove creator from history"""
        if creator_name in self.history_data:
            del self.history_data[creator_name]
            self._save_history()

    def clear_all(self):
        """Clear entire history"""
        self.history_data = {}
        self._save_history()

    def get_summary(self) -> str:
        """Get formatted summary of all downloads"""
        if not self.history_data:
            return "No download history yet."

        total_creators = len(self.history_data)
        total_videos = sum(c.get('total_downloaded', 0) for c in self.history_data.values())
        total_failed = sum(c.get('total_failed', 0) for c in self.history_data.values())

        summary = f"📊 Download History Summary\n"
        summary += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        summary += f"👥 Total Creators: {total_creators}\n"
        summary += f"✅ Total Videos Downloaded: {total_videos}\n"
        summary += f"❌ Total Failed: {total_failed}\n"
        summary += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        summary += "Recent Activity:\n"
        # Sort by last download time
        sorted_creators = sorted(
            self.history_data.items(),
            key=lambda x: x[1].get('last_download', ''),
            reverse=True
        )

        for creator, info in sorted_creators[:10]:  # Show last 10
            last_time = info.get('last_download', 'Never')
            if last_time and last_time != 'Never':
                try:
                    dt = datetime.fromisoformat(last_time)
                    last_time = dt.strftime('%Y-%m-%d %H:%M')
                except Exception:
                    pass

            summary += f"  • {creator}: {info.get('total_downloaded', 0)} videos "
            summary += f"({last_time})\n"

        return summary
