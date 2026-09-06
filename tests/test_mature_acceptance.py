from datetime import datetime, timedelta, timezone

from memetrader.mature_acceptance import (
    evaluate_mature_acceptance,
    mature_acceptance_policy,
)


UTC = timezone.utc


def _frame(at, index, *, price=1.0, liquidity=1_000.0, volume=100.0, buys=1, sells=1):
    return {
        "id": index,
        "token_id": "solana:TOKEN",
        "pair_address": "POOL",
        "price": price,
        "liquidity": liquidity,
        "volume": volume,
        "buys": buys,
        "sells": sells,
        "pool_age_seconds": 22_000.0 + index,
        "observed_at": at.isoformat(),
        "ingested_at": (at + timedelta(milliseconds=100)).isoformat(),
        "recorded_at": (at + timedelta(milliseconds=200)).isoformat(),
    }


def test_mature_acceptance_policy_is_single_5u_noncapital_pattern_arm():
    policy = mature_acceptance_policy()
    assert policy["arm_id"] == "mature_new_acceptance_5u_v1"
    assert policy["notional_usd"] == 5.0
    assert policy["entry_match_mode"] == "isolated_pattern_observer"
    assert policy["capital_experiment"] is False
    assert "capital_exit_kind" not in policy
    assert policy["exit_mode"] == "market_mark_pattern_scaleout"


def test_narrative_event_freezes_pre_event_baseline_then_readies_on_second_confirmation():
    activated = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
    baseline_at = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    event_at = baseline_at + timedelta(seconds=10)
    current_at = event_at + timedelta(seconds=5)
    history = [_frame(baseline_at, 1), _frame(current_at, 2)]
    narrative = {
        "evidence_id": 44,
        "token_id": "solana:TOKEN",
        "pair_address": "POOL",
        "exact_token_relation": True,
        "independent_sources": 2,
        "source_urls": ["https://one.example/item", "https://two.example/item"],
        "verification_id": 9,
        "basis": "original_source_contract_mentions_and_independent_fact_support",
        "observed_at": event_at.isoformat(),
        "recorded_at": (event_at + timedelta(milliseconds=100)).isoformat(),
    }
    ready, reason, state, evidence = evaluate_mature_acceptance(
        history, narrative, decision_at=current_at + timedelta(seconds=1), activated_at=activated
    )
    assert ready is False and reason == "mature_acceptance_event_frozen"
    assert evidence["episode"]["baseline"]["snapshot_id"] == 1
    assert evidence["episode"]["event_kind"] == "independent_information"

    first_at = event_at + timedelta(seconds=25)
    history.append(_frame(first_at, 3, price=1.01, liquidity=1_010))
    ready, reason, state, _ = evaluate_mature_acceptance(
        history, narrative, state, decision_at=first_at + timedelta(seconds=1), activated_at=activated
    )
    assert ready is False and reason == "mature_acceptance_first_confirmation"

    second_at = first_at + timedelta(seconds=20)
    history.append(_frame(second_at, 4, price=1.02, liquidity=1_010))
    ready, reason, state, evidence = evaluate_mature_acceptance(
        history, narrative, state, decision_at=second_at + timedelta(seconds=1), activated_at=activated
    )
    assert ready is True and reason == "mature_acceptance_two_frame_confirmed"
    assert state["status"] == "READY"
    assert evidence["execution_contract"].endswith("next_independent_original_pool_frame")


def test_natural_event_uses_raw_quiet_predicate_not_strategy_ready_state():
    activated = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
    trigger_at = datetime(2026, 9, 6, 10, 15, tzinfo=UTC)
    history = []
    for index, seconds_before in enumerate((900, 810, 720, 630, 540, 450, 360, 270, 180, 120, 60), start=1):
        history.append(_frame(
            trigger_at - timedelta(seconds=seconds_before), index,
            price=1.0, liquidity=1_000.0, volume=100.0, buys=1, sells=1,
        ))
    history.append(_frame(
        trigger_at, 20, price=1.12, liquidity=1_000.0,
        volume=1_000.0, buys=7, sells=3,
    ))
    ready, reason, state, evidence = evaluate_mature_acceptance(
        history,
        decision_at=trigger_at + timedelta(seconds=1),
        activated_at=activated,
    )
    assert ready is False and reason == "mature_acceptance_event_frozen"
    assert evidence["episode"]["event_kind"] == "natural_reactivation"
    assert evidence["episode"]["basis"].endswith("not_strategy_ready_state")

    first_at = trigger_at + timedelta(seconds=20)
    history.append(_frame(first_at, 21, price=1.13, liquidity=1_005.0, volume=900, buys=6, sells=3))
    ready, reason, state, _ = evaluate_mature_acceptance(
        history, previous_state=state,
        decision_at=first_at + timedelta(seconds=1), activated_at=activated,
    )
    assert ready is False and reason == "mature_acceptance_first_confirmation"
    second_at = first_at + timedelta(seconds=20)
    history.append(_frame(second_at, 22, price=1.14, liquidity=1_010.0, volume=800, buys=5, sells=3))
    ready, reason, _, _ = evaluate_mature_acceptance(
        history, previous_state=state,
        decision_at=second_at + timedelta(seconds=1), activated_at=activated,
    )
    assert ready is True and reason == "mature_acceptance_two_frame_confirmed"


def test_narrative_without_pre_event_exact_pool_baseline_waits():
    activated = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
    event_at = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    after = event_at + timedelta(seconds=20)
    narrative = {
        "evidence_id": 45,
        "token_id": "solana:TOKEN",
        "pair_address": "POOL",
        "exact_token_relation": True,
        "independent_sources": 2,
        "source_urls": ["https://one.example/item", "https://two.example/item"],
        "basis": "original_source_contract_mentions_and_independent_fact_support",
        "observed_at": event_at.isoformat(),
        "recorded_at": (event_at + timedelta(milliseconds=100)).isoformat(),
    }
    ready, reason, state, _ = evaluate_mature_acceptance(
        [_frame(after, 1)], narrative,
        decision_at=after + timedelta(seconds=1), activated_at=activated,
    )
    assert ready is False and reason == "awaiting_mature_acceptance_event"
    assert "episode" not in state
