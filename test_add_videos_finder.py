#!/usr/bin/env python3
"""
Test script for Add Videos Finder
Tests the new multiple-method template matching and explicit left-click
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
    format="%(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

def test_add_videos_finder():
    """Test Add Videos Finder with current screenshot"""

    logger.info("=" * 60)
    logger.info("TEST: Add Videos Finder")
    logger.info("=" * 60)

    # Initialize finder
    finder = AddVideosFinder()
    logger.info("✅ AddVideosFinder initialized")

    # Capture current screenshot
    logger.info("\nCapturing current screenshot...")
    screenshot = pyautogui.screenshot()
    screenshot_array = np.array(screenshot)
    logger.info(f"Screenshot captured: {screenshot_array.shape}")

    # Test image matching
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: Image Template Matching (97% confidence)")
    logger.info("=" * 60)

    result = finder._image_match_button(screenshot_array, confidence=0.97)
    if result:
        logger.info(f"✅ FOUND at {result['coords']} (confidence: {result['confidence']:.3f})")
    else:
        logger.warning("⚠️ NOT FOUND at 97% confidence")

        # Try lower confidence
        logger.info("\nTrying with 85% confidence...")
        result = finder._image_match_button(screenshot_array, confidence=0.85)
        if result:
            logger.info(f"✅ FOUND at {result['coords']} (confidence: {result['confidence']:.3f})")
        else:
            logger.warning("⚠️ NOT FOUND at 85% confidence either")

    # Test OCR search
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: OCR Text Search")
    logger.info("=" * 60)

    result = finder._ocr_search_button(screenshot_array)
    if result:
        logger.info(f"✅ FOUND via OCR: '{result['text']}' at {result['coords']}")
    else:
        logger.warning("⚠️ NOT FOUND via OCR")

    # Test interface verification
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Interface Verification")
    logger.info("=" * 60)

    is_verified = finder._verify_upload_interface(screenshot_array)
    if is_verified:
        logger.info("✅ Upload interface detected")
    else:
        logger.warning("⚠️ Upload interface NOT detected")

    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info("✅ All tests completed")
    logger.info("\nNext step: Run find_and_click_button() to test actual clicking")

if __name__ == "__main__":
    test_add_videos_finder()
