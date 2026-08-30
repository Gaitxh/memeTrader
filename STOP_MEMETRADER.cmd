@echo off
setlocal
cd /d E:\memeTrader
if exist scripts\stop_scheduled_task.ps1 (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\stop_scheduled_task.ps1
) else if exist scripts\remove_scheduled_task.ps1 (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\remove_scheduled_task.ps1
) else (
  schtasks /End /TN "memeTrader-Paper" >nul 2>nul
)
pause
