"""
modules/link_grabber/intelligence.py
INTELLIGENT METHOD LEARNING SYSTEM

Features:
- Tracks method performance per creator
- Learns which method works best for each creator
- Auto-selects best method on next extraction
- Self-optimizing over time
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging


# Display-name → stable method_id migration map
_DISPLAY_TO_ID: Dict[str, str] = {
    "Method 0: yt-dlp primary (Dual API + Proxy + UA Rotation)": "ytdlp_primary",
    "Method 2: yt-dlp --get-url": "ytdlp_get_url",
    "Method 1: yt-dlp --dump-json (with dates)": "ytdlp_dump_json",
    "Method 3: yt-dlp with retries": "ytdlp_with_retry",
    "Method 6: gallery-dl": "gallery_dl",
    "Method 6b: Instagram GraphQL API (cookies)": "instagram_graphql",
    "Method 6b: Instagram Web API (cookies)": "instagram_graphql",
    "Method 5: Instaloader": "instaloader",
    "Method C: Facebook Page JSON (c_user+xs cookies -> video links)": "facebook_json",
    "Method C: Facebook Page JSON (c_user+xs cookies \u2192 video links)": "facebook_json",
    "Method B: Instagram Mobile API (sessionid -> direct JSON)": "instagram_mobile_api",
    "Method B: Instagram Mobile API (sessionid \u2192 direct JSON)": "instagram_mobile_api",
    "Method D: Attach Selenium to running Chrome (CDP port)": "selenium_cdp_attach",
    "Method A: Existing Browser Session (Chrome user-data-dir)": "selenium_profile",
    "Method A: Selenium (Chrome user-data-dir profile)": "selenium_profile",
    "Method 7: Playwright (Stealth + Proxy + Human Behavior)": "playwright",
    "Method 7: Playwright (ENHANCED: Stealth + Proxy + Human Behavior)": "playwright",
    "Method 8: Selenium Headless (Proxy + Cookies + Stealth)": "selenium_headless",
    "Method 8: Selenium Headless (ENHANCED: Proxy + Cookies + Stealth)": "selenium_headless",
    "Method 4: yt-dlp with user agent": "ytdlp_with_ua",
}


class MethodLearningSystem:
    """
    Intelligent system that learns which extraction method works best
    for each creator and platform.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize learning system"""
        if cache_file is None:
            try:
                from modules.config.paths import get_data_dir
                data_folder = get_data_dir()
            except ImportError:
                # Use data_files folder in root (fallback)
                root = Path(__file__).parent.parent.parent
                data_folder = root / "data_files"
            data_folder.mkdir(parents=True, exist_ok=True)
            cache_file = data_folder / "creator_method_cache.json"

        self.cache_file = cache_file
        self._save_lock = threading.Lock()
        self.cache: Dict = self.load_cache()
        self._migrate_cache_keys()

    def load_cache(self) -> Dict:
        """Load learning cache from disk"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load learning cache: {e}")

        return {}

    def save_cache(self):
        """Save learning cache to disk (thread-safe, atomic write)."""
        with self._save_lock:
            try:
                # Write to temp file first, then rename (atomic on same filesystem)
                fd, tmp_path = tempfile.mkstemp(
                    suffix=".tmp", dir=str(self.cache_file.parent)
                )
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as f:
                        json.dump(self.cache, f, indent=2, ensure_ascii=False)
                    # Atomic replace
                    os.replace(tmp_path, str(self.cache_file))
                except Exception:
                    # Clean up temp file on failure
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    raise
            except Exception as e:
                logging.error(f"Failed to save learning cache: {e}")

    @staticmethod
    def _migrate_key(key: str) -> str:
        """Map old display-name key to stable method_id if needed."""
        return _DISPLAY_TO_ID.get(key, key)

    def _migrate_cache_keys(self):
        """One-time migration: convert display-name keys to stable method_ids."""
        migrated = False
        for cache_key, entry in self.cache.items():
            if 'performance_history' in entry:
                old_history = entry['performance_history']
                new_history: Dict = {}
                for method_key, stats in old_history.items():
                    new_key = self._migrate_key(method_key)
                    if new_key != method_key:
                        migrated = True
                    if new_key in new_history:
                        # Merge stats if both old and new key exist
                        existing = new_history[new_key]
                        existing['success_count'] += stats.get('success_count', 0)
                        existing['fail_count'] += stats.get('fail_count', 0)
                        existing['total_links'] += stats.get('total_links', 0)
                        existing['total_time'] += stats.get('total_time', 0)
                        if existing['success_count'] > 0:
                            existing['avg_links'] = existing['total_links'] / existing['success_count']
                            existing['avg_time'] = existing['total_time'] / existing['success_count']
                        total = existing['success_count'] + existing['fail_count']
                        existing['success_rate'] = (existing['success_count'] / total * 100) if total > 0 else 0
                        existing['score'] = self._calculate_score(existing)
                    else:
                        new_history[new_key] = stats
                entry['performance_history'] = new_history
            if 'best_method' in entry and entry['best_method']:
                old_best = entry['best_method']
                new_best = self._migrate_key(old_best)
                if new_best != old_best:
                    migrated = True
                entry['best_method'] = new_best

            # Also migrate download_performance_history if present
            if 'download_performance_history' in entry:
                old_dl = entry['download_performance_history']
                new_dl: Dict = {}
                for method_key, stats in old_dl.items():
                    new_key = self._migrate_key(method_key)
                    if new_key != method_key:
                        migrated = True
                    new_dl[new_key] = stats
                entry['download_performance_history'] = new_dl
            if 'best_download_method' in entry and entry['best_download_method']:
                old_dl_best = entry['best_download_method']
                new_dl_best = self._migrate_key(old_dl_best)
                if new_dl_best != old_dl_best:
                    migrated = True
                entry['best_download_method'] = new_dl_best

        if migrated:
            logging.info("Migrated learning cache keys from display names to stable method IDs")
            self.save_cache()

    def get_best_method(self, creator: str, platform: str) -> Optional[str]:
        """
        Get the best method for this creator based on past performance.
        Returns method name or None if creator is unknown.
        """
        creator_key = self._make_creator_key(creator, platform)

        if creator_key not in self.cache:
            return None

        return self.cache[creator_key].get('best_method')

    def get_best_tab(self, creator: str, platform: str) -> Optional[str]:
        """Get best-performing content tab for a creator/platform."""
        creator_key = self._make_creator_key(creator, platform)
        if creator_key not in self.cache:
            return None
        return self.cache[creator_key].get('best_tab')

    def get_method_order(self, creator: str, platform: str) -> List[str]:
        """
        Get methods ordered by performance for this creator.
        Returns list of method names in priority order.
        """
        creator_key = self._make_creator_key(creator, platform)

        if creator_key not in self.cache:
            return []

        # Get all methods with performance data
        perf_history = self.cache[creator_key].get('performance_history', {})

        if not perf_history:
            return []

        # Calculate scores and sort
        method_scores = []
        for method_name, stats in perf_history.items():
            score = self._calculate_score(stats)
            if score > 0:  # Only include methods with successful extractions
                method_scores.append((method_name, score))

        # Sort by score (highest first)
        method_scores.sort(key=lambda x: x[1], reverse=True)

        return [method_name for method_name, _ in method_scores]

    def record_performance(
        self,
        creator: str,
        platform: str,
        method: str,
        success: bool,
        links_count: int = 0,
        time_taken: float = 0.0,
        error_msg: str = ""
    ):
        """
        Record performance of a method for a creator.

        Args:
            creator: Creator name (e.g., "MrBeast")
            platform: Platform name (e.g., "youtube")
            method: Method name (e.g., "Method 1: yt-dlp --get-url")
            success: Whether extraction was successful
            links_count: Number of links extracted
            time_taken: Time taken in seconds
            error_msg: Error message if failed
        """
        creator_key = self._make_creator_key(creator, platform)

        # Initialize creator entry if not exists
        if creator_key not in self.cache:
            self.cache[creator_key] = {
                'creator': creator,
                'platform': platform,
                'best_method': None,
                'best_tab': None,
                'total_extractions': 0,
                'first_seen': datetime.now().isoformat(),
                'last_extraction': None,
                'performance_history': {},
                'tab_history': {},
            }

        # Update extraction count and timestamp
        self.cache[creator_key]['total_extractions'] += 1
        self.cache[creator_key]['last_extraction'] = datetime.now().isoformat()

        # Initialize method stats if not exists
        if method not in self.cache[creator_key]['performance_history']:
            self.cache[creator_key]['performance_history'][method] = {
                'success_count': 0,
                'fail_count': 0,
                'total_links': 0,
                'total_time': 0.0,
                'avg_links': 0.0,
                'avg_time': 0.0,
                'success_rate': 0.0,
                'score': 0.0,
                'last_error': None,
                'last_success': None
            }

        stats = self.cache[creator_key]['performance_history'][method]

        # Update stats
        if success:
            stats['success_count'] += 1
            stats['total_links'] += links_count
            stats['total_time'] += time_taken
            stats['last_success'] = datetime.now().isoformat()

            # Calculate averages
            stats['avg_links'] = stats['total_links'] / stats['success_count']
            stats['avg_time'] = stats['total_time'] / stats['success_count']
        else:
            stats['fail_count'] += 1
            stats['last_error'] = error_msg[:200] if error_msg else "Unknown error"

        # Calculate success rate
        total_attempts = stats['success_count'] + stats['fail_count']
        stats['success_rate'] = (stats['success_count'] / total_attempts * 100) if total_attempts > 0 else 0

        # Calculate performance score
        stats['score'] = self._calculate_score(stats)

        # Update best method for this creator
        self._update_best_method(creator_key)

        # Save cache
        self.save_cache()

    def record_best_tab(self, creator: str, platform: str, tab: str, available_tabs: List[str]):
        """Record which content tab worked best for a creator."""
        creator_key = self._make_creator_key(creator, platform)
        tab_value = (tab or "").strip().lower()
        if not tab_value:
            return

        if creator_key not in self.cache:
            self.cache[creator_key] = {
                'creator': creator,
                'platform': platform,
                'best_method': None,
                'best_tab': None,
                'total_extractions': 0,
                'first_seen': datetime.now().isoformat(),
                'last_extraction': datetime.now().isoformat(),
                'performance_history': {},
                'tab_history': {},
            }

        creator_entry = self.cache[creator_key]
        tab_history = creator_entry.setdefault('tab_history', {})

        for tab_name in available_tabs or []:
            normalized = str(tab_name).strip().lower()
            if not normalized:
                continue
            tab_history.setdefault(
                normalized,
                {
                    'success_count': 0,
                    'last_success': None,
                },
            )

        tab_stats = tab_history.setdefault(
            tab_value,
            {
                'success_count': 0,
                'last_success': None,
            },
        )
        tab_stats['success_count'] += 1
        tab_stats['last_success'] = datetime.now().isoformat()

        best_tab = tab_value
        best_score = tab_stats['success_count']
        for tab_name, stats in tab_history.items():
            score = int(stats.get('success_count', 0) or 0)
            if score > best_score:
                best_score = score
                best_tab = tab_name

        creator_entry['best_tab'] = best_tab
        self.save_cache()

    def _calculate_score(self, stats: Dict) -> float:
        """
        Calculate performance score for a method.

        Score formula:
        - Success rate (0-100): Higher is better
        - Avg time penalty: Faster is better
        - Avg links bonus: More links is better

        Score = (success_rate * 2) - (avg_time / 10) + (avg_links / 100)

        Example:
        - 100% success, 10s avg, 250 links avg = 200 - 1 + 2.5 = 201.5
        - 80% success, 30s avg, 180 links avg = 160 - 3 + 1.8 = 158.8
        """
        if stats['success_count'] == 0:
            return 0.0

        success_component = stats['success_rate'] * 2  # 0-200 points
        time_penalty = stats['avg_time'] / 10  # Penalty for slow methods
        links_bonus = stats['avg_links'] / 100  # Bonus for getting more links

        score = success_component - time_penalty + links_bonus

        return max(0.0, score)  # Never negative

    def _update_best_method(self, creator_key: str):
        """Update which method is best for this creator"""
        if creator_key not in self.cache:
            return

        perf_history = self.cache[creator_key].get('performance_history', {})

        if not perf_history:
            return

        # Find method with highest score
        best_method = None
        best_score = -1

        for method_name, stats in perf_history.items():
            if stats['success_count'] == 0:
                continue  # Skip methods that never succeeded

            score = stats['score']

            if score > best_score:
                best_score = score
                best_method = method_name

        self.cache[creator_key]['best_method'] = best_method

    # ------------------------------------------------------------------
    # Download method learning (strategy memory for video_downloader)
    # ------------------------------------------------------------------
    def record_download_performance(
        self,
        creator: str,
        platform: str,
        method_id: str,
        success: bool,
        time_taken: float = 0.0,
        error_msg: str = ""
    ):
        """Record download method performance for strategy memory."""
        creator_key = self._make_creator_key(creator, platform)

        if creator_key not in self.cache:
            self.cache[creator_key] = {
                'creator': creator,
                'platform': platform,
                'best_method': None,
                'best_tab': None,
                'total_extractions': 0,
                'first_seen': datetime.now().isoformat(),
                'last_extraction': None,
                'performance_history': {},
                'tab_history': {},
            }

        entry = self.cache[creator_key]
        dl_history = entry.setdefault('download_performance_history', {})

        if method_id not in dl_history:
            dl_history[method_id] = {
                'success_count': 0,
                'fail_count': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'success_rate': 0.0,
                'score': 0.0,
                'last_error': None,
            }

        stats = dl_history[method_id]
        if success:
            stats['success_count'] += 1
            stats['total_time'] += time_taken
            if stats['success_count'] > 0:
                stats['avg_time'] = stats['total_time'] / stats['success_count']
        else:
            stats['fail_count'] += 1
            stats['last_error'] = (error_msg[:200]) if error_msg else None

        total = stats['success_count'] + stats['fail_count']
        stats['success_rate'] = (stats['success_count'] / total * 100) if total > 0 else 0
        stats['score'] = max(0.0, stats['success_rate'] * 2 - stats['avg_time'] / 10)

        # Update best download method
        best_dl = None
        best_dl_score = -1
        for mid, s in dl_history.items():
            if s['success_count'] > 0 and s['score'] > best_dl_score:
                best_dl_score = s['score']
                best_dl = mid
        entry['best_download_method'] = best_dl

        self.save_cache()

    def get_best_download_method(self, creator: str, platform: str) -> Optional[str]:
        """Get the best download method_id for a creator/platform."""
        creator_key = self._make_creator_key(creator, platform)
        entry = self.cache.get(creator_key)
        if not entry:
            return None
        return entry.get('best_download_method')

    def get_download_method_order(self, creator: str, platform: str) -> List[str]:
        """Get download methods ordered by score for a creator/platform."""
        creator_key = self._make_creator_key(creator, platform)
        entry = self.cache.get(creator_key)
        if not entry:
            return []
        dl_history = entry.get('download_performance_history', {})
        scored = [
            (mid, s['score'])
            for mid, s in dl_history.items()
            if s.get('success_count', 0) > 0
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [mid for mid, _ in scored]

    def _make_creator_key(self, creator: str, platform: str) -> str:
        """Create unique key for creator+platform"""
        # Normalize creator name
        creator_clean = creator.lower().strip().lstrip('@')
        platform_clean = platform.lower().strip()

        return f"{platform_clean}:{creator_clean}"

    def get_creator_stats(self, creator: str, platform: str) -> Optional[Dict]:
        """Get all stats for a creator"""
        creator_key = self._make_creator_key(creator, platform)
        return self.cache.get(creator_key)

    def get_summary(self) -> Dict:
        """Get summary of learning system"""
        total_creators = len(self.cache)
        total_extractions = sum(c['total_extractions'] for c in self.cache.values())

        platforms = {}
        for creator_data in self.cache.values():
            platform = creator_data['platform']
            platforms[platform] = platforms.get(platform, 0) + 1

        return {
            'total_creators': total_creators,
            'total_extractions': total_extractions,
            'platforms': platforms,
            'cache_file': str(self.cache_file)
        }

    def format_creator_report(self, creator: str, platform: str) -> str:
        """Format a readable report for a creator's performance"""
        stats = self.get_creator_stats(creator, platform)

        if not stats:
            return f"No learning data for @{creator} ({platform})"

        report = []
        report.append(f"📊 Learning Data for @{stats['creator']} ({stats['platform'].upper()})")
        report.append("=" * 60)
        report.append(f"Total Extractions: {stats['total_extractions']}")
        report.append(f"First Seen: {stats['first_seen'][:10]}")
        report.append(f"Last Extraction: {stats.get('last_extraction', 'Never')[:10]}")
        report.append(f"Best Method: {stats['best_method'] or 'Not determined yet'}")
        report.append("")
        report.append("Method Performance:")
        report.append("-" * 60)

        # Sort methods by score
        perf = stats.get('performance_history', {})
        sorted_methods = sorted(
            perf.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )

        for method_name, method_stats in sorted_methods:
            if method_stats['success_count'] == 0 and method_stats['fail_count'] == 0:
                continue

            report.append(f"\n{method_name}:")
            report.append(f"  Success Rate: {method_stats['success_rate']:.1f}% "
                         f"({method_stats['success_count']}✅ / {method_stats['fail_count']}❌)")

            if method_stats['success_count'] > 0:
                report.append(f"  Avg Links: {method_stats['avg_links']:.0f}")
                report.append(f"  Avg Time: {method_stats['avg_time']:.1f}s")
                report.append(f"  Performance Score: {method_stats['score']:.1f}")

        return "\n".join(report)


# Global instance
_learning_system = None


def get_learning_system() -> MethodLearningSystem:
    """Get global learning system instance"""
    global _learning_system

    if _learning_system is None:
        _learning_system = MethodLearningSystem()

    return _learning_system
