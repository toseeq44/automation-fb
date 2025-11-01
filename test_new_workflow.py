#!/usr/bin/env python3
"""Test the new clean Facebook automation workflow."""

import logging
from pathlib import Path

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Test the new 5-step workflow."""

    logger.info("=" * 70)
    logger.info("Testing New Facebook Automation Workflow")
    logger.info("=" * 70)

    try:
        # Import the new clean API
        from modules.auto_uploader.facebook_steps import (
            run_workflow,
            WorkflowError,
            CredentialsError,
            ShortcutError,
            BrowserLaunchError,
        )

        logger.info("\n✓ Successfully imported new workflow")
        logger.info("\nStarting workflow execution...\n")

        data_folder = Path("./data")

        # Run the complete workflow
        run_workflow(data_folder)

        logger.info("\n" + "=" * 70)
        logger.info("✅ WORKFLOW COMPLETED SUCCESSFULLY!")
        logger.info("=" * 70)
        return True

    except CredentialsError as e:
        logger.error("\n" + "=" * 70)
        logger.error("❌ CREDENTIALS ERROR")
        logger.error("=" * 70)
        logger.error(f"Problem: {e}")
        logger.error("\nSolution: Create ./data/login_data.txt with format:")
        logger.error("  browser: Chrome")
        logger.error("  email: your.email@facebook.com")
        logger.error("  password: YourPassword123")
        return False

    except ShortcutError as e:
        logger.error("\n" + "=" * 70)
        logger.error("❌ SHORTCUT ERROR")
        logger.error("=" * 70)
        logger.error(f"Problem: {e}")
        logger.error("\nSolution: Create browser shortcut on Desktop")
        logger.error("  1. Go to Desktop")
        logger.error("  2. Right-click the browser")
        logger.error("  3. Select 'Create shortcut'")
        logger.error("  4. Save to Desktop")
        return False

    except BrowserLaunchError as e:
        logger.error("\n" + "=" * 70)
        logger.error("❌ BROWSER LAUNCH ERROR")
        logger.error("=" * 70)
        logger.error(f"Problem: {e}")
        logger.error("\nSolution: Check if browser window opened")
        logger.error("  1. Is the browser shortcut valid?")
        logger.error("  2. Does the browser window have correct title?")
        logger.error("  3. Is pygetwindow installed? (pip install pygetwindow)")
        return False

    except WorkflowError as e:
        logger.error("\n" + "=" * 70)
        logger.error("❌ WORKFLOW ERROR")
        logger.error("=" * 70)
        logger.error(f"Problem: {e}")
        logger.error("\nCheck logs above for details")
        return False

    except Exception as e:
        logger.error("\n" + "=" * 70)
        logger.error("❌ UNEXPECTED ERROR")
        logger.error("=" * 70)
        logger.error(f"Problem: {e}")
        logger.error("\nThis is unexpected. Check logs for details")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
