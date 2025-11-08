#!/usr/bin/env python3
"""
Test script for Add Videos Button Click
Tests the explicit left-click and interface verification
"""

import logging
import sys
from pathlib import Path
import numpy as np
import pyautogui
import time

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from modules.auto_uploader.browser.video_upload_workflow.add_videos_finder import AddVideosFinder

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s"
)

logger = logging.getLogger(__name__)

def test_add_videos_click():
    """Test Add Videos click functionality"""

    logger.info("=" * 70)
    logger.info("TEST: Add Videos Button Click Functionality")
    logger.info("=" * 70)

    # Initialize finder
    finder = AddVideosFinder()

    # Capture screenshot
    logger.info("\nCapturing screenshot...")
    screenshot = pyautogui.screenshot()
    screenshot_array = np.array(screenshot)

    # Step 1: Find button
    logger.info("\n" + "=" * 70)
    logger.info("STEP 1: Find Add Videos Button")
    logger.info("=" * 70)

    button_result = finder.find_and_click_button(screenshot_array)

    logger.info("\n" + "=" * 70)
    logger.info("RESULT")
    logger.info("=" * 70)
    if button_result:
        logger.info("✅ Add Videos button click completed successfully")
        logger.info("   - Button was found and clicked")
        logger.info("   - Interface change detected or proceeding anyway")
        logger.info("   - Ready for next phase")
    else:
        logger.warning("❌ Add Videos button click failed")

    return button_result

if __name__ == "__main__":
    try:
        success = test_add_videos_click()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
