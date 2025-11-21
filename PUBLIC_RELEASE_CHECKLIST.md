# ContentFlow Pro - Public Release Checklist

## Critical Configuration Changes Required

### 1. Disable Development Mode
**File:** `dev_config.py`
```python
# CHANGE THIS:
DEV_MODE = True  

# TO THIS:
DEV_MODE = False
```

### 2. Secure Admin Key
**File:** `server/routes.py` (line with ADMIN_KEY)
```python
# CURRENT (EXPOSED):
ADMIN_KEY = "CFPRO_ADMIN_2024_SECRET"

# CHANGE TO:
import os
ADMIN_KEY = os.getenv('CFPRO_ADMIN_KEY', '')  # Use environment variable
```

### 3. Configure API Keys
**File:** `api_config.json`

Users need to add their own API keys:
```json
{
  "youtube_api_key": "YOUR_YOUTUBE_API_KEY_HERE",
  "instagram_access_token": "YOUR_INSTAGRAM_TOKEN_HERE",
  "tiktok_api_key": "YOUR_TIKTOK_API_KEY_HERE",
  "facebook_access_token": "YOUR_FACEBOOK_TOKEN_HERE"
}
```

**Where to get them:**
- YouTube: https://console.cloud.google.com/
- Instagram: https://developers.facebook.com/
- TikTok: https://developers.tiktok.com/
- Facebook: https://developers.facebook.com/

### 4. Setup License Server
**Options:**

**Option A: Local Development**
```bash
cd server
python app.py  # Runs on http://localhost:5000
```

**Option B: Production Deployment**
- Deploy `/server/` folder to cloud (AWS, Heroku, DigitalOcean, etc.)
- Update license server URL in `modules/config/config_manager.py`:
```python
"server_url": "https://your-server.com"  # Change from localhost:5000
```

### 5. Encrypt API Keys at Rest
**File:** `modules/video_downloader/` (or use app-wide encryption)

Add encryption for API keys:
```python
from cryptography.fernet import Fernet

# Generate key once
key = Fernet.generate_key()

# Encrypt/decrypt API keys
cipher = Fernet(key)
encrypted_key = cipher.encrypt(api_key.encode())
decrypted_key = cipher.decrypt(encrypted_key).decode()
```

### 6. Default Paths Configuration
Currently hardcoded to user home directory:
- Downloads: `~/Downloads/ContentFlow`
- Edited videos: `~/Videos/ContentFlow`
- Temp: `~/.contentflow/temp`
- Cache: `~/.contentflow/cache`
- Logs: `~/.contentflow/logs`

**Status:** These are user-friendly defaults and don't need changes

### 7. Hardcode to Remove/Update

| Path | Current | Action | File |
|------|---------|--------|------|
| License Server | localhost:5000 | Make configurable | config_manager.py |
| Admin Key | CFPRO_ADMIN_2024_SECRET | Use env var | server/routes.py |
| GUI Redesign Path | gui-redesign/ | Relative (OK for prod) | gui_modern.py |
| API Keys | Empty template | User input UI | api_config.json |

---

## User Setup Guide for Public Release

### Installation Instructions (for users)

```bash
# 1. Install Python 3.8+
# Download from python.org

# 2. Install FFmpeg (system dependency)
# Windows: Download from ffmpeg.org
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg

# 3. Clone and setup
git clone https://github.com/YOUR_GITHUB/automation-fb.git
cd automation-fb

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Configure API Keys
# Edit api_config.json and add your API keys

# 6. Run Application
python main.py
```

### User Documentation Files Needed

Create these documentation files for users:

1. **GETTING_STARTED.md** - Step-by-step setup
2. **API_SETUP_GUIDE.md** - How to get API keys
3. **TROUBLESHOOTING.md** - Common issues
4. **CHANGELOG.md** - Version history
5. **LICENSE.md** - License information

---

## Testing Before Release

### Unit Tests to Add
- [ ] Test link grabber with each platform
- [ ] Test video downloader with various URLs
- [ ] Test video editor filters and effects
- [ ] Test metadata removal
- [ ] Test license validation
- [ ] Test offline mode (3-day grace period)

### Integration Tests
- [ ] Full workflow: Grab → Download → Edit → Upload
- [ ] API key validation
- [ ] License server communication
- [ ] Cookie management
- [ ] Folder mapping

### Manual Testing Checklist
- [ ] Windows compatibility
- [ ] macOS compatibility
- [ ] Linux compatibility
- [ ] Large file handling (500MB+)
- [ ] Batch operations
- [ ] Error recovery

---

## Security Audit Before Release

### Required Changes
- [ ] Remove hardcoded ADMIN_KEY
- [ ] Add API key encryption
- [ ] Use environment variables for secrets
- [ ] Implement HTTPS for license server
- [ ] Add input validation
- [ ] Add SQL injection prevention
- [ ] Sanitize user inputs

### Optional but Recommended
- [ ] Two-factor authentication for license activation
- [ ] Rate limiting on API endpoints
- [ ] Audit logging
- [ ] CORS headers configuration
- [ ] DDoS protection

---

## Release Checklist

### Code Preparation
- [ ] Remove development files (.claude/, test_*.py)
- [ ] Update version in main.py
- [ ] Set DEV_MODE = False in dev_config.py
- [ ] Update all URLs to production
- [ ] Remove TODO comments
- [ ] Update README.md with real instructions
- [ ] Add LICENSE file

### Documentation
- [ ] Complete API_SETUP_GUIDE.md
- [ ] Write TROUBLESHOOTING.md
- [ ] Create video tutorials
- [ ] Document all features
- [ ] Add keyboard shortcuts guide
- [ ] Create FAQ

### Distribution
- [ ] Create Windows installer (PyInstaller)
- [ ] Create macOS app bundle
- [ ] Create Linux packages (AppImage, deb, rpm)
- [ ] Set up auto-update system
- [ ] Create GitHub releases
- [ ] Update website with download links

### Deployment
- [ ] Deploy license server to production
- [ ] Set up database backups
- [ ] Configure monitoring/alerts
- [ ] Test license server with actual users
- [ ] Set up support email/contact
- [ ] Create bug report system

---

## File Paths Summary

### Configuration Files Users Need to Update
```
api_config.json              # Add API keys
dev_config.py              # Set DEV_MODE = False
modules/config/            # May need license server URL update
```

### All Image/Asset Files (No changes needed)
```
modules/auto_uploader/helper_images/          # 20 PNG files
gui-redesign/assets/                          # SVG + HTML logos
presets/                                      # 5 preset JSON files
```

### Core Module Files (No public changes needed)
```
modules/link_grabber/       # Works out of the box
modules/video_downloader/   # Works out of the box
modules/video_editor/       # Works out of the box
modules/auto_uploader/      # May need IX Browser setup
```

### Server Files (Must be deployed)
```
server/app.py              # Flask license server
server/models.py           # Database models
server/routes.py           # API endpoints
```

---

## Estimated Tasks Before Public Release

| Task | Effort | Priority |
|------|--------|----------|
| Remove hardcoded secrets | 2 hours | CRITICAL |
| Write user documentation | 8 hours | CRITICAL |
| Create installers | 4 hours | HIGH |
| Security audit | 3 hours | HIGH |
| Deploy license server | 2 hours | HIGH |
| User testing | 5 hours | MEDIUM |
| Create video tutorials | 6 hours | MEDIUM |
| Set up support system | 2 hours | MEDIUM |
| GitHub setup | 1 hour | LOW |

**Total Estimate: 33 hours (4 business days)**

---

## Go/No-Go Decision Criteria

### Go Criteria (All must be met)
- [ ] DEV_MODE = False
- [ ] Admin key uses environment variable
- [ ] License server deployed and tested
- [ ] API key template documented
- [ ] User setup guide complete
- [ ] Security audit passed
- [ ] All critical bugs fixed
- [ ] Works on Windows, macOS, Linux

### No-Go Criteria (Any blocks release)
- [ ] Exposed hardcoded secrets
- [ ] License system not functional
- [ ] Critical bugs found
- [ ] No user documentation
- [ ] Insufficient testing

---

## Post-Release Monitoring

### First Week
- Monitor license server uptime
- Track user registrations
- Watch for bug reports
- Check support emails
- Monitor error logs

### Ongoing
- Weekly backup checks
- Monthly security updates
- Quarterly feature updates
- Regular user feedback review

---

## Support & Feedback

### User Support Channels to Setup
- Email: support@yoursite.com
- Discord: https://discord.gg/yourinvite
- GitHub Issues: Bug reports
- Website: FAQ and documentation

### Feedback Collection
- In-app error reporting
- User surveys
- Feature request voting
- Beta testing program

