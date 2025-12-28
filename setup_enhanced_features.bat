@echo off
REM Enhanced Title Generator - Quick Setup Script for Windows
REM Run this script to install all required AI packages

echo.
echo ========================================
echo   Enhanced Title Generator - Setup
echo ========================================
echo.
echo This will install AI packages for:
echo   - Audio transcription (Whisper)
echo   - Visual analysis (CLIP)
echo   - Multilingual support
echo.
echo Required: ~2-4GB download, 5GB disk space
echo Time: 10-15 minutes
echo.
pause

echo.
echo [1/3] Installing OpenAI Whisper...
echo.
pip install openai-whisper
if %errorlevel% neq 0 (
    echo ERROR: Whisper installation failed!
    echo Try: python -m pip install openai-whisper
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Transformers...
echo.
pip install transformers
if %errorlevel% neq 0 (
    echo ERROR: Transformers installation failed!
    pause
    exit /b 1
)

echo.
echo [3/3] Installing PyTorch...
echo.
pip install torch
if %errorlevel% neq 0 (
    echo ERROR: PyTorch installation failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Verifying Installation...
echo ========================================
echo.

python -c "import whisper; print('✓ Whisper OK')"
python -c "import transformers; print('✓ Transformers OK')"
python -c "import torch; print('✓ PyTorch OK')"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   SUCCESS! 🎉
    echo ========================================
    echo.
    echo All packages installed successfully!
    echo.
    echo NEXT STEPS:
    echo 1. Close this window
    echo 2. RESTART your video editing application
    echo 3. Open Title Generator
    echo 4. Look for: "ENHANCED MODE - FULL AI FEATURES"
    echo.
    echo You're ready to generate amazing titles! ✨
    echo.
) else (
    echo.
    echo ========================================
    echo   VERIFICATION FAILED
    echo ========================================
    echo.
    echo Packages installed but verification failed.
    echo Please check error messages above.
    echo.
)

pause
