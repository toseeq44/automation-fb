# Facebook Auto Uploader - Clean Structure Documentation

## Overview
This is a **simplified, well-organized** version of the Facebook Auto Uploader module. All complex and redundant files have been removed, leaving only the essential components that work together seamlessly.

---

## 📁 Folder Structure

```
modules/auto_uploader/
├── __init__.py                          # Module exports
├── core.py                              # Main uploader orchestrator
├── gui.py                               # PyQt5 GUI interface
├── browser_controller.py                # Browser launching & Selenium connection
├── upload_manager.py                    # Facebook upload logic
├── utils.py                             # Utility functions
├── install_dependencies.py              # Auto-installer for dependencies
├── requirements.txt                     # Python dependencies
├── README.md                            # General documentation
├── .gitignore                           # Git ignore rules
│
├── data/                                # Application data (JSON-based)
│   ├── settings.json                    # Configuration (browsers, upload settings)
│   ├── upload_tracking.json             # Upload history tracking
│   └── logs/                            # Log files (auto-generated)
│
├── creators/                            # Creator video folders
│   ├── {creator_name}/                  # Each creator has their own folder
│   │   ├── video1.mp4
│   │   ├── video2.mp4
│   │   └── videos_description.json      # Metadata for videos
│   └── videos_description.json.example  # Template
│
└── creator_shortcuts/                   # Browser profile shortcuts
    ├── {browser_type}/                  # GoLogin, IX (Incogniton)
    │   └── {account_name}/              # Browser account
    │       ├── login_data.txt           # Login credentials
    │       └── {creator_name}/          # Creator profile folder
    │           └── profile.lnk          # Windows shortcut to profile
    └── login_data.txt.example           # Template
```

---

## 🔧 Core Files Explained

### 1. **`core.py`** (325 lines) - Main Orchestrator
**Purpose**: Coordinates the entire upload workflow

**Key Responsibilities**:
- Scans `creator_shortcuts/` folder to find browser accounts and creators
- Loads configuration from `settings.json`
- Loads tracking data from `upload_tracking.json`
- Launches browsers and processes each creator
- Manages the upload lifecycle

**Key Methods**:
```python
FacebookAutoUploader.__init__()          # Initialize with simple JSON config
.run()                                   # Main execution flow
.scan_creator_shortcuts()                # Build account→creator mapping
.process_browser_account()               # Process all creators for a browser account
._process_creator()                      # Process single creator
.cleanup()                               # Save tracking & close browsers
```

**Dependencies**: Only uses `browser_controller`, `upload_manager`, and `utils` - no complex configuration classes.

---

### 2. **`gui.py`** (311 lines) - GUI Interface
**Purpose**: Provides a user-friendly PyQt5 interface

**Key Features**:
- Background thread execution (no GUI freezing)
- Real-time log output
- Start/Stop/Clear controls
- Status indicators and progress bar
- Graceful error handling with helpful messages

**Key Components**:
```python
UploaderThread                           # Background worker thread
AutoUploaderPage                         # Main GUI widget
.start_upload()                          # Launch uploader in thread
.append_log()                            # Add messages to log display
.upload_finished()                       # Handle completion
```

**Simplified**: No complex SettingsManager or UI wizards - just simple direct execution.

---

### 3. **`browser_controller.py`** (400 lines) - Browser Management
**Purpose**: Handles browser launching and Selenium connection

**Key Features**:
- Launch GoLogin/Incogniton browsers
- Open profiles via Windows shortcuts (PyAutoGUI)
- Connect Selenium via remote debugging (port 9222/9223)
- Anti-detection measures (stealth settings)
- Graceful error handling

**Key Methods**:
```python
BrowserController.launch_browser()       # Launch browser executable
.open_profile_via_shortcut()            # Open profile via .lnk file
.connect_selenium()                      # Connect Selenium WebDriver
.close_browser()                         # Close browser instance
.close_all()                             # Cleanup all browsers
```

**Platform**: Windows-specific (uses pyautogui, pygetwindow)

---

### 4. **`upload_manager.py`** (433 lines) - Upload Logic
**Purpose**: Handles Facebook login and video uploads

**Key Features**:
- Facebook login automation (email, password, 2FA support)
- Navigate to page upload URL
- Fill video upload form (title, description, tags)
- Track upload status and history
- Retry logic for failed uploads

**Key Methods**:
```python
UploadManager.upload_creator_videos()    # Process all videos for creator
._login_to_facebook()                    # Automated login with 2FA
._upload_single_video()                  # Upload one video
._fill_upload_form()                     # Fill video metadata
._track_upload()                         # Save to upload history
```

**Data Sources**:
- Gets videos from `creators/{creator_name}/`
- Gets metadata from `videos_description.json`
- Gets login credentials from `login_data.txt`

---

### 5. **`utils.py`** (401 lines) - Utilities
**Purpose**: Shared utility functions for config, tracking, and file operations

**Key Functions**:
```python
load_config(path)                        # Load settings.json
save_config(path, config)                # Save settings.json
load_tracking_data(path)                 # Load upload_tracking.json
save_tracking_data(path, data)           # Save upload_tracking.json
parse_login_data(file)                   # Parse login_data.txt
get_video_files(folder)                  # Find video files (mp4, avi, mov, mkv)
get_config_value(config, key, default)   # Dot notation access (e.g., "browsers.GoLogin.port")
format_file_size(bytes)                  # Human-readable file sizes
```

**Approach**: Simple JSON-based operations, no database complexity.

---

### 6. **`__init__.py`** (10 lines) - Module Exports
**Purpose**: Define public API of the module

```python
from .core import FacebookAutoUploader
from .gui import AutoUploaderPage

__all__ = ['FacebookAutoUploader', 'AutoUploaderPage']
__version__ = '1.0.0-simplified'
```

---

### 7. **`install_dependencies.py`** (Small utility)
**Purpose**: Auto-install required Python packages

**Usage**:
```bash
python modules/auto_uploader/install_dependencies.py
```

---

## 🔄 Workflow Explanation

### **Complete Upload Workflow**:

```
1. USER STARTS UPLOAD (via GUI or direct execution)
   ↓
2. core.py: Load settings.json & upload_tracking.json
   ↓
3. core.py: Scan creator_shortcuts/ folder
   → Build mapping: {browser_type: {account_name: [creator_names]}}
   ↓
4. core.py: Display summary (creators & pending videos)
   ↓
5. FOR EACH browser_type (GoLogin, IX):
   ↓
   6. FOR EACH account_name:
      ↓
      7. browser_controller.py: Launch browser
      ↓
      8. Load login_data.txt for account
      ↓
      9. FOR EACH creator_name:
         ↓
         10. browser_controller.py: Open profile via profile.lnk shortcut
         ↓
         11. browser_controller.py: Connect Selenium WebDriver
         ↓
         12. upload_manager.py: Login to Facebook (if needed)
         ↓
         13. upload_manager.py: Get videos from creators/{creator_name}/
         ↓
         14. upload_manager.py: Load metadata from videos_description.json
         ↓
         15. FOR EACH video (not yet uploaded):
             ↓
             16. upload_manager.py: Navigate to page upload URL
             ↓
             17. upload_manager.py: Upload video file
             ↓
             18. upload_manager.py: Fill form (title, description, tags)
             ↓
             19. upload_manager.py: Submit & wait for completion
             ↓
             20. utils.py: Save to upload_tracking.json
         ↓
         21. Close Selenium driver
      ↓
      22. browser_controller.py: Close browser
   ↓
23. core.py: Save final tracking data
   ↓
24. DONE!
```

---

## 📝 Configuration Files

### **`data/settings.json`** - Main Configuration
```json
{
  "browsers": {
    "GoLogin": {
      "enabled": true,
      "executable_path": "C:\\Program Files\\GoLogin\\gologin.exe",
      "port": 9222
    },
    "IX": {
      "enabled": true,
      "executable_path": "C:\\Program Files\\Incogniton\\incogniton.exe",
      "port": 9223
    }
  },
  "upload_settings": {
    "max_retries": 3,
    "upload_timeout": 300,
    "check_interval": 5,
    "page_load_timeout": 30
  },
  "facebook": {
    "login_url": "https://www.facebook.com/login",
    "upload_url_template": "https://www.facebook.com/{page_id}/videos/upload"
  },
  "setup_completed": true
}
```

### **`data/upload_tracking.json`** - Upload History
```json
{
  "upload_history": [
    {
      "creator_name": "JohnDoe",
      "video_file": "video1.mp4",
      "page_id": "123456789",
      "status": "completed",
      "timestamp": "2024-10-31T10:30:00",
      "browser_type": "GoLogin",
      "account_name": "Account1"
    }
  ],
  "failed_uploads": [],
  "browser_accounts": {},
  "last_updated": "2024-10-31T10:30:00"
}
```

---

## 🎯 Usage Examples

### **Method 1: GUI Mode (Recommended)**
```python
from modules.auto_uploader import AutoUploaderPage

# In your main GUI application
uploader_page = AutoUploaderPage(back_callback=go_to_main_menu)
uploader_page.show()
```

### **Method 2: Direct Execution**
```python
from modules.auto_uploader import FacebookAutoUploader

uploader = FacebookAutoUploader()
success = uploader.run()
```

### **Method 3: Command Line**
```bash
cd modules/auto_uploader
python core.py
```

---

## 🗑️ Files Removed (Redundant/Complex)

The following files were removed to simplify the structure:

1. **`auth_handler.py`** (43 lines)
   - Used keyring for credential management
   - Overly complex for simple text-file credentials
   - Not needed - credentials are in login_data.txt

2. **`browser_launcher.py`** (35 lines)
   - Unnecessary facade wrapper
   - Just called browser_controller methods
   - Removed - use browser_controller directly

3. **`configuration.py`** (143 lines)
   - Complex SettingsManager class with CLI wizards
   - Caused TypeError with interactive_collector
   - Replaced with simple JSON loading in utils.py

4. **`history_manager.py`** (69 lines)
   - Duplicate functionality
   - Same as upload tracking in utils.py
   - Removed - use load_tracking_data/save_tracking_data

5. **`ui_configurator.py`** (104 lines)
   - CLI-based setup wizard
   - Not needed for GUI application
   - Settings are pre-configured in settings.json

**Backup**: Complex versions saved as `.complex.backup` files for reference.

---

## ✅ Benefits of Simplified Structure

1. **Easy to Understand**: Clear file purposes, no redundant abstractions
2. **Simple Dependencies**: Only 7 core files, no complex class hierarchies
3. **JSON-based**: No database setup, just text files
4. **Well Organized**: Logical separation of concerns
5. **Maintainable**: Each file has a single, clear responsibility
6. **Error-Free**: Removed sources of TypeError and import conflicts
7. **Documented**: Clear explanation of workflow and usage

---

## 🚀 Getting Started

### **1. Install Dependencies**
```bash
pip install -r modules/auto_uploader/requirements.txt
# OR
python modules/auto_uploader/install_dependencies.py
```

### **2. Configure Browsers**
Edit `data/settings.json` with your browser paths.

### **3. Setup Creator Shortcuts**
```
creator_shortcuts/
└── GoLogin/
    └── MyAccount/
        ├── login_data.txt              # Add credentials
        └── JohnDoe/
            └── profile.lnk             # Create shortcut to profile
```

### **4. Add Videos**
```
creators/
└── JohnDoe/
    ├── video1.mp4
    ├── video2.mp4
    └── videos_description.json         # Add metadata
```

### **5. Run Uploader**
```bash
python modules/auto_uploader/core.py
# OR use GUI from main application
```

---

## 📞 Support

If you encounter issues:
1. Check log files in `data/logs/`
2. Verify configuration in `data/settings.json`
3. Ensure all dependencies are installed
4. Check browser executable paths

---

**Version**: 1.0.0-simplified
**Last Updated**: 2024-10-31
**Status**: Production Ready ✅
