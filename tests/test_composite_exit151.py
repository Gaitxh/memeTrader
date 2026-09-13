"""Forward-only contract tests for the composite151 exit arm."""
import json
from datetime import timedelta

import pytest

from memetrader.age_rate_revisions import next_frame_minimum_principal_recovery_raw
from memetrader.composite_exit151 import ARM, PARENT, VERSION, evaluate
from memetrader.models import TokenCandidate, iso
from memetrader.paper_execution import sell_terms
from test_resource_bound_store import setup_store


def _position(clock, *, pair="pool"):
    return {
        "token_id": "solana:Composite151Fixture",
        "entry_pair_address": pair,
        "opened_at": iso(clock - timedelta(minutes=6)),
        "stake_usd": 20.0,
        "realized_proceeds_usd": 0.0,
    }


def _mark(clock, sequence, *, pair="pool", price=1.0, liquidity=100.0,
          buys=10, sells=10, observed_delta=0):
    observed = clock + timedelta(seconds=observed_delta)
    return {
        "token_id": "solana:Composite151Fixture", "pair_address": pair,
        "status": "VISIBLE", "sequence": sequence,
        "observed_at": iso(observed), "recorded_at": iso(observed),
        "price": price, "liquidity": liquidity, "buys": buys, "sells": sells,
    }


@pytest.mark.parametrize("mutate", [
    lambda position, mark, now: mark.update(price=None),
    lambda position, mark, now: mark.update(observed_at=iso(now + timedelta(seconds=1)), recorded_at=iso(now + timedelta(seconds=1))),
    lambda position, mark, now: mark.update(observed_at=iso(now - timedelta(seconds=16)), recorded_at=iso(now - timedelta(seconds=16))),
    lambda position, mark, now: mark.update(pair_address="other-original-pool"),
])
def test_composite151_rejects_missing_future_stale_and_non_entry_pool(mutate):
    from memetrader.models import utcnow
    now = utcnow(); position = _position(now); mark = _mark(now, 1)
    mutate(position, mark, now)
    state, evidence = evaluate(position, mark, {}, now)
    assert evidence is None
    assert "confirmation" not in state


def test_composite151_non_entry_pool_cannot_even_seed_restart_state():
    from memetrader.models import utcnow
    now = utcnow(); position = _position(now)
    state, evidence = evaluate(position, _mark(now, 1, pair="other-original-pool"), {}, now)
    assert evidence is None
    assert state == {}


def test_composite151_rejects_repeated_and_invalid_sampling_intervals():
    from memetrader.models import utcnow
    now = utcnow(); position = _position(now)
    state, _ = evaluate(position, _mark(now, 1, price=1.0, buys=20, sells=10, liquidity=200), {}, now)
    state2, evidence = evaluate(position, _mark(now + timedelta(seconds=14), 2, price=.9, buys=10, sells=20, liquidity=100), state, now + timedelta(seconds=14))
    assert evidence is None and state2 == state
    state3, evidence = evaluate(position, _mark(now + timedelta(seconds=15), 1, price=.9, buys=10, sells=20, liquidity=100), state, now + timedelta(seconds=15))
    assert evidence is None and state3 == state
    state4, evidence = evaluate(position, _mark(now + timedelta(seconds=91), 2, price=.9, buys=10, sells=20, liquidity=100), state, now + timedelta(seconds=91))
    assert evidence is None and "confirmation" not in state4


def test_composite151_requires_two_distinct_three_of_four_decay_confirmations_and_roundtrips_json():
    from memetrader.models import utcnow
    now = utcnow(); position = _position(now)
    # First sample is only support; it cannot itself become a confirmation.
    state, evidence = evaluate(position, _mark(now, 1, price=1, buys=20, sells=10, liquidity=200), {}, now)
    assert evidence is None
    state, evidence = evaluate(position, _mark(now + timedelta(seconds=15), 2, price=.9, buys=10, sells=20, liquidity=100), state, now + timedelta(seconds=15))
    assert evidence is None and state["confirmation"]["sequence"] == 2
    restored = json.loads(json.dumps(state))
    state, evidence = evaluate(position, _mark(now + timedelta(seconds=30), 3, price=.8, buys=6, sells=24, liquidity=80), restored, now + timedelta(seconds=30))
    assert evidence is not None
    assert evidence["first"]["sequence"] == 2 and evidence["second"]["sequence"] == 3
    assert sum(value is True for value in evidence["votes"].values()) >= 3
    # Same state/frame after a restart is idempotent; it cannot create a second trigger.
    _, duplicate = evaluate(position, _mark(now + timedelta(seconds=30), 3, price=.8, buys=6, sells=24, liquidity=80), json.loads(json.dumps(state)), now + timedelta(seconds=30))
    assert duplicate is None


def test_composite151_recovery_vote_clears_first_confirmation_and_unknown_never_votes():
    from memetrader.models import utcnow
    now = utcnow(); position = _position(now)
    state, _ = evaluate(position, _mark(now, 1, price=1, buys=20, sells=10, liquidity=200), {}, now)
    state, _ = evaluate(position, _mark(now + timedelta(seconds=15), 2, price=.9, buys=10, sells=20, liquidity=100), state, now + timedelta(seconds=15))
    assert "confirmation" in state
    state, evidence = evaluate(position, _mark(now + timedelta(seconds=30), 3, price=1.0, buys=20, sells=10, liquidity=150), state, now + timedelta(seconds=30))
    assert evidence is None and "confirmation" not in state
    state, evidence = evaluate(position, _mark(now + timedelta(seconds=45), 4, price=.8, buys=None, sells=24, liquidity=80), state, now + timedelta(seconds=45))
    assert evidence is None and "confirmation" not in state


def test_composite151_registration_is_append_only_and_parent_contract_is_unchanged(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original = store._chain_meme_trader_registration(version)["definition_json"]
    # The production registration intentionally clones the already-forwarded
    # moonbag policy addition; install that parent in the otherwise empty fixture.
    from memetrader.alpha149 import policies as alpha149_policies
    source_parent = next(item for item in alpha149_policies({}) if item["arm_id"] == PARENT)
    store.append_chain_meme_trader_policy(source_parent, activated_at=clock[0])
    # The public registration is deliberately idempotent and has its own frontier.
    assert store.register_chain_meme_composite151_experiment() == 1
    assert store.register_chain_meme_composite151_experiment() == 0
    assert store._chain_meme_trader_registration(version)["definition_json"] == original
    child = store.db.execute("SELECT * FROM chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id=?", (version, ARM)).fetchone()
    assert child is not None
    child_policy = json.loads(child["policy_json"])
    parent_row = store.db.execute("SELECT policy_json FROM chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id=?", (version, PARENT)).fetchone()
    parent = json.loads(parent_row["policy_json"])
    expected_filter = {**parent["entry_filter"], "direction": ARM}
    assert child_policy["entry_filter"] == expected_filter
    assert child_policy["take_profit"] == parent["take_profit"]
    assert child_policy["composite_exit151"]["version"] == VERSION
    assert parent.get("composite_exit151") is None
    store.close()


def test_composite151_recovery_sizing_is_strict_partial_net_and_deterministic():
    # This is the exact existing Store helper used again at actual fill; no signal
    # can alter raw quantity, cash, or principal-recovered state before this step.
    definition = {"sell_slippage_bps": 400, "additional_fee_usd_each_fill": 0}
    policy = {"dynamic_principal_recovery": "confirmed_decay151"}
    position = {"stake_usd": 20.0, "realized_proceeds_usd": 0.0,
                "amount_raw": "1000000", "remaining_quantity_tokens": 10.0}
    raw = next_frame_minimum_principal_recovery_raw(position, {"market_price_usd": 3.0}, definition, policy=policy)
    assert raw is not None and 0 < raw < int(position["amount_raw"])
    net = sell_terms(position["remaining_quantity_tokens"] * raw / int(position["amount_raw"]), 3.0, definition)["net_usd"]
    prior_raw = raw - 1
    prior_net = sell_terms(position["remaining_quantity_tokens"] * prior_raw / int(position["amount_raw"]), 3.0, definition)["net_usd"]
    assert net >= 20.0 > prior_net
    assert next_frame_minimum_principal_recovery_raw(position, {"market_price_usd": 3.0}, definition, policy=policy) == raw


def _store_position_for_composite_fill(tmp_path, monkeypatch):
    """One real resource-entry position with only the composite exit added."""
    from copy import deepcopy
    from memetrader.composite_exit151 import CONTRACT
    from memetrader.resource_bound_research import resource_policies
    from test_resource_bound_store import quote

    store, clock = setup_store(tmp_path, monkeypatch)
    parent = next(p for p in resource_policies() if p["arm_id"] == "resource_age_rate_candidate_v1")
    child = deepcopy(parent)
    child.update(arm_id=ARM, canonical_id=ARM, entry_family=ARM,
                 source_arm_ids=[parent["arm_id"]], excess_return_vs_arm=parent["arm_id"],
                 composite_exit151=CONTRACT.copy(), dynamic_principal_recovery="confirmed_decay151",
                 # The test isolates the composite; existing hard/trailing exits must not pre-empt it.
                 hard_stop_return=-.99, trailing_activate_return=99., max_hold_minutes=60.)
    store.append_chain_meme_trader_policy(parent, activated_at=clock[0])
    store.append_chain_meme_trader_policy(child, activated_at=clock[0])
    token = TokenCandidate("solana", "Composite151StoreFixture", "C151")
    created = int((clock[0] - timedelta(minutes=90)).timestamp() * 1000)
    for _ in range(2):
        clock[0] += timedelta(seconds=16)
        store.observe_chain_meme_pattern(token, quote(token, "pool", created, clock[0], age_rate=True), recorded_at=clock[0])
    position = lambda: store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (ARM,)).fetchone()
    assert position() is not None

    def mark(price, buys, sells, liquidity=10000.):
        clock[0] += timedelta(seconds=15)
        snapshot = quote(token, "pool", created, clock[0], price=price, age_rate=True)
        snapshot.buys_5m, snapshot.sells_5m, snapshot.liquidity_usd = buys, sells, liquidity
        store.upsert_chain_meme_trader_market_mark(token, snapshot, recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[token.token_id])
        return position()
    return store, clock, position, mark


def test_composite151_store_trigger_next_frame_fill_conserves_raw_and_survives_restart(tmp_path, monkeypatch):
    store, clock, position, mark = _store_position_for_composite_fill(tmp_path, monkeypatch)
    # Parent support plus two 15-second independent 3-of-4 decay confirmations,
    # after the evaluator's five-minute minimum hold.
    clock[0] += timedelta(minutes=6)
    mark(3.0, 40, 10, 14000)
    mark(2.9, 25, 20, 12000)
    before = mark(2.8, 10, 30, 10000)
    assert before["pending_mark_id"] is not None
    pending = store.db.execute("SELECT * FROM chain_meme_trader_marks WHERE id=?", (before["pending_mark_id"],)).fetchone()
    assert pending["action"] == "PRINCIPAL_RECOVERY" and "confirmed_market_decay_net_recovery151" in pending["reason"]
    initial_raw = int(before["amount_raw"])
    # The next independent original-pool frame, rather than trigger price, owns fill sizing.
    after = mark(2.7, 8, 35, 9000)
    assert after["status"] == "open" and after["principal_recovered"] == 1
    assert 0 < int(after["amount_raw"]) < initial_raw
    filled = store.db.execute("SELECT * FROM chain_meme_trader_marks WHERE id=?", (pending["id"],)).fetchone()
    sold = int(filled["sell_amount_raw"])
    assert sold + int(after["amount_raw"]) == initial_raw
    assert after["realized_proceeds_usd"] >= after["stake_usd"]
    # Re-evaluating the same already-filled state cannot insert a second SELL.
    sells = store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='SELL'", (ARM,)).fetchone()[0]
    store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=["solana:Composite151StoreFixture"])
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='SELL'", (ARM,)).fetchone()[0] == sells == 1
    database = store.path
    # Evaluation records the newest receipt even when its pending recovery mark
    # is settled in that same cycle; fetch the committed JSON rather than an
    # earlier row object returned by the helper.
    state_before = store.db.execute("SELECT capital_exit_state_json FROM chain_meme_trader_positions WHERE arm_id=?", (ARM,)).fetchone()[0]
    store.close()
    from memetrader.store import Store
    restored = Store(database, initial_cash_usd=1000)
    row = restored.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (ARM,)).fetchone()
    assert row["capital_exit_state_json"] == state_before and row["principal_recovered"] == 1
    assert restored.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='SELL'", (ARM,)).fetchone()[0] == 1
    restored.close()


def test_composite151_store_next_frame_uncoverable_does_not_claim_principal_recovered(tmp_path, monkeypatch):
    store, clock, position, mark = _store_position_for_composite_fill(tmp_path, monkeypatch)
    clock[0] += timedelta(minutes=6)
    mark(3.0, 40, 10, 14000)
    mark(2.9, 25, 20, 12000)
    triggered = mark(2.8, 10, 30, 10000)
    assert triggered["pending_mark_id"] is not None
    # The fill frame has collapsed enough that a strictly partial raw amount can no longer
    # return the debit.  Existing settlement exhausts the mark without fabricating proceeds.
    after = mark(.05, 5, 40, 8000)
    assert after["principal_recovered"] == 0
    assert float(after["realized_proceeds_usd"] or 0) == 0
    pending = store.db.execute("SELECT status FROM chain_meme_trader_marks WHERE id=?", (triggered["pending_mark_id"],)).fetchone()
    assert pending["status"] == "exhausted"
    store.close()
