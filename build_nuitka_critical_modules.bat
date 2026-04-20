@echo off
setlocal

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

echo ============================================
echo   Nuitka Critical Module Builder
echo ============================================
echo Using Python: %PYTHON_EXE%
echo.

%PYTHON_EXE% build_nuitka_critical.py
if errorlevel 1 (
    echo.
    echo Nuitka critical-module build failed.
    exit /b 1
)

echo.
echo Probe command:
echo   %PYTHON_EXE% launch_nuitka_critical_test.py --probe-only
echo Launch command:
echo   %PYTHON_EXE% launch_nuitka_critical_test.py
echo.
endlocal
