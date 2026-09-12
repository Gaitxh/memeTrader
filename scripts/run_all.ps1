<#
  Entry point for the scheduled task that owns the whole memeTrader runtime on
  this machine.

  It exists for one reason: the runtime must not inherit this host's proxy
  variables (see `run_with_clean_env.ps1` for the full explanation - NO_PROXY
  contains `[::1]`, which httpx 0.28 cannot parse, and HTTPS_PROXY would send
  every websocket handshake through a proxy the installed libraries cannot use).
  The scheduled task launches this file, this file sanitizes the environment
  once, and both services below inherit the sanitized copy.

  Services, in order:
    1. ChainMemeTrader Web console on 127.0.0.1:8790 (skipped when already up)
    2. Paper runtime supervisor (blocking; restarts the bot if it exits)
#>
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

# Same egress decision as `run_with_clean_env.ps1`: keep the local mixed-port
# proxy for the websocket collectors (DexScreener's WSS surfaces are reachable
# only through it on this network), and keep NO_PROXY parseable so httpx 0.28
# does not raise `InvalidURL: Invalid port: ':1]'` on the `[::1]` entry this
# machine used to export.
$proxyUrl = "http://127.0.0.1:7890"
$env:HTTP_PROXY = $proxyUrl
$env:HTTPS_PROXY = $proxyUrl
$env:http_proxy = $proxyUrl
$env:https_proxy = $proxyUrl
$env:NO_PROXY = "localhost,127.0.0.1"
$env:no_proxy = $env:NO_PROXY

Set-Location $root

function Test-ChainWeb {
  try {
    $result = Invoke-RestMethod -Uri "http://127.0.0.1:8790/health" -TimeoutSec 3
    return [bool]$result.ok
  } catch {
    return $false
  }
}

if (-not (Test-ChainWeb)) {
  Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\run_chain_web.ps1`"" `
    -WorkingDirectory $root `
    -WindowStyle Hidden
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    if (Test-ChainWeb) { break }
  }
}

# Blocking supervisor loop: keeps the Paper runtime alive.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\run_paper.ps1"
exit $LASTEXITCODE
