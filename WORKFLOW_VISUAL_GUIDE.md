# Facebook Automation - Visual Workflow Guide

## 🎯 The 5-Step Workflow

```
START
  ↓
┌─────────────────────────────────────────────┐
│ STEP 1: Load Credentials                    │
│ File: step_1_load_credentials.py            │
│                                             │
│ Read login_data.txt from disk               │
│ Parse: browser, email, password             │
│ Return: Credentials object                  │
└─────────────────────────────────────────────┘
  ↓
  ✅ Success → Continue
  ❌ Error → CredentialsError (File missing or invalid)
  ↓
┌─────────────────────────────────────────────┐
│ STEP 2: Find Browser Shortcut               │
│ File: step_2_find_shortcut.py               │
│                                             │
│ Take browser name from credentials          │
│ Search Desktop for matching .lnk file       │
│ Use known patterns for supported browsers   │
│ Return: Path to shortcut                    │
└─────────────────────────────────────────────┘
  ↓
  ✅ Success → Continue
  ❌ Error → ShortcutError (Shortcut not on desktop)
  ↓
┌─────────────────────────────────────────────┐
│ STEP 3: Launch Browser & Maximize           │
│ File: step_3_launch_browser.py              │
│                                             │
│ Open the shortcut file                      │
│ Wait for browser to launch (12 sec)         │
│ Mouse moves in circles (looks natural)      │
│ Find browser window                         │
│ Activate and maximize it                    │
│ Wait for stabilization (2 sec)              │
└─────────────────────────────────────────────┘
  ↓
  ✅ Success → Continue
  ❌ Error → BrowserLaunchError (Can't find window)
  ↓
  💤 WAIT 3 SECONDS (with mouse movement)
  ↓
┌─────────────────────────────────────────────┐
│ STEP 4: Check Login Session                 │
│ File: step_4_check_session.py               │
│                                             │
│ Take screenshot                             │
│ Search for profile icon                     │
│ → Found: Return LOGGED_IN                   │
│ Search for login form                       │
│ → Found: Return LOGGED_OUT                  │
│ → Not found: Return UNKNOWN                 │
└─────────────────────────────────────────────┘
  ↓
  📊 Check returned status:
  ├─→ LOGGED_IN  │
  ├─→ LOGGED_OUT │
  └─→ UNKNOWN    │
  ↓
  ┌──────────────────────────────────┬──────────────────────────────────┬──────────────────────────────────┐
  │ If LOGGED_IN                     │ If LOGGED_OUT                    │ If UNKNOWN                       │
  ├──────────────────────────────────┼──────────────────────────────────┼──────────────────────────────────┤
  │ Do logout first, then login      │ Just login with credentials      │ Attempt login as precaution     │
  └──────────────────────────────────┴──────────────────────────────────┴──────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────┐
│ STEP 5: Handle Login / Logout               │
│ File: step_5_handle_login.py                │
│                                             │
│ If logged in:                               │
│  • Click profile icon                       │
│  • Click logout button                      │
│  • Wait 4 seconds for logout                │
│  • Then proceed to login                    │
│                                             │
│ Then login (or just login if not in):       │
│  • Click login form                         │
│  • Type email                               │
│  • Press Tab                                │
│  • Type password                            │
│  • Press Enter                              │
│  • Wait 6 seconds for Facebook              │
└─────────────────────────────────────────────┘
  ↓
  ✅ WORKFLOW COMPLETE
  ↓
END
```

---

## 📁 File Organization

```
facebook_steps/
│
├─ 📖 Documentation
│  ├─ README_STRUCTURE.md        ← Technical details
│  ├─ USAGE_GUIDE.md             ← Examples & troubleshooting
│  └─ FILES_CREATED.md           ← Summary of new files
│
├─ 🎯 Main Orchestrator
│  └─ workflow_main.py           ← Runs all 5 steps
│
├─ 🔧 Core Steps (5 files)
│  ├─ step_1_load_credentials.py ← Load from file
│  ├─ step_2_find_shortcut.py    ← Search desktop
│  ├─ step_3_launch_browser.py   ← Open & maximize
│  ├─ step_4_check_session.py    ← Check login state
│  └─ step_5_handle_login.py     ← Login/logout
│
├─ 🔨 Utilities
│  └─ utils_mouse_feedback.py    ← Mouse movement
│
├─ ⚙️  Module API
│  └─ __init__.py                ← Exports (updated)
│
└─ 📚 Legacy (backward compatible)
   ├─ login_data_reader.py
   ├─ shortcut_locator.py
   ├─ browser_opener.py
   ├─ window_preparer.py
   ├─ session_status.py
   ├─ session_actions.py
   ├─ mouse_feedback.py
   └─ workflow.py
```

---

## 🔄 Data Flow Between Steps

```
STEP 1                      STEP 2
   ↓                           ↓
   Credentials ────────────→ browser_name
   {                           │
     browser: "Chrome"         │ find_shortcut()
     email: "..."              │
     password: "..."           ↓
   }                       Path("/Desktop/Google Chrome.lnk")
                                │
                                ├─→ STEP 3
                                    │
                                    open_shortcut()
                                    maximize_window()
                                    │
                                    └─→ STEP 4
                                        │
                                        check_session()
                                        │
                                        SessionStatus.LOGGED_IN
                                        SessionStatus.LOGGED_OUT
                                        SessionStatus.UNKNOWN
                                        │
                                        └─→ STEP 5
                                            if LOGGED_IN:
                                              logout()
                                            login(credentials) ←─────────┐
                                                                        │
                                        Credentials returned from Step 1 ─┘
```

---

## 🎭 Example Execution Scenarios

### Scenario 1: Fresh Browser (Not Logged In)

```
STEP 1: Load credentials ✅
  ↓
STEP 2: Find browser shortcut ✅
  ↓
STEP 3: Launch & maximize ✅
  ↓
STEP 4: Check session → LOGGED_OUT ✅
  ↓
STEP 5: Login with credentials ✅
  ↓
✨ DONE - User is now logged in
```

### Scenario 2: Browser Already Has Active Session

```
STEP 1: Load credentials ✅
  ↓
STEP 2: Find browser shortcut ✅
  ↓
STEP 3: Launch & maximize ✅
  ↓
STEP 4: Check session → LOGGED_IN ✅
  ↓
STEP 5a: Logout current user ✅
  ↓
STEP 5b: Login with provided credentials ✅
  ↓
✨ DONE - Old session replaced with new login
```

### Scenario 3: Error - Shortcut Not Found

```
STEP 1: Load credentials ✅
  ↓
STEP 2: Find browser shortcut ❌
  ↓
⚠️  ShortcutError
    "Could not find shortcut for 'Chrome'
     Searched for: Google Chrome.lnk, Chrome.lnk
     Desktop path: C:\Users\YourName\Desktop"
  ↓
❌ WORKFLOW FAILED
   (User knows exactly what to fix)
```

---

## 🖱️ Mouse Feedback During Waits

When you see `human_delay()` calls, here's what happens:

```
human_delay(12, "Waiting for browser to launch...")

Time: 0 seconds        Time: 6 seconds        Time: 12 seconds
┌──────────┐          ┌──────────┐          ┌──────────┐
│          │          │    ✓     │          │          │
│    🖱    │  ✓ ✓ ✓   │   ✓  ✓   │  ✓ ✓ ✓   │    🖱    │
│          │  ✓   ✓   │  ✓    ✓  │  ✓   ✓   │          │
│          │ ✓  ✓  ✓  │ ✓      ✓ │ ✓  ✓  ✓  │          │
└──────────┘          └──────────┘          └──────────┘

Mouse traces circles randomly during the entire wait.
Looks natural, not like a bot sitting idle.
```

---

## 🚨 Error Handling

Each step can produce specific errors:

```
STEP 1: CredentialsError
   ├─ File not found
   ├─ File format incorrect
   └─ Missing required fields

STEP 2: ShortcutError
   ├─ Browser shortcut not on desktop
   ├─ Desktop directory doesn't exist
   └─ Browser name invalid

STEP 3: BrowserLaunchError
   ├─ Shortcut file invalid
   ├─ Browser window not found
   └─ Window management failed

STEP 4: SessionStatus.UNKNOWN
   └─ (Not an error - returns safest option)

STEP 5: (No exception)
   └─ Returns bool or completes silently
```

All errors are caught by `FacebookAutomationWorkflow` and wrapped in `WorkflowError`.

---

## 📊 API Imports

### Clean New API
```python
from modules.auto_uploader.facebook_steps import (
    # Functions for each step
    load_credentials,          # Step 1
    find_shortcut,            # Step 2
    open_shortcut,            # Step 3
    maximize_window,          # Step 3
    check_session,            # Step 4
    login,                    # Step 5
    logout,                   # Step 5

    # Data types
    Credentials,              # From Step 1
    SessionStatus,            # From Step 4

    # Utilities
    human_delay,             # Used everywhere

    # Exceptions
    CredentialsError,        # From Step 1
    ShortcutError,           # From Step 2
    BrowserLaunchError,      # From Step 3

    # Main orchestrator
    FacebookAutomationWorkflow,
    run_workflow,
    WorkflowError,
)
```

---

## 🔍 What Each File Contains

### step_1_load_credentials.py (72 lines)
- Reads file line-by-line
- Parses key:value format
- Validates required fields
- Returns Credentials object

### step_2_find_shortcut.py (87 lines)
- Knows 7+ browser types
- Searches desktop
- Uses pattern matching
- Returns Path or raises error

### step_3_launch_browser.py (127 lines)
- Opens .lnk shortcut
- Finds window by title
- Retries multiple times
- Maximizes and stabilizes

### step_4_check_session.py (78 lines)
- Uses image recognition
- Detects profile icon
- Detects login form
- Returns status enum

### step_5_handle_login.py (142 lines)
- Locates UI elements
- Performs clicks
- Types credentials
- Waits for processing

### utils_mouse_feedback.py (73 lines)
- Generates random circles
- Moves mouse smoothly
- Fills entire wait time
- Looks natural

### workflow_main.py (180 lines)
- Orchestrates all steps
- Passes data between steps
- Handles errors
- Provides clear logging

---

## ⏱️ Typical Execution Timeline

```
T=0s    START

T=1s    "Step 1: Load Credentials"
        Load login_data.txt
T=2s    ✓ Credentials loaded

T=2s    "Step 2: Find Browser Shortcut"
        Search Desktop for shortcut
T=3s    ✓ Shortcut found: Google Chrome.lnk

T=3s    "Step 3: Launch Browser & Maximize"
        Open shortcut
T=5s    Mouse circles...
T=10s   Mouse circles...
T=12s   ✓ Browser window found and maximized

T=14s   "Step 4: Check Session Status"
        Screenshot and image detection
T=16s   ✓ Session status: LOGGED_OUT

T=16s   "Step 5: Handle Login/Logout"
        Login with provided credentials
T=18s   Typing email...
T=19s   Typing password...
T=20s   Submitting form...
T=26s   ✓ Login completed

T=26s   ✅ WORKFLOW COMPLETE

Total time: ~26 seconds with waits included
```

---

## 💡 Key Insights

1. **Modularity**: Each step is independent and can be tested alone
2. **Clarity**: Function names tell you exactly what they do
3. **Safety**: Errors are specific and helpful
4. **Naturalism**: Mouse movement makes automation invisible
5. **Reliability**: Retries and fallbacks handle edge cases
6. **Maintainability**: Change one step without touching others

---

## 🎓 Learning Path

1. **Read first**: `FACEBOOK_AUTOMATION_REFACTOR_SUMMARY.md` (overview)
2. **Understand**: `README_STRUCTURE.md` (technical details)
3. **Practice**: `USAGE_GUIDE.md` (code examples)
4. **Reference**: Source code docstrings (detailed docs)
5. **Extend**: Add your own modifications!

---

## ✨ Summary

Your automation workflow is now:

- **Clear** - Numbered steps are obvious
- **Modular** - Each step in its own file
- **Documented** - Complete guides with examples
- **Safe** - Error messages tell you what to fix
- **Reliable** - Retries and fallbacks included
- **Professional** - Production-ready code quality

**Ready to use!** 🚀
