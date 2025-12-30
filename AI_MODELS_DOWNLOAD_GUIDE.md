# 📥 AI MODELS DOWNLOAD GUIDE - Complete List + URLs

## 🎯 Quick Summary

**All models should be placed in ONE location:**
- **Windows:** `C:\AI_Models\` or `Desktop\AI_Models\`
- **Linux/Mac:** `~/AI_Models/` or `~/Desktop/AI_Models/`

**Total Size:** ~3 GB (one-time download)
**Internet Required:** Only for initial download
**After Download:** Works 100% offline!

---

## 📦 REQUIRED MODELS (Must Download)

### 1. **PyTorch** (Deep Learning Framework)
**Required by:** BLIP, YOLO
**Size:** ~2 GB
**Installation:**
```bash
pip install torch torchvision torchaudio
```

**URLs:**
- **Official:** https://pytorch.org/get-started/locally/
- **Download:** Auto-installs via pip
- **Documentation:** https://pytorch.org/docs/stable/index.html

**Verification:**
```python
import torch
print(torch.__version__)  # Should show: 2.x.x
print(torch.cuda.is_available())  # GPU check (optional)
```

---

### 2. **Transformers Library** (HuggingFace)
**Required by:** BLIP models
**Size:** ~500 MB
**Installation:**
```bash
pip install transformers
```

**URLs:**
- **Official:** https://huggingface.co/docs/transformers/
- **Download:** Auto-installs via pip
- **GitHub:** https://github.com/huggingface/transformers

---

## 🔍 VISION MODELS (For Image Analysis)

### 3. **BLIP Image Captioning Model** ⭐ MOST IMPORTANT!
**Purpose:** Describes what's happening in video frames
**Size:** ~500 MB
**Accuracy:** 90%+
**Required:** YES (for accurate title generation)

**Download Methods:**

**Method 1: Automatic (Recommended)**
```python
# Run this Python script - downloads automatically to cache:
from transformers import BlipProcessor, BlipForConditionalGeneration

# Downloads to ~/.cache/huggingface/hub/
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

print("✅ BLIP model downloaded!")
```

**Method 2: Manual Download to AI_Models**
```python
import os
from transformers import BlipProcessor, BlipForConditionalGeneration

# Download to specific folder
models_dir = r"C:\AI_Models\blip-image-captioning-base"  # Windows
# models_dir = os.path.expanduser("~/AI_Models/blip-image-captioning-base")  # Linux/Mac

processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

# Save to AI_Models folder
processor.save_pretrained(models_dir)
model.save_pretrained(models_dir)

print(f"✅ BLIP saved to: {models_dir}")
```

**Method 3: Direct Download (Advanced)**
```bash
# Using git-lfs (large file support)
cd C:\AI_Models\  # or ~/AI_Models/
git lfs install
git clone https://huggingface.co/Salesforce/blip-image-captioning-base
```

**URLs:**
- **HuggingFace:** https://huggingface.co/Salesforce/blip-image-captioning-base
- **Paper:** https://arxiv.org/abs/2201.12086
- **Demo:** https://huggingface.co/spaces/Salesforce/BLIP

**Folder Structure After Download:**
```
C:\AI_Models\
└── blip-image-captioning-base\
    ├── config.json                    (1 KB)
    ├── preprocessor_config.json       (1 KB)
    ├── pytorch_model.bin              (500 MB) ← Main file!
    ├── special_tokens_map.json        (1 KB)
    ├── tokenizer_config.json          (1 KB)
    └── vocab.txt                      (232 KB)
```

---

### 4. **YOLO (YOLOv8 Nano)** ⭐ OBJECT DETECTION!
**Purpose:** Detects objects in video (person, food, phone, etc.)
**Size:** 6 MB (very small!)
**Accuracy:** 85%
**Required:** Recommended (but optional)

**Download Methods:**

**Method 1: Automatic (Easiest)**
```python
from ultralytics import YOLO

# Downloads automatically to ~/.cache/ultralytics/
model = YOLO('yolov8n.pt')
print("✅ YOLO downloaded!")
```

**Method 2: Manual Download**
```bash
# Download directly:
# Go to: https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
# Or use wget:
cd C:\AI_Models\  # or ~/AI_Models/
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
```

**Method 3: Copy from Cache**
```bash
# After automatic download, copy to AI_Models:
# Windows:
copy %USERPROFILE%\.cache\ultralytics\yolov8n.pt C:\AI_Models\yolov8n.pt

# Linux/Mac:
cp ~/.cache/ultralytics/yolov8n.pt ~/AI_Models/yolov8n.pt
```

**URLs:**
- **GitHub:** https://github.com/ultralytics/ultralytics
- **Direct Download:** https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
- **Documentation:** https://docs.ultralytics.com/
- **All Versions:** https://github.com/ultralytics/assets/releases

**File Details:**
```
yolov8n.pt           (6 MB) ← Single file!
```

---

## 🎙️ AUDIO MODELS (Optional - For Language Detection)

### 5. **Whisper (Optional)**
**Purpose:** Audio transcription and language detection
**Size:** 150-500 MB (depending on version)
**Required:** NO (uses Groq API instead)
**Use Case:** If you want offline audio analysis

**Download (If Needed):**
```python
import whisper

# Download base model (150 MB)
model = whisper.load_model("base")

# Or download to specific location:
import os
os.environ['WHISPER_CACHE_DIR'] = r"C:\AI_Models\whisper"
model = whisper.load_model("base")
```

**Versions Available:**
| Model | Size | Accuracy |
|-------|------|----------|
| tiny | 75 MB | Good |
| base | 150 MB | Better |
| small | 500 MB | Best |

**URLs:**
- **GitHub:** https://github.com/openai/whisper
- **Models:** https://github.com/openai/whisper/blob/main/whisper/__init__.py

**Note:** Currently using **Groq Whisper API** (online), so local model NOT required.

---

## 🔤 OCR MODELS (Text Recognition)

### 6. **Tesseract OCR** (System Binary)
**Purpose:** Extract text from video frames
**Size:** ~50 MB (system installation)
**Required:** YES
**Note:** This is NOT a Python package - it's a system binary!

**Installation:**

**Windows:**
```bash
# Download installer from:
https://github.com/UB-Mannheim/tesseract/wiki

# Or use package manager:
choco install tesseract

# Or scoop:
scoop install tesseract
```

**Linux/Ubuntu:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr

# With language packs:
sudo apt-get install tesseract-ocr-eng tesseract-ocr-ara tesseract-ocr-hin
```

**Mac:**
```bash
brew install tesseract

# With language packs:
brew install tesseract-lang
```

**URLs:**
- **Official:** https://github.com/tesseract-ocr/tesseract
- **Windows Installer:** https://github.com/UB-Mannheim/tesseract/wiki
- **Documentation:** https://tesseract-ocr.github.io/

**Language Data Files (Optional):**
If you want additional languages, download from:
- **URL:** https://github.com/tesseract-ocr/tessdata
- **Location (Windows):** `C:\Program Files\Tesseract-OCR\tessdata\`
- **Location (Linux):** `/usr/share/tesseract-ocr/4.00/tessdata/`

**Supported Languages:**
```
eng.traineddata    (English)
ara.traineddata    (Arabic/Urdu)
hin.traineddata    (Hindi)
chi_sim.traineddata (Chinese Simplified)
jpn.traineddata    (Japanese)
kor.traineddata    (Korean)
```

---

## 📚 PYTHON LIBRARIES (Install via pip)

### 7. **PyTesseract** (Python wrapper for Tesseract)
```bash
pip install pytesseract
```
**URL:** https://pypi.org/project/pytesseract/

### 8. **Ultralytics** (YOLO wrapper)
```bash
pip install ultralytics
```
**URL:** https://pypi.org/project/ultralytics/

### 9. **OpenCV** (Computer Vision)
```bash
pip install opencv-python
```
**URL:** https://pypi.org/project/opencv-python/

### 10. **MoviePy** (Video Processing)
```bash
pip install moviepy
```
**URL:** https://pypi.org/project/moviepy/

---

## 🗂️ FINAL FOLDER STRUCTURE

**After downloading all models:**

```
C:\AI_Models\                          (or ~/AI_Models/)
│
├── blip-image-captioning-base\        (500 MB)
│   ├── config.json
│   ├── preprocessor_config.json
│   ├── pytorch_model.bin              ← Main BLIP model
│   ├── special_tokens_map.json
│   ├── tokenizer_config.json
│   └── vocab.txt
│
├── yolov8n.pt                         (6 MB) ← YOLO model
│
└── whisper\                           (Optional)
    └── base.pt                        (150 MB)

Total Size: ~656 MB (without Whisper)
           ~806 MB (with Whisper base)
```

---

## ✅ VERIFICATION SCRIPT

Save this as `verify_models.py` and run to check everything:

```python
import os
import sys

print("=" * 70)
print("🔍 VERIFYING AI MODELS INSTALLATION")
print("=" * 70)
print()

# Check AI_Models folder
models_locations = [
    r"C:\AI_Models",
    os.path.join(os.path.expanduser("~"), "AI_Models"),
    os.path.join(os.path.expanduser("~"), "Desktop", "AI_Models")
]

models_dir = None
for loc in models_locations:
    if os.path.exists(loc):
        models_dir = loc
        print(f"✅ Found AI_Models at: {loc}")
        break

if not models_dir:
    print("❌ AI_Models folder not found!")
    print("   Create: C:\\AI_Models\\ (Windows) or ~/AI_Models/ (Linux/Mac)")
    sys.exit(1)

print()
print("Checking models...")
print("-" * 70)

# Check BLIP
blip_path = os.path.join(models_dir, "blip-image-captioning-base")
if os.path.exists(blip_path):
    size = sum(os.path.getsize(os.path.join(blip_path, f))
               for f in os.listdir(blip_path) if os.path.isfile(os.path.join(blip_path, f)))
    print(f"✅ BLIP Model Found: {blip_path}")
    print(f"   Size: {size / 1024**2:.0f} MB")
else:
    print(f"❌ BLIP Model Missing!")
    print(f"   Download to: {blip_path}")
    print(f"   URL: https://huggingface.co/Salesforce/blip-image-captioning-base")

print()

# Check YOLO
yolo_path = os.path.join(models_dir, "yolov8n.pt")
if os.path.exists(yolo_path):
    size = os.path.getsize(yolo_path)
    print(f"✅ YOLO Model Found: {yolo_path}")
    print(f"   Size: {size / 1024**2:.0f} MB")
else:
    print(f"❌ YOLO Model Missing!")
    print(f"   Download to: {yolo_path}")
    print(f"   URL: https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt")

print()

# Check Python libraries
print("Checking Python libraries...")
print("-" * 70)

libs = [
    ('torch', 'PyTorch'),
    ('transformers', 'Transformers'),
    ('ultralytics', 'Ultralytics'),
    ('cv2', 'OpenCV'),
    ('pytesseract', 'PyTesseract'),
    ('moviepy', 'MoviePy')
]

for module, name in libs:
    try:
        exec(f"import {module}")
        mod = sys.modules[module]
        version = getattr(mod, '__version__', 'installed')
        print(f"✅ {name:20} {version}")
    except ImportError:
        print(f"❌ {name:20} NOT INSTALLED")
        print(f"   Install: pip install {module if module != 'cv2' else 'opencv-python'}")

print()

# Check Tesseract
print("Checking Tesseract OCR...")
print("-" * 70)
try:
    import subprocess
    result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
    if result.returncode == 0:
        version = result.stdout.split('\n')[0]
        print(f"✅ Tesseract: {version}")
    else:
        print("❌ Tesseract not found in PATH")
except:
    print("❌ Tesseract not installed")
    print("   Windows: https://github.com/UB-Mannheim/tesseract/wiki")
    print("   Linux: sudo apt-get install tesseract-ocr")

print()
print("=" * 70)
print("✅ Verification complete!")
print("=" * 70)
```

---

## 📋 QUICK SETUP CHECKLIST

**Step 1: Create AI_Models Folder**
```bash
# Windows:
mkdir C:\AI_Models

# Linux/Mac:
mkdir ~/AI_Models
```

**Step 2: Install Python Libraries**
```bash
pip install -r requirements.txt

# Or individually:
pip install torch transformers ultralytics opencv-python pytesseract moviepy
```

**Step 3: Install Tesseract (System Binary)**
```bash
# Windows: Download installer from
https://github.com/UB-Mannheim/tesseract/wiki

# Linux:
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara

# Mac:
brew install tesseract
```

**Step 4: Download BLIP Model**
```python
# Run this Python script:
from transformers import BlipProcessor, BlipForConditionalGeneration
import os

models_dir = r"C:\AI_Models\blip-image-captioning-base"
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
processor.save_pretrained(models_dir)
model.save_pretrained(models_dir)
print(f"✅ Saved to: {models_dir}")
```

**Step 5: Download YOLO Model**
```bash
cd C:\AI_Models
# Download: https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
# Or let it auto-download on first use
```

**Step 6: Verify Everything**
```bash
python verify_models.py
```

**Step 7: Run App**
```bash
python main.py
```

---

## 🌐 ALL URLS SUMMARY

| Model/Library | Download URL |
|---------------|--------------|
| **BLIP** | https://huggingface.co/Salesforce/blip-image-captioning-base |
| **YOLO** | https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt |
| **PyTorch** | https://pytorch.org/get-started/locally/ |
| **Transformers** | https://huggingface.co/docs/transformers/installation |
| **Ultralytics** | https://pypi.org/project/ultralytics/ |
| **Tesseract (Windows)** | https://github.com/UB-Mannheim/tesseract/wiki |
| **Tesseract Data** | https://github.com/tesseract-ocr/tessdata |
| **OpenCV** | https://pypi.org/project/opencv-python/ |
| **MoviePy** | https://pypi.org/project/moviepy/ |
| **Whisper (Optional)** | https://github.com/openai/whisper |

---

## 💾 DISK SPACE REQUIREMENTS

| Component | Size | Required? |
|-----------|------|-----------|
| PyTorch | 2 GB | ✅ YES |
| BLIP Model | 500 MB | ✅ YES |
| YOLO Model | 6 MB | ⭐ Recommended |
| Transformers | 500 MB | ✅ YES |
| Tesseract | 50 MB | ✅ YES |
| Other libraries | 200 MB | ✅ YES |
| **TOTAL** | **~3.2 GB** | - |

---

## 🎯 PRIORITY LIST (What to Download First)

**Priority 1 (MUST HAVE):**
1. ✅ PyTorch (`pip install torch`)
2. ✅ Transformers (`pip install transformers`)
3. ✅ BLIP Model (500 MB)
4. ✅ Tesseract OCR (50 MB)

**Priority 2 (Highly Recommended):**
5. ⭐ YOLO Model (6 MB) - Small but powerful!
6. ⭐ Ultralytics (`pip install ultralytics`)

**Priority 3 (Optional):**
7. 💡 Whisper (150 MB) - Only if offline audio needed

---

**Last Updated:** 2024-12-29
**Total Download:** ~3.2 GB
**Status:** ✅ COMPLETE GUIDE WITH ALL URLS
