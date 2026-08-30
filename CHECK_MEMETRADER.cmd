@echo off
setlocal
cd /d E:\memeTrader
if not exist .venv\Scripts\python.exe (
  echo Python environment is missing. Run scripts\install_windows.ps1 first.
  pause
  exit /b 2
)
.venv\Scripts\python.exe -m memetrader status --config config.json --limit 30
powershell.exe -NoProfile -Command "try { Invoke-RestMethod http://127.0.0.1:8765/health | ConvertTo-Json -Depth 5 } catch { Write-Error $_; exit 3 }"
echo.
pause
