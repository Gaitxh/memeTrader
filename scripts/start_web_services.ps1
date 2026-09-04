$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$localStarter = Join-Path $PSScriptRoot "open_web_console.ps1"
$protectedStarter = Join-Path $PSScriptRoot "share_web_console.ps1"
$chainStarter = Join-Path $PSScriptRoot "open_chain_web.ps1"
$mutex = [System.Threading.Mutex]::new($false, "Local\memeTraderWebServicesStartup")
$acquired = $false

try {
  $acquired = $mutex.WaitOne([TimeSpan]::FromSeconds(30))
  if (-not $acquired) {
    throw "Another memeTrader Web services startup is still in progress."
  }

  Set-Location $root
  & $localStarter -NoOpen | Out-Null
  & $chainStarter -NoOpen | Out-Null
  & $protectedStarter -NoOpen | Out-Null
} finally {
  if ($acquired) {
    $mutex.ReleaseMutex()
  }
  $mutex.Dispose()
}
