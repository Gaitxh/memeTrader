from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_command_is_project_relative_and_preserves_check_exit():
    text=(ROOT/'CHECK_MEMETRADER.cmd').read_text(encoding='utf-8-sig')
    assert 'cd /d "%~dp0"' in text
    assert '%~dp0scripts\\check_system.ps1' in text
    assert 'set "check_exit=%ERRORLEVEL%"' in text
    assert 'exit /b %check_exit%' in text
    assert '--no-pause' in text
    assert 'E:\\memeTrader' not in text and '8765' not in text
    assert '-m memetrader status' not in text

def test_checker_reads_primary_console_without_mutating_services():
    text=(ROOT/'scripts/check_system.ps1').read_text(encoding='utf-8-sig')
    assert 'http://127.0.0.1:8790' in text
    assert '/api/live?summary_only=1' in text
    assert "Split-Path -Parent $PSScriptRoot" in text
    for prohibited in ('Stop-Process','Start-Process','Set-Content','Add-Content','sqlite3','ExecutionPolicy Bypass'):
        assert prohibited not in text

def test_api_failure_and_empty_holdings_are_not_zero_trade_claims():
    text=(ROOT/'scripts/check_system.ps1').read_text(encoding='utf-8-sig')
    assert "runtime_status = 'unknown'" in text
    assert 'open_positions = $null' in text
    assert 'Zero open positions is not zero historical trades' in text
    assert 'API process path is not independently attested' in text
    assert '$config.live.enabled' in text
    assert '$live.system.paper_only -and $live.system.live_locked' in text

def test_powershell_syntax_is_valid():
    exe=shutil.which('powershell.exe') or shutil.which('pwsh')
    if exe is None: pytest.skip('PowerShell parser unavailable on this test host')
    path=str(ROOT/'scripts/check_system.ps1').replace("'","''")
    command=("$tokens=$null; $errors=$null; "
        f"[void][System.Management.Automation.Language.Parser]::ParseFile('{path}',[ref]$tokens,[ref]$errors); "
        "if ($errors.Count) { $errors | Out-String | Write-Output; exit 1 }")
    result=subprocess.run([exe,'-NoProfile','-Command',command],capture_output=True,text=True,timeout=15)
    assert result.returncode==0, result.stdout+result.stderr
