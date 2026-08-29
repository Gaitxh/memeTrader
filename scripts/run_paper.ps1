$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$logDir = Join-Path (Get-Location) "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$supervisorLog = Join-Path $logDir "paper-supervisor.log"
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

while ($true) {
  $started = Get-Date
  $exitCode = -1

  try {
    # Keep Python attached to this PowerShell process so Task Scheduler owns the
    # complete process tree. Structured runtime events are already persisted by
    # memeTrader to data/notifications.jsonl; Python crashes go to
    # data/logs/runtime-crash.log.
    & $python -m memetrader run --config config.json
    $exitCode = $LASTEXITCODE
  } catch {
    $_ | Out-String | Add-Content -Path $supervisorLog -Encoding UTF8
    $exitCode = -1
  }

  $elapsed = [Math]::Round(((Get-Date) - $started).TotalSeconds, 1)
  if ($exitCode -eq 0) {
    Add-Content -Path $supervisorLog -Encoding UTF8 -Value "$(Get-Date -Format o) run_seconds=$elapsed exit=0 stopped"
    exit 0
  }

  Add-Content -Path $supervisorLog -Encoding UTF8 -Value "$(Get-Date -Format o) run_seconds=$elapsed exit=$exitCode restart_in=5"
  Start-Sleep -Seconds 5
}
