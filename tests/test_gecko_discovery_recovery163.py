import asyncio
from types import SimpleNamespace

from memetrader import runtime as runtime_module
from memetrader.collectors import GeckoLowPriorityDeferred


class _Store:
    CHAIN_MEME_TRADER_ACTIVE_VERSION = "test"

    def __init__(self):
        self.finished = []
        self.heartbeats = []

    def start_token_discovery_round(self, **_kwargs):
        return 7

    def finish_token_discovery_round(self, round_id, **kwargs):
        self.finished.append((round_id, kwargs))

    def heartbeat(self, source, **kwargs):
        self.heartbeats.append((source, kwargs))


def test_multichain_gecko_recovery_rotates_one_chain_per_cycle():
    runtime = runtime_module.Runtime.__new__(runtime_module.Runtime)
    runtime.config = {
        "sources": {
            "multichain_meme_data": {
                "chains": ["solana", "bsc", "robinhood"],
                "geckoterminal_discovery_enabled": True,
            }
        }
    }
    runtime.chain_meme_trader_only = True
    runtime.store = _Store()
    seen = []

    async def gecko(chain):
        seen.append(chain)

    async def dex(**_kwargs):
        return None

    runtime._poll_gecko_network = gecko
    runtime.poll_dexscreener_discovery_once = dex
    for _ in range(4):
        asyncio.run(runtime.poll_multichain_meme_data_once())

    assert seen == ["solana", "bsc", "robinhood", "solana"]


def test_gecko_capacity_deferral_is_interrupted_not_source_error(monkeypatch):
    runtime = runtime_module.Runtime.__new__(runtime_module.Runtime)
    runtime.store = _Store()
    runtime.http = SimpleNamespace(_gecko_start_waiters={True: []})
    runtime._critical_onchain_exit_event = asyncio.Event()
    runtime._gecko_pool_backoff_until = 0.0
    notified = []
    runtime._notify_source_error = lambda source, exc: notified.append((source, exc))

    class DeferredCollector:
        def __init__(self, _http, _network):
            pass

        async def poll(self):
            raise GeckoLowPriorityDeferred()

    monkeypatch.setattr(runtime_module, "GeckoNewPoolsCollector", DeferredCollector)
    asyncio.run(runtime._poll_gecko_network("bsc"))

    assert runtime.store.finished == [(7, {"status": "interrupted"})]
    assert notified == []
