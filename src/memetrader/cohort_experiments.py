"""Strictly-forward cohort experiment definitions and pure selectors.

The caller supplies bounded observations already held locally.  This module
does not fetch data, persist state, register policies, or execute trades.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from itertools import islice
from statistics import median
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .capital_policies import capital_policies
from .models import CHAIN_MEME_MIN_POOL_LIQUIDITY_USD


WAIT = "WAIT"
OBSERVE = "OBSERVE"
FROZEN = "FROZEN"
ARMED = "ARMED"
SELECT = "SELECT"
CohortResult = tuple[str, str, dict[str, Any], dict[str, Any]]

CLONE_EPISODE_KIND = "frozen_same_symbol_clone_episode/v1"
MAX_CANDIDATES = 25

CLONE_EPISODE_POLICY = MappingProxyType({
    "version": "clone-episode-leaders/v1",
    "minimum_candidates": 5,
    "maximum_candidates": MAX_CANDIDATES,
    "maximum_discovery_span_seconds": 600.0,
    "maximum_snapshot_age_seconds": 30.0,
})

RELATIVE_RESILIENCE_POLICY = MappingProxyType({
    "version": "observed-set-relative-resilience/v1",
    "minimum_candidates": 5,
    "maximum_candidates": MAX_CANDIDATES,
    "minimum_down_share": 0.60,
    "maximum_median_price_return": 0.0,
    "minimum_confirmation_rounds": 2,
    "minimum_round_span_seconds": 5.0,
    "maximum_round_skew_seconds": 5.0,
    "maximum_snapshot_age_seconds": 30.0,
})

CLONE_HANDOFF_POLICY = MappingProxyType({
    "version": "clone-liquidity-handoff/v1",
    "minimum_confirmation_rounds": 2,
    "minimum_round_span_seconds": 5.0,
    "maximum_round_skew_seconds": 5.0,
    "maximum_snapshot_age_seconds": 30.0,
})

PASSIVE_RELATIVE_RESILIENCE_POLICY = MappingProxyType({
    **dict(RELATIVE_RESILIENCE_POLICY),
    "version": "observed-set-relative-resilience/passive-pilot-v1",
    "minimum_candidates": 3,
    "maximum_candidates": 4,
})

PASSIVE_MAX_TOKENS = 200
PASSIVE_HISTORY_PER_TOKEN = 3
PASSIVE_MAX_EPISODES = 5
PASSIVE_EPISODE_TTL_SECONDS = 600.0


def cohort_experiment_policies() -> list[dict[str, Any]]:
    """Independent forward Paper policies; all use common safety and settlement."""
    parent = next(
        policy for policy in capital_policies()
        if policy["arm_id"] == "effective_breadth_v1"
    )
    specs = (
        (
            "clone_liquidity_leader_v1",
            "clone_liquidity_leader",
            "clone_initial_leader",
            "same_frozen_episode_not_same_buy",
            [],
        ),
        (
            "clone_m5volume_leader_v1",
            "clone_m5volume_leader",
            "clone_initial_leader",
            "same_frozen_episode_not_same_buy",
            [],
        ),
        (
            "clone_consensus_leader_v2",
            "clone_consensus_leader",
            "clone_consensus_leader",
            "same_frozen_episode_unique_liquidity_and_m5volume_leader_not_same_buy",
            [],
        ),
        (
            "observed_set_relative_resilience_candidate_v1",
            "observed_set_relative_resilience",
            "observed_set_relative_resilience",
            "same_initial_opportunity_different_entry_time_not_same_buy",
            [],
        ),
        (
            "observed_set_relative_resilience_control_v1",
            "observed_set_relative_resilience_control",
            "observed_set_relative_resilience",
            "same_initial_opportunity_different_entry_time_not_same_buy",
            [],
        ),
        (
            "clone_liquidity_handoff_v1",
            "clone_liquidity_handoff",
            "clone_liquidity_handoff",
            "same_initial_clone_episode_no_second_buy_control",
            ["clone_liquidity_leader_v1"],
        ),
    )
    policies: list[dict[str, Any]] = []
    for arm_id, direction, group, semantics, sources in specs:
        policy = copy.deepcopy(parent)
        policy.update({
            "arm_id": arm_id,
            "canonical_id": arm_id,
            "name": direction,
            "family": "cohort_forward_experiment",
            "description": "冻结同一初始机会的5U严格前向实验；尚未证明盈利。",
            "entry_family": direction,
            "source_entry_family": "cohort_observer",
            "entry_gate": "cohort_strict_forward_asof",
            "entry_match_mode": "isolated_cohort_observer",
            "paired_opportunity_group": group,
            "paired_opportunity_semantics": semantics,
            "notional_usd": 5.0,
            "source_arm_ids": sources,
            "required_inputs": [
                "bounded_local_observations",
                "exact_original_pool_identity",
                "next_independent_frame",
            ],
            "no_historical_backfill": True,
            "capital_experiment": False,
            "capital_exit_kind": None,
        })
        policy.pop("paired_entry_group", None)
        policy["entry_filter"] = {"direction": direction}
        if arm_id == "clone_consensus_leader_v2":
            policy['signal_origin_clock']='frozen_at'
            policy["entry_filter"]["max_concurrent_positions"] = 4
            policy.update(observer_only=False,decision_eligible=True,affects='paper_only',
                          evidence_status='FORWARD_HYPOTHESIS_NOT_ALPHA')
        if direction == "clone_liquidity_handoff":
            policy["opportunity_control_arm_id"] = "clone_liquidity_leader_v1"
        policies.append(policy)
    #136: reuse this exact cohort/next-frame pipeline, not a parallel trader.
    from .market_microstructure import BRANCH_LIMITS
    for arm in ('organic_early_flow_v1','organic_reawakening_flow_v1',
                'event_clone_narrative_reawakening_v1'):
        policy=copy.deepcopy(policies[2])
        limit=BRANCH_LIMITS.get(arm,dict(stake_usd=5,max_open=4))
        policy.update(arm_id=arm,canonical_id=arm,name=arm,entry_family=arm,
            notional_usd=limit['stake_usd'],paired_opportunity_group=arm,
            paired_opportunity_semantics='independent_frozen_episode_no_funded_duplicate_control',
            description='严格前向独立Paper假设；已有原池市场帧、共同安全门和后帧成交，不代表已证明盈利。',
            max_hold_minutes=15.0 if arm=='organic_early_flow_v1' else 30.0)
        policy['entry_filter']={'direction':arm,'max_concurrent_positions':limit['max_open']}
        policy['signal_origin_clock']='event_recorded_at' if arm=='event_clone_narrative_reawakening_v1' else 'signal_at'
        policies.append(policy)
    return policies


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _result(action: str, reason: str, state: Mapping[str, Any], evidence: Mapping[str, Any]) -> CohortResult:
    return action, reason, copy.deepcopy(dict(state)), copy.deepcopy(dict(evidence))


def _hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _receipt(
    row: Mapping[str, Any], decision: datetime, activated: datetime,
    maximum_age_seconds: float,
) -> tuple[datetime, datetime] | None:
    observed = _time(row.get("observed_at"))
    recorded = _time(row.get("recorded_at"))
    if (
        not observed
        or not recorded
        or not activated <= observed <= recorded <= decision
        or (decision - observed).total_seconds() > maximum_age_seconds
    ):
        return None
    return observed, recorded


def _identity(row: Mapping[str, Any]) -> tuple[str, str, str] | None:
    token_id = str(row.get("token_id") or "").strip()
    pair = str(row.get("pair_address") or "").strip()
    chain = str(row.get("chain") or "").strip().lower()
    if not token_id or not pair or not chain or ":" not in token_id:
        return None
    if token_id.partition(":")[0].lower() != chain:
        return None
    return token_id, pair, chain


def _bounded_rows(rows: Iterable[Mapping[str, Any]], maximum: int) -> list[Mapping[str, Any]] | None:
    supplied = list(islice(rows, maximum + 1))
    if len(supplied) > maximum or any(not isinstance(row, Mapping) for row in supplied):
        return None
    return supplied


def _market_candidate(
    row: Mapping[str, Any], decision: datetime, activated: datetime, maximum_age: float,
    *, require_volume: bool,
) -> dict[str, Any] | None:
    identity = _identity(row)
    receipt = _receipt(row, decision, activated, maximum_age)
    price = _number(row.get("price_usd", row.get("price")))
    liquidity = _number(row.get("liquidity_usd", row.get("liquidity")))
    volume = _number(row.get("volume_5m_usd"))
    lifecycle = str(row.get("lifecycle") or "").strip()
    symbol = str(row.get("normalized_symbol") or "").strip().casefold()
    if (
        not identity
        or not receipt
        or row.get("original_pool") is not True
        or price is None
        or price <= 0.0
        or liquidity is None
        or liquidity < 0.0
        or require_volume and (volume is None or volume < 0.0)
        or not lifecycle
        or not symbol
    ):
        return None
    token_id, pair, chain = identity
    observed, recorded = receipt
    return {
        "token_id": token_id,
        "pair_address": pair,
        "chain": chain,
        "lifecycle": lifecycle,
        "normalized_symbol": symbol,
        "observed_at": _stamp(observed),
        "recorded_at": _stamp(recorded),
        "price_usd": price,
        "liquidity_usd": liquidity,
        "volume_5m_usd": volume,
    }


def _unique_top(candidates: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
    ordered = sorted(candidates, key=lambda item: (-float(item[field]), item["token_id"]))
    if len(ordered) > 1 and ordered[0][field] == ordered[1][field]:
        return None
    return copy.deepcopy(ordered[0]) if ordered else None


def _validated_clone_episode(value: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or value.get("kind") != CLONE_EPISODE_KIND:
        return None
    payload = value.get("payload")
    if not isinstance(payload, Mapping) or not isinstance(payload.get("candidates"), list):
        return None
    candidates = payload["candidates"]
    if payload.get("candidate_set_hash") != _hash(candidates):
        return None
    identities = [(item.get("token_id"), item.get("pair_address")) for item in candidates]
    if len(identities) != len(set(identities)):
        return None
    return copy.deepcopy(dict(payload))


def freeze_clone_episode(
    candidates: Iterable[Mapping[str, Any]], *, episode_id: str,
    decision_at: Any, activated_at: Any,
    existing: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] = CLONE_EPISODE_POLICY,
) -> CohortResult:
    """Freeze one same-chain/lifecycle/symbol set and its two initial leaders."""
    if existing is not None:
        payload = _validated_clone_episode(existing)
        if payload is None or payload.get("episode_id") != str(episode_id):
            return _result(WAIT, "invalid_existing_clone_episode", {}, {})
        return _result(FROZEN, "clone_episode_already_frozen", existing, payload)

    decision, activated = _time(decision_at), _time(activated_at)
    maximum = int(policy["maximum_candidates"])
    supplied = _bounded_rows(candidates, maximum)
    if not decision or not activated or decision < activated or not str(episode_id).strip() or supplied is None:
        return _result(WAIT, "invalid_clone_episode_request", {}, {})
    parsed = [
        _market_candidate(
            row, decision, activated, float(policy["maximum_snapshot_age_seconds"]),
            require_volume=True,
        )
        for row in supplied
    ]
    if any(item is None for item in parsed) or len(parsed) < int(policy["minimum_candidates"]):
        return _result(WAIT, "clone_episode_insufficient_fresh_candidates", {}, {})
    rows = [item for item in parsed if item is not None]
    identities = [(item["token_id"], item["pair_address"]) for item in rows]
    if len(identities) != len(set(identities)) or len({pair for _, pair in identities}) != len(rows):
        return _result(WAIT, "clone_episode_duplicate_identity", {}, {})
    if len({(item["chain"], item["lifecycle"], item["normalized_symbol"]) for item in rows}) != 1:
        return _result(WAIT, "clone_episode_mixed_scope", {}, {})

    discovered = [_time(row.get("discovered_at")) for row in supplied]
    if any(value is None or not activated <= value <= decision for value in discovered):
        return _result(WAIT, "clone_episode_discovery_provenance_required", {}, {})
    observed_discoveries = [value for value in discovered if value is not None]
    if (max(observed_discoveries) - min(observed_discoveries)).total_seconds() > float(policy["maximum_discovery_span_seconds"]):
        return _result(WAIT, "clone_episode_discovery_span_exceeded", {}, {})

    rows.sort(key=lambda item: (item["token_id"], item["pair_address"]))
    liquidity_leader = _unique_top(rows, "liquidity_usd")
    volume_leader = _unique_top(rows, "volume_5m_usd")
    candidate_hash = _hash(rows)
    payload = {
        "episode_id": str(episode_id).strip(),
        "frozen_at": _stamp(decision),
        "chain": rows[0]["chain"],
        "lifecycle": rows[0]["lifecycle"],
        "normalized_symbol": rows[0]["normalized_symbol"],
        "candidate_count": len(rows),
        "candidate_set_hash": candidate_hash,
        "candidates": rows,
        "liquidity_leader": liquidity_leader,
        "m5volume_leader": volume_leader,
        "leaders_overlap": bool(
            liquidity_leader and volume_leader
            and liquidity_leader["token_id"] == volume_leader["token_id"]
        ),
    }
    payload["differential_pair_eligible"] = bool(
        liquidity_leader and volume_leader and not payload["leaders_overlap"]
    )
    state = {
        "kind": CLONE_EPISODE_KIND,
        "source_key": f"clone-episode|{candidate_hash[:24]}",
        "observed_at": _stamp(decision),
        "recorded_at": _stamp(decision),
        "payload": payload,
    }
    reason = "clone_episode_frozen" if liquidity_leader and volume_leader else "clone_episode_frozen_without_unique_leaders"
    return _result(FROZEN, reason, state, payload)


def _entry_frame(
    frame: Mapping[str, Any], target: Mapping[str, Any], *, after: datetime,
    decision: datetime, activated: datetime, maximum_age: float,
    minimum_liquidity: float = CHAIN_MEME_MIN_POOL_LIQUIDITY_USD,
) -> dict[str, Any] | None:
    parsed = _market_candidate(frame, decision, activated, maximum_age, require_volume=False)
    if (
        parsed is None
        or parsed["token_id"] != target.get("token_id")
        or parsed["pair_address"] != target.get("pair_address")
        or parsed["chain"] != target.get("chain")
        or parsed["lifecycle"] != target.get("lifecycle")
        or _time(parsed["observed_at"]) <= after
        or parsed["liquidity_usd"] < minimum_liquidity
    ):
        return None
    return parsed


def evaluate_clone_leader_entry(
    frozen_episode: Mapping[str, Any], frame: Mapping[str, Any], *,
    leader_kind: str, decision_at: Any, activated_at: Any,
    policy: Mapping[str, Any] = CLONE_EPISODE_POLICY,
) -> CohortResult:
    payload = _validated_clone_episode(frozen_episode)
    decision, activated = _time(decision_at), _time(activated_at)
    field = {"liquidity": "liquidity_leader", "m5volume": "m5volume_leader"}.get(leader_kind)
    target = payload.get(field) if payload and field else None
    frozen_at = _time(payload.get("frozen_at")) if payload else None
    if not payload or not decision or not activated or not isinstance(target, Mapping) or not frozen_at:
        return _result(WAIT, "clone_leader_not_available", {}, {})
    parsed = _entry_frame(
        frame, target, after=frozen_at, decision=decision, activated=activated,
        maximum_age=float(policy["maximum_snapshot_age_seconds"]),
        minimum_liquidity=float(policy.get("min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD)),
    )
    if parsed is None:
        return _result(WAIT, "awaiting_clone_leader_next_original_pool_frame", {}, {"target": target})
    return _result(SELECT, "clone_leader_next_frame_confirmed", {}, {
        "episode_id": payload["episode_id"], "leader_kind": leader_kind,
        "selected": target, "entry_frame": parsed,
        "differential_pair_eligible": payload["differential_pair_eligible"],
    })


def evaluate_clone_consensus_leader_entry(
    frozen_episode: Mapping[str, Any], frame: Mapping[str, Any], *,
    decision_at: Any, activated_at: Any,
    policy: Mapping[str, Any] = CLONE_EPISODE_POLICY,
) -> CohortResult:
    """Select only a frozen unique leader shared by liquidity and m5 volume."""
    payload = _validated_clone_episode(frozen_episode)
    decision, activated = _time(decision_at), _time(activated_at)
    frozen_at = _time(payload.get("frozen_at")) if payload else None
    if not payload or not decision or not activated or not frozen_at or frozen_at < activated:
        return _result(WAIT, "clone_consensus_leader_not_available", {}, {})
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return _result(WAIT, "clone_consensus_leader_not_available", {}, {})
    liquidity_leader = _unique_top(candidates, "liquidity_usd")
    volume_leader = _unique_top(candidates, "volume_5m_usd")
    if (
        liquidity_leader is None
        or volume_leader is None
        or (liquidity_leader["token_id"], liquidity_leader["pair_address"])
        != (volume_leader["token_id"], volume_leader["pair_address"])
    ):
        return _result(WAIT, "clone_consensus_leader_not_unique_or_not_shared", {}, {
            "episode_id": payload["episode_id"],
        })
    parsed = _entry_frame(
        frame, liquidity_leader, after=frozen_at, decision=decision, activated=activated,
        maximum_age=float(policy["maximum_snapshot_age_seconds"]),
        minimum_liquidity=float(policy.get("min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD)),
    )
    if parsed is None:
        return _result(WAIT, "awaiting_clone_consensus_leader_next_original_pool_frame", {}, {
            "target": liquidity_leader,
        })
    return _result(SELECT, "clone_consensus_leader_next_frame_confirmed", {}, {
        "episode_id": payload["episode_id"],
        "frozen_at": payload["frozen_at"],
        "selected": liquidity_leader,
        "entry_frame": parsed,
        "unique_liquidity_and_m5volume_leader": True,
    })


def _resilience_row(
    row: Mapping[str, Any], decision: datetime, activated: datetime, maximum_age: float,
) -> dict[str, Any] | None:
    parsed = _market_candidate(row, decision, activated, maximum_age, require_volume=False)
    price_return = _number(row.get("price_return"))
    liquidity_return = _number(row.get("liquidity_return"))
    prior_low = _number(row.get("prior_low_price_usd"))
    if parsed is None or price_return is None or liquidity_return is None or prior_low is None or prior_low <= 0.0:
        return None
    parsed.update({
        "price_return": price_return,
        "liquidity_return": liquidity_return,
        "prior_low_price_usd": prior_low,
    })
    return parsed


def _resilience_target(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [
        row for row in rows
        if row["price_usd"] >= row["prior_low_price_usd"] and row["liquidity_return"] >= 0.0
    ]
    ordered = sorted(
        eligible,
        key=lambda row: (-row["price_return"], -row["liquidity_return"], row["token_id"]),
    )
    if len(ordered) > 1 and (
        ordered[0]["price_return"], ordered[0]["liquidity_return"]
    ) == (ordered[1]["price_return"], ordered[1]["liquidity_return"]):
        return None
    return copy.deepcopy(ordered[0]) if ordered else None


def evaluate_relative_resilience_round(
    observations: Iterable[Mapping[str, Any]], state: Mapping[str, Any] | None = None,
    *, round_id: str, decision_at: Any, activated_at: Any,
    policy: Mapping[str, Any] = RELATIVE_RESILIENCE_POLICY,
) -> CohortResult:
    """Freeze one observed set and arm control/candidate at their own times."""
    decision, activated = _time(decision_at), _time(activated_at)
    supplied = _bounded_rows(observations, int(policy["maximum_candidates"]))
    new_state = copy.deepcopy(dict(state or {}))
    if not decision or not activated or decision < activated or not str(round_id).strip() or supplied is None:
        return _result(WAIT, "invalid_relative_resilience_round", new_state, {})
    rows = [
        _resilience_row(row, decision, activated, float(policy["maximum_snapshot_age_seconds"]))
        for row in supplied
    ]
    if any(row is None for row in rows) or len(rows) < int(policy["minimum_candidates"]):
        return _result(WAIT, "relative_resilience_insufficient_fresh_members", new_state, {})
    parsed = [row for row in rows if row is not None]
    if len({(row["token_id"], row["pair_address"]) for row in parsed}) != len(parsed):
        return _result(WAIT, "relative_resilience_duplicate_identity", new_state, {})
    scopes = {(row["chain"], row["lifecycle"]) for row in parsed}
    if len(scopes) != 1:
        return _result(WAIT, "relative_resilience_mixed_scope", new_state, {})
    observed_times = [_time(row["observed_at"]) for row in parsed]
    if (max(observed_times) - min(observed_times)).total_seconds() > float(policy["maximum_round_skew_seconds"]):
        return _result(WAIT, "relative_resilience_round_not_simultaneous", new_state, {})
    parsed.sort(key=lambda row: (row["token_id"], row["pair_address"]))
    identities = [(row["token_id"], row["pair_address"]) for row in parsed]
    identity_hash = _hash(identities)

    if new_state.get("identity_hash") and new_state["identity_hash"] != identity_hash:
        return _result(WAIT, "relative_resilience_frozen_set_changed", new_state, {})
    if new_state.get("last_round_id") == str(round_id):
        return _result(WAIT, "duplicate_relative_resilience_round", new_state, {})
    target = new_state.get("initial_target")
    if not isinstance(target, Mapping):
        target = _resilience_target(parsed)
        if target is None:
            return _result(WAIT, "relative_resilience_no_unique_target", new_state, {})
        new_state.update({
            "identity_hash": identity_hash,
            "frozen_identities": identities,
            "chain": parsed[0]["chain"],
            "lifecycle": parsed[0]["lifecycle"],
            "initial_target": target,
            "control_armed_at": _stamp(max(observed_times)),
        })
    by_identity = {(row["token_id"], row["pair_address"]): row for row in parsed}
    target_row = by_identity.get((target["token_id"], target["pair_address"]))
    if target_row is None:
        return _result(WAIT, "relative_resilience_target_missing", new_state, {})

    round_observed = max(observed_times)
    prior_at = _time(new_state.get("last_accepted_at"))
    if prior_at and (round_observed - prior_at).total_seconds() < float(policy["minimum_round_span_seconds"]):
        return _result(WAIT, "relative_resilience_round_too_close", new_state, {})
    down_share = sum(row["price_return"] < 0.0 for row in parsed) / len(parsed)
    median_return = median(row["price_return"] for row in parsed)
    weak_environment = bool(
        down_share >= float(policy["minimum_down_share"])
        and median_return < float(policy["maximum_median_price_return"])
    )
    target_holds = bool(
        target_row["price_usd"] >= target_row["prior_low_price_usd"]
        and target_row["liquidity_return"] >= 0.0
    )
    streak = int(new_state.get("candidate_streak") or 0) + 1 if weak_environment and target_holds else 0
    new_state.update({
        "last_round_id": str(round_id),
        "last_accepted_at": _stamp(round_observed),
        "candidate_streak": streak,
    })
    if streak >= int(policy["minimum_confirmation_rounds"]):
        new_state["candidate_armed_at"] = _stamp(round_observed)
    evidence = {
        "round_id": str(round_id),
        "candidate_count": len(parsed),
        "observed_set_scope": {"chain": parsed[0]["chain"], "lifecycle": parsed[0]["lifecycle"]},
        "down_share": down_share,
        "median_price_return": median_return,
        "weak_environment": weak_environment,
        "initial_target": target,
        "target_holds_price_and_liquidity": target_holds,
        "candidate_streak": streak,
        "control_armed_at": new_state["control_armed_at"],
        "candidate_armed_at": new_state.get("candidate_armed_at"),
    }
    if new_state.get("candidate_armed_at"):
        return _result(ARMED, "relative_resilience_candidate_armed", new_state, evidence)
    return _result(OBSERVE, "relative_resilience_control_armed", new_state, evidence)


def evaluate_relative_resilience_entry(
    state: Mapping[str, Any], frame: Mapping[str, Any], *, arm_kind: str,
    decision_at: Any, activated_at: Any,
    policy: Mapping[str, Any] = RELATIVE_RESILIENCE_POLICY,
) -> CohortResult:
    decision, activated = _time(decision_at), _time(activated_at)
    target = state.get("initial_target") if isinstance(state, Mapping) else None
    armed_key = {"control": "control_armed_at", "candidate": "candidate_armed_at"}.get(arm_kind)
    armed_at = _time(state.get(armed_key)) if armed_key and isinstance(state, Mapping) else None
    if not decision or not activated or not isinstance(target, Mapping) or not armed_at:
        return _result(WAIT, "relative_resilience_arm_not_ready", state, {})
    parsed = _entry_frame(
        frame, target, after=armed_at, decision=decision, activated=activated,
        maximum_age=float(policy["maximum_snapshot_age_seconds"]),
        minimum_liquidity=float(policy.get("min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD)),
    )
    if parsed is None:
        return _result(WAIT, "awaiting_relative_resilience_next_original_pool_frame", state, {"target": target})
    return _result(SELECT, "relative_resilience_next_frame_confirmed", state, {
        "arm_kind": arm_kind, "selected": target, "entry_frame": parsed,
        "paired_opportunity_semantics": "same_initial_opportunity_not_same_buy",
    })


def _handoff_round(
    frozen_payload: Mapping[str, Any], observations: Iterable[Mapping[str, Any]],
    decision: datetime, activated: datetime, policy: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], datetime] | None:
    supplied = _bounded_rows(observations, len(frozen_payload["candidates"]))
    if supplied is None or len(supplied) != len(frozen_payload["candidates"]):
        return None
    parsed = [
        _market_candidate(row, decision, activated, float(policy["maximum_snapshot_age_seconds"]), require_volume=False)
        for row in supplied
    ]
    if any(row is None for row in parsed):
        return None
    rows = [row for row in parsed if row is not None]
    frozen_ids = {(row["token_id"], row["pair_address"]) for row in frozen_payload["candidates"]}
    if {(row["token_id"], row["pair_address"]) for row in rows} != frozen_ids:
        return None
    if any(row["chain"] != frozen_payload["chain"] or row["lifecycle"] != frozen_payload["lifecycle"] for row in rows):
        return None
    observed = [_time(row["observed_at"]) for row in rows]
    if (max(observed) - min(observed)).total_seconds() > float(policy["maximum_round_skew_seconds"]):
        return None
    rows.sort(key=lambda row: (row["token_id"], row["pair_address"]))
    return rows, max(observed)


def evaluate_clone_handoff_round(
    frozen_episode: Mapping[str, Any], closed_leader: Mapping[str, Any],
    observations: Iterable[Mapping[str, Any]], state: Mapping[str, Any] | None = None,
    *, round_id: str, decision_at: Any, activated_at: Any,
    policy: Mapping[str, Any] = CLONE_HANDOFF_POLICY,
) -> CohortResult:
    """Arm one liquidity-leadership handoff inside the original frozen set."""
    payload = _validated_clone_episode(frozen_episode)
    decision, activated = _time(decision_at), _time(activated_at)
    new_state = copy.deepcopy(dict(state or {}))
    old = payload.get("liquidity_leader") if payload else None
    closed_at = _time(closed_leader.get("closed_at"))
    closed_recorded = _time(closed_leader.get("closed_recorded_at"))
    if (
        not payload or not decision or not activated or not str(round_id).strip()
        or not isinstance(old, Mapping) or not closed_at or not closed_recorded
        or not activated <= closed_at <= closed_recorded <= decision
        or closed_leader.get("token_id") != old.get("token_id")
        or closed_leader.get("pair_address") != old.get("pair_address")
    ):
        return _result(WAIT, "invalid_clone_handoff_context", new_state, {})
    if new_state.get("handoff_used") is True:
        return _result(WAIT, "clone_handoff_already_used", new_state, {})
    if new_state.get("last_round_id") == str(round_id):
        return _result(WAIT, "duplicate_clone_handoff_round", new_state, {})
    current = _handoff_round(payload, observations, decision, activated, policy)
    if current is None or current[1] <= closed_recorded:
        return _result(WAIT, "clone_handoff_full_frozen_set_required", new_state, {})
    rows, round_observed = current
    previous = new_state.get("previous_round")
    current_values = {
        f"{row['token_id']}|{row['pair_address']}": {
            "token_id": row["token_id"], "pair_address": row["pair_address"],
            "chain": row["chain"], "lifecycle": row["lifecycle"],
            "normalized_symbol": row["normalized_symbol"],
            "price_usd": row["price_usd"], "liquidity_usd": row["liquidity_usd"],
        }
        for row in rows
    }
    if not isinstance(previous, Mapping):
        new_state.update({
            "last_round_id": str(round_id),
            "last_accepted_at": _stamp(round_observed),
            "previous_round": current_values,
            "handoff_streak": 0,
        })
        return _result(OBSERVE, "clone_handoff_baseline_recorded", new_state, {})
    prior_at = _time(new_state.get("last_accepted_at"))
    if not prior_at or (round_observed - prior_at).total_seconds() < float(policy["minimum_round_span_seconds"]):
        return _result(WAIT, "clone_handoff_round_too_close", new_state, {})

    old_key = f"{old['token_id']}|{old['pair_address']}"
    old_now, old_prior = current_values[old_key], previous.get(old_key)
    if not isinstance(old_prior, Mapping):
        return _result(WAIT, "clone_handoff_old_leader_missing", new_state, {})
    old_weak = bool(
        old_now["price_usd"] < float(old_prior["price_usd"])
        and old_now["liquidity_usd"] <= float(old_prior["liquidity_usd"])
    )
    expanding: list[dict[str, Any]] = []
    for key, row in current_values.items():
        prior = previous.get(key)
        if key != old_key and isinstance(prior, Mapping) and (
            row["price_usd"] > float(prior["price_usd"])
            and row["liquidity_usd"] > float(prior["liquidity_usd"])
        ):
            expanding.append(row)
    target = _unique_top(expanding, "liquidity_usd") if old_weak else None
    prior_target = new_state.get("handoff_target")
    same_target = bool(
        target and isinstance(prior_target, Mapping)
        and target["token_id"] == prior_target.get("token_id")
        and target["pair_address"] == prior_target.get("pair_address")
    )
    streak = int(new_state.get("handoff_streak") or 0) + 1 if target and same_target else (1 if target else 0)
    new_state.update({
        "last_round_id": str(round_id),
        "last_accepted_at": _stamp(round_observed),
        "previous_round": current_values,
        "handoff_target": target,
        "handoff_streak": streak,
    })
    evidence = {
        "episode_id": payload["episode_id"], "old_leader": old,
        "old_leader_weakened": old_weak, "handoff_target": target,
        "handoff_streak": streak, "basis": "reported_price_and_liquidity_not_actual_capital_flow",
    }
    if target and streak >= int(policy["minimum_confirmation_rounds"]):
        new_state.update({
            "handoff_armed_at": _stamp(round_observed),
            "handoff_transition": {
                "old_token_id": old["token_id"], "new_token_id": target["token_id"],
                "armed_at": _stamp(round_observed),
            },
        })
        return _result(ARMED, "clone_liquidity_handoff_armed", new_state, evidence)
    return _result(OBSERVE, "clone_liquidity_handoff_monitoring", new_state, evidence)


def evaluate_clone_handoff_entry(
    frozen_episode: Mapping[str, Any], state: Mapping[str, Any], frame: Mapping[str, Any],
    *, decision_at: Any, activated_at: Any,
    policy: Mapping[str, Any] = CLONE_HANDOFF_POLICY,
) -> CohortResult:
    payload = _validated_clone_episode(frozen_episode)
    decision, activated = _time(decision_at), _time(activated_at)
    target = state.get("handoff_target") if isinstance(state, Mapping) else None
    armed_at = _time(state.get("handoff_armed_at")) if isinstance(state, Mapping) else None
    if not payload or not decision or not activated or not isinstance(target, Mapping) or not armed_at:
        return _result(WAIT, "clone_handoff_not_armed", state, {})
    parsed = _entry_frame(
        frame, target, after=armed_at, decision=decision, activated=activated,
        maximum_age=float(policy["maximum_snapshot_age_seconds"]),
        minimum_liquidity=float(policy.get("min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD)),
    )
    if parsed is None:
        return _result(WAIT, "awaiting_clone_handoff_next_original_pool_frame", state, {"target": target})
    new_state = copy.deepcopy(dict(state))
    new_state["handoff_used"] = True
    return _result(SELECT, "clone_handoff_next_frame_confirmed", new_state, {
        "episode_id": payload["episode_id"], "selected": target,
        "entry_frame": parsed, "handoff_transition": state.get("handoff_transition"),
    })


def _passive_frame(
    row: Mapping[str, Any], decision: datetime, activated: datetime,
) -> dict[str, Any] | None:
    parsed = _market_candidate(
        row, decision, activated,
        max(CLONE_EPISODE_POLICY["maximum_snapshot_age_seconds"],
            PASSIVE_RELATIVE_RESILIENCE_POLICY["maximum_snapshot_age_seconds"]),
        require_volume=False,
    )
    if parsed is None:
        return None
    discovered = _time(row.get("discovered_at") or row.get("first_seen_at"))
    if discovered is not None and not activated <= discovered <= decision:
        return None
    parsed.update({
        "discovered_at": _stamp(discovered) if discovered else None,
        "original_pool": True,
        "is_held": row.get("is_held") is True,
        "volume_5m_usd": _number(row.get("volume_5m_usd")),
    })
    return parsed


def _decision_key(episode_id: str, arm_id: str) -> str:
    return f"{episode_id}|{arm_id}"


def _emit_signal(
    signals: dict[tuple[str, str], dict[str, Any]], *, episode_id: str,
    arm_id: str, evidence: Mapping[str, Any], already_bought: set[str],
) -> None:
    key = _decision_key(episode_id, arm_id)
    selected = evidence.get("selected")
    if key in already_bought or not isinstance(selected, Mapping):
        return
    identity = (str(selected.get("token_id") or ""), str(selected.get("pair_address") or ""))
    if not all(identity):
        return
    signals.setdefault(identity, {})[arm_id] = {
        "episode_id": episode_id,
        "decision_key": key,
        "selected": copy.deepcopy(dict(selected)),
        "decision_evidence": copy.deepcopy(dict(evidence)),
        "scope": "bounded_passive_observed_set_not_full_chain",
    }


def _passive_resilience_row(
    current: Mapping[str, Any], history: list[Mapping[str, Any]],
) -> dict[str, Any] | None:
    if len(history) < 2:
        return None
    previous = history[-2]
    prior_price = _number(previous.get("price_usd"))
    prior_liquidity = _number(previous.get("liquidity_usd"))
    price = _number(current.get("price_usd"))
    liquidity = _number(current.get("liquidity_usd"))
    prior_prices = [_number(item.get("price_usd")) for item in history[:-1]]
    if (
        None in {prior_price, prior_liquidity, price, liquidity}
        or prior_price <= 0.0
        or prior_liquidity <= 0.0
        or any(value is None or value <= 0.0 for value in prior_prices)
    ):
        return None
    return {
        **copy.deepcopy(dict(current)),
        "price_return": price / prior_price - 1.0,
        "liquidity_return": liquidity / prior_liquidity - 1.0,
        "prior_low_price_usd": min(value for value in prior_prices if value is not None),
    }


def consume_passive_cohort_batch(
    frames: Iterable[Mapping[str, Any]], state: Mapping[str, Any] | None = None,
    *, now: Any, activated_at: Any,
    closed_leaders: Mapping[str, Mapping[str, Any]] | None = None,
    already_bought: Iterable[str] = (),
    min_pool_liquidity_usd: float = CHAIN_MEME_MIN_POOL_LIQUIDITY_USD,
) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    """Consume one existing natural quote batch without requesting more data.

    State is JSON-serializable and bounded to 200 identities, three distinct
    observations per identity and five total active clone/resilience episodes.
    ``closed_leaders`` is keyed by clone episode id. ``already_bought`` contains
    the returned decision keys after the caller completes an entry.
    """
    decision, activated = _time(now), _time(activated_at)
    new_state = copy.deepcopy(dict(state or {}))
    signals: dict[tuple[str, str], dict[str, Any]] = {}
    supplied = _bounded_rows(frames, PASSIVE_MAX_TOKENS)
    if not decision or not activated or decision < activated or supplied is None:
        return new_state, signals
    bought = {str(value) for value in already_bought}
    closures = closed_leaders if isinstance(closed_leaders, Mapping) else {}
    cutoff = decision.timestamp() - PASSIVE_EPISODE_TTL_SECONDS

    histories = new_state.get("token_frames")
    # new_state already owns a deep copy of every nested row/episode.
    histories = histories if isinstance(histories, Mapping) else {}
    for key in list(histories):
        rows = histories.get(key)
        if not isinstance(rows, list):
            histories.pop(key, None)
            continue
        kept = [row for row in rows if (_time(row.get("observed_at")) or datetime.min.replace(tzinfo=timezone.utc)).timestamp() >= cutoff]
        if kept:
            histories[key] = kept[-PASSIVE_HISTORY_PER_TOKEN:]
        else:
            histories.pop(key, None)

    clone_episodes = new_state.get("clone_episodes")
    clone_episodes = clone_episodes if isinstance(clone_episodes, Mapping) else {}
    resilience_episodes = new_state.get("resilience_episodes")
    resilience_episodes = resilience_episodes if isinstance(resilience_episodes, Mapping) else {}
    for episodes in (clone_episodes, resilience_episodes):
        for episode_id in list(episodes):
            expires = _time((episodes[episode_id] or {}).get("expires_at")) if isinstance(episodes[episode_id], Mapping) else None
            if not expires or expires <= decision:
                episodes.pop(episode_id, None)

    current_by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in supplied:
        parsed = _passive_frame(raw, decision, activated)
        if parsed is None:
            continue
        identity = (parsed["token_id"], parsed["pair_address"])
        key = f"{identity[0]}|{identity[1]}"
        history = histories.get(key)
        history = history if isinstance(history, list) else []
        observed = parsed["observed_at"]
        if any(item.get("observed_at") == observed for item in history):
            continue
        history.append(parsed)
        history.sort(key=lambda item: _time(item["observed_at"]))
        histories[key] = history[-PASSIVE_HISTORY_PER_TOKEN:]
        prior = current_by_identity.get(identity)
        if prior is None or _time(parsed["observed_at"]) > _time(prior["observed_at"]):
            current_by_identity[identity] = parsed

    if len(histories) > PASSIVE_MAX_TOKENS:
        ordered = sorted(
            histories.items(),
            key=lambda item: _time(item[1][-1]["observed_at"]),
            reverse=True,
        )
        histories = dict(ordered[:PASSIVE_MAX_TOKENS])
    new_state["token_frames"] = histories
    new_state["clone_episodes"] = clone_episodes
    new_state["resilience_episodes"] = resilience_episodes
    if not current_by_identity:
        return new_state, signals

    current_rows = list(current_by_identity.values())

    # Existing clone episodes consume only members that naturally reappear in
    # this same batch. Missing members never trigger a compensating request.
    for episode_id, episode in clone_episodes.items():
        frozen = episode.get("frozen") if isinstance(episode, Mapping) else None
        payload = _validated_clone_episode(frozen) if isinstance(frozen, Mapping) else None
        if not payload:
            continue
        by_identity = {(row["token_id"], row["pair_address"]): row for row in current_rows}
        for leader_kind, arm_id in (
            ("liquidity", "clone_liquidity_leader_v1"),
            ("m5volume", "clone_m5volume_leader_v1"),
        ):
            target = payload.get("liquidity_leader" if leader_kind == "liquidity" else "m5volume_leader")
            frame = by_identity.get((target.get("token_id"), target.get("pair_address"))) if isinstance(target, Mapping) else None
            if frame:
                action, _, _, evidence = evaluate_clone_leader_entry(
                    frozen, frame, leader_kind=leader_kind,
                    decision_at=decision, activated_at=activated,
                    policy={**CLONE_EPISODE_POLICY, "min_pool_liquidity_usd": min_pool_liquidity_usd},
                )
                if action == SELECT:
                    _emit_signal(signals, episode_id=episode_id, arm_id=arm_id,
                                 evidence=evidence, already_bought=bought)

        consensus_target = payload.get("liquidity_leader")
        consensus_frame = (
            by_identity.get((consensus_target.get("token_id"), consensus_target.get("pair_address")))
            if isinstance(consensus_target, Mapping) else None
        )
        if consensus_frame:
            action, _, _, evidence = evaluate_clone_consensus_leader_entry(
                frozen, consensus_frame, decision_at=decision, activated_at=activated,
                policy={**CLONE_EPISODE_POLICY, "min_pool_liquidity_usd": min_pool_liquidity_usd},
            )
            if action == SELECT:
                _emit_signal(signals, episode_id=episode_id,
                             arm_id="clone_consensus_leader_v2",
                             evidence=evidence, already_bought=bought)

        handoff_state = episode.get("handoff_state") if isinstance(episode.get("handoff_state"), Mapping) else {}
        if handoff_state.get("handoff_armed_at"):
            target = handoff_state.get("handoff_target")
            frame = by_identity.get((target.get("token_id"), target.get("pair_address"))) if isinstance(target, Mapping) else None
            handoff_key = _decision_key(episode_id, "clone_liquidity_handoff_v1")
            if handoff_key in bought:
                handoff_state["handoff_used"] = True
                episode["handoff_state"] = handoff_state
            elif frame:
                action, _, _, evidence = evaluate_clone_handoff_entry(
                    frozen, handoff_state, frame,
                    decision_at=decision, activated_at=activated,
                    policy={**CLONE_HANDOFF_POLICY, "min_pool_liquidity_usd": min_pool_liquidity_usd},
                )
                if action == SELECT:
                    _emit_signal(signals, episode_id=episode_id,
                                 arm_id="clone_liquidity_handoff_v1",
                                 evidence=evidence, already_bought=bought)
        else:
            closure = closures.get(episode_id)
            frozen_ids = {(row["token_id"], row["pair_address"]) for row in payload["candidates"]}
            full_round = [row for row in current_rows if (row["token_id"], row["pair_address"]) in frozen_ids]
            if isinstance(closure, Mapping) and len(full_round) == len(frozen_ids):
                round_id = "passive-handoff|" + _hash([(row["token_id"], row["observed_at"]) for row in full_round])[:24]
                _, _, updated, _ = evaluate_clone_handoff_round(
                    frozen, closure, full_round, handoff_state,
                    round_id=round_id, decision_at=decision, activated_at=activated,
                )
                episode["handoff_state"] = updated

    # Freeze S04 only when all five same-scope observations coexist naturally
    # in this batch. An active scope suppresses later-member replacement.
    active_clone_scopes = {str(value.get("scope_key")) for value in clone_episodes.values()}
    grouped_clone: dict[str, list[dict[str, Any]]] = {}
    for row in current_rows:
        if row.get("discovered_at") and row.get("volume_5m_usd") is not None:
            scope = f"{row['chain']}|{row['lifecycle']}|{row['normalized_symbol']}"
            grouped_clone.setdefault(scope, []).append(row)
    for scope, rows in sorted(grouped_clone.items()):
        if scope in active_clone_scopes or len(clone_episodes) + len(resilience_episodes) >= PASSIVE_MAX_EPISODES:
            continue
        if len(rows) < int(CLONE_EPISODE_POLICY["minimum_candidates"]):
            continue
        rows = sorted(rows, key=lambda row: (row["token_id"], row["pair_address"]))[:MAX_CANDIDATES]
        episode_id = "passive-clone-" + _hash([(row["token_id"], row["pair_address"], row["observed_at"]) for row in rows])[:24]
        action, _, frozen, _ = freeze_clone_episode(
            rows, episode_id=episode_id, decision_at=decision,
            activated_at=activated,
        )
        if action == FROZEN:
            clone_episodes[episode_id] = {
                "scope_key": scope,
                "expires_at": _stamp(decision + timedelta(seconds=PASSIVE_EPISODE_TTL_SECONDS)),
                "frozen": frozen,
                "handoff_state": {},
            }
            active_clone_scopes.add(scope)

    # S09 pilot uses 3-4 non-held members and each member's own immediately
    # preceding real frame; it never imports a member after the set is frozen.
    active_resilience_scopes = {str(value.get("scope_key")) for value in resilience_episodes.values()}
    grouped_resilience: dict[str, list[dict[str, Any]]] = {}
    for row in current_rows:
        scope = f"{row['chain']}|{row['lifecycle']}"
        if not row.get("is_held") or scope in active_resilience_scopes:
            grouped_resilience.setdefault(scope, []).append(row)
    for scope, batch_rows in sorted(grouped_resilience.items()):
        episode_id = next(
            (key for key, value in resilience_episodes.items() if value.get("scope_key") == scope),
            None,
        )
        if episode_id is None:
            if scope in active_resilience_scopes or len(clone_episodes) + len(resilience_episodes) >= PASSIVE_MAX_EPISODES:
                continue
            eligible = []
            for row in sorted(batch_rows, key=lambda value: (value["token_id"], value["pair_address"])):
                history = histories.get(f"{row['token_id']}|{row['pair_address']}", [])
                computed = _passive_resilience_row(row, history)
                if computed:
                    eligible.append(computed)
            eligible = eligible[:int(PASSIVE_RELATIVE_RESILIENCE_POLICY["maximum_candidates"])]
            if len(eligible) < int(PASSIVE_RELATIVE_RESILIENCE_POLICY["minimum_candidates"]):
                continue
            episode_id = "passive-resilience-" + _hash([(row["token_id"], row["pair_address"], row["observed_at"]) for row in eligible])[:24]
            episode = {
                "scope_key": scope,
                "expires_at": _stamp(decision + timedelta(seconds=PASSIVE_EPISODE_TTL_SECONDS)),
                "evaluator_state": {},
            }
            resilience_episodes[episode_id] = episode
            active_resilience_scopes.add(scope)
        else:
            episode = resilience_episodes[episode_id]

        evaluator_state = episode.get("evaluator_state") if isinstance(episode.get("evaluator_state"), Mapping) else {}
        frozen_ids = {
            tuple(identity) for identity in evaluator_state.get("frozen_identities", [])
        } if evaluator_state.get("frozen_identities") else None
        selected_rows = [row for row in batch_rows if frozen_ids is None or (row["token_id"], row["pair_address"]) in frozen_ids]
        computed_rows = []
        for row in selected_rows:
            history = histories.get(f"{row['token_id']}|{row['pair_address']}", [])
            computed = _passive_resilience_row(row, history)
            if computed:
                computed_rows.append(computed)
        if frozen_ids is not None and {(row["token_id"], row["pair_address"]) for row in computed_rows} != frozen_ids:
            continue
        computed_rows = sorted(computed_rows, key=lambda row: (row["token_id"], row["pair_address"]))[:4]
        if len(computed_rows) < 3:
            continue

        by_identity = {(row["token_id"], row["pair_address"]): row for row in current_rows}
        target = evaluator_state.get("initial_target")
        if isinstance(target, Mapping):
            target_frame = by_identity.get((target.get("token_id"), target.get("pair_address")))
            if target_frame:
                for arm_kind, arm_id in (
                    ("control", "observed_set_relative_resilience_control_v1"),
                    ("candidate", "observed_set_relative_resilience_candidate_v1"),
                ):
                    action, _, _, evidence = evaluate_relative_resilience_entry(
                        evaluator_state, target_frame, arm_kind=arm_kind,
                        decision_at=decision, activated_at=activated,
                        policy={**PASSIVE_RELATIVE_RESILIENCE_POLICY, "min_pool_liquidity_usd": min_pool_liquidity_usd},
                    )
                    if action == SELECT:
                        _emit_signal(signals, episode_id=episode_id, arm_id=arm_id,
                                     evidence=evidence, already_bought=bought)
        round_id = "passive-resilience|" + _hash([(row["token_id"], row["observed_at"]) for row in computed_rows])[:24]
        _, _, updated, _ = evaluate_relative_resilience_round(
            computed_rows, evaluator_state, round_id=round_id,
            decision_at=decision, activated_at=activated,
            policy=PASSIVE_RELATIVE_RESILIENCE_POLICY,
        )
        episode["evaluator_state"] = updated

    new_state["clone_episodes"] = clone_episodes
    new_state["resilience_episodes"] = resilience_episodes
    return new_state, signals


__all__ = [
    "WAIT", "OBSERVE", "FROZEN", "ARMED", "SELECT",
    "CLONE_EPISODE_KIND", "CLONE_EPISODE_POLICY",
    "RELATIVE_RESILIENCE_POLICY", "CLONE_HANDOFF_POLICY",
    "PASSIVE_RELATIVE_RESILIENCE_POLICY", "PASSIVE_MAX_TOKENS",
    "PASSIVE_HISTORY_PER_TOKEN", "PASSIVE_MAX_EPISODES",
    "cohort_experiment_policies", "freeze_clone_episode",
    "evaluate_clone_leader_entry", "evaluate_clone_consensus_leader_entry",
    "evaluate_relative_resilience_round",
    "evaluate_relative_resilience_entry", "evaluate_clone_handoff_round",
    "evaluate_clone_handoff_entry", "consume_passive_cohort_batch",
]
