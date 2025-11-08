#!/usr/bin/env python3
"""
End-to-end workflow test
Tests complete flow: bookmark navigation + Add Videos button detection
"""

import logging
import sys
from pathlib import Path
import numpy as np
import pyautogui
import time

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from modules.auto_uploader.browser.video_upload_workflow.workflow_orchestrator import UploadWorkflowOrchestrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)

logger = logging.getLogger(__name__)

def test_end_to_end():
    """Test complete workflow"""

    logger.info("╔════════════════════════════════════════╗")
    logger.info("║  END-TO-END WORKFLOW TEST              ║")
    logger.info("╚════════════════════════════════════════╝\n")

    # Initialize orchestrator
    orchestrator = UploadWorkflowOrchestrator()

    # Use the profile that was mentioned in previous work
    profile_id = "Nathaniel Cobb coocking"

    logger.info(f"Testing profile: {profile_id}\n")

    # Run workflow
    success = orchestrator.execute_workflow(profile_id)

    logger.info("\n╔════════════════════════════════════════╗")
    if success:
        logger.info("║  ✅ WORKFLOW TEST COMPLETED           ║")
    else:
        logger.info("║  ❌ WORKFLOW TEST FAILED              ║")
    logger.info("╚════════════════════════════════════════╝\n")

    return success

if __name__ == "__main__":
    try:
        success = test_end_to_end()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
