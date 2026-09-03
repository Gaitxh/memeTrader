param(
  [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run_web.ps1"
$healthUrl = "http://127.0.0.1:8787/api/health"
$siteUrl = "http://127.0.0.1:8787/"

function Test-WebConsole {
  try {
    $result = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    return [bool]$result.ok
  } catch {
    return $false
  }
}

function Test-LoopbackListener {
  return [bool](Get-NetTCPConnection `
    -LocalAddress "127.0.0.1" `
    -LocalPort 8787 `
    -State Listen `
    -ErrorAction SilentlyContinue)
}

if (-not (Test-WebConsole) -and -not (Test-LoopbackListener)) {
  Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $root `
    -WindowStyle Hidden

  $ready = $false
  for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (Test-WebConsole) {
      $ready = $true
      break
    }
  }
  if (-not $ready) {
    throw "memeTrader Web Console did not become ready at $healthUrl"
  }
}

if (-not $NoOpen) {
  Start-Process $siteUrl
}
