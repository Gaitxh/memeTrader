from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from memetrader.early_observed_buyers import (
    ARM_ID, NOTIONAL_USD, distribution_evidence, evaluate_observed_buyer_distribution,
    seal_observed_buyers,
)
from memetrader.market_flow import build_market_frame


T = datetime(2026, 9, 6, tzinfo=timezone.utc)


def stamp(seconds):
    return (T + timedelta(seconds=seconds)).isoformat()


def window(start=0, end=10, trades=None, decimals=6, conversion=True):
    received = stamp(end + 1)
    identity = dict(pool_address="pool", base_mint="base", quote_mint="quote")
    trades = trades or [("BUY", "early", 2), ("BUY", "other", 1)]
    rows = [dict(**identity, signature=f"{start}-{i}", instruction_path="0.1", slot=100+i,
        signer_address=who, side=side, block_time=stamp(start + (i+1)/(len(trades)+1)*(end-start)),
        observed_at=received, recorded_at=received, base_amount_raw=10**9,
        quote_amount_raw=amount*10**decimals, amount_complete=True,
        amount_source="parsed_spl_transfer") for i,(side,who,amount) in enumerate(trades)]
    return build_market_frame(rows, window_start=stamp(start), window_end=stamp(end),
        resolver={**identity, "status": "verified", "base_decimals": 9, "quote_decimals": decimals,
                  "observed_at": received, "recorded_at": received},
        scan=dict(complete=True, coverage_complete=True, coverage_start=stamp(start),
            coverage_end=stamp(end), observed_at=received, recorded_at=received),
        quote_conversion=dict(quote_mint="quote", usd_per_quote=100.0, observed_at=received,
            recorded_at=received, max_age_seconds=30) if conversion else None,
        decision_at=received)


def seal(frame=None, **kwargs):
    return seal_observed_buyers(frame or window(), source_evidence_id=11,
        activation_evidence_id=10, activated_at=stamp(-1), now=stamp(11), **kwargs)


def test_first_observed_seal_is_bounded_immutable_and_birth_provenance_is_explicit():
    first = seal()
    assert first["coverage"] == "first_observed_buyers_only"
    assert first["mint_initial_holder_coverage"] == "unknown"
    birth = dict(verified=True, pool_address="pool", base_mint="base", birth_at=stamp(-20),
                 observed_at=stamp(-10), recorded_at=stamp(-10), birth_kind="token_creation")
    assert seal(birth_fact=birth)["coverage"] == "early_observed_buyers"
    assert seal(birth_fact={**birth, "birth_at": stamp(-1000)})["coverage"] == "first_observed_buyers_only"
    assert seal(birth_fact={**birth, "observed_at": stamp(12), "recorded_at": stamp(12)}) is None
    later = window(20, 30, [("BUY", "future_winner", 100)])
    assert seal_observed_buyers(later, source_evidence_id=12, activation_evidence_id=10,
        activated_at=stamp(-1), now=stamp(31), existing=first) == first
    crowded = seal(window(trades=[("BUY", f"b{i}", 1) for i in range(40)]))
    assert crowded["buyer_addresses"] == [f"b{i}" for i in range(32)]
    assert crowded["omitted_buyer_count"] == 8
    assert ARM_ID == "early_observed_buyer_distribution_v1" and NOTIONAL_USD == 5


def test_seal_requires_new_frontier_complete_real_post_activation_window():
    frame = window()
    assert seal_observed_buyers(frame, source_evidence_id=10, activation_evidence_id=10,
        activated_at=stamp(-1), now=stamp(11)) is None
    assert seal_observed_buyers(frame, source_evidence_id=11, activation_evidence_id=10,
        activated_at=stamp(5), now=stamp(11)) is None
    assert seal({**frame, "complete": False}) is None
    invalid = deepcopy(frame)
    invalid["trades"][0]["amount_source"] = "instruction_max_quote_limit"
    assert seal(invalid) is None
    future = deepcopy(frame)
    future["trades"][0]["recorded_at"] = stamp(12)
    assert seal(future) is None
    assert seal(window(trades=[("SELL", "not_a_buyer", 1)])) is None


@pytest.mark.parametrize("decimals", [6, 9])
def test_actual_subset_dedup_units_no_fake_usd_and_same_pool(decimals):
    cohort = seal()
    frame = window(12, 22, [("SELL", "early", 2), ("SELL", "outsider", 1)], decimals)
    frame["trades"].append(deepcopy(frame["trades"][0]))
    result = distribution_evidence(cohort, frame, source_evidence_id=12, now=stamp(23))
    assert result["complete"] and result["matched_sell_count"] == 1
    assert result["matched_sell_quote_raw"] == 2*10**decimals
    assert result["matched_sell_quote_usd"] == 200 and result["total_sell_notional_usd"] == 300
    assert not result["conversion_is_execution_evidence"]
    unknown = window(12, 22, [("SELL", "early", 2)], decimals, conversion=False)
    assert distribution_evidence(cohort, unknown, source_evidence_id=12, now=stamp(23))["matched_sell_quote_usd"] is None
    assert not distribution_evidence({**cohort, "pool_address": "other-pool"}, frame,
        source_evidence_id=12, now=stamp(23))["complete"]
    assert not distribution_evidence(cohort, frame, source_evidence_id=11, now=stamp(23))["complete"]
    assert not distribution_evidence(cohort, window(10,20), source_evidence_id=12,
        now=stamp(21))["complete"]  # Before local sealing is not later distribution.


def test_independent_distribution_exit_two_new_windows_gap_and_repeat_guards():
    cohort = seal()
    position = dict(token_id="solana:base", pair_address="pool", opened_at=stamp(12))
    def frame(start, end, evidence_id):
        return dict(token_id="solana:base", pair_address="pool", buyer_cohort=cohort,
            source_evidence_id=evidence_id,
            distribution_window=window(start,end,[("SELL","early",2),("SELL","outsider",1)]),
            effective_depth_change_ratio=-.2, effective_buyer_breadth_change_ratio=-.3)
    first = frame(12,22,12)
    action, _, state, _ = evaluate_observed_buyer_distribution(position, first, now=stamp(23))
    assert action == "HOLD" and state["distribution_bad_streak"] == 1
    assert evaluate_observed_buyer_distribution(position, first, state, now=stamp(23))[0] == "WAIT"
    action, _, _, evidence = evaluate_observed_buyer_distribution(position, frame(22,32,13), state, now=stamp(33))
    assert action == "SELL" and evidence["sell_fraction"] == 1
    assert evidence["strategy"] == ARM_ID and evidence["coverage"] == "first_observed_buyers_only"
    assert evaluate_observed_buyer_distribution(position, frame(21,31,14), state, now=stamp(32))[0] == "WAIT"
    assert evaluate_observed_buyer_distribution(position, frame(25,35,15), state, now=stamp(36))[0] == "HOLD"
    changed = frame(22,32,13)
    changed["buyer_cohort"] = {**cohort, "cohort_id": "replacement"}
    assert evaluate_observed_buyer_distribution(position, changed, state, now=stamp(33))[0] == "WAIT"
    assert state["distribution_bad_streak"] == 1  # Pure evaluation did not mutate caller state.
