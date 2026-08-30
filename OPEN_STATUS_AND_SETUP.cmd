@echo off
setlocal
set "ROOT=E:\memeTrader"
if exist "%ROOT%\CURRENT_STATUS.md" start "" notepad.exe "%ROOT%\CURRENT_STATUS.md"
start "" explorer.exe "%ROOT%\browser-extension"
start "" explorer.exe "%ROOT%"
where msedge.exe >nul 2>nul && start "" msedge.exe "edge://extensions/"
where chrome.exe >nul 2>nul && start "" chrome.exe "chrome://extensions/"
echo.
echo 1. Turn on Developer mode in Chrome/Edge extensions.
echo 2. Choose Load unpacked and select E:\memeTrader\browser-extension.
echo 3. Open extension options and copy bridge.token from E:\memeTrader\config.json.
echo 4. Keep only curated PUBLIC feeds/pages open. Private messages are intentionally excluded.
echo.
pause
