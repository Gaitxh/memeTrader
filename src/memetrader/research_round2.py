"""Second-round preregistered mechanisms; bounded L0 state, not validated alpha."""
from copy import deepcopy
from math import log

from .capital_exits import _as_time, _begin, _number, _result
from .research_finalists import finalist_policies

CONTRACT = "open-mechanisms/20260907-v1"
EXIT_KINDS = frozenset({"round2_slow_grace", "round2_giveback_duration",
                        "round2_response_exhaustion", "round2_runner_requalification"})


def round2_policies():
    parents = {p["arm_id"]: p for p in finalist_policies()}
    names = {"chase": "首报价追价预算", "slow_grace": "慢进展一次延期",
             "giveback_duration": "利润回吐驻留时间", "response_exhaustion": "活跃增长价格响应耗尽",
             "runner_requalification": "分批兑现后残仓重新资格"}
    result = []
    for mechanism, name in names.items():
        parent = parents.get({"slow_grace": "finalist_progress_clock_v1",
            "giveback_duration": "finalist_profit_budget_v1"}.get(mechanism),
            parents["finalist_baseline_v1"])
        for role in ("control", "candidate"):
            p = deepcopy(parent)
            arm = f"round2_{mechanism}_{role}_v1"
            p.update(arm_id=arm, canonical_id=arm, name=name + ("·候选" if role == "candidate" else "·对照"),
                description=name + "；第二轮独立预注册假设，未证明盈利；共享首后帧入场，5U/最多4仓。",
                source_arm_ids=[parent["arm_id"]], paired_entry_group="round2_" + mechanism,
                paired_entry_size=2, research_round2=CONTRACT,
                evidence_review="docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/ROUND2/EXPERIMENT_CARDS.md")
            if mechanism == "chase":
                p["entry_chase_budget_fraction"] = .04 if role == "candidate" else None
                p["entry_chase_role"] = role
            elif role == "candidate":
                p.update(capital_exit_kind="round2_" + mechanism,
                    capital_exit_policy={"version": CONTRACT + "/" + mechanism,
                        "kind": "round2_" + mechanism, "maximum_frame_age_seconds": 15,
                        "minimum_span_seconds": 5, "maximum_gap_seconds": 60,
                        "progress_fraction": .01, "no_progress_seconds": 180,
                        "grace_seconds": 120, "liquidity_retention": .85,
                        "profit_arm_fraction": .20, "profit_retrace_fraction": .50,
                        "giveback_seconds": 120, "runner_seconds": 180,
                        "response_fraction": .10, "minimum_response_move": .01})
            if mechanism == "runner_requalification":
                p["take_profit"] = [{"return": .30, "fraction_of_remaining": .50}]
                p["runner_epoch_after_partial"] = True
            result.append(p)
    return result


def chase_decision(signal_price, receipt_price, budget):
    signal, receipt = _number(signal_price), _number(receipt_price)
    if signal is None or receipt is None or signal <= 0 or receipt <= 0:
        return False, None
    drift = receipt / signal - 1
    return budget is None or drift <= float(budget) + 1e-12, drift


def evaluate_round2_exit(position, frame, state=None, *, now, policy):
    kind = policy["kind"]
    new, evidence, error = _begin(kind, policy, position, frame, state, now)
    if error:
        return _result("WAIT", error, new, evidence)
    at = _as_time(frame["observed_at"])
    price, liq, value, stake = (_number(x) for x in (frame.get("price_usd"),
        frame.get("liquidity_usd"), frame.get("economic_value_usd"), position.get("stake_usd")))
    provider = str(frame.get("provider") or "")
    if (not frame.get("original_pool") or not provider or price is None or price <= 0
            or liq is None or liq < 0 or value is None or stake is None or stake <= 0):
        new.pop("window", None)
        return _result("WAIT", "round2_incomplete_frame", new, evidence)
    if new.get("status") == "EXIT_TRIGGERED":
        return _result("HOLD", "round2_exit_already_triggered", new, evidence)
    window = list(new.get("window") or [])
    prior = window[-1] if window else None
    gap = (at - _as_time(prior["at"])).total_seconds() if prior else None
    if gap is not None and gap < policy["minimum_span_seconds"]:
        return _result("WAIT", "round2_frame_too_close", dict(state or {}), evidence)
    reset = not prior or gap > policy["maximum_gap_seconds"] or prior["provider"] != provider
    if reset:
        window = []
        new.update(progress_at=at.isoformat(), progress_value=value, progress_liquidity=liq,
                   peak_profit=value-stake)
        for key in ("under_since", "profit_line", "grace_until"):
            new.pop(key, None)
        if new.get("runner_epoch"):
            new["runner_observable_since"] = at.isoformat()
    buys, sells, volume = (_number(frame.get(k)) for k in ("buys", "sells", "volume"))
    share = buys / (buys+sells) if buys is not None and sells is not None and min(buys,sells) >= 0 and buys+sells > 0 else None
    window = (window + [{"at": at.isoformat(), "price": price, "value": value,
        "liquidity": liq, "provider": provider, "share": share, "volume": volume}])[-3:]
    new["window"] = window
    trigger = False
    if kind == "round2_slow_grace":
        if value >= new["progress_value"] + stake * policy["progress_fraction"]:
            new.update(progress_at=at.isoformat(), progress_value=value, progress_liquidity=liq)
            new.pop("grace_until", None)
        elapsed = (at - _as_time(new["progress_at"])).total_seconds()
        if elapsed >= policy["no_progress_seconds"]:
            improving = (len(window) == 3 and window[0]["value"] < window[1]["value"] < value
                and value >= new["progress_value"]
                and liq >= new["progress_liquidity"] * policy["liquidity_retention"])
            if not new.get("grace_used") and improving:
                from datetime import timedelta
                new.update(grace_used=True, grace_until=(at+timedelta(seconds=policy["grace_seconds"])).isoformat())
            trigger = not new.get("grace_until") or at >= _as_time(new["grace_until"])
    elif kind == "round2_giveback_duration":
        profit = value - stake
        new["peak_profit"] = max(new["peak_profit"], profit)
        if new.get("under_since") and profit > new["profit_line"]:
            new.pop("under_since", None)
            new.pop("profit_line", None)
        if (not new.get("under_since") and new["peak_profit"] >= stake*policy["profit_arm_fraction"]
                and profit <= new["peak_profit"]*(1-policy["profit_retrace_fraction"])):
            new.update(under_since=at.isoformat(), profit_line=new["peak_profit"]*(1-policy["profit_retrace_fraction"]))
        trigger = bool(new.get("under_since") and
            (at-_as_time(new["under_since"])).total_seconds() >= policy["giveback_seconds"])
    elif kind == "round2_response_exhaustion" and len(window) == 3:
        a,b,c = window
        if all(f["volume"] is not None and f["volume"] > 0 and f["share"] is not None for f in window):
            r1 = log(b["price"]/a["price"])/(_as_time(b["at"])-_as_time(a["at"])).total_seconds()
            r2 = log(c["price"]/b["price"])/(_as_time(c["at"])-_as_time(b["at"])).total_seconds()
            trigger = (b["price"]/a["price"]-1 >= policy["minimum_response_move"]
                and r1 > 0 and 0 <= r2 <= policy["response_fraction"]*r1
                and a["volume"] < b["volume"] < c["volume"]
                and a["share"] > b["share"] > c["share"] and c["share"] < .5)
            evidence.update(prior_log_price_rate=r1, current_log_price_rate=r2)
    elif kind == "round2_runner_requalification":
        epoch = new.get("runner_epoch")
        if epoch and not new.get("runner_qualified"):
            if float(position.get("remaining_quantity_tokens") or 0) != epoch["quantity_tokens"]:
                return _result("WAIT", "round2_runner_quantity_changed", new, evidence)
            net = _number(frame.get("net_recovery_usd"))
            qualified = (net is not None and net > epoch["net_value_usd"] + epoch["remaining_cost_usd"]*policy["progress_fraction"]
                and liq >= epoch["liquidity_usd"]*policy["liquidity_retention"])
            if qualified:
                new["runner_qualified"] = True
            since = new.get("runner_observable_since") or epoch["filled_at"]
            trigger = not qualified and (at-_as_time(since)).total_seconds() >= policy["runner_seconds"]
    evidence.update(observation_reset=reset, economic_value_usd=value,
        required_fill="next_original_pool_frame", sell_fraction=1.0)
    if trigger:
        new["status"] = "EXIT_TRIGGERED"
    return _result("SELL" if trigger else "HOLD", kind+("_armed" if trigger else "_monitoring"), new, evidence)
