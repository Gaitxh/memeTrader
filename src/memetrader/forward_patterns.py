"""Small, deterministic, as-of experiments; no network calls or account writes.

Thresholds are preregistered hypotheses, not fitted performance claims. Aggregate
transaction counts never stand in for independent wallets or transaction flow.
"""
from __future__ import annotations

from typing import Any, Mapping

from .models import parse_time


DIRECTIONS = {
    "participation": "早期参与扩散",
    "quiet_reawakening": "静默压缩复苏",
    "sustained_breakout": "持续多窗突破",
    "pullback_reclaim": "回撤收复",
    "conditional_runner": "条件兑现与趋势残仓",
    "support_risk": "机械支撑风险",
    "migration": "迁移后确认",
    "narrative": "信息优先注意力",
    "panic_reclaim": "流动性保留反转",
}


def experiment_policies() -> list[dict[str, Any]]:
    policies = []
    for direction, name in DIRECTIONS.items():
        for control in (False, True):
            arm = f"experiment_{direction}_{'control' if control else 'candidate'}_v1"
            policy = {
                "arm_id": arm, "canonical_id": arm, "name": name + ("·对照" if control else "·候选"),
                "description": name + "独立前向试验；未证明盈利，不使用部署前观察序列。",
                "family": "additive_forward_challenger", "entry_family": direction,
                "source_entry_family": direction, "entry_gate": "bounded_pattern_observer_v1",
                "entry_match_mode": "isolated_pattern_observer",
                "entry_filter": {"direction": direction, "control": control,
                                 "contract": "forward-patterns/v1", "max_gap_seconds": 90},
                "exit_family": "pattern_cost_scaleout", "exit_mode": "market_mark_pattern_scaleout",
                "execution_profile": "dexscreener-market-paper/v2-before-after",
                "hard_stop_return": -0.20, "trailing_activate_return": 0.30,
                "trailing_drawdown": 0.15, "max_hold_minutes": 15.0,
                "take_profit": [{"return": 0.30, "fraction_of_remaining": 0.50},
                                {"return": 0.80, "fraction_of_remaining": 1.0}],
                "exact_risk_alerts": "shadow_only_no_trading_authority",
                "research_overlay": "none", "forward_enabled": True,
                "fidelity_status": "ADDITIVE_FORWARD",
                "fidelity_note": "独立候选对照；时点数据不足时等待，不冒充交易证据",
                "source_arm_ids": [], "no_historical_backfill": True,
            }
            if direction == "conditional_runner":
                policy.update({
                    "exit_family": "conditional_runner" if not control else "quick_realize",
                    "trailing_activate_return": 0.12,
                    "take_profit": [{"return": 0.12, "fraction_of_remaining": 1.0},
                                    {"return": 0.30, "fraction_of_remaining": 1.0}],
                    "conditional_exit": {"enabled": not control, "buy_ratio_min": 0.55,
                                         "liquidity_retention_min": 0.8, "samples": 2},
                })
            if direction == "support_risk":
                policy["entry_filter"]["evidence_basis"] = "confirmed_raw_reserves_plus_available_effective_depth"
                policy["entry_filter"]["treatment"] = "exclude_observed_unwind_or_synthetic_support_not_regularity_alone"
            if direction == "migration":
                policy["entry_filter"]["evidence_basis"] = "post_deployment_migration_message_and_rpc_verified_new_pool"
            policies.append(policy)
    return policies


def buy_ratio(frame: Mapping[str, Any]) -> float | None:
    buys, sells = frame.get("buys"), frame.get("sells")
    if buys is None or sells is None or buys + sells <= 0:
        return None
    return buys / (buys + sells)


def pattern_signal(
    history: list[dict[str, Any]], policy: Mapping[str, Any], *,
    decision_at: str, activated_at: str,
    context: Mapping[str, Any] | None = None,
) -> tuple[bool, str]:
    """Observe a signal. Execution must use a separate later same-pool sample."""
    if not history:
        return False, "awaiting_observation"
    now, start = parse_time(decision_at), parse_time(activated_at)
    last = history[-1]
    frames = [f for f in history if f["token_id"] == last["token_id"]
              and f["pair_address"] == last["pair_address"]
              and start <= parse_time(f["observed_at"]) <= parse_time(f["ingested_at"])
              <= parse_time(f["recorded_at"]) <= now]
    if not frames or frames[-1] is not last or not 0 <= (now - parse_time(last["observed_at"])).total_seconds() <= 30:
        return False, "stale_or_noncausal_observation"
    liquidity = last.get("liquidity")
    if liquidity is not None and liquidity < 1:
        return False, "entry_pool_liquidity_below_1_usd"
    if not last.get("price") or last["price"] <= 0:
        return False, "invalid_price"
    cfg = policy["entry_filter"]
    direction, control = cfg["direction"], cfg["control"]
    age = last.get("pool_age_seconds")
    if age is None or age < 0:
        return False, "pool_age_unknown"
    ratio = buy_ratio(last)
    count = (last.get("buys") or 0) + (last.get("sells") or 0)
    context = context or {}

    if direction == "conditional_runner":
        return (age <= 900 and count >= 3), "broad_launch_pattern"
    if direction in {"participation", "migration", "narrative", "support_risk"}:
        # Evidence producers provide their actual local availability timestamp.
        evidence = context.get(direction)
        if not evidence or not evidence.get("available_at"):
            return False, f"awaiting_{direction}_evidence"
        if not start <= parse_time(evidence["available_at"]) <= now:
            return False, "evidence_outside_forward_boundary"
        if evidence.get("token_id") != last["token_id"] or evidence.get("pair_address") != last["pair_address"]:
            return False, "evidence_identity_mismatch"
        if direction == "participation":
            if not age <= 900 or not evidence.get("trade_identity_verified"):
                return False, "awaiting_verified_trade_identity"
            passed = count >= 3 and (control or (
                evidence.get("unique_buyers", 0) >= 5 and evidence.get("new_buyers_second_window", 0) >= 3
                and evidence.get("largest_buyer_share", 1) <= 0.5))
        elif direction == "migration":
            passed = bool(evidence.get("pool_rpc_verified") and (
                control or evidence.get("canonical_migration_pool")
                and evidence.get("migration_signature") and evidence.get("post_migration_samples", 0) >= 2
                and evidence.get("migration_observed_at")
                and start <= parse_time(evidence["migration_observed_at"]) <= now))
        elif direction == "support_risk":
            # Entry-only comparison. No Vault-triggered exit at a stale DEX price.
            passed = bool(evidence.get("coherent_confirmed_slot") and count >= 3 and (
                control or evidence.get("unwind_hazard") == "LOW"))
        else:
            passed = bool(evidence.get("exact_token_relation") and evidence.get("independent_sources", 0) >= 2
                          and (not control or ratio is not None and ratio >= 0.55 and count >= 10))
        return passed, direction + ("_passed" if passed else "_conditions_not_met")

    # Select independent observations in time, not repeated reads of one frame.
    selected = []
    for frame in frames:
        if not selected or (parse_time(frame["observed_at"]) - parse_time(selected[-1]["observed_at"])).total_seconds() >= 15:
            selected.append(frame)
    if len(selected) < 3 or selected[-1] is not last:
        return False, "awaiting_distinct_observation_sequence"
    tail = selected[-12:]
    if any((parse_time(b["observed_at"]) - parse_time(a["observed_at"])).total_seconds() > cfg["max_gap_seconds"]
           for a, b in zip(tail, tail[1:])):
        return False, "observation_gap_not_market_quiet"
    recent = [f for f in selected if (parse_time(last["observed_at"]) - parse_time(f["observed_at"])).total_seconds() <= 300]
    if len(recent) < 3:
        return False, "awaiting_recent_sequence"
    prices = [f["price"] for f in recent]
    retained = all(f.get("liquidity") is not None and f["liquidity"] >= 1 for f in recent)
    retention = min(f["liquidity"] for f in recent) / recent[0]["liquidity"] if retained else 0
    flow = ratio is not None and ratio >= 0.55
    passed = False
    if direction == "sustained_breakout":
        last3 = recent[-3:]
        previous_prices = [f["price"] for f in last3]
        passed = 900 <= age <= 21600 and flow and retention >= 0.8 and prices[-1] / prices[0] >= 1.12
        if not control:
            passed = passed and all(b >= a for a, b in zip(previous_prices, previous_prices[1:]))
            passed = passed and all(buy_ratio(f) is not None and buy_ratio(f) >= 0.55 for f in last3[-2:])
            passed = passed and last3[-1].get("volume", 0) >= last3[0].get("volume", 0)
    elif direction == "pullback_reclaim":
        peak_index = max(range(len(prices) - 1), key=prices.__getitem__)
        peak = prices[peak_index]
        passed = age >= 900 and flow and retention >= 0.8 and prices[-1] / prices[0] >= 1.10
        if not control:
            lows = prices[peak_index + 1:-1]
            low = min(lows) if lows else peak
            passed = passed and peak / prices[0] >= 1.15 and 0.85 <= low / peak <= 0.95
            passed = passed and prices[-1] / low >= 1.05 and prices[-1] / peak >= 0.95
    elif direction == "panic_reclaim":
        low_index = min(range(len(prices)), key=prices.__getitem__)
        low = prices[low_index]
        passed = age >= 900 and liquidity is not None and liquidity >= 5000 and flow
        passed = passed and low_index > 0 and low_index <= len(prices) - 3
        passed = passed and low / prices[0] <= 0.80 and prices[-1] / low >= 1.05 and prices[-1] > prices[-2] > low
        passed = passed and (control or retention >= 0.8)
    elif direction == "quiet_reawakening":
        passed = age >= 21600 and flow and count >= 10 and (last.get("volume") or 0) >= 1000
        if not control:
            quiet = [f for f in selected if 120 <= (parse_time(last["observed_at"]) - parse_time(f["observed_at"])).total_seconds() <= 900]
            passed = passed and len(quiet) >= 8
            if passed:
                span = (parse_time(quiet[-1]["observed_at"]) - parse_time(quiet[0]["observed_at"])).total_seconds()
                passed = span >= 600 and all((parse_time(b["observed_at"]) - parse_time(a["observed_at"])).total_seconds() <= cfg["max_gap_seconds"]
                                            for a, b in zip(quiet, quiet[1:]))
                passed = passed and all(f.get("buys") is not None and f.get("sells") is not None
                                            and f["buys"] + f["sells"] <= 2
                                            and f.get("volume") is not None and f["volume"] <= 200 for f in quiet)
                passed = passed and max(f["price"] for f in quiet) / min(f["price"] for f in quiet) <= 1.10
                passed = passed and prices[-1] / quiet[-1]["price"] >= 1.12 and retention >= 0.8
    return bool(passed), direction + ("_passed" if passed else "_conditions_not_met")


def conditional_fraction(policy: Mapping[str, Any], marks: list[Mapping[str, Any]],
                         entry_liquidity: float | None) -> float:
    cfg = policy.get("conditional_exit") or {}
    if not cfg.get("enabled") or entry_liquidity is None or entry_liquidity < 1 or len(marks) < 2:
        return 1.0
    return 0.5 if all(buy_ratio(m) is not None and buy_ratio(m) >= cfg["buy_ratio_min"]
                      and m.get("liquidity") is not None
                      and m["liquidity"] / entry_liquidity >= cfg["liquidity_retention_min"]
                      for m in marks[-2:]) else 1.0
