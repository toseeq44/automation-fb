# 🛡️ Antivirus & EXE Disappearing Issues - Complete Guide

## 🔴 **Problem: EXE Disappears After Running**

**Symptom:** OneSoul.exe runs successfully but then the exe file disappears from the folder.

**Root Cause:** Windows Defender or other antivirus software is flagging the exe as a false positive and quarantining/deleting it.

---

## ✅ **Why This Happens**

PyInstaller-built executables are often flagged by antivirus software because:

1. **No Digital Signature** - Unsigned executables are suspicious to antivirus
2. **PyInstaller Bootloader** - Common pattern used by malware
3. **Self-extracting behavior** - Exe unpacks Python runtime at startup
4. **Missing Version Info** - No company/product metadata
5. **No Manifest** - Windows can't verify compatibility

---

## 🔧 **Fixes Implemented**

### 1. **Version Info Resource** ✅
Added `version_info.txt` with proper metadata:
- Company Name: OneSoul Inc
- Product Name: OneSoul Video Automation Suite
- File Version: 1.0.0.0
- Copyright info

**This tells Windows "this is a legitimate application"**

### 2. **Windows Manifest** ✅
Added `manifest.xml` with:
- Windows 10/11 compatibility declarations
- DPI awareness settings
- Modern Windows controls
- No admin privileges required (uac_admin=False)

**This prevents UAC prompts and SmartScreen warnings**

### 3. **UPX Disabled** ✅
UPX compression is disabled in spec file:
```python
upx=False,  # Prevents antivirus false positives
```

**Many antiviruses flag UPX-compressed executables**

---

## 🛡️ **Windows Defender - Add Exclusions**

### Method 1: Add Folder Exclusion (Recommended)

1. Open **Windows Security**
2. Go to **Virus & threat protection**
3. Click **Manage settings** under "Virus & threat protection settings"
4. Scroll down to **Exclusions**
5. Click **Add or remove exclusions**
6. Click **Add an exclusion** → **Folder**
7. Browse to your `dist\OneSoul\` folder
8. Click **Select Folder**

### Method 2: Add File Exclusion

1. Follow steps 1-5 above
2. Click **Add an exclusion** → **File**
3. Browse to `dist\OneSoul\OneSoul.exe`
4. Click **Open**

### Method 3: Add Process Exclusion

1. Follow steps 1-5 above
2. Click **Add an exclusion** → **Process**
3. Type: `OneSoul.exe`
4. Click **Add**

---

## 🔍 **Check if Antivirus Deleted Your EXE**

### Windows Defender:

1. Open **Windows Security**
2. Go to **Virus & threat protection**
3. Click **Protection history**
4. Look for recent quarantined items
5. If you see `OneSoul.exe`:
   - Click on it
   - Click **Actions** → **Restore**
   - Then add exclusion (see above)

### Windows Security Event Log:

1. Press `Win + R`
2. Type: `eventvwr.msc`
3. Press Enter
4. Navigate to: **Applications and Services Logs** → **Microsoft** → **Windows** → **Windows Defender** → **Operational**
5. Look for events with "Threat detected" or "Action taken"
6. Check if OneSoul.exe is mentioned

---

## 📝 **Other Antivirus Software**

### Avast / AVG:

1. Open Avast/AVG
2. Go to **Menu** → **Settings**
3. Go to **General** → **Exceptions**
4. Click **Add Exception**
5. Add `dist\OneSoul\` folder or `OneSoul.exe` file

### Norton:

1. Open Norton
2. Click **Settings**
3. Click **Antivirus**
4. Click **Scans and Risks**
5. Scroll to **Exclusions/Low Risks**
6. Click **Configure**
7. Add `dist\OneSoul\` folder

### McAfee:

1. Open McAfee
2. Click **Virus and Spyware Protection**
3. Click **Excluded Files**
4. Click **Add File** or **Add Folder**
5. Add `dist\OneSoul\` folder

### Kaspersky:

1. Open Kaspersky
2. Click **Settings**
3. Click **Additional** → **Threats and Exclusions**
4. Click **Manage Exclusions**
5. Click **Add**
6. Add `dist\OneSoul\` folder

---

## 🧪 **Testing After Fixes**

### Step 1: Clean Build
```bash
# Delete old build
rmdir /s /q build
rmdir /s /q dist

# Ensure ffmpeg exists
ls ffmpeg/ffmpeg.exe
ls ffmpeg/ffprobe.exe

# Build with new version info and manifest
.\.venv\Scripts\pyinstaller --clean onesoul_enhanced.spec
```

### Step 2: Check Build Output
```bash
cd dist\OneSoul
dir

# Should see:
# - OneSoul.exe (with proper icon)
# - _internal\ (folder)
# - ffmpeg\ (if ffmpeg was in root)
```

### Step 3: Test Execution

**IMPORTANT: Add antivirus exclusion BEFORE running!**

1. Add `dist\OneSoul\` to antivirus exclusions
2. Run `OneSoul.exe`
3. Check if exe still exists after running
4. Check if icon appears in taskbar

### Step 4: Verify Version Info

Right-click `OneSoul.exe` → Properties → Details tab

You should see:
- File description: OneSoul - All Solution One Place
- Product name: OneSoul Video Automation Suite
- File version: 1.0.0.0
- Copyright: Copyright (c) 2025 OneSoul Inc

**If you see these details, version info is embedded correctly!**

---

## 🚀 **Distribution to Other PCs**

### Before Distributing:

1. ✅ Build with version info and manifest
2. ✅ Test on your PC with antivirus exclusion
3. ✅ Verify version info is embedded
4. ✅ Check icon appears correctly
5. ✅ Create README with antivirus instructions

### Include in Distribution:

Create a `README.txt` file:

```
OneSoul - All Solution One Place
Version 1.0.0

⚠️  IMPORTANT: Antivirus False Positive Warning

Windows Defender or your antivirus may flag this application as suspicious.
This is a FALSE POSITIVE. The application is safe.

To use OneSoul:
1. Right-click OneSoul.exe → Properties → Details
   Verify: OneSoul Inc, Version 1.0.0
2. Add this folder to your antivirus exclusions
3. Run OneSoul.exe

For antivirus exclusion instructions, see ANTIVIRUS_GUIDE.md
```

---

## 🔐 **Optional: Code Signing (Best Solution)**

**Best way to prevent antivirus issues: Sign the exe with a digital certificate**

### Free Options:

1. **Self-signed certificate** (only works on your PC):
   ```bash
   # Create self-signed cert (Windows)
   New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=OneSoul Inc"

   # Sign exe
   signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com OneSoul.exe
   ```

2. **Let's Encrypt** - Not for code signing

### Paid Options:

1. **DigiCert** - $200-400/year
2. **Sectigo** - $150-300/year
3. **GlobalSign** - $200-350/year

**Note:** Code signing certificates require business verification.

---

## 📊 **Checklist**

Before release, verify:

- [ ] Version info embedded (`version_info.txt` in spec)
- [ ] Manifest embedded (`manifest.xml` in spec)
- [ ] UPX disabled (`upx=False` in spec)
- [ ] Icon properly embedded
- [ ] FFmpeg binaries included
- [ ] Tested on clean PC
- [ ] Antivirus exclusion instructions provided
- [ ] README.txt included with distribution

---

## 🐛 **Troubleshooting**

### Issue: EXE still disappears even after exclusion

**Solution:**
1. Check if multiple antivirus programs are running
2. Disable real-time protection temporarily
3. Rebuild exe with new version info
4. Try different antivirus exclusion methods

### Issue: Icon doesn't appear

**Solution:**
1. Verify icon file exists: `gui-redesign/assets/onesoul_logo.ico`
2. Check icon size (should be 256x256 or smaller)
3. Rebuild exe
4. Restart Windows Explorer (taskbar)

### Issue: Windows SmartScreen warning

**Solution:**
1. Click "More info"
2. Click "Run anyway"
3. Or: Sign exe with code signing certificate

### Issue: "Windows protected your PC" message

**Solution:**
This is Windows SmartScreen. Options:
1. Click "More info" → "Run anyway"
2. Add exclusion in Windows Defender
3. Sign exe with code signing certificate

---

## 📞 **Support**

If issues persist:

1. Check Windows Security Protection History
2. Check Event Viewer for Windows Defender logs
3. Try different antivirus exclusion methods
4. Rebuild exe with `--clean` flag
5. Test on different PC

---

**Last Updated:** 2026-01-09
**Status:** ✅ Version Info & Manifest Added
