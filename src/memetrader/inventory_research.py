"""Strict-forward displayed-inventory and cost-space hypotheses, not proven alpha.

Dex quantities are a displayed pool proxy, not verified LP events, wallet flow,
executable depth, or a guarantee against rebasing/manipulated tokens.
"""
from copy import deepcopy

from .capital_exits import _as_time, _begin, _number, _result
from .models import canonical_token_address
from .paper_execution import buy_terms, sell_terms

CONTRACT = "inventory-cost-space/20260908-v1"
EXIT_KIND = "inventory_contraction"


def inventory_fields(pair):
    """Project only explicitly labelled v2 surfaces; absent data stays unknown."""
    chain = pair.get("chainId")
    labels = {str(x).lower() for x in (pair.get("labels") or [])}
    if (chain not in {"bsc", "robinhood"} or pair.get("dexId") not in {"pancakeswap", "uniswap"}
            or labels != {"v2"}):
        return {}
    liquidity = pair.get("liquidity") or {}
    base, quote, native = (_number(x) for x in
        (liquidity.get("base"), liquidity.get("quote"), pair.get("priceNative")))
    base_address = canonical_token_address(chain, str((pair.get("baseToken") or {}).get("address") or ""))
    quote_address = canonical_token_address(chain, str((pair.get("quoteToken") or {}).get("address") or ""))
    if (not base_address or not quote_address or base_address == quote_address
            or any(x is None or x <= 0 for x in (base, quote, native))):
        return {}
    return {"token_id": chain + ":" + base_address,
            "pair_address": canonical_token_address(chain, str(pair.get("pairAddress") or "")),
            "quote_address": quote_address, "dex": pair["dexId"],
            "base": base, "quote": quote, "native": native}


def inventory_policies():
    from .forward_patterns import experiment_policies
    from .research_finalists import finalist_policies
    baseline = next(p for p in finalist_policies() if p["arm_id"] == "finalist_baseline_v1")
    result = []
    for kind, name in (("baseline", "双边库存扩张后突破"),
                       ("contraction", "双边库存突破与收缩退出"),
                       ("cost_space", "恐慌修复与成本后空间")):
        parent = (next(p for p in experiment_policies()
                       if p["arm_id"] == "experiment_panic_reclaim_candidate_v1")
                  if kind == "cost_space" else baseline)
        p = deepcopy(parent)
        arm = "inventory_" + kind + "_v1"
        for key in ("paired_entry_group", "paired_entry_size", "capital_exit_kind", "capital_exit_policy"):
            p.pop(key, None)
        p.update(arm_id=arm, canonical_id=arm, name=name,
                 description=name + "；严格前向待证伪假设，5U/最多4仓，非已验证Alpha。",
                 notional_usd=5.0, require_post_decision_observation=True,
                 source_arm_ids=[parent["arm_id"]],
                 evidence_review="docs/PROJECT_CONTEXT/STRATEGY_EXPLORATION_20260908.md",
                 entry_family="cost_space" if kind == "cost_space" else "inventory_expansion",
                 source_entry_family="panic_reclaim" if kind == "cost_space" else "inventory_expansion")
        p["entry_filter"] = {"contract": CONTRACT, "direction": p["entry_family"],
            "control": False, "max_gap_seconds": 60, "max_concurrent_positions": 4,
            "occupied_signal_policy": "reject_without_queue_or_replay",
            "minimum_net_anchor_space": .10, "expansion_min": 1.05,
            "breakout_min": 1.06}
        if kind != "cost_space":
            p.update(paired_entry_group="inventory_exit_matched_v1", paired_entry_size=2)
        if kind == "contraction":
            p.update(capital_exit_kind=EXIT_KIND, capital_exit_policy={
                "version": CONTRACT + "/contraction", "kind": EXIT_KIND,
                "maximum_frame_age_seconds": 15, "minimum_span_seconds": 5,
                "maximum_gap_seconds": 60, "contraction_ratio": .85,
                "price_band": .05, "confirmations": 2})
        result.append(p)
    return result


def research_signal(history, policy, *, decision_at, activated_at):
    now, start = _as_time(decision_at), _as_time(activated_at)
    evidence = {"contract": CONTRACT, "hypothesis_only": True}
    if not history or now is None or start is None:
        return False, "inventory_missing_history", evidence
    latest = history[-1]
    evidence["upstream_provider"] = latest.get("upstream_provider")
    last_at = _as_time(latest.get("observed_at"))
    if last_at is None or not 0 <= (now - last_at).total_seconds() <= 30:
        return False, "inventory_stale_frame", evidence
    frames, prior = [], None
    for f in history:
        observed, ingested, recorded = (_as_time(f.get(k)) for k in ("observed_at", "ingested_at", "recorded_at"))
        if observed is not None and (observed < start or (last_at - observed).total_seconds() > 300):
            continue
        if (None in (observed, ingested, recorded) or not start <= observed <= ingested <= recorded <= now
                or prior is not None and not 0 < (observed - prior).total_seconds() <= 60):
            return False, "inventory_noncausal_or_gap", evidence
        if (f.get("token_id") != latest.get("token_id") or f.get("pair_address") != latest.get("pair_address")
                or not f.get("upstream_provider") or f.get("upstream_provider") != latest.get("upstream_provider")):
            return False, "inventory_identity_or_source_boundary", evidence
        if _number(f.get("price")) is None or f["price"] <= 0:
            return False, "inventory_missing_price", evidence
        prior = observed
        frames.append(f)
    # Backward spacing always includes the newest frame under dense sampling.
    selected = []
    for f in reversed(frames):
        at = _as_time(f["observed_at"])
        if (last_at - at).total_seconds() <= 300 and (not selected or
                (_as_time(selected[-1]["observed_at"]) - at).total_seconds() >= 15):
            selected.append(f)
    selected.reverse()
    if len(selected) < 3 or selected[-1] is not latest:
        return False, "inventory_wait_independent_frames", evidence
    evidence["frame_ids"] = [f["id"] for f in selected]
    cfg = policy["entry_filter"]
    if cfg["direction"] == "cost_space":
        from .forward_patterns import pattern_signal
        parent = {**policy, "entry_filter": {**cfg, "contract": "forward-patterns/v1", "direction": "panic_reclaim"}}
        passed, reason = pattern_signal(selected, parent, decision_at=decision_at, activated_at=activated_at)
        evidence["parent_ready"] = passed
        if not passed:
            return False, reason, evidence
        low_index = min(range(len(selected)), key=lambda i: selected[i]["price"])
        anchor = max(selected[:low_index], key=lambda f: f["price"])
        terms = buy_terms(policy["notional_usd"], latest["price"], policy.get("_execution") or {})
        hypothetical = sell_terms(terms["quantity_tokens"], anchor["price"], policy.get("_execution") or {})
        space = hypothetical["net_usd"] / terms["total_cost_usd"] - 1
        evidence.update(anchor_frame_id=anchor["id"], anchor_price=anchor["price"],
                        anchor_observed_at=anchor["observed_at"], net_anchor_space=space,
                        anchor_is_prediction=False, signal_price=latest["price"])
        passed = space >= cfg["minimum_net_anchor_space"]
        return passed, "cost_space_ready" if passed else "cost_space_insufficient", evidence
    floor = max(1000., float((policy.get("_execution") or {}).get("min_pool_liquidity_usd", 1000)))
    window = selected[-3:]
    inventories = [f.get("inventory") or {} for f in window]
    for f in frames:
        if _as_time(f["observed_at"]) < _as_time(window[0]["observed_at"]):
            continue
        inv = f.get("inventory") or {}
        if (f.get("upstream_provider") != "dexscreener" or not inv
                or inv.get("token_id") != latest["token_id"] or inv.get("pair_address") != latest["pair_address"]
                or (inv.get("quote_address"), inv.get("dex")) !=
                   (inventories[-1].get("quote_address"), inventories[-1].get("dex"))):
            return False, "inventory_unavailable_or_surface_boundary", evidence
        if _number(f.get("liquidity")) is None or f["liquidity"] < floor:
            return False, "inventory_liquidity_unknown_or_low", evidence
    a, b, c = inventories
    age = _number(latest.get("pool_age_seconds"))
    count = (latest.get("buys") or 0) + (latest.get("sells") or 0)
    passed = (age is not None and 120 <= age <= 86400 and count >= 3
              and b["base"] / a["base"] >= cfg["expansion_min"]
              and b["quote"] / a["quote"] >= cfg["expansion_min"]
              and .97 <= b["native"] / a["native"] <= 1.03
              and .97 <= window[1]["price"] / window[0]["price"] <= 1.03
              and c["native"] / b["native"] >= cfg["breakout_min"]
              and latest["price"] / window[1]["price"] >= 1.03
              and min(c[k] / b[k] for k in ("base", "quote")) >= .97)
    evidence.update(frame_ids=[f["id"] for f in window], inventory= inventories,
                    price_usd=[f["price"] for f in window], rebase_status="unverified")
    return bool(passed), "inventory_expansion_ready" if passed else "inventory_expansion_wait", evidence


def post_signal_compatible(latest, evidence, policy):
    if latest.get("upstream_provider") != evidence.get("upstream_provider"):
        return False
    if policy["entry_filter"]["direction"] == "cost_space":
        return True
    prior = (evidence.get("inventory") or [{}])[-1]
    current = latest.get("inventory") or {}
    return bool(prior and current and all(current.get(k) == prior.get(k)
        for k in ("token_id", "pair_address", "quote_address", "dex")))


def evaluate_inventory_exit(position, frame, state, *, now, policy):
    updated, evidence, bad = _begin(EXIT_KIND, policy, position, frame, state, now)
    if bad:
        return _result("WAIT", bad, updated, evidence)
    if updated.get("phase") == "EXIT_TRIGGERED":
        return _result("SELL", "inventory_contraction_confirmed", updated, evidence)
    inv = frame.get("inventory") or {}
    entry = frame.get("entry_inventory") or {}
    price = _number(frame.get("price_usd"))
    if (not frame.get("original_pool") or frame.get("provider") != "dexscreener"
            or not inv or inv.get("token_id") != frame.get("token_id")
            or inv.get("pair_address") != frame.get("pair_address") or price is None or price <= 0
            or not entry or any(inv.get(k) != entry.get(k) for k in ("quote_address", "dex"))):
        updated.pop("anchor", None)
        updated.pop("accepted", None)
        updated["bad_count"] = 0
        return _result("WAIT", "inventory_exit_evidence_unavailable", updated, evidence)
    current = {**inv, "price_usd": price, "observed_at": frame["observed_at"], "frame_id": frame["frame_id"]}
    previous = updated.get("accepted")
    if previous:
        gap = (_as_time(current["observed_at"]) - _as_time(previous["observed_at"])).total_seconds()
        if gap < policy["minimum_span_seconds"]:
            return _result("WAIT", "inventory_exit_wait_spacing", dict(state or {}), evidence)
        if (gap > policy["maximum_gap_seconds"] or previous.get("boundary_at") != inv.get("boundary_at")
                or (previous["quote_address"], previous["dex"]) !=
                (inv["quote_address"], inv["dex"])):
            updated.pop("anchor", None)
            updated["bad_count"] = 0
            previous = None
    anchor = updated.get("anchor") or previous
    collapsed = False
    if anchor:
        ratios = {k: current[k] / anchor[k] for k in ("base", "quote", "native", "price_usd")}
        collapsed = (max(ratios["base"], ratios["quote"]) <= policy["contraction_ratio"]
                     and all(1-policy["price_band"] <= ratios[k] <= 1+policy["price_band"]
                             for k in ("native", "price_usd")))
        evidence.update(anchor=anchor, ratios=ratios)
    updated["accepted"] = current
    updated["bad_count"] = int(updated.get("bad_count", 0)) + 1 if collapsed else 0
    if collapsed:
        updated["anchor"] = anchor
    else:
        updated.pop("anchor", None)
    if updated["bad_count"] >= policy["confirmations"]:
        updated["phase"] = "EXIT_TRIGGERED"
        return _result("SELL", "inventory_contraction_confirmed", updated, evidence)
    return _result("HOLD", "inventory_contraction_wait", updated, evidence)
