# Helper Images for Browser Automation

This directory contains reference images used for UI detection with OpenCV image recognition.

## Required Images

The browser automation module uses these images to detect UI elements:

### 1. check_user_status.png
**Purpose:** Detect if a user is logged in to Facebook
**What to capture:** Screenshot of the profile icon or logged-in indicator (top-right corner of Facebook)
**When to capture:** When you are logged in to Facebook
**Size recommendation:** 50x50 to 100x100 pixels

### 2. user_status_dropdown.png
**Purpose:** Detect the dropdown menu when hovering over profile icon
**What to capture:** Screenshot of the dropdown that appears with logout option
**When to capture:** When hovering over the profile icon and the dropdown is visible
**Size recommendation:** 200x300 to 300x400 pixels

### 3. browser_close_popup.png
**Purpose:** Detect "Safe and Exit" browser close confirmation popup
**What to capture:** Screenshot of the popup that appears when trying to close browser
**When to capture:** When the "Safe and Exit" popup is visible
**Size recommendation:** 300x200 to 400x300 pixels

### 4. login_page.png (Optional)
**Purpose:** Detect Facebook login page
**What to capture:** Screenshot of distinctive element on Facebook login page (e.g., logo, login button)
**When to capture:** When on Facebook login page
**Size recommendation:** 200x200 to 300x300 pixels

## How to Create These Images

1. **Manual Screenshot Method:**
   - Use your browser's screenshot tool or a tool like Snipping Tool (Windows), Screenshot (Mac)
   - Navigate to the state you want to capture
   - Take a screenshot of ONLY the specific UI element you want to detect
   - Save as PNG with the exact filename listed above
   - Place in this directory

2. **Automated Screenshot Method:**
   ```python
   from modules.auto_uploader.browser.screen_detector import ScreenDetector

   detector = ScreenDetector()

   # When the element you want to capture is visible on screen:
   detector.save_screenshot('check_user_status.png', region=(1800, 50, 100, 100))
   # Adjust region=(x, y, width, height) to capture just the element
   ```

## Tips for Good Template Images

1. **Keep images small** - Capture only the element you want to detect, not the entire screen
2. **High contrast** - Choose elements with distinctive colors/patterns
3. **Stable elements** - Choose UI elements that don't change appearance
4. **Clear screenshots** - Avoid blur, use original browser zoom level (100%)
5. **Test your images** - Verify detection works by running the automation

## Testing Image Detection

You can test if your images are detected correctly:

```python
from modules.auto_uploader.browser.screen_detector import ScreenDetector

detector = ScreenDetector()

# Test user status detection
result = detector.detect_user_status()
print(f"User logged in: {result['logged_in']}, Confidence: {result['confidence']}")

# Test custom element detection
result = detector.detect_custom_element('your_custom_image.png')
print(f"Element found: {result['found']}, Position: {result['position']}")
```

## Image Format Requirements

- **Format:** PNG (recommended for quality and transparency support)
- **Color:** RGB or RGBA
- **Quality:** Original/high quality, no compression artifacts
- **Background:** Should match the browser background where element appears

## Troubleshooting

If image detection is not working:

1. **Lower confidence threshold:**
   ```python
   detector = ScreenDetector(confidence=0.7)  # Default is 0.8
   ```

2. **Check image size** - Make sure template isn't larger than the actual element
3. **Verify image path** - Ensure images are in this directory
4. **Update images** - If Facebook UI changed, recapture screenshots
5. **Check zoom level** - Capture and detect at the same browser zoom level

## Current Status

- [ ] check_user_status.png - **NOT YET CREATED**
- [ ] user_status_dropdown.png - **NOT YET CREATED**
- [ ] browser_close_popup.png - **NOT YET CREATED**
- [ ] login_page.png - **OPTIONAL, NOT YET CREATED**

**Action Required:** Please create these images before using the browser automation module.
