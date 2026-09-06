"""Preregistered L0 hypotheses from the 2026-09-07 evidence review, not alpha.

Bounded existing observer frames only; no network, database or future labels.
Rolling m5 counts/volume are proxies, never independent wallets or net flow.
"""
from __future__ import annotations

from copy import deepcopy
from statistics import median

from .capital_exits import _as_time, _begin, _number, _result
from .models import CHAIN_MEME_MIN_POOL_LIQUIDITY_USD


CONTRACT = "all-history-finalists/20260907-v1"
EXIT_KINDS = frozenset({"finalist_profit_budget", "finalist_progress_clock",
                        "finalist_depth_divergence", "finalist_activity_failure"})


def finalist_policies():
    from .forward_patterns import experiment_policies
    template = next(p for p in experiment_policies()
                    if p["arm_id"] == "experiment_sustained_breakout_candidate_v1")
    entries = (
        ("boundary_retest", "冻结突破边界回测再启动"),
        ("seller_absorption", "卖方笔数占优后承接翻转"),
        ("price_then_depth", "价格先行后流动性追认"),
    )
    exits = (("baseline", "共同入场退出基线"),
             ("profit_budget", "净利润预算回吐退出"),
             ("progress_clock", "有效进展时钟退出"),
             ("depth_divergence", "增流动性却跌价退出"),
             ("activity_failure", "活跃增加却跌价退出"))
    result = []
    for kind, name in entries + exits:
        p = deepcopy(template)
        arm = f"finalist_{kind}_v1"
        is_exit = (kind, name) in exits
        p.update(arm_id=arm, canonical_id=arm, name=name,
                 description=name + "；全历史复核后的独立假设，未证明盈利；5U/最多4仓。",
                 notional_usd=5.0, max_hold_minutes=30.0,
                 require_post_decision_observation=True,
                 source_arm_ids=["experiment_conditional_runner_candidate_v1"] if is_exit
                     else ["experiment_sustained_breakout_candidate_v1"],
                 evidence_review="docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/FINAL_CONTRACT.md")
        direction = "conditional_runner" if is_exit else kind
        p.update(entry_family=direction, source_entry_family=direction)
        p["entry_filter"] = {"direction": direction, "control": False,
            "contract": "forward-patterns/v1" if is_exit else CONTRACT,
            "max_gap_seconds": 60, "max_concurrent_positions": 4,
            "occupied_signal_policy": "reject_without_queue_or_replay"}
        if is_exit:
            p.update(take_profit=[], paired_entry_group="finalist_exit_matched_v1",
                     paired_entry_size=5)
            if kind != "baseline":
                p.update(capital_exit_kind="finalist_" + kind,
                         capital_exit_policy={"version": CONTRACT + "/" + kind,
                             "kind": "finalist_" + kind, "maximum_frame_age_seconds": 15,
                             "minimum_span_seconds": 5, "maximum_gap_seconds": 60,
                             "profit_arm_fraction": .20, "profit_retrace_fraction": .50,
                             "progress_fraction": .01, "no_progress_seconds": 180})
        result.append(p)
    return result


def finalist_signal(history, policy, *, decision_at, activated_at):
    """Nine independently spaced observations, three ordered phases, then fill later."""
    now, start = _as_time(decision_at), _as_time(activated_at)
    if not history or now is None or start is None:
        return False, "finalist_missing_history"
    latest = history[-1]
    last_at = _as_time(latest.get("observed_at"))
    if last_at is None or not 0 <= (now - last_at).total_seconds() <= 30:
        return False, "finalist_stale_frame"
    # Select backwards so dense sampling never drops the actual latest frame.
    selected = []
    for frame in reversed(history):
        observed = _as_time(frame.get("observed_at"))
        if observed is None or observed < start:
            continue
        if not selected or (selected[-1][0] - observed).total_seconds() >= 15:
            selected.append((observed, frame))
            if len(selected) == 9:
                break
    if len(selected) < 9:
        return False, "finalist_awaiting_nine_independent_frames"
    selected.reverse()
    if not 120 <= (last_at - selected[0][0]).total_seconds() <= 600:
        return False, "finalist_sequence_span"
    # Reject holes, cross-pool/source stitching and unavailable values inside the
    # selected time window; never remove a bad middle frame to manufacture a path.
    floor = float(policy.get("_execution", {}).get(
        "min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD))
    provider = latest.get("upstream_provider")
    prior_at = None
    for frame in history:
        observed = _as_time(frame.get("observed_at"))
        if observed is not None and observed < selected[0][0]:
            continue
        ingested, recorded = _as_time(frame.get("ingested_at")), _as_time(frame.get("recorded_at"))
        if (None in (observed, ingested, recorded)
                or not start <= observed <= ingested <= recorded <= now):
            return False, "finalist_noncausal_frame"
        if frame.get("token_id") != latest.get("token_id") or frame.get("pair_address") != latest.get("pair_address"):
            return False, "finalist_identity_mismatch"
        if not provider or frame.get("upstream_provider") != provider:
            return False, "finalist_source_boundary"
        if prior_at is not None and not 0 < (observed - prior_at).total_seconds() <= 60:
            return False, "finalist_observation_gap"
        prior_at = observed
        price, liq = _number(frame.get("price")), _number(frame.get("liquidity"))
        buys, sells, vol = (_number(frame.get(k)) for k in ("buys", "sells", "volume"))
        if (price is None or price <= 0 or liq is None or liq < max(floor, .01)
                or buys is None or sells is None or min(buys, sells) < 0
                or buys + sells < 3 or vol is None or vol <= 0):
            return False, "finalist_incomplete_l0"
    frames = [f for _, f in selected]
    age = _number(latest.get("pool_age_seconds"))
    if age is None or not 120 <= age <= 86400:
        return False, "finalist_age_outside_contract"
    p = [float(f["price"]) for f in frames]
    liq = [float(f["liquidity"]) for f in frames]
    share = [f["buys"] / (f["buys"] + f["sells"]) for f in frames]
    a, b, c = p[:3], p[3:6], p[6:]
    direction = policy["entry_filter"]["direction"]
    retained = min(liq[3:]) >= .85 * median(liq[:3])
    if direction == "boundary_retest":
        boundary = max(a)
        passed = (max(a) / min(a) <= 1.04 and min(b) >= boundary * 1.06
                  and max(b) <= boundary * 1.35
                  and .98 <= min(c) / boundary <= 1.04
                  and c[-1] >= boundary * 1.06 and c[-1] >= c[-2] * 1.02
                  and c[-1] <= max(b) * 1.03 and min(share[-2:]) >= .55)
    elif direction == "seller_absorption":
        passed = (max(share[:3]) <= .45 and max(a) / min(a) <= 1.08
                  and min(b) >= .95 * min(a)
                  and median(share[:3]) + .05 <= median(share[3:6]) <= .55
                  and min(share[-3:]) >= .60 and c[0] <= c[1] < c[2]
                  and 1.06 <= c[-1] / median(a) <= 1.25)
    elif direction == "price_then_depth":
        passed = (max(a) / min(a) <= 1.04 and 1.10 <= median(b) / median(a) <= 1.30
                  and max(liq[3:6]) <= median(liq[:3]) * 1.05
                  and .97 <= min(c) / median(b) and max(c) / median(b) <= 1.05
                  and liq[-1] >= median(liq[:3]) * 1.20
                  and liq[-3] < liq[-2] <= liq[-1] and min(share[-2:]) >= .55)
    else:
        return False, "finalist_unknown_direction"
    return bool(passed and retained), "finalist_" + direction + ("_ready" if passed and retained else "_wait")


def evaluate_finalist_exit(position, frame, state=None, *, now, policy):
    """O(1) state per position. Net economic value, never a synthetic raw amount."""
    kind = policy["kind"]
    new, evidence, error = _begin(kind, policy, position, frame, state, now)
    if error:
        return _result("WAIT", error, new, evidence)
    price, liq, value, stake = (_number(v) for v in (
        frame.get("price_usd"), frame.get("liquidity_usd"),
        frame.get("economic_value_usd"), position.get("stake_usd")))
    if (not frame.get("original_pool") or not str(frame.get("provider") or "").strip()
            or price is None or price <= 0 or liq is None
            or liq < 0 or value is None or stake is None or stake <= 0):
        new.pop("accepted", None)
        new["bad_streak"] = 0
        return _result("WAIT", "finalist_incomplete_exit_frame", new, evidence)
    if new.get("status") == "EXIT_TRIGGERED":
        return _result("HOLD", "finalist_exit_already_triggered", new, evidence)
    at = _as_time(frame["observed_at"])
    prior = new.get("accepted")
    gap = (at - _as_time(prior["at"])).total_seconds() if prior else None
    if gap is not None and gap < policy["minimum_span_seconds"]:
        return _result("WAIT", "finalist_frame_too_close", dict(state or {}), evidence)
    provider = frame.get("provider")
    reset = not prior or gap > policy["maximum_gap_seconds"] or prior.get("provider") != provider
    if reset:
        prior = None
        new.update(bad_streak=0, progress_value=value, progress_at=at.isoformat(),
                   peak_profit=value-stake)
    profit = value - stake
    new["peak_profit"] = max(float(new.get("peak_profit", profit)), profit)
    trigger = False
    share = volume = None
    if kind == "finalist_progress_clock":
        if value >= float(new["progress_value"]) + stake * policy["progress_fraction"]:
            new.update(progress_value=value, progress_at=at.isoformat())
        trigger = (at - _as_time(new["progress_at"])).total_seconds() >= policy["no_progress_seconds"]
    elif kind == "finalist_profit_budget":
        bad = (new["peak_profit"] >= stake * policy["profit_arm_fraction"]
               and profit <= new["peak_profit"] * (1 - policy["profit_retrace_fraction"]))
        new["bad_streak"] = int(new.get("bad_streak", 0)) + 1 if bad and prior else 0
        trigger = new["bad_streak"] >= 2
    else:
        buys, sells, volume = (_number(frame.get(k)) for k in ("buys", "sells", "volume"))
        share = buys / (buys + sells) if buys is not None and sells is not None and min(buys, sells) >= 0 and buys + sells > 0 else None
        bad = bool(prior and provider and price < prior["price"] and value < prior["value"])
        if kind == "finalist_depth_divergence":
            bad = bad and liq > prior["liquidity"] * 1.01
        elif kind == "finalist_activity_failure":
            bad = (bad and share is not None and volume is not None
                   and prior.get("share") is not None and prior.get("volume") is not None
                   and share > prior["share"] and volume > prior["volume"] * 1.02)
        else:
            return _result("WAIT", "finalist_unknown_exit", dict(state or {}), evidence)
        new["bad_streak"] = int(new.get("bad_streak", 0)) + 1 if bad else 0
        trigger = new["bad_streak"] >= 2
    new["accepted"] = {"at": at.isoformat(), "price": price, "liquidity": liq,
                       "value": value, "provider": provider,
                       "share": share, "volume": volume}
    evidence.update(economic_value_usd=value, net_profit_usd=profit,
                    peak_profit_usd=new["peak_profit"], observation_reset=reset,
                    required_fill="next_original_pool_frame", sell_fraction=1.0)
    if trigger:
        new["status"] = "EXIT_TRIGGERED"
    return _result("SELL" if trigger else "HOLD", kind + ("_armed" if trigger else "_monitoring"), new, evidence)
