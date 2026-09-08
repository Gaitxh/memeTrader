import asyncio
import json
from datetime import timedelta

import pytest

from memetrader.early_impulse import impulse_policies, impulse_signal, evaluate_impulse_probation
from memetrader.models import TokenCandidate, utcnow
from memetrader.runner_capture import runner_policies, runner_signal, post_signal_compatible
from memetrader.runtime import Runtime, initial_config
from test_resource_bound_store import setup_store
from test_runner_capture import frame, runner_quote, PAIR


def test_opportunity_entry_is_distinct_and_uses_only_available_fields():
    start = utcnow()
    f = frame(start + timedelta(seconds=1), buys=80, sells=120, pc5=10, volume=100)
    f.update(volume_h1=None, buys_h1=None, sells_h1=None)
    p = impulse_policies()[0]
    passed, _, evidence = impulse_signal([f], p, decision_at=f['recorded_at'], activated_at=start)
    assert passed
    assert not runner_signal([f], runner_policies()[0], decision_at=f['recorded_at'], activated_at=start)[0]
    later = {**f, 'observed_at': (start + timedelta(seconds=2)).isoformat(), 'price': 1.05}
    assert post_signal_compatible(later, evidence, p, decision_at=later['observed_at'])
    assert not post_signal_compatible({**later, 'upstream_provider': 'other'}, evidence, p,
                                     decision_at=later['observed_at'])


@pytest.mark.parametrize('change', [
    {'ingested_at': '2099-01-01T00:00:00Z'}, {'price': float('nan')},
    {'liquidity': 4999}, {'pool_age_seconds': 901}, {'buys': -1}, {'price_change_m5': None},
])
def test_entry_rejects_future_missing_or_invalid_evidence(change):
    start = utcnow()
    f = frame(start + timedelta(seconds=1), buys=100, sells=100)
    f.update(change)
    assert not impulse_signal([f], impulse_policies()[0], decision_at=f['recorded_at'], activated_at=start)[0]


def probation_sequence(changes, *, high=5.1):
    start = utcnow()
    position = {'token_id': 'solana:RunnerFixture', 'pair_address': PAIR,
                'opened_at': start.isoformat(), 'stake_usd': 5., 'highest_economic_value_usd': high}
    state = {}
    output = []
    for seconds, change in changes:
        at = start + timedelta(seconds=seconds)
        f = {'frame_id': str(seconds), 'token_id': position['token_id'], 'pair_address': PAIR,
             'original_pool': True, 'provider': 'dexscreener', 'observed_at': at.isoformat(),
             'recorded_at': at.isoformat(), 'price_usd': 1., 'economic_value_usd': 4.8,
             'buys': 100, 'sells': 100, 'boundary_at': None, **change}
        result = evaluate_impulse_probation(position, f, state, now=at,
                                            policy=impulse_policies()[2]['capital_exit_policy'])
        state = json.loads(json.dumps(result[2]))  # persisted state survives process replacement
        output.append(result)
    return output


def test_probation_one_causal_checkpoint_and_latched_decision():
    out = probation_sequence([(300, {}), (600, {'price_usd': .97, 'buys': 80, 'sells': 80}),
                              (610, {'price_usd': .95, 'buys': 50, 'sells': 50})])
    assert out[1][0:2] == ('SELL', 'impulse_probation_failed_renewal')
    assert out[1][3]['required_fill'] == 'next_original_pool_frame'
    assert out[2][0] == 'WAIT'


@pytest.mark.parametrize('changes,high', [
    ([(300, {}), (600, {'price_usd': .97, 'buys': 80, 'sells': 80})], 6.5),
    ([(300, {}), (600, {'economic_value_usd': 5.1})], 5.1),
    ([(300, {}), (600, {'price_usd': .97, 'buys': 80, 'sells': 80, 'provider': 'other'})], 5.1),
    ([(300, {}), (600, {'price_usd': .97, 'buys': 80, 'sells': 80, 'boundary_at': 'gap'})], 5.1),
    ([(331, {}), (600, {'price_usd': .97, 'buys': 80, 'sells': 80})], 5.1),
    ([(300, {}), (631, {'price_usd': .97, 'buys': 80, 'sells': 80})], 5.1),
])
def test_probation_cannot_retrofit_missed_or_incompatible_checkpoint(changes, high):
    out = probation_sequence(changes, high=high)
    assert all(x[0] == 'WAIT' for x in out)
    assert out[-1][2]['review_done']


def test_startup_registers_three_arms_at_one_actual_frontier(tmp_path):
    async def scenario():
        config = initial_config()
        config.update(database='db.sqlite3', chain_meme_trader_only_enabled=True)
        config['bridge']['enabled'] = False
        runtime = Runtime(config, tmp_path)
        rows = runtime.store.db.execute("SELECT * FROM chain_meme_trader_policy_additions "
                                        "WHERE arm_id IN (?,?,?)", [p['arm_id'] for p in impulse_policies()]).fetchall()
        assert len(rows) == 3
        assert len({(r['activated_at'], r['activation_snapshot_id'], r['activation_evaluation_id']) for r in rows}) == 1
        assert runtime.store.register_chain_meme_early_impulse() == 0
        assert runtime.store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_policy_additions "
                                        "WHERE arm_id LIKE 'early_impulse_profit_lock_%'").fetchone()[0] == 2
        assert runtime.store.register_chain_meme_impulse_profit_lock() == 0
        await runtime.close()
    asyncio.run(scenario())


def test_same_fill_independent_exits_and_next_observation_costed_accounting(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original = store._chain_meme_trader_registration(version)['definition_json']
    funding = [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_paper_funding_activations')]
    assert store.register_chain_meme_early_impulse() == 3
    token = TokenCandidate('solana', 'RunnerFixture', 'Impulse', created_at=clock[0]-timedelta(minutes=5))
    created = int(token.created_at.timestamp()*1000)

    def quote(at, price, count):
        q = runner_quote(token, PAIR, created, at, price=price)
        q.buys_5m = q.sells_5m = count // 2
        q.raw['pair']['txns']['m5'] = {'buys': count//2, 'sells': count//2}
        return q

    for i in range(2):
        clock[0] += timedelta(seconds=16)
        assert store.observe_chain_meme_pattern(token, quote(clock[0], 1., 200), recorded_at=clock[0]) == (0 if i == 0 else 3)
    rows = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'early_impulse_%'").fetchall()
    assert len(rows) == 3 and len({r['source_entry_fill_id'] for r in rows}) == 1
    assert all(r['paper_quantity_tokens'] == pytest.approx(5/1.04) for r in rows)
    opened = clock[0]

    def mark(seconds, price, count):
        clock[0] = opened + timedelta(seconds=seconds)
        store.upsert_chain_meme_trader_market_mark(token, quote(clock[0], price, count), recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[token.token_id])

    def positions():
        return {r['arm_id']: r for r in store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'early_impulse_%'")}

    mark(300, 1.04, 400)
    mark(600, 1.00, 300)
    assert all(r['status'] == 'open' for r in positions().values())  # signal is not its own sell fill
    mark(601, .99, 300)
    p = positions()['early_impulse_probation_60m_v1']
    assert p['status'] == 'closed' and p['close_reason'].startswith('impulse_probation_failed_renewal')
    assert p['realized_pnl_usd'] == pytest.approx(5/1.04*.99*.96 - 5)
    mark(901, 1.00, 300)
    mark(902, 1.00, 300)
    assert positions()['early_impulse_control_15m_v1']['status'] == 'closed'
    assert positions()['early_impulse_trailing_60m_v1']['status'] == 'open'
    mark(3601, 1.00, 300)
    mark(3602, 1.00, 300)
    assert positions()['early_impulse_trailing_60m_v1']['status'] == 'closed'
    assert store._chain_meme_trader_registration(version)['definition_json'] == original
    assert [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_paper_funding_activations')] == funding
    store.close()
