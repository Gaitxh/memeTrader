"""Exercise the launcher with mocked process/network calls; never start services."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("already_running,locked", [(False, True), (True, True), (True, False)])
def test_system_launcher(tmp_path, already_running, locked):
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Windows launcher")
    source = Path(__file__).resolve().parents[1]
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("start_system.ps1", "open_chain_web.ps1"):
        shutil.copyfile(source / "scripts" / name, scripts / name)
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    driver = tmp_path / "check.ps1"
    driver.write_text(r'''
$ErrorActionPreference = 'Stop'
$global:launches = [System.Collections.Generic.List[string]]::new()
function Start-Process { param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,$RedirectStandardOutput,$RedirectStandardError)
  $global:launches.Add([string]$ArgumentList)
  $global:started = $true
}
function Get-CimInstance { param($ClassName,$Filter)
  if ($global:started) {
    [pscustomobject]@{CommandLine='-m memetrader run --config config.json';ExecutablePath=(Join-Path $PSScriptRoot '.venv\Scripts\python.exe');ProcessId=101;ParentProcessId=100}
  }
}
function Invoke-RestMethod { param($Uri,$TimeoutSec)
  if ($Uri -like '*/api/live') {
    return @{version='existing-period';system=@{runtime_status='running';paper_only=$true;live_locked=$global:locked;heartbeat_age_seconds=1;open_position_count=0}}
  }
  if ($Uri -like '*/api/performance') { return @{generated_at='2026-09-10T00:00:00Z'} }
  return @{ok=$true;runtime_status='running';version='existing-period'}
}
$global:started = RUNNING
$global:locked = LOCKED
$failed = $false
try { & (Join-Path $PSScriptRoot 'scripts\start_system.ps1') -NoOpen } catch { $failed = $true }
[pscustomobject]@{launches=@($global:launches);failed=$failed} | ConvertTo-Json -Compress
'''.replace("RUNNING", "$true" if already_running else "$false")
       .replace("LOCKED", "$true" if locked else "$false"), encoding="utf-8-sig")
    result = subprocess.run([powershell, "-NoProfile", "-File", str(driver)],
                            capture_output=True, text=True, timeout=20, check=True)
    state = json.loads(result.stdout.strip().splitlines()[-1])
    assert state["failed"] is not locked
    assert len(state["launches"]) == (0 if already_running else 1)
    if state["launches"]:
        assert "run_paper.ps1" in state["launches"][0]
