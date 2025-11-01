# Facebook Automation Workflow - Usage Guide (اردو اور English)

## Quick Start / جلدی شروع کریں

### English Version

#### Basic Usage

```python
from pathlib import Path
from modules.auto_uploader.facebook_steps import run_workflow

# Run the complete workflow
run_workflow(Path("./data"))
```

#### Detailed Usage with Error Handling

```python
from pathlib import Path
from modules.auto_uploader.facebook_steps import (
    FacebookAutomationWorkflow,
    WorkflowError,
    CredentialsError,
    ShortcutError,
    BrowserLaunchError,
)

try:
    data_folder = Path("./data")
    workflow = FacebookAutomationWorkflow(data_folder)
    workflow.run()
    print("✓ Workflow completed successfully!")

except CredentialsError as e:
    print(f"❌ Credentials Error: {e}")
    print("  → Check if login_data.txt exists and has correct format")

except ShortcutError as e:
    print(f"❌ Shortcut Error: {e}")
    print("  → Browser shortcut not found on desktop")

except BrowserLaunchError as e:
    print(f"❌ Browser Launch Error: {e}")
    print("  → Browser failed to launch or window could not be found")

except WorkflowError as e:
    print(f"❌ Workflow Error: {e}")
    print("  → Check logs for details")
```

#### Step-by-Step Usage

If you want to run each step individually:

```python
from pathlib import Path
from modules.auto_uploader.facebook_steps import (
    load_credentials,
    find_shortcut,
    open_shortcut,
    maximize_window,
    check_session,
    SessionStatus,
    login,
    logout,
    human_delay,
)

data_folder = Path("./data")

# STEP 1: Load credentials
print("Step 1: Loading credentials...")
credentials = load_credentials(data_folder)
print(f"✓ Browser: {credentials.browser}")
print(f"✓ Email: {credentials.email}")

# STEP 2: Find shortcut
print("\nStep 2: Finding browser shortcut...")
shortcut = find_shortcut(credentials.browser)
print(f"✓ Shortcut found: {shortcut}")

# STEP 3: Open and maximize
print("\nStep 3: Opening browser and maximizing...")
open_shortcut(shortcut)
maximize_window(credentials.browser)
print("✓ Browser ready")

# STEP 4: Check session
print("\nStep 4: Checking login session...")
human_delay(3, "Waiting for page to load...")
session = check_session()
print(f"✓ Session status: {session.value}")

# STEP 5: Handle login/logout
print("\nStep 5: Handling login/logout...")
if session == SessionStatus.LOGGED_IN:
    print("  → Already logged in, logging out first...")
    logout()
    human_delay(2)

print("  → Logging in with provided credentials...")
login(credentials)
print("✓ Login complete")
```

---

### اردو ورژن

#### بنیادی استعمال

```python
from pathlib import Path
from modules.auto_uploader.facebook_steps import run_workflow

# مکمل ورک فلو چلائیں
run_workflow(Path("./data"))
```

#### غلطی سے نمٹنے کے ساتھ تفصیلی استعمال

```python
from pathlib import Path
from modules.auto_uploader.facebook_steps import (
    FacebookAutomationWorkflow,
    WorkflowError,
    CredentialsError,
    ShortcutError,
    BrowserLaunchError,
)

try:
    data_folder = Path("./data")
    workflow = FacebookAutomationWorkflow(data_folder)
    workflow.run()
    print("✓ ورک فلو کامیابی سے مکمل ہوگیا!")

except CredentialsError as e:
    print(f"❌ رسائی کی معلومات میں خرابی: {e}")
    print("  → چیک کریں کہ login_data.txt موجود ہے اور صحیح فارمیٹ میں ہے")

except ShortcutError as e:
    print(f"❌ شارٹ کٹ نہیں ملا: {e}")
    print("  → براہ کرم براؤزر کا شارٹ کٹ ڈیسک ٹاپ پر رکھیں")

except BrowserLaunchError as e:
    print(f"❌ براؤزر کھولنے میں خرابی: {e}")
    print("  → براؤزر نہیں کھل سکا یا ونڈو نہیں ملی")

except WorkflowError as e:
    print(f"❌ ورک فلو میں خرابی: {e}")
    print("  → تفصیلات کے لیے لاگز دیکھیں")
```

#### مرحلہ وار استعمال

اگر آپ ہر مرحلہ الگ الگ چلانا چاہتے ہیں:

```python
from pathlib import Path
from modules.auto_uploader.facebook_steps import (
    load_credentials,
    find_shortcut,
    open_shortcut,
    maximize_window,
    check_session,
    SessionStatus,
    login,
    logout,
    human_delay,
)

data_folder = Path("./data")

# مرحلہ 1: رسائی کی معلومات لوڈ کریں
print("مرحلہ 1: رسائی کی معلومات لوڈ ہو رہی ہیں...")
credentials = load_credentials(data_folder)
print(f"✓ براؤزر: {credentials.browser}")
print(f"✓ ای میل: {credentials.email}")

# مرحلہ 2: شارٹ کٹ تلاش کریں
print("\nمرحلہ 2: براؤزر شارٹ کٹ تلاش ہو رہا ہے...")
shortcut = find_shortcut(credentials.browser)
print(f"✓ شارٹ کٹ ملا: {shortcut}")

# مرحلہ 3: کھولیں اور بڑا کریں
print("\nمرحلہ 3: براؤزر کھول رہے ہیں اور بڑا کر رہے ہیں...")
open_shortcut(shortcut)
maximize_window(credentials.browser)
print("✓ براؤزر تیار ہے")

# مرحلہ 4: سیشن چیک کریں
print("\nمرحلہ 4: لاگ ان سیشن چیک ہو رہا ہے...")
human_delay(3, "صفحہ لوڈ ہونے کا انتظار کیا جا رہا ہے...")
session = check_session()
print(f"✓ سیشن کی حالت: {session.value}")

# مرحلہ 5: لاگ ان/لاگ آؤٹ سنبھالیں
print("\nمرحلہ 5: لاگ ان/لاگ آؤٹ سنبھالا جا رہا ہے...")
if session == SessionStatus.LOGGED_IN:
    print("  → پہلے سے لاگ ان ہے، پہلے لاگ آؤٹ کر رہے ہیں...")
    logout()
    human_delay(2)

print("  → فراہم کردہ رسائی کی معلومات سے لاگ ان ہو رہے ہیں...")
login(credentials)
print("✓ لاگ ان مکمل")
```

---

## Setup Requirements / ضروری سیٹ اپ

### login_data.txt File Format

**Location:** `./data/login_data.txt`

**Format:**
```
browser: Chrome
email: your.email@facebook.com
password: YourPassword123
```

**Supported Browsers:**
- Chrome
- Firefox
- Edge
- IX Browser
- GoLogin
- Incogniton
- Orbita

### Required Image Files

Place these screenshot images in `./modules/auto_uploader/helper_images/`:

1. **current_profile_cordinates.png** - Profile icon (for detecting logged-in state)
2. **new_login_cordinates.png** - Login form (for detecting logged-out state)
3. **current_profile_relatdOption_cordinates.png** - Logout option

These images are used for automated detection of the current login state.

### Python Requirements

```bash
pip install pyautogui pygetwindow pillow opencv-python
```

---

## Example: Integration into Larger Script

### English Example

```python
#!/usr/bin/env python3
"""Main script to automate Facebook uploads."""

import logging
from pathlib import Path
from modules.auto_uploader.facebook_steps import (
    run_workflow,
    WorkflowError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("facebook_automation.log"),
        logging.StreamHandler(),
    ]
)

def main():
    """Main entry point."""
    try:
        logging.info("=" * 70)
        logging.info("Starting Facebook Automation")
        logging.info("=" * 70)

        data_folder = Path("./data")
        run_workflow(data_folder)

        logging.info("=" * 70)
        logging.info("Facebook Automation Complete!")
        logging.info("=" * 70)

        # Continue with next automation steps...
        logging.info("Proceeding to next task...")
        # upload_content()
        # post_to_facebook()

    except WorkflowError as e:
        logging.error(f"Workflow failed: {e}")
        return 1
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
```

### اردو مثال

```python
#!/usr/bin/env python3
"""فیس بک اپ لوڈس کو خودکار بنانے کی اہم تدوین۔"""

import logging
from pathlib import Path
from modules.auto_uploader.facebook_steps import (
    run_workflow,
    WorkflowError,
)

# لاگنگ ترتیب دیں
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("facebook_automation.log"),
        logging.StreamHandler(),
    ]
)

def main():
    """اہم داخل نقطہ۔"""
    try:
        logging.info("=" * 70)
        logging.info("فیس بک خودکار شروع ہو رہا ہے")
        logging.info("=" * 70)

        data_folder = Path("./data")
        run_workflow(data_folder)

        logging.info("=" * 70)
        logging.info("فیس بک خودکار مکمل ہوگیا!")
        logging.info("=" * 70)

        # اگلی خودکاری کے مراحل پر جائیں...
        logging.info("اگلے کام پر جا رہے ہیں...")
        # upload_content()
        # post_to_facebook()

    except WorkflowError as e:
        logging.error(f"ورک فلو ناکام: {e}")
        return 1
    except Exception as e:
        logging.error(f"غیر متوقع خرابی: {e}", exc_info=True)
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
```

---

## Troubleshooting / مسائل کا حل

### Problem: "login_data.txt not found"
**Solution:** Ensure the file exists at `./data/login_data.txt` with the correct format.

**مسئلہ:** "login_data.txt نہیں ملا"
**حل:** یقینی بنائیں کہ فائل `./data/login_data.txt` پر موجود ہے۔

---

### Problem: "Could not find shortcut for 'Chrome'"
**Solution:**
1. Go to Desktop
2. Right-click the browser
3. Create a shortcut if it doesn't exist
4. Ensure the shortcut name matches a known pattern

**مسئلہ:** "Chrome کا شارٹ کٹ نہیں ملا"
**حل:**
1. ڈیسک ٹاپ پر جائیں
2. براؤزر پر دائیں کلک کریں
3. شارٹ کٹ بنائیں اگر موجود نہ ہو
4. شارٹ کٹ کا نام معروف نمونہ سے ملے

---

### Problem: "Could not find window for browser"
**Solution:**
1. Increase the retry count in `maximize_window()`
2. Check that the browser is actually starting
3. Increase the wait time in `open_shortcut()`

**مسئلہ:** "براؤزر کی ونڈو نہیں ملی"
**حل:**
1. `maximize_window()` میں دوبارہ کوشش کی تعداد بڑھائیں
2. چیک کریں کہ براؤزر واقعی شروع ہو رہا ہے
3. `open_shortcut()` میں انتظار کا وقت بڑھائیں

---

### Problem: "Image lookup failed"
**Solution:**
1. Ensure reference images exist in `helper_images/` folder
2. Images must be accurate screenshots of the current Facebook UI
3. Check image file permissions
4. Increase confidence threshold if images are slightly different

**مسئلہ:** "تصویر کی تلاش ناکام"
**حل:**
1. یقینی بنائیں کہ حوالہ تصویریں `helper_images/` فولڈر میں موجود ہیں
2. تصویریں موجودہ فیس بک یوآئی کی درست اسکرین شاٹ ہونی چاہیں
3. تصویر فائل کی اجازتیں چیک کریں
4. اگر تصویریں قدرے مختلف ہوں تو اعتماد کی حد بڑھائیں

---

## Advanced Configuration

### Custom Wait Times

```python
from modules.auto_uploader.facebook_steps import (
    open_shortcut,
    maximize_window,
)

# Increase wait time for slow systems
open_shortcut(shortcut, wait_seconds=20)

# Increase retries for finding window
maximize_window(browser_name, max_retries=5, retry_wait_seconds=6)
```

### Custom Typing Speed

```python
from modules.auto_uploader.facebook_steps import login

# Slower typing (more human-like)
login(credentials, typing_interval=0.1)

# Faster typing
login(credentials, typing_interval=0.02)
```

### Image Detection Confidence

```python
from modules.auto_uploader.facebook_steps import check_session

# Stricter matching (fewer false positives)
status = check_session(confidence=0.95)

# Looser matching (better for different displays)
status = check_session(confidence=0.60)
```

---

## Support

For detailed information, see:
- `README_STRUCTURE.md` - Complete architecture guide
- Python logging output - Check logs for detailed execution information
- `modules/auto_uploader/facebook_steps/` - Read docstrings in source files

تفصیلی معلومات کے لیے دیکھیں:
- `README_STRUCTURE.md` - مکمل ڈیزائن گائیڈ
- Python لاگنگ آؤٹ پٹ - تفصیلی عمل کی معلومات کے لیے لاگز چیک کریں
- `modules/auto_uploader/facebook_steps/` - ماخذ فائلوں میں دستاویزات پڑھیں
