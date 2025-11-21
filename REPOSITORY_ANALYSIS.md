# ContentFlow Pro - Comprehensive Repository Analysis

**Repository Location:** `/home/user/automation-fb`  
**Total Files:** 338  
**Python Files:** 190  
**Lines of Code:** ~984 (core modules)  
**Image/Asset Files:** 22  

---

## 1. PROJECT STRUCTURE (Complete Tree)

```
automation-fb/
├── .claude/                          # Claude Code configuration
│   └── settings.local.json
├── .git/                             # Git repository
├── .gitignore
├── cookies/                          # Browser cookies storage
├── data_files/                       # Data and credentials
│   ├── credentials/
│   └── creator_method_cache.json
├── gui-redesign/                     # Modern UI redesign (OneSoul Flow)
│   ├── assets/
│   │   ├── onesoul_animated_logo.html
│   │   ├── onesoul_logo.svg
│   │   └── logo_preview.html
│   ├── components/
│   │   ├── content_area.py
│   │   ├── main_window.py
│   │   ├── sidebar.py
│   │   └── topbar.py
│   ├── styles/
│   ├── demo_app.py
│   ├── __init__.py
│   └── Documentation/
│       ├── ARCHITECTURE.md
│       ├── DESIGN_SUMMARY.md
│       ├── GET_STARTED.md
│       ├── INTEGRATION_GUIDE.md
│       └── README.md
├── modules/                          # Core application modules
│   ├── __init__.py
│   ├── api_manager/                  # API configuration & management
│   │   ├── core.py
│   │   ├── gui.py
│   │   └── __init__.py
│   ├── auto_uploader/                # Facebook/Instagram upload automation
│   │   ├── __init__.py
│   │   ├── gui.py
│   │   ├── main.py
│   │   ├── orchestrator.py
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   ├── install_dependencies.py
│   │   ├── approaches/               # Different automation strategies
│   │   │   ├── base_approach.py
│   │   │   ├── approach_factory.py
│   │   │   ├── free_automation/
│   │   │   └── ixbrowser/            # IX Browser integration
│   │   │       ├── api_client.py
│   │   │       ├── browser_launcher.py
│   │   │       ├── config_handler.py
│   │   │       ├── connection_manager.py
│   │   │       ├── login_manager.py
│   │   │       ├── upload_helper.py
│   │   │       ├── ix_config.json
│   │   │       └── [config, core, data, utils]
│   │   ├── auth/                     # Authentication handlers
│   │   ├── browser/                  # Browser automation
│   │   │   ├── profile_selector/
│   │   │   └── video_upload_workflow/
│   │   ├── config/                   # Configuration management
│   │   ├── creator_shortcuts/        # Creator profile management
│   │   │   ├── GoLogin/
│   │   │   └── IX/
│   │   ├── creators/                 # Creator data handling
│   │   ├── data/                     # Data files
│   │   ├── data_files/               # Presets and settings
│   │   ├── helper_images/            # UI reference images (20 PNG files)
│   │   ├── tracking/                 # Upload tracking
│   │   ├── ui/                       # UI components
│   │   ├── upload/                   # Upload logic
│   │   └── utils/                    # Utilities
│   ├── config/                       # Application configuration
│   │   ├── __init__.py
│   │   └── config_manager.py
│   ├── license/                      # License management system
│   │   ├── __init__.py
│   │   ├── license_manager.py
│   │   └── hardware_id.py
│   ├── link_grabber/                 # Video link extraction
│   │   ├── __init__.py
│   │   ├── core.py
│   │   ├── core_backup.py
│   │   ├── gui.py
│   │   └── intelligence.py
│   ├── logging/                      # Logging system
│   │   ├── __init__.py
│   │   └── logger.py
│   ├── metadata_remover/             # Metadata removal tool
│   │   ├── __init__.py
│   │   └── gui.py
│   ├── ui/                           # UI components
│   │   ├── __init__.py
│   │   ├── activation_dialog.py
│   │   └── license_info_dialog.py
│   ├── video_downloader/             # Video downloading
│   │   ├── __init__.py
│   │   ├── core.py
│   │   ├── gui.py
│   │   ├── bulk_preview_dialog.py
│   │   ├── cookies_utils.py
│   │   ├── download_manager.py
│   │   ├── folder_mapping_dialog.py
│   │   ├── folder_mapping_manager.py
│   │   ├── history_manager.py
│   │   ├── instagram_helper.py
│   │   ├── move_progress_dialog.py
│   │   ├── url_utils.py
│   │   ├── video_mover.py
│   │   └── yt_dlp_worker.py
│   ├── video_editor/                 # Video editing suite
│   │   ├── __init__.py
│   │   ├── core.py
│   │   ├── integrated_editor.py
│   │   ├── crop_dialog.py
│   │   ├── custom_video_player.py
│   │   ├── dual_control_panel.py
│   │   ├── dual_preview_widget.py
│   │   ├── filters.py
│   │   ├── media_library_enhanced.py
│   │   ├── preset_dialog.py
│   │   ├── preset_manager.py
│   │   ├── presets.py
│   │   ├── timeline_widget.py
│   │   ├── transitions.py
│   │   ├── unified_control_panel.py
│   │   ├── utils.py
│   │   ├── video_utils.py
│   │   └── effects/
│   ├── workflows/                    # Combined workflow orchestration
│   │   ├── __init__.py
│   │   └── combo.py
│   └── cookies_manager.py            # Centralized cookies management
├── presets/                          # Video editing presets
│   ├── YouTube Standard.preset.json
│   ├── YouTube Shorts.preset.json
│   ├── TikTok Standard.preset.json
│   ├── Instagram Square.preset.json
│   └── Instagram Reels.preset.json
├── server/                           # License server (Flask)
│   ├── app.py
│   ├── models.py
│   └── routes.py
├── main.py                           # Main application entry point
├── gui.py                            # Legacy GUI
├── gui_modern.py                     # Modern OneSoul Flow GUI
├── run_new_ui.py                     # Launch modern UI demo
├── api_config.json                   # API credentials (template)
├── dev_config.py                     # Development configuration
├── requirements.txt                  # Python dependencies
└── [Multiple documentation files]

```

---

## 2. PYTHON DEPENDENCIES (requirements.txt)

### Core Dependencies:
- **yt-dlp>=2024.3.10** - Video downloading from multiple platforms
- **PyQt5>=5.15.9** - GUI framework
- **PyQtWebEngine>=5.15.0** - Animated logo support
- **requests>=2.31.0** - HTTP requests
- **google-api-python-client>=2.0.0** - YouTube API integration
- **instaloader>=4.9.0** - Instagram scraping
- **beautifulsoup4>=4.12.0** - HTML parsing
- **lxml>=4.9.0** - XML/HTML processing
- **browser_cookie3** - Automatic browser cookie extraction
- **cryptography>=41.0.7** - Encryption for credentials

### Video Editing Dependencies:
- **moviepy>=1.0.3** - Video editing framework
- **pillow>=10.0.0** - Image processing
- **numpy>=1.24.0** - Numerical computations
- **scipy>=1.10.0** - Scientific computing
- **imageio>=2.31.0** - Image I/O
- **imageio-ffmpeg>=0.4.9** - FFmpeg integration

### Automation Dependencies:
- **opencv-python>=4.8.0** - Image recognition for UI detection
- **pyautogui>=0.9.54** - Mouse and keyboard automation
- **pygetwindow>=0.0.9** - Cross-platform window management
- **psutil>=5.9.0** - Process management
- **pyperclip>=1.8.2** - Clipboard operations

### Optional/Server Dependencies:
- Flask - License server
- Flask-SQLAlchemy - Database ORM
- Flask-Limiter - API rate limiting

---

## 3. MAIN ENTRY POINTS

### **main.py** (Primary Entry Point)
- Launches ContentFlow Pro application
- Initializes PyQt5 application
- Loads configuration from `~/.contentflow/config.json`
- Manages license validation (online + offline 3-day grace period)
- Shows license activation dialog if needed
- Supports development mode via `dev_config.py` (DEV_MODE = True skips license checks)
- Uses modern GUI if `USE_MODERN_UI = True` (default)

### **gui_modern.py** (OneSoul Flow - Modern UI)
- 896 lines of code
- Professional 3D modern interface
- Centralized theme system (OneSoulTheme class)
- Navigation between module pages using QStackedWidget
- Integrated modules:
  - LinkGrabberPage
  - VideoDownloaderPage
  - IntegratedVideoEditor
  - MetadataRemoverPage
  - AutoUploaderPage
  - APIConfigPage
  - CombinedWorkflowPage

### **gui.py** (Legacy GUI)
- 725 lines of code
- Basic TabWidget-based navigation
- Same module integration as modern GUI

### **run_new_ui.py** (Demo Launcher)
- Launches the GUI redesign demo from `gui-redesign/demo_app.py`
- Adds `gui-redesign/` to Python path

---

## 4. MODULES OVERVIEW

| Module | Files | Purpose | Key Features |
|--------|-------|---------|--------------|
| **link_grabber** | 4 | Extract video URLs from creator profiles | Multi-platform support, cookie auth, rate limiting |
| **video_downloader** | 12 | Download videos from URLs | Quality selection, batch downloads, folder mapping |
| **video_editor** | 15 | Edit and process videos | Trim, crop, filters, transitions, presets |
| **metadata_remover** | 2 | Remove metadata from video files | Batch processing, backup originals |
| **auto_uploader** | 20+ | Automate uploads to social platforms | IX Browser, GoLogin, Free Automation approaches |
| **api_manager** | 3 | Configure and test API keys | YouTube, Instagram, TikTok, Facebook APIs |
| **config** | 2 | Application configuration management | Settings persistence, defaults |
| **license** | 3 | License validation system | Hardware-based, offline support |
| **logging** | 2 | Centralized logging system | File and console output, daily rotation |
| **ui** | 3 | UI dialogs and components | License activation, info dialogs |
| **workflows** | 2 | Combined workflow orchestration | Grab + Download combo |

---

## 5. DATA FILES & ASSETS

### Image/Helper Files (20 PNG files):
Located in `/home/user/automation-fb/modules/auto_uploader/helper_images/`:
```
- add_videos_button.png
- all_bookmarks.png
- bookmarks_close.png
- browser_close_popup.png
- browser_close_shortNotice.png
- bulkuploading_preview.png
- check_user_status.png
- ix_search_input.png
- ix_search_input_active.png
- login_password_icon.png
- login_profile_icon.png
- open ixbrowser frontpage.png
- open_side_panel_to_see_all_bookmarks.png
- profile_open_button.png
- publish_button_after_data.png
- publish_button_befor_data.png
- results_found_in_all_bookmarks.png
- sample_login_window.png
- search_bookmarks_bar.png
- user_status_dropdown.png
- userprofile_icon_for_logout.png
```

### SVG/HTML Assets (3 files):
Located in `/home/user/automation-fb/gui-redesign/assets/`:
```
- onesoul_logo.svg (2.9 KB)
- onesoul_animated_logo.html (7.7 KB)
- logo_preview.html (1.8 KB)
```

### Preset Files (5 JSON):
Located in `/home/user/automation-fb/presets/`:
```
- YouTube Standard.preset.json
- YouTube Shorts.preset.json
- TikTok Standard.preset.json
- Instagram Square.preset.json
- Instagram Reels.preset.json
```

### Configuration Files:
```
- api_config.json (114 bytes - EMPTY template)
- data_files/creator_method_cache.json (49 KB)
- data_files/credentials/approach_ix.json
- modules/auto_uploader/approaches/ixbrowser/ix_config.json
- modules/auto_uploader/approaches/ixbrowser/data/bot_state.json
- modules/auto_uploader/approaches/ixbrowser/data/folder_progress.json
- modules/auto_uploader/data_files/settings.json
```

---

## 6. GUI-REDESIGN STRUCTURE

Modern UI framework (OneSoul Flow):

```
gui-redesign/
├── components/
│   ├── content_area.py (8.5 KB)
│   ├── main_window.py (7.3 KB)
│   ├── sidebar.py (8.4 KB)
│   └── topbar.py (7.8 KB)
├── styles/
├── assets/
│   ├── onesoul_logo.svg
│   ├── onesoul_animated_logo.html
│   └── logo_preview.html
├── demo_app.py
├── __init__.py
└── Documentation/
    ├── ARCHITECTURE.md
    ├── DESIGN_SUMMARY.md
    ├── GET_STARTED.md
    ├── INTEGRATION_GUIDE.md
    └── README.md
```

**Theme System** (gui_modern.py):
- BG_PRIMARY: "#050712"
- BG_SIDEBAR: "#0a0e1a"
- CYAN: "#00d4ff"
- MAGENTA: "#ff00ff"

---

## 7. CONFIGURATION FILES

### **api_config.json** (Template)
```json
{
  "youtube_api_key": "",
  "instagram_access_token": "",
  "tiktok_api_key": "",
  "facebook_access_token": ""
}
```
**Status:** Empty template - users must fill in their own API keys

### **dev_config.py** (Development Settings)
```python
DEV_MODE = True  # Set to False for production
DEV_CONFIG = {
    'skip_license': True,
    'auto_activate': True,
    'mock_license_info': {
        'license_key': 'DEV-MODE-TEST-KEY',
        'plan_type': 'yearly',
        'days_remaining': 999,
        'device_name': 'Development Device'
    }
}
```
**Status:** Development mode enabled - bypasses license checks

### **config_manager.py** (Default Paths)
Default configuration stored in `~/.contentflow/config.json`:
```
- downloads: ~/Downloads/ContentFlow
- edited_videos: ~/Videos/ContentFlow
- temp: ~/.contentflow/temp
- cache: ~/.contentflow/cache
- license_server: http://localhost:5000
- logs: ~/.contentflow/logs/
```

---

## 8. HARDCODED PATHS & CONFIGURATION

### **Relative Paths:**
```python
# gui_modern.py
animated_logo_path = os.path.join("gui-redesign", "assets", "onesoul_animated_logo.html")
static_logo_path = os.path.join("gui-redesign", "assets", "onesoul_logo.svg")

# run_new_ui.py
gui_redesign_path = os.path.join(os.path.dirname(__file__), 'gui-redesign')
```

### **Hardcoded URLs:**
```python
# api_manager/core.py
YouTube: https://www.googleapis.com/youtube/v3
Instagram: https://graph.instagram.com
TikTok: https://open.tiktokapis.com/v2
Facebook: https://graph.facebook.com/v18.0

# modules/ui/license_info_dialog.py
License Server: http://localhost:5000
```

### **API Documentation URLs:**
```python
YouTube: https://console.cloud.google.com/
Instagram: https://developers.facebook.com/
TikTok: https://developers.tiktok.com/
Facebook: https://developers.facebook.com/
```

### **License Server Settings:**
```python
# modules/config/config_manager.py
server_url: http://localhost:5000
grace_period_days: 3
last_check: None
```

### **TODO/FIXME Items Found:**
```python
# server/routes.py
ADMIN_KEY = "CFPRO_ADMIN_2024_SECRET"  # TODO: Move to environment variable

# modules/video_editor/integrated_editor.py
# TODO: Skip playback
# TODO: Update video volume
# TODO: Toggle fullscreen mode
```

---

## 9. USER CONFIGURATION REQUIREMENTS

### **Essential Changes for Public Release:**

#### 1. **API Keys** (api_config.json)
Users MUST provide their own:
- YouTube API Key (from Google Cloud Console)
- Instagram Access Token
- TikTok API Key
- Facebook Access Token

#### 2. **License Server Configuration**
- Default: `http://localhost:5000`
- Users need either:
  - Running local license server (Flask app in /server/)
  - Cloud-hosted license server
  - Change `dev_config.py` DEV_MODE = False and point to remote server

#### 3. **Development Mode**
- **Currently:** `dev_config.py` has `DEV_MODE = True` (skips license)
- **For Production:** Change `DEV_MODE = False` in `dev_config.py`

#### 4. **Default Paths**
Auto-created in user's home directory:
- `~/.contentflow/` - App data
- `~/Downloads/ContentFlow/` - Downloaded videos
- `~/Videos/ContentFlow/` - Edited videos
- `~/.contentflow/logs/` - Application logs

#### 5. **Browser/Automation Setup**
For auto_uploader:
- Install IX Browser (optional)
- Or use free_automation approach
- Configure browser profiles

#### 6. **FFmpeg**
System dependency required:
```bash
# Windows: Download from ffmpeg.org
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg
```

---

## 10. KEY HARDCODED SETTINGS TO MODIFY

For making the bot public, these need user configuration:

| Setting | Location | Default | Change For Public |
|---------|----------|---------|-------------------|
| `DEV_MODE` | dev_config.py | True | False |
| `ADMIN_KEY` | server/routes.py | CFPRO_ADMIN_2024_SECRET | Use environment variable |
| License Server | config_manager.py | http://localhost:5000 | Remote server URL |
| API Keys | api_config.json | Empty | User input UI |
| Download Path | config_manager.py | ~/Downloads/ContentFlow | User selectable |
| Temp Path | config_manager.py | ~/.contentflow/temp | Auto-managed |
| License Check | main.py | Enabled | Can be disabled for free tier |

---

## 11. PROJECT STATISTICS

```
Total Files:              338
Python Files:             190
Image/Asset Files:        22 (PNG) + 3 (SVG/HTML)
Documentation Files:      50+ markdown files
Lines of Code:            ~984 (core modules)
Largest Modules:
  - video_downloader/gui.py: 896 lines
  - link_grabber/gui.py: 725 lines
  - api_manager/gui.py: 437 lines
  - gui_modern.py: 27,756 bytes
```

---

## 12. CRITICAL NOTES FOR PUBLIC RELEASE

### ⚠️ Security Concerns:
1. **Admin Key Exposed** - `server/routes.py` has hardcoded `ADMIN_KEY`
   - Solution: Move to environment variables or secure config

2. **API Keys Not Encrypted** - `api_config.json` stores keys in plain text
   - Solution: Encrypt API keys at rest using cryptography library

3. **License Server Not Hardened** - Flask dev server used
   - Solution: Deploy with production WSGI server (gunicorn, etc.)

4. **Dev Mode Enabled** - License checks bypassed by default
   - Solution: Set `DEV_MODE = False` before distribution

### ✅ Positive Security Features:
1. License hardware binding (anti-piracy)
2. 3-day offline grace period
3. Browser cookie encryption (cryptography library)
4. Secure credential storage structure

### 📋 Missing for Full Public Release:
1. User registration/account system UI
2. License activation UI (exists but undocumented)
3. Update checker
4. Error reporting mechanism
5. User documentation
6. Installer (EXE/DMG/DEB)

---

## 13. INSTALLATION & SETUP GUIDE

```bash
# 1. Clone repository
git clone https://github.com/toseeq44/automation-fb.git
cd automation-fb

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install system dependencies
# Windows: Install FFmpeg from ffmpeg.org
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg

# 4. Configure API keys
# Edit api_config.json with your YouTube, Instagram, TikTok, Facebook keys

# 5. Setup license server (optional for dev)
# For production, deploy server/ folder or set DEV_MODE = False

# 6. Run application
python main.py
```

---

## 14. QUICK START FOR USERS

```bash
# Run the modern UI
python main.py

# Or launch GUI redesign demo
python run_new_ui.py

# Test individual components (from repository root)
python test_enhanced_link_grabber.py
python test_cookies_system.py
python test_methods.py
```

---

## SUMMARY

ContentFlow Pro is a comprehensive video automation suite with:
- Multi-platform link grabbing (YouTube, Instagram, TikTok, Facebook, Twitter)
- Advanced video downloading with quality selection
- Professional video editing capabilities
- Automated upload system (IX Browser integration)
- License management system with hardware binding
- Modern PyQt5-based GUI with customizable theme

**Ready for Public Release:** After updating:
1. API key configuration UI
2. License server setup
3. Development mode to False
4. Security hardening (admin keys, API key encryption)
5. User documentation
6. Installer creation
