$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$taskName = "memeTrader Paper Bot"
$runner = Join-Path $PSScriptRoot "run_paper.ps1"
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$legacyRunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$legacyRunName = "memeTraderPaperBot"

if (-not (Test-Path $runner)) {
  throw "Runner not found: $runner"
}

if (Get-ItemProperty -Path $legacyRunKey -Name $legacyRunName -ErrorAction SilentlyContinue) {
  Remove-ItemProperty -Path $legacyRunKey -Name $legacyRunName -Force
  Write-Host "Removed legacy current-user Run entry: $legacyRunName"
}

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
  Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
}

$arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`""
$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument $arguments `
  -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$settings = New-ScheduledTaskSettingsSet `
  -MultipleInstances IgnoreNew `
  -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -StartWhenAvailable `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal `
  -UserId $userId `
  -LogonType Interactive `
  -RunLevel Limited

Register-ScheduledTask `
  -TaskName $taskName `
  -Action $action `
  -Trigger $trigger `
  -Settings $settings `
  -Principal $principal `
  -Force | Out-Null

Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2
$task = Get-ScheduledTask -TaskName $taskName
Write-Host "Installed and started scheduled task: $taskName"
Write-Host "State: $($task.State)"
Write-Host "Runner: $runner"
