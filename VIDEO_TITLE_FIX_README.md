# Video Title Input Fix - Complete Solution

## Problem Summary

Your video upload was working perfectly up to a point:

✅ **WORKING:**
- Page loaded successfully
- Found 7 clickable elements
- Located "Add videos" button
- File sent to uploader
- Upload progress monitored (5% → 100%)
- Upload completed successfully

❌ **ISSUE:**
- Could not set video title
- All XPath selectors returned empty results:
  - `//input[@placeholder='Title']`
  - `//input[@name='title']`
  - `//input[@aria-label contains 'Title']`
  - `//textarea[@placeholder contains 'describe your reel']`

## Root Cause

Facebook's upload interface uses **dynamic DOM elements** that:
1. May load asynchronously after upload completes
2. Could be `contenteditable` divs instead of input/textarea
3. Have varying placeholder text depending on upload type (Reels vs Video vs Story)
4. Require proper wait conditions before interacting

## The Solution

I've created a comprehensive `VideoTitleSetter` class that:

### ✨ Features

1. **30+ Selector Strategies** - Tries multiple XPath and CSS selectors
2. **Smart Wait Conditions** - Waits for upload to complete before searching
3. **Multiple Input Types** - Handles textarea, input, and contenteditable divs
4. **Fallback Strategies** - Context-based searching when standard selectors fail
5. **JavaScript Fallback** - Uses JS to set values when normal methods fail
6. **Description Support** - Can also set video description
7. **Detailed Logging** - Shows exactly which selector worked or why it failed

### 📁 Files Created

1. **`modules/auto_uploader/browser/video_upload_workflow/title_setter.py`**
   - Main VideoTitleSetter class
   - Comprehensive selector strategies
   - Robust error handling

2. **`test_title_setter.py`**
   - Test script and examples
   - Integration demonstrations
   - Usage patterns

## How to Use

### Method 1: Quick Integration (Standalone)

```python
from selenium import webdriver
from modules.auto_uploader.browser.video_upload_workflow.title_setter import VideoTitleSetter

# After your video upload completes...

# Create title setter with your existing Selenium driver
title_setter = VideoTitleSetter(driver, max_wait=30)

# Set the title (and optionally description)
success = title_setter.set_video_title(
    title="Amazing Social Experiment - Acts of Kindness",
    description="Watch this heartwarming video! #kindness #wholesome"
)

if success:
    print("✅ Title set successfully!")
else:
    print("❌ Failed to set title - check logs for details")
```

### Method 2: Integration with Your Workflow

Add this to your existing upload workflow (after file upload completes):

```python
# Your existing workflow
# 1. Open browser ✅
# 2. Navigate to page ✅
# 3. Click "Add Videos" button ✅
# 4. Upload file ✅
# 5. Monitor progress (5% → 100%) ✅

# NEW STEP 6: Set title
from modules.auto_uploader.browser.video_upload_workflow.title_setter import VideoTitleSetter

title_setter = VideoTitleSetter(driver)

# Load video metadata (from your JSON or config)
video_metadata = {
    "title": "Social Experiment - Random Acts of Kindness",
    "description": "Spreading positivity #kindness #socialexperiment"
}

# Set title
title_setter.set_video_title(
    title=video_metadata["title"],
    description=video_metadata["description"]
)

# 7. Click publish button
# 8. Done!
```

### Method 3: Integration with Orchestrator

If you're using the `UploadWorkflowOrchestrator`, add Phase 5:

```python
# In workflow_orchestrator.py

from .title_setter import VideoTitleSetter

class UploadWorkflowOrchestrator:
    def __init__(self, profiles_root, helper_images_path, driver=None):
        # ... existing initialization ...
        self.videos_finder = AddVideosFinder(helper_images_path)

        # Add title setter
        self.title_setter = VideoTitleSetter(driver, max_wait=30)

    def execute_workflow(self, profile_id, video_metadata=None):
        # ... Phase 1-4 existing code ...

        # PHASE 5: Set Video Title
        logger.info("\n[ORCHESTRATOR] ═════════════════════════════")
        logger.info("[ORCHESTRATOR] PHASE 5: Set Video Title")
        logger.info("[ORCHESTRATOR] ═════════════════════════════")

        if video_metadata and video_metadata.get("title"):
            self.title_setter.set_driver(driver)  # Update driver if needed

            success = self.title_setter.set_video_title(
                title=video_metadata["title"],
                description=video_metadata.get("description")
            )

            if success:
                logger.info("[ORCHESTRATOR] ✅ Title set successfully")
            else:
                logger.warning("[ORCHESTRATOR] ⚠️ Failed to set title")
        else:
            logger.info("[ORCHESTRATOR] ⚠️ No title metadata provided")

        # Continue with publish/submit...
```

## Testing

### Test with Existing Browser

```bash
# Make sure you have a Chrome/ixBrowser running with debugging port 9223
python test_title_setter.py
```

Choose option 1 to test with actual browser connection.

### View Examples

```bash
python test_title_setter.py
```

Choose option 2 or 3 to see integration examples.

## What Makes This Solution Robust?

### 1. Comprehensive Selectors (30+ strategies)

The title setter tries multiple approaches in order:

**XPath Selectors:**
- Exact match: `//textarea[@placeholder='Title']`
- Case insensitive: `//textarea[contains(@placeholder, 'itle')]`
- Name attribute: `//textarea[@name='title']`
- Aria-label: `//textarea[@aria-label='Title']`
- Facebook-specific: `//textarea[contains(@placeholder, 'describe your')]`
- Contenteditable divs: `//div[@contenteditable='true' and @role='textbox']`

**CSS Selectors:**
- `textarea[placeholder*='itle']`
- `div[contenteditable='true'][role='textbox']`

**Fallback:**
- First visible textarea
- Context-based search (looks for upload-related text near inputs)

### 2. Smart Waiting

```python
# Waits for upload progress to complete
self._wait_for_upload_completion()

# Then searches for title input
# Uses WebDriverWait for each selector attempt
wait = WebDriverWait(self.driver, 3)
element = wait.until(EC.presence_of_element_located(...))
```

### 3. Multiple Input Methods

```python
# Method 1: Standard Selenium
element.click()
element.clear()
element.send_keys(value)

# Method 2: JavaScript (if Method 1 fails)
if tag_name == "div":  # contenteditable
    driver.execute_script("arguments[0].innerText = arguments[1];", element, value)
else:  # input/textarea
    driver.execute_script("arguments[0].value = arguments[1];", element, value)

# Triggers input event for React/Vue apps
driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
```

### 4. Detailed Logging

Every step is logged so you can see exactly what happened:

```
[TITLE SETTER] Searching for title input field...
[TITLE SETTER] Trying: Title placeholder (case insensitive)
[TITLE SETTER] Trying: Contains 'itle' in placeholder
[TITLE SETTER] ✅ Found title input using: Contenteditable div (common in FB)
[TITLE SETTER] Setting value: 'Amazing Social Experiment...'
[TITLE SETTER] ✅ Value verified in element
[TITLE SETTER] ✅ Title set successfully
```

## Troubleshooting

### Issue: "No WebDriver instance available"

**Solution:** Make sure you pass your Selenium driver to the title setter:

```python
title_setter = VideoTitleSetter(driver)  # Pass driver here
# or
title_setter.set_driver(driver)  # Update driver later
```

### Issue: "Could not find title input field"

**Solution:** Check the logs to see which selectors were tried. You may need to:

1. Wait longer for the page to load
2. Take a screenshot to see the actual DOM structure
3. Inspect the page and find the exact selector
4. Add a custom selector to the list

```python
# Add custom selector
element = driver.find_element(By.XPATH, "your_custom_xpath")
title_setter._set_input_value(element, "My Title")
```

### Issue: "Title not persisting after setting"

**Solution:** Facebook may require additional actions:

1. Click elsewhere to trigger blur event
2. Wait before clicking publish
3. Check if there's a character limit

```python
# After setting title
element.send_keys(Keys.TAB)  # Trigger blur
time.sleep(1)  # Wait for validation
```

## Next Steps

1. ✅ Integrate `VideoTitleSetter` into your upload workflow
2. ✅ Test with real Facebook upload
3. ✅ Adjust selectors if needed for your specific page type
4. ✅ Add publish button click after title is set

## Example: Complete Upload Flow

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from modules.auto_uploader.browser.video_upload_workflow.title_setter import VideoTitleSetter
import time

# Connect to ixBrowser
options = Options()
options.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(options=options)

# Navigate to page (your existing code)
# Click "Add Videos" (your existing code)
# Upload file (your existing code)

# Wait for upload to complete
print("Waiting for upload to complete...")
time.sleep(10)  # or monitor progress as you already do

# NEW: Set title
print("Setting video title...")
title_setter = VideoTitleSetter(driver, max_wait=30)

success = title_setter.set_video_title(
    title="Social Experiment - Acts of Kindness",
    description="Heartwarming video! #kindness #wholesome #socialexperiment"
)

if success:
    print("✅ Title set! Ready to publish")

    # Click publish button (add your code here)
    # publish_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Publish')]")
    # publish_button.click()

    print("✅ Upload complete!")
else:
    print("❌ Could not set title - manual intervention needed")

# Keep browser open or close
# driver.quit()
```

## Video Metadata JSON Format

Structure your video metadata like this:

```json
{
  "Social_experiment_socialexperiment_kindness.mp4": {
    "title": "Random Acts of Kindness - Social Experiment",
    "description": "Watch how strangers react to unexpected kindness! This heartwarming social experiment shows the power of small gestures. #kindness #socialexperiment #wholesome #hopecore #fyp",
    "tags": ["kindness", "social experiment", "wholesome", "hopecore"],
    "bookmark": "The Guardian Bloom",
    "scheduled_time": "11:43:31"
  }
}
```

Then use it in your workflow:

```python
import json

# Load metadata
with open("videos_description.json") as f:
    metadata = json.load(f)

video_file = "Social_experiment_socialexperiment_kindness.mp4"
video_meta = metadata[video_file]

# Upload and set title
# ... upload code ...
title_setter.set_video_title(
    title=video_meta["title"],
    description=video_meta["description"]
)
```

## Summary

✅ **Fixed:** Video title can now be set using 30+ robust selector strategies
✅ **Added:** Comprehensive waiting and error handling
✅ **Added:** Support for contenteditable divs (Facebook's common input type)
✅ **Added:** JavaScript fallback for tricky inputs
✅ **Added:** Description field support
✅ **Added:** Detailed logging for debugging

Your upload workflow now has a complete Phase 5 for setting video metadata! 🎉

---

**Need Help?**

Check the logs for detailed information about what selectors were tried and why they failed. The logging will guide you to the exact issue.

**Questions?**

- Check `test_title_setter.py` for examples
- Review `title_setter.py` code comments
- Enable DEBUG logging for even more details:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
