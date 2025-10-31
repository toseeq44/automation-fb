@echo off
REM Facebook Upload Bot - Windows Setup Script
REM Run this first to set up the bot

echo.
echo ========================================
echo   Facebook Upload Bot Setup
echo ========================================
echo.

REM Check Python
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] ERROR: Python is not installed
    echo [!] Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)
python --version
echo [+] Python found!
echo.

REM Create virtual environment
echo [2/5] Creating virtual environment...
if exist "venv" (
    echo [!] Virtual environment already exists
) else (
    python -m venv venv
    if errorlevel 1 (
        echo [X] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [+] Virtual environment created!
)
echo.

REM Activate virtual environment
echo [3/5] Activating virtual environment...
call venv\Scripts\activate.bat
echo [+] Virtual environment activated!
echo.

REM Install dependencies
echo [4/5] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [X] Failed to install dependencies
    pause
    exit /b 1
)
echo [+] Dependencies installed!
echo.

REM Run setup wizard
echo [5/5] Running setup wizard...
echo.
python setup.py

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Configure your settings in config/settings.json
echo   2. Add your videos to creators/ folder
echo   3. Set up login credentials in creator_shortcuts/
echo   4. Run: run_bot.bat
echo.
pause
