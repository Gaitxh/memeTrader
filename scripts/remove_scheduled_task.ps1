$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$taskName = "memeTrader Paper Bot"
$legacyRunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$legacyRunName = "memeTraderPaperBot"
$startup = [Environment]::GetFolderPath("Startup")
$legacyShortcut = Join-Path $startup "memeTrader Paper Bot.lnk"

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
  Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
  Write-Host "Removed scheduled task: $taskName"
} else {
  Write-Host "Scheduled task not installed: $taskName"
}

if (Get-ItemProperty -Path $legacyRunKey -Name $legacyRunName -ErrorAction SilentlyContinue) {
  Remove-ItemProperty -Path $legacyRunKey -Name $legacyRunName -Force
  Write-Host "Removed legacy current-user Run entry: $legacyRunName"
}
if (Test-Path $legacyShortcut) {
  Remove-Item $legacyShortcut -Force
  Write-Host "Removed legacy startup shortcut: $legacyShortcut"
}

$processes = Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and $_.CommandLine -like "*$root*" -and (
    ($_.Name -eq "powershell.exe" -and $_.CommandLine -like "*memeTrader*run_paper.ps1*") -or
    ($_.Name -eq "python.exe" -and $_.CommandLine -like "*-m memetrader run*")
  )
} | Sort-Object @{Expression = { if ($_.Name -eq "powershell.exe") { 0 } else { 1 } }}

foreach ($process in $processes) {
  if (Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue) {
    & taskkill.exe /PID $process.ProcessId /T /F | Out-Null
  }
}

Write-Host "memeTrader startup and resident processes removed."
