param([switch]$NoOpen)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run_chain_web.ps1"
$healthUrl = "http://127.0.0.1:8790/health"
$siteUrl = "http://127.0.0.1:8790/"

function Test-ChainWeb {
  try {
    $result = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    return [bool]$result.ok
  } catch {
    return $false
  }
}

if (-not (Test-ChainWeb)) {
  Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $root `
    -WindowStyle Hidden
  $ready = $false
  for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (Test-ChainWeb) { $ready = $true; break }
  }
  if (-not $ready) { throw "ChainMemeTrader Web did not become ready at $healthUrl" }
}

if (-not $NoOpen) { Start-Process $siteUrl }
