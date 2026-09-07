"""Archive-inspired, unproven path/activity hypotheses using fresh local frames.

Rolling counts are overlapping window proxies, not wallets or actual net flow.
The historical archive is never read by the runtime or used to seed a position.
"""
from copy import deepcopy
from math import log

from .capital_exits import _as_time, _begin, _number, _result

CONTRACT = "archive-path-activity/20260908-v1"
EXIT_KIND = "archive_crowded_plateau"


def archive_policies():
    from .research_finalists import finalist_policies
    parent = next(p for p in finalist_policies() if p["arm_id"] == "finalist_baseline_v1")
    result = []
    for kind, name in (("drift", "低参与高效率漂移"),
                       ("plateau", "低参与漂移与拥挤平台退出"),
                       ("release", "高活动停滞后效率释放")):
        p = deepcopy(parent)
        for key in ("paired_entry_group", "paired_entry_size", "capital_exit_kind", "capital_exit_policy"):
            p.pop(key, None)
        arm = "archive_" + kind + "_v1"
        direction = "release" if kind == "release" else "drift"
        p.update(arm_id=arm, canonical_id=arm, name=name,
            description=name + "；历史结构启发的待证伪假设，5U/最多4仓，非已验证Alpha。",
            source_arm_ids=[parent["arm_id"]], entry_family=direction,
            source_entry_family=direction, notional_usd=5.,
            evidence_review="docs/PROJECT_CONTEXT/ARCHIVE_RESEARCH_20260908.md")
        p["entry_filter"] = {"contract": CONTRACT, "direction": direction,
            "control": False, "max_gap_seconds": 30, "max_concurrent_positions": 4,
            "occupied_signal_policy": "reject_without_queue_or_replay",
            "independent_frames": 6, "minimum_spacing_seconds": 15,
            "maximum_frame_age_seconds": 15, "drift_efficiency": .75,
            "drift_return_min": .06, "drift_return_max": .25,
            "churn_activity_min": 2., "release_return_min": .06}
        if kind != "release":
            p.update(paired_entry_group="archive_plateau_matched_v1", paired_entry_size=2)
        if kind == "plateau":
            p.update(capital_exit_kind=EXIT_KIND, capital_exit_policy={
                "version": CONTRACT + "/plateau", "kind": EXIT_KIND,
                "maximum_frame_age_seconds": 15, "minimum_span_seconds": 5,
                "maximum_gap_seconds": 30, "frames": 6, "net_profit_min": .10,
                "price_range_max": .015, "peak_distance_max": .02,
                "activity_growth_min": 1.30, "efficiency_max": .25})
        result.append(p)
    return result


def path_efficiency(prices):
    changes = [log(b / a) for a, b in zip(prices, prices[1:])]
    distance = sum(abs(x) for x in changes)
    return sum(changes) / distance if distance else 0.


def archive_signal(history, policy, *, decision_at, activated_at):
    now, start = _as_time(decision_at), _as_time(activated_at)
    evidence = {"contract": CONTRACT, "hypothesis_only": True}
    if not history or now is None or start is None:
        return False, "archive_missing_history", evidence
    latest, cfg = history[-1], policy["entry_filter"]
    last_at = _as_time(latest.get("observed_at"))
    if last_at is None or not 0 <= (now - last_at).total_seconds() <= cfg["maximum_frame_age_seconds"]:
        return False, "archive_stale_frame", evidence
    selected = []
    for f in reversed(history):
        at = _as_time(f.get("observed_at"))
        if at is None or at < start:
            continue
        if not selected or (_as_time(selected[-1]["observed_at"]) - at).total_seconds() >= cfg["minimum_spacing_seconds"]:
            selected.append(f)
            if len(selected) == cfg["independent_frames"]:
                break
    if len(selected) < cfg["independent_frames"]:
        return False, "archive_wait_independent_frames", evidence
    selected.reverse()
    first_at = _as_time(selected[0]["observed_at"])
    floor = max(.01, float((policy.get("_execution") or {}).get("min_pool_liquidity_usd", 1000)))
    prior = None
    # Validate every middle frame, not just the independently spaced subset.
    for f in history:
        observed, ingested, recorded = (_as_time(f.get(k)) for k in ("observed_at", "ingested_at", "recorded_at"))
        if observed is not None and observed < first_at:
            continue
        if (None in (observed, ingested, recorded) or not start <= observed <= ingested <= recorded <= now
                or prior is not None and not 0 < (observed - prior).total_seconds() <= cfg["max_gap_seconds"]):
            return False, "archive_noncausal_or_gap", evidence
        if (f.get("token_id") != latest.get("token_id") or f.get("pair_address") != latest.get("pair_address")
                or not f.get("upstream_provider") or f.get("upstream_provider") != latest.get("upstream_provider")):
            return False, "archive_identity_or_source_boundary", evidence
        price, liq, vol, buys, sells, bh, sh, age = (_number(f.get(k)) for k in
            ("price", "liquidity", "volume", "buys", "sells", "buys_h1", "sells_h1", "pool_age_seconds"))
        if (None in (price, liq, vol, buys, sells, bh, sh, age) or price <= 0 or liq < floor
                or vol <= 0 or min(buys, sells, bh, sh) < 0 or buys + sells < 3
                or bh < buys or sh < sells or bh + sh <= buys + sells
                or not 3600 <= age <= 86400):
            return False, "archive_incomplete_or_immature_window", evidence
        prior = observed
    prices = [f["price"] for f in selected]
    activity = [11 * (f["buys"] + f["sells"]) /
        (f["buys_h1"] + f["sells_h1"] - f["buys"] - f["sells"]) for f in selected]
    shares = [f["buys"] / (f["buys"] + f["sells"]) for f in selected]
    efficiency, progress = path_efficiency(prices), prices[-1] / prices[0] - 1
    if cfg["direction"] == "drift":
        passed = (cfg["drift_return_min"] <= progress <= cfg["drift_return_max"]
            and efficiency >= cfg["drift_efficiency"] and max(activity[-3:]) < 1
            and min(shares[-3:]) >= .55)
    else:
        passed = (max(prices[:3]) / min(prices[:3]) <= 1.04
            and min(activity[:3]) >= cfg["churn_activity_min"]
            and prices[-1] >= max(prices[:3]) * (1 + cfg["release_return_min"])
            and path_efficiency(prices[3:]) >= .6 and min(activity[3:]) >= 1.5
            and shares[-1] >= sum(shares[:3]) / 3 + .10)
    evidence.update(frame_ids=[f["id"] for f in selected], prices=prices,
        activity_ratio=activity, buy_share=shares, efficiency=efficiency, price_return=progress,
        upstream_provider=latest["upstream_provider"], signal_observed_at=latest["observed_at"])
    return bool(passed), "archive_" + cfg["direction"] + ("_ready" if passed else "_wait"), evidence


def post_signal_compatible(latest, evidence, *, decision_at):
    previous, current, now = (_as_time(x) for x in
        (evidence.get("signal_observed_at"), latest.get("observed_at"), decision_at))
    return (None not in (previous, current, now) and 0 < (current - previous).total_seconds() <= 30
        and 0 <= (now - current).total_seconds() <= 15
        and latest.get("upstream_provider") == evidence.get("upstream_provider"))


def evaluate_plateau_exit(position, frame, state, *, now, policy):
    new, evidence, bad = _begin(EXIT_KIND, policy, position, frame, state, now)
    if bad:
        return _result("WAIT", bad, new, evidence)
    price, buys, sells, value, stake = (_number(v) for v in (frame.get("price_usd"),
        frame.get("buys"), frame.get("sells"), frame.get("economic_value_usd"), position.get("stake_usd")))
    if (not frame.get("original_pool") or not frame.get("provider")
            or None in (price, buys, sells, value, stake) or price <= 0 or stake <= 0
            or min(buys, sells) < 0 or buys + sells < 3):
        new["window"] = []
        return _result("WAIT", "archive_plateau_incomplete_frame", new, evidence)
    if new.get("phase") == "EXIT_TRIGGERED":
        return _result("SELL", "archive_plateau_confirmed", new, evidence)
    window = new.get("window") or []
    peak = max(float(new.get("peak_price", price)), price)
    new["peak_price"] = peak
    if window:
        gap = (_as_time(frame["observed_at"]) - _as_time(window[-1]["at"])).total_seconds()
        if (gap > policy["maximum_gap_seconds"] or window[-1]["provider"] != frame["provider"]
                or window[-1].get("boundary_at") != frame.get("boundary_at")):
            window = []
        elif gap < policy["minimum_span_seconds"]:
            return _result("WAIT", "archive_plateau_wait_spacing", new, evidence)
    window = (window + [{"at": frame["observed_at"], "id": frame["frame_id"],
        "price": price, "count": buys + sells, "share": buys / (buys + sells),
        "provider": frame["provider"], "boundary_at": frame.get("boundary_at")}])[-policy["frames"]:]
    new["window"] = window
    trigger = False
    if len(window) == policy["frames"]:
        prices = [f["price"] for f in window]
        efficiency = path_efficiency(prices)
        trigger = (value / stake - 1 >= policy["net_profit_min"]
            and min(prices) >= peak * (1 - policy["peak_distance_max"])
            and max(prices) / min(prices) - 1 <= policy["price_range_max"]
            and abs(efficiency) <= policy["efficiency_max"]
            and window[-1]["count"] >= window[0]["count"] * policy["activity_growth_min"]
            and window[-1]["share"] <= window[0]["share"])
        evidence.update(frame_ids=[f["id"] for f in window], efficiency=efficiency,
            activity_growth=window[-1]["count"] / window[0]["count"])
    evidence.update(peak_price=peak, economic_return=value / stake - 1,
        rolling_counts_are_flow=False, required_fill="next_original_pool_frame")
    if trigger:
        new["phase"] = "EXIT_TRIGGERED"
    return _result("SELL" if trigger else "HOLD", "archive_plateau_confirmed" if trigger else
        "archive_plateau_monitoring", new, evidence)
