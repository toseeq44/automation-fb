# Facebook Automation Workflow - Clean Structure Guide

## Overview

This module implements a clean, modular 5-step workflow for Facebook browser automation. Each step is independent and focused on a single responsibility, making the code easy to understand, maintain, and test.

## Project Structure

```
facebook_steps/
├── README_STRUCTURE.md              # This file
├── __init__.py                      # Module API exports
├── workflow_main.py                 # Main orchestrator (ties all steps together)
├── step_1_load_credentials.py       # Load login data from file
├── step_2_find_shortcut.py          # Find browser shortcut on desktop
├── step_3_launch_browser.py         # Open browser and maximize window
├── step_4_check_session.py          # Check current login state
├── step_5_handle_login.py           # Handle login/logout actions
├── utils_mouse_feedback.py          # Utility: Human-like mouse movement
│
├── [Legacy files - still working for backward compatibility]
├── login_data_reader.py
├── shortcut_locator.py
├── browser_opener.py
├── window_preparer.py
├── session_status.py
├── session_actions.py
├── mouse_feedback.py
└── workflow.py
```

## The 5-Step Workflow

### Step 1: Load Credentials
**File:** `step_1_load_credentials.py`

**Responsibility:** Read and parse the `login_data.txt` file.

**Expected File Format:**
```
browser: Chrome
email: user@example.com
password: securepassword123
```

**Key Classes:**
- `Credentials` - Data class holding browser, email, password
- `CredentialsError` - Exception for credential issues

**Key Functions:**
- `load_credentials(data_folder)` - Main entry point

**What it does:**
1. Reads `login_data.txt` from the specified folder
2. Parses key-value pairs (supports comments starting with #)
3. Validates all required fields are present
4. Returns a `Credentials` object

---

### Step 2: Find Browser Shortcut
**File:** `step_2_find_shortcut.py`

**Responsibility:** Extract browser name and locate its shortcut on the desktop.

**Key Classes:**
- `ShortcutError` - Exception when shortcut cannot be found

**Key Functions:**
- `find_shortcut(browser_name, desktop_path=None)` - Main entry point

**What it does:**
1. Takes the browser name from credentials (e.g., "Chrome", "IX")
2. Searches the desktop for matching `.lnk` shortcut files
3. Uses known naming patterns for popular browsers
4. Falls back to generic patterns if no known match
5. Returns the path to the found shortcut

**Supported Browsers:**
- IX Browser (ixBrowser.lnk, IX Browser.lnk)
- GoLogin (GoLogin.lnk, gologin.lnk)
- Incogniton (Incogniton.lnk)
- Orbita (Orbita.lnk)
- Chrome (Google Chrome.lnk, Chrome.lnk)
- Edge (Microsoft Edge.lnk, Edge.lnk)
- Firefox (Mozilla Firefox.lnk, Firefox.lnk)

---

### Step 3: Launch Browser
**File:** `step_3_launch_browser.py`

**Responsibility:** Open the browser shortcut and maximize its window.

**Key Classes:**
- `BrowserLaunchError` - Exception for browser launch issues

**Key Functions:**
- `open_shortcut(shortcut_path, wait_seconds=12)` - Launch the browser
- `maximize_window(browser_name, max_retries=3, retry_wait_seconds=4)` - Find and maximize window

**What it does:**

**open_shortcut():**
1. Validates the shortcut file exists
2. Opens the shortcut using `os.startfile()`
3. Waits with human-like mouse movement (visual feedback)

**maximize_window():**
1. Searches for the browser window by title patterns
2. Retries multiple times (default 3) if window not immediately found
3. Activates the window
4. Maximizes it
5. Waits for the window to stabilize

---

### Step 4: Check Session Status
**File:** `step_4_check_session.py`

**Responsibility:** Determine if a user is currently logged into Facebook.

**Key Classes:**
- `SessionStatus` - Enum with values: LOGGED_IN, LOGGED_OUT, UNKNOWN

**Key Functions:**
- `check_session(save_screenshot_to=None, confidence=0.75)` - Check login state

**What it does:**
1. Takes a screenshot for analysis
2. Looks for profile icon (indicates logged-in state)
3. Looks for login form (indicates logged-out state)
4. Saves screenshot for debugging if requested
5. Returns a `SessionStatus` enum value

**Detection Method:**
Uses image recognition with PyAutoGUI to locate reference images:
- Profile icon image → User is logged in
- Login form image → User is logged out
- Neither found → Status unknown

---

### Step 5: Handle Login/Logout
**File:** `step_5_handle_login.py`

**Responsibility:** Perform login or logout based on session state.

**Key Functions:**
- `logout()` - Log out current session
- `login(credentials, typing_interval=0.05)` - Log in with credentials

**What it does:**

**logout():**
1. Searches for profile icon on screen
2. Clicks it to open the profile menu
3. Searches for logout button
4. Clicks logout button
5. Waits for logout to complete

**login():**
1. Locates the login form (or uses screen center as fallback)
2. Clicks the form to focus it
3. Types email address with human-like speed
4. Presses Tab to move to password field
5. Types password
6. Presses Enter to submit
7. Waits for Facebook to process the login

---

## Main Orchestrator

**File:** `workflow_main.py`

**Class:** `FacebookAutomationWorkflow`

**How to use:**
```python
from pathlib import Path
from modules.auto_uploader.facebook_steps import FacebookAutomationWorkflow

data_folder = Path("./data")
workflow = FacebookAutomationWorkflow(data_folder)
workflow.run()
```

**Or use the convenience function:**
```python
from modules.auto_uploader.facebook_steps import run_workflow

run_workflow(Path("./data"))
```

**What it does:**
1. Calls all 5 steps in sequence
2. Passes data between steps
3. Handles errors with detailed logging
4. Prints progress with section headers
5. Provides clear success/failure messages

**Example Output:**
```
======================================================================
STEP 1: Load Credentials
======================================================================
INFO - Loading credentials from: ./data
INFO - ✓ Credentials loaded successfully
INFO -   Browser: Chrome
INFO -   Email: user@example.com

======================================================================
STEP 2: Find Browser Shortcut
======================================================================
INFO - Searching for 'Chrome' shortcut on desktop...
INFO - ✓ Shortcut found: Google Chrome.lnk

[... continues for steps 3-5 ...]
```

---

## Utility Module

**File:** `utils_mouse_feedback.py`

**Key Functions:**
- `human_delay(seconds, status=None)` - Pause with visual mouse feedback

**What it does:**
1. Moves the mouse in random circular patterns during waits
2. Uses randomized circle parameters (size, position, speed)
3. Creates the appearance of human activity
4. Helps avoid detection by monitoring systems
5. Logs status messages during delays

**Mouse Movement Features:**
- Random circle radius: 40-120 pixels
- Random circle steps: 16-32 points
- Random movement speed: 0.02-0.06 seconds per step
- Entire pause is filled with movement (no idle time)

---

## Error Handling

Each step defines its own exception class:

```python
from modules.auto_uploader.facebook_steps import (
    CredentialsError,      # Step 1
    ShortcutError,         # Step 2
    BrowserLaunchError,    # Step 3
    # Step 4 has no exceptions (returns SessionStatus.UNKNOWN)
    # Step 5 returns bool (True = success, False = not applicable)
)
```

The main workflow catches these and wraps them in `WorkflowError`:

```python
from modules.auto_uploader.facebook_steps import FacebookAutomationWorkflow, WorkflowError

try:
    workflow = FacebookAutomationWorkflow(Path("./data"))
    workflow.run()
except WorkflowError as e:
    print(f"Workflow failed: {e}")
```

---

## Configuration

### login_data.txt Format

Required fields:
- `browser` - Name of the browser (e.g., "Chrome", "IX", "Firefox")
- `email` - Facebook email address
- `password` - Facebook password

Optional features:
- Comments: Lines starting with `#` are ignored
- Empty lines are ignored
- Extra whitespace is trimmed

Example:
```
# My Facebook credentials for automation
browser: Chrome
email: user@example.com
password: MySecurePassword123!
```

### Environment Setup

**Requirements:**
```
pyautogui      # For screen interaction and mouse control
pygetwindow    # For window management
```

**Image Files Required:**
Place these in `modules/auto_uploader/helper_images/`:
- `current_profile_cordinates.png` - Screenshot of profile icon
- `new_login_cordinates.png` - Screenshot of login form
- `current_profile_relatdOption_cordinates.png` - Screenshot of logout button

---

## Development Guide

### Adding New Steps

To add a new step:

1. Create `step_X_<description>.py`
2. Define custom exception class
3. Create main function(s)
4. Add docstrings explaining purpose and workflow
5. Update `workflow_main.py` to call your step
6. Update `__init__.py` to export your classes/functions

### Testing Individual Steps

```python
# Test Step 1
from modules.auto_uploader.facebook_steps import load_credentials
creds = load_credentials(Path("./data"))

# Test Step 2
from modules.auto_uploader.facebook_steps import find_shortcut
shortcut = find_shortcut(creds.browser)

# Test Step 3
from modules.auto_uploader.facebook_steps import open_shortcut, maximize_window
open_shortcut(shortcut)
maximize_window(creds.browser)

# Test Step 4
from modules.auto_uploader.facebook_steps import check_session
status = check_session()

# Test Step 5
from modules.auto_uploader.facebook_steps import login, logout
if status.value == "logged_out":
    login(creds)
```

---

## Logging

All components use Python's standard `logging` module. Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Log output includes:
- Step progress and status
- File paths and searches
- Timing information
- Error details
- Debug information for troubleshooting

---

## Backward Compatibility

The old files are still available and imported in `__init__.py` for backward compatibility:
- `login_data_reader.py`
- `shortcut_locator.py`
- `browser_opener.py`
- `window_preparer.py`
- `session_status.py`
- `session_actions.py`
- `mouse_feedback.py`
- `workflow.py`

You can still use the old API, but the new step-based API is cleaner and easier to understand.

---

## Summary

This cleaned-up structure makes the Facebook automation workflow:

✅ **Easy to understand** - Each file has one clear responsibility
✅ **Easy to modify** - Change one step without affecting others
✅ **Easy to test** - Each step can be tested independently
✅ **Easy to debug** - Clear error messages and logging
✅ **Easy to extend** - Add new steps without breaking existing code
✅ **Well documented** - Docstrings and comments throughout

The workflow is designed for educational and authorized testing purposes only.
