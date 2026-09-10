@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0scripts\start_system.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed. Details are above; logs: %~dp0data\logs
  pause
  exit /b 1
)
exit /b 0
