import asyncio
import json
import threading
from datetime import timedelta

from memetrader.admission_audit import AdmissionAudit
from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.runtime import Runtime


def flush(audit):
    async def run():
        await audit.flush()
        if audit.flush_task is not None:
            await audit.flush_task
    asyncio.run(run())


def test_audit_preserves_actual_watch_and_has_no_receipt_io(tmp_path, monkeypatch):
    now = utcnow()
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: now)
    plain, audited = Runtime.__new__(Runtime), Runtime.__new__(Runtime)
    for runtime in (plain, audited):
        runtime.config = {"paper": {"max_quote_age_seconds": 45}}
        runtime._pattern_held_tokens = set()
    audit = audited._admission_audit = AdmissionAudit(tmp_path / "audit")

    def send(index, age=60, liquidity=5000, pool=None):
        token = TokenCandidate("bsc", f"0x{index:040x}", "fixture")
        snapshot = TokenSnapshot("bsc", token.address, 1, liquidity, None, 200, 6, 4,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"pairAddress": pool or f"0x{index+100:040x}",
                "pairCreatedAt": (now-timedelta(seconds=age)).timestamp()*1000}})
        for runtime in (plain, audited):
            runtime._remember_pattern_quotes({token.token_id: (token, snapshot)})
        assert plain._pattern_watch == audited._pattern_watch
        assert plain._pattern_watch_nonheld_by_chain_bucket == audited._pattern_watch_nonheld_by_chain_bucket

    for i in range(10):
        send(i)
    send(10)  # full valid watch
    send(0, liquidity=0)
    send(11)  # unusable replacement
    send(12, age=2000)  # growth base reclaims early borrow
    send(12, age=2000, pool="another-pool")
    assert not audit.path.exists()
    reasons = [x["actual"]["reason"] for x in audit.pending]
    assert {"admit_base", "admit_borrow", "skip_bucket_full", "replace_unusable",
            "reclaim_reservation", "skip_other_pool"} <= set(reasons)
    assert len(audit.pending[-1]["actual_pre"]) == 10
    flush(audit)
    rows = [json.loads(line) for line in audit.path.read_text().splitlines()]
    assert len(rows) == 15
    assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in rows)
    assert audit.status()["written"] == 15


def test_audit_overflow_and_sink_failure_do_not_affect_receipts(tmp_path):
    audit = AdmissionAudit(tmp_path)
    audit.MAX_PENDING = 1
    now = utcnow()
    token = TokenCandidate("bsc", "token", "fixture")
    snap = TokenSnapshot("bsc", "token", 1, 5000, None, 1, None, None,
        observed_at=now, ingested_at=now, raw={"pairAddress": "pool", "pairCreatedAt": now.timestamp()*1000})
    event = audit.capture(now, token, snap, {}, set(), 1000)
    event["actual"] = {"reason": "admit_base"}
    assert audit.capture(now, token, snap, {}, set(), 1000) is None
    assert audit.status()["dropped_audit"] == 1
    flush(audit)
    rows = [json.loads(line) for line in audit.path.read_text().splitlines()]
    assert rows[0]["kind"] == "DROPPED_AUDIT"
    audit.last_flush = 0
    event = audit.capture(now, token, snap, {}, set(), 1000)
    event["actual"] = {}
    audit._write = lambda *args: (_ for _ in ()).throw(OSError("fixture unavailable"))
    flush(audit)
    assert audit.status()["errors"] == 1
    assert audit.status()["dropped_audit"] == 2


def test_slow_audit_sink_does_not_block_cohort_or_spawn_more_workers(tmp_path):
    audit = AdmissionAudit(tmp_path)
    released = threading.Event()
    audit.pending.append({})
    audit._write = lambda *args: (released.wait(2), 1)[1]

    async def run():
        await asyncio.wait_for(audit.flush(), .1)
        worker = audit.flush_task
        audit.pending.append({})
        audit.last_flush = 0
        await asyncio.wait_for(audit.flush(), .1)
        assert audit.flush_task is worker and len(audit.pending) == 1
        released.set()
        await worker
    asyncio.run(run())
