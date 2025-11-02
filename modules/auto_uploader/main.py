"""
Facebook Auto Uploader - Main Entry Point
==========================================

This is the main entry point for the modular auto uploader system.

Usage:
    python main.py

The modular architecture provides:
- Browser management (launch, connect, profile, status, window, session)
- Authentication (credentials, login, 2FA, logout)
- Upload operations (video upload, metadata, progress, post-processing)
- Tracking (history, statistics, duplicates, reports)
- Configuration (settings, paths, validation, defaults)
- Data operations (file handling, JSON, metadata, cache)
- Core orchestration (main workflow coordination)
- UI (setup wizard, dashboard)
- Utilities (logging, validation, formatting, helpers)

All modules are reusable and can be imported independently.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.auto_uploader.core.orchestrator import UploadOrchestrator
from modules.auto_uploader.utils.logger import setup_logging


def main():
    """Main entry point."""
    # Setup logging
    setup_logging(level=logging.INFO)

    logging.info("="*60)
    logging.info("Facebook Auto Uploader - Modular Architecture v2.0")
    logging.info("="*60)

    try:
        # Initialize orchestrator
        orchestrator = UploadOrchestrator()

        # Run workflow
        success = orchestrator.run()

        if success:
            logging.info("Upload process completed successfully!")
            return 0
        else:
            logging.error("Upload process failed!")
            return 1

    except KeyboardInterrupt:
        logging.info("\nProcess interrupted by user")
        return 130
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
