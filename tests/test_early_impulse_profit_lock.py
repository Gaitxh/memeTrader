import json
from datetime import timedelta

import pytest

from memetrader.early_impulse import impulse_policies, profit_lock_policies
from memetrader.models import TokenCandidate
from test_resource_bound_store import setup_store
from test_runner_capture import PAIR, runner_quote


CONTROL, CANDIDATE = [p['arm_id'] for p in profit_lock_policies()]


def test_profit_lock_changes_only_one_exit_tier_and_owns_its_entry_group():
    old = json.dumps(impulse_policies(), sort_keys=True)
    control, candidate = profit_lock_policies()
    identity = {'arm_id', 'canonical_id', 'name', 'description', 'evidence_review',
                'paired_entry_group', 'paired_entry_size'}
    assert {k: v for k, v in control.items() if k not in identity} == {
        k: v for k, v in impulse_policies()[1].items() if k not in identity}
    assert {k: v for k, v in candidate.items() if k not in identity | {'take_profit'}} == {
        k: v for k, v in control.items() if k not in identity | {'take_profit'}}
    assert candidate['take_profit'] == [{'return': .40, 'fraction_of_remaining': .50}]
    assert control['paired_entry_group'] == candidate['paired_entry_group']
    assert control['paired_entry_group'] != impulse_policies()[1]['paired_entry_group']
    assert control['paired_entry_size'] == candidate['paired_entry_size'] == 2
    assert control['entry_filter']['max_concurrent_positions'] == 4
    assert json.dumps(impulse_policies(), sort_keys=True) == old


@pytest.fixture
def profit_pair(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    store.register_chain_meme_early_impulse()
    old_rows = [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_policy_additions')]
    funding = [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_paper_funding_activations')]
    token = TokenCandidate('solana', 'RunnerFixture', 'Impulse', created_at=clock[0]-timedelta(minutes=5))
    created = int(token.created_at.timestamp()*1000)

    def quote(at, price, pair=PAIR):
        q = runner_quote(token, pair, created, at, price=price)
        q.buys_5m = q.sells_5m = 100
        q.raw['pair']['txns']['m5'] = {'buys': 100, 'sells': 100}
        return q

    def positions():
        return {r['arm_id']: r for r in store.db.execute(
            'SELECT * FROM chain_meme_trader_positions WHERE arm_id IN (?,?)', (CONTROL, CANDIDATE))}

    # A pre-deployment opportunity must not become the new pair's entry signal.
    clock[0] += timedelta(seconds=16)
    store.observe_chain_meme_pattern(token, quote(clock[0], 1.), recorded_at=clock[0])
    clock[0] += timedelta(seconds=16)
    assert store.register_chain_meme_impulse_profit_lock() == 2
    assert store.register_chain_meme_impulse_profit_lock() == 0
    new_rows = store.db.execute('SELECT * FROM chain_meme_trader_policy_additions '
                               'WHERE arm_id IN (?,?)', (CONTROL, CANDIDATE)).fetchall()
    assert len(new_rows) == 2
    assert len({(r['activated_at'], r['activation_snapshot_id'], r['activation_evaluation_id'])
                for r in new_rows}) == 1
    for i in range(2):
        clock[0] += timedelta(seconds=16)
        store.observe_chain_meme_pattern(token, quote(clock[0], 1.), recorded_at=clock[0])
        assert len(positions()) == (0 if i == 0 else 2)
    rows = positions().values()
    assert len({r['source_entry_fill_id'] for r in rows}) == 1
    assert all(r['stake_usd'] == 5 and r['remaining_quantity_tokens'] == pytest.approx(5/1.04) for r in rows)
    opened = clock[0]

    def mark(seconds, price, *, observed_seconds=None, pair=PAIR):
        clock[0] = opened + timedelta(seconds=seconds)
        observed = opened + timedelta(seconds=observed_seconds if observed_seconds is not None else seconds)
        store.upsert_chain_meme_trader_market_mark(token, quote(observed, price, pair), recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[token.token_id])

    yield store, positions, mark
    assert [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_policy_additions '
                                               'WHERE arm_id NOT IN (?,?)', (CONTROL, CANDIDATE))] == old_rows
    assert [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_paper_funding_activations')] == funding
    store.close()


def test_costed_trigger_later_half_fill_once_and_remainder_ledger(profit_pair):
    store, positions, mark = profit_pair
    quantity = 5/1.04
    mark(10, 1.50)  # Nominal +50%, but only +38.46% after both slippages.
    assert positions()[CANDIDATE]['pending_mark_id'] is None
    mark(20, 1.52)  # Cost-adjusted +40.3077%.
    assert positions()[CANDIDATE]['pending_mark_id'] is not None
    assert positions()[CONTROL]['pending_mark_id'] is None
    assert positions()[CANDIDATE]['remaining_quantity_tokens'] == pytest.approx(quantity)
    mark(21, 1.52, observed_seconds=20)  # Re-recording the trigger is not a later observation.
    assert positions()[CANDIDATE]['remaining_quantity_tokens'] == pytest.approx(quantity)
    mark(22, 1.50)
    candidate = positions()[CANDIDATE]
    assert candidate['status'] == 'open' and candidate['next_tp_index'] == 1
    assert candidate['remaining_quantity_tokens'] == pytest.approx(quantity/2)
    assert candidate['allocated_cost_usd'] == pytest.approx(2.5)
    assert candidate['realized_pnl_usd'] == pytest.approx(quantity/2*1.5*.96 - 2.5)
    assert positions()[CONTROL]['remaining_quantity_tokens'] == pytest.approx(quantity)
    mark(30, 1.60)
    mark(31, 1.60)
    assert positions()[CANDIDATE]['remaining_quantity_tokens'] == pytest.approx(quantity/2)
    mark(3601, 1.50)
    assert all(r['status'] == 'open' for r in positions().values())
    mark(3602, 1.45)
    expected = {CONTROL: quantity*1.45*.96-5,
                CANDIDATE: quantity/2*(1.50+1.45)*.96-5}
    for arm, row in positions().items():
        assert row['status'] == 'closed'
        assert row['allocated_cost_usd'] == pytest.approx(5)
        assert row['realized_pnl_usd'] == pytest.approx(expected[arm])
        trades = store.db.execute('SELECT * FROM chain_meme_trader_trades WHERE arm_id=?', (arm,)).fetchall()
        assert sum(t['net_cash_flow_usd'] for t in trades) == pytest.approx(expected[arm])
        assert len([t for t in trades if t['side'] == 'SELL']) == (2 if arm == CANDIDATE else 1)


def test_profit_lock_cannot_fill_other_pool_or_claim_trigger_price_after_gap(profit_pair):
    store, positions, mark = profit_pair
    mark(10, 1.52)
    mark(11, 1.52, pair='OtherPool')
    assert positions()[CANDIDATE]['remaining_quantity_tokens'] == pytest.approx(5/1.04)
    mark(12, .64)
    candidate = positions()[CANDIDATE]
    assert candidate['remaining_quantity_tokens'] == pytest.approx(5/1.04/2)
    assert candidate['realized_pnl_usd'] == pytest.approx(5/1.04/2*.64*.96-2.5)
    sell = store.db.execute("SELECT * FROM chain_meme_trader_trades WHERE arm_id=? AND side='SELL'",
                            (CANDIDATE,)).fetchone()
    assert sell['net_cash_flow_usd'] == pytest.approx(5/1.04/2*.64*.96)
