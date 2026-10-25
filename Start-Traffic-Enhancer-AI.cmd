@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-windows.ps1" -AI
if errorlevel 1 echo Startup failed. Read the errors above.
pause
