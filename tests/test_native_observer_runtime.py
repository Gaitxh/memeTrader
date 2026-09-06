import asyncio
from types import SimpleNamespace

from memetrader.runtime import Runtime
from memetrader.models import iso, utcnow


def test_official_sources_rotate_without_new_hot_path_calls():
    runtime = Runtime.__new__(Runtime)
    collectors = []
    async def collect(*, collector):
        collectors.append(collector.__name__)
    runtime.chain_meme_authoritative_events_once = collect
    async def run():
        for _ in range(4):
            await runtime.chain_meme_extra_official_once()
    asyncio.run(run())
    assert collectors == ["collect_kraken_listing_events", "collect_kucoin_listing_events",
                          "collect_coinbase_status_observations", "collect_kraken_listing_events"]


def test_native_event_only_queues_bounded_identity_hydration():
    at = iso(utcnow())
    events = [{"token": "0x" + f"{i:040x}", "event": "TokenCreate",
        "transaction_hash": f"tx{i}", "log_index": i, "observed_at": at} for i in range(10)]
    class Observer:
        CHAIN, ERROR_PREFIX = "bsc", "four_meme"
        async def observe(self):
            return {"status": "OK", "events": events, "observed_at": at, "skipped_blocks": 3}
    runtime = Runtime.__new__(Runtime)
    runtime._critical_onchain_exit_event = asyncio.Event()
    runtime._evm_route_quote_lock = asyncio.Lock()
    idle = asyncio.Event()
    idle.set()
    runtime._chain_meme_active_idle = lambda: idle
    runtime._native_launch_observers = [Observer()]
    runtime._native_launch_cursor = 0
    queued, recorded, heartbeats = [], [], []
    runtime.store = SimpleNamespace(start_token_discovery_round=lambda **kw: 1,
        token_discovery_known=lambda key: False,
        record_chain_meme_pattern_evidence=lambda *a, **kw: recorded.append((a,kw)) or 1,
        upsert_token=lambda *a, **kw: None,
        enqueue_token_detail_hydration=lambda *a, **kw: queued.append(a),
        add_token_discovery_exposure=lambda *a, **kw: None,
        finish_token_discovery_round=lambda *a, **kw: None,
        heartbeat=lambda *a, **kw: heartbeats.append(kw))
    asyncio.run(runtime.chain_meme_native_launch_once())
    assert len(queued) == len(recorded) == 8
    assert all(row[0][1] == "" for row in recorded)  # TokenManager is never a pool.
    assert "unprocessed=2" in heartbeats[-1]["error_detail"]
    runtime._critical_onchain_exit_event.set()
    asyncio.run(runtime.chain_meme_native_launch_once())
    assert len(queued) == 8  # Exit-priority skip does not poll or hydrate.
