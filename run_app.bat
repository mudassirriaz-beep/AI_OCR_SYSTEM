@echo off
title AI Document System
cd /d "%~dp0"

:: First-time setup if venv doesn't exist
if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. Running first-time setup...
    echo.
    call setup_env.bat
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

:: Activate virtual environment
call venv\Scripts\activate.bat

echo.
echo ============================================
echo   AI Document System is starting...
echo   Open your browser at: http://localhost:5001
echo   Press Ctrl+C to stop the server.
echo ============================================
echo.

:: Open browser after 3-second delay (in background)
start "" /B powershell -WindowStyle Hidden -Command "Start-Sleep 3; Start-Process 'http://localhost:5001'"

:: Start the Flask app
python form_filler_ui.py

pause
