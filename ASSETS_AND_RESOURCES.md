# ContentFlow Pro - Assets and Resources Guide

## Complete List of All Image/Asset Files with Absolute Paths

### 1. Helper Images for Auto-Uploader (20 PNG files)

These images are used for UI element detection in the automated upload workflow:

```
/home/user/automation-fb/modules/auto_uploader/helper_images/

- add_videos_button.png                    (UI button reference)
- all_bookmarks.png                        (Bookmarks list)
- bookmarks_close.png                      (Close button)
- browser_close_popup.png                  (Browser popup close)
- browser_close_shortNotice.png            (Short notice close)
- bulkuploading_preview.png                (Upload preview)
- check_user_status.png                    (User status indicator)
- ix_search_input.png                      (Search input field)
- ix_search_input_active.png               (Active search state)
- login_password_icon.png                  (Password field icon)
- login_profile_icon.png                   (Profile icon)
- open ixbrowser frontpage.png             (Browser homepage)
- open_side_panel_to_see_all_bookmarks.png (Side panel)
- profile_open_button.png                  (Profile opener)
- publish_button_after_data.png            (Publish after upload)
- publish_button_befor_data.png            (Publish before data)
- results_found_in_all_bookmarks.png       (Search results)
- sample_login_window.png                  (Login window)
- search_bookmarks_bar.png                 (Bookmarks search)
- user_status_dropdown.png                 (User menu dropdown)
- userprofile_icon_for_logout.png          (Logout icon)
```

**Purpose:** Image recognition for automated browser interactions (IX Browser)

**Format:** PNG images
**Total Size:** ~5-10 MB
**Usage:** OpenCV-based UI detection in auto_uploader module

---

### 2. Logo and Branding Assets (3 files)

Located in `/home/user/automation-fb/gui-redesign/assets/`:

```
- onesoul_logo.svg           (2.9 KB)  - Static SVG logo
- onesoul_animated_logo.html (7.7 KB)  - Animated HTML5 logo
- logo_preview.html          (1.8 KB)  - Logo preview template
```

**Purpose:** OneSoul Flow branding
**Usage:** Main GUI logo display
**Implementation:** SVG for static, HTML5 with CSS/JS for animation

**Colors Used (from logo):**
- Cyan: #00d4ff
- Magenta: #ff00ff
- Dark Background: #050712

---

### 3. Video Editing Presets (5 JSON files)

Located in `/home/user/automation-fb/presets/`:

```
YouTube Standard.preset.json
- Format: MP4
- Resolution: 1920x1080 (16:9)
- Frame Rate: 30fps
- Codec: H.264
- Audio: AAC 128kbps

YouTube Shorts.preset.json
- Format: MP4
- Resolution: 1080x1920 (9:16)
- Frame Rate: 60fps
- Codec: H.264
- Audio: AAC 128kbps

TikTok Standard.preset.json
- Format: MP4
- Resolution: 1080x1920 (9:16)
- Frame Rate: 60fps
- Codec: H.265 (recommended)
- Audio: AAC 128kbps

Instagram Square.preset.json
- Format: MP4
- Resolution: 1080x1080 (1:1)
- Frame Rate: 30fps
- Codec: H.264
- Audio: AAC 128kbps

Instagram Reels.preset.json
- Format: MP4
- Resolution: 1080x1920 (9:16)
- Frame Rate: 60fps
- Codec: H.264
- Audio: AAC 128kbps
```

**Purpose:** Quick video export settings for different platforms
**Usage:** Video editor preset system
**Format:** JSON configuration files

---

### 4. Configuration/Data Files

#### API Configuration
```
/home/user/automation-fb/api_config.json (114 bytes - EMPTY)
```
**Purpose:** Template for API keys (users fill in their own)
**Contains:** YouTube, Instagram, TikTok, Facebook API credentials
**Status:** Currently empty - needs user configuration

#### Creator Method Cache
```
/home/user/automation-fb/data_files/creator_method_cache.json (49 KB)
```
**Purpose:** Cached data about creator uploading methods
**Auto-Generated:** Yes, during operation

#### Credentials File
```
/home/user/automation-fb/data_files/credentials/approach_ix.json
```
**Purpose:** IX Browser authentication credentials
**Security:** Should be encrypted

#### Auto-Uploader Settings
```
/home/user/automation-fb/modules/auto_uploader/data_files/settings.json
```
**Purpose:** Upload workflow settings
**Auto-Created:** Yes, during first run

#### IX Browser Configuration
```
/home/user/automation-fb/modules/auto_uploader/approaches/ixbrowser/ix_config.json
```
**Purpose:** IX Browser connection settings
**Contents:** Browser API endpoints, ports, etc.

#### Upload Tracking
```
/home/user/automation-fb/modules/auto_uploader/approaches/ixbrowser/data/bot_state.json
/home/user/automation-fb/modules/auto_uploader/approaches/ixbrowser/data/folder_progress.json
```
**Purpose:** Track upload progress and bot state
**Auto-Updated:** During uploads

---

## Asset Organization for Distribution

### For End Users
Users will have these asset directories:

```
~/.contentflow/                    # Hidden app data
├── config.json                    # Main configuration
├── logs/                          # Daily log files
├── temp/                          # Temporary files
├── cache/                         # Cached data
└── folder_mappings.json           # Download folder mappings
```

### For Developers/Installers
Assets to bundle:

```
gui-redesign/assets/               # Required
  ├── onesoul_logo.svg
  ├── onesoul_animated_logo.html
  └── logo_preview.html

modules/auto_uploader/helper_images/  # Required (for automation)
  └── [20 PNG files listed above]

presets/                           # Required
  ├── YouTube Standard.preset.json
  ├── YouTube Shorts.preset.json
  ├── TikTok Standard.preset.json
  ├── Instagram Square.preset.json
  └── Instagram Reels.preset.json
```

---

## Asset Paths in Code

### Relative Paths (from project root)
```python
# GUI logo paths
animated_logo = "gui-redesign/assets/onesoul_animated_logo.html"
static_logo = "gui-redesign/assets/onesoul_logo.svg"

# Presets paths
presets_dir = "presets/"

# Helper images paths
helper_images = "modules/auto_uploader/helper_images/"
```

### Absolute Paths (runtime)
```python
# User config directory
user_config = Path.home() / ".contentflow"

# Downloaded videos
downloads = Path.home() / "Downloads" / "ContentFlow"

# Edited videos
edited = Path.home() / "Videos" / "ContentFlow"

# Logs
logs = Path.home() / ".contentflow" / "logs"

# Cache
cache = Path.home() / ".contentflow" / "cache"

# Temp
temp = Path.home() / ".contentflow" / "temp"
```

---

## Adding New Assets

### How to Add Images to Auto-Uploader

1. **Capture the UI element** using a screenshot tool
2. **Save as PNG** in `/modules/auto_uploader/helper_images/`
3. **Update helper image list** if adding automation for new platforms
4. **Import in code:**
   ```python
   import cv2
   image = cv2.imread('modules/auto_uploader/helper_images/element.png')
   ```

### How to Add Video Presets

1. **Create preset JSON** in `/presets/`
   ```json
   {
     "name": "Platform Preset Name",
     "format": "mp4",
     "resolution": [1920, 1080],
     "fps": 30,
     "codec": "h264",
     "bitrate": "8000k",
     "audio_codec": "aac",
     "audio_bitrate": "128k"
   }
   ```

2. **Register in code:**
   ```python
   # modules/video_editor/preset_manager.py
   PRESETS = {
     "Platform Preset Name": "presets/yourpreset.json"
   }
   ```

3. **Test in video editor UI**

---

## Asset Licensing & Attribution

### Logos
- **OneSoul Flow Logo** - Original design
- **Colors:** Cyan (#00d4ff), Magenta (#ff00ff)

### Icons/Images
- **Helper Images** - UI screenshots from IX Browser
- **Presets** - Generated from platform specifications

### External Libraries Used for Assets
- **moviepy** - Video processing (asset library)
- **pillow** - Image processing
- **opencv-python** - Image recognition
- **imageio** - Image/video I/O

---

## Troubleshooting Asset Issues

### Logo Not Displaying
1. Check if `gui-redesign/assets/` exists
2. Verify SVG file permissions (readable)
3. Check if PyQtWebEngine is installed (for animations)
4. Fallback to static SVG if HTML animation fails

### Helper Images Not Found
1. Ensure `modules/auto_uploader/helper_images/` exists
2. Check image file names (case-sensitive on Linux/Mac)
3. Verify OpenCV is installed: `pip install opencv-python`
4. Check file permissions

### Presets Not Loading
1. Verify JSON syntax in preset file
2. Ensure presets directory is readable
3. Check if preset parser handles custom settings
4. Look for JSON parse errors in logs

### Missing Fonts or Rendering Issues
1. Install system fonts: `apt install fonts-dejavu` (Linux)
2. Check PIL/Pillow font paths
3. Use fallback fonts in video editor
4. Verify FFmpeg is installed

---

## Asset Files Summary Table

| Type | Count | Location | Format | Size |
|------|-------|----------|--------|------|
| Helper Images | 20 | helper_images/ | PNG | 5-10 MB |
| Logos | 3 | gui-redesign/assets/ | SVG/HTML | 12 KB |
| Presets | 5 | presets/ | JSON | 50 KB |
| Config Templates | 1 | root | JSON | 114 B |
| Data Files | 4 | data_files/ | JSON | 50 MB |
| **TOTAL** | **33** | **Multiple** | **Mixed** | **~65 MB** |

---

## Updating Assets for New Platforms

### Step 1: Capture Helper Images
- Open platform in IX Browser
- Take screenshots of key UI elements
- Save as PNG in helper_images/

### Step 2: Create Video Preset
- Document platform specs
- Create preset JSON in presets/
- Test export with video editor

### Step 3: Update Automation Code
- Add recognition logic in auto_uploader/
- Register helper images in code
- Test with real videos

### Step 4: Update Documentation
- Add platform to README
- Update REPOSITORY_ANALYSIS.md
- Create platform-specific guides

---

## Asset Performance Optimization

### Images
- Helper images use OpenCV for fast matching
- Consider image size for faster processing
- PNG compression recommended for distribution

### Presets
- JSON loading is instantaneous
- Consider caching preset objects
- Presets can be edited by advanced users

### Logos
- SVG scales to any resolution
- HTML animation can be CPU-intensive
- Provide static fallback

### General
- All assets should be < 100MB total
- Lazy load assets when possible
- Cache frequently used assets

