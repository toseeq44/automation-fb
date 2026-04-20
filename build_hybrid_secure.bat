@echo off
REM OneSoul Hybrid Secure Build Script
REM Builds critical modules with Nuitka, then packages the app with PyInstaller.

setlocal

echo ============================================
echo   OneSoul Hybrid Secure Builder
echo ============================================
echo.

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo [1/6] Using virtual environment Python...
    echo     %PYTHON_EXE%
) else (
    echo [!] Warning: Virtual environment not found
    echo     Continuing with global Python...
)

echo.
echo [2/6] Building Nuitka critical modules...
%PYTHON_EXE% build_nuitka_critical.py
if errorlevel 1 (
    echo.
    echo [!] Nuitka critical-module build failed.
    exit /b 1
)

echo.
echo [3/6] Probe compiled modules...
%PYTHON_EXE% launch_nuitka_critical_test.py --probe-only
if errorlevel 1 (
    echo.
    echo [!] Probe failed. Compiled modules are not loading cleanly.
    exit /b 1
)

echo.
echo [4/6] Enabling hybrid PyInstaller packaging...
set "ONESOUL_ENABLE_NUITKA_CRITICAL=1"

echo.
echo [5/6] Running standard build flow with hybrid flag...
call build.bat
if errorlevel 1 (
    echo.
    echo [!] Hybrid PyInstaller build failed.
    exit /b 1
)

echo.
echo [6/6] Hybrid secure build completed.
echo Output location: dist\OneSoul\
echo Main executable: dist\OneSoul\OneSoul.exe
echo.
endlocal
