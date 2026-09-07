from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.store import Store
from test_l0_store import _snapshot


@pytest.mark.parametrize('chain', ['solana', 'bsc', 'robinhood'])
def test_old_cohort_and_sell_require_observation_after_decision(tmp_path, monkeypatch, chain):
    clock = [utcnow()]
    monkeypatch.setattr('memetrader.store.utcnow', lambda: clock[0])
    monkeypatch.setattr('memetrader.models.utcnow', lambda: clock[0])
    store = Store(tmp_path / 'timing.sqlite3', initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_cohort_experiments()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    definition_before = store._chain_meme_trader_registration(version)['definition_json']
    base = clock[0]
    token = TokenCandidate(chain, str(Pubkey.new_unique()) if chain == 'solana' else '0x'+'12'*20, 'Timing', 'T')
    pair = str(Pubkey.new_unique()) if chain == 'solana' else '0x'+'ab'*20
    arm = 'clone_liquidity_leader_v1'
    signal_at = base + timedelta(seconds=3)
    clock[0] = base + timedelta(seconds=5)
    signal = {arm: {'episode_id': 'e1', 'decision_key': 'e1|'+arm,
        'selected': {'token_id': token.token_id, 'pair_address': pair},
        'observed_at': iso(signal_at), 'recorded_at': iso(clock[0]), 'decision_evidence': {}}}
    assert store.observe_chain_meme_pattern(token, _snapshot(token, pair, signal_at),
        recorded_at=clock[0], cohort_signals=signal) == 0
    before = tuple(store.db.execute('SELECT * FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 1').fetchone())
    clock[0] = base + timedelta(seconds=7)
    assert store.observe_chain_meme_pattern(token, _snapshot(token, pair, base+timedelta(seconds=4)),
        recorded_at=clock[0], cohort_signals={}) == 0
    assert tuple(store.db.execute('SELECT * FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 1').fetchone()) == before
    clock[0] = base + timedelta(seconds=8)
    assert store.observe_chain_meme_pattern(token, _snapshot(token, pair, clock[0]),
        recorded_at=clock[0], cohort_signals={}) == 1

    def mark(observed_seconds, received_seconds):
        clock[0] = base + timedelta(seconds=received_seconds)
        store.upsert_chain_meme_trader_market_mark(token,
            _snapshot(token, pair, base+timedelta(seconds=observed_seconds), price=.5), recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=clock[0])

    mark(10, 12)
    mark(11, 14)  # Received later, observed before the real SELL trigger.
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE side='SELL'").fetchone()[0] == 0
    mark(15, 15)
    sell = store.db.execute("SELECT * FROM chain_meme_trader_trades WHERE side='SELL'").fetchone()
    assert sell is not None
    assert sell['net_cash_flow_usd'] == pytest.approx(5 / 2.08 * .5 * .96)
    assert store._chain_meme_trader_registration(version)['definition_json'] == definition_before
    store.close()
