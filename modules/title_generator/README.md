# 🪄 Enhanced Multilingual Title Generator

Content-aware video title generation with AI-powered multilingual support.

## 🌟 Features

### **Multi-Source Content Analysis**
- **🎙️ Audio Transcription**: OpenAI Whisper for speech-to-text and language detection
- **👁️ Visual Analysis**: CLIP for object, scene, and action detection
- **📝 Text Extraction**: Tesseract OCR for on-screen text
- **🧠 Content Aggregation**: Intelligent combination of all sources

### **Multilingual Support**
- **English** (en)
- **Portuguese/Brazilian** (pt)
- **French** (fr)
- **Spanish** (es)
- **Urdu** (ur)
- **Hindi** (hi)
- **Arabic** (ar)

### **Platform Optimization**
- **Facebook**: Up to 255 characters
- **TikTok**: Up to 150 characters (viral-optimized)
- **Instagram**: Up to 125 characters
- **YouTube**: Up to 100 characters

### **Niche-Specific Templates**
- Cooking
- Gaming
- Tutorials
- Reviews
- Vlogs
- Fitness
- Music
- Beauty/Fashion
- Education

---

## 📦 Installation

### **1. Install Python Dependencies**
```bash
pip install -r modules/title_generator/REQUIREMENTS.txt
```

### **2. Install Tesseract OCR**

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**MacOS:**
```bash
brew install tesseract
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki

### **3. Configure Groq API (Optional)**

For AI-enhanced title refinement:

1. Get free API key from: https://console.groq.com
2. Run the title generator
3. Enter API key when prompted

---

## 🚀 Quick Start

### **Using the GUI**

```python
from modules.title_generator import TitleGeneratorDialog
from PyQt5.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
dialog = TitleGeneratorDialog()
dialog.exec_()
```

### **Using the Enhanced Generator Directly**

```python
from modules.title_generator import EnhancedTitleGenerator

# Initialize generator
generator = EnhancedTitleGenerator(model_size='base')

# Generate title
video_info = {
    'path': '/path/to/video.mp4',
    'filename': 'my_video.mp4'
}

title = generator.generate_title(
    video_info,
    platform='facebook',  # or 'tiktok', 'instagram'
    enable_ai=True
)

print(f"Generated Title: {title}")
```

---

## 🎯 How It Works

### **Phase 1: Multi-Source Analysis**

```
VIDEO INPUT
    │
    ├─ 🎙️ AUDIO ANALYSIS (Whisper)
    │   ├─ Transcribe speech → text
    │   ├─ Detect language (ur/en/pt/fr/es/hi/ar)
    │   └─ Extract keywords from speech
    │
    ├─ 👁️ VISUAL ANALYSIS (CLIP)
    │   ├─ Scene change detection → key frames
    │   ├─ Object detection (food, person, product, etc.)
    │   ├─ Scene classification (kitchen, outdoor, studio)
    │   ├─ Niche detection (cooking, gaming, tutorial)
    │   └─ Action recognition (cooking, playing, talking)
    │
    └─ 📝 TEXT ANALYSIS (OCR)
        ├─ Extract text from frames
        ├─ Detect language from text
        ├─ Extract keywords
        └─ Identify entities (names, brands)
```

### **Phase 2: Content Aggregation**

```
COMBINE ALL SOURCES
    │
    ├─ Language Determination
    │   Priority: Audio > Text > Default (English)
    │
    ├─ Niche Classification
    │   Priority: Visual > Audio Keywords > Text Keywords
    │
    ├─ Element Extraction
    │   WHO: Subject/person (I, Chef, Player, Reviewer)
    │   WHAT: Action/topic (Recipe, Gameplay, Tutorial)
    │   WHERE: Scene (kitchen, outdoor, studio)
    │   TIME: Duration (formatted)
    │
    └─ Platform Optimization
        Duration + Aspect Ratio → Facebook/TikTok
```

### **Phase 3: Title Generation**

```
MULTILINGUAL TEMPLATES
    │
    ├─ Select language-specific templates
    │   Based on detected language
    │
    ├─ Select niche templates
    │   cooking, gaming, review, tutorial, vlog, fitness
    │
    ├─ Select content type
    │   speed, tutorial, viral, challenge
    │
    └─ Fill templates with content
        {WHO} {WHAT} in {TIME}
        → "Chef Makes Pizza in 5 Minutes"
```

### **Phase 4: AI Refinement** (Optional)

```
GROQ API
    │
    ├─ Send all variants + full context
    │   Audio transcription
    │   Visual objects
    │   Keywords
    │   Metadata
    │
    ├─ AI analyzes actual content
    │
    └─ Returns best/refined title
        Content-accurate
        Platform-optimized
        Language-specific
```

---

## 📊 Content-Aware Examples

### **Example 1: Cooking Video (Urdu Audio)**

**Input:**
- Audio: "aaj main pizza banaunga..." (Today I'll make pizza...)
- Visual: [person, kitchen, food, stove, dough]
- OCR: "پیزا ریسیپی" (Pizza Recipe)
- Duration: 5 minutes

**Output:**
```
Language: Urdu (ur)
Niche: cooking
Title: "صرف 5 منٹ میں پیزا | جلدی ریسیپی"
Translation: "Pizza in Just 5 Minutes | Quick Recipe"
```

### **Example 2: Gaming Video (Portuguese Audio)**

**Input:**
- Audio: "jogando fortnite..." (playing fortnite...)
- Visual: [screen, game, controller, keyboard]
- Duration: 10 minutes

**Output:**
```
Language: Portuguese (pt)
Niche: gaming
Title: "Fortnite em 10 Minutos | Gameplay Insano"
Translation: "Fortnite in 10 Minutes | Insane Gameplay"
```

### **Example 3: Review Video (English Audio)**

**Input:**
- Audio: "unboxing the new iPhone 16..."
- Visual: [product, box, hands, phone, table]
- OCR: "iPhone 16 Pro"

**Output:**
```
Language: English (en)
Niche: review
Title: "iPhone 16 Pro Review | Is It Worth $1200?"
```

### **Example 4: Tutorial Video (French Audio)**

**Input:**
- Audio: "comment faire..." (how to make...)
- Visual: [computer, screen, code, keyboard]
- Duration: 15 minutes

**Output:**
```
Language: French (fr)
Niche: tutorial
Title: "Comment Coder en Python | Tutoriel pour Débutants"
Translation: "How to Code in Python | Tutorial for Beginners"
```

---

## ⚙️ Configuration Options

### **Model Sizes** (Whisper Audio Analysis)

```python
# Tiny: Fastest, less accurate (~1GB RAM)
generator = EnhancedTitleGenerator(model_size='tiny')

# Base: Good balance (recommended) (~1.5GB RAM)
generator = EnhancedTitleGenerator(model_size='base')

# Small: Better accuracy, slower (~2.5GB RAM)
generator = EnhancedTitleGenerator(model_size='small')

# Medium: High accuracy, slow (~5GB RAM)
generator = EnhancedTitleGenerator(model_size='medium')
```

### **Platform Selection**

```python
# Facebook (up to 255 chars)
title = generator.generate_title(video_info, platform='facebook')

# TikTok (up to 150 chars, viral hooks)
title = generator.generate_title(video_info, platform='tiktok')

# Instagram (up to 125 chars)
title = generator.generate_title(video_info, platform='instagram')

# YouTube (up to 100 chars)
title = generator.generate_title(video_info, platform='youtube')
```

### **AI Refinement**

```python
# With AI refinement (requires Groq API key)
title = generator.generate_title(video_info, enable_ai=True)

# Without AI (uses first template variant)
title = generator.generate_title(video_info, enable_ai=False)
```

---

## 🔧 Advanced Usage

### **Batch Processing**

```python
from pathlib import Path
from modules.title_generator import EnhancedTitleGenerator

generator = EnhancedTitleGenerator()

video_folder = Path('/path/to/videos')
for video_path in video_folder.glob('*.mp4'):
    video_info = {
        'path': str(video_path),
        'filename': video_path.name
    }

    title = generator.generate_title(video_info)
    print(f"{video_path.name} → {title}")
```

### **Custom Language Detection**

```python
# Quick language detection only
from modules.title_generator import AudioAnalyzer

analyzer = AudioAnalyzer()
language = analyzer.detect_language_only('/path/to/video.mp4')
print(f"Detected Language: {language}")
```

### **Visual Analysis Only**

```python
from modules.title_generator import VisualAnalyzer

analyzer = VisualAnalyzer()
visual_data = analyzer.analyze_video_visual('/path/to/video.mp4')

print(f"Niche: {visual_data['niche']}")
print(f"Objects: {visual_data['objects']}")
print(f"Scene: {visual_data['scene']}")
```

---

## 📈 Performance Optimization

### **Speed vs Quality Trade-offs**

1. **Fast Mode** (3-5 seconds per video):
   - Whisper: `tiny` model
   - Frames: 6 key frames
   - No AI refinement

2. **Balanced Mode** (10-15 seconds per video):
   - Whisper: `base` model (recommended)
   - Frames: 12 key frames
   - AI refinement enabled

3. **Quality Mode** (20-30 seconds per video):
   - Whisper: `small` or `medium` model
   - Frames: 15-20 key frames
   - AI refinement enabled

### **GPU Acceleration**

For faster CLIP processing, install PyTorch with CUDA:

```bash
# Check CUDA version
nvidia-smi

# Install PyTorch with CUDA 11.8
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Or CUDA 12.1
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

## 🐛 Troubleshooting

### **Issue: "Whisper not installed"**
```bash
pip install openai-whisper
```

### **Issue: "CLIP not available"**
```bash
pip install transformers torch
```

### **Issue: "Tesseract not found"**
Install Tesseract OCR (see Installation section above)

### **Issue: "No speech detected"**
- Video may have no audio track
- Audio volume too low
- Try different Whisper model size

### **Issue: "Generic titles generated"**
- Enable AI refinement with Groq API key
- Check video content clarity
- Ensure good lighting and visible objects

### **Issue: "Wrong language detected"**
- Audio language auto-detected by Whisper
- If incorrect, audio may be unclear
- OCR text can influence language if no clear audio

---

## 📝 Supported Language Examples

### **English**
- "How to Make Pizza in 5 Minutes | Quick Recipe"
- "iPhone 16 Pro Review | Is It Worth It?"

### **Portuguese**
- "Como Fazer Pizza em 5 Minutos | Receita Rápida"
- "Review iPhone 16 Pro | Vale a Pena?"

### **French**
- "Comment Faire une Pizza en 5 Minutes | Recette Rapide"
- "Test iPhone 16 Pro | Ça Vaut le Coup?"

### **Spanish**
- "Cómo Hacer Pizza en 5 Minutos | Receta Rápida"
- "Review iPhone 16 Pro | ¿Vale la Pena?"

### **Urdu**
- "صرف 5 منٹ میں پیزا | جلدی ریسیپی"
- "iPhone 16 Pro ریویو | کیا یہ قابل ہے؟"

### **Hindi**
- "सिर्फ 5 मिनट में पिज्जा | जल्दी रेसिपी"
- "iPhone 16 Pro रिव्यू | क्या यह लायक है?"

### **Arabic**
- "بيتزا في 5 دقائق فقط | وصفة سريعة"
- "مراجعة iPhone 16 Pro | هل يستحق؟"

---

## 🤝 Contributing

Found a bug or want to add a new language? Please submit an issue or pull request!

---

## 📄 License

Part of the automation-fb project.

---

## 🙏 Credits

- **OpenAI Whisper**: Audio transcription and language detection
- **CLIP (OpenAI)**: Visual content understanding
- **Groq API**: AI-powered title refinement
- **Tesseract**: OCR text extraction
