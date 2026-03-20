# Binaries Folder

This folder contains external binaries needed for EXE build.

## Required Files:

### yt-dlp.exe
**Purpose:** Link Grabber module uses this for extracting links from social media platforms.

**Download:**
1. Visit: https://github.com/yt-dlp/yt-dlp/releases/latest
2. Download: `yt-dlp.exe` (Windows executable)
3. Place in this `bin/` folder

**Verification:**
```bash
bin/yt-dlp.exe --version
```

---

**Note:** Without `yt-dlp.exe`, the Link Grabber will not work in the compiled EXE on machines that don't have yt-dlp installed.
