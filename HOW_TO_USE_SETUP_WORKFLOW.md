# کیسے استعمال کریں - Setup Workflow / How to Use - Setup Workflow

## مسئلہ / Problem

آپ نے کہا:
- User کو شروع میں پوچھو کہاں files ہیں
- `login_data.txt` کا path hardcoded نہ ہو
- پرانی files delete کریں

## حل / Solution

### نیا نظام / New System

```
پہلی بار / First Time:
  User شروع کرے (Start button دبائے)
    ↓
  System پوچھے: "login_data.txt کہاں ہے؟"
    ↓
  User بتائے (C:\Users\...\data)
    ↓
  System save کرے (~/.facebook_automation_setup.json)
    ↓
  Automation چلے

اگلی دفعہ / Next Time:
  User شروع کرے
    ↓
  System saved paths استعمال کرے
    ↓
  No questions asked
    ↓
  Automation چلے
```

---

## کیسے Use کریں / How to Use

### آپ کے GUI میں / In Your GUI

جب user "Start Upload" button دبائے:

```python
from modules.auto_uploader.facebook_steps import start_automation

# بس ایک لائن! / Just one line!
if start_automation():
    print("✓ Success - User is logged in")
    # اب upload کریں
else:
    print("❌ Failed - Check errors above")
```

### یہ کیا کرتا ہے / What It Does

1. **پہلی بار / First Time:**
   - User سے پوچھے: login_data.txt کہاں ہے؟
   - User سے پوچھے: Browser shortcut کہاں ہے؟
   - Paths save کرے

2. **ہر بار / Every Time:**
   - Credentials load کرے
   - Shortcut تلاش کرے
   - Browser کھولے
   - Login check کرے
   - Login کرے

---

## مثالیں / Examples

### سادہ ترین / Simplest

```python
from modules.auto_uploader.facebook_steps import start_automation

# یہ سب کچھ خود کرتا ہے!
start_automation()
```

### اختیارات کے ساتھ / With Options

```python
from modules.auto_uploader.facebook_steps import start_automation

# دوبارہ setup پوچھو (اگر paths بدل گئے)
start_automation(force_setup=True)
```

### مکمل کنٹرول / Full Control

```python
from modules.auto_uploader.facebook_steps import WorkflowWithSetup

workflow = WorkflowWithSetup()

# Step 1: Setup (ask user)
if not workflow.setup():
    print("Setup failed")
    exit(1)

# Step 2: Run automation
if not workflow.run():
    print("Automation failed")
    exit(1)

print("✓ Success!")
```

---

## Setup File کہاں ہے / Where Setup File Is

```
~/.facebook_automation_setup.json
```

مطلب / Means:
```
C:\Users\YourName\.facebook_automation_setup.json
```

اندر / Inside:
```json
{
  "login_data_path": "C:\\Users\\YourName\\Desktop\\data",
  "desktop_path": "C:\\Users\\YourName\\Desktop",
  "setup_date": "1699..."
}
```

---

## دوبارہ Setup کریں / Reset Setup

اگر user paths بدلنا چاہے:

```python
from modules.auto_uploader.facebook_steps import SetupManager

# Delete saved setup
SetupManager.reset_setup()

# Next time: Will ask again
```

یا:

```python
# Force ask again
start_automation(force_setup=True)
```

---

## Current Setup دیکھیں / View Current Setup

```python
from modules.auto_uploader.facebook_steps import SetupManager

# دکھائیں current setup
SetupManager.show_setup()
```

Output:
```
======================================================================
📋 Current Setup
======================================================================
  login_data_path: C:\Users\YourName\Desktop\data
  desktop_path: C:\Users\YourName\Desktop
  setup_date: 1699...
======================================================================
```

---

## Test کریں / Test It

```bash
cd c:\Users\Fast Computers\automation
python SIMPLE_USAGE_EXAMPLE.py
```

یہ:
1. پہلی بار: Setup پوچھے گا
2. اگلی بار: Setup use کرے گا
3. سب کچھ خود ہو جائے گا

---

## اگر Error آئے / If Error Occurs

### "Path does not exist"
- Check کریں کہ path صحیح ہے
- مثال: `C:\Users\YourName\Desktop\data`

### "login_data.txt not found"
- Check کریں فائل موجود ہے
- یا setup دوبارہ کریں

### "Browser shortcut not found"
- Check کریں shortcut Desktop پر ہے
- یا صحیح Desktop path دیں

---

## Flow Diagram

```
┌────────────────────────┐
│   User clicks Start    │
└────────────┬───────────┘
             │
             ↓
    ┌────────────────────┐
    │ Is setup saved?    │
    └────┬──────────┬────┘
         │ Yes      │ No
         │          │
         ↓          ↓
    ┌───────┐  ┌──────────────────────┐
    │ Use   │  │ Ask user for paths:  │
    │saved  │  │ - login_data.txt     │
    │paths  │  │ - browser shortcut   │
    └───┬───┘  └──────────┬───────────┘
        │                 │
        │                 ↓
        │            ┌──────────────────┐
        │            │ Save paths to:   │
        │            │ ~/.facebook...   │
        │            └────────┬─────────┘
        │                     │
        └─────────┬───────────┘
                  │
                  ↓
        ┌─────────────────────┐
        │ Load Credentials    │
        │ Find Shortcut       │
        │ Open Browser        │
        │ Check Session       │
        │ Login if needed     │
        └────────┬────────────┘
                 │
        ✓ or ❌
                 │
                 ↓
        Return True / False
```

---

## Code Structure

```
modules/auto_uploader/facebook_steps/

Step 1-5: Individual steps (پہلے سے موجود)
↓
workflow_main.py: Combines steps
↓
setup_manager.py: Save/load paths ← NEW!
↓
workflow_with_setup.py: Complete flow with setup ← NEW!
↓
__init__.py: Export start_automation ← UPDATED!
```

---

## خلاصہ / Summary

| پہلے / Before | اب / Now |
|---|---|
| Hardcoded paths | User سے پوچھتا ہے |
| Setup پوچھو ہر بار | صرف پہلی بار |
| Complex config | سادہ input |
| Manual paths | Auto save/load |

---

## استعمال کریں / Use It

### GUI سے / From GUI:

```python
# جب user "Start Upload" دبائے
from modules.auto_uploader.facebook_steps import start_automation

success = start_automation()
if success:
    # اب اگلا step کریں
    upload_content()
```

### Script سے / From Script:

```python
from SIMPLE_USAGE_EXAMPLE import main

if main():
    print("Ready to upload!")
```

---

## اگلے قدم / Next Steps

1. **Test کریں:**
   ```bash
   python SIMPLE_USAGE_EXAMPLE.py
   ```

2. **اپنے GUI میں integrate کریں:**
   ```python
   from modules.auto_uploader.facebook_steps import start_automation
   ```

3. **User paths ask کریں اور save کریں - خود ہو جاتا ہے!**

---

**اب سب کچھ automatic ہے!** ✨
