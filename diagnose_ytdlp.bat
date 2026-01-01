@echo off
REM Check yt-dlp installation on PC 2

echo ========================================
echo YT-DLP DIAGNOSTIC CHECK
echo ========================================
echo.

REM Check if yt-dlp exists
echo [1/5] Checking if yt-dlp is installed...
where yt-dlp
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: yt-dlp not found in PATH!
    echo Please install: pip install -U yt-dlp
    goto :END
)
echo OK: yt-dlp found
echo.

REM Check yt-dlp version
echo [2/5] Checking yt-dlp version...
yt-dlp --version
echo.

REM Check if outdated
echo [3/5] Checking for updates...
yt-dlp -U
echo.

REM Test basic extraction
echo [4/5] Testing basic extraction...
echo Testing with: https://www.youtube.com/@peakzmotivation
yt-dlp --flat-playlist --get-url https://www.youtube.com/@peakzmotivation
echo.

REM Check Python version
echo [5/5] Checking Python version...
python --version
echo.

:END
echo ========================================
echo Diagnostic complete!
echo ========================================
pause
