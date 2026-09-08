"""Entry opportunity and exit hazard are separate, unproven Paper hypotheses."""
from copy import deepcopy

from .capital_exits import _as_time, _begin, _number, _result
from .models import CHAIN_MEME_MIN_POOL_LIQUIDITY_USD
from .runner_capture import runner_policies

CONTRACT = "early-impulse-opportunity/20260908-v1"
EXIT_KIND = "impulse_probation"


def impulse_policies():
    parent = runner_policies()[1]
    result = []
    for suffix, title, minutes in (
        ("control_15m", "15分钟对照", 15.),
        ("trailing_60m", "60分钟追踪", 60.),
        ("probation_60m", "10分钟续持检查", 60.),
    ):
        p = deepcopy(parent)
        arm = "early_impulse_" + suffix + "_v1"
        p.update(arm_id=arm, canonical_id=arm, name="早期放量上涨·" + title,
                 description="5分钟成交≥200且上涨≥10%的小额机会实验；同次成交比较退出，未证明Alpha。",
                 entry_family="early_impulse_opportunity", source_entry_family="early_impulse_opportunity",
                 entry_gate="early_impulse_opportunity_v1", max_hold_minutes=minutes,
                 source_arm_ids=[], paired_entry_group="early_impulse_same_fill_v1", paired_entry_size=3,
                 evidence_review="docs/PROJECT_CONTEXT/EARLY_IMPULSE_PAPER_20260908.md")
        p["entry_filter"] = {
            "contract": CONTRACT, "direction": "early_impulse_opportunity",
            "max_concurrent_positions": 4, "single_token_lifetime_entry": True,
            "occupied_signal_policy": "reject_without_queue_or_replay",
            "maximum_frame_age_seconds": 15, "maximum_gap_seconds": 30,
            "minimum_liquidity_usd": 5000., "maximum_pair_age_seconds": 900,
            "minimum_trades_5m": 200, "minimum_price_change_5m_pct": 10.,
            "post_signal_max_up_drift": .30, "post_signal_max_down_drift": .18,
        }
        if suffix == "probation_60m":
            p.update(capital_exit_kind=EXIT_KIND, capital_exit_policy={
                "version": CONTRACT + "/probation-v1", "maximum_frame_age_seconds": 15,
                "baseline_seconds": 300, "review_seconds": 600, "checkpoint_tolerance_seconds": 30,
                "activation_return": .30, "price_retention_max": .98, "activity_retention_max": .80,
            })
        result.append(p)
    return result


def impulse_signal(history, policy, *, decision_at, activated_at):
    cfg = policy["entry_filter"]
    evidence = {"contract": CONTRACT, "hypothesis_only": True, "rolling_activity_is_proxy": True}
    now, start = _as_time(decision_at), _as_time(activated_at)
    if not history or now is None or start is None:
        return False, "impulse_missing_history", evidence
    f = history[-1]
    at, ing, rec = (_as_time(f.get(k)) for k in ("observed_at", "ingested_at", "recorded_at"))
    if (None in (at, ing, rec) or not start <= at <= ing <= rec <= now
            or (now - at).total_seconds() > cfg["maximum_frame_age_seconds"]
            or not all(f.get(k) for k in ("token_id", "pair_address", "upstream_provider"))):
        return False, "impulse_noncausal_or_stale_identity", evidence
    price, liq, age, buys, sells, pc = (_number(f.get(k)) for k in
        ("price", "liquidity", "pool_age_seconds", "buys", "sells", "price_change_m5"))
    floor = max(cfg["minimum_liquidity_usd"], float((policy.get("_execution") or {}).get(
        "min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD)))
    if (None in (price, liq, age, buys, sells, pc) or price <= 0 or liq < floor
            or min(buys, sells) < 0 or not 0 <= age <= cfg["maximum_pair_age_seconds"]):
        return False, "impulse_market_floor_age_or_fields", evidence
    passed = buys + sells >= cfg["minimum_trades_5m"] and pc >= cfg["minimum_price_change_5m_pct"]
    evidence.update(signal_observed_at=f["observed_at"], signal_recorded_at=f["recorded_at"],
                    signal_price=price, pair_address=f["pair_address"], upstream_provider=f["upstream_provider"],
                    trades_5m=buys + sells, price_change_m5_pct=pc, pair_age_seconds=age)
    return passed, "impulse_opportunity_ready" if passed else "impulse_conditions_not_met", evidence


def evaluate_impulse_probation(position, frame, state, *, now, policy):
    new, evidence, bad = _begin(EXIT_KIND, policy, position, frame, state, now)
    if bad:
        return _result("WAIT", bad, new, evidence)
    if new.get("review_done"):
        return _result("WAIT", "impulse_probation_already_reviewed", new, evidence)
    elapsed = evidence["elapsed_seconds"]
    tolerance = policy["checkpoint_tolerance_seconds"]
    if elapsed > policy["review_seconds"] + tolerance:
        new["review_done"] = True
        return _result("WAIT", "impulse_probation_checkpoint_missed", new, evidence)
    price, value, stake, buys, sells = (_number(x) for x in (
        frame.get("price_usd"), frame.get("economic_value_usd"), position.get("stake_usd"),
        frame.get("buys"), frame.get("sells")))
    if (not frame.get("original_pool") or not frame.get("provider")
            or None in (price, value, stake, buys, sells) or price <= 0 or stake <= 0 or min(buys, sells) < 0):
        return _result("WAIT", "impulse_probation_incomplete_frame", new, evidence)
    # Use the persisted whole-position high, not just sparse checkpoint prices.
    high = max(value, _number(position.get("highest_economic_value_usd")) or 0)
    if high >= stake * (1 + policy["activation_return"]):
        new["review_done"] = True
        return _result("WAIT", "impulse_probation_trailing_activated", new, evidence)
    if policy["baseline_seconds"] <= elapsed <= policy["baseline_seconds"] + tolerance and "baseline" not in new:
        new["baseline"] = {"price": price, "trades": buys + sells, "provider": frame["provider"],
                           "observed_at": frame["observed_at"], "boundary_at": frame.get("boundary_at")}
    if elapsed < policy["review_seconds"]:
        return _result("WAIT", "impulse_probation_wait_checkpoint", new, evidence)
    baseline = new.get("baseline")
    new["review_done"] = True
    if (not baseline or baseline["trades"] <= 0 or baseline["provider"] != frame["provider"]
            or baseline.get("boundary_at") != frame.get("boundary_at")):
        return _result("WAIT", "impulse_probation_baseline_unavailable", new, evidence)
    weak = (value <= stake and price <= baseline["price"] * policy["price_retention_max"]
            and buys + sells <= baseline["trades"] * policy["activity_retention_max"])
    evidence.update(baseline=baseline, price_retention=price / baseline["price"],
                    activity_retention=(buys + sells) / baseline["trades"], economic_return=value / stake - 1,
                    required_fill="next_original_pool_frame")
    return _result("SELL" if weak else "WAIT",
                   "impulse_probation_failed_renewal" if weak else "impulse_probation_continue", new, evidence)
