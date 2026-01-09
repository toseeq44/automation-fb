# OneSoul EXE Build Instructions

## 🔴 **CRITICAL: EXE Disappearing Issue**

**If your exe disappears after running, it's being deleted by antivirus!**

See **ANTIVIRUS_GUIDE.md** for complete solution.

**Quick Fix:**
1. Add `dist\OneSoul\` folder to Windows Defender exclusions
2. Rebuild exe (it now includes version info to prevent false positives)

---

## ✅ Pre-Build Checklist

Before running the build command, ensure these files/folders exist in the **ROOT directory**:

```
automation-fb/
├── cloudflared.exe          ✓ (Your local file - not in git)
├── ffmpeg/                  ✓ (Your local folder - not in git) **REQUIRED**
│   ├── ffmpeg.exe          ⚠️  Must exist before build
│   └── ffprobe.exe         ⚠️  Must exist before build
├── bin/
│   └── yt-dlp.exe          ⚠️  Optional (auto-download available)
├── main.py                  ✓ (Already in git)
├── onesoul_enhanced.spec    ✓ (Already in git - updated)
├── version_info.txt         ✓ (NEW - prevents antivirus issues)
├── manifest.xml             ✓ (NEW - Windows compatibility)
├── gui-redesign/            ✓ (Already in git)
├── modules/                 ✓ (Already in git)
└── requirements.txt         ✓ (Already in git)
```

### 📥 Quick Download (NEW)

Run the helper script to download missing binaries:
```bash
download_binaries.bat
```

This will:
- Check for missing ffmpeg.exe and ffprobe.exe
- Auto-download yt-dlp.exe if missing
- Verify all required files exist

**Manual Download:**
- **FFmpeg:** https://github.com/BtbN/FFmpeg-Builds/releases (Download `ffmpeg-master-latest-win64-gpl.zip`)
- **yt-dlp:** https://github.com/yt-dlp/yt-dlp/releases (Download `yt-dlp.exe`)

### File Sizes (Approximate)
- `cloudflared.exe`: ~50-60 MB
- `ffmpeg/ffmpeg.exe`: ~100-120 MB
- `ffmpeg/ffprobe.exe`: ~100-120 MB
- `yt-dlp.exe`: ~10-15 MB

**Note:** Binary files are NOT in git repository (`.gitignore`). Download them manually.

---

## 🛠️ Build Command

### Option 1: Using Virtual Environment (Recommended)
```bash
# 1. Activate virtual environment
.\.venv\Scripts\activate

# 2. Ensure PyInstaller is installed
pip install pyinstaller

# 3. Clean previous builds
pyinstaller --clean onesoul_enhanced.spec

# 4. Check output
ls -la dist/OneSoul/
```

### Option 2: Without Virtual Environment
```bash
# If PyInstaller is globally installed
pyinstaller --clean onesoul_enhanced.spec
```

---

## 📦 Build Output

After successful build, you'll see:

```
dist/OneSoul/
├── OneSoul.exe                         # Main executable (your app)
├── _internal/                          # Python runtime & dependencies
│   ├── (Python DLLs and packages)
│   └── ...
├── cloudflared.exe                     # Bundled (if found)
├── ffmpeg/                             # Bundled (if found)
│   ├── ffmpeg.exe
│   └── ffprobe.exe
├── modules/auto_uploader/              # Extracted assets
│   ├── helper_images/                  # Image recognition files
│   │   ├── add_videos_button.png
│   │   ├── publish_button_after_data.png
│   │   └── ... (18 PNG files total)
│   ├── creator_shortcuts/
│   ├── creators/
│   └── data/
├── gui-redesign/assets/                # GUI resources
│   ├── onesoul_logo.ico
│   ├── onesoul_logo.svg
│   └── ...
├── api_config.json                     # Config file
└── presets/                            # (if exists)
```

**Total size:** Approximately 400-600 MB (with all dependencies)

---

## ⚠️ Expected Warnings (During Build)

The spec file will show these messages - **THIS IS NORMAL**:

### ✅ If files found:
```
✓ ffmpeg directory found
✓ presets directory found
```

### ⚠️ If files missing (still builds successfully):
```
⚠️  WARNING: cloudflared.exe not found - skipping
⚠️  WARNING: ffmpeg directory not found - video editing may not work
⚠️  WARNING: presets directory not found
```

**Note:** Build will complete even if these files are missing. You can manually add them later to `dist/OneSoul/` folder.

---

## 🧪 Testing the EXE

### Test on YOUR machine (quick test):
```bash
# Run from dist folder
cd dist/OneSoul
./OneSoul.exe
```

**Expected:**
1. ✅ No console window (GUI mode)
2. ✅ License activation dialog appears (if no license)
3. ✅ Main OneSoul window opens
4. ✅ All modules load correctly

### Test on CLEAN machine (production test):
1. **Copy entire `dist/OneSoul/` folder** to a USB drive
2. Transfer to a Windows PC **WITHOUT Python installed**
3. Run `OneSoul.exe`
4. Test all features:
   - ✓ License activation
   - ✓ Auto uploader (IXBrowser)
   - ✓ Video downloader
   - ✓ Video editor (requires ffmpeg)
   - ✓ Link grabber

---

## 🐛 Troubleshooting

### Build fails with "ModuleNotFoundError"
```bash
# Install missing dependency
pip install <missing-module>

# Or reinstall all
pip install -r requirements.txt
```

### "cloudflared.exe not found" during build
- **Solution:** Place `cloudflared.exe` in root directory
- **Or:** Ignore warning - add manually later to `dist/OneSoul/`

### "ffmpeg directory not found" during build
- **Solution:** Create `ffmpeg/` folder in root with `ffmpeg.exe` and `ffprobe.exe`
- **Or:** Ignore warning - video editing won't work until added

### EXE runs but shows errors
**Check logs:**
- Location: `%APPDATA%/OneSoul/logs/`
- File: `onesoul.log`

**Common issues:**
1. **Missing helper_images:** Build didn't include PNG files
   - Fix: Check `modules/auto_uploader/helper_images/*.png` exists before build
2. **License server unreachable:**
   - Fix: Start server separately or set DEV_MODE=True
3. **Video upload fails:**
   - Fix: Ensure helper_images loaded correctly

---

## 📝 Build Environment Info

**Tested on:**
- Python: 3.x
- PyInstaller: 5.x+
- OS: Windows 10/11
- Architecture: x64

**Dependencies bundled:**
- PyQt5 (GUI)
- Selenium (Browser automation)
- OpenCV (Image recognition)
- yt-dlp (Video downloading)
- moviepy (Video editing - requires ffmpeg)
- All other packages from requirements.txt

---

## 🚀 Distribution

### For End Users:
1. **Zip the entire `dist/OneSoul/` folder**
2. **Upload to cloud/send to customers**
3. **User extracts and runs `OneSoul.exe`**
4. **Provide license key for activation**

### Recommended ZIP size:
- With cloudflared + ffmpeg: ~500-600 MB
- Without optional files: ~200-300 MB

---

## 🔐 License System

**Server must be running for license validation:**

```bash
# Terminal 1: Start license server
cd server/
python app.py

# Terminal 2: Start cloudflared tunnel
.\cloudflared.exe tunnel --url http://localhost:5000

# Copy the public URL (e.g., https://xxx.trycloudflare.com)
# Update client config with this URL
```

**Generate licenses:**
- Admin GUI opens automatically when server starts
- Enter customer email, plan type, duration
- Copy license key → send to customer

---

## 📞 Support

If build issues occur:
1. Check this file for troubleshooting steps
2. Verify all files in checklist exist
3. Check build logs for specific errors
4. Ensure all dependencies installed: `pip install -r requirements.txt`

---

**Last Updated:** 2025-12-18
**Build Configuration:** onesoul_enhanced.spec
**Path Compatibility:** ✅ Fixed for PyInstaller (commit: ab5b484)
