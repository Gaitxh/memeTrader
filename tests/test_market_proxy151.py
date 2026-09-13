from copy import deepcopy
from datetime import timedelta
import json

from memetrader import alpha149
from memetrader.market_proxy151 import SPECS, flags, policy
from memetrader.models import iso
from test_resource_bound_store import setup_store


def test_proxy_reaches_without_wallet_fields_and_keeps_old_flags():
    f = dict(current=dict(price_usd=1, liquidity_usd=5000, volume_5m_usd=130,
                         buys_5m=80, sells_5m=40),
             prev=dict(price_usd=1, liquidity_usd=5000, volume_5m_usd=100,
                       buys_5m=60, sells_5m=40), buy_count_share=2/3)
    assert all(flags(f).values())
    old = alpha149._pre_proxy151_mechanisms(f)
    new = alpha149.mechanisms(f)
    assert all(new[k] == v for k, v in old.items() if k not in flags(f))
    assert not new.get('participant_growth') and not new.get('participant_breadth')
    for field in ('liquidity_usd',):
        missing = deepcopy(f); missing['current'][field] = None
        assert not any(flags(missing).values())
    missing = deepcopy(f); missing['prev']['buys_5m'] = None
    assert not flags(missing)['trade_activity_growth151']


def test_actual_engine_emits_available_data_proxy(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    engine = alpha149.Engine(clock[0])
    for count in (60, 80):
        clock[0] += timedelta(seconds=16)
        at = iso(clock[0])
        row = dict(token_id='solana:Proxy151', pair_address='Pool', chain='solana',
            provider='dexscreener', price_usd=1, liquidity_usd=5000,
            volume_5m_usd=count * 10, buys_5m=count, sells_5m=40,
            pool_age_seconds=600, observed_at=at, recorded_at=at, ingested_at=at)
        assert engine.accept(row, clock[0])
    signals = engine.signals_for(row['token_id'], 'Pool', clock[0])
    assert set(SPECS).issubset(signals)
    assert 'alpha149_participant_growth_v1' not in signals
    store.close()


def test_registration_preserves_parent_cash_controls_and_exit_contract(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    sources = {p['arm_id']: p for p in alpha149.policies({})}
    for _, _, parent in SPECS.values():
        store.append_chain_meme_trader_policy(sources[parent], activated_at=clock[0])
    before = {r['arm_id']: r['policy_json'] for r in store.db.execute(
        'SELECT arm_id,policy_json FROM chain_meme_trader_policy_additions')}
    assert store.register_chain_meme_market_proxy151_experiments() == 2
    assert store.register_chain_meme_market_proxy151_experiments() == 0
    after = {r['arm_id']: r['policy_json'] for r in store.db.execute(
        'SELECT arm_id,policy_json FROM chain_meme_trader_policy_additions')}
    assert all(after[k] == v for k, v in before.items())
    for arm, (_, _, parent) in SPECS.items():
        child, base = json.loads(after[arm]), json.loads(before[parent])
        for key in ('take_profit', 'hard_stop_return', 'trailing_drawdown', 'max_hold_minutes'):
            assert child.get(key) == base.get(key)
        assert child['entry_filter']['direction'] == arm
        assert child['feature_contract'] == 'market-proxy/151-v1'
    store.close()
