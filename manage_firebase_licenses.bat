@echo off
set "PYTHON_EXE=python"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

%PYTHON_EXE% manage_firebase_licenses.py %*
