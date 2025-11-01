# 📁 Project Structure - Enhanced Link Grabber

## 🗂️ Directory Organization

```
automation/
├── 📁 config/                 # Configuration files
│   ├── api_config.json       # API keys and settings
│   └── user_preferences.json # User preferences
│
├── 📁 cookies/               # Browser cookies storage
│   ├── youtube_cookies.pkl   # YouTube session cookies
│   ├── instagram_cookies.pkl # Instagram session cookies
│   ├── tiktok_cookies.pkl    # TikTok session cookies
│   ├── facebook_cookies.pkl  # Facebook session cookies
│   └── twitter_cookies.pkl   # Twitter/X session cookies
│
├── 📁 data/                  # Extracted data storage
│   ├── extracted_links/      # Saved link extractions
│   ├── video_metadata/       # Video information
│   └── export_files/         # Exported files
│
├── 📁 logs/                  # Application logs
│   ├── link_grabber.log      # Link grabber activity
│   ├── error.log             # Error logs
│   └── debug.log             # Debug information
│
├── 📁 modules/               # Core application modules
│   ├── 📁 link_grabber/      # Link extraction module
│   │   ├── core.py           # Core extraction logic
│   │   └── gui.py            # User interface
│   │
│   ├── 📁 video_downloader/  # Video download module
│   ├── 📁 video_editor/      # Video editing module
│   ├── 📁 auto_uploader/     # Auto upload module
│   ├── 📁 metadata_remover/  # Metadata removal module
│   ├── 📁 api_manager/       # API management module
│   └── cookies_manager.py    # Cookies management system
│
├── 📁 venv/                  # Python virtual environment
├── main.py                   # Main application entry point
├── gui.py                    # Main GUI application
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

## 🍪 Cookies Management

### Where Cookies Are Stored
- **Location**: `cookies/` directory
- **Format**: Pickle files (.pkl) for security
- **Platforms**: YouTube, Instagram, TikTok, Facebook, Twitter

### How to Add Cookies

#### Method 1: Manual Addition (Recommended)
1. Open Link Grabber module
2. Click "✏️ Add Manual" button
3. Select platform
4. Follow instructions to extract cookies from browser
5. Paste cookies in format: `cookie_name=cookie_value`

#### Method 2: Browser Developer Tools
1. Login to platform in browser
2. Press F12 → Application/Storage → Cookies
3. Copy required cookies
4. Use manual addition dialog

### Required Cookies by Platform

#### YouTube
- `session_token`
- `__Secure-1PSID`
- `__Secure-3PSID`
- `VISITOR_INFO1_LIVE`
- `YSC`
- `PREF`

#### Instagram
- `sessionid`
- `csrftoken`
- `ds_user_id`
- `mid`
- `rur`

#### TikTok
- `sessionid`
- `msToken`
- `ttwid`
- `odin_tt`
- `passport_csrf_token`

#### Facebook
- `c_user`
- `xs`
- `fr`
- `datr`
- `sb`

#### Twitter/X
- `auth_token`
- `ct0`
- `guest_id`
- `personalization_id`
- `twid`

## 🔧 Configuration Files

### API Configuration (`config/api_config.json`)
```json
{
    "youtube_api_key": "your_youtube_api_key_here",
    "instagram_username": "your_instagram_username",
    "instagram_password": "your_instagram_password",
    "tiktok_session": "your_tiktok_session",
    "facebook_token": "your_facebook_token"
}
```

### User Preferences (`config/user_preferences.json`)
```json
{
    "default_max_videos": 50,
    "auto_save_extractions": true,
    "export_format": "txt",
    "theme": "dark",
    "language": "en"
}
```

## 📊 Data Storage

### Extracted Links (`data/extracted_links/`)
- Organized by date and platform
- JSON format with metadata
- Includes video titles, URLs, and timestamps

### Video Metadata (`data/video_metadata/`)
- Video duration, views, likes
- Upload dates and descriptions
- Thumbnail URLs

### Export Files (`data/export_files/`)
- TXT exports of link lists
- CSV files for spreadsheet import
- JSON files for API integration

## 📝 Logging System

### Log Files (`logs/`)
- **link_grabber.log**: All extraction activities
- **error.log**: Error messages and stack traces
- **debug.log**: Detailed debugging information

### Log Levels
- **INFO**: General information
- **WARNING**: Non-critical issues
- **ERROR**: Critical errors
- **DEBUG**: Detailed debugging info

## 🚀 Usage Workflow

### 1. Initial Setup
```
1. Install dependencies: pip install -r requirements.txt
2. Setup cookies for platforms you want to use
3. Configure API keys (optional)
4. Run application: python main.py
```

### 2. Link Extraction Process
```
1. Open Link Grabber module
2. Check cookies status
3. Add/update cookies if needed
4. Paste URL or use bulk mode
5. Start extraction
6. Export results
```

### 3. Data Management
```
1. Check extracted_links/ for saved extractions
2. Use export_files/ for sharing data
3. Monitor logs/ for troubleshooting
4. Update cookies/ when sessions expire
```

## 🔒 Security Considerations

### Cookies Security
- Cookies stored in encrypted pickle format
- Local storage only (not uploaded anywhere)
- User responsible for cookie management
- Clear cookies when no longer needed

### API Keys
- Store in config files (not in code)
- Use environment variables for production
- Rotate keys regularly
- Never commit keys to version control

### Data Privacy
- All data stored locally
- No external data transmission
- User controls all data
- Respect platform terms of service

## 🛠️ Maintenance

### Regular Tasks
1. **Update cookies** when sessions expire
2. **Check logs** for errors
3. **Clean old data** to save space
4. **Update dependencies** for security
5. **Backup config files**

### Troubleshooting
1. Check `logs/error.log` for issues
2. Verify cookies are valid
3. Test with simple URLs first
4. Clear cookies and re-add if needed
5. Check internet connection

## 📈 Performance Optimization

### File Management
- Regular cleanup of old extractions
- Compress large log files
- Monitor disk space usage
- Archive old data

### Network Optimization
- Use reasonable delays between requests
- Batch process multiple URLs
- Monitor rate limits
- Use cookies for authenticated requests

---

**🎯 This organized structure ensures efficient management of your link extraction project while maintaining security and performance.**
