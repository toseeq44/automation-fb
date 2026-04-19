@echo off
setlocal

cd /d "%~dp0\.."

echo ============================================
echo   OneSoul License Server
echo ============================================
echo Fixed client URL comes from license_endpoints.json
echo Starting server on http://localhost:5000
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" server\app.py
) else (
    python server\app.py
)

endlocal
