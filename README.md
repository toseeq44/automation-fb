# ContentFlow Pro - Video Automation Suite

> **Complete video automation platform with link grabbing, downloading, editing, metadata removal, and licensing system**

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-Proprietary-red)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [License System](#license-system)
- [Usage Guide](#usage-guide)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Support](#support)

---

## 🎯 Overview

ContentFlow Pro is a professional desktop application for content creators and social media managers. It provides a complete suite of tools for automating video workflows across multiple platforms.

### Supported Platforms
- ✅ YouTube
- ✅ Instagram
- ✅ TikTok
- ✅ Facebook
- ✅ Twitter/X

---

## ✨ Features

### 1. 🔗 Link Grabber
- Extract video links from creator profiles and channels
- Multi-platform support (YouTube, Instagram, TikTok, Facebook, Twitter)
- Bulk URL processing
- Cookie support (manual + browser auto-extract)
- Rate limiting for safe extraction
- Export links to file

### 2. 📥 Video Downloader
- Download videos from extracted links
- Quality selection (360p to 8K)
- Audio-only extraction (MP3)
- Subtitle download
- Batch downloads with queue system
- Pause/Resume/Cancel support
- Resume interrupted downloads
- Custom output folders
- Filename customization

### 3. ✂️ Video Editor
- Trim, crop, rotate, and flip videos
- Add text overlays with customization
- Add watermarks/logos
- Background music mixing
- Apply filters (brightness, contrast, saturation, blur, etc.)
- Merge multiple videos
- Add transitions
- Multiple output formats (MP4, AVI, MOV, MKV, WebM)
- Quality presets

### 4. 🧹 Metadata Remover
- Remove ALL metadata from video files
- Batch processing
- Preview metadata before removal
- Backup original files option
- Progress tracking

### 5. 📤 Auto Uploader (Coming Soon)
- Automated uploads to YouTube, Instagram, TikTok, Facebook
- Scheduled posting
- Batch upload support

### 6. 🔐 License System
- Hardware-based license binding
- Online and offline (3-day grace period) validation
- Secure activation/deactivation
- Device transfer support
- Encrypted local license storage

---

## 🚀 Installation

### Prerequisites

- **Python 3.8 or higher**
- **pip** package manager
- **yt-dlp** (for link grabbing and downloading)
- **FFmpeg** (for video processing)

### Step 1: Install System Dependencies

#### Windows
```bash
# Install Python from python.org
# Install FFmpeg from ffmpeg.org

# Add both to PATH
```

#### macOS
```bash
brew install python3 ffmpeg yt-dlp
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3 python3-pip ffmpeg
pip3 install yt-dlp
```

### Step 2: Clone Repository

```bash
git clone https://github.com/toseeq44/automation-fb.git
cd automation-fb
```

### Step 3: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Run the Application

```bash
python main.py
```

---

## 🔐 License System

### How It Works

1. **Hardware Binding**: Each license is tied to your device's hardware fingerprint
2. **One Device**: One license = one active device at a time
3. **Online Validation**: App validates license with server periodically
4. **Offline Grace**: Works offline for up to 3 days after last validation
5. **Device Transfer**: Deactivate on old device, activate on new device

### Subscription Plans

#### 📅 Monthly Plan - $20/month
- All features unlocked
- Unlimited usage
- 30 days access

#### 📆 Yearly Plan - $200/year (Save $40!)
- All features unlocked
- Unlimited usage
- 365 days access
- Best value!

#### 🎁 7-Day Free Trial
- All features
- No credit card required
- Perfect for testing

### Getting a License

**Contact:**
- Phone: 0307-7361139
- Email: support@contentflowpro.com

### Activating Your License

1. Launch ContentFlow Pro
2. Enter your license key when prompted
3. Click "Activate License"
4. Done! App is now fully unlocked

### License Management

- **View License Info**: Click on license status in status bar
- **Deactivate**: Open license info dialog → click "Deactivate"
- **Transfer to New Device**: Deactivate on old device → activate on new device

---

## 📖 Usage Guide

### Link Grabber

1. Open **Link Grabber** module
2. Enter creator URL (e.g., `https://youtube.com/@channelname`)
3. (Optional) Set max videos limit
4. (Optional) Add cookies for private content
5. Click **"Start Grabbing"**
6. Wait for extraction to complete
7. Click **"Save to Folder"** to export links

**Tips:**
- Use cookies for age-restricted or private content
- Enable rate limiting to avoid detection
- Supports channel, profile, and playlist URLs

### Video Downloader

1. Open **Video Downloader** module
2. Import links from Link Grabber or paste URLs
3. Select quality for each video
4. Click **"Download All"** or select specific videos
5. Monitor progress in real-time
6. Videos saved to configured output folder

**Features:**
- Individual progress bars
- Download speed indicators
- Pause/Resume support
- Auto-retry on failure

### Video Editor

1. Open **Video Editor** module
2. Load video file
3. Use tools palette to apply edits:
   - **Trim**: Set start/end time
   - **Crop**: Choose aspect ratio
   - **Text**: Add custom text overlays
   - **Watermark**: Add logo/image
   - **Filters**: Adjust brightness, contrast, etc.
4. Preview changes
5. Export edited video

**Tips:**
- Use "Before/After" preview to compare
- Save project to re-edit later
- Multiple text/watermark layers supported

### Metadata Remover

1. Open **Metadata Remover** module
2. Add video files (drag & drop or click "Add Files")
3. Preview metadata
4. Check "Backup Originals" if desired
5. Click **"Remove Metadata"**
6. Done! Metadata-free videos in output folder

---

## 📁 Project Structure

```
contentflow-pro/
├── main.py                      # Application entry point
├── gui.py                       # Main GUI window
├── requirements.txt             # Python dependencies
├── config.json                  # User configuration
├── README.md                    # This file
│
├── modules/
│   ├── license/                 # License management
│   │   ├── hardware_id.py       # Hardware fingerprinting
│   │   └── license_manager.py   # Activation/validation
│   │
│   ├── logging/                 # Logging system
│   │   └── logger.py
│   │
│   ├── config/                  # Configuration
│   │   └── config_manager.py
│   │
│   ├── link_grabber/            # Link extraction
│   │   ├── core.py
│   │   └── gui.py
│   │
│   ├── video_downloader/        # Video downloading
│   │   ├── core.py
│   │   └── gui.py
│   │
│   ├── video_editor/            # Video editing
│   │   ├── core.py
│   │   └── gui.py
│   │
│   ├── metadata_remover/        # Metadata removal
│   │   └── gui.py
│   │
│   ├── auto_uploader/           # Auto upload (coming soon)
│   │   └── gui.py
│   │
│   └── ui/                      # UI components
│       ├── activation_dialog.py
│       └── license_info_dialog.py
│
└── server/                      # License server (backend)
    ├── app.py                   # Flask application
    ├── models.py                # Database models
    ├── routes.py                # API routes
    ├── requirements.txt
    └── README.md
```

---

## ⚙️ Configuration

Configuration file: `~/.contentflow/config.json`

### Default Settings

```json
{
  "app": {
    "theme": "dark",
    "language": "en"
  },
  "license": {
    "server_url": "http://localhost:5000"
  },
  "paths": {
    "downloads": "~/Downloads/ContentFlow",
    "edited_videos": "~/Videos/ContentFlow"
  },
  "rate_limiting": {
    "enabled": true,
    "preset": "balanced"
  },
  "downloader": {
    "default_quality": "1080p",
    "concurrent_downloads": 3
  },
  "editor": {
    "default_format": "mp4",
    "default_codec": "h264"
  }
}
```

### Editing Configuration

1. Open config file at `~/.contentflow/config.json`
2. Edit values as needed
3. Save file
4. Restart application

**or**

Use in-app Settings dialog (coming soon)

---

## 🛠️ Development

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/toseeq44/automation-fb.git
cd automation-fb

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python main.py
```

### Running License Server Locally

```bash
cd server
pip install -r requirements.txt
python app.py
```

Server runs at `http://localhost:5000`

### Project Dependencies

- **PyQt5**: GUI framework
- **yt-dlp**: Video downloading and metadata extraction
- **requests**: HTTP client for license API
- **cryptography**: License encryption
- **FFmpeg**: Video processing (system dependency)

---

## 🐛 Troubleshooting

### License Issues

**Problem**: "Unable to connect to license server"
- **Solution**: Check internet connection. App works offline for 3 days after last validation.

**Problem**: "Hardware ID mismatch"
- **Solution**: Hardware changed. Deactivate old license and reactivate with new hardware.

**Problem**: "License already activated on another device"
- **Solution**: Deactivate license on old device first, then activate on new device.

### Link Grabber Issues

**Problem**: "No videos found"
- **Solutions**:
  - Check URL is correct
  - Try adding cookies for private/age-restricted content
  - Ensure yt-dlp is installed and updated

**Problem**: "Login required"
- **Solution**: Add cookies (manual or browser auto-extract)

### Downloader Issues

**Problem**: "Download failed"
- **Solutions**:
  - Check internet connection
  - Verify video is still available
  - Try lower quality
  - Add cookies if content is restricted

**Problem**: "FFmpeg not found"
- **Solution**: Install FFmpeg and add to system PATH

### General Issues

**Problem**: Application won't start
- **Solutions**:
  - Verify Python 3.8+ is installed
  - Run `pip install -r requirements.txt`
  - Check logs at `~/.contentflow/logs/`

**Problem**: Slow performance
- **Solutions**:
  - Reduce concurrent downloads
  - Disable hardware acceleration in editor
  - Close other applications

---

## 📝 Logs

Logs are stored at: `~/.contentflow/logs/`

- **Daily logs**: `contentflow_YYYYMMDD.log`
- **Error logs**: `errors_YYYYMMDD.log`

Logs automatically cleanup after 30 days.

**Export logs**: Use in-app export feature or manually copy from logs folder

---

## 🔒 Privacy & Security

- License data encrypted locally
- Hardware ID uses one-way hash (SHA-256)
- No personal data collected except email for license
- Cookies stored locally, never transmitted to our servers
- All license API calls use HTTPS

---

## 🆘 Support

### Contact

- **Developer**: Toseeq Ur Rehman
- **Phone**: 0307-7361139
- **Email**: support@contentflowpro.com
- **GitHub Issues**: https://github.com/toseeq44/automation-fb/issues

### Getting Help

1. Check this README
2. Review logs at `~/.contentflow/logs/`
3. Search GitHub issues
4. Contact support

### Reporting Bugs

When reporting bugs, please include:
- Operating system and version
- Python version
- Full error message
- Steps to reproduce
- Relevant log files

---

## 📜 License

**Proprietary Software**

ContentFlow Pro is proprietary software. You must have a valid license to use this software. Unauthorized copying, distribution, or modification is prohibited.

© 2024 Toseeq Ur Rehman. All rights reserved.

---

## 🎉 Acknowledgments

- **yt-dlp**: For excellent video downloading capabilities
- **PyQt5**: For powerful GUI framework
- **FFmpeg**: For video processing
- **browser_cookie3**: For browser cookie extraction

---

## 🗺️ Roadmap

### Upcoming Features

- ✅ Phase 1: License System (Completed)
- ⏳ Phase 2: Video Downloader (In Progress)
- ⏳ Phase 3: Metadata Remover (In Progress)
- 📅 Phase 4: Video Editor (Planned)
- 📅 Phase 5: Auto Uploader (Planned)
- 📅 Phase 6: Settings UI (Planned)
- 📅 Phase 7: Bulk Operations (Planned)
- 📅 Phase 8: Scheduler (Planned)

---

## 💡 Tips & Best Practices

1. **Always backup original files** before editing
2. **Use cookies** for private/age-restricted content
3. **Enable rate limiting** to avoid platform detection
4. **Keep license activated** - validate online every 3 days
5. **Update regularly** for new features and bug fixes
6. **Export logs** when reporting issues
7. **Use balanced rate limiting** for best results

---

## 📊 System Requirements

### Minimum Requirements
- **OS**: Windows 10, macOS 10.15, or Linux (Ubuntu 20.04+)
- **CPU**: Dual-core 2.0 GHz
- **RAM**: 4 GB
- **Storage**: 500 MB for app + space for downloaded videos
- **Internet**: Required for license validation and downloading

### Recommended Requirements
- **OS**: Windows 11, macOS 13+, or Linux (Ubuntu 22.04+)
- **CPU**: Quad-core 3.0 GHz or better
- **RAM**: 8 GB or more
- **Storage**: SSD with 50 GB+ free space
- **Internet**: Broadband connection

---

**Built with ❤️ by Toseeq Ur Rehman**

---

*Last Updated: 2024-10-23*
