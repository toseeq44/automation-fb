#!/usr/bin/env python3
"""
Test Script for Auto Uploader Bookmark Counter Fix
Demonstrates correct per-bookmark tracking and deduplication
"""

import os
import sys
import tempfile
import json
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))

# Direct import to avoid dependency issues
import importlib.util
spec = importlib.util.spec_from_file_location(
    "state_manager",
    "modules/auto_uploader/approaches/ixbrowser/core/state_manager.py"
)
state_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state_manager_module)
StateManager = state_manager_module.StateManager


def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_single_bookmark_multiple_videos():
    """Test: Multiple videos to same bookmark should count as 1 bookmark"""
    print_header("TEST 1: Multiple Videos to Same Bookmark")

    # Create temporary directory
    temp_dir = tempfile.mkdtemp()

    try:
        # Initialize state manager
        state_manager = StateManager(data_dir=temp_dir)

        print("📁 Uploading to Bookmark: 'CreatorA'")
        print("-" * 70)

        # Simulate uploading 3 videos to same bookmark
        for i in range(1, 4):
            state_manager.increment_daily_bookmarks(count=1, bookmark_name="CreatorA")
            daily_stats = state_manager.get_daily_stats()
            print(f"Video {i} uploaded → Unique Bookmarks: {daily_stats['bookmarks_uploaded']}, "
                  f"Total Videos: {daily_stats['videos_uploaded']}")

        print("\n" + "-" * 70)
        daily_stats = state_manager.get_daily_stats()

        # Verify results
        assert daily_stats['bookmarks_uploaded'] == 1, "Should count as 1 unique bookmark"
        assert daily_stats['videos_uploaded'] == 3, "Should count 3 videos"

        print("✅ TEST PASSED")
        print(f"   Expected: 1 bookmark, 3 videos")
        print(f"   Got: {daily_stats['bookmarks_uploaded']} bookmark(s), {daily_stats['videos_uploaded']} video(s)")

        # Show per-bookmark stats
        bookmark_stats = state_manager.get_bookmark_usage_stats("CreatorA")
        print(f"\n📊 CreatorA Stats:")
        print(f"   Videos: {bookmark_stats['videos']}")
        print(f"   First Upload: {bookmark_stats['first_upload']}")
        print(f"   Last Upload: {bookmark_stats['last_upload']}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_multiple_bookmarks():
    """Test: Multiple bookmarks should each count once"""
    print_header("TEST 2: Multiple Unique Bookmarks")

    temp_dir = tempfile.mkdtemp()

    try:
        state_manager = StateManager(data_dir=temp_dir)

        bookmarks = ["CreatorA", "CreatorB", "CreatorC"]
        videos_per_bookmark = [3, 5, 2]

        print("📁 Uploading to Multiple Bookmarks:")
        print("-" * 70)

        for bookmark, video_count in zip(bookmarks, videos_per_bookmark):
            print(f"\nBookmark: '{bookmark}' ({video_count} videos)")
            for i in range(video_count):
                state_manager.increment_daily_bookmarks(count=1, bookmark_name=bookmark)

            daily_stats = state_manager.get_daily_stats()
            print(f"  → Unique Bookmarks: {daily_stats['bookmarks_uploaded']}, "
                  f"Total Videos: {daily_stats['videos_uploaded']}")

        print("\n" + "-" * 70)
        daily_stats = state_manager.get_daily_stats()

        total_videos = sum(videos_per_bookmark)

        # Verify results
        assert daily_stats['bookmarks_uploaded'] == 3, "Should count 3 unique bookmarks"
        assert daily_stats['videos_uploaded'] == total_videos, f"Should count {total_videos} videos"

        print("✅ TEST PASSED")
        print(f"   Expected: 3 bookmarks, {total_videos} videos")
        print(f"   Got: {daily_stats['bookmarks_uploaded']} bookmark(s), {daily_stats['videos_uploaded']} video(s)")

        # Show all bookmarks used
        bookmarks_used = state_manager.get_bookmarks_used_today()
        print(f"\n📋 Bookmarks Used Today: {', '.join(bookmarks_used)}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_mixed_scenario():
    """Test: Real-world scenario with multiple bookmarks and videos"""
    print_header("TEST 3: Real-World Scenario")

    temp_dir = tempfile.mkdtemp()

    try:
        state_manager = StateManager(data_dir=temp_dir)

        # Simulate real upload scenario
        upload_sequence = [
            ("CreatorA", 1),
            ("CreatorA", 1),
            ("CreatorB", 1),
            ("CreatorA", 1),
            ("CreatorC", 1),
            ("CreatorB", 1),
            ("CreatorB", 1),
        ]

        print("📁 Upload Sequence:")
        print("-" * 70)

        for i, (bookmark, count) in enumerate(upload_sequence, 1):
            state_manager.increment_daily_bookmarks(count=count, bookmark_name=bookmark)
            daily_stats = state_manager.get_daily_stats()

            bookmark_stats = state_manager.get_bookmark_usage_stats(bookmark)
            print(f"Upload {i}: {bookmark} → "
                  f"Unique: {daily_stats['bookmarks_uploaded']}, "
                  f"Total Videos: {daily_stats['videos_uploaded']}, "
                  f"{bookmark} Videos: {bookmark_stats['videos']}")

        print("\n" + "-" * 70)
        daily_stats = state_manager.get_daily_stats()

        # Verify
        assert daily_stats['bookmarks_uploaded'] == 3, "Should have 3 unique bookmarks"
        assert daily_stats['videos_uploaded'] == 7, "Should have 7 total videos"

        print("✅ TEST PASSED")
        print(f"   Expected: 3 unique bookmarks, 7 total videos")
        print(f"   Got: {daily_stats['bookmarks_uploaded']} bookmark(s), {daily_stats['videos_uploaded']} video(s)")

        # Show detailed summary
        print("\n" + state_manager.get_detailed_daily_summary())

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_backward_compatibility():
    """Test: Legacy calls without bookmark_name still work"""
    print_header("TEST 4: Backward Compatibility (No bookmark_name)")

    temp_dir = tempfile.mkdtemp()

    try:
        state_manager = StateManager(data_dir=temp_dir)

        print("📁 Legacy increment (no bookmark_name parameter):")
        print("-" * 70)

        # Old-style call without bookmark_name
        for i in range(1, 4):
            state_manager.increment_daily_bookmarks(count=1)  # No bookmark_name
            daily_stats = state_manager.get_daily_stats()
            print(f"Upload {i} → Bookmarks: {daily_stats['bookmarks_uploaded']}, "
                  f"Videos: {daily_stats['videos_uploaded']}")

        print("\n" + "-" * 70)
        daily_stats = state_manager.get_daily_stats()

        # Verify legacy behavior
        assert daily_stats['bookmarks_uploaded'] == 3, "Legacy: Should increment each time"
        assert daily_stats['videos_uploaded'] == 3, "Legacy: Videos = bookmarks"

        print("✅ TEST PASSED")
        print(f"   Legacy behavior maintained: {daily_stats['bookmarks_uploaded']} bookmarks, "
              f"{daily_stats['videos_uploaded']} videos")
        print("   (No deduplication when bookmark_name not provided)")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_daily_limit_check():
    """Test: Daily limit check uses correct counter"""
    print_header("TEST 5: Daily Limit Check")

    temp_dir = tempfile.mkdtemp()

    try:
        state_manager = StateManager(data_dir=temp_dir)

        # Simulate uploading to bookmarks close to limit
        for i in range(198):
            state_manager.increment_daily_bookmarks(count=1, bookmark_name=f"Creator{i}")

        # Upload 5 videos to same bookmark
        for _ in range(5):
            state_manager.increment_daily_bookmarks(count=1, bookmark_name="CreatorLast1")

        # Upload 3 videos to another bookmark
        for _ in range(3):
            state_manager.increment_daily_bookmarks(count=1, bookmark_name="CreatorLast2")

        daily_stats = state_manager.get_daily_stats()
        limit_check = state_manager.check_daily_limit(user_type="basic", limit=200)

        print(f"Unique Bookmarks: {daily_stats['bookmarks_uploaded']}")
        print(f"Total Videos: {daily_stats['videos_uploaded']}")
        print(f"Daily Limit: {limit_check['limit']}")
        print(f"Limit Reached: {limit_check['limit_reached']}")
        print(f"Remaining: {limit_check['remaining']}")

        assert daily_stats['bookmarks_uploaded'] == 200, "Should be 200 unique bookmarks"
        assert daily_stats['videos_uploaded'] == 206, "Should be 206 total videos"
        assert limit_check['limit_reached'] == True, "Limit should be reached"
        assert limit_check['remaining'] == 0, "No bookmarks remaining"

        print("\n✅ TEST PASSED")
        print("   Limit correctly based on UNIQUE bookmarks, not total videos!")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 10 + "AUTO UPLOADER BOOKMARK COUNTER FIX - TESTS" + " " * 16 + "║")
    print("╚" + "═" * 68 + "╝")

    # Run all test cases
    test_single_bookmark_multiple_videos()
    test_multiple_bookmarks()
    test_mixed_scenario()
    test_backward_compatibility()
    test_daily_limit_check()

    # Summary
    print_header("ALL TESTS PASSED ✅")
    print("Key Features Verified:")
    print("  ✓ Per-bookmark tracking and deduplication")
    print("  ✓ Unique bookmark counting (not total videos)")
    print("  ✓ Multiple videos to same bookmark counted correctly")
    print("  ✓ Detailed per-bookmark statistics")
    print("  ✓ Daily limit based on unique bookmarks")
    print("  ✓ Backward compatibility maintained")
    print("\n🎯 Fix Summary:")
    print("  OLD: Counter incremented for every video upload")
    print("  NEW: Counter increments only for UNIQUE bookmarks/pages")
    print("  Result: Daily limit now correctly tracks pages, not videos!")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
