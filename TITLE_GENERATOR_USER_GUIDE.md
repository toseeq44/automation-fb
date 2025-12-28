# 🎬 AI Title Generator - Complete User Setup Guide

## 📋 Overview

This guide will help you set up the **Enhanced AI-Powered Title Generator** that creates content-accurate, multilingual video titles.

---

## ⚠️ IMPORTANT: Python Version Compatibility

**CRITICAL:** The AI features require **Python 3.11 or 3.12**

**❌ Python 3.14 is NOT supported** (PyTorch compatibility issues)
**❌ Python 3.9 or older** (missing features)

**Check your Python version:**
```bash
python --version
```

If you have Python 3.14 or newer, you MUST install Python 3.11 or 3.12.

---

## 🚀 Quick Start (Automatic Installation)

### Option 1: One-Click Auto-Install (Easiest)

1. **Open the application**
2. **Click Title Generator**
3. **You'll see a red banner:** "BASIC MODE - LIMITED FEATURES"
4. **Click the green button:** "🚀 AUTO-INSTALL AI Packages"
5. **Wait 10-15 minutes** (downloading ~2-4GB)
6. **Install Visual C++ when prompted** (see below)
7. **Restart application**
8. **✅ Done! Enhanced Mode activated**

---

## 🔧 Manual Installation (Step-by-Step)

### Step 1: Check System Requirements

**Minimum Requirements:**
- ✅ Windows 10/11 (64-bit)
- ✅ Python 3.11 or 3.12 (NOT 3.14!)
- ✅ 5GB free disk space
- ✅ Internet connection (for downloads)
- ✅ Administrator rights (for installing tools)

---

### Step 2: Install Required System Tools

#### A. Visual C++ Redistributables (REQUIRED)

**Why needed?** All AI packages use compiled C/C++ code that needs these runtime libraries.

**Download:** https://aka.ms/vs/17/release/vc_redist.x64.exe

**Install:**
1. Download the file (25 MB)
2. Right-click → "Run as Administrator"
3. Click "Install"
4. Wait 1-2 minutes
5. Done!

**If already installed:** Run again and choose "Repair"

---

#### B. Tesseract OCR (REQUIRED for text extraction)

**Why needed?** Extracts on-screen text from videos for better title generation.

**Download:** https://github.com/UB-Mannheim/tesseract/wiki

Choose: **tesseract-ocr-w64-setup-5.3.3.exe** (latest version)

**Install:**
1. Download the installer (50 MB)
2. Run installer
3. **IMPORTANT:** During installation, note the install path (default: `C:\Program Files\Tesseract-OCR`)
4. **Add to PATH:**
   - Open System Environment Variables
   - Edit PATH
   - Add: `C:\Program Files\Tesseract-OCR`
5. Click OK
6. Restart Command Prompt

**Verify installation:**
```bash
tesseract --version
```

Should show: `tesseract 5.3.3` or similar

---

### Step 3: Install Python Packages

**Open Command Prompt or PowerShell:**

```bash
# Activate your virtual environment first (if using)
# For example:
.venv\Scripts\activate

# Then install AI packages:
pip install openai-whisper transformers torch opencv-python pytesseract scikit-learn groq moviepy
```

**Download size:** ~2-4GB (be patient!)

**Time:** 10-15 minutes depending on internet speed

---

### Step 4: Verify Installation

**Test if everything works:**

```bash
python -c "import torch; print('✅ PyTorch:', torch.__version__)"
python -c "import whisper; print('✅ Whisper: OK')"
python -c "import transformers; print('✅ Transformers: OK')"
python -c "import cv2; print('✅ OpenCV: OK')"
python -c "import pytesseract; print('✅ Tesseract: OK')"
```

**All should show ✅ with no errors!**

---

### Step 5: Restart Application

**Close the application completely** (not just the window)

**Reopen it**

**Open Title Generator** - You should now see:

```
┌────────────────────────────────────────┐
│ ✅ ENHANCED MODE - FULL AI FEATURES    │
│                                        │
│ 🎙️  Audio Analysis + Language         │
│ 👁️  Visual Content Analysis           │
│ 🌐 Multilingual Support               │
│ 🎯 Content-Aware Title Generation     │
└────────────────────────────────────────┘
```

**✅ SUCCESS! You're ready to generate amazing titles!**

---

## ❌ Troubleshooting

### Problem 1: "DLL initialization failed" Error

**Symptoms:**
```
Error: [WinError 1114] A dynamic link library (DLL) initialization routine failed
```

**Solutions:**

**Try in this order:**

1. **Install Visual C++ Redistributables**
   - Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - Run as Administrator
   - Choose "Repair" if already installed

2. **Check Python Version**
   ```bash
   python --version
   ```
   - If Python 3.14 → **Downgrade to Python 3.11 or 3.12**
   - Download Python 3.11: https://www.python.org/downloads/release/python-31110/

3. **Reinstall PyTorch (CPU version)**
   ```bash
   pip uninstall torch torchvision torchaudio -y
   pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cpu
   ```

4. **Fresh Install Everything**
   ```bash
   # Uninstall all AI packages
   pip uninstall openai-whisper transformers torch torchvision torchaudio -y

   # Fresh install
   pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cpu
   pip install openai-whisper transformers opencv-python pytesseract scikit-learn
   ```

---

### Problem 2: Still Shows "Basic Mode" After Installation

**Check:**

1. **Did you restart the application?**
   - Must completely close and reopen

2. **Check logs:**
   - Look for "✅ Found AI packages installed via pip"
   - If not found, packages didn't install correctly

3. **Test imports manually:**
   ```bash
   python -c "import torch; import whisper; import transformers; print('All OK!')"
   ```
   - If error → packages not working
   - If success → restart application again

4. **Check virtual environment:**
   - Make sure you're in the correct venv
   - Check: `where python` (should point to your venv)

---

### Problem 3: Tesseract Not Found

**Symptoms:**
```
pytesseract.pytesseract.TesseractNotFoundError
```

**Solutions:**

1. **Install Tesseract** (see Step 2B above)

2. **Add to PATH:**
   ```
   C:\Program Files\Tesseract-OCR
   ```

3. **Or set path in code manually:**
   Create file: `C:\Users\<YourName>\.automation-fb\tesseract_path.txt`

   Contents:
   ```
   C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

---

### Problem 4: "Out of Memory" During Installation

**Solutions:**

1. **Free up disk space** (need minimum 5GB)

2. **Install packages one by one:**
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   pip install transformers
   pip install openai-whisper
   pip install opencv-python pytesseract scikit-learn groq moviepy
   ```

---

### Problem 5: Slow Download Speeds

**Solutions:**

1. **Use different mirror:**
   ```bash
   pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple torch transformers
   ```

2. **Download during off-peak hours**

3. **Use conda instead:**
   ```bash
   conda install pytorch torchvision torchaudio cpuonly -c pytorch
   pip install openai-whisper transformers
   ```

---

## 🎯 What You Get with Enhanced Mode

### Features Unlocked:

✅ **Audio Transcription**
- Automatic speech-to-text
- 20+ languages detected automatically
- Keywords extracted from speech

✅ **Visual Content Analysis**
- Object detection (food, people, gaming, etc.)
- Scene detection (indoor, outdoor, kitchen, etc.)
- Action recognition (cooking, gaming, tutorial, etc.)
- Niche classification (cooking, gaming, review, fitness, etc.)

✅ **Text Extraction (OCR)**
- On-screen text detected
- Multiple languages supported
- Captions, titles, graphics extracted

✅ **Multilingual Title Generation**
- Titles in 7+ languages:
  - English, Portuguese, French, Spanish
  - Urdu, Hindi, Arabic
- Auto-detects video language
- Platform-specific optimization

✅ **Platform Optimization**
- Facebook (255 chars)
- TikTok (150 chars)
- Instagram (125 chars)
- YouTube (100 chars)

✅ **Content-Aware Titles**
- Based on ACTUAL video content
- Not generic templates
- Includes specific objects, actions, topics

---

## 📊 Before vs After Comparison

### Example 1: French Cooking Video

**Basic Mode (Generic):**
```
"Amazing Content in 30 Seconds"
```

**Enhanced Mode (Content-Aware):**
```
"Recette de Pâtes Carbonara en 30 Secondes | Cuisine Rapide"
(Pasta Carbonara Recipe in 30 Seconds | Quick Cooking)
```

---

### Example 2: Urdu Tutorial Video

**Basic Mode (Generic):**
```
"Tutorial Video"
```

**Enhanced Mode (Content-Aware):**
```
"موبائل کی ترتیبات | مکمل گائیڈ"
(Mobile Settings | Complete Guide)
```

---

### Example 3: Gaming Montage

**Basic Mode (Generic):**
```
"Game Video Insane"
```

**Enhanced Mode (Content-Aware):**
```
"Call of Duty Epic Moments | Best Kills Compilation"
```

---

## 📝 Summary Checklist

**Before using Enhanced Title Generator:**

- [ ] Python 3.11 or 3.12 installed (NOT 3.14)
- [ ] Visual C++ Redistributables installed
- [ ] Tesseract OCR installed
- [ ] All Python packages installed (`pip install ...`)
- [ ] Imports tested successfully
- [ ] Application restarted
- [ ] "ENHANCED MODE" green banner visible

**Once all checked ✅, you're ready!**

---

## 🆘 Still Need Help?

If you followed all steps and still have issues:

1. **Check Python version again** - Most common issue!
2. **Reinstall Visual C++ Redistributables** - Choose "Repair"
3. **Try older PyTorch version** - `pip install torch==2.4.0`
4. **Create fresh virtual environment** - Start from scratch
5. **Check application logs** - Look for specific error messages

---

## 💡 Pro Tips

1. **First title generation is slower** - Models download on first use (~500MB)
2. **Subsequent titles are fast** - Models cached locally
3. **Works offline** - After first download, no internet needed
4. **Platform selection matters** - Choose your target platform for optimized titles
5. **Groq API key needed** - For AI refinement (free tier available)

---

**Happy title generating! 🎉**
