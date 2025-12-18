@echo off
REM OneSoul EXE Build Script
REM Automates the PyInstaller build process

echo ============================================
echo   OneSoul EXE Builder
echo ============================================
echo.

REM Check if virtual environment exists
if exist ".venv\Scripts\activate.bat" (
    echo [1/5] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo [!] Warning: Virtual environment not found
    echo     Continuing with global Python...
)

echo.
echo [2/5] Checking PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [!] PyInstaller not found. Installing...
    pip install pyinstaller
) else (
    echo     PyInstaller is installed
)

echo.
echo [3/5] Pre-build file check...
if exist "cloudflared.exe" (
    echo     [OK] cloudflared.exe found
) else (
    echo     [!] cloudflared.exe NOT found - will skip
)

if exist "ffmpeg" (
    if exist "ffmpeg\ffmpeg.exe" (
        echo     [OK] ffmpeg directory found
    ) else (
        echo     [!] ffmpeg folder exists but ffmpeg.exe missing
    )
) else (
    echo     [!] ffmpeg directory NOT found - will skip
)

if exist "modules\auto_uploader\helper_images" (
    echo     [OK] helper_images directory found
) else (
    echo     [ERROR] helper_images NOT found - BUILD WILL FAIL
    pause
    exit /b 1
)

echo.
echo [4/5] Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
echo     Previous builds cleaned

echo.
echo [5/5] Building EXE with PyInstaller...
echo     This may take 5-10 minutes...
echo.

pyinstaller --clean onesoul_enhanced.spec

if errorlevel 1 (
    echo.
    echo ============================================
    echo   BUILD FAILED!
    echo ============================================
    echo.
    echo Check the error messages above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD SUCCESSFUL!
echo ============================================
echo.
echo Output location: dist\OneSoul\
echo Main executable: dist\OneSoul\OneSoul.exe
echo.
echo Next steps:
echo 1. Test the EXE: cd dist\OneSoul ^&^& OneSoul.exe
echo 2. Check BUILD_INSTRUCTIONS.md for testing guide
echo 3. Zip dist\OneSoul\ folder for distribution
echo.

REM List the dist folder
echo Files in dist\OneSoul\:
dir /b dist\OneSoul\ | findstr /v /c:"_internal"

echo.
echo Build completed at: %date% %time%
echo.
pause
