import json
from datetime import timedelta

import pytest

from memetrader.models import TokenCandidate, utcnow
from memetrader.runner_capture import runner_policies, runner_signal, ultra_early_policies
from test_resource_bound_store import setup_store
from test_runner_capture import PAIR, frame, runner_quote


def test_age_is_signal_pool_age_and_old_runner_contract_is_unchanged():
    before = json.dumps(runner_policies(), sort_keys=True)
    control, lock = ultra_early_policies()
    assert control['entry_filter'] == {**runner_policies()[1]['entry_filter'], 'maximum_pair_age_seconds': 180}
    assert control['entry_filter'] == lock['entry_filter']
    identity = {'arm_id', 'canonical_id', 'name', 'description', 'take_profit'}
    assert {k:v for k,v in control.items() if k not in identity} == {k:v for k,v in lock.items() if k not in identity}
    assert lock['take_profit'] == [{'return':.40, 'fraction_of_remaining':.50},
                                   {'return':.80, 'fraction_of_remaining':1.0}]
    at = utcnow()
    for seconds in (150, 180, 181, 300):
        f = frame(at+timedelta(seconds=1))
        f.update(pool_age_seconds=seconds, token_age_seconds=seconds)
        assert runner_signal([f], control, decision_at=f['recorded_at'], activated_at=at)[0] == (seconds <= 180)
        assert runner_signal([f], runner_policies()[1], decision_at=f['recorded_at'], activated_at=at)[0]
    assert json.dumps(runner_policies(), sort_keys=True) == before


def test_new_frontier_same_fill_two_tiers_whole_value_and_ledger(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    store.register_chain_meme_runner_capture()
    old = [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_policy_additions')]
    funding = [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_paper_funding_activations')]
    token = TokenCandidate('solana', 'RunnerFixture', 'FastRunner', created_at=clock[0]-timedelta(seconds=60))
    created = int(token.created_at.timestamp()*1000)
    control, lock = [p['arm_id'] for p in ultra_early_policies()]

    def positions():
        return {r['arm_id']:r for r in store.db.execute(
            'SELECT * FROM chain_meme_trader_positions WHERE arm_id IN (?,?)', (control,lock))}

    clock[0] += timedelta(seconds=16)
    store.observe_chain_meme_pattern(token, runner_quote(token,PAIR,created,clock[0]), recorded_at=clock[0])
    clock[0] += timedelta(seconds=16)
    assert store.register_chain_meme_ultra_early_runner() == 2
    additions = store.db.execute('SELECT * FROM chain_meme_trader_policy_additions WHERE arm_id IN (?,?)', (control,lock)).fetchall()
    assert len({(r['activated_at'],r['activation_snapshot_id'],r['activation_evaluation_id']) for r in additions}) == 1
    assert store.register_chain_meme_ultra_early_runner() == 0
    for i in range(2):
        clock[0] += timedelta(seconds=16)
        store.observe_chain_meme_pattern(token, runner_quote(token,PAIR,created,clock[0]), recorded_at=clock[0])
        assert len(positions()) == (0 if i == 0 else 2)
    assert len({r['source_entry_fill_id'] for r in positions().values()}) == 1
    assert all(r['source_entry_fill_id'] is not None for r in positions().values())
    assert all(r['stake_usd'] == 5 for r in positions().values())
    opened = clock[0]

    def mark(seconds, price):
        clock[0] = opened+timedelta(seconds=seconds)
        q = runner_quote(token,PAIR,created,clock[0],price=price)
        store.upsert_chain_meme_trader_market_mark(token,q,recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[token.token_id])

    quantity = 5/1.04
    mark(10,1.52)
    assert positions()[lock]['remaining_quantity_tokens'] == pytest.approx(quantity)
    mark(11,1.52)
    assert positions()[lock]['remaining_quantity_tokens'] == pytest.approx(quantity/2)
    assert positions()[lock]['allocated_cost_usd'] == pytest.approx(2.5)
    mark(20,2.0)  # Unsold full-position return exceeds 80%, but realized+remaining does not.
    assert positions()[lock]['pending_mark_id'] is None
    mark(30,2.4)
    assert positions()[lock]['status'] == 'open' and positions()[lock]['pending_mark_id'] is not None
    mark(31,2.3)
    candidate = positions()[lock]
    assert candidate['status'] == 'closed' and candidate['next_tp_index'] == 2
    assert positions()[control]['status'] == 'open'
    assert candidate['realized_pnl_usd'] == pytest.approx(quantity/2*(1.52+2.3)*.96-5)
    mark(901,2.3)
    mark(902,2.3)
    for arm, r in positions().items():
        assert r['status'] == 'closed' and r['allocated_cost_usd'] == pytest.approx(5)
        cash = store.db.execute('SELECT SUM(net_cash_flow_usd) FROM chain_meme_trader_trades WHERE arm_id=?',(arm,)).fetchone()[0]
        assert cash == pytest.approx(r['realized_pnl_usd'])
    assert [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_policy_additions WHERE arm_id NOT IN (?,?)',(control,lock))] == old
    assert [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_paper_funding_activations')] == funding
    store.close()
