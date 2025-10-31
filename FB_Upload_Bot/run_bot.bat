@echo off
REM Facebook Upload Bot - Windows Launcher
REM Double-click this file to run the bot

echo.
echo ========================================
echo   Facebook Upload Bot Launcher
echo ========================================
echo.

REM Check if venv exists
if exist "venv\Scripts\activate.bat" (
    echo [+] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [!] Virtual environment not found
    echo [!] Using system Python
)

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] ERROR: Python is not installed or not in PATH
    echo [!] Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

REM Check if requirements are installed
python -c "import selenium" >nul 2>&1
if errorlevel 1 (
    echo [!] Dependencies not installed
    echo [+] Installing requirements...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [X] Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Run the bot
echo [+] Starting Facebook Upload Bot...
echo.
python fb_upload_bot.py

REM Keep window open
echo.
echo ========================================
echo   Bot finished
echo ========================================
pause
