"""Frozen observed-buyer cohorts, not reconstructed mint-initial holders.

Pure, no RPC/storage. Call the sealer on each new single complete market_flow
window until it returns a cohort, then persist it once per deployment/token/pool.
Create facts may establish birth time only: creator/initial SOL is not a buyer.
Later SELLs come from the same already-collected actual SPL swap windows.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from .capital_exits import CREATOR_DISTRIBUTION_POLICY, evaluate_creator_early_holder_distribution
from .market_flow import IDENTITY_FIELDS, _receipt, _stamp, _time, build_market_frame


ARM_ID = "early_observed_buyer_distribution_v1"
NOTIONAL_USD = 5.0
MAX_BUYERS = 32
EARLY_SECONDS = 120
EXIT_POLICY = {**CREATOR_DISTRIBUTION_POLICY, "version": "early-observed-buyer-distribution/v1"}


def observed_buyer_policy():
    from .capital_policies import capital_policies
    p = deepcopy(next(p for p in capital_policies() if p["arm_id"] == "creator_early_holder_distribution_v1"))
    p.update(arm_id=ARM_ID, canonical_id=ARM_ID, name="首次观察买家·动态派发",
             entry_family="early_observed_buyer_distribution", notional_usd=NOTIONAL_USD,
             capital_exit_kind="early_observed_buyer_distribution", capital_exit_policy=dict(EXIT_POLICY),
             source_arm_ids=["creator_early_holder_distribution_v1"],
             description="封存首个完整买盘窗口的买家集合，观察其后实际卖出；不冒充完整初始持有人。")
    p["entry_filter"] = {"direction": "early_observed_buyer_distribution"}
    return p


def _window(window, now):
    if window.get("complete") is not True:
        return None
    result = build_market_frame(window.get("trades", ()),
        window_start=window.get("window_start"), window_end=window.get("window_end"),
        resolver=window.get("resolver"), scan=window.get("scan"),
        quote_conversion=window.get("quote_conversion"), decision_at=now)
    decision, observed = _time(now), _time(result.get("observed_at"))
    return result if (result["complete"] and decision is not None and observed is not None
                      and 0 <= decision - observed <= 30) else None


def seal_observed_buyers(window, *, source_evidence_id, activation_evidence_id,
                         activated_at, now, birth_fact=None, existing=None):
    """Freeze the first nonempty complete post-activation BUY window.

    ``window`` is one build_market_frame result, not an overlapping two-window
    aggregate. Evidence ids are the independent registration and current scan
    frontiers. Existing cohorts are returned unchanged; never append later buyers.
    Optional birth_fact has verified=True, exact pool_address/base_mint,
    birth_kind ('token_creation'|'pool_creation'), birth_at and both receipt times.
    Missing/old birth retains honest first-observed-only coverage.
    """
    if existing is not None:
        return deepcopy(existing)
    activated, decision = _time(activated_at), _time(now)
    if (type(source_evidence_id) is not int or type(activation_evidence_id) is not int
            or not source_evidence_id > activation_evidence_id >= 0
            or activated is None or decision is None or activated > decision):
        return None
    frame = _window(window, now)
    if frame is None or _time(frame["window_start"]) < activated:
        return None
    buys = sorted((row for row in frame["trades"] if row["side"] == "BUY"),
                  key=lambda row: (_time(row["block_time"]), row["signature"], row["instruction_path"]))
    addresses = list(dict.fromkeys(row["signer_address"] for row in buys))
    if not addresses:
        return None
    identity = {key: frame["resolver"][key] for key in IDENTITY_FIELDS}
    early, birth = False, None
    if birth_fact is not None:
        birth = _time(birth_fact.get("birth_at"))
        if (birth_fact.get("verified") is not True or not _receipt(birth_fact, decision)
                or birth is None or birth > _time(birth_fact.get("observed_at"))
                or birth_fact.get("birth_kind") not in {"token_creation", "pool_creation"}
                or any(birth_fact.get(key) != identity[key] for key in ("pool_address", "base_mint"))):
            return None
        early = birth <= _time(frame["window_start"]) < _time(frame["window_end"]) <= birth + EARLY_SECONDS
    cohort = {**identity, "version": EXIT_POLICY["version"], "sealed_at": _stamp(decision),
        "activated_at": _stamp(activated), "activation_evidence_id": activation_evidence_id,
        "source_evidence_id": source_evidence_id, "window_start": frame["window_start"],
        "window_end": frame["window_end"], "buyer_addresses": addresses[:MAX_BUYERS],
        "omitted_buyer_count": max(0, len(addresses) - MAX_BUYERS),
        "coverage": "early_observed_buyers" if early else "first_observed_buyers_only",
        "birth_kind": birth_fact["birth_kind"] if early else None,
        "birth_at": _stamp(birth) if early else None,
        "identity_unit": "signer_address_not_human", "mint_initial_holder_coverage": "unknown",
        "selection_basis": "first_complete_observed_buy_window_first_32_chronological_signers"}
    cohort["cohort_id"] = hashlib.sha256(json.dumps(cohort, sort_keys=True).encode()).hexdigest()
    return cohort


def distribution_evidence(cohort, window, *, source_evidence_id, now):
    """Actual matched SELL subset from one complete fresh window after sealing.

    This cannot prove holders' inventory exhaustion or hidden beneficial ownership.
    USD is nullable and uses only the supplied fresh reference, never a fill.
    """
    out = {"complete": False, "reason": "missing_or_noncausal_observed_buyer_cohort"}
    sealed, decision = _time(cohort.get("sealed_at")), _time(now)
    buyers = cohort.get("buyer_addresses")
    if (sealed is None or decision is None or sealed > decision
            or not isinstance(buyers, list) or not 0 < len(buyers) <= MAX_BUYERS
            or type(source_evidence_id) is not int
            or source_evidence_id <= int(cohort.get("source_evidence_id", -1))):
        return out
    frame = _window(window, now)
    if frame is None:
        return {**out, "reason": "incomplete_or_stale_actual_swap_window"}
    if (any(frame["resolver"].get(key) != cohort.get(key) for key in IDENTITY_FIELDS)
            or _time(frame["window_start"]) < sealed):
        return out
    members = set(buyers)
    matched = [row for row in frame["trades"]
               if row["side"] == "SELL" and row["signer_address"] in members]
    raw = sum(row["quote_amount_raw"] for row in matched)
    rate = (frame.get("quote_conversion") or {}).get("usd_per_quote") if frame["usd_conversion_complete"] else None
    usd = raw / 10**frame["resolver"]["quote_decimals"] * rate if rate is not None else None
    return {"complete": True, "reason": "actual_observed_buyer_distribution",
        "cohort_id": cohort["cohort_id"], "coverage": cohort["coverage"],
        "source_evidence_id": source_evidence_id, "window_start": frame["window_start"],
        "window_end": frame["window_end"], "observed_at": frame["observed_at"],
        "recorded_at": frame["recorded_at"], "matched_sell_quote_raw": raw,
        "matched_sell_quote_usd": usd, "matched_sell_count": len(matched),
        "total_sell_notional_usd": frame.get("sell_quote_notional_usd"),
        "net_quote_flow_usd": frame.get("net_quote_flow_usd"),
        "conversion_is_execution_evidence": False, "mint_initial_holder_coverage": "unknown"}


def evaluate_observed_buyer_distribution(position, frame, state=None, *, now, policy=EXIT_POLICY):
    """Independent evaluator with the standard capital ExitResult tuple.

    frame adds buyer_cohort, distribution_window (single market_flow window),
    source_evidence_id to normal capital_context market/depth/breadth fields.
    Existing creator policy thresholds/baseline are reused, not modified. Only
    contiguous, nonoverlapping post-position windows can confirm distribution.
    SELL remains an intent using the existing later same-pool Paper frame.
    """
    previous = deepcopy(state or {})
    cohort = frame.get("buyer_cohort") or {}
    window = frame.get("distribution_window") or {}
    evidence = distribution_evidence(cohort, window,
        source_evidence_id=frame.get("source_evidence_id"), now=now)
    if not evidence["complete"]:
        return "WAIT", evidence["reason"], previous, evidence
    if (position.get("token_id") != "solana:" + str(cohort.get("base_mint"))
            or position.get("pair_address") != cohort.get("pool_address")
            or (previous.get("buyer_cohort_id") not in {None, cohort["cohort_id"]})):
        return "WAIT", "observed_buyer_cohort_identity_changed", previous, evidence
    start, opened = _time(evidence["window_start"]), _time(position.get("opened_at"))
    last_end = _time(previous.get("distribution_window_end"))
    if opened is None or start < opened or (last_end is not None and start < last_end):
        return "WAIT", "noncausal_or_overlapping_distribution_window", previous, evidence
    if last_end is not None and start > last_end:
        previous["distribution_bad_streak"] = 0
    enriched = {**frame, "frame_id": str(evidence["source_evidence_id"]),
        "observed_at": evidence["observed_at"], "recorded_at": evidence["recorded_at"],
        "flow_semantics": "actual_notional", "net_quote_flow_usd": evidence["net_quote_flow_usd"],
        "creator_or_early_holder_sell_notional_usd": evidence["matched_sell_quote_usd"],
        "total_sell_notional_usd": evidence["total_sell_notional_usd"]}
    action, reason, new_state, details = evaluate_creator_early_holder_distribution(
        position, enriched, previous, now=now, policy=policy)
    if action != "WAIT":
        new_state.update(buyer_cohort_id=cohort["cohort_id"], distribution_window_end=evidence["window_end"])
    return action, reason, new_state, {**details, **evidence, "strategy": ARM_ID,
        "reason": reason, "coverage": cohort["coverage"]}
