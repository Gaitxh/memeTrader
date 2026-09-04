param(
  [ValidateRange(1, 65535)]
  [int]$Port = 8790,
  [string]$HostAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$logDir = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

& $python -m memetrader chain-web --config config.json --host $HostAddress --port $Port
exit $LASTEXITCODE
