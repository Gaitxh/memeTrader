"""Pure S07 mature-token acceptance policy and forward state evaluator."""
from __future__ import annotations

import copy
import hashlib
from types import MappingProxyType
from typing import Any, Mapping

from .forward_patterns import experiment_policies, pattern_signal
from .models import CHAIN_MEME_MIN_POOL_LIQUIDITY_USD, parse_time


MATURE_ACCEPTANCE_POLICY = MappingProxyType({
    "version": "mature-new-acceptance/v1",
    "minimum_pool_age_seconds": 21_600.0,
    "minimum_confirmation_gap_seconds": 15.0,
    "maximum_confirmation_gap_seconds": 90.0,
    "maximum_frame_age_seconds": 30.0,
})

_QUIET_REAWAKENING_POLICY = next(
    policy for policy in experiment_policies()
    if policy["arm_id"] == "experiment_quiet_reawakening_candidate_v1"
)


def mature_acceptance_policy() -> dict[str, Any]:
    """Return the sole 5U S07 arm without registering it."""
    policy = copy.deepcopy(_QUIET_REAWAKENING_POLICY)
    policy.update({
        "arm_id": "mature_new_acceptance_5u_v1",
        "canonical_id": "mature_new_acceptance_5u_v1",
        "name": "成熟币新事件接受确认 5U",
        "description": (
            "成熟池独立信息或自然再活跃事件后，两次原池价格/流动性确认；"
            "严格前向5U实验，尚未证明盈利。"
        ),
        "entry_family": "mature_new_acceptance",
        "source_entry_family": "mature_new_acceptance",
        "entry_match_mode": "isolated_pattern_observer",
        "entry_gate": "bounded_pattern_observer_v1",
        "entry_filter": {
            "direction": "mature_new_acceptance",
            "contract": MATURE_ACCEPTANCE_POLICY["version"],
            "event_kinds": ["independent_information", "natural_reactivation"],
            "minimum_pool_age_seconds": MATURE_ACCEPTANCE_POLICY["minimum_pool_age_seconds"],
            "minimum_confirmation_gap_seconds": MATURE_ACCEPTANCE_POLICY["minimum_confirmation_gap_seconds"],
            "maximum_confirmation_gap_seconds": MATURE_ACCEPTANCE_POLICY["maximum_confirmation_gap_seconds"],
        },
        "notional_usd": 5.0,
        "capital_experiment": False,
        "required_inputs": [
            "exact_pool_history",
            "qualified_narrative_or_raw_quiet_reactivation",
            "two_post_event_confirmations",
            "next_frame_trade",
        ],
        "source_arm_ids": ["experiment_quiet_reawakening_candidate_v1"],
        "no_historical_backfill": True,
    })
    policy.pop("capital_exit_kind", None)
    policy.pop("capital_exit_policy", None)
    return policy


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def _event_id(parts: list[Any]) -> str:
    payload = "|".join(str(value) for value in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _valid_history(
    history: list[dict[str, Any]], *, decision_at: Any, activated_at: Any,
    maximum_age_seconds: float,
) -> tuple[list[dict[str, Any]], str | None]:
    if not history or len(history) > 80:
        return [], "awaiting_bounded_exact_pool_history"
    decision, activated = parse_time(decision_at), parse_time(activated_at)
    last = history[-1]
    token_id = str(last.get("token_id") or "")
    pair_address = str(last.get("pair_address") or "")
    if not token_id or not pair_address:
        return [], "missing_exact_pool_identity"
    frames = []
    for frame in history:
        if frame.get("token_id") != token_id or frame.get("pair_address") != pair_address:
            continue
        try:
            observed = parse_time(frame.get("observed_at"))
            ingested = parse_time(frame.get("ingested_at"))
            recorded = parse_time(frame.get("recorded_at"))
        except (TypeError, ValueError):
            continue
        price = _number(frame.get("price"))
        liquidity = _number(frame.get("liquidity"))
        if (
            activated <= observed <= ingested <= recorded <= decision
            and price is not None and price > 0.0
            and liquidity is not None and liquidity >= 0.0
        ):
            frames.append(frame)
    if not frames or frames[-1] is not last:
        return [], "stale_or_noncausal_observation"
    if (decision - parse_time(last["observed_at"])).total_seconds() > maximum_age_seconds:
        return [], "stale_or_noncausal_observation"
    return frames, None


def _baseline_payload(frame: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": frame.get("id"),
        "observed_at": frame["observed_at"],
        "ingested_at": frame["ingested_at"],
        "recorded_at": frame["recorded_at"],
        "price_usd": float(frame["price"]),
        "liquidity_usd": float(frame["liquidity"]),
    }


def _qualified_narrative_event(
    narrative: Mapping[str, Any] | None, frames: list[dict[str, Any]],
    *, decision_at: Any, activated_at: Any, minimum_age: float,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if not isinstance(narrative, Mapping) or not frames:
        return None
    last = frames[-1]
    try:
        observed = parse_time(narrative.get("observed_at"))
        recorded = parse_time(narrative.get("recorded_at"))
        decision, activated = parse_time(decision_at), parse_time(activated_at)
    except (TypeError, ValueError):
        return None
    urls = narrative.get("source_urls")
    evidence_id = narrative.get("evidence_id")
    if (
        narrative.get("exact_token_relation") is not True
        or int(narrative.get("independent_sources") or 0) < 2
        or narrative.get("basis") != "original_source_contract_mentions_and_independent_fact_support"
        or not isinstance(urls, list) or len(set(str(url) for url in urls if url)) < 2
        or evidence_id is None
        or narrative.get("token_id") != last["token_id"]
        or narrative.get("pair_address") != last["pair_address"]
        or not activated <= observed <= recorded <= decision
    ):
        return None
    eligible = [
        frame for frame in frames
        if parse_time(frame["recorded_at"]) <= recorded
        and parse_time(frame["observed_at"]) < observed
    ]
    if not eligible:
        return None
    baseline = eligible[-1]
    baseline_age = _number(baseline.get("pool_age_seconds"))
    if baseline_age is None:
        return None
    age_at_event = baseline_age + max(
        0.0, (observed - parse_time(baseline["observed_at"])).total_seconds()
    )
    if age_at_event < minimum_age:
        return None
    event = {
        "event_kind": "independent_information",
        "event_id": f"narrative:{evidence_id}",
        "event_evidence_id": evidence_id,
        "event_observed_at": narrative["observed_at"],
        "event_recorded_at": narrative["recorded_at"],
        "verification_id": narrative.get("verification_id"),
        "source_urls": list(urls),
        "pool_age_seconds_at_event": age_at_event,
    }
    return event, _baseline_payload(baseline)


def _natural_reactivation_event(
    frames: list[dict[str, Any]], *, decision_at: Any, activated_at: Any,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    passed, _ = pattern_signal(
        frames,
        _QUIET_REAWAKENING_POLICY,
        decision_at=str(decision_at),
        activated_at=str(activated_at),
    )
    if not passed:
        return None
    trigger = frames[-1]
    trigger_at = parse_time(trigger["observed_at"])
    quiet = [
        frame for frame in frames
        if 120.0 <= (trigger_at - parse_time(frame["observed_at"])).total_seconds() <= 900.0
    ]
    if not quiet:
        return None
    baseline = quiet[-1]
    trigger_identity = trigger.get("id") or _event_id([
        trigger["token_id"], trigger["pair_address"],
        trigger["observed_at"], trigger["recorded_at"],
    ])
    event = {
        "event_kind": "natural_reactivation",
        "event_id": f"market:{trigger_identity}",
        "trigger_snapshot_id": trigger.get("id"),
        "event_observed_at": trigger["observed_at"],
        "event_recorded_at": trigger["recorded_at"],
        "pool_age_seconds_at_event": float(trigger["pool_age_seconds"]),
        "basis": "raw_exact_pool_quiet_reawakening_predicate_not_strategy_ready_state",
    }
    return event, _baseline_payload(baseline)


def evaluate_mature_acceptance(
    history: list[dict[str, Any]],
    narrative: Mapping[str, Any] | None = None,
    previous_state: Mapping[str, Any] | None = None,
    *,
    decision_at: Any,
    activated_at: Any,
    policy: Mapping[str, Any] = MATURE_ACCEPTANCE_POLICY,
) -> tuple[bool, str, dict[str, Any], dict[str, Any]]:
    """Advance one mature event through two confirmations.

    ``ready=True`` means the second confirmation is complete.  The caller must
    retain the normal pattern pending rule so BUY uses a later independent
    frame; this function never claims or executes that fill.
    """
    state = copy.deepcopy(dict(previous_state or {}))
    evidence: dict[str, Any] = {"policy_version": policy["version"]}
    if state.get("policy_version") not in {None, policy["version"]}:
        return False, "mature_acceptance_policy_changed", state, evidence
    frames, error = _valid_history(
        history,
        decision_at=decision_at,
        activated_at=activated_at,
        maximum_age_seconds=float(policy["maximum_frame_age_seconds"]),
    )
    if error:
        return False, error, state, evidence
    last = frames[-1]
    age = _number(last.get("pool_age_seconds"))
    if age is None or age < float(policy["minimum_pool_age_seconds"]):
        return False, "awaiting_mature_pool_age", state, evidence
    if state.get("status") == "READY":
        return False, "mature_acceptance_episode_already_ready", state, evidence

    episode = state.get("episode")
    if not isinstance(episode, Mapping) or state.get("status") == "EXPIRED":
        candidates = []
        narrative_candidate = _qualified_narrative_event(
            narrative,
            frames,
            decision_at=decision_at,
            activated_at=activated_at,
            minimum_age=float(policy["minimum_pool_age_seconds"]),
        )
        if narrative_candidate is not None:
            candidates.append(narrative_candidate)
        natural_candidate = _natural_reactivation_event(
            frames, decision_at=decision_at, activated_at=activated_at
        )
        if natural_candidate is not None:
            candidates.append(natural_candidate)
        if not candidates:
            return False, "awaiting_mature_acceptance_event", state, evidence
        seen = list(state.get("seen_episode_ids") or [])[-7:]
        selected = None
        for event, baseline in candidates:
            episode_id = _event_id([
                policy["version"], event["event_id"], last["token_id"], last["pair_address"]
            ])
            if episode_id not in seen:
                selected = event, baseline, episode_id
                break
        if selected is None:
            return False, "mature_acceptance_episode_already_seen", state, evidence
        event, baseline, episode_id = selected
        episode = {
            "episode_id": episode_id,
            "token_id": last["token_id"],
            "pair_address": last["pair_address"],
            **event,
            "baseline": baseline,
            "confirmations": [],
        }
        state.update({
            "policy_version": policy["version"],
            "status": "AWAITING_CONFIRMATIONS",
            "episode": episode,
            "seen_episode_ids": [*seen, episode_id],
        })
        evidence.update({"episode": copy.deepcopy(episode), "scope": "single_exact_pool"})
        return False, "mature_acceptance_event_frozen", state, evidence

    if (
        episode.get("token_id") != last["token_id"]
        or episode.get("pair_address") != last["pair_address"]
    ):
        return False, "mature_acceptance_episode_identity_mismatch", state, evidence
    event_at = parse_time(episode["event_recorded_at"])
    current_at = parse_time(last["observed_at"])
    confirmations = copy.deepcopy(list(episode.get("confirmations") or []))
    if any(item.get("observed_at") == last["observed_at"] for item in confirmations):
        return False, "duplicate_mature_acceptance_frame", state, evidence
    anchor_at = parse_time(confirmations[-1]["observed_at"]) if confirmations else event_at
    gap = (current_at - anchor_at).total_seconds()
    evidence.update({
        "episode_id": episode["episode_id"],
        "event_kind": episode["event_kind"],
        "confirmation_gap_seconds": gap,
    })
    if gap < float(policy["minimum_confirmation_gap_seconds"]):
        return False, "mature_acceptance_confirmation_too_close", state, evidence
    if gap > float(policy["maximum_confirmation_gap_seconds"]):
        state["status"] = "EXPIRED"
        return False, "mature_acceptance_confirmation_expired", state, evidence
    if float(last["liquidity"]) < CHAIN_MEME_MIN_POOL_LIQUIDITY_USD:
        return False, "mature_acceptance_pool_liquidity_below_shared_floor", state, evidence

    baseline = episode["baseline"]
    reference = confirmations[-1] if confirmations else baseline
    price_ok = float(last["price"]) >= float(reference["price_usd"])
    if confirmations:
        price_ok = float(last["price"]) > float(reference["price_usd"])
    liquidity_ok = float(last["liquidity"]) >= float(reference["liquidity_usd"])
    evidence.update({
        "reference_price_usd": float(reference["price_usd"]),
        "reference_liquidity_usd": float(reference["liquidity_usd"]),
        "price_confirmed": price_ok,
        "liquidity_confirmed": liquidity_ok,
    })
    confirmation = {
        "snapshot_id": last.get("id"),
        "observed_at": last["observed_at"],
        "recorded_at": last["recorded_at"],
        "price_usd": float(last["price"]),
        "liquidity_usd": float(last["liquidity"]),
    }
    if not price_ok or not liquidity_ok:
        if (
            float(last["price"]) >= float(baseline["price_usd"])
            and float(last["liquidity"]) >= float(baseline["liquidity_usd"])
        ):
            episode["confirmations"] = [confirmation]
            state["episode"] = episode
            return False, "mature_acceptance_confirmation_restarted", state, evidence
        return False, "mature_acceptance_structure_not_confirmed", state, evidence

    confirmations.append(confirmation)
    episode["confirmations"] = confirmations
    state["episode"] = episode
    if len(confirmations) < 2:
        return False, "mature_acceptance_first_confirmation", state, evidence
    state["status"] = "READY"
    evidence.update({
        "episode": copy.deepcopy(episode),
        "ready_snapshot_id": last.get("id"),
        "execution_contract": "shared_pattern_pending_then_next_independent_original_pool_frame",
    })
    return True, "mature_acceptance_two_frame_confirmed", state, evidence


__all__ = [
    "MATURE_ACCEPTANCE_POLICY",
    "mature_acceptance_policy",
    "evaluate_mature_acceptance",
]
