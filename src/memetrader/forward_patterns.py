"""Small, deterministic, as-of experiments; no network calls or account writes.

Thresholds are preregistered hypotheses, not fitted performance claims. Aggregate
transaction counts never stand in for independent wallets or transaction flow.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Any, Mapping

from .models import CHAIN_MEME_MIN_POOL_LIQUIDITY_USD, parse_time


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
            if direction == "participation":
                policy["entry_filter"]["identity_unit"] = "signer_address_not_human"
                policy["entry_filter"]["largest_buyer_share_basis"] = "verified_buy_instruction_count"
            if direction == "narrative":
                policy["entry_filter"]["evidence_basis"] = "original_source_contract_mentions_and_independent_fact_support"
            if direction == "migration":
                policy["entry_filter"]["evidence_basis"] = "post_deployment_migration_message_and_rpc_verified_new_pool"
            policies.append(policy)
    return policies


def buy_ratio(frame: Mapping[str, Any]) -> float | None:
    buys, sells = frame.get("buys"), frame.get("sells")
    if buys is None or sells is None or buys + sells <= 0:
        return None
    return buys / (buys + sells)


def result_driven_policies() -> list[dict[str, Any]]:
    """Independent single-mechanism tests; parent contracts remain unchanged."""
    import copy
    from .capital_exits import EARN_THE_HOLD_POLICY
    parents = {p["arm_id"]: p for p in experiment_policies()}
    specs = (
        ("serial_conditional_runner_v1", "experiment_conditional_runner_candidate_v1",
         "单槽条件兑现", {"max_concurrent_positions": 1,
                          "occupied_signal_policy": "reject_without_queue_or_replay"}),
        ("sustained_breakout_earn_hold_v1", "experiment_sustained_breakout_candidate_v1",
         "突破后持仓资格", {"required_market_surface": "solana_pumpswap"}),
    )
    result = []
    for arm, parent, name, extra in specs:
        policy = copy.deepcopy(parents[parent])
        policy.update(arm_id=arm, canonical_id=arm, name=name,
                      source_arm_ids=[parent], notional_usd=20.0,
                      description="基于自然结果提出的独立机制实验，尚未证明优于原策略。")
        policy["entry_filter"].update(extra)
        if arm == "sustained_breakout_earn_hold_v1":
            policy.update(capital_exit_kind="earn_the_hold",
                          capital_exit_policy=dict(EARN_THE_HOLD_POLICY))
        result.append(policy)
    return result


def cycle_and_volatility_policies() -> list[dict[str, Any]]:
    """Two new mechanisms with controls, without changing the existing factory."""
    import copy
    template = experiment_policies()[0]
    specs = (
        ("observed_cycle_reset_reacceleration", "首波深重置后二次启动", "cycle_reset", {
            "min_age_seconds": 1800, "min_frames": 16, "min_span_seconds": 720,
            "base_from_seconds": 300, "base_to_seconds": 60, "base_min_frames": 6,
            "base_min_span_seconds": 180, "base_range_max": 1.08,
            "trigger_min": 1.12, "trigger_max": 1.35, "volume_acceleration_min": 1.5,
            "liquidity_retention_min": 0.8, "buy_ratio_min": 0.6, "count_min": 6,
            "peak_age_min_seconds": 360, "peak_age_max_seconds": 900,
            "first_wave_min": 1.35, "trough_peak_min": 0.50, "trough_peak_max": 0.75,
            "base_peak_volume_max": 0.5, "trigger_peak_max": 0.90,
        }),
        ("volatility_scaled_depth_flow_momentum", "波动率归一化资金压力动量", "volatility_flow", {
            "min_age_seconds": 900, "max_age_seconds": 21600, "min_frames": 9,
            "min_span_seconds": 120, "max_span_seconds": 600,
            "sigma_floor": 0.005, "mad_scale": 1.4826, "z_min": 2.0,
            "trigger_min": 1.04, "trigger_max": 1.25, "control_trigger_min": 1.08,
            "liquidity_retention_min": 0.85, "buy_ratio_min": 0.6,
            "count_min": 8, "pressure_min": 0.02,
        }),
    )
    result = []
    for prefix, name, direction, thresholds in specs:
        for control in (False, True):
            arm = prefix + ("_control_v1" if control else "_v1")
            policy = copy.deepcopy(template)
            policy.update(arm_id=arm, canonical_id=arm, name=name + ("·对照" if control else "·候选"),
                          entry_family=direction, source_entry_family=direction, notional_usd=5.0,
                          description="独立5U因果实验；只用部署后同池价格、流动性与5分钟聚合量，尚未证明盈利。",
                          entry_filter={"direction": direction, "control": control,
                                        "contract": "cycle-volatility/v1", "max_gap_seconds": 90,
                                        **thresholds})
            result.append(policy)
    return result


def _cycle_volatility_signal(selected, cfg):
    direction, control = cfg["direction"], cfg["control"]
    window = selected if direction == "cycle_reset" else selected[-cfg["min_frames"]:]
    if len(window) < cfg["min_frames"]:
        return False, "awaiting_cycle_volatility_sequence"
    last = window[-1]
    times = [parse_time(f["observed_at"]) for f in window]
    span = (times[-1] - times[0]).total_seconds()
    if span < cfg["min_span_seconds"] or span > cfg.get("max_span_seconds", 1200):
        return False, "cycle_volatility_window_not_ready"
    if any((b - a).total_seconds() > cfg["max_gap_seconds"] for a, b in zip(times, times[1:])):
        return False, "observation_gap_not_market_quiet"
    if any(f.get("price") is None or not math.isfinite(f["price"]) or f["price"] <= 0 for f in window):
        return False, "awaiting_valid_price_sequence"
    age = last["pool_age_seconds"]
    if not cfg["min_age_seconds"] <= age <= cfg.get("max_age_seconds", math.inf):
        return False, "cycle_volatility_age_not_met"
    if (buy_ratio(last) or 0) < cfg["buy_ratio_min"] or (last.get("buys") or 0) + (last.get("sells") or 0) < cfg["count_min"]:
        return False, "cycle_volatility_buy_pressure_not_met"
    if direction == "cycle_reset":
        base_indices = [i for i, t in enumerate(times)
                        if cfg["base_to_seconds"] <= (times[-1] - t).total_seconds() <= cfg["base_from_seconds"]]
        if len(base_indices) < cfg["base_min_frames"] or (times[base_indices[-1]] - times[base_indices[0]]).total_seconds() < cfg["base_min_span_seconds"]:
            return False, "awaiting_observed_reset_base"
        base = [window[i] for i in base_indices]
        if any(f.get("volume") is None or f.get("liquidity") is None or f["liquidity"] < 1 for f in [*base, last]):
            return False, "awaiting_reset_volume_liquidity"
        base_prices = [f["price"] for f in base]
        base_volume = median(f["volume"] for f in base)
        passed = (max(base_prices) / min(base_prices) <= cfg["base_range_max"]
                  and cfg["trigger_min"] <= last["price"] / median(base_prices) <= cfg["trigger_max"]
                  and base_volume > 0 and last["volume"] >= base_volume * cfg["volume_acceleration_min"]
                  and last["liquidity"] >= median(f["liquidity"] for f in base) * cfg["liquidity_retention_min"])
        if passed and not control:
            pre_base = window[:base_indices[0]]
            peak_index = max(range(len(pre_base)), key=lambda i: pre_base[i]["price"]) if pre_base else 0
            if peak_index == 0:
                return False, "awaiting_observed_first_wave"
            peak = window[peak_index]["price"]
            peak_age = (times[-1] - times[peak_index]).total_seconds()
            trough = min(f["price"] for f in window[peak_index + 1:base_indices[0] + 1])
            peak_frames = window[max(0, peak_index - 1):peak_index + 2]
            if any(f.get("volume") is None for f in peak_frames):
                return False, "awaiting_first_wave_volume"
            passed = (cfg["peak_age_min_seconds"] <= peak_age <= cfg["peak_age_max_seconds"]
                      and peak / min(f["price"] for f in window[:peak_index]) >= cfg["first_wave_min"]
                      and cfg["trough_peak_min"] <= trough / peak <= cfg["trough_peak_max"]
                      and base_volume <= median(f["volume"] for f in peak_frames) * cfg["base_peak_volume_max"]
                      and last["price"] <= peak * cfg["trigger_peak_max"])
    else:
        if any(f.get("liquidity") is None or f["liquidity"] < 1 for f in window):
            return False, "awaiting_volatility_liquidity"
        if any(f.get("volume") is None or (buy_ratio(f) or 0) < cfg["buy_ratio_min"] for f in window[-2:]):
            return False, "awaiting_sustained_buy_pressure"
        baseline = [math.log(b["price"] / a["price"]) / math.sqrt((tb - ta).total_seconds() / 60)
                    for a, b, ta, tb in zip(window[:6], window[1:7], times[:6], times[1:7])]
        center = median(baseline)
        sigma = max(cfg["sigma_floor"], cfg["mad_scale"] * median(abs(x - center) for x in baseline))
        trigger = last["price"] / window[-3]["price"]
        z = math.log(trigger) / (sigma * math.sqrt((times[-1] - times[-3]).total_seconds() / 60))
        # This is an aggregate-count/volume proxy, not observed signed money flow or LOB OFI.
        pressures = [(2 * buy_ratio(f) - 1) * f["volume"] / f["liquidity"] for f in window[-2:]]
        passed = (cfg["trigger_min"] <= trigger <= cfg["trigger_max"]
                  and min(f["liquidity"] for f in window[-3:]) >= median(f["liquidity"] for f in window[:7]) * cfg["liquidity_retention_min"]
                  and pressures[0] > 0 and pressures[1] >= max(pressures[0], cfg["pressure_min"])
                  and (trigger >= cfg["control_trigger_min"] if control else z >= cfg["z_min"]))
    return bool(passed), direction + ("_passed" if passed else "_conditions_not_met")


def pattern_signal(
    history: list[dict[str, Any]], policy: Mapping[str, Any], *,
    decision_at: str, activated_at: str,
    context: Mapping[str, Any] | None = None,
) -> tuple[bool, str]:
    """Observe a signal. Execution must use a separate later same-pool sample."""
    if policy.get("entry_filter", {}).get("contract") == "all-history-finalists/20260907-v1":
        from .research_finalists import finalist_signal
        return finalist_signal(history, policy, decision_at=decision_at, activated_at=activated_at)
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
    if liquidity is None:
        return False, "entry_pool_liquidity_unknown"
    if liquidity is not None and liquidity < float(policy.get("_execution", {}).get(
            "min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD)):
        return False, "entry_pool_liquidity_below_configured_floor"
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
            passed = count >= 3 and evidence.get("unique_buyers", 0) > 0 and (control or (
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
    if direction in {"cycle_reset", "volatility_flow"}:
        return _cycle_volatility_signal(selected, cfg)
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
            passed = (passed and last3[-1].get("volume") is not None
                      and last3[0].get("volume") is not None
                      and last3[-1]["volume"] >= last3[0]["volume"])
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
