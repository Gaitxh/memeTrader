"""Unproven quiet-base demand renewal, using only deployment-forward frames."""
from statistics import median

from .capital_exits import _as_time, _number
from .models import CHAIN_MEME_MIN_POOL_LIQUIDITY_USD
from .runner_capture import runner_policies

CONTRACT = "quiet-base-renewal/20260908-v1"


def renewal_policies():
    result = runner_policies()
    for p in result:
        control = p["entry_filter"]["control"]
        arm = "quiet_renewal_legacy_exit_control_v1" if control else "quiet_renewal_v1"
        p.update(arm_id=arm, canonical_id=arm,
                 name="安静底部需求恢复·" + ("旧式退出对照" if control else "尾部持有"),
                 description="同池连续安静底部后两帧需求恢复；5U/最多4仓，独立前向假设。",
                 entry_family="quiet_renewal", source_entry_family="quiet_renewal",
                 entry_gate="quiet_base_renewal_v1", paired_entry_group="quiet_renewal_same_fill_v1",
                 evidence_review="docs/PROJECT_CONTEXT/EARLY_WINNERS_20260908.md")
        p["entry_filter"] = {
            "contract": CONTRACT, "direction": "quiet_renewal", "control": control,
            "max_concurrent_positions": 4, "single_token_lifetime_entry": True,
            "occupied_signal_policy": "reject_without_queue_or_replay",
            "maximum_frame_age_seconds": 15, "maximum_gap_seconds": 30,
            "minimum_spacing_seconds": 15, "base_frames": 13,
            "minimum_base_span_seconds": 180, "base_range_max": .04,
            "base_turnover_max": .20, "minimum_liquidity_usd": 5000.,
            "minimum_pair_age_seconds": 600, "maximum_pair_age_seconds": 259200,
            "breakout_ratio": 1.08, "demand_growth": 1.5,
            "minimum_trades_5m": 10, "minimum_liquidity_retention": .80,
            "post_signal_max_up_drift": .30, "post_signal_max_down_drift": .18,
        }
    return result


def renewal_signal(history, policy, *, decision_at, activated_at):
    cfg = policy["entry_filter"]
    evidence = {"contract": CONTRACT, "hypothesis_only": True, "rolling_activity_is_proxy": True}
    now, start = _as_time(decision_at), _as_time(activated_at)
    if not history or now is None or start is None:
        return False, "renewal_missing_history", evidence
    latest = history[-1]
    end = _as_time(latest.get("observed_at"))
    if end is None or not 0 <= (now - end).total_seconds() <= cfg["maximum_frame_age_seconds"]:
        return False, "renewal_stale_frame", evidence
    selected = []
    for f in reversed(history):
        at = _as_time(f.get("observed_at"))
        if at is None or at < start:
            continue
        if not selected or (_as_time(selected[-1]["observed_at"]) - at).total_seconds() >= cfg["minimum_spacing_seconds"]:
            selected.append(f)
            if len(selected) == cfg["base_frames"] + 2:
                break
    if len(selected) < cfg["base_frames"] + 2:
        return False, "renewal_wait_base", evidence
    selected.reverse()
    first = _as_time(selected[0]["observed_at"])
    floor = max(cfg["minimum_liquidity_usd"], float((policy.get("_execution") or {}).get(
        "min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD)))
    prior = None
    # Check intervening frames too: spacing must not hide a bad source or timestamp.
    for f in history:
        at, ing, rec = (_as_time(f.get(k)) for k in ("observed_at", "ingested_at", "recorded_at"))
        if at is not None and at < first:
            continue
        if (None in (at, ing, rec) or not start <= at <= ing <= rec <= now
                or prior is not None and not 0 < (at - prior).total_seconds() <= cfg["maximum_gap_seconds"]):
            return False, "renewal_noncausal_or_gap", evidence
        if (not latest.get("upstream_provider") or any(f.get(k) != latest.get(k)
                for k in ("token_id", "pair_address", "upstream_provider"))):
            return False, "renewal_identity_or_source", evidence
        price, liq, vol, buys, sells = (_number(f.get(k)) for k in
                                     ("price", "liquidity", "volume", "buys", "sells"))
        if (None in (price, liq, vol, buys, sells) or price <= 0 or liq < floor
                or min(vol, buys, sells) < 0):
            return False, "renewal_market_missing_or_floor", evidence
        prior = at
    age = _number(latest.get("pool_age_seconds"))
    if age is None or not cfg["minimum_pair_age_seconds"] <= age <= cfg["maximum_pair_age_seconds"]:
        return False, "renewal_age_outside_window", evidence
    base, release = selected[:-2], selected[-2:]
    if (_as_time(base[-1]["observed_at"]) - first).total_seconds() < cfg["minimum_base_span_seconds"]:
        return False, "renewal_short_base", evidence
    prices = [float(f["price"]) for f in base]
    base_trades = median(float(f["buys"]) + float(f["sells"]) for f in base)
    turnover = median(float(f["volume"]) / float(f["liquidity"]) for f in base)
    retention = min(float(f["liquidity"]) for f in selected) / float(base[0]["liquidity"])
    passed = (max(prices) / min(prices) - 1 <= cfg["base_range_max"]
              and turnover <= cfg["base_turnover_max"]
              and retention >= cfg["minimum_liquidity_retention"]
              and all(float(f["price"]) >= max(prices) * cfg["breakout_ratio"]
                      and float(f["buys"]) + float(f["sells"]) >= max(
                          cfg["minimum_trades_5m"], base_trades * cfg["demand_growth"])
                      for f in release)
              and float(release[-1]["price"]) >= float(release[0]["price"]))
    evidence.update(signal_observed_at=latest["observed_at"], signal_recorded_at=latest["recorded_at"],
                    signal_price=float(latest["price"]), pair_address=latest["pair_address"],
                    upstream_provider=latest["upstream_provider"],
                    base_range=max(prices) / min(prices) - 1, base_trades_5m=base_trades,
                    base_turnover=turnover, liquidity_retention=retention,
                    selected_frame_ids=[f.get("id") for f in selected])
    return passed, "renewal_ready" if passed else "renewal_conditions_not_met", evidence
