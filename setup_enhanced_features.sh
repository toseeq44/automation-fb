#!/bin/bash
# Enhanced Title Generator - Quick Setup Script for Linux/Mac
# Run this script to install all required AI packages

echo ""
echo "========================================"
echo "  Enhanced Title Generator - Setup"
echo "========================================"
echo ""
echo "This will install AI packages for:"
echo "  - Audio transcription (Whisper)"
echo "  - Visual analysis (CLIP)"
echo "  - Multilingual support"
echo ""
echo "Required: ~2-4GB download, 5GB disk space"
echo "Time: 10-15 minutes"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

echo ""
echo "[1/3] Installing OpenAI Whisper..."
echo ""
pip install openai-whisper || python -m pip install openai-whisper
if [ $? -ne 0 ]; then
    echo "ERROR: Whisper installation failed!"
    exit 1
fi

echo ""
echo "[2/3] Installing Transformers..."
echo ""
pip install transformers || python -m pip install transformers
if [ $? -ne 0 ]; then
    echo "ERROR: Transformers installation failed!"
    exit 1
fi

echo ""
echo "[3/3] Installing PyTorch..."
echo ""
pip install torch || python -m pip install torch
if [ $? -ne 0 ]; then
    echo "ERROR: PyTorch installation failed!"
    exit 1
fi

echo ""
echo "========================================"
echo "  Verifying Installation..."
echo "========================================"
echo ""

python -c "import whisper; print('✓ Whisper OK')"
python -c "import transformers; print('✓ Transformers OK')"
python -c "import torch; print('✓ PyTorch OK')"

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "  SUCCESS! 🎉"
    echo "========================================"
    echo ""
    echo "All packages installed successfully!"
    echo ""
    echo "NEXT STEPS:"
    echo "1. Close this terminal"
    echo "2. RESTART your video editing application"
    echo "3. Open Title Generator"
    echo "4. Look for: 'ENHANCED MODE - FULL AI FEATURES'"
    echo ""
    echo "You're ready to generate amazing titles! ✨"
    echo ""
else
    echo ""
    echo "========================================"
    echo "  VERIFICATION FAILED"
    echo "========================================"
    echo ""
    echo "Packages installed but verification failed."
    echo "Please check error messages above."
    echo ""
fi
