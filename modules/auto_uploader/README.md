# Facebook Auto Uploader Module

Automates video uploads to Facebook pages using anti-detect browsers (GoLogin/Incogniton) without APIs.

## 📁 Folder Structure

```
modules/auto_uploader/
├── data/
│   ├── settings.json          # Configuration
│   ├── upload_tracking.json   # Upload history (JSON)
│   └── logs/                  # Log files
├── creators/                  # Your video content
│   ├── Creator1/
│   │   ├── video1.mp4
│   │   └── videos_description.json
│   └── Creator2/
│       └── ...
├── creator_shortcuts/         # Browser account setup
│   ├── GoLogin/
│   │   └── account1@/
│   │       ├── login_data.txt
│   │       └── Creator1/
│   └── IX/
│       └── ...
├── core.py                    # Main logic
├── browser_controller.py      # Browser management
├── upload_manager.py          # Upload logic
├── utils.py                   # Helper functions
└── gui.py                     # GUI interface
```

## 🚀 Quick Setup

### 1. Add Your Videos

```bash
cd modules/auto_uploader/creators
mkdir MyChannel
# Copy your videos to MyChannel/
```

### 2. Create Metadata

Create `creators/MyChannel/videos_description.json`:

```json
{
  "video1.mp4": {
    "title": "My Video Title",
    "description": "Description here\n\n#hashtags",
    "tags": ["tag1", "tag2"]
  }
}
```

### 3. Configure Login

Create `creator_shortcuts/GoLogin/myaccount@/login_data.txt`:

```
MyChannel|fb_email@gmail.com|password|Page Name|123456789
```

Format: `profile_name|facebook_email|password|page_name|page_id`

### 4. Configure Browser

Edit `data/settings.json`:

```json
{
  "browsers": {
    "gologin": {
      "enabled": true,
      "debug_port": 9222
    }
  }
}
```

## 💻 Usage

### Via GUI

Run the main application and click "Auto Uploader"

### Via Code

```python
from modules.auto_uploader import FacebookAutoUploader

uploader = FacebookAutoUploader()
uploader.run()
```

### Via Command Line

```bash
cd modules/auto_uploader
python core.py
```

## ⚙️ Configuration

### Browser Settings

- `exe_path`: Path to browser executable
- `debug_port`: Remote debugging port (9222 for GoLogin, 9223 for Incogniton)
- `startup_wait`: Seconds to wait for browser startup
- `enabled`: Enable/disable browser

### Upload Settings

- `wait_after_upload`: Wait time after each upload (seconds)
- `wait_between_videos`: Wait time between videos (seconds)
- `delete_after_upload`: Delete video after successful upload
- `skip_uploaded`: Skip already uploaded videos
- `upload_timeout`: Maximum upload time (seconds)

## 📊 Tracking System

Uses JSON-based tracking (`data/upload_tracking.json`):

```json
{
  "upload_history": [
    {
      "creator_name": "Creator1",
      "video_file": "video1.mp4",
      "status": "completed",
      "timestamp": "2024-10-31T12:00:00"
    }
  ],
  "failed_uploads": [],
  "browser_accounts": {}
}
```

## 🔒 Security

- Keep `login_data.txt` private
- Files are stored locally only
- Use anti-detect browsers for safety
- Enable 2FA on Facebook accounts

## 🐛 Troubleshooting

### "Failed to launch browser"
- Check browser is installed
- Verify `exe_path` in settings
- Try using desktop shortcut

### "Failed to connect Selenium"
- Ensure browser is running
- Check debug port (9222/9223)
- Verify ChromeDriver installed

### "No login data found"
- Check `login_data.txt` exists
- Verify file format (pipe-separated)
- Ensure profile name matches creator folder

## 📝 Notes

- Windows optimized (uses pyautogui, pygetwindow)
- Requires GoLogin or Incogniton browser
- No Facebook API needed
- Use responsibly and comply with Facebook TOS

## 🔗 Integration

Part of the automation-fb project. Works with existing modules:

```python
# Download videos
from modules.video_downloader import download_video

# Upload to Facebook
from modules.auto_uploader import FacebookAutoUploader
```

---

**Happy Uploading! 🚀**
