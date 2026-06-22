@echo off
title AI Document System - First Time Setup
cd /d "%~dp0"

echo ============================================
echo   AI Document System - Environment Setup
echo ============================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10 or newer.
    echo Download from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

:: Create virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

:: Activate and install packages
echo.
echo Installing dependencies (this may take several minutes)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo WARNING: Some packages may have failed. Check output above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Setup complete! You can now run:
echo   run_app.bat
echo ============================================
pause
