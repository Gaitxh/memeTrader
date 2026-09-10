param([switch]$NoOpen, [ValidateRange(10, 180)][int]$WaitSeconds = 90)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot 'run_paper.ps1'
$python = Join-Path $root '.venv\Scripts\python.exe'
$baseUrl = 'http://127.0.0.1:8790'
$mutex = [System.Threading.Mutex]::new($false, 'Local\memeTraderSystemStartup')
$acquired = $false

function Get-PaperProcesses {
  $processes = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe' OR Name='python.exe'")
  $supervisors = @($processes | Where-Object {
    $_.CommandLine -match ('-File\s+"?' + [regex]::Escape($runner) + '(?:"|\s|$)')
  })
  $workers = @($processes | Where-Object {
    $_.CommandLine -match '-m\s+memetrader\s+run\s+--config\s+"?config\.json(?:"|\s|$)' -and
    ($_.ExecutablePath -eq $python -or $_.ParentProcessId -in $supervisors.ProcessId)
  })
  return @($supervisors) + @($workers)
}

try {
  $acquired = $mutex.WaitOne([TimeSpan]::FromSeconds($WaitSeconds))
  if (-not $acquired) { throw 'Another startup is in progress. Please wait for that window.' }
  Set-Location $root
  if (-not (Test-Path -LiteralPath $python)) { throw "Project Python is missing: $python" }
  $logDir = Join-Path $root 'data\logs'
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null

  if (@(Get-PaperProcesses).Count -eq 0) {
    Write-Host 'Starting Paper runtime...'
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Start-Process -FilePath 'powershell.exe' `
      -ArgumentList "-NoProfile -File `"$runner`"" `
      -WorkingDirectory $root -WindowStyle Hidden `
      -RedirectStandardOutput (Join-Path $logDir "startup-$stamp-paper-out.log") `
      -RedirectStandardError (Join-Path $logDir "startup-$stamp-paper-err.log") | Out-Null
  } else {
    Write-Host 'Reusing existing Paper runtime/supervisor.'
  }

  Write-Host 'Starting/checking the current Web console (8790)...'
  & (Join-Path $PSScriptRoot 'open_chain_web.ps1') -NoOpen
  $deadline = (Get-Date).AddSeconds($WaitSeconds)
  $ready = $false
  do {
    try { $health = Invoke-RestMethod "$baseUrl/health" -TimeoutSec 3 } catch { $health = $null }
    if ($health.ok -and $health.runtime_status -eq 'running' -and @(Get-PaperProcesses).Count -gt 0) {
      $ready = $true
      break
    }
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $deadline)
  if (-not $ready) { throw "Web may be available but Paper heartbeat is not ready. Logs: $logDir" }

  $live = Invoke-RestMethod "$baseUrl/api/live" -TimeoutSec 15
  $performance = Invoke-RestMethod "$baseUrl/api/performance" -TimeoutSec 15
  if ($live.system.runtime_status -ne 'running' -or -not $live.system.paper_only -or -not $live.system.live_locked) {
    throw 'Runtime/Paper safety status is not ready. No settings have been changed.'
  }
  if ($live.version -ne $health.version -or -not $performance.generated_at) {
    throw 'API status is incomplete or inconsistent. Please inspect the logs.'
  }
  Write-Host "READY: Paper running; Live locked; funding period $($live.version)"
  Write-Host "Heartbeat age: $($live.system.heartbeat_age_seconds)s; open positions: $($live.system.open_position_count)"
  Write-Host "$baseUrl/#/overview"
  if (-not $NoOpen) { Start-Process "$baseUrl/#/overview" }
} finally {
  if ($acquired) { $mutex.ReleaseMutex() }
  $mutex.Dispose()
}
