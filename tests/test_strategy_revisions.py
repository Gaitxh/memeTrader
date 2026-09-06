from datetime import datetime, timedelta, timezone

from memetrader.strategy_revisions import (
    ACTIVITY_FLOOR_ARMS,
    ADDITIVE_L0_LOSS_EXIT_ARMS,
    CONDITIONAL_RUNNER_ARMS,
    FLASH_ARM,
    INACTIVITY_ARM,
    MATURE_ARM,
    evaluate_l0_loss_deterioration,
    revision_entry_signal,
    revision_context_signal,
    revision_spec,
)


UTC = timezone.utc


def _policy(arm_id):
    base = {
        "arm_id": arm_id,
        "canonical_id": arm_id,
        "stage": 5,
        "name": "old",
        "behavior_contract_hash": "old-hash",
    }
    if arm_id == FLASH_ARM:
        base["entry_filter"] = {
            "max_age_seconds_exclusive": 120.0,
            "prior55_trades_equal": 0,
            "min_m5_trades": 50,
            "max_m5_volume_usd_exclusive": 1_000.0,
        }
    elif arm_id == MATURE_ARM:
        base["entry_filter"] = {
            "min_age_seconds": 300.0,
            "max_age_seconds": 900.0,
            "min_prior55_trades_exclusive": 2,
        }
    return base


def _entry_frame(start, seconds, frame_id, **overrides):
    observed = start + timedelta(seconds=seconds)
    frame = {
        "frame_id": frame_id,
        "identity": {
            "chain": "solana",
            "token_id": "solana:TOKEN",
            "pair_address": "POOL",
        },
        "observed_at": observed.isoformat(),
        "ingested_at": (observed + timedelta(seconds=1)).isoformat(),
        "recorded_at": (observed + timedelta(seconds=2)).isoformat(),
        "price": 1.0,
        "liquidity": 1_000.0,
        "volume": 300.0,
        "buys": 30,
        "sells": 25,
        "pool_age_seconds": 60.0 + seconds,
        "prior55_trades": 0,
    }
    frame.update(overrides)
    return frame


def test_revision_spec_keeps_unselected_contracts_unchanged():
    unrelated = {"arm_id": "other", "stage": 99, "nested": {"keep": True}}
    assert revision_spec(unrelated) == unrelated
    assert revision_spec(unrelated) is not unrelated

    inactivity = revision_spec(_policy(INACTIVITY_ARM))
    assert inactivity["arm_id"] == INACTIVITY_ARM
    assert inactivity["canonical_id"] == INACTIVITY_ARM
    assert inactivity["stage"] == 5
    assert inactivity["strategy_revision"] == 2
    assert inactivity["capital_exit_kind"] == "l0_loss_deterioration"
    assert inactivity["revision_history"][0]["behavior_contract_hash"] == "old-hash"

    flash = revision_spec(_policy(FLASH_ARM))
    assert flash.get("entry_match_mode") == _policy(FLASH_ARM).get("entry_match_mode")
    assert "entry_revision_kind" not in flash
    assert flash["entry_filter"]["min_m5_volume_usd"] == 200.0
    assert "max_m5_volume_usd_exclusive" not in flash["entry_filter"]

    mature = revision_spec(_policy(MATURE_ARM))
    assert mature["entry_revision_kind"] == "mature_confirmation"
    assert mature["entry_filter"] == _policy(MATURE_ARM)["entry_filter"]

    input_only = {
        "arm_id": "experiment_narrative_candidate_v1",
        "strategy_revision": 1,
    }
    replacement = revision_spec(input_only)
    assert replacement["strategy_revision"] == 2
    assert replacement["entry_revision_kind"] == "evidence_extension_l0"
    assert replacement["revision_history"][0]["strategy_revision"] == 1


def test_capital_release_revisions_preserve_slots_and_change_actual_exit_rules():
    from memetrader.l0_experiments import l0_experiment_policies
    from memetrader.store import Store
    policies = [Store.chain_meme_trader_v21_policies()[-1],
                Store.chain_meme_trader_cost_coverage_scaleout_policy(),
                *l0_experiment_policies()]
    revised = [revision_spec(policy) for policy in policies]
    for old, new in zip(policies, revised):
        assert new["arm_id"] == old["arm_id"]
        assert new["strategy_revision"] == 2
        assert new["revision_changes"]
        assert new["revision_history"][0]["name"] == old["name"]
        assert new["entry_family"] == old["entry_family"]
        assert new.get("notional_usd", 20) == old.get("notional_usd", 20)
    assert revised[0]["take_profit"] == [{"return": .4, "fraction_of_remaining": .75}]
    assert revised[1]["take_profit"] == [{"return": .3, "fraction_of_remaining": 1.0}]
    assert revised[2]["capital_exit_kind"] == "l0_loss_deterioration"
    assert revised[3]["capital_exit_kind"] is None
    assert revised[2]["runner_review_minutes"] == revised[3]["runner_review_minutes"] == 10
    assert revised[4]["take_profit"][0]["fraction_of_remaining"] == .5
    assert revised[5]["take_profit"][0]["fraction_of_remaining"] == 1


def test_group_revisions_preserve_main_coverage_and_existing_exits():
    activity_arm = next(iter(ACTIVITY_FLOOR_ARMS))
    activity = revision_spec({
        "arm_id": activity_arm,
        "canonical_id": activity_arm,
        "stage": 1,
        "entry_match_mode": "main_full_coverage",
        "entry_filter": {"direction": "broad_launch"},
        "capital_exit_kind": "existing_exit",
    })
    assert activity["strategy_revision"] == 2
    assert activity["entry_match_mode"] == "main_full_coverage"
    assert activity["entry_filter"]["min_m5_trades"] == 3
    assert activity["entry_filter"]["min_m5_volume_usd"] == 200.0
    assert activity["capital_exit_kind"] == "existing_exit"

    exit_arm = next(iter(ADDITIVE_L0_LOSS_EXIT_ARMS))
    additive_exit = revision_spec({
        "arm_id": exit_arm,
        "canonical_id": exit_arm,
        "stage": 2,
        "entry_match_mode": "main_full_coverage",
        "exit_family": "peak_guard",
    })
    assert additive_exit["entry_match_mode"] == "main_full_coverage"
    assert additive_exit["exit_family"] == "peak_guard"
    assert "capital_exit_kind" not in additive_exit
    assert additive_exit["revision_exit_kind"] == "l0_loss_deterioration"
    assert additive_exit["revision_exit_policy"]["minimum_hold_seconds"] == 60.0


def test_conditional_runner_pair_uses_the_same_two_frame_confirmation():
    start = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    history = [
        _entry_frame(start, 10, "first", price=1.0, liquidity=1_000),
        _entry_frame(start, 30, "second", price=1.01, liquidity=1_010),
    ]
    results = []
    for arm_id in sorted(CONDITIONAL_RUNNER_ARMS):
        policy = revision_spec({
            "arm_id": arm_id,
            "canonical_id": arm_id,
            "stage": 135,
            "entry_match_mode": "isolated_pattern_observer",
            "entry_filter": {
                "direction": "conditional_runner",
                "control": arm_id.endswith("control_v1"),
            },
        })
        assert policy["paired_entry_group"] == "conditional_runner_revision_v2"
        results.append(revision_entry_signal(
            history,
            policy,
            decision_at=start + timedelta(seconds=33),
            activated_at=start,
        ))
    assert results == [
        (True, "conditional_runner_confirmation_ready"),
        (True, "conditional_runner_confirmation_ready"),
    ]


def test_strategy083_requires_baseline_and_two_spaced_loss_deteriorations():
    opened = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    position = {
        "opened_at": opened.isoformat(),
        "token_id": "solana:TOKEN",
        "pair_address": "POOL",
        "remaining_cost_usd": 20.0,
    }

    def frame(seconds, frame_id, price, liquidity, recovery):
        observed = opened + timedelta(seconds=seconds)
        return {
            "frame_id": frame_id,
            "token_id": "solana:TOKEN",
            "pair_address": "POOL",
            "original_pool": True,
            "observed_at": observed.isoformat(),
            "recorded_at": (observed + timedelta(seconds=1)).isoformat(),
            "price_usd": price,
            "liquidity_usd": liquidity,
            "net_recovery_usd": recovery,
        }

    early = frame(30, "early", 1.0, 1_000.0, 19.5)
    result = evaluate_l0_loss_deterioration(
        position, early, now=opened + timedelta(seconds=32)
    )
    assert result[:2] == ("WAIT", "l0_loss_minimum_hold_not_reached")

    base = frame(60, "base", 1.0, 1_000.0, 19.0)
    action, reason, state, _ = evaluate_l0_loss_deterioration(
        position, base, result[2], now=opened + timedelta(seconds=62)
    )
    assert (action, reason) == ("HOLD", "l0_loss_baseline_recorded")

    bad1 = frame(66, "bad1", 0.95, 1_000.0, 18.0)
    action, reason, state, evidence = evaluate_l0_loss_deterioration(
        position, bad1, state, now=opened + timedelta(seconds=68)
    )
    assert (action, reason) == ("HOLD", "l0_loss_deterioration_monitoring")
    assert evidence["deterioration_streak"] == 1

    bad2 = frame(72, "bad2", 0.90, 990.0, 17.0)
    action, reason, _, evidence = evaluate_l0_loss_deterioration(
        position, bad2, state, now=opened + timedelta(seconds=74)
    )
    assert (action, reason) == ("SELL", "l0_loss_deterioration_armed")
    assert evidence["required_fill"] == "next_original_pool_frame"
    assert "principal_recovered" not in evidence


def test_flash_revision_keeps_main_opportunity_coverage():
    original = _policy(FLASH_ARM)
    original["entry_match_mode"] = "main_full_coverage"
    policy = revision_spec(original)
    assert policy["entry_match_mode"] == "main_full_coverage"
    assert "entry_revision_kind" not in policy
    assert policy["entry_filter"] == {
        "max_age_seconds_exclusive": 120.0,
        "prior55_trades_equal": 0,
        "min_m5_trades": 50,
        "min_m5_volume_usd": 200.0,
    }


def test_mature_revision_requires_two_spaced_active_confirmations():
    start = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    policy = revision_spec(_policy(MATURE_ARM))
    history = [
        _entry_frame(
            start, 10, "base", pool_age_seconds=400.0, prior55_trades=3,
        ),
        _entry_frame(
            start, 30, "confirm1", price=1.0, liquidity=1_000.0,
            pool_age_seconds=420.0, prior55_trades=3,
        ),
        _entry_frame(
            start, 50, "confirm2", price=1.01, liquidity=1_010.0,
            pool_age_seconds=440.0, prior55_trades=3,
        ),
    ]
    ready, reason = revision_entry_signal(
        history,
        policy,
        decision_at=start + timedelta(seconds=53),
        activated_at=start,
    )
    assert (ready, reason) == (True, "mature_confirmation_ready")


def test_mature_revision_selects_spaced_frames_from_dense_two_second_history():
    start = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    policy = revision_spec(_policy(MATURE_ARM))
    history = [
        _entry_frame(
            start, seconds, f"dense-{seconds}",
            price=1.0 + seconds / 10_000,
            liquidity=1_000.0 + seconds,
            pool_age_seconds=400.0 + seconds,
            prior55_trades=3,
        )
        for seconds in range(10, 51, 2)
    ]
    ready, reason = revision_entry_signal(
        history,
        policy,
        decision_at=start + timedelta(seconds=53),
        activated_at=start,
    )
    assert (ready, reason) == (True, "mature_confirmation_ready")


def test_entry_revisions_reject_future_duplicate_and_other_pool_frames():
    start = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    policy = revision_spec(_policy(next(iter(CONDITIONAL_RUNNER_ARMS))))
    valid = _entry_frame(start, 10, "signal")

    future = _entry_frame(start, 20, "future")
    ready, reason = revision_entry_signal(
        [valid, future], policy,
        decision_at=start + timedelta(seconds=19), activated_at=start,
    )
    assert (ready, reason) == (False, "noncausal_or_future_entry_frame")

    duplicate = _entry_frame(start, 20, "signal")
    ready, reason = revision_entry_signal(
        [valid, duplicate], policy,
        decision_at=start + timedelta(seconds=23), activated_at=start,
    )
    assert (ready, reason) == (False, "duplicate_or_missing_entry_frame")

    other_pool = _entry_frame(start, 20, "other")
    other_pool["identity"]["pair_address"] = "OTHER"
    ready, reason = revision_entry_signal(
        [valid, other_pool], policy,
        decision_at=start + timedelta(seconds=23), activated_at=start,
    )
    assert (ready, reason) == (False, "mixed_entry_identity")


def test_quiet_revision_uses_three_observed_quiet_frames_then_reawakening():
    start = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    policy = revision_spec({
        "arm_id": "experiment_quiet_reawakening_candidate_v1",
        "canonical_id": "experiment_quiet_reawakening_candidate_v1",
        "stage": 129,
        "entry_filter": {"direction": "quiet_reawakening", "control": False},
    })
    history = [
        _entry_frame(start, 10, "quiet-1", price=1.00, liquidity=1_000, volume=100, buys=1, sells=1),
        _entry_frame(start, 150, "quiet-2", price=1.02, liquidity=990, volume=120, buys=0, sells=1),
        _entry_frame(start, 290, "quiet-3", price=1.01, liquidity=980, volume=80, buys=1, sells=0),
        _entry_frame(
            start, 430, "wake", price=1.14, liquidity=900, volume=1_100,
            buys=7, sells=3, pool_age_seconds=22_000,
        ),
    ]
    ready, reason = revision_entry_signal(
        history, policy,
        decision_at=start + timedelta(seconds=433), activated_at=start,
    )
    assert (ready, reason) == (True, "quiet_reawakening_confirmation_ready")


def test_risk_revisions_keep_catastrophe_veto_and_use_l0_confirmation():
    start = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    history = [
        _entry_frame(start, 10, "first", price=1.0, liquidity=1_000),
        _entry_frame(start, 20, "second", price=1.01, liquidity=1_010),
    ]
    common = {
        "sealed": True,
        "cutoff_at": (start - timedelta(days=1)).isoformat(),
        "trained_at": (start - timedelta(hours=1)).isoformat(),
        "observed_at": history[-1]["observed_at"],
        "recorded_at": history[-1]["recorded_at"],
        "sample_status": "sufficient_sample",
    }
    competing = revision_spec({
        "arm_id": "competing_risk_v1", "canonical_id": "competing_risk_v1",
        "stage": 161, "entry_filter": {"direction": "competing_risk"},
    })
    ready, reason = revision_context_signal(
        history, competing,
        context={"competing_risk": {**common, "p_profit": .3, "p_death": .1,
                                     "p_ordinary_loss": .6}},
        decision_at=start + timedelta(seconds=23), activated_at=start,
    )
    assert (ready, reason) == (True, "competing_risk_l0_confirmation_ready")

    duration = revision_spec({
        "arm_id": "duration_competing_risk_v1",
        "canonical_id": "duration_competing_risk_v1", "stage": 179,
        "entry_filter": {"direction": "duration_competing_risk", "horizon_seconds": 300},
    })
    ready, reason = revision_context_signal(
        history, duration,
        context={"duration_risk": {
            **common,
            "gap_sensitivity": {"300": {
                "profit_exit": .3, "loss_exit": .5,
                "writeoff_exit": .1, "observation_gap": .1,
            }},
        }},
        decision_at=start + timedelta(seconds=23), activated_at=start,
    )
    assert (ready, reason) == (True, "duration_risk_l0_confirmation_ready")
