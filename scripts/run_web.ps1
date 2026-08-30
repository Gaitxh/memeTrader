param(
  [ValidateRange(1, 65535)]
  [int]$Port = 8787,
  [string]$HostAddress = "127.0.0.1",
  [string]$AccessTokenFile = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$logDir = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

$arguments = @(
  "-m", "memetrader", "web",
  "--config", "config.json",
  "--host", $HostAddress,
  "--port", "$Port"
)
if ($AccessTokenFile) {
  $arguments += @("--access-token-file", $AccessTokenFile)
}

& $python @arguments
exit $LASTEXITCODE
