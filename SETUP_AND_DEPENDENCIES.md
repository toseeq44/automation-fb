# مکمل سیٹ اپ گائیڈ - Complete Setup Guide

## 🔴 اہم / CRITICAL: Required Python Packages

Bot کو کام کرنے کے لیے یہ packages ضروری ہیں:

### Required (ضروری)
```bash
pip install pyautogui          # Mouse/keyboard automation
pip install pygetwindow        # Window detection
pip install opencv-python      # Image template matching
pip install Pillow            # Image handling
pip install numpy             # Array operations
```

### Optional (اختیاری - but recommended)
```bash
pip install PyQt5             # GUI interface
pip install requests          # API calls
```

## ⚡ Quick Installation

```bash
# Copy this entire command and run it
pip install pyautogui pygetwindow opencv-python Pillow numpy PyQt5

# Verify installation
python -c "import cv2; import pyautogui; import pygetwindow; print('All packages installed successfully!')"
```

---

## 📁 Project Structure

Ensure these folders exist:

```
c:\Users\Fast Computers\automation\
├── modules\
│   └── auto_uploader\
│       ├── helper_images\          ← CRITICAL: 5 PNG images MUST be here
│       │   ├── current_profile_cordinates.png
│       │   ├── new_login_cordinates.png
│       │   ├── current_profile_relatdOption_cordinates.png
│       │   ├── IXbrowser_exiteNotifiction_cordinates.png
│       │   └── already_userLoginSave_screen_cordintaes.png
│       ├── data\
│       │   ├── settings.json
│       │   ├── login_data.txt        ← Your Facebook credentials here
│       │   ├── logs\                 ← Logs are saved here
│       │   ├── screenshots\          ← Temp screenshots
│       │   └── debug_screenshots\    ← Debug images
│       ├── image_matcher.py          ← Template matching (FIXED)
│       ├── login_detector.py
│       ├── browser_launcher.py       ← Browser automation (FIXED)
│       ├── browser_monitor.py
│       ├── screen_analyzer.py
│       ├── mouse_activity.py
│       ├── core.py
│       ├── gui.py
│       └── ...other files
└── ...other folders
```

---

## 🔍 What's Different in This Version

### FIXED: Image Matcher
**Old Problem**: Used SSIM algorithm which required scikit-image
**New Solution**: Uses OpenCV (cv2.matchTemplate) which is more reliable

```python
# BEFORE:
from skimage.metrics import structural_similarity as ssim  # ❌ Error if not installed

# AFTER:
import cv2  # ✅ Works with opencv-python
```

### IMPROVED: Browser Launch
**Old Problem**: Clicked too early before page loaded
**New Solution**: Waits properly for browser window + extra 5 seconds for elements to load

```python
# BEFORE:
window = monitor.find_browser_window(patterns, timeout=30)
# Immediately continues...

# AFTER:
window = monitor.find_browser_window(patterns, timeout=60)  # Longer wait
time.sleep(5)  # Extra time for page elements
```

### IMPROVED: Exit Popup Handling
**Now includes**: Better detection and multiple close methods

---

## 📱 Before Starting

### Step 1: Install OpenCV (Most Important!)

```bash
# This is the KEY package for image template matching
pip install opencv-python

# Verify it installed correctly
python -c "import cv2; print(f'OpenCV version: {cv2.__version__}')"
```

### Step 2: Install All Dependencies

```bash
pip install pyautogui pygetwindow opencv-python Pillow numpy PyQt5
```

### Step 3: Verify All Packages

```bash
python << 'EOF'
import sys

packages = [
    ('pyautogui', 'Mouse/Keyboard automation'),
    ('pygetwindow', 'Window detection'),
    ('cv2', 'Image matching (OpenCV)'),
    ('PIL', 'Image handling'),
    ('numpy', 'Array operations'),
    ('PyQt5', 'GUI'),
]

print("Package Status:")
print("=" * 50)

all_ok = True
for package, description in packages:
    try:
        __import__(package)
        print(f"✅ {package:15} - {description}")
    except ImportError:
        print(f"❌ {package:15} - {description}")
        all_ok = False

print("=" * 50)
if all_ok:
    print("✅ All packages installed successfully!")
else:
    print("❌ Some packages missing. Run:")
    print("pip install pyautogui pygetwindow opencv-python Pillow numpy PyQt5")
EOF
```

### Step 4: Check Helper Images

```bash
# Windows Command:
dir "c:\Users\Fast Computers\automation\modules\auto_uploader\helper_images"

# Should show 5 PNG files:
# - current_profile_cordinates.png
# - new_login_cordinates.png
# - current_profile_relatdOption_cordinates.png
# - IXbrowser_exiteNotifiction_cordinates.png
# - already_userLoginSave_screen_cordintaes.png
```

If images missing, copy them from wherever you have them.

---

## ⚙️ Configuration

### File 1: login_data.txt

Location: `modules/auto_uploader/data/login_data.txt`

Format (pipe-separated):
```
profile_name|facebook_email|facebook_password|facebook_page_name|page_id|browser_type
```

Example:
```
account1|myemail@gmail.com|mypassword123|My Page Name|1234567|ix
account2|another@gmail.com|password456|Another Page|7654321|ix
```

### File 2: settings.json

Already configured, but check:
```json
{
  "automation": {
    "mode": "free_automation",
    "setup_completed": true,
    "paths": {
      "creators_root": "C:\\Users\\Fast Computers\\Desktop\\Toseeq Links Grabber",
      "shortcuts_root": "C:\\Users\\Fast Computers\\Desktop\\creator_shortcuts",
      "history_file": "C:\\Users\\Fast Computers\\automation\\modules\\auto_uploader\\data\\history.json"
    }
  },
  "browsers": {
    "ix": {
      "enabled": true,
      "exe_path": "C:\\Users\\{user}\\AppData\\Local\\Programs\\Incogniton\\Incogniton.exe"
    }
  }
}
```

---

## 🚀 Running the Bot

### Method 1: Using GUI (Recommended)

```bash
cd "c:\Users\Fast Computers\automation"
python modules/auto_uploader/gui.py
```

Then:
1. Click "Configure Settings" button
2. Add your login data in login_data.txt
3. Click "Start Upload"
4. Watch the bot work!

### Method 2: Command Line

```bash
cd "c:\Users\Fast Computers\automation"
python modules/auto_uploader/core.py
```

### Method 3: Debug Mode (See detailed logs)

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from modules.auto_uploader.core import FacebookAutoUploader
uploader = FacebookAutoUploader()
uploader.run()
```

---

## 🔧 Troubleshooting

### Error: "OpenCV not available"

**Solution**:
```bash
pip install opencv-python

# If still fails:
pip install --upgrade opencv-python
```

### Error: "Window not found"

**Reason**: ixBrowser didn't launch
**Solution**:
1. Check ixBrowser is installed
2. Check it's in correct path: `C:\Users\{user}\AppData\Local\Programs\Incogniton\`
3. Try launching ixBrowser manually first

### Error: "Templates not found"

**Reason**: Helper images missing
**Solution**:
```bash
# Check images exist
dir "c:\Users\Fast Computers\automation\modules\auto_uploader\helper_images"

# If missing, ask user to provide them
```

### Error: "Could not determine login status"

**Reason**: Templates don't match current screen
**Solution**:
1. Take screenshot of login page
2. Compare with helper images
3. Update helper image if needed

---

## 📝 Step-by-Step Startup

### Before First Run

```
✅ 1. Python installed (3.7+)
✅ 2. pip install packages (see above)
✅ 3. Helper images in correct folder
✅ 4. login_data.txt with your credentials
✅ 5. ixBrowser installed
```

### First Run

```
1. Open Terminal/CMD
2. cd "c:\Users\Fast Computers\automation"
3. python modules/auto_uploader/gui.py
4. Wait for GUI window
5. Click "Configure Settings" (if first time)
6. Click "Start Upload"
7. Watch console for detailed logs
```

### Expected Console Output

```
============================================================
🚀 Browser Launch Process
============================================================

1️⃣  Checking network connectivity...
✓ Network connectivity: OK

2️⃣  Launching browser...
✓ Launched ix from ixBrowser.lnk

3️⃣  Waiting for browser to be ready...
🔍 Searching for browser window...
✓ Found browser window: ixBrowser
⏳ Waiting for browser to fully load...
✓ Browser fully loaded

4️⃣  Maximizing window...
✓ Browser window maximized

5️⃣  Handling popups and notifications...
🍪 Handling cookie banner...
  ✓ Cookie banner closed

6️⃣  Detecting login status...
🔍 Analyzing login status...
✓ Detected logged-in status (profile icon visible)

✅ Browser Launch Complete
```

---

## 🎯 Verification Checklist

### Before Running

- [ ] Python 3.7+ installed
- [ ] All pip packages installed
- [ ] 5 helper PNG images in `helper_images/` folder
- [ ] login_data.txt has your credentials
- [ ] ixBrowser installed
- [ ] Internet connection working
- [ ] No other bot running (only one at a time)

### After Starting

- [ ] GUI window opens
- [ ] No errors in console
- [ ] "Start Upload" button is clickable
- [ ] Browser launches when you click start
- [ ] Browser window appears on screen
- [ ] Console shows step-by-step progress

### During Execution

- [ ] Network check passes ✓
- [ ] Browser launches ✓
- [ ] Browser window found ✓
- [ ] Waiting messages appear
- [ ] Login status detected
- [ ] No stuck/hanging messages

---

## 🚨 If Something Goes Wrong

### Step 1: Check Logs

```bash
# Logs are saved in:
c:\Users\Fast Computers\automation\modules\auto_uploader\data\logs\

# View latest log:
# Find the newest file with name upload_YYYYMMDD_HHMMSS.log
# Open it in any text editor
```

### Step 2: Enable Debug Logging

Change in code temporarily:
```python
# In core.py or gui.py
logging.basicConfig(level=logging.DEBUG)  # Shows everything
```

### Step 3: Check Helper Images

```bash
# Make sure all 5 images exist:
dir "c:\Users\Fast Computers\automation\modules\auto_uploader\helper_images"

# Should show:
# current_profile_cordinates.png
# new_login_cordinates.png
# current_profile_relatdOption_cordinates.png
# IXbrowser_exiteNotifiction_cordinates.png
# already_userLoginSave_screen_cordintaes.png
```

### Step 4: Verify OpenCV

```bash
python -c "import cv2; print('OpenCV OK'); print(cv2.matchTemplate.__doc__)"
```

---

## 📞 Support

If stuck:
1. Check this guide first
2. Read console error messages carefully
3. Check log files in `data/logs/`
4. Verify all packages with verification script above

---

## 🎉 You're Ready!

Once all dependencies are installed and setup complete, your bot will:
- ✅ Launch ixBrowser automatically
- ✅ Detect if you're logged in or not
- ✅ Auto-logout if needed
- ✅ Auto-login with new credentials
- ✅ Handle popups automatically
- ✅ Close browser safely
- ✅ Upload videos (final step, not yet implemented)

**Happy uploading!** 🚀
