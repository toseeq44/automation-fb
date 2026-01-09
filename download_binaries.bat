@echo off
REM OneSoul - Download Required Binaries Script
REM This script helps download ffmpeg and yt-dlp if missing

echo ============================================
echo   OneSoul Binary Downloader
echo ============================================
echo.
echo This script will help you download required binaries:
echo   - FFmpeg (for video editing)
echo   - yt-dlp (for video downloading)
echo.

REM Check if ffmpeg exists
if exist "ffmpeg\ffmpeg.exe" (
    echo [OK] ffmpeg.exe already exists
) else (
    echo [!] ffmpeg.exe NOT FOUND
    echo.
    echo Please download FFmpeg manually:
    echo 1. Visit: https://github.com/BtbN/FFmpeg-Builds/releases
    echo 2. Download: ffmpeg-master-latest-win64-gpl.zip
    echo 3. Extract ffmpeg.exe and ffprobe.exe
    echo 4. Create folder: ffmpeg\
    echo 5. Copy both exe files to ffmpeg\ folder
    echo.
    echo Expected location:
    echo   %cd%\ffmpeg\ffmpeg.exe
    echo   %cd%\ffmpeg\ffprobe.exe
    echo.
)

REM Check if yt-dlp exists
if exist "bin\yt-dlp.exe" (
    echo [OK] yt-dlp.exe already exists
) else (
    echo [!] yt-dlp.exe NOT FOUND
    echo.
    echo Attempting to download yt-dlp...

    REM Try to download using PowerShell
    powershell -Command "& {
        try {
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' -OutFile 'bin\yt-dlp.exe'
            Write-Host '[SUCCESS] yt-dlp.exe downloaded successfully'
        } catch {
            Write-Host '[FAILED] Could not download yt-dlp.exe'
            Write-Host 'Please download manually from: https://github.com/yt-dlp/yt-dlp/releases'
        }
    }"
)

echo.
echo ============================================
echo   Final Check
echo ============================================
echo.

REM Final verification
set MISSING=0

if exist "ffmpeg\ffmpeg.exe" (
    echo [OK] ffmpeg.exe found
) else (
    echo [X] ffmpeg.exe MISSING
    set MISSING=1
)

if exist "ffmpeg\ffprobe.exe" (
    echo [OK] ffprobe.exe found
) else (
    echo [X] ffprobe.exe MISSING
    set MISSING=1
)

if exist "bin\yt-dlp.exe" (
    echo [OK] yt-dlp.exe found
) else (
    echo [X] yt-dlp.exe MISSING (optional - only needed for Link Grabber)
)

if exist "gui-redesign\assets\onesoul_logo.ico" (
    echo [OK] Icon file found
) else (
    echo [X] Icon file MISSING
    set MISSING=1
)

echo.

if %MISSING%==1 (
    echo ============================================
    echo   Some required files are missing!
    echo ============================================
    echo.
    echo Please download the missing files manually.
    echo See BUILD_INSTRUCTIONS.md for download links.
    echo.
) else (
    echo ============================================
    echo   All required files are present!
    echo ============================================
    echo.
    echo You can now build the EXE:
    echo   build.bat
    echo.
)

pause
