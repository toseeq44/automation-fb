"""
Browser Module
===============
Handles all browser-related operations for automation.

This module is HIGHLY REUSABLE and can be imported by other modules
like video_downloader, link_grabber, etc.

Submodules:
-----------
- launcher: Browser launching operations (desktop search, launch, process management)
- connector: Selenium connection management
- profile_manager: Profile opening and switching
- status_checker: Browser status monitoring
- window_manager: Window operations (cross-platform)
- session_manager: Session persistence and restoration
- screen_detector: Image recognition for UI detection (NEW)
- mouse_controller: Human-like mouse movements with bezier curves (NEW)
- login_manager: Intelligent login/logout with autofill handling (NEW)
- fullscreen_manager: Fullscreen operations with F11 (NEW)
- workflow_controller: Complete workflow orchestration (NEW)

Example Usage:
--------------
from modules.auto_uploader.browser.launcher import BrowserLauncher
from modules.auto_uploader.browser.connector import SeleniumConnector
from modules.auto_uploader.browser.workflow_controller import WorkflowController

# Simple workflow approach
controller = WorkflowController('gologin')
controller.execute_complete_workflow('email@example.com', 'password123')

# Manual approach
launcher = BrowserLauncher()
launcher.launch_gologin()

connector = SeleniumConnector()
driver = connector.connect_to_port(9222)
"""

__version__ = "2.0.0"
__all__ = [
    "BrowserLauncher",
    "SeleniumConnector",
    "ProfileManager",
    "StatusChecker",
    "WindowManager",
    "SessionManager",
    "ScreenDetector",
    "MouseController",
    "LoginManager",
    "FullscreenManager",
    "WorkflowController",
    "AdvancedScreenAnalyzer",
    "OCRDetector",
    "HealthChecker",
    "CoordinatePredictor",
    "StrategyOrchestrator",
    "IXProfileSelector",
]

from .advanced_screen_analyzer import AdvancedScreenAnalyzer
from .health_checker import HealthChecker
from .ml_coordinate_predictor import CoordinatePredictor
from .ocr_detector import OCRDetector
from .strategy_orchestrator import StrategyOrchestrator
from .profile_selector import IXProfileSelector
