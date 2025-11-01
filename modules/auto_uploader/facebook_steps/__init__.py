"""Clean, step-by-step Facebook automation workflow.

This module provides a structured 5-step workflow:
1. Load credentials from login_data.txt
2. Find browser shortcut on desktop
3. Launch browser and maximize window
4. Check current login session status
5. Handle login/logout based on session state

Main entry point: FacebookAutomationWorkflow
"""

# New clean API
from .step_1_load_credentials import Credentials, CredentialsError, load_credentials
from .step_2_find_shortcut import ShortcutError, find_shortcut
from .step_3_launch_browser import BrowserLaunchError, maximize_window, open_shortcut
from .step_4_check_session import SessionStatus, check_session
from .step_5_handle_login import login, logout
from .utils_mouse_feedback import human_delay
from .workflow_main import FacebookAutomationWorkflow, WorkflowError, run_workflow
from .setup_manager import SetupManager
from .workflow_with_setup import WorkflowWithSetup, start_automation

# Legacy imports (for backward compatibility)
from .login_data_reader import LoginData, LoginDataError, load_login_data
from .shortcut_locator import ShortcutNotFoundError, find_browser_shortcut
from .browser_opener import BrowserLaunchError as BrowserLaunchErrorLegacy, open_browser
from .window_preparer import BrowserWindowNotFoundError, focus_and_prepare_window
from .session_status import SessionState as SessionStateLegacy, detect_session_state
from .session_actions import login_with_credentials, logout_current_session
from .mouse_feedback import human_delay as human_delay_legacy
from .workflow import FacebookAutomationWorkflow as FacebookAutomationWorkflowLegacy

__all__ = [
    # New clean API
    "Credentials",
    "CredentialsError",
    "load_credentials",
    "ShortcutError",
    "find_shortcut",
    "BrowserLaunchError",
    "maximize_window",
    "open_shortcut",
    "SessionStatus",
    "check_session",
    "login",
    "logout",
    "human_delay",
    "FacebookAutomationWorkflow",
    "WorkflowError",
    "run_workflow",
    # Setup and Complete Workflow
    "SetupManager",
    "WorkflowWithSetup",
    "start_automation",
    # Legacy API (backward compatibility)
    "LoginData",
    "LoginDataError",
    "load_login_data",
    "ShortcutNotFoundError",
    "find_browser_shortcut",
    "BrowserWindowNotFoundError",
    "focus_and_prepare_window",
    "detect_session_state",
    "login_with_credentials",
    "logout_current_session",
    "open_browser",
]
