from datetime import datetime, timedelta, timezone

from memetrader.cohort_experiments import (
    consume_passive_cohort_batch,
    evaluate_clone_handoff_entry,
    evaluate_clone_handoff_round,
    evaluate_clone_consensus_leader_entry,
    evaluate_clone_leader_entry,
    evaluate_relative_resilience_entry,
    evaluate_relative_resilience_round,
    cohort_experiment_policies,
    freeze_clone_episode,
)


UTC = timezone.utc


def _candidate(now, index, *, chain="solana", lifecycle="new_pool", symbol="clone"):
    observed = now - timedelta(seconds=2)
    return {
        "token_id": f"{chain}:TOKEN{index}",
        "pair_address": f"POOL{index}",
        "chain": chain,
        "lifecycle": lifecycle,
        "normalized_symbol": symbol,
        "original_pool": True,
        "discovered_at": (now - timedelta(minutes=index)).isoformat(),
        "observed_at": observed.isoformat(),
        "recorded_at": (observed + timedelta(milliseconds=100)).isoformat(),
        "price_usd": 1.0 + index / 100,
        "liquidity_usd": 1_000.0 + index * 100,
        "volume_5m_usd": 1_000.0 - index * 100,
    }


def _clone_episode(now):
    candidates = [_candidate(now, index) for index in range(5)]
    action, reason, state, evidence = freeze_clone_episode(
        candidates,
        episode_id="episode-1",
        decision_at=now,
        activated_at=now - timedelta(hours=1),
    )
    assert (action, reason) == ("FROZEN", "clone_episode_frozen")
    return candidates, state, evidence


def _entry_frame(target, observed):
    return {
        "token_id": target["token_id"],
        "pair_address": target["pair_address"],
        "chain": target["chain"],
        "lifecycle": target["lifecycle"],
        "normalized_symbol": target["normalized_symbol"],
        "original_pool": True,
        "observed_at": observed.isoformat(),
        "recorded_at": (observed + timedelta(milliseconds=100)).isoformat(),
        "price_usd": target["price_usd"],
        "liquidity_usd": max(100.0, target["liquidity_usd"]),
    }


def test_clone_entry_shared_floor_can_be_lowered_or_raised():
    from memetrader.cohort_experiments import CLONE_EPISODE_POLICY
    now = datetime(2026, 9, 6, tzinfo=UTC)
    _, episode, evidence = _clone_episode(now)
    target = evidence["liquidity_leader"]
    frame = _entry_frame(target, now + timedelta(seconds=1))
    frame["liquidity_usd"] = 100.0
    def evaluate(floor):
        return evaluate_clone_leader_entry(episode, frame, leader_kind="liquidity",
            decision_at=now + timedelta(seconds=2), activated_at=now - timedelta(hours=1),
            policy={**CLONE_EPISODE_POLICY, "min_pool_liquidity_usd": floor})[0]
    assert evaluate(100.0) == "SELECT"
    assert evaluate(1000.0) == "WAIT"


def test_policy_shapes_use_opportunity_pairing_not_same_buy_pairing():
    policies = cohort_experiment_policies()
    assert len(policies) == 12
    assert all(policy["notional_usd"] == ({'organic_early_flow_v1':2.0,'synthetic_fast_harvest_v1':1.0}.get(policy['arm_id'],5.0)) for policy in policies)
    assert all("paired_entry_group" not in policy for policy in policies)
    assert all(policy.get("paired_opportunity_group") for policy in policies)
    handoff = next(policy for policy in policies if policy["arm_id"] == "clone_liquidity_handoff_v1")
    assert handoff["opportunity_control_arm_id"] == "clone_liquidity_leader_v1"
    consensus = next(policy for policy in policies if policy["arm_id"] == "clone_consensus_leader_v2")
    assert consensus["entry_filter"] == {"direction": "clone_consensus_leader", "max_concurrent_positions": 4}


def test_clone_episode_freezes_unique_liquidity_and_volume_leaders_and_never_merges():
    now = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    candidates, frozen, evidence = _clone_episode(now)
    assert evidence["liquidity_leader"]["token_id"] == "solana:TOKEN4"
    assert evidence["m5volume_leader"]["token_id"] == "solana:TOKEN0"
    assert evidence["differential_pair_eligible"] is True

    later = candidates + [_candidate(now + timedelta(seconds=1), 5)]
    action, reason, unchanged, _ = freeze_clone_episode(
        later,
        episode_id="episode-1",
        decision_at=now + timedelta(seconds=1),
        activated_at=now - timedelta(hours=1),
        existing=frozen,
    )
    assert (action, reason) == ("FROZEN", "clone_episode_already_frozen")
    assert unchanged == frozen

    target = evidence["liquidity_leader"]
    frame_at = now + timedelta(seconds=6)
    action, reason, _, selected = evaluate_clone_leader_entry(
        frozen,
        _entry_frame(target, frame_at),
        leader_kind="liquidity",
        decision_at=frame_at + timedelta(seconds=1),
        activated_at=now - timedelta(hours=1),
    )
    assert (action, reason) == ("SELECT", "clone_leader_next_frame_confirmed")
    assert selected["selected"]["token_id"] == target["token_id"]


def test_clone_episode_rejects_mixed_chain_or_lifecycle():
    now = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    candidates = [_candidate(now, index) for index in range(5)]
    candidates[-1] = _candidate(now, 4, lifecycle="mature")
    action, reason, _, _ = freeze_clone_episode(
        candidates,
        episode_id="mixed",
        decision_at=now,
        activated_at=now - timedelta(hours=1),
    )
    assert (action, reason) == ("WAIT", "clone_episode_mixed_scope")


def test_clone_consensus_leader_requires_shared_unique_leader_and_later_same_pool_frame():
    now = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    candidates = [_candidate(now, index) for index in range(5)]
    for index, candidate in enumerate(candidates):
        candidate["volume_5m_usd"] = 1_000.0 + index * 100
    action, reason, frozen, evidence = freeze_clone_episode(
        candidates, episode_id="consensus", decision_at=now,
        activated_at=now - timedelta(hours=1),
    )
    assert (action, reason) == ("FROZEN", "clone_episode_frozen")
    target = evidence["liquidity_leader"]
    action, reason, _, _ = evaluate_clone_consensus_leader_entry(
        frozen, _entry_frame(target, now), decision_at=now,
        activated_at=now - timedelta(hours=1),
    )
    assert (action, reason) == ("WAIT", "awaiting_clone_consensus_leader_next_original_pool_frame")
    action, reason, _, selected = evaluate_clone_consensus_leader_entry(
        frozen, _entry_frame(target, now + timedelta(seconds=1)),
        decision_at=now + timedelta(seconds=2), activated_at=now - timedelta(hours=1),
    )
    assert (action, reason) == ("SELECT", "clone_consensus_leader_next_frame_confirmed")
    assert selected["selected"]["token_id"] == target["token_id"]

    _, distinct_frozen, _ = _clone_episode(now)
    action, reason, _, _ = evaluate_clone_consensus_leader_entry(
        distinct_frozen, _entry_frame(target, now + timedelta(seconds=1)),
        decision_at=now + timedelta(seconds=2), activated_at=now - timedelta(hours=1),
    )
    assert (action, reason) == ("WAIT", "clone_consensus_leader_not_unique_or_not_shared")


def _resilience_round(now, returns, *, prices=None, liquidities=None):
    prices = prices or [1.0] * 5
    liquidities = liquidities or [1_000.0] * 5
    rows = []
    for index, value in enumerate(returns):
        row = _candidate(now, index)
        row.update({
            "observed_at": (now - timedelta(seconds=2)).isoformat(),
            "recorded_at": (now - timedelta(seconds=1)).isoformat(),
            "price_usd": prices[index],
            "liquidity_usd": liquidities[index],
            "price_return": value,
            "liquidity_return": 0.05 if index == 0 else -0.02,
            "prior_low_price_usd": 0.9,
        })
        rows.append(row)
    return rows


def test_relative_resilience_arms_control_then_candidate_and_uses_later_frame():
    activated = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
    first_at = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    first = _resilience_round(first_at, [0.02, -0.10, -0.12, -0.08, -0.05])
    action, reason, state, evidence = evaluate_relative_resilience_round(
        first, round_id="r1", decision_at=first_at, activated_at=activated
    )
    assert (action, reason) == ("OBSERVE", "relative_resilience_control_armed")
    assert evidence["weak_environment"] is True
    assert state["initial_target"]["token_id"] == "solana:TOKEN0"

    control_at = first_at + timedelta(seconds=1)
    control_frame = _entry_frame(state["initial_target"], control_at)
    action, reason, _, _ = evaluate_relative_resilience_entry(
        state,
        control_frame,
        arm_kind="control",
        decision_at=control_at + timedelta(seconds=1),
        activated_at=activated,
    )
    assert (action, reason) == ("SELECT", "relative_resilience_next_frame_confirmed")

    second_at = first_at + timedelta(seconds=6)
    second = _resilience_round(second_at, [0.01, -0.11, -0.13, -0.09, -0.06])
    action, reason, state, evidence = evaluate_relative_resilience_round(
        second, state, round_id="r2", decision_at=second_at, activated_at=activated
    )
    assert (action, reason) == ("ARMED", "relative_resilience_candidate_armed")
    assert evidence["candidate_streak"] == 2

    candidate_at = second_at + timedelta(seconds=1)
    action, reason, _, selected = evaluate_relative_resilience_entry(
        state,
        _entry_frame(state["initial_target"], candidate_at),
        arm_kind="candidate",
        decision_at=candidate_at + timedelta(seconds=1),
        activated_at=activated,
    )
    assert (action, reason) == ("SELECT", "relative_resilience_next_frame_confirmed")
    assert selected["paired_opportunity_semantics"] == "same_initial_opportunity_not_same_buy"


def _handoff_rows(now, values):
    rows = []
    for index, (price, liquidity) in enumerate(values):
        row = _candidate(now, index)
        row.update({
            "observed_at": (now - timedelta(seconds=2)).isoformat(),
            "recorded_at": (now - timedelta(seconds=1)).isoformat(),
            "price_usd": price,
            "liquidity_usd": liquidity,
        })
        rows.append(row)
    return rows


def test_clone_handoff_requires_two_rounds_and_enters_only_frozen_new_leader_next_frame():
    activated = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
    frozen_at = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    _, frozen, evidence = _clone_episode(frozen_at)
    old = evidence["liquidity_leader"]
    closed = {
        "token_id": old["token_id"],
        "pair_address": old["pair_address"],
        "closed_at": (frozen_at + timedelta(seconds=1)).isoformat(),
        "closed_recorded_at": (frozen_at + timedelta(seconds=2)).isoformat(),
    }
    baseline_at = frozen_at + timedelta(seconds=10)
    baseline = _handoff_rows(
        baseline_at,
        [(1.0, 1_000), (1.0, 1_100), (1.0, 1_200), (1.0, 1_300), (1.0, 1_400)],
    )
    action, reason, state, _ = evaluate_clone_handoff_round(
        frozen, closed, baseline, round_id="h0", decision_at=baseline_at, activated_at=activated
    )
    assert (action, reason) == ("OBSERVE", "clone_handoff_baseline_recorded")

    first_at = baseline_at + timedelta(seconds=6)
    first = _handoff_rows(
        first_at,
        [(1.1, 1_200), (1.0, 1_100), (1.0, 1_200), (1.0, 1_300), (0.9, 1_300)],
    )
    action, reason, state, evidence = evaluate_clone_handoff_round(
        frozen, closed, first, state, round_id="h1", decision_at=first_at, activated_at=activated
    )
    assert (action, reason) == ("OBSERVE", "clone_liquidity_handoff_monitoring")
    assert evidence["handoff_target"]["token_id"] == "solana:TOKEN0"

    second_at = first_at + timedelta(seconds=6)
    second = _handoff_rows(
        second_at,
        [(1.2, 1_300), (1.0, 1_100), (1.0, 1_200), (1.0, 1_300), (0.8, 1_200)],
    )
    action, reason, state, evidence = evaluate_clone_handoff_round(
        frozen, closed, second, state, round_id="h2", decision_at=second_at, activated_at=activated
    )
    assert (action, reason) == ("ARMED", "clone_liquidity_handoff_armed")
    assert evidence["basis"] == "reported_price_and_liquidity_not_actual_capital_flow"

    entry_at = second_at + timedelta(seconds=2)
    action, reason, state, selected = evaluate_clone_handoff_entry(
        frozen,
        state,
        _entry_frame(state["handoff_target"], entry_at),
        decision_at=entry_at + timedelta(seconds=1),
        activated_at=activated,
    )
    assert (action, reason) == ("SELECT", "clone_handoff_next_frame_confirmed")
    assert state["handoff_used"] is True
    assert selected["selected"]["token_id"] == "solana:TOKEN0"


def _passive_batch(now, prices, liquidities, *, same_symbol=False):
    rows = []
    for index, (price, liquidity) in enumerate(zip(prices, liquidities)):
        row = _candidate(now, index, symbol="clone" if same_symbol else f"symbol{index}")
        row.update({
            "observed_at": (now - timedelta(seconds=2)).isoformat(),
            "recorded_at": (now - timedelta(seconds=1)).isoformat(),
            "price_usd": price,
            "liquidity_usd": liquidity,
            "is_held": False,
        })
        rows.append(row)
    return rows


def test_passive_adapter_freezes_same_batch_clone_and_emits_only_on_later_natural_frames():
    activated = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
    first_at = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    first = _passive_batch(
        first_at, [1, 1, 1, 1, 1], [1_000, 1_100, 1_200, 1_300, 1_400],
        same_symbol=True,
    )
    state, signals = consume_passive_cohort_batch(
        first, now=first_at, activated_at=activated
    )
    assert signals == {}
    assert len(state["clone_episodes"]) == 1

    second_at = first_at + timedelta(seconds=6)
    second = _passive_batch(
        second_at, [1, 1, 1, 1, 1], [1_000, 1_100, 1_200, 1_300, 1_400],
        same_symbol=True,
    )
    state, signals = consume_passive_cohort_batch(
        second, state, now=second_at, activated_at=activated
    )
    assert "clone_liquidity_leader_v1" in signals[("solana:TOKEN4", "POOL4")]
    assert "clone_m5volume_leader_v1" in signals[("solana:TOKEN0", "POOL0")]
    decision_key = signals[("solana:TOKEN4", "POOL4")]["clone_liquidity_leader_v1"]["decision_key"]

    third_at = second_at + timedelta(seconds=6)
    state, signals = consume_passive_cohort_batch(
        _passive_batch(third_at, [1] * 5, [1_000, 1_100, 1_200, 1_300, 1_400], same_symbol=True),
        state,
        now=third_at,
        activated_at=activated,
        already_bought=[decision_key],
    )
    assert "clone_liquidity_leader_v1" not in signals.get(("solana:TOKEN4", "POOL4"), {})
    assert all(len(history) <= 3 for history in state["token_frames"].values())


def test_passive_adapter_emits_consensus_only_for_shared_unique_frozen_leader():
    activated = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
    first_at = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    first = _passive_batch(first_at, [1] * 5, [1_000, 1_100, 1_200, 1_300, 1_400], same_symbol=True)
    for index, row in enumerate(first):
        row["volume_5m_usd"] = 1_000 + index * 100
    state, signals = consume_passive_cohort_batch(first, now=first_at, activated_at=activated)
    assert signals == {}
    second_at = first_at + timedelta(seconds=6)
    second = _passive_batch(second_at, [1] * 5, [1_000, 1_100, 1_200, 1_300, 1_400], same_symbol=True)
    for index, row in enumerate(second):
        row["volume_5m_usd"] = 1_000 + index * 100
    _, signals = consume_passive_cohort_batch(second, state, now=second_at, activated_at=activated)
    assert "clone_consensus_leader_v2" in signals[("solana:TOKEN4", "POOL4")]


def test_passive_batch_keeps_prior_state_independent_of_later_observations():
    import copy
    activated = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
    at = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    frames = _passive_batch(at, [1] * 5, [1000,1100,1200,1300,1400], same_symbol=True)
    state, _ = consume_passive_cohort_batch(frames, now=at, activated_at=activated)
    before = copy.deepcopy(state)
    later = at + timedelta(seconds=6)
    next_state, _ = consume_passive_cohort_batch(
        _passive_batch(later, [1.1] * 5, [1000,1100,1200,1300,1400], same_symbol=True),
        state, now=later, activated_at=activated)
    assert state == before
    next(iter(next_state['token_frames'].values()))[0]['price_usd'] = 99
    next(iter(next_state['clone_episodes'].values()))['handoff_state']['handoff_used'] = True
    assert state == before


def test_passive_relative_pilot_uses_three_members_own_previous_frames():
    activated = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
    at0 = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    state, signals = consume_passive_cohort_batch(
        _passive_batch(at0, [1, 1, 1], [1_000, 1_000, 1_000]),
        now=at0,
        activated_at=activated,
    )
    assert signals == {} and state["resilience_episodes"] == {}

    at1 = at0 + timedelta(seconds=6)
    state, signals = consume_passive_cohort_batch(
        _passive_batch(at1, [1.01, .9, .8], [1_050, 900, 800]),
        state,
        now=at1,
        activated_at=activated,
    )
    assert signals == {}
    assert len(state["resilience_episodes"]) == 1

    at2 = at1 + timedelta(seconds=6)
    state, signals = consume_passive_cohort_batch(
        _passive_batch(at2, [1.02, .85, .75], [1_100, 850, 750]),
        state,
        now=at2,
        activated_at=activated,
    )
    assert "observed_set_relative_resilience_control_v1" in signals[("solana:TOKEN0", "POOL0")]

    at3 = at2 + timedelta(seconds=6)
    state, signals = consume_passive_cohort_batch(
        _passive_batch(at3, [1.03, .8, .7], [1_150, 800, 700]),
        state,
        now=at3,
        activated_at=activated,
    )
    assert "observed_set_relative_resilience_candidate_v1" in signals[("solana:TOKEN0", "POOL0")]
    evidence = signals[("solana:TOKEN0", "POOL0")]["observed_set_relative_resilience_candidate_v1"]
    assert evidence["scope"] == "bounded_passive_observed_set_not_full_chain"


def test_passive_adapter_bounds_tokens_histories_and_total_episodes():
    activated = datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
    state = {}
    for step in range(4):
        now = datetime(2026, 9, 6, 10, step, tzinfo=UTC)
        batch = []
        for index in range(60):
            row = _candidate(now, step * 60 + index, symbol=f"unique{step}-{index}")
            row["is_held"] = False
            batch.append(row)
        state, signals = consume_passive_cohort_batch(
            batch, state, now=now, activated_at=activated
        )
        assert signals == {}
    assert len(state["token_frames"]) <= 200
    assert all(len(history) <= 3 for history in state["token_frames"].values())
    assert len(state["clone_episodes"]) + len(state["resilience_episodes"]) <= 5
