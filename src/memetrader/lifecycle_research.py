"""Bounded holding/sizing experiments. Historical outcome classes never enter here."""
from copy import deepcopy

from .capital_exits import _as_time, _begin, _number, _result

CONTRACT = "holding-lifecycle/20260908-v1"
EXIT_KINDS = frozenset({"lifecycle_renewal", "lifecycle_failed_rebound",
                       "lifecycle_giveback_area", "lifecycle_risk_trim"})
PROBE_KIND = "lifecycle_renewal_shadow"


def lifecycle_policies():
    from .research_finalists import finalist_policies
    from .staged_probe import STAGED_PROBE_POLICY
    parent = next(p for p in finalist_policies() if p["arm_id"] == "finalist_baseline_v1")
    result = []
    for kind, name in (("baseline", "生命周期共同入场基线"), ("renewal", "盈利新脉冲有限续持"),
                       ("failed_rebound", "支撑破位后反弹失败退出"),
                       ("giveback_area", "反复回吐面积预算退出"),
                       ("risk_trim", "早期不回本且转弱减仓"),
                       ("probe", "盈利修复后加仓Shadow对照")):
        p = deepcopy(parent)
        arm = "lifecycle_" + kind + "_v1"
        p.update(arm_id=arm, canonical_id=arm, name=name,
            description=name + "；独立5U/最多4仓，未证明Alpha，旧账户不变。",
            entry_family="lifecycle_broad", source_entry_family="lifecycle_broad",
            source_arm_ids=[parent["arm_id"]], paired_entry_group="lifecycle_same_fill_v1",
            paired_entry_size=6, evidence_review="docs/PROJECT_CONTEXT/LIFECYCLE_RESEARCH_20260908.md")
        p["entry_filter"].update(contract=CONTRACT, direction="broad", max_gap_seconds=30)
        if kind in {"renewal", "failed_rebound", "giveback_area", "risk_trim"}:
            p.update(capital_exit_kind="lifecycle_" + kind, capital_exit_policy={
                "version": CONTRACT + "/" + kind, "kind": "lifecycle_" + kind,
                "maximum_frame_age_seconds": 15, "minimum_span_seconds": 5,
                "maximum_gap_seconds": 30, "base_deadline_seconds": 1800,
                "maximum_deadline_seconds": 7200, "profit_min": .10,
                "support_rise_min": 1.03, "support_break_ratio": .98,
                "rebound_ratio": 1.03, "giveback_area_budget": 6.,
                "trim_checkpoint_seconds": 120, "trim_tolerance_seconds": 15,
                "trim_fraction": .75})
            if kind == "renewal":
                p["max_hold_minutes"] = 120.
        if kind == "probe":
            p.update(probe_kind=PROBE_KIND, shadow_notional_usd=5., shadow_affects_formal_pnl=False,
                probe_policy={**dict(STAGED_PROBE_POLICY), "version": CONTRACT + "/probe",
                    "shadow_notional_usd": 5., "minimum_span_seconds": 5,
                    "maximum_gap_seconds": 30, "qualification_deadline_seconds": 600})
        result.append(p)
    return result


def lifecycle_signal(history, policy, *, decision_at, activated_at):
    evidence = {"contract": CONTRACT, "hypothesis_only": True}
    if not history:
        return False, "lifecycle_no_frame", evidence
    f = history[-1]
    start, now, observed, ingested, recorded = (_as_time(v) for v in
        (activated_at, decision_at, f.get("observed_at"), f.get("ingested_at"), f.get("recorded_at")))
    if (None in (start, now, observed, ingested, recorded)
            or not start <= observed <= ingested <= recorded <= now
            or (now-observed).total_seconds() > 15 or not f.get("upstream_provider")):
        return False, "lifecycle_noncausal_frame", evidence
    price, liq, age, b, s = (_number(f.get(k)) for k in ("price", "liquidity", "pool_age_seconds", "buys", "sells"))
    floor = float((policy.get("_execution") or {}).get("min_pool_liquidity_usd", 1000))
    passed = (None not in (price, liq, age, b, s) and price > 0 and liq >= floor
              and 0 <= age <= 900 and min(b,s) >= 0 and b+s >= 3)
    evidence.update(upstream_provider=f["upstream_provider"], signal_observed_at=f["observed_at"])
    return passed, "lifecycle_broad_ready" if passed else "lifecycle_broad_wait", evidence


def evaluate_lifecycle_exit(position, frame, state, *, now, policy):
    kind = policy["kind"]
    new, evidence, bad = _begin(kind, policy, position, frame, state, now)
    if bad:
        return _result("WAIT", bad, new, evidence)
    price, liq, value, stake, buys, sells = (_number(v) for v in (frame.get("price_usd"),
        frame.get("liquidity_usd"), frame.get("economic_value_usd"), position.get("stake_usd"),
        frame.get("buys"), frame.get("sells")))
    if (not frame.get("original_pool") or not frame.get("provider")
            or None in (price,liq,value,stake) or price <= 0 or stake <= 0 or liq < 0):
        new.update(window=[], supports=[], broken=None, area=0.)
        new.pop("peak_value",None)
        new.pop("area_sample",None)
        return _result("WAIT", "lifecycle_incomplete_frame", new, evidence)
    elapsed = evidence["elapsed_seconds"]
    if new.get("exit_triggered"):
        return _result("SELL", "lifecycle_exit_confirmed", new, evidence)
    window = new.get("window") or []
    previous = window[-1] if window else None
    gap = (_as_time(frame["observed_at"]) - _as_time(previous["at"])).total_seconds() if previous else 0.
    reset = bool(previous and (gap > policy["maximum_gap_seconds"]
        or previous["provider"] != frame["provider"] or previous.get("boundary_at") != frame.get("boundary_at")))
    if reset:
        window, previous = [], None
        new.update(supports=[], broken=None, area=0.)
        new.pop("peak_value",None)
        new.pop("area_sample",None)
    # Running maxima include intervening fresh ticks, even when too close to
    # become another independent support point.
    new["peak_value"] = max(float(new.get("peak_value", value)), value)
    if kind == "lifecycle_giveback_area":
        sample = new.get("area_sample")
        if value >= new["peak_value"]:
            new["area"] = 0.
        elif sample:
            dt = (_as_time(frame["observed_at"])-_as_time(sample["at"])).total_seconds()
            if 0 < dt <= policy["maximum_gap_seconds"] and sample["peak"]/stake-1 >= .30:
                new["area"] = float(new.get("area",0.))+max(0.,(sample["peak"]-sample["value"])/stake)*dt
        new["area_sample"] = {"at":frame["observed_at"],"value":value,"peak":new["peak_value"]}
        evidence.update(giveback_area_fraction_seconds=new.get("area",0.),required_fill="next_original_pool_frame")
        if float(new.get("area",0.)) >= policy["giveback_area_budget"]:
            new["exit_triggered"] = True
            return _result("SELL","lifecycle_giveback_area_triggered",new,evidence)
    if previous and gap < policy["minimum_span_seconds"]:
        return _result("WAIT", "lifecycle_wait_spacing", new, evidence)
    count = buys+sells if buys is not None and sells is not None and min(buys,sells)>=0 else None
    point = {"price":price,"liquidity":liq,"value":value,"count":count,
        "at":frame["observed_at"],"provider":frame["provider"],"boundary_at":frame.get("boundary_at")}
    window = (window + [point])[-25:]
    new["window"] = window
    supports = list(new.get("supports") or [])
    if len(window)>=3:
        a,b,c=window[-3:]
        if b["price"] < a["price"] and b["price"] < c["price"]:
            supports=(supports+[b])[-2:]
    new["supports"] = supports
    profit = value/stake-1
    trigger = False
    if kind == "lifecycle_renewal" and elapsed >= policy["base_deadline_seconds"]:
        if "extension_granted" not in new:
            qualified = (len(supports)==2 and supports[-1]["price"] >= supports[0]["price"]*policy["support_rise_min"]
                and (_as_time(frame["observed_at"])-_as_time(supports[-1]["at"])).total_seconds() <= 300
                and profit>=policy["profit_min"] and price>max(x["price"] for x in window[:-1])
                and liq>=.85*window[0]["liquidity"])
            new.update(extension_granted=qualified, extension_decided_at=frame["observed_at"])
        trigger = not new["extension_granted"] or elapsed>=policy["maximum_deadline_seconds"]
        evidence["extension_granted"] = new["extension_granted"]
    elif kind == "lifecycle_failed_rebound":
        broken = new.get("broken")
        if broken:
            if price>=broken["support"]:
                new["broken"] = None
            elif broken.get("bounced"):
                trigger = price < broken["low"]*.99
            elif price>=broken["low"]*policy["rebound_ratio"]:
                broken["bounced"] = True
            else:
                broken["low"] = min(broken["low"],price)
        elif supports and profit>=policy["profit_min"] and price<supports[-1]["price"]*policy["support_break_ratio"]:
            new["broken"]={"support":supports[-1]["price"],"low":price,"bounced":False}
    elif kind == "lifecycle_risk_trim" and not new.get("trim_decided"):
        checkpoint=policy["trim_checkpoint_seconds"]
        if elapsed>=checkpoint:
            new["trim_decided"]=True
            old=next((f for f in reversed(window[:-1]) if (_as_time(point["at"])-_as_time(f["at"])).total_seconds()>=60),None)
            trim=(elapsed<=checkpoint+policy["trim_tolerance_seconds"] and old is not None
                and profit<0 and price<old["price"] and count is not None and old["count"] is not None and count<old["count"])
            if trim:
                new["trim_requested"]=True
                evidence.update(sell_fraction=policy["trim_fraction"], required_fill="next_original_pool_frame")
                return _result("SELL_PARTIAL","lifecycle_early_weakness_trim",new,evidence)
    evidence.update(economic_return=profit, observation_reset=reset, required_fill="next_original_pool_frame")
    if trigger:new["exit_triggered"]=True
    return _result("SELL" if trigger else "HOLD",kind+("_triggered" if trigger else "_monitoring"),new,evidence)


def evaluate_lifecycle_probe(position, frame, state, *, now, policy):
    """5U additive leg stays Shadow; reuse the existing budget/fee/close ledger."""
    from .staged_probe import evaluate_staged_probe
    state = state or {}
    if frame.get("event_kind") == "formal_exit_quote" or state.get("status") in {"QUALIFIED","SHADOW_OPEN","SHADOW_CLOSED"}:
        if state.get("status") == "QUALIFIED":
            before=_as_time(state.get("qualified_at_observed_at"));at=_as_time(frame.get("observed_at"))
            if (None in (before,at) or (at-before).total_seconds()>30
                or frame.get("provider")!=state.get("provider")
                or frame.get("boundary_at")!=state.get("boundary_at")):
                return "HOLD","lifecycle_shadow_signal_expired",{**state,"status":"COMPLETE_NO_SHADOW"},{}
        return evaluate_staged_probe(position,frame,state,now=now,policy=policy)
    new,evidence,bad=_begin(PROBE_KIND,{k:v for k,v in policy.items() if k!="_execution"},position,frame,state,now)
    if bad:return "WAIT",bad,new,evidence
    if new.get("status") == "COMPLETE_NO_SHADOW":return "HOLD","lifecycle_shadow_complete",new,evidence
    if evidence["elapsed_seconds"]>policy["qualification_deadline_seconds"]:
        new["status"]="COMPLETE_NO_SHADOW"
        return "HOLD","lifecycle_shadow_window_expired",new,evidence
    price,liq,net,stake=(_number(v) for v in (frame.get("price_usd"),frame.get("liquidity_usd"),frame.get("net_recovery_usd"),position.get("stake_usd")))
    window=new.get("window") or []
    if (not frame.get("original_pool") or not frame.get("provider") or None in (price,liq,net,stake) or min(price,stake)<=0):
        new["window"]=[]
        return "WAIT","lifecycle_shadow_missing",new,evidence
    if window:
        gap=(_as_time(frame["observed_at"])-_as_time(window[-1]["at"])).total_seconds()
        if gap>30 or frame["provider"]!=new.get("provider") or frame.get("boundary_at")!=new.get("boundary_at"):
            window=[]
        elif gap<5:return "WAIT","lifecycle_shadow_spacing",new,evidence
    window=(window+[{"price":price,"liquidity":liq,"at":frame["observed_at"]}])[-4:]
    new.update(window=window,provider=frame["provider"],boundary_at=frame.get("boundary_at"))
    if len(window)==4:
        a,b,c,d=window
        if (b["price"]<a["price"] and c["price"]>b["price"] and d["price"]>max(a["price"],c["price"])*1.03
                and net>=stake*1.10 and liq>=.85*a["liquidity"]):
            new.update(status="QUALIFIED",qualified_at_observed_at=frame["observed_at"],qualification_frame_id=frame["frame_id"])
            evidence.update(shadow_notional_usd=5.,affects_formal_pnl=False)
            return "SHADOW_QUALIFIED","lifecycle_new_impulse_shadow_qualified",new,evidence
    return "HOLD","lifecycle_shadow_monitoring",new,evidence
