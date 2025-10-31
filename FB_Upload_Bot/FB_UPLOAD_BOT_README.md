# Facebook Upload Bot 🚀

**Windows-based Python automation bot that uploads videos to Facebook pages using anti-detect browsers (GoLogin/Incogniton) without APIs - completely free!**

## 📋 Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## ✨ Features

- ✅ **API-Free**: No Facebook API keys or developer accounts needed
- ✅ **Multi-Browser Support**: Works with GoLogin and Incogniton anti-detect browsers
- ✅ **Multi-Account Management**: Manage multiple browser accounts, each with multiple Facebook profiles
- ✅ **Automatic Video Upload**: Single and bulk upload capabilities
- ✅ **Metadata Support**: Automatic title, description, and tags from JSON files
- ✅ **Upload Tracking**: SQLite database tracks all uploads and prevents duplicates
- ✅ **Error Recovery**: Retry failed uploads with configurable attempts
- ✅ **Login Automation**: Automatic Facebook login with 2FA support
- ✅ **Smart Scheduling**: Wait between uploads to avoid rate limiting
- ✅ **Detailed Logging**: Comprehensive logs for debugging and monitoring

---

## 💻 Requirements

### Software Requirements

1. **Operating System**: Windows 10/11 (64-bit)
2. **Python**: 3.8 or higher
3. **Anti-Detect Browser**: One of the following:
   - [GoLogin](https://gologin.com/) - Free tier available
   - [Incogniton](https://incogniton.com/) - Free tier available
4. **ChromeDriver**: Automatically managed by webdriver-manager

### Python Dependencies

All dependencies are listed in `requirements.txt`:
- selenium
- webdriver-manager
- pyautogui
- pygetwindow
- pillow

---

## 🔧 Installation

### Step 1: Install Python

Download and install Python 3.8+ from [python.org](https://www.python.org/downloads/)

Make sure to check "Add Python to PATH" during installation.

### Step 2: Install Anti-Detect Browser

Choose one (or both):

**Option A: GoLogin**
1. Download from [https://gologin.com/](https://gologin.com/)
2. Install and create an account
3. Set up your browser profiles

**Option B: Incogniton**
1. Download from [https://incogniton.com/](https://incogniton.com/)
2. Install and create an account
3. Set up your browser profiles

### Step 3: Clone/Download the Bot

```bash
cd /path/to/automation-fb
cd FB_Upload_Bot
```

### Step 4: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### Step 5: Run Setup Wizard

```bash
python setup.py
```

The setup wizard will:
- Check your Python version
- Verify folder structure
- Test dependencies
- Help you configure browsers

---

## 📁 Project Structure

```
FB_Upload_Bot/
├── config/
│   ├── settings.json           # Global settings
│   └── upload_status.db        # SQLite database (auto-created)
│
├── creators/                   # Your video content
│   ├── Creator1/
│   │   ├── video1.mp4
│   │   ├── video2.mp4
│   │   └── videos_description.json  # Metadata for videos
│   ├── Creator2/
│   │   └── ...
│   └── Creator3/
│       └── ...
│
├── creator_shortcuts/          # Browser account configuration
│   ├── GoLogin/               # GoLogin browser accounts
│   │   ├── account1@/
│   │   │   ├── login_data.txt      # Facebook credentials
│   │   │   ├── Creator1/
│   │   │   │   ├── single video.lnk
│   │   │   │   ├── bulk videos.lnk
│   │   │   │   └── profile.lnk     # Browser profile shortcut
│   │   │   └── Creator2/
│   │   │       └── ...
│   │   └── account2@/
│   │       └── ...
│   │
│   └── IX/                    # Incogniton browser accounts
│       └── account1@/
│           └── ...
│
├── logs/                       # Auto-generated logs
│   └── upload_log_YYYYMMDD_HHMMSS.txt
│
├── fb_upload_bot.py           # Main bot script
├── browser_controller.py      # Browser management
├── upload_manager.py          # Upload logic
├── utils.py                   # Utility functions
├── setup.py                   # Setup wizard
├── requirements.txt           # Dependencies
└── FB_UPLOAD_BOT_README.md    # This file
```

---

## ⚙️ Configuration

### 1. Configure Browser Settings

Edit `config/settings.json`:

```json
{
  "browsers": {
    "gologin": {
      "exe_path": "C:\\Users\\{user}\\AppData\\Local\\Programs\\GoLogin\\GoLogin.exe",
      "desktop_shortcut": "~/Desktop/GoLogin.lnk",
      "debug_port": 9222,
      "startup_wait": 15,
      "enabled": true
    },
    "ix": {
      "exe_path": "C:\\Users\\{user}\\AppData\\Local\\Programs\\Incogniton\\Incogniton.exe",
      "desktop_shortcut": "~/Desktop/Incogniton.lnk",
      "debug_port": 9223,
      "startup_wait": 15,
      "enabled": true
    }
  }
}
```

**Important**: `{user}` will be automatically replaced with your Windows username.

### 2. Set Up Creator Folders

1. Create a folder for each creator in `creators/`:
   ```
   creators/
   ├── MyGamingChannel/
   ├── MyTechReviews/
   └── MyCookingShow/
   ```

2. Add your videos to each creator folder:
   ```
   creators/MyGamingChannel/
   ├── gameplay1.mp4
   ├── gameplay2.mp4
   └── videos_description.json
   ```

### 3. Configure Video Metadata

Create `videos_description.json` in each creator folder:

```json
{
  "gameplay1.mp4": {
    "title": "Epic Gaming Moments - Part 1",
    "description": "Check out these amazing gaming moments!\n\n#gaming #gameplay #epic",
    "tags": ["gaming", "gameplay", "entertainment"],
    "thumbnail": null,
    "schedule": null
  },
  "gameplay2.mp4": {
    "title": "Pro Gaming Tutorial",
    "description": "Learn how to game like a pro!\n\n#tutorial #gaming #howto",
    "tags": ["tutorial", "gaming"],
    "thumbnail": "thumbnail.jpg",
    "schedule": "2024-11-15 18:00:00"
  }
}
```

### 4. Set Up Browser Accounts

For each browser account, create the folder structure:

```
creator_shortcuts/GoLogin/myaccount@/
├── login_data.txt
├── Creator1/
├── Creator2/
└── Creator3/
```

**Note**: Creator folder names MUST match the names in `creators/` folder.

### 5. Configure Login Credentials

Edit `login_data.txt` in each browser account folder:

```
# Format: profile_name|facebook_email|facebook_password|page_name|page_id
Creator1|myemail@gmail.com|mypassword|My Gaming Page|123456789012345
Creator2|myemail2@gmail.com|mypassword2|Tech Reviews Page|987654321098765
```

**Security Note**: Keep this file secure! It contains sensitive credentials.

---

## 🚀 Usage Guide

### Quick Start

1. **Activate virtual environment** (if using):
   ```bash
   venv\Scripts\activate
   ```

2. **Run the bot**:
   ```bash
   python fb_upload_bot.py
   ```

3. **Monitor the logs**:
   - Console output shows real-time progress
   - Detailed logs saved in `logs/` folder

### What Happens When You Run the Bot

1. **Scans** your `creator_shortcuts/` folder to find all browser accounts and creators
2. **Displays** a summary of what will be uploaded
3. **For each browser account**:
   - Launches the browser
   - Opens each creator's profile
   - Uploads their pending videos
   - Waits between uploads to avoid rate limiting
4. **Tracks** all uploads in the database
5. **Logs** everything for your review

### Upload Process Flow

```
1. Launch Browser (GoLogin/Incogniton)
   ↓
2. Open Profile via Shortcut or GUI
   ↓
3. Connect Selenium to Browser
   ↓
4. Navigate to Facebook Upload Page
   ↓
5. Check if Login Required → Login if needed
   ↓
6. Select Video File
   ↓
7. Fill Metadata (Title, Description)
   ↓
8. Wait for Upload/Processing
   ↓
9. Click Publish
   ↓
10. Record in Database
    ↓
11. Optional: Delete Video File
    ↓
12. Wait Before Next Video
```

---

## 🔍 Advanced Configuration

### Upload Settings

In `config/settings.json`:

```json
"upload_settings": {
  "wait_after_upload": 30,           // Wait after each upload (seconds)
  "wait_between_videos": 120,        // Wait between videos (seconds)
  "retry_attempts": 3,               // Retry failed uploads
  "retry_delay": 60,                 // Delay between retries (seconds)
  "delete_after_upload": false,      // Delete video after upload
  "batch_size": 5,                   // Max videos per session
  "upload_timeout": 600,             // Upload timeout (seconds)
  "skip_uploaded": true              // Skip already uploaded videos
}
```

### Facebook Settings

```json
"facebook": {
  "upload_url": "https://www.facebook.com/",
  "video_upload_url": "https://www.facebook.com/video/upload",
  "page_upload_url": "https://www.facebook.com/{page_id}/videos",
  "wait_for_login": 20,
  "wait_for_video_processing": 30
}
```

### Logging Settings

```json
"logging": {
  "level": "INFO",                   // DEBUG, INFO, WARNING, ERROR
  "format": "%(asctime)s - %(levelname)s - %(message)s",
  "console_output": true,
  "file_output": true
}
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "Failed to launch browser"

**Solutions**:
- Verify browser is installed correctly
- Check `exe_path` in `settings.json`
- Try using desktop shortcut instead
- Make sure browser is not already running

#### 2. "Failed to connect Selenium"

**Solutions**:
- Ensure browser is running
- Check debug port in settings (9222 for GoLogin, 9223 for IX)
- Verify ChromeDriver is installed (`webdriver-manager` should handle this)
- Try restarting the browser

#### 3. "No login data found"

**Solutions**:
- Check `login_data.txt` exists in browser account folder
- Verify file format is correct (pipe-separated)
- Ensure profile_name matches creator folder name

#### 4. "Could not find file input element"

**Solutions**:
- Facebook's UI might have changed
- Try updating the bot
- Check if you're logged in correctly
- Verify you're on the correct upload page

#### 5. "Upload timeout"

**Solutions**:
- Increase `upload_timeout` in settings
- Check your internet connection
- Verify video file is not corrupted
- Try uploading a smaller test video

### Debug Mode

Enable debug logging in `config/settings.json`:

```json
"logging": {
  "level": "DEBUG"
}
```

This will show detailed information about every action.

---

## 🔒 Security Best Practices

1. **Protect Credentials**:
   - Never commit `login_data.txt` to Git
   - Use strong, unique passwords
   - Enable 2FA on Facebook accounts

2. **Rate Limiting**:
   - Don't upload too many videos at once
   - Use reasonable wait times between uploads
   - Facebook may flag automated behavior

3. **Account Safety**:
   - Use anti-detect browsers to protect accounts
   - Rotate between accounts if uploading frequently
   - Monitor for Facebook security warnings

4. **File Security**:
   - Keep database file (`upload_status.db`) secure
   - Regularly backup your configuration
   - Use `.gitignore` for sensitive files

---

## 📊 Database Management

The bot uses SQLite to track uploads. You can query the database:

```bash
sqlite3 config/upload_status.db
```

**Useful queries**:

```sql
-- View all uploaded videos
SELECT * FROM upload_history ORDER BY upload_time DESC;

-- Check pending uploads
SELECT * FROM upload_queue WHERE status = 'pending';

-- View browser accounts
SELECT * FROM browser_accounts;

-- Check failed uploads
SELECT * FROM upload_queue WHERE status = 'failed';
```

---

## 🎯 Tips for Best Results

### Video Preparation
- Use supported formats: MP4, AVI, MOV, MKV
- Optimize video size (Facebook recommends < 4GB)
- Prepare metadata in advance
- Test with small videos first

### Scheduling
- Upload during low-traffic hours
- Space out uploads across multiple days
- Don't exceed Facebook's daily upload limits

### Profiles
- Use one Facebook profile per creator for better organization
- Keep profile names consistent across folders
- Create browser profile shortcuts for faster access

### Monitoring
- Check logs regularly for errors
- Monitor database for upload status
- Keep track of Facebook's response to uploads

---

## ❓ FAQ

**Q: Is this against Facebook's Terms of Service?**
A: This bot automates manual actions you would perform anyway. Use responsibly and don't spam. Anti-detect browsers help maintain account security.

**Q: Can I use this for personal profiles instead of pages?**
A: Yes, but be careful with rate limits. Facebook is stricter with personal profiles.

**Q: Do I need to pay for GoLogin/Incogniton?**
A: Both offer free tiers. Paid plans provide more profiles and features.

**Q: Can I run multiple instances of the bot?**
A: Not recommended. The bot already handles multiple accounts sequentially.

**Q: What if Facebook asks for verification during login?**
A: The bot will pause and wait for you to complete 2FA or verification manually.

**Q: Can I schedule uploads for specific times?**
A: Currently, the bot uploads immediately. Scheduled uploads are in the metadata but not yet implemented.

**Q: How do I update the bot?**
A: Pull latest changes from Git. Check README for any breaking changes.

**Q: Can I contribute to the bot?**
A: Yes! Submit issues and pull requests on GitHub.

---

## 📝 Changelog

### Version 1.0.0 (Initial Release)
- Multi-browser support (GoLogin, Incogniton)
- Automatic video upload with metadata
- SQLite database tracking
- Comprehensive logging
- Setup wizard
- Error recovery and retry logic

---

## 🤝 Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review the logs in `logs/` folder
3. Run the setup wizard: `python setup.py`
4. Check database for upload status

---

## ⚠️ Disclaimer

This bot is for educational and personal use only. Users are responsible for complying with Facebook's Terms of Service and applicable laws. The authors are not responsible for any misuse or account suspensions resulting from the use of this bot.

---

## 📜 License

This project is provided as-is for personal use. Modify and distribute responsibly.

---

**Happy Uploading! 🎬🚀**
