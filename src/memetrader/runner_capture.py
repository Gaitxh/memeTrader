"""Strictly-forward early runner capture experiment.

This module targets a different objective from the broad launch strategies: rare
right-tail continuation.  Runtime decisions use only observations available at
the decision time.  Historical winner labels are deliberately absent.

Rolling 5m/1h transaction counts and volume are activity proxies, not unique
wallets, signed flow, or proof of organic demand.
"""
from __future__ import annotations

from copy import deepcopy
from math import log
from statistics import median
from typing import Any, Mapping

from .capital_exits import _as_time, _begin, _number, _result
from .models import CHAIN_MEME_MIN_POOL_LIQUIDITY_USD


CONTRACT = "early-runner-capture/20260908-v1"
EXIT_KIND = "runner_exhaustion"


def runner_policies() -> list[dict[str, Any]]:
    """One tail-preserving arm plus a same-fill legacy-exit control."""
    from .research_finalists import finalist_policies

    parent = next(p for p in finalist_policies() if p["arm_id"] == "finalist_baseline_v1")
    result: list[dict[str, Any]] = []
    specs = (
        ("runner_capture_v1", "早期强势延续·尾部捕获", False),
        ("runner_capture_legacy_exit_control_v1", "早期强势延续·旧式退出对照", True),
    )
    for arm, name, control in specs:
        p = deepcopy(parent)
        for key in (
            "capital_exit_kind", "capital_exit_policy", "conditional_exit",
            "paired_entry_group", "paired_entry_size", "take_profit",
        ):
            p.pop(key, None)
        p.update(
            arm_id=arm,
            canonical_id=arm,
            name=name,
            description=(
                "严格前向早期Runner实验；只用当时可得的同池价格、流动性、"
                "滚动成交/成交量代理；5U，最多4仓；未证明Alpha。"
            ),
            family="additive_forward_challenger",
            entry_family="runner_capture",
            source_entry_family="runner_capture",
            entry_gate="early_runner_quality_v1",
            entry_match_mode="isolated_pattern_observer",
            source_arm_ids=[parent["arm_id"]],
            notional_usd=5.0,
            require_post_decision_observation=True,
            paired_entry_group="runner_capture_same_fill_v1",
            paired_entry_size=2,
            exact_risk_alerts="shadow_only_no_trading_authority",
            research_overlay="none",
            forward_enabled=True,
            fidelity_status="ADDITIVE_FORWARD",
            fidelity_note="新独立Paper假设；不回填、不使用未来赢家标签；同池下一观察成交",
            no_historical_backfill=True,
            evidence_review="user_runner_casebook_20260908",
        )
        p["entry_filter"] = {
            "contract": CONTRACT,
            "direction": "runner_capture",
            "control": control,
            "max_concurrent_positions": 4,
            "occupied_signal_policy": "reject_without_queue_or_replay",
            "single_token_lifetime_entry": True,
            "maximum_frame_age_seconds": 15,
            "maximum_gap_seconds": 30,
            "minimum_spacing_seconds": 10,
            "persistent_frames": 3,
            "persistent_minimum_span_seconds": 20,
            "minimum_liquidity_usd": 5_000.0,
            "maximum_token_age_seconds": 5_400,
            "maximum_pair_age_seconds": 5_400,
            "migration_pair_age_seconds": 300,
            "migration_token_pair_age_gap_seconds": 600,
            "minimum_trades_5m": 20,
            "minimum_buy_share": 0.45,
            "minimum_turnover": 0.35,
            "minimum_activity_acceleration": 1.20,
            "explosive_price_change_5m": 0.12,
            "explosive_minimum_trades_5m": 40,
            "explosive_minimum_turnover": 0.75,
            "explosive_minimum_activity_acceleration": 1.50,
            "persistent_return_min": 0.08,
            "persistent_efficiency_min": 0.45,
            "persistent_near_high_ratio": 0.95,
            "minimum_liquidity_retention": 0.75,
            "post_signal_max_up_drift": 0.30,
            "post_signal_max_down_drift": 0.18,
        }
        if control:
            p.update(
                hard_stop_return=-0.20,
                trailing_activate_return=0.30,
                trailing_drawdown=0.15,
                max_hold_minutes=15.0,
                take_profit=[],
            )
        else:
            # Do not let the generic median-token exit logic clip the right tail.
            # Catastrophic loss/liquidity exits remain active for this Paper arm.
            p.update(
                hard_stop_return=-0.40,
                trailing_activate_return=99.0,
                trailing_drawdown=1.0,
                max_hold_minutes=360.0,
                take_profit=[],
                capital_exit_kind=EXIT_KIND,
                capital_exit_policy={
                    "version": CONTRACT + "/exhaustion-v1",
                    "kind": EXIT_KIND,
                    "maximum_frame_age_seconds": 15,
                    "minimum_span_seconds": 5,
                    "maximum_gap_seconds": 30,
                    "window_frames": 12,
                    "minimum_peak_return": 0.35,
                    "warning_drawdown_floor": 0.15,
                    "warning_drawdown_ceiling": 0.35,
                    "warning_volatility_multiplier": 3.0,
                    "warning_rebound_ratio": 1.08,
                    "warning_peak_reclaim_ratio": 0.97,
                    "warning_second_break_ratio": 0.99,
                    "warning_bad_share": 0.47,
                    "warning_bad_streak": 2,
                    "plateau_frames": 6,
                    "plateau_peak_distance": 0.06,
                    "plateau_price_range": 0.08,
                    "plateau_activity_growth": 1.15,
                    "plateau_buy_share_decay": 0.06,
                    "plateau_efficiency_abs": 0.25,
                    "giveback_peak_return": 0.50,
                    "giveback_area_budget": 10.0,
                    "liquidity_peak_retention": 0.55,
                    "liquidity_break_drawdown": 0.10,
                },
            )
        result.append(p)
    return result


def _buy_share(frame: Mapping[str, Any]) -> float | None:
    buys, sells = _number(frame.get("buys")), _number(frame.get("sells"))
    if buys is None or sells is None or min(buys, sells) < 0 or buys + sells <= 0:
        return None
    return buys / (buys + sells)


def _path_efficiency(prices: list[float]) -> float:
    if len(prices) < 2 or any(p <= 0 for p in prices):
        return 0.0
    changes = [log(b / a) for a, b in zip(prices, prices[1:])]
    distance = sum(abs(x) for x in changes)
    return sum(changes) / distance if distance else 0.0


def _activity_acceleration(frame: Mapping[str, Any]) -> float | None:
    buys, sells = _number(frame.get("buys")), _number(frame.get("sells"))
    bh, sh = _number(frame.get("buys_h1")), _number(frame.get("sells_h1"))
    if None in (buys, sells, bh, sh):
        return None
    m5 = buys + sells
    prior55 = max(0.0, bh + sh - m5)
    if m5 <= 0:
        return None
    return 1_000_000.0 if prior55 <= 0 else m5 / (prior55 / 11.0)


def _volume_acceleration(frame: Mapping[str, Any]) -> float | None:
    m5, h1 = _number(frame.get("volume")), _number(frame.get("volume_h1"))
    if m5 is None or h1 is None or m5 <= 0:
        return None
    prior55 = max(0.0, h1 - m5)
    return 1_000_000.0 if prior55 <= 0 else m5 / (prior55 / 11.0)


def _pct(value: Any) -> float | None:
    number = _number(value)
    return number / 100.0 if number is not None else None


def runner_signal(
    history: list[dict[str, Any]], policy: Mapping[str, Any], *,
    decision_at: Any, activated_at: Any,
) -> tuple[bool, str, dict[str, Any]]:
    """Detect early demand quality, then require a later same-pool fill frame."""
    cfg = policy["entry_filter"]
    evidence: dict[str, Any] = {"contract": CONTRACT, "hypothesis_only": True}
    now, start = _as_time(decision_at), _as_time(activated_at)
    if not history or now is None or start is None:
        return False, "runner_missing_history", evidence
    latest = history[-1]
    observed = _as_time(latest.get("observed_at"))
    ingested = _as_time(latest.get("ingested_at"))
    recorded = _as_time(latest.get("recorded_at"))
    if (None in (observed, ingested, recorded)
            or not start <= observed <= ingested <= recorded <= now
            or (now - observed).total_seconds() > cfg["maximum_frame_age_seconds"]
            or not latest.get("upstream_provider")):
        return False, "runner_noncausal_or_stale_frame", evidence

    price, liq, pair_age = (_number(latest.get(k)) for k in
                            ("price", "liquidity", "pool_age_seconds"))
    token_age = _number(latest.get("token_age_seconds"))
    if token_age is None:
        token_age = pair_age
    floor = max(
        float((policy.get("_execution") or {}).get(
            "min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD)),
        float(cfg["minimum_liquidity_usd"]),
    )
    if (price is None or price <= 0 or liq is None or liq < floor
            or pair_age is None or token_age is None or min(pair_age, token_age) < 0):
        return False, "runner_market_floor_or_age_unknown", evidence
    if (token_age > cfg["maximum_token_age_seconds"]
            or pair_age > cfg["maximum_pair_age_seconds"]):
        return False, "runner_age_outside_early_window", evidence
    if (pair_age <= cfg["migration_pair_age_seconds"]
            and token_age - pair_age >= cfg["migration_token_pair_age_gap_seconds"]):
        return False, "runner_successor_pair_requires_migration_verification", evidence

    buys, sells = _number(latest.get("buys")), _number(latest.get("sells"))
    volume = _number(latest.get("volume"))
    share = _buy_share(latest)
    trades = buys + sells if buys is not None and sells is not None else None
    turnover = volume / liq if volume is not None and liq > 0 else None
    tx_accel = _activity_acceleration(latest)
    volume_accel = _volume_acceleration(latest)
    acceleration = max(x for x in (tx_accel, volume_accel) if x is not None) \
        if any(x is not None for x in (tx_accel, volume_accel)) else None
    price_change_5m = _pct(latest.get("price_change_m5"))
    if (trades is None or trades < cfg["minimum_trades_5m"]
            or share is None or share < cfg["minimum_buy_share"]
            or volume is None or volume <= 0 or turnover is None):
        return False, "runner_activity_quality_not_met", evidence

    common = (
        turnover >= cfg["minimum_turnover"]
        or acceleration is not None and acceleration >= cfg["minimum_activity_acceleration"]
    )
    explosive = bool(
        common
        and price_change_5m is not None
        and price_change_5m >= cfg["explosive_price_change_5m"]
        and trades >= cfg["explosive_minimum_trades_5m"]
        and turnover >= cfg["explosive_minimum_turnover"]
        and acceleration is not None
        and acceleration >= cfg["explosive_minimum_activity_acceleration"]
    )

    selected: list[dict[str, Any]] = []
    for frame in reversed(history):
        at = _as_time(frame.get("observed_at"))
        if at is None or at < start:
            continue
        if (frame.get("token_id") != latest.get("token_id")
                or frame.get("pair_address") != latest.get("pair_address")
                or frame.get("upstream_provider") != latest.get("upstream_provider")):
            continue
        if not selected or (_as_time(selected[-1]["observed_at"]) - at).total_seconds() >= cfg["minimum_spacing_seconds"]:
            selected.append(frame)
            if len(selected) == cfg["persistent_frames"]:
                break
    selected.reverse()

    persistent = False
    progress = efficiency = near_high = retention = None
    if len(selected) == cfg["persistent_frames"]:
        first_at = _as_time(selected[0]["observed_at"])
        span = (observed - first_at).total_seconds() if first_at is not None else -1
        valid = span >= cfg["persistent_minimum_span_seconds"]
        prior_at = None
        prices: list[float] = []
        liquidities: list[float] = []
        for frame in selected:
            at, ing, rec = (_as_time(frame.get(k)) for k in
                            ("observed_at", "ingested_at", "recorded_at"))
            fp, fl = _number(frame.get("price")), _number(frame.get("liquidity"))
            fb, fs = _number(frame.get("buys")), _number(frame.get("sells"))
            if (None in (at, ing, rec, fp, fl, fb, fs)
                    or not start <= at <= ing <= rec <= now
                    or fp <= 0 or fl < floor or min(fb, fs) < 0 or fb + fs < 3
                    or prior_at is not None and not 0 < (at - prior_at).total_seconds() <= cfg["maximum_gap_seconds"]):
                valid = False
                break
            prior_at = at
            prices.append(float(fp))
            liquidities.append(float(fl))
        if valid:
            progress = prices[-1] / prices[0] - 1.0
            efficiency = _path_efficiency(prices)
            near_high = prices[-1] / max(prices)
            retention = min(liquidities) / liquidities[0]
            persistent = bool(
                common
                and progress >= cfg["persistent_return_min"]
                and efficiency >= cfg["persistent_efficiency_min"]
                and near_high >= cfg["persistent_near_high_ratio"]
                and retention >= cfg["minimum_liquidity_retention"]
            )

    passed = explosive or persistent
    route = "explosive" if explosive else "persistent" if persistent else "wait"
    evidence.update(
        route=route,
        signal_observed_at=latest["observed_at"],
        signal_recorded_at=latest["recorded_at"],
        upstream_provider=latest["upstream_provider"],
        pair_address=latest["pair_address"],
        signal_price=float(price),
        liquidity_usd=float(liq),
        token_age_seconds=float(token_age),
        pair_age_seconds=float(pair_age),
        trades_5m=float(trades),
        buy_share=share,
        turnover=turnover,
        tx_rate_acceleration=tx_accel,
        volume_rate_acceleration=volume_accel,
        price_change_5m=price_change_5m,
        selected_frame_ids=[f.get("id") for f in selected],
        path_return=progress,
        path_efficiency=efficiency,
        near_high_ratio=near_high,
        liquidity_retention=retention,
        rolling_activity_is_proxy=True,
    )
    return passed, "runner_" + route + ("_ready" if passed else "_conditions_not_met"), evidence


def post_signal_compatible(
    latest: Mapping[str, Any], evidence: Mapping[str, Any], policy: Mapping[str, Any], *,
    decision_at: Any,
) -> bool:
    """The buy fill must be a later, fresh, same-provider/same-pool observation."""
    cfg = policy["entry_filter"]
    signal_at = _as_time(evidence.get("signal_observed_at"))
    current_at = _as_time(latest.get("observed_at"))
    now = _as_time(decision_at)
    signal_price = _number(evidence.get("signal_price"))
    current_price = _number(latest.get("price"))
    current_liq = _number(latest.get("liquidity"))
    if None in (signal_at, current_at, now, signal_price, current_price, current_liq):
        return False
    dt = (current_at - signal_at).total_seconds()
    floor = max(
        float((policy.get("_execution") or {}).get(
            "min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD)),
        float(cfg["minimum_liquidity_usd"]),
    )
    drift = current_price / signal_price - 1.0
    return bool(
        0 < dt <= cfg["maximum_gap_seconds"]
        and 0 <= (now - current_at).total_seconds() <= cfg["maximum_frame_age_seconds"]
        and latest.get("pair_address") == evidence.get("pair_address")
        and latest.get("upstream_provider") == evidence.get("upstream_provider")
        and current_liq >= floor
        and -cfg["post_signal_max_down_drift"] <= drift <= cfg["post_signal_max_up_drift"]
    )


def evaluate_runner_exit(
    position: Mapping[str, Any], frame: Mapping[str, Any], state: Mapping[str, Any] | None, *,
    now: Any, policy: Mapping[str, Any],
):
    """Causal exhaustion state machine; it does not claim to predict the exact peak."""
    new, evidence, bad = _begin(EXIT_KIND, policy, position, frame, state, now)
    if bad:
        return _result("WAIT", bad, new, evidence)
    price, liq, value, stake = (_number(v) for v in (
        frame.get("price_usd"), frame.get("liquidity_usd"),
        frame.get("economic_value_usd"), position.get("stake_usd"),
    ))
    buys, sells, volume = (_number(frame.get(k)) for k in ("buys", "sells", "volume"))
    if (not frame.get("original_pool") or not frame.get("provider")
            or None in (price, liq, value, stake, buys, sells, volume)
            or price <= 0 or liq < 0 or stake <= 0 or min(buys, sells, volume) < 0
            or buys + sells <= 0):
        new.update(window=[], warning=None, giveback_area=0.0)
        new.pop("giveback_sample", None)
        return _result("WAIT", "runner_exit_incomplete_frame", new, evidence)
    if new.get("exit_triggered"):
        return _result("SELL", "runner_exhaustion_confirmed", new, evidence)

    at = _as_time(frame["observed_at"])
    window = list(new.get("window") or [])
    if window:
        prior_at = _as_time(window[-1]["at"])
        gap = (at - prior_at).total_seconds()
        if (gap > policy["maximum_gap_seconds"]
                or window[-1]["provider"] != frame["provider"]
                or window[-1].get("boundary_at") != frame.get("boundary_at")):
            window = []
            new.update(warning=None, giveback_area=0.0)
            new.pop("giveback_sample", None)
        elif gap < policy["minimum_span_seconds"]:
            return _result("WAIT", "runner_exit_wait_spacing", new, evidence)

    prior_peak_value = float(new.get("peak_value", value))
    peak_value = max(prior_peak_value, float(value))
    prior_peak_price = float(new.get("peak_price", price))
    peak_price = max(prior_peak_price, float(price))
    peak_liq = max(float(new.get("peak_liquidity", liq)), float(liq))
    made_new_value_high = value >= prior_peak_value
    new.update(peak_value=peak_value, peak_price=peak_price, peak_liquidity=peak_liq)
    if made_new_value_high:
        new["warning"] = None
        new["giveback_area"] = 0.0

    share = buys / (buys + sells)
    point = {
        "at": frame["observed_at"], "price": float(price), "value": float(value),
        "liquidity": float(liq), "count": float(buys + sells), "volume": float(volume),
        "share": share, "provider": frame["provider"], "boundary_at": frame.get("boundary_at"),
    }
    window = (window + [point])[-int(policy["window_frames"]):]
    new["window"] = window

    economic_return = value / stake - 1.0
    peak_return = peak_value / stake - 1.0
    drawdown = value / peak_value - 1.0 if peak_value > 0 else 0.0
    trigger = None

    # A high near its running peak with rising activity but falling buy share is
    # a causal exhaustion warning.  This is intentionally stricter than a plain
    # trailing stop so normal early-runner volatility can survive.
    pf = int(policy["plateau_frames"])
    if peak_return >= policy["minimum_peak_return"] and len(window) >= pf:
        recent = window[-pf:]
        prices = [x["price"] for x in recent]
        efficiency = _path_efficiency(prices)
        near_peak = min(prices) >= peak_price * (1.0 - policy["plateau_peak_distance"])
        compact = max(prices) / min(prices) - 1.0 <= policy["plateau_price_range"]
        activity_up = recent[-1]["count"] >= recent[0]["count"] * policy["plateau_activity_growth"]
        share_down = recent[-1]["share"] <= recent[0]["share"] - policy["plateau_buy_share_decay"]
        if (near_peak and compact and activity_up and share_down
                and abs(efficiency) <= policy["plateau_efficiency_abs"]):
            trigger = "runner_crowded_plateau_exhaustion"
            evidence.update(
                plateau_frame_count=pf, plateau_efficiency=efficiency,
                plateau_activity_growth=recent[-1]["count"] / max(1.0, recent[0]["count"]),
                plateau_buy_share_change=recent[-1]["share"] - recent[0]["share"],
            )

    # Volatility-scaled warning: a drawdown alone never exits.  We wait for
    # either demand deterioration or a failed rebound/second break.
    returns = [abs(log(b["price"] / a["price"])) for a, b in zip(window, window[1:])
               if a["price"] > 0 and b["price"] > 0]
    local_vol = median(returns[-6:]) if returns else 0.0
    warning_threshold = min(
        policy["warning_drawdown_ceiling"],
        max(policy["warning_drawdown_floor"],
            policy["warning_volatility_multiplier"] * local_vol),
    )
    warning = dict(new.get("warning") or {})
    if trigger is None and peak_return >= policy["minimum_peak_return"]:
        if drawdown <= -warning_threshold:
            prior_warning_low = float(warning.get("low_price", price)) if warning else None
            if not warning:
                warning = {
                    "peak_price": peak_price, "low_price": float(price),
                    "bounced": False, "bad_streak": 0,
                    "threshold": warning_threshold,
                }
            if price >= float(warning["peak_price"]) * policy["warning_peak_reclaim_ratio"]:
                warning = {}
            else:
                if price >= float(warning["low_price"]) * policy["warning_rebound_ratio"]:
                    warning["bounced"] = True
                bad_share = share <= policy["warning_bad_share"]
                warning["bad_streak"] = int(warning.get("bad_streak", 0)) + 1 if bad_share else 0
                second_break = (warning.get("bounced") and prior_warning_low is not None
                    and price <= prior_warning_low * policy["warning_second_break_ratio"])
                warning["low_price"] = min(float(warning.get("low_price", price)), float(price))
                if second_break:
                    trigger = "runner_failed_rebound_second_break"
                elif int(warning.get("bad_streak", 0)) >= policy["warning_bad_streak"]:
                    trigger = "runner_drawdown_with_demand_deterioration"
        elif warning and price >= float(warning.get("low_price", price)) * policy["warning_rebound_ratio"]:
            warning["bounced"] = True
        new["warning"] = warning or None

    # Time-integrated giveback avoids reacting to a single wick while preventing
    # a large winner from leaking for minutes after the peak.
    sample = new.get("giveback_sample")
    area = float(new.get("giveback_area", 0.0))
    if peak_return >= policy["giveback_peak_return"] and drawdown < 0:
        if sample:
            sample_at = _as_time(sample.get("at"))
            dt = (at - sample_at).total_seconds() if sample_at is not None else 0.0
            if 0 < dt <= policy["maximum_gap_seconds"]:
                area += max(0.0, -float(sample.get("drawdown", 0.0))) * dt
        new["giveback_sample"] = {"at": frame["observed_at"], "drawdown": drawdown}
        new["giveback_area"] = area
        if trigger is None and area >= policy["giveback_area_budget"]:
            trigger = "runner_sustained_giveback_budget"
    else:
        new["giveback_area"] = 0.0
        new["giveback_sample"] = {"at": frame["observed_at"], "drawdown": drawdown}

    if (trigger is None and peak_return >= policy["minimum_peak_return"]
            and liq <= peak_liq * policy["liquidity_peak_retention"]
            and drawdown <= -policy["liquidity_break_drawdown"]):
        trigger = "runner_liquidity_and_price_break"

    evidence.update(
        economic_return=economic_return,
        peak_economic_return=peak_return,
        drawdown_from_peak=drawdown,
        local_log_volatility=local_vol,
        warning_drawdown_threshold=warning_threshold,
        buy_share=share,
        giveback_area_fraction_seconds=float(new.get("giveback_area", 0.0)),
        peak_liquidity_usd=peak_liq,
        required_fill="next_original_pool_frame",
        exact_peak_prediction=False,
    )
    if trigger is not None:
        new["exit_triggered"] = True
        new["exit_reason"] = trigger
        return _result("SELL", trigger, new, evidence)
    return _result("HOLD", "runner_exhaustion_monitoring", new, evidence)
