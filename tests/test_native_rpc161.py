"""Transport failures retain exact identity but never become chain observations."""
import asyncio
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from memetrader.collectors import SolanaHeldAccountCollector
from memetrader.native_execution import apply_curve_quote, buy, targets
from memetrader.runtime import Runtime
from test_native_execution138 import setup


@pytest.mark.parametrize('failure', ['http429', 'timeout', 'invalid_bundle'])
def test_failed_curve_read_preserves_identity_and_ledger(tmp_path, monkeypatch, failure):
    store, clock, plan = setup(tmp_path, monkeypatch)
    assert buy(store, plan, now=clock[0]) == 'BOUGHT'
    target = targets(store)[0]
    before = [tuple(row) for row in store.db.execute('SELECT * FROM chain_meme_trader_trades')]
    state_before = target['state_json']
    clock[0] += timedelta(seconds=1)

    def reply(request):
        if failure == 'timeout':
            raise httpx.ReadTimeout('bounded test timeout', request=request)
        if failure == 'http429':
            return httpx.Response(429)
        return httpx.Response(200, json={'result': {'context': {'slot': 1}, 'value': []}})

    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
            collector = SolanaHeldAccountCollector.__new__(SolanaHeldAccountCollector)
            collector.http, collector.rpc_url = http, 'https://rpc.test'
            collector.max_multiple_accounts = 10
            return (await collector.bonding_curve_quotes([dict(
                token_id=target['token_id'], base_mint=plan['execution_frame']['base_mint'],
                curve_address=target['curve'], remaining_amount_raw=target['amount_raw'],
            )]))[0]

    quote = asyncio.run(collect())
    assert quote['pool_address'] == target['curve']
    assert quote['context_slot'] == 0 and quote['status'] == 'LOCAL_UNKNOWN_RPC'
    assert quote['reason'] == {'http429': 'HTTPStatusError:429', 'timeout': 'ReadTimeout',
                               'invalid_bundle': 'ValueError'}[failure]
    assert apply_curve_quote(store, target, quote, None, None, now=clock[0]) == 'UNKNOWN_RPC'
    assert targets(store)[0]['state_json'] == state_before
    assert targets(store)[0]['amount_raw'] == target['amount_raw']
    assert [tuple(row) for row in store.db.execute('SELECT * FROM chain_meme_trader_trades')] == before
    for field in ('token_id', 'pool_address', 'remaining_amount_raw'):
        with pytest.raises(ValueError, match='native_exit_identity_amount'):
            apply_curve_quote(store, target, dict(quote, **{field: 'wrong'}), None, None, now=clock[0])
    store.close()


def test_classified_rpc_failure_is_not_a_successful_heartbeat(monkeypatch):
    runtime = Runtime.__new__(Runtime)
    heartbeats = []
    runtime.store = SimpleNamespace(heartbeat=lambda *a, **kw: heartbeats.append(kw))
    monkeypatch.setattr('memetrader.native_execution.targets', lambda store: [{}])
    monkeypatch.setattr('memetrader.native_execution.ensure_time_exit', lambda *a: None)
    async def failed(target):
        return 'UNKNOWN_RPC'
    runtime._native_held_once = failed
    asyncio.run(runtime.chain_meme_native_held_once())
    assert heartbeats == [{'item': False, 'error': 'UNKNOWN_RPC'}]
