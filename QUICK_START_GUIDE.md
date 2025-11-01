# Quick Start Guide - Facebook Auto Uploader

## 🚀 Getting Started

### Step 1: Verify Setup
```bash
# Check if all required modules are present
cd "c:\Users\Fast Computers\automation\modules\auto_uploader"
ls -la | grep -E "(image_matcher|login_detector|mouse_activity|helper_images)"
```

Expected files:
- ✅ `image_matcher.py` - Template matching
- ✅ `login_detector.py` - Login detection
- ✅ `mouse_activity.py` - Visual feedback
- ✅ `helper_images/` folder with 5 PNG images

### Step 2: Prepare Login Data

Create `modules/auto_uploader/login_data.txt` with your Facebook credentials:

**Format 1: Pipe-separated (recommended)**
```
profile_name|email@example.com|password123|facebook_page_name|page_id|ix
```

**Format 2: Key-value**
```
browser: ix
email: email@example.com
password: password123
page_name: facebook_page_name
profile_name: my_profile
---
browser: ix
email: another@example.com
password: password456
page_name: another_page
```

### Step 3: Run the Application

```bash
# Option 1: Run from GUI
python modules/auto_uploader/gui.py

# Option 2: Run from command line
python modules/auto_uploader/core.py
```

### Step 4: Watch the Magic ✨

The bot will:
1. ✅ Check internet connection
2. ✅ Launch ixBrowser
3. ✅ Detect if you're logged in
4. ✅ If logged in: Logout automatically
5. ✅ If not logged in: Skip logout
6. ✅ Clear any old login data
7. ✅ Enter your new credentials
8. ✅ Wait for login to complete
9. ✅ Show you a circular mouse animation (visual feedback)
10. ✅ Handle popups (cookies, notifications, etc.)
11. ✅ Handle Exit Safely popup when closing

---

## 🔧 What Was Fixed

### Problem 1: Templates Not Loading
**Before**: Templates looked for in `data/templates/` but were in `helper_images/`
**After**: Auto-detects both locations, prefers `helper_images/`

### Problem 2: Exit Safely Popup
**Before**: Bot couldn't close the exit confirmation dialog
**After**: Automatically detects and closes "Exit Safely" popup using:
- Image detection (finds button location)
- Fallback to Alt+F4 if button click fails

### Problem 3: Old Login Data
**Before**: Old email/password from previous session remained in fields
**After**: Clears all fields before typing new credentials using Ctrl+A + Delete

---

## 📋 How Each Component Works

### 1. ImageMatcher (`image_matcher.py`)
Compares current screen with helper images using SSIM algorithm

**Helper Images Used**:
- `current_profile_cordinates.png` → "You are logged in" indicator
- `new_login_cordinates.png` → "Login form visible" indicator
- `current_profile_relatdOption_cordinates.png` → "Logout button" location
- `IXbrowser_exiteNotifiction_cordinates.png` → "Exit dialog" indicator

**Detection Accuracy**: 85%+ similarity match

### 2. LoginDetector (`login_detector.py`)
Uses ImageMatcher to determine login status

**Returns**:
- `LOGGED_IN` - User logged into Facebook
- `NOT_LOGGED_IN` - Login form visible, no user logged in
- `UNCLEAR` - Cannot determine status

### 3. MouseActivityIndicator (`mouse_activity.py`)
Shows circular mouse movement during operations

**Visual Pattern**:
```
     →→→
   ↙     ↖
  ↙       ↖
   ↖     ↙
     ←←←
```

Runs in background thread (non-blocking)

### 4. BrowserLauncher (`browser_launcher.py`)
Orchestrates all operations

**Login Flow**:
```
1. Check if logged in
   ↓
2. If YES → Logout
   ↓
3. Clear login fields
   ↓
4. Enter email + password
   ↓
5. Submit form
   ↓
6. Wait for confirmation
```

---

## 🔍 Troubleshooting

### Issue 1: "Template not found" warnings

**Solution**:
```bash
# Verify helper images exist
ls "c:\Users\Fast Computers\automation\modules\auto_uploader\helper_images"
```

Should show:
- current_profile_cordinates.png
- new_login_cordinates.png
- current_profile_relatdOption_cordinates.png
- IXbrowser_exiteNotifiction_cordinates.png

### Issue 2: Login detection always returns UNCLEAR

**Possible Causes**:
1. Helper images don't match your screen resolution
2. UI elements are positioned differently
3. Browser window is minimized or hidden

**Fix**:
1. Open ixBrowser and login manually
2. Take screenshot: `Shift + Windows + S`
3. Compare with helper_images/current_profile_cordinates.png
4. Update helper image if UI looks different

### Issue 3: Exit Safely popup not closing

**Solution**:
The bot tries three approaches:
1. Click button at center-right
2. Click button at bottom-right
3. Use Alt+F4 (keyboard shortcut)

If all fail:
```python
# You can manually close it by pressing:
# 1. Tab (to focus "Exit Safely" button)
# 2. Enter (to click it)
```

### Issue 4: Old login data still visible

**Solution**: Clear manually:
1. Open login form
2. Press Ctrl+A (select all)
3. Press Delete (clear)
4. Run bot again

---

## 🧪 Testing Checklist

Before using in production, test:

- [ ] **Network Check**
  - Run bot when offline → should fail with network error
  - Run bot when online → should pass

- [ ] **Browser Launch**
  - Watch ixBrowser launch from desktop
  - Window should maximize
  - See circular mouse animation

- [ ] **Login Detection**
  - **Logged In State**: Bot detects profile icon
  - **Not Logged In State**: Bot detects login form
  - **Mixed State**: Bot handles both correctly

- [ ] **Auto Logout**
  - Login manually
  - Run bot → should logout automatically
  - Check: Facebook page shows login form after

- [ ] **Auto Login**
  - Logout manually
  - Run bot with credentials → should login
  - Check: Facebook shows you are logged in after

- [ ] **Account Switching**
  - Login with Account A
  - Run bot with Account B credentials
  - Should logout A and login B
  - Check: You are now logged in as Account B

- [ ] **Exit Popup**
  - Close browser normally
  - "Exit Safely" dialog appears
  - Bot automatically closes it
  - Check: Browser window closes without error

- [ ] **Error Handling**
  - Try with wrong password → should show timeout after 30s
  - Try without internet → should fail early
  - Missing credentials → should use manual mode

---

## 📊 System Requirements

### Software
- Python 3.7+
- PyQt5 (for GUI)
- PyAutoGUI (for automation)
- PIL/Pillow (for images)
- scikit-image (for SSIM)
- NumPy (for arrays)

### Hardware
- Screen resolution: 1920x1080 (optimal)
- Mouse: Enabled and accessible
- Keyboard: Standard English layout

### Internet
- Stable connection for login
- Facebook accessible from your region

---

## 🎯 Advanced Usage

### Using with Selenium Integration

```python
from browser_launcher import BrowserLauncher
from configuration import SettingsManager

settings = SettingsManager(...)
launcher = BrowserLauncher(settings)

# Launch and login
launcher.launch('ix')
launcher.handle_facebook_login('email@example.com', 'password')

# Connect Selenium
driver = launcher.connect('ix')

# Use Selenium to upload videos
# driver.get('https://www.facebook.com/...')
# ... upload logic ...

# Clean up
launcher.close('ix', handle_exit_popup=True)
```

### Custom Template Directory

```python
from login_detector import LoginDetector
from pathlib import Path

# Use custom templates location
custom_templates = Path("C:/my_custom_templates")
detector = LoginDetector(custom_templates)
```

### Manual Login Detection

```python
from image_matcher import ImageMatcher

matcher = ImageMatcher()

# Take screenshot
screenshot = matcher.take_screenshot()

# Check login status
status = matcher.detect_login_status(screenshot)
print(f"Status: {status}")  # LOGGED_IN, NOT_LOGGED_IN, or UNCLEAR
```

---

## 📞 Support & Help

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
# Now you'll see detailed logs of all operations
```

### Check Logs

```bash
# Logs are saved in:
modules/auto_uploader/data/logs/

# View latest log:
tail -f modules/auto_uploader/data/logs/upload_*.log
```

### Common Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| "Network not available" | No internet | Check WiFi/connection |
| "Failed to launch browser" | ixBrowser not installed | Install ixBrowser |
| "Could not detect browser window" | Window not found | Check if browser launched |
| "Could not determine login status" | Templates not matching | Update helper images |
| "Login verification timeout" | Login taking too long | Check 2FA, internet speed |
| "Could not find logout button" | Logout failed | Try manual logout |

---

## 🚀 Performance Tips

1. **Faster Login**: Ensure stable internet connection
2. **Better Detection**: Use matching screen resolution (1920x1080)
3. **Smooth Animation**: Run on system with decent specs
4. **Fewer Errors**: Keep helper images updated

---

## 📝 Notes

- Bot logs every step to console and log file
- All coordinates are calculated from screen center
- Activity indicator runs in background (doesn't block other operations)
- Templates are cached in memory after first load
- Safe to run multiple times (previous state is detected and handled)

---

## 🎉 You're Ready!

Everything is set up and working. Now you can:
1. Add your Facebook credentials to login_data.txt
2. Run the bot
3. Watch it automatically login and handle uploads
4. Enjoy automated Facebook video uploading!

**Happy uploading! 🚀**
