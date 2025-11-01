# Browser Launch & Monitoring Guide

## Overview

The new browser launch system is **intelligent, automated, and user-friendly**. It handles:

✅ **Network Detection** - Checks internet connectivity before launching
✅ **Browser Window Detection** - Finds browser window even with different titles
✅ **Intelligent Loading** - Uses screen analysis to detect when page is fully loaded
✅ **Popup Auto-Handling** - Closes cookies, notifications, and ads automatically
✅ **Smart Timeouts** - Adapts to slow/fast networks automatically
✅ **Full Visibility** - Maximizes window for proper viewing

---

## Architecture

### Three Main Components:

#### 1. **BrowserMonitor** (`browser_monitor.py`)
- Detects browser window using multiple title patterns
- Checks network connectivity
- Monitors browser loading status using screen analysis
- Intelligently waits for full page load (not just window opening)
- Maximizes window for visibility

**Key Features:**
- Multiple retry attempts for window detection
- Screen screenshot comparison to detect page stability
- Network connectivity with automatic retry
- Responsive window verification

#### 2. **ScreenAnalyzer** (`screen_analyzer.py`)
- Detects and closes cookie banners
- Closes notification permission popups
- Removes ad popups
- Cleans up screenshots automatically (prevents disk bloat)

**Key Features:**
- Multiple close methods (keyboard, clicking)
- Intelligent popup detection
- Auto-cleanup of temporary files
- Fallback strategies for stubborn popups

#### 3. **BrowserLauncher** (`browser_launcher.py`)
- Orchestrates the complete launch process
- Integrates Monitor and Analyzer
- Provides step-by-step logging
- Graceful error handling

---

## Launch Process (6 Steps)

```
1️⃣  Network Check          → Verify internet connectivity
2️⃣  Browser Launch          → Start browser application
3️⃣  Load Wait              → Intelligent wait for full load
4️⃣  Window Maximize        → Full screen for visibility
5️⃣  Popup Handling         → Auto-close notifications/cookies
6️⃣  Status Report          → Show final status
```

---

## Expected Console Output

```
============================================================
🚀 Browser Launch Process
============================================================

1️⃣  Checking network connectivity...
✓ Network connectivity: OK

2️⃣  Launching browser...
Trying alternative shortcut: C:\Users\...\Desktop\ixBrowser.lnk
✓ Launched ix from ixBrowser.lnk
⏳ Waiting 15 seconds for browser to start...
  ... 5/15 seconds elapsed

3️⃣  Waiting for browser to fully load...
✓ Found browser window: 'ixBrowser - [Window Title]'
⏳ Waiting for browser to fully load (max 60s)...
  [10s] Page still loading...
  [20s] Page still loading...
✓ Browser fully loaded (32s)

4️⃣  Maximizing window...
✓ Browser window maximized

5️⃣  Handling popups and notifications...
🍪 Handling cookie banner...
  ✓ Cookie banner closed
🔔 Handling notification popup...
  ✓ Notification popup closed
📢 Handling ad popups...
  ✓ Ad popups closed
✓ Popup handling completed

============================================================
✅ Browser Launch Complete
============================================================
Browser Type: ix
Window Found: True
Network Connected: True
```

---

## How It Works

### Network Detection
```python
monitor.check_network_connectivity()
# Returns: True if connected, False if not
# Tries to connect to Google DNS (8.8.8.8:53)
# Automatically retries if first attempt fails
```

### Window Detection
```python
monitor.find_browser_window(patterns=['ixBrowser', 'IX Browser', ...])
# Searches for window by title
# Automatically retries every 2 seconds
# Timeout: 30 seconds
# Returns: Window object if found
```

### Intelligent Loading
```python
monitor.wait_for_browser_load(timeout=60)
# Takes screenshots periodically
# Compares screenshots to detect if page changed
# When 2 consecutive screenshots are identical = page loaded
# Verifies browser is responsive
# Adaptive to network speed (can complete in 10s or 50s)
```

### Popup Handling
```python
analyzer.handle_all_popups()
# Closes cookie banner (keyboard shortcuts)
# Closes notification popup (Tab + Enter)
# Closes ad popups (Escape key)
# Tries multiple methods until successful
# Cleans up screenshot files
```

---

## Error Handling

### Network Not Available
```
❌ Network not available
Please check your internet connection and try again
```
**Solution:** Check WiFi/internet and try again

### Browser Won't Launch
```
❌ Failed to launch browser
```
**Solution:** Ensure desktop shortcut exists: `Desktop/ixBrowser.lnk`

### Window Not Found
```
⚠  Could not detect browser window
⚠  Browser may be running, proceeding anyway...
```
**Solution:** Browser may be hidden or has different title. System will proceed.

### Load Timeout
```
⚠  Browser load timeout (page may still be loading)
```
**Solution:** Network is very slow. Manual interaction may be needed.

---

## Configuration

### Timeout Values (can be customized)

```python
# Browser window detection timeout
timeout=30  # seconds (find browser window)

# Page load timeout
timeout=60  # seconds (wait for page fully loaded)

# Network retry
max_retries=2  # attempts
```

### Popup Handling

All enabled by default. Handles:
- ✅ Cookie banners
- ✅ Notification permission popups
- ✅ Ad popups
- ✅ Generic popups (Escape key)

### Screenshot Cleanup

Automatic cleanup of old screenshots (> 1 hour old) to prevent disk bloat.

---

## Technical Details

### Screen Analysis Method

1. Takes screenshot every 2 seconds
2. Compares with previous screenshot (byte comparison)
3. If identical for 2 checks = page is loaded
4. More reliable than time-based waiting
5. Adapts to network speed automatically

### Popup Detection

Uses **behavioral automation** instead of OCR:
- Tries keyboard shortcuts (Escape, Tab, Enter)
- Tries mouse clicks on common close button locations
- Multiple fallback strategies
- No OCR needed (simpler, faster, more reliable)

### Screenshot Storage

```
modules/auto_uploader/data/screenshots/
├── screen_1730473200.png  (deleted after 1 hour)
├── screen_1730473202.png
└── screen_1730473204.png
```

Auto-deleted to prevent disk usage growth.

---

## Usage Example

```python
from browser_launcher import BrowserLauncher
from configuration import SettingsManager

settings = SettingsManager(...)
launcher = BrowserLauncher(settings)

# Launch with all features
browser_window = launcher.launch('ix', auto_handle_popups=True)

if browser_window:
    print("✅ Browser launched successfully")
else:
    print("❌ Browser launch failed")
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Browser not opening | Check desktop shortcut exists |
| Network timeout | Check internet connection |
| Window not found | Browser may be minimized or hidden |
| Popups not closing | Manual close required, try different popup |
| Slow launch | Normal for slow internet, wait longer |

---

## Future Enhancements

Possible additions (not implemented yet):
- 2FA/OTP detection and handling
- Login status detection
- Facebook page auto-navigation
- Video detection on page
- Performance metrics logging

