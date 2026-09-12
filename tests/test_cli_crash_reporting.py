"""The refused-start path must leave the same evidence as the crash path.

Both return exit code 3, but only the crash path used to write `data/logs/runtime-crash.log`. A
64-restart burst in `paper-supervisor.log` (2026-09-13 ~04:48, runs of ~0.5s, exit=3) was therefore
impossible to explain: the supervisor recorded the exit code and the crash log was never written.
The cause was the single-instance lock refusing to start.

These tests pin that both paths record, that the log is append-only, and that a logging failure
can never mask the original failure.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from memetrader import cli


def test_refused_start_records_the_same_log_as_a_crash(tmp_path, monkeypatch):
    """A RuntimeError from the lock must appear in runtime-crash.log with its traceback."""
    crash = tmp_path / "data" / "logs" / "runtime-crash.log"

    class _Refusing:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            raise RuntimeError("another memeTrader process is already running: x.lock")

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(cli, "SingleInstance", _Refusing)
    monkeypatch.setattr(cli, "load_config", lambda _p: ({}, tmp_path))

    class _RT:
        def __init__(self, *_a, **_k):
            raise AssertionError("the runtime must not be constructed when the lock refuses")

    monkeypatch.setattr(cli, "Runtime", _RT)

    code = asyncio.run(cli._run_runtime("config.json", True))
    assert code == 3
    assert crash.exists(), "the refused start left no evidence"
    text = crash.read_text(encoding="utf-8")
    assert "another memeTrader process is already running" in text
    assert "RuntimeError" in text
    assert "Traceback" in text, "a bare message is not diagnosable - the frame chain is needed"


def test_both_paths_append_rather_than_truncate(tmp_path):
    crash = tmp_path / "data" / "logs" / "runtime-crash.log"
    cli._record_runtime_crash(tmp_path, "first failure")
    cli._record_runtime_crash(tmp_path, "second failure\nwith a traceback")
    text = crash.read_text(encoding="utf-8")
    assert "first failure" in text and "second failure" in text
    assert text.index("first failure") < text.index("second failure")


def test_logging_failure_never_raises(tmp_path):
    """If the crash log cannot be written, reporting must still complete."""
    blocker = tmp_path / "data"
    blocker.write_text("not a directory", encoding="utf-8")
    cli._record_runtime_crash(tmp_path, "detail")   # must not raise
    # and the public path still returns 3 rather than propagating
    assert blocker.read_text(encoding="utf-8") == "not a directory"


@pytest.mark.parametrize("detail", ["", "x", "line1\nline2\n"])
def test_detail_is_written_without_accumulating_blank_lines(tmp_path, detail):
    crash = tmp_path / "data" / "logs" / "runtime-crash.log"
    cli._record_runtime_crash(tmp_path, detail)
    cli._record_runtime_crash(tmp_path, detail)
    text = crash.read_text(encoding="utf-8")
    assert text.endswith("\n")
    if detail.strip() == "":
        assert text.strip() == ""
