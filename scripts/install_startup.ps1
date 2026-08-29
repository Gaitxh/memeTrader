$ErrorActionPreference = "Stop"
$installer = Join-Path $PSScriptRoot "install_scheduled_task.ps1"
if (-not (Test-Path $installer)) {
  throw "Scheduled-task installer not found: $installer"
}
Write-Host "The legacy HKCU Run startup path is deprecated; installing the single scheduled task instead."
& $installer
