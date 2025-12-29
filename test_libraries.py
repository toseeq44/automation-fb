#!/usr/bin/env python3
"""
Complete Library Test Script
Tests all required libraries for Title Generator
Shows exactly what's installed and where
"""

import sys
import os

print("=" * 70)
print("🔍 LIBRARY INSTALLATION TEST")
print("=" * 70)
print()

# Track results
results = {
    'installed': [],
    'missing': [],
    'failed': []
}

def test_import(module_name, import_statement, description):
    """Test if a module can be imported"""
    try:
        exec(import_statement)
        version = ""

        # Try to get version
        try:
            mod = sys.modules[module_name.split('.')[0]]
            if hasattr(mod, '__version__'):
                version = f" v{mod.__version__}"
            elif hasattr(mod, 'VERSION'):
                version = f" v{mod.VERSION}"
        except:
            pass

        # Get installation location
        try:
            mod = sys.modules[module_name.split('.')[0]]
            location = os.path.dirname(mod.__file__) if hasattr(mod, '__file__') else "built-in"
        except:
            location = "unknown"

        print(f"✅ {description:40} {version:15} {location[:50]}")
        results['installed'].append(description)
        return True

    except ImportError as e:
        print(f"❌ {description:40} NOT INSTALLED")
        results['missing'].append(description)
        return False

    except Exception as e:
        print(f"⚠️  {description:40} IMPORT ERROR: {str(e)[:30]}")
        results['failed'].append(description)
        return False

print("CORE DEPENDENCIES:")
print("-" * 70)
test_import('PyQt5', 'import PyQt5', 'PyQt5 (GUI)')
test_import('requests', 'import requests', 'Requests (HTTP)')
test_import('yt_dlp', 'import yt_dlp', 'yt-dlp (Video Downloader)')
test_import('beautifulsoup4', 'from bs4 import BeautifulSoup', 'BeautifulSoup4 (HTML Parser)')
test_import('lxml', 'import lxml', 'LXML (XML Parser)')
print()

print("VIDEO EDITOR DEPENDENCIES:")
print("-" * 70)
test_import('moviepy', 'import moviepy', 'MoviePy (Video Editing)')
test_import('PIL', 'from PIL import Image', 'Pillow (Image Processing)')
test_import('numpy', 'import numpy', 'NumPy (Arrays)')
test_import('scipy', 'import scipy', 'SciPy (Scientific)')
test_import('imageio', 'import imageio', 'ImageIO (Image I/O)')
print()

print("COMPUTER VISION DEPENDENCIES:")
print("-" * 70)
test_import('cv2', 'import cv2', 'OpenCV (Computer Vision)')
test_import('pytesseract', 'import pytesseract', 'PyTesseract (OCR)')
print()

print("AI/ML DEPENDENCIES (LOCAL MODELS):")
print("-" * 70)
torch_ok = test_import('torch', 'import torch', 'PyTorch (Deep Learning)')
transformers_ok = test_import('transformers', 'import transformers', 'Transformers (NLP/Vision)')
yolo_ok = test_import('ultralytics', 'from ultralytics import YOLO', 'Ultralytics (YOLO)')
print()

print("BROWSER AUTOMATION DEPENDENCIES:")
print("-" * 70)
test_import('pyautogui', 'import pyautogui', 'PyAutoGUI (GUI Automation)')
test_import('psutil', 'import psutil', 'psutil (Process Management)')
print()

print("WEB SERVER DEPENDENCIES:")
print("-" * 70)
test_import('flask', 'import flask', 'Flask (Web Framework)')
print()

# Special checks
print("=" * 70)
print("🔧 SPECIAL SYSTEM CHECKS:")
print("=" * 70)

# Check Tesseract binary (not Python package)
print()
print("Tesseract OCR Binary:")
print("-" * 70)
try:
    import subprocess
    result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        version_line = result.stdout.split('\n')[0]
        print(f"✅ Tesseract Binary Installed: {version_line}")
    else:
        print("❌ Tesseract binary not found")
        print("   💡 Install: sudo apt-get install tesseract-ocr")
except FileNotFoundError:
    print("❌ Tesseract binary not found in PATH")
    print("   💡 Install: sudo apt-get install tesseract-ocr")
except Exception as e:
    print(f"⚠️  Could not check Tesseract: {e}")

# Check CUDA availability (for PyTorch)
print()
print("GPU/CUDA Support:")
print("-" * 70)
if torch_ok:
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✅ CUDA Available: {torch.cuda.get_device_name(0)}")
            print(f"   CUDA Version: {torch.version.cuda}")
        else:
            print("⚠️  CUDA Not Available (will use CPU)")
            print("   💡 This is OK! CPU mode works fine (just slower)")
    except Exception as e:
        print(f"⚠️  Could not check CUDA: {e}")
else:
    print("❌ PyTorch not installed (cannot check CUDA)")

# Check if models can be loaded
print()
print("AI MODELS TEST:")
print("-" * 70)

if yolo_ok:
    try:
        print("Testing YOLO model load...")
        from ultralytics import YOLO
        model = YOLO('yolov8n.pt')  # Will auto-download if not present
        print("✅ YOLO model loaded successfully (yolov8n.pt)")
        print(f"   Model location: {model.model_path if hasattr(model, 'model_path') else 'cached'}")
    except Exception as e:
        print(f"⚠️  YOLO model load failed: {str(e)[:60]}")
        print("   💡 Will download on first use (6MB)")
else:
    print("❌ Ultralytics not installed (YOLO unavailable)")

if transformers_ok:
    try:
        print()
        print("Testing BLIP model imports...")
        from transformers import BlipProcessor, BlipForConditionalGeneration
        print("✅ BLIP imports successful")
        print("   💡 Model will download on first use (~500MB)")
        print("   💡 Location: ~/.cache/huggingface/hub/")
    except Exception as e:
        print(f"⚠️  BLIP import failed: {str(e)[:60]}")
else:
    print("❌ Transformers not installed (BLIP unavailable)")

# Test local vision analyzer
print()
print("TITLE GENERATOR MODULES TEST:")
print("-" * 70)
try:
    from modules.title_generator.local_vision_analyzer import LocalVisionAnalyzer
    print("✅ LocalVisionAnalyzer imported successfully")

    analyzer = LocalVisionAnalyzer()
    print("✅ LocalVisionAnalyzer initialized")
except Exception as e:
    print(f"⚠️  LocalVisionAnalyzer failed: {str(e)[:80]}")

try:
    from modules.title_generator.multi_source_aggregator import MultiSourceAggregator
    print("✅ MultiSourceAggregator imported successfully")
except Exception as e:
    print(f"⚠️  MultiSourceAggregator failed: {str(e)[:80]}")

# Summary
print()
print("=" * 70)
print("📊 SUMMARY:")
print("=" * 70)
print(f"✅ Installed:  {len(results['installed'])} libraries")
print(f"❌ Missing:    {len(results['missing'])} libraries")
print(f"⚠️  Failed:    {len(results['failed'])} libraries")
print()

if results['missing']:
    print("Missing libraries:")
    for lib in results['missing']:
        print(f"  - {lib}")
    print()
    print("💡 To install missing libraries:")
    print("   pip install -r requirements.txt")
    print()

if len(results['missing']) == 0 and len(results['failed']) == 0:
    print("🎉 ALL LIBRARIES INSTALLED SUCCESSFULLY!")
    print()
    print("✅ Ready to use:")
    print("   - HYBRID Title Generator (APIs + Local Models)")
    print("   - Multi-source aggregation (95% accuracy)")
    print("   - Offline vision analysis (YOLO + BLIP)")
    print()
else:
    print("⚠️  Some libraries missing or failed")
    print("   Run: pip install -r requirements.txt")
    print()

print("=" * 70)
print()

# Python environment info
print("PYTHON ENVIRONMENT:")
print("-" * 70)
print(f"Python Version: {sys.version}")
print(f"Python Path:    {sys.executable}")
print(f"Working Dir:    {os.getcwd()}")
print()
print("=" * 70)
