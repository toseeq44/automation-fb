@echo off
:: Test script to diagnose TikTok link grabbing issues
:: This tests yt-dlp directly to see what's happening

echo ========================================
echo TikTok Link Grabber Diagnostic Test
echo ========================================
echo.

:: Test 1: Check yt-dlp version
echo [TEST 1] Checking yt-dlp version...
yt-dlp --version
if errorlevel 1 (
    echo ERROR: yt-dlp not found or not working!
    pause
    exit /b 1
)
echo.

:: Test 2: Simple command without cookies (like your batch script)
echo [TEST 2] Testing simple command WITHOUT cookies...
echo Command: yt-dlp --flat-playlist --get-url https://www.tiktok.com/@elaime.liao
echo.
yt-dlp --flat-playlist --get-url "https://www.tiktok.com/@elaime.liao"
echo.
echo Result: Check if any URLs were printed above
echo.
pause

:: Test 3: With cookies
echo [TEST 3] Testing WITH cookies file...
echo Command: yt-dlp --flat-playlist --get-url --cookies cookies\tiktok.txt https://www.tiktok.com/@elaime.liao
echo.
if exist "cookies\tiktok.txt" (
    yt-dlp --flat-playlist --get-url --cookies "cookies\tiktok.txt" "https://www.tiktok.com/@elaime.liao"
    echo.
) else (
    echo WARNING: cookies\tiktok.txt not found!
    echo Please create cookie file first.
    echo.
)
pause

:: Test 4: Verbose mode to see errors
echo [TEST 4] Testing with VERBOSE mode to see errors...
echo Command: yt-dlp --flat-playlist --get-url --verbose --cookies cookies\tiktok.txt https://www.tiktok.com/@elaime.liao
echo.
if exist "cookies\tiktok.txt" (
    yt-dlp --flat-playlist --get-url --verbose --cookies "cookies\tiktok.txt" "https://www.tiktok.com/@elaime.liao" 2>&1 | more
) else (
    yt-dlp --flat-playlist --get-url --verbose "https://www.tiktok.com/@elaime.liao" 2>&1 | more
)
echo.
pause

:: Test 5: Check if TikTok is blocking
echo [TEST 5] Testing if TikTok extractor works at all...
echo Trying a single TikTok video instead of profile...
yt-dlp --get-url "https://www.tiktok.com/@scout2015/video/6718335390845095173"
echo.
pause

echo ========================================
echo Diagnostic Complete!
echo ========================================
echo.
echo If all tests failed:
echo   - TikTok might be blocking yt-dlp
echo   - Your IP might be geo-blocked
echo   - Cookies might be expired
echo   - yt-dlp might need updating: yt-dlp -U
echo.
echo If test worked in browser but not here:
echo   - Use fresh cookies from Chrome extension
echo   - Try --cookies-from-browser chrome
echo.
pause
