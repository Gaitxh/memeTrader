import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from memetrader.models import TokenCandidate, iso
from memetrader.runtime import Runtime
from memetrader.runtime_timing import RuntimeTiming
from memetrader.store import Store

T = datetime(2026, 9, 10, 19, 11, 34, tzinfo=timezone.utc)
V = 'held-priority147-test'


def test_real_store_expiry_terminal_pool_pending_and_restart(tmp_path):
    path = tmp_path / 'targets.sqlite3'
    store = Store(path, initial_cash_usd=1000)
    store.db.execute('INSERT INTO chain_meme_trader_registrations VALUES(?,?,0,?)',
                     (V, iso(T), json.dumps({'max_signal_to_execution_start_seconds': 300})))
    # A longer existing deadline must survive the old default120s boundary.
    cases = [('stale', 301, None, None, None), ('reject', 20, 'REJECT', None, None),
             ('expired', 20, 'EXPIRED_SECURITY_OR_NEXT_FRAME', None, None),
             ('closed', 20, None, 'closed', None), ('fresh', 200, None, None, None),
             ('held', 7200, 'REJECT', 'open', None), ('sell', 7200, None, None, 'SELL'),
             ('buy', 7200, None, None, 'BUY'), ('future', -1, None, None, None)]
    for i, (name, age, terminal, position, intent) in enumerate(cases, 1):
        token = TokenCandidate('bsc', f'0x{i:040x}', name)
        at = iso(T - timedelta(seconds=age)); pool = f'0x{i+100:040x}'
        store.upsert_token(token, seen_at=T-timedelta(seconds=age))
        store.db.execute('INSERT INTO chain_meme_trader_v6_cohorts(id,definition_version,token_id,entry_family,'
            'source_snapshot_id,pair_address,decided_at,episode_no,feature_json) VALUES(?,?,?,\'broad_launch\',?,?,?,1,\'{}\')',
            (i, V, token.token_id, i, pool, at))
        store.db.execute('INSERT INTO chain_meme_trader_entry_decisions(definition_version,arm_id,shadow_cohort_id,'
            'token_id,baseline_quote_result_id,decided_at,status,reason) VALUES(?,\'arm\',?,?,0,?,\'admitted\',\'fixture\')',
            (V, i, token.token_id, at))
        if terminal:
            store.db.execute('INSERT INTO chain_meme_cohort_enrollment_claims VALUES(?,?,?,?,?,?)',
                (V, 'arm', name, i, at, terminal))
        if position:
            store.db.execute('INSERT INTO chain_meme_trader_positions(definition_version,arm_id,shadow_cohort_id,token_id,'
                'source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,entry_execution_price_usd,'
                'paper_quantity_tokens,remaining_quantity_tokens,amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,opened_at) '
                'VALUES(?,\'arm\',?,?,?,0,0,1,1.04,1,1,\'1\',\'1\',1.04,1,?,?)',
                (V, i, token.token_id, i, position, at))
        if intent:
            store.db.execute('INSERT INTO chain_meme_trader_order_intents(intent_key,definition_version,execution_mode,arm_id,'
                'shadow_cohort_id,token_id,side,input_mint,output_mint,input_amount_raw,slippage_bps,status,reason,created_at,expires_at) '
                'VALUES(?,?,\'paper\',\'arm\',?,?,?,\'in\',\'out\',\'1\',400,\'retry\',\'fixture\',?,?)',
                (name, V, i, token.token_id, intent, at, iso(T+timedelta(seconds=10))))
    # Unrelated arm's terminal claim must not reject a valid opportunity.
    store.db.execute('INSERT INTO chain_meme_cohort_enrollment_claims VALUES(?,?,?,?,?,?)',
                     (V, 'other', 'other', 5, iso(T), 'REJECT'))
    store.db.commit()
    before = [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_entry_decisions')]
    stats = {}
    rows = store.chain_meme_trader_market_mark_targets(definition_version=V, as_of=T, diagnostics=stats)
    ids = {r['address'] for r in rows}
    assert ids == {f'0x{i:040x}' for i in (5, 6, 7, 8)}
    fresh = next(r for r in rows if r['address'] == f'0x{5:040x}')
    assert fresh['original_entry_pair_addresses'] == f'0x{105:040x}'
    assert stats['actual_open'] == 1 and stats['pending_recent'] == 3
    assert stats['obsolete_filtered'] == 8  # Includes receipts already represented by open/intent.
    rows_at_deadline = store.chain_meme_trader_market_mark_targets(definition_version=V, as_of=T+timedelta(seconds=100))
    assert fresh['token_id'] in {r['token_id'] for r in rows_at_deadline}
    later = store.chain_meme_trader_market_mark_targets(definition_version=V, as_of=T+timedelta(seconds=101))
    assert {r['address'] for r in later} == {f'0x{i:040x}' for i in (6, 7, 9)}
    # A second Store instance/restart obtains exactly the same frozen target set.
    reopened = Store(path, initial_cash_usd=1000)
    assert reopened.chain_meme_trader_market_mark_targets(definition_version=V, as_of=T) == rows
    assert before == [tuple(r) for r in reopened.db.execute('SELECT * FROM chain_meme_trader_entry_decisions')]
    reopened.close(); store.close()


def test_runtime_separates_open_pending_and_preserves_flat_callback():
    async def scenario():
        targets = [{'token_id': 'bsc:held', 'watch_reason': 'OPEN_POSITION,RECENT_DECISION'},
                   {'token_id': 'bsc:fresh', 'watch_reason': 'RECENT_DECISION'},
                   {'token_id': 'bsc:sell', 'watch_reason': 'PENDING_INTENT'}]
        for item in targets:
            item.update(chain='bsc', address=item['token_id'].split(':')[1])
        r = Runtime.__new__(Runtime); r.chain_meme_trader_only = True; r.runtime_timing = RuntimeTiming()
        def selected(**kwargs):
            kwargs['diagnostics'].update(actual_open=1,pending_recent=2,obsolete_filtered=14)
            return targets
        r.store = SimpleNamespace(CHAIN_MEME_TRADER_ACTIVE_VERSION=V,
            chain_meme_trader_market_mark_targets=selected, heartbeat=lambda *a, **kw: None)
        seen = []
        async def refresh(rows, **kwargs): seen.extend(rows); return len(rows)
        r._refresh_chain_meme_market_marks = refresh
        await r.chain_meme_market_marks_once()
        assert r._pattern_held_tokens == {'bsc:held'}
        assert r._pattern_pending_tokens == {'bsc:fresh', 'bsc:sell'}
        assert len(seen) == 3
        assert r.runtime_timing.snapshot()['held_retrieval']['target_supply']['actual_open'] == 1
        idle = asyncio.Event(); idle.set()
        r._chain_meme_active_idle = lambda: idle
        from memetrader.models import TokenSnapshot, utcnow
        async def quoted(chain, addresses, **kwargs):
            now = utcnow()
            return {f'{chain}:{a}': (TokenCandidate(chain,a,a), TokenSnapshot(
                chain,a,1,5000,None,500,4,2,observed_at=now,ingested_at=now,
                provider='dexscreener',raw={'pair':{'pairAddress':'pool-'+a}})) for a in addresses}
        callbacks = []
        r._dex_batch_quote = quoted; r._paper_quote_rejections = lambda *args: []
        r.store.apply_chain_meme_trader_market_mark_batch = lambda outcomes, **kw: len(outcomes)
        r.store.observe_flat_compression_breakout_market_batch = lambda outcomes, **kw: callbacks.extend(outcomes)
        assert await Runtime._refresh_chain_meme_market_marks(r,targets,
            heartbeat_name='low-test',high_priority=False,observe_flat_breakout=True) == 3
        assert {o.get('target_token_id') or o.get('token_id') for o in callbacks} == r._market_priority_tokens
    asyncio.run(scenario())


def test_low_priority_different_original_pool_is_not_dropped():
    # Same actual Runtime boundary as the Lead's carried-period regression.
    async def scenario():
        r = Runtime.__new__(Runtime)
        r._market_priority_tokens = {'bsc:same'}
        idle = asyncio.Event(); idle.set()
        r._chain_meme_active_idle = lambda: idle
        calls = []
        async def fetch(chain, addresses, **kwargs):
            calls.append((chain, addresses))
            raise RuntimeError('test-no-network')
        r._dex_batch_quote = fetch
        r._queue_market_pool_gap = lambda *a, **kw: None
        r.store = SimpleNamespace(heartbeat=lambda *a, **kw: None,
            apply_chain_meme_trader_market_mark_batch=lambda *a, **kw: None)
        await r._refresh_chain_meme_market_marks(
            [{'token_id': 'bsc:same', 'chain': 'bsc', 'address': 'same',
              'entry_pair_addresses': 'pool-carried'}],
            heartbeat_name='carried-test', high_priority=False,
            evaluate_versions=['old-period'])
        assert calls == [('bsc', ['same'])]
    asyncio.run(scenario())


def test_pending_is_protected_without_held_exemption(monkeypatch):
    from memetrader.models import TokenSnapshot
    r = Runtime.__new__(Runtime)
    clock = [T]
    monkeypatch.setattr('memetrader.runtime.utcnow', lambda: clock[0])
    r.store = SimpleNamespace(get_kv=lambda key, default=None: default)
    r._pattern_held_tokens = set(); r._pattern_pending_tokens = set()
    r._pattern_protection_ready = True; r._paper_quote_rejections = lambda *a: []
    token = TokenCandidate('bsc', '0x'+'1'*40, 'pending')
    snap = TokenSnapshot('bsc', token.address, 1, 5000, None, 500, 4, 2,
        observed_at=T, ingested_at=T, raw={'pair': {'pairAddress': '0x'+'2'*40,
        'pairCreatedAt': (T-timedelta(days=1)).timestamp()*1000}})
    r._remember_pattern_quotes({token.token_id: (token, snap)})
    r._pattern_watch[token.token_id]['expires_at'] = T
    r._pattern_pending_tokens = {token.token_id}
    clock[0] += timedelta(seconds=1); r._remember_pattern_quotes({})
    assert token.token_id in r._pattern_watch and token.token_id in r._lease145_protected
    assert token.token_id not in r._pattern_held_tokens
    assert r._pattern_watch_nonheld_by_chain_bucket['bsc']['mature'] == 1
