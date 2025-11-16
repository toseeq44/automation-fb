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
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging


class MethodLearningSystem:
    """
    Intelligent system that learns which extraction method works best
    for each creator and platform.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize learning system"""
        if cache_file is None:
            # Use data_files folder in root
            root = Path(__file__).parent.parent.parent
            data_folder = root / "data_files"
            data_folder.mkdir(parents=True, exist_ok=True)
            cache_file = data_folder / "creator_method_cache.json"

        self.cache_file = cache_file
        self.cache: Dict = self.load_cache()

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
        """Save learning cache to disk"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to save learning cache: {e}")

    def get_best_method(self, creator: str, platform: str) -> Optional[str]:
        """
        Get the best method for this creator based on past performance.
        Returns method name or None if creator is unknown.
        """
        creator_key = self._make_creator_key(creator, platform)

        if creator_key not in self.cache:
            return None

        return self.cache[creator_key].get('best_method')

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
                'total_extractions': 0,
                'first_seen': datetime.now().isoformat(),
                'last_extraction': None,
                'performance_history': {}
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
