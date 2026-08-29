$ErrorActionPreference = "Stop"
$remover = Join-Path $PSScriptRoot "remove_scheduled_task.ps1"
if (-not (Test-Path $remover)) {
  throw "Scheduled-task remover not found: $remover"
}
& $remover
