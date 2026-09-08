"""Resource-bounded, preregistered Paper hypotheses; no data acquisition."""
from copy import deepcopy
from math import log1p

from .capital_exits import _as_time, _number, _result
from .models import CHAIN_MEME_MIN_POOL_LIQUIDITY_USD
from .research_finalists import finalist_policies, evaluate_finalist_exit

CONTRACT = "resource-bound/20260907-v1"
EXIT_KIND = "resource_profit_structure"
ENTRY_KINDS = frozenset({"age_rate", "cooling_hold"})


def resource_policies():
    parents = {p["arm_id"]: p for p in finalist_policies()}
    result = []
    for mechanism, name in (("age_rate", "池龄归一化活动加速"),
                            ("cooling_hold", "涨后降温端点守位"),
                            ("profit_structure", "盈利支撑保持时钟豁免")):
        parent = parents["finalist_progress_clock_v1" if mechanism == "profit_structure"
                         else "finalist_baseline_v1"]
        for role in ("control", "candidate"):
            p = deepcopy(parent)
            arm = f"resource_{mechanism}_{role}_v1"
            p.update(arm_id=arm, canonical_id=arm, name=name + ("·对照" if role == "control" else "·候选"),
                description=name + "；仅现有行情和真实账本，独立前向假设，未证明盈利；5U/最多4仓。",
                source_arm_ids=[parent["arm_id"]], resource_bound_research=CONTRACT,
                evidence_review="docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/RESOURCE_BOUND_DESIGN.md")
            if mechanism in ENTRY_KINDS:
                p.pop("paired_entry_group", None)
                p.pop("paired_entry_size", None)
                p.update(entry_family="resource_" + mechanism, source_entry_family="resource_" + mechanism)
                p["entry_filter"].update(contract=CONTRACT, direction=mechanism,
                    control=role == "control", opportunity="first_common_eligible_frame_per_pool",
                    min_rate_acceleration=3.0, cooling_retrace_fraction=.25)
            else:
                p.update(paired_entry_group="resource_profit_structure_v1", paired_entry_size=2)
                if role == "candidate":
                    p.update(capital_exit_kind=EXIT_KIND,
                        capital_exit_policy={**p["capital_exit_policy"], "kind": EXIT_KIND,
                            "version": CONTRACT + "/profit_structure", "liquidity_retention": .85,
                            "support_confirmation": "three_observed_prices_strict_middle_low"})
            result.append(p)
    return result


def resource_entry_signal(history, policy, *, decision_at, activated_at):
    """Same first common opportunity; the candidate can reject independently."""
    evidence = {"contract": CONTRACT, "common_ready": False}
    now, start = _as_time(decision_at), _as_time(activated_at)
    if not history or now is None or start is None:
        return False, "resource_missing_frame", evidence
    last = history[-1]
    observed, ingested, recorded = (_as_time(last.get(k)) for k in
                                    ("observed_at", "ingested_at", "recorded_at"))
    if (None in (observed, ingested, recorded) or not start <= observed <= ingested <= recorded <= now
            or (now - observed).total_seconds() > 30 or not last.get("upstream_provider")):
        return False, "resource_stale_or_noncausal_frame", evidence
    price, liq, age, buys, sells, volume, hour_volume, hour_buys, hour_sells = (
        _number(last.get(k)) for k in ("price", "liquidity", "pool_age_seconds", "buys", "sells",
                                      "volume", "volume_h1", "buys_h1", "sells_h1"))
    floor = float(policy.get("_execution", {}).get("min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD))
    if (any(v is None for v in (price, liq, age, buys, sells, volume, hour_volume, hour_buys, hour_sells))
            or price <= 0 or liq < floor or min(age, buys, sells, volume, hour_volume, hour_buys, hour_sells) < 0):
        return False, "resource_incomplete_aggregate_frame", evidence
    trades, prior_trades, prior_volume = buys + sells, hour_buys + hour_sells - buys - sells, hour_volume - volume
    if prior_trades <= 0 or prior_volume <= 0:
        return False, "resource_no_comparable_positive_baseline", evidence
    cfg = policy["entry_filter"]
    mechanism = cfg["direction"]
    candidate = False
    if mechanism == "age_rate":
        if not 900 < age < 21600 or not (trades >= 8 or volume >= 1000):
            return False, "resource_age_rate_common_wait", evidence
        old_rate = max(trades / (prior_trades / 11), volume / (prior_volume / 11))
        actual_minutes = min(55.0, age / 60 - 5)
        adjusted_rate = old_rate * actual_minutes / 55
        if old_rate < cfg["min_rate_acceleration"]:
            return False, "resource_old_rate_below_threshold", evidence
        candidate = adjusted_rate >= cfg["min_rate_acceleration"]
        evidence.update(old_max_rate=old_rate, adjusted_max_rate=adjusted_rate,
                        prior_minutes=actual_minutes)
    elif mechanism == "cooling_hold":
        r5, r60 = (_number(last.get(k)) for k in ("price_change_m5", "price_change_h1"))
        if not 3600 <= age <= 86400 or trades < 8 or volume <= 0 or r5 is None or r60 is None or min(r5, r60) <= -100:
            return False, "resource_cooling_common_wait", evidence
        execution = policy.get("_execution") or {}
        buy_slip = float(execution.get("buy_slippage_bps", 400)) / 10000
        sell_slip = float(execution.get("sell_slippage_bps", 400)) / 10000
        # This is an earlier displacement scale, never predicted future profit.
        fee = float(execution.get("additional_fee_usd_each_fill", 0))
        friction_log = (log1p(buy_slip) - log1p(-sell_slip)
                        + log1p(2 * fee / float(policy["notional_usd"])))
        g5, g55 = log1p(r5 / 100), log1p(r60 / 100) - log1p(r5 / 100)
        activity_ratio = (volume / 5) / (prior_volume / 55)
        if g55 < friction_log:
            return False, "resource_prior_rise_below_friction_scale", evidence
        candidate = -cfg["cooling_retrace_fraction"] * g55 <= g5 <= 0 and activity_ratio < 1
        evidence.update(recent_log_return=g5, prior_log_return=g55, activity_ratio=activity_ratio,
                        friction_log_scale=friction_log, path_semantics="aggregate_endpoints_not_intrawindow_path")
    else:
        return False, "resource_unknown_entry", evidence
    evidence.update(common_ready=True, candidate_passed=bool(candidate), observed_at=last["observed_at"],
                    age_seconds=age, m5_trades=trades, m5_volume_usd=volume,
                    prior_trades=prior_trades, prior_volume_usd=prior_volume)
    passed = bool(cfg["control"] or candidate)
    return passed, "resource_" + mechanism + ("_ready" if passed else "_candidate_rejected"), evidence


def age_rate_horizon_policies():
    """S1: frozen common entry, only 15/60-minute holding horizon differs."""
    parent = next(p for p in resource_policies() if p["arm_id"] == "resource_age_rate_candidate_v1")
    result = []
    for minutes, role in ((15, "fast"), (60, "runner")):
        p = deepcopy(parent)
        arm = f"age_rate_horizon_{role}_v1"
        p.update(arm_id=arm, canonical_id=arm, name=f"池龄归一化·{minutes}分钟配对",
            description="同一池龄归一化入场/同成交/5U最多4仓；仅持仓时限不同，严格前向，未验证盈利。",
            source_arm_ids=[parent["arm_id"]], max_hold_minutes=float(minutes),
            paired_entry_group="age_rate_horizon_pair_v1", paired_entry_size=2,
            evidence_review="docs/PROJECT_CONTEXT/STRATEGY_FORWARD_CONVERGENCE_20260909.md")
        result.append(p)
    return result


def evaluate_resource_exit(position, frame, state=None, *, now, policy):
    """Only mask the existing progress-clock SELL while current support holds."""
    base_policy = {**policy, "kind": "finalist_progress_clock"}
    action, reason, new, evidence = evaluate_finalist_exit(position, frame, state, now=now, policy=base_policy)
    if action == "WAIT" or (state or {}).get("status") == "EXIT_TRIGGERED":
        return action, reason, new, evidence
    if evidence.get("observation_reset"):
        new.pop("support", None)
        new.pop("structure_window", None)
    point = {"price": float(frame["price_usd"]), "liquidity": float(frame["liquidity_usd"]),
             "at": frame["observed_at"]}
    window = (list(new.get("structure_window") or []) + [point])[-3:]
    new["structure_window"] = window
    support = new.get("support")
    if support and point["price"] < support["price"]:
        support = None
        new.pop("support", None)
    if len(window) == 3 and window[0]["price"] > window[1]["price"] < window[2]["price"]:
        pivot = window[1]
        if support is None or pivot["price"] > support["price"]:
            support = {**pivot, "confirmed_at": point["at"]}
            new["support"] = support
    healthy = bool(support and frame["economic_value_usd"] > position["stake_usd"]
        and point["price"] >= support["price"]
        and point["liquidity"] >= support["liquidity"] * policy["liquidity_retention"])
    clock_triggered = action == "SELL"
    if clock_triggered and healthy:
        new.pop("status", None)
        action = "HOLD"
    evidence.update(strategy=EXIT_KIND, support=support, currently_healthy=healthy,
                    clock_triggered=clock_triggered, clock_exempted=clock_triggered and healthy)
    reason = EXIT_KIND + ("_exempted" if clock_triggered and healthy else
                         "_armed" if action == "SELL" else "_monitoring")
    return _result(action, reason, new, evidence)
