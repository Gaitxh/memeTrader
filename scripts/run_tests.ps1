$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\python.exe -m compileall -q src tests
& .\.venv\Scripts\python.exe -m memetrader replay examples\historical\temporal_guard.synthetic.json --decision-at 2026-01-01T00:05:00Z
