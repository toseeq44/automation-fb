"""
Test script for VideoTitleSetter
Demonstrates how to use the title setter after video upload completes
"""

import logging
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from modules.auto_uploader.browser.video_upload_workflow.title_setter import VideoTitleSetter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def test_title_setter_with_selenium():
    """
    Example: Using VideoTitleSetter with existing Selenium driver.

    This assumes you already have:
    1. Browser opened and navigated to Facebook
    2. Video uploaded successfully (100% complete)
    3. Upload form is visible with title field
    """

    # Example: Connect to existing Chrome instance via debugging port
    # (This is how you'd connect to ixBrowser or other browser)
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9223")

    try:
        logger.info("Connecting to browser...")
        driver = webdriver.Chrome(options=chrome_options)

        logger.info("✅ Connected to browser successfully")

        # Create title setter instance
        title_setter = VideoTitleSetter(driver, max_wait=30)

        # Set video title
        video_title = "Amazing Social Experiment - Acts of Kindness"
        video_description = "Watch this heartwarming social experiment! #kindness #wholesome #fyp"

        logger.info(f"Setting title: '{video_title}'")

        success = title_setter.set_video_title(
            title=video_title,
            description=video_description
        )

        if success:
            logger.info("✅ Title set successfully!")
            logger.info("🎉 Video metadata updated!")
        else:
            logger.error("❌ Failed to set title")
            logger.error("Check the logs above to see which selectors were tried")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        # Don't quit the driver if you want to keep the browser open
        # driver.quit()
        logger.info("Test complete")


def example_integration_with_workflow():
    """
    Example: How to integrate title setter into your upload workflow.

    This shows the typical flow:
    1. Open browser and navigate to page
    2. Find and click "Add Videos" button
    3. Upload file
    4. Wait for upload progress (5% → 100%)
    5. SET TITLE ← NEW STEP
    6. Submit/publish
    """

    logger.info("=" * 60)
    logger.info("EXAMPLE WORKFLOW WITH TITLE SETTER")
    logger.info("=" * 60)

    # Assume we have a driver instance from your existing workflow
    # driver = ...

    # After upload completes (you already have this working):
    logger.info("✅ STEP 1-4: Video uploaded 100% complete")

    # NEW STEP 5: Set the title
    logger.info("\n📝 STEP 5: Setting video title...")

    # You can initialize title setter once and reuse it
    # title_setter = VideoTitleSetter(driver)

    # Or create it when needed
    # success = title_setter.set_video_title("My Video Title")

    # Example with video metadata from JSON
    video_metadata = {
        "title": "Social Experiment - Random Acts of Kindness",
        "description": "Spreading positivity! #kindness #socialexperiment #wholesome",
        "tags": ["kindness", "social experiment", "wholesome"]
    }

    # Set title and description
    # success = title_setter.set_video_title(
    #     title=video_metadata["title"],
    #     description=video_metadata["description"]
    # )

    logger.info("✅ STEP 5: Title set successfully")
    logger.info("\n📤 STEP 6: Click publish/submit button...")
    logger.info("✅ WORKFLOW COMPLETE!")


def example_usage_in_orchestrator():
    """
    Example: How to add title setter to UploadWorkflowOrchestrator.

    Add this to your workflow_orchestrator.py:
    """

    example_code = '''
# In workflow_orchestrator.py

from .title_setter import VideoTitleSetter

class UploadWorkflowOrchestrator:
    def __init__(self, profiles_root, helper_images_path, driver=None):
        # ... existing code ...
        self.videos_finder = AddVideosFinder(helper_images_path)

        # ADD THIS:
        self.title_setter = VideoTitleSetter(driver, max_wait=30)

    def execute_workflow(self, profile_id, video_metadata=None):
        # ... existing phases 1-4 ...

        # PHASE 5: Set video title (ADD THIS PHASE)
        logger.info("\\n[ORCHESTRATOR] ═════════════════════════════════════════════")
        logger.info("[ORCHESTRATOR] PHASE 5: Set Video Title")
        logger.info("[ORCHESTRATOR] ═════════════════════════════════════════════")

        if video_metadata and video_metadata.get("title"):
            # Set the Selenium driver if not already set
            self.title_setter.set_driver(driver)  # your selenium driver

            success = self.title_setter.set_video_title(
                title=video_metadata["title"],
                description=video_metadata.get("description")
            )

            if success:
                logger.info("[ORCHESTRATOR] ✅ Title set successfully")
            else:
                logger.warning("[ORCHESTRATOR] ⚠️ Failed to set title")
        else:
            logger.info("[ORCHESTRATOR] ⚠️ No title provided, skipping")

        # Continue with remaining workflow...
'''

    logger.info("=" * 60)
    logger.info("INTEGRATION EXAMPLE FOR ORCHESTRATOR")
    logger.info("=" * 60)
    print(example_code)


def main():
    """Run examples."""

    print("\n" + "=" * 60)
    print("VIDEO TITLE SETTER - TEST & EXAMPLES")
    print("=" * 60)

    print("\n📚 USAGE EXAMPLES:")
    print("\n1. Test with existing browser (requires Chrome with debugging port)")
    print("2. View integration example for workflow")
    print("3. View integration example for orchestrator")

    choice = input("\nEnter choice (1/2/3) or press Enter to show all: ").strip()

    if choice == "1":
        test_title_setter_with_selenium()
    elif choice == "2":
        example_integration_with_workflow()
    elif choice == "3":
        example_usage_in_orchestrator()
    else:
        # Show all examples
        example_integration_with_workflow()
        print("\n")
        example_usage_in_orchestrator()

        print("\n" + "=" * 60)
        print("To test with actual browser, run:")
        print("  python test_title_setter.py")
        print("  Then choose option 1")
        print("=" * 60)


if __name__ == "__main__":
    main()
