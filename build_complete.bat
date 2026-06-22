@echo off
cd /d "%~dp0"
echo ================================================================
echo  AI Document System - Complete Build
echo  Everything downloads automatically. No manual steps needed.
echo ================================================================
echo.
powershell -ExecutionPolicy Bypass -NoExit -File "%~dp0build_complete.ps1"
echo.
pause
