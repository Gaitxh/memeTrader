@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0scripts\check_system.ps1"
set "check_exit=%ERRORLEVEL%"
echo.
if /I "%~1"=="--no-pause" goto done
pause
:done
exit /b %check_exit%
