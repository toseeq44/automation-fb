#!/bin/bash
# Setup script for custom model directory

echo "Setting up custom model directory..."
echo "=" * 70

# Create custom directory
MODELS_DIR="$HOME/.title_generator/models"
mkdir -p "$MODELS_DIR"

echo "✅ Created: $MODELS_DIR"
echo ""

# Instructions
cat << 'EOF'
📁 CUSTOM MODEL DIRECTORY SETUP COMPLETE!

Location: ~/.title_generator/models/

TO USE CUSTOM DIRECTORY:
1. Models will auto-download to cache (~/.cache/huggingface/, ~/.cache/ultralytics/)
2. To use custom directory, copy models there:

   # Copy BLIP model
   cp -r ~/.cache/huggingface/hub/models--Salesforce--blip-image-captioning-base \
         ~/.title_generator/models/blip-image-captioning-base

   # Copy YOLO model
   cp ~/.cache/ultralytics/yolov8n.pt \
      ~/.title_generator/models/yolov8n.pt

3. Or download directly to custom directory (first time only):
   python3 << PYTHON
from transformers import BlipProcessor, BlipForConditionalGeneration
import os

models_dir = os.path.expanduser("~/.title_generator/models/blip-image-captioning-base")
print(f"Downloading BLIP to {models_dir}...")

processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

processor.save_pretrained(models_dir)
model.save_pretrained(models_dir)

print("✅ BLIP model saved!")
PYTHON

FOR EXE DISTRIBUTION:
- Bundle small models (YOLO 6MB) in EXE
- Large models (BLIP 500MB) → User downloads on first run
- Save to: C:\TitleGenerator\models\ (Windows)

DISK SPACE REQUIRED:
- BLIP: 500 MB
- YOLO: 6 MB
- Total: ~506 MB

EOF

echo "=" * 70
echo "✅ Setup complete!"
