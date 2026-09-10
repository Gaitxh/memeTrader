import asyncio
from datetime import timedelta
from types import SimpleNamespace

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import Runtime


class LeaseStore:
    def __init__(self):
        self.kv = {}
        self._market_entry_pending_tokens = set()
        self._pattern_ready_until = {}
        self.saved = []
        self.observed = 0

    def get_kv(self, key, default=None):
        return self.kv.get(key, default)

    def set_kv(self, key, value):
        self.kv[key] = value
        self.saved.append((key, value))

    def capital_cross_section(self, _):
        return {}

    def observe_chain_meme_pattern(self, *_, **__):
        self.observed += 1
        return 0

    def heartbeat(self, *_, **__):
        return None


def quote(now, number, *, age=600):
    token = TokenCandidate("bsc", f"0x{number:040x}", "lease fixture", "L")
    pair = f"0x{number + 1000:040x}"
    snapshot = TokenSnapshot(
        "bsc", token.address, 1.0, 5000.0, 100000.0, 500.0, 6, 3,
        observed_at=now, ingested_at=now, provider="fixture",
        raw={"pair": {"chainId": "bsc", "baseToken": {"address": token.address, "name": "lease fixture", "symbol": "L"},
                       "pairAddress": pair, "pairCreatedAt": (now - timedelta(seconds=age)).timestamp() * 1000}},
    )
    return token, snapshot


def bare_runtime(store):
    runtime = Runtime.__new__(Runtime)
    runtime.store = store
    runtime._pattern_held_tokens = set()
    runtime._chain_paper_execution = {"min_pool_liquidity_usd": 1000.0}
    runtime._paper_quote_rejections = lambda *args: []
    return runtime


def test_remember_keeps_first_120_seconds_then_rotates_quiet_early_candidate(monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: clock[0])
    store = LeaseStore()
    runtime = bare_runtime(store)
    runtime._pattern_protection_ready = True
    old = {index: quote(clock[0], index, age=700) for index in range(1, 11)}
    runtime._remember_pattern_quotes(old)
    assert all(item["min_observe_until"] == clock[0] + timedelta(seconds=120)
               for item in runtime._pattern_watch.values())

    newcomer = quote(clock[0], 99, age=100)
    runtime._remember_pattern_quotes({99: newcomer})
    assert newcomer[0].token_id not in runtime._pattern_watch

    clock[0] += timedelta(seconds=121)
    newcomer = quote(clock[0], 99, age=100)
    runtime._remember_pattern_quotes({99: newcomer})
    assert newcomer[0].token_id in runtime._pattern_watch
    assert len(runtime._pattern_watch) == 10
    assert runtime._pattern_watch_replacements == 1


def test_held_and_pending_expired_watch_identity_is_preserved(monkeypatch):
    now = utcnow()
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: now)
    store = LeaseStore()
    runtime = bare_runtime(store)
    held_token, held_quote = quote(now, 1)
    pending_token, pending_quote = quote(now, 2)
    runtime._pattern_held_tokens = {held_token.token_id}
    store._market_entry_pending_tokens.add(pending_token.token_id)
    runtime._pattern_watch = {
        held_token.token_id: {"token": held_token, "bucket": "early", "quote": held_quote,
                              "pair_address": held_quote.raw["pair"]["pairAddress"], "expires_at": now - timedelta(seconds=1)},
        pending_token.token_id: {"token": pending_token, "bucket": "early", "quote": pending_quote,
                                 "pair_address": pending_quote.raw["pair"]["pairAddress"], "expires_at": now - timedelta(seconds=1)},
    }
    runtime._remember_pattern_quotes({})
    assert set(runtime._pattern_watch) == {held_token.token_id, pending_token.token_id}
    assert runtime._pattern_watch[held_token.token_id]["expires_at"] == now - timedelta(seconds=1)
    assert runtime._pattern_watch[pending_token.token_id]["expires_at"] > now


def test_observer_records_phase_once_without_new_request_and_restores_quote_free_lease(monkeypatch):
    now = utcnow()
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: now)
    store = LeaseStore()
    runtime = bare_runtime(store)
    token, snapshot = quote(now, 7)
    pool = snapshot.raw["pair"]["pairAddress"]
    runtime._rank_no_ca_events = lambda: None
    runtime._dex_quote_low_priority_available = lambda: False
    requested = []

    async def no_request(*args, **kwargs):
        requested.append((args, kwargs))
        return {}

    runtime._dex_batch_quote = no_request
    idle = asyncio.Event()
    idle.set()
    runtime._chain_meme_active_idle = lambda: idle
    store._trajectory144 = SimpleNamespace(pools={(token.token_id, pool): {
        "phase": "impulse", "impulse_at": iso(now),
    }})
    runtime._remember_pattern_quotes({token.token_id: (token, snapshot)})
    asyncio.run(runtime.chain_meme_pattern_observer_once())

    assert requested == []
    assert store.observed == 1
    lease = runtime._pattern_watch[token.token_id]
    assert lease["phase"] == "impulse"
    assert lease["min_observe_until"] == now + timedelta(seconds=300)
    saved = store.kv["chain-meme-pattern-watch:leases145"]
    assert "quote" not in saved["leases"][0]
    assert store.kv["coverage145:status"]["opportunities"][0]["frame_count"] == 1

    restored = bare_runtime(store)
    restored._remember_pattern_quotes({})
    recovered = restored._pattern_watch[token.token_id]
    assert recovered["quote"] is None
    assert recovered["min_observe_until"] == now + timedelta(seconds=300)
