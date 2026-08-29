$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[test]"
if (-not (Test-Path "config.json")) {
  & .\.venv\Scripts\python.exe -m memetrader init --config config.json
}
Write-Host "Installed. Run scripts\run_tests.ps1, then memetrader doctor --online."
