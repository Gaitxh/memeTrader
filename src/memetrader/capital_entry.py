"""Pure strict-forward capital-entry hypotheses."""
from __future__ import annotations
from datetime import datetime
import math
from typing import Any, Mapping, Sequence
from .capital_policies import direct_lp_float_constrained_signal, authoritative_event_shock_signal


def _time(value: Any) -> datetime | None:
    if not value: return None
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError): return None


def _finite(value: Any) -> float | None:
    try: result = float(value)
    except (TypeError, ValueError): return None
    return result if math.isfinite(result) else None


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if str(value).strip() == str(result) else None


def _num(policy: Mapping[str, Any], key: str) -> float | None:
    return _finite((policy.get("entry_filter") or {}).get(key))


def _evidence_ok(e: Mapping[str, Any], decision: datetime, activated: datetime,
                 *, fresh: bool = True) -> bool:
    observed = _time(e.get("observed_at"))
    recorded = _time(e.get("recorded_at") or e.get("available_at"))
    return bool(observed and recorded and activated <= observed <= recorded <= decision
                and (not fresh or (decision - observed).total_seconds() <= 30))


def _common(history: Sequence[Mapping[str, Any]], policy: Mapping[str, Any],
            decision_at: str, activated_at: str, context: Mapping[str, Any]):
    decision, activated = _time(decision_at), _time(activated_at)
    if not decision or not activated or decision < activated:
        return None, None, "wait_noncausal_or_pre_activation"
    if not history: return None, None, "wait_history_not_strict_asof"
    for p in history:
        observed, ingested, recorded = (_time(p.get(k)) for k in ("observed_at", "ingested_at", "recorded_at"))
        if not observed or not ingested or not recorded or not activated <= observed <= ingested <= recorded <= decision:
            return None, None, "wait_history_not_strict_asof"
        if context.get("token_id") is not None and p.get("token_id") != context["token_id"]:
            return None, None, "wait_history_identity"
        if context.get("pair_address") is not None and p.get("pair_address") != context["pair_address"]:
            return None, None, "wait_history_identity"
    latest = max(_time(p["observed_at"]) for p in history)
    if (decision - latest).total_seconds() > 30: return None, None, "wait_history_stale"
    filt = policy.get("entry_filter")
    if not isinstance(filt, Mapping): return None, None, "wait_missing_entry_filter"
    return decision, activated, None


def capital_entry_signal(history: Sequence[Mapping[str, Any]], policy: Mapping[str, Any],
                         decision_at: str, activated_at: str,
                         context: Mapping[str, Any]) -> tuple[bool, str]:
    decision, activated, error = _common(history, policy, decision_at, activated_at, context)
    if error: return False, error
    filt = policy["entry_filter"]; direction = str(filt.get("direction") or "").lower()
    if direction == "wave_reset_reentry":
        first, new = context.get("first_wave"), context.get("new_episode")
        if not isinstance(first, Mapping) or not isinstance(new, Mapping) or not _evidence_ok(first, decision, activated, fresh=False) or not _evidence_ok(new, decision, activated): return False, "wait_wave_reset_provenance"
        closed, observed = _time(first.get("closed_at")), _time(new.get("observed_at")); lo, hi = _num(policy, "min_gap_seconds"), _num(policy, "max_gap_seconds")
        if first.get("status") not in {"closed", "written_off"} or not closed or not activated <= closed <= decision or not observed or None in (lo, hi) or not lo <= (observed - closed).total_seconds() <= hi: return False, "wait_wave_reset_first_wave_or_cooldown"
        ok = all(new.get(k) is True for k in ("fresh_flow", "depth_rebuilt", "structure_reclaimed")); return (ok, "wave_reset_reentry_confirmed" if ok else "wait_wave_reset_confirmation")
    if direction == "migration_absorption":
        m = context.get("migration"); minimum = _num(policy, "min_absorption_frames")
        ok = isinstance(m, Mapping) and _evidence_ok(m, decision, activated, fresh=False) and minimum is not None and _finite(m.get("absorption_frame_count")) is not None and m["absorption_frame_count"] >= minimum and all(m.get(k) is True for k in ("flush_confirmed", "sell_pressure_decayed", "depth_rebuilt", "buy_absorption"))
        return (ok, "migration_absorption_confirmed" if ok else "wait_migration_absorption")
    flow = context.get("amountful_flow")
    if direction in {"capital_velocity", "effective_breadth", "churn_resistant"} and (not isinstance(flow, Mapping) or not _evidence_ok(flow, decision, activated)): return False, "wait_amountful_flow_provenance"
    if direction == "capital_velocity":
        v = [_finite(flow.get(k)) for k in ("capital_velocity_usd_per_second", "effective_breadth", "top3_notional_share")]; t = [_num(policy, k) for k in ("min_capital_velocity_usd_per_second", "min_effective_breadth", "max_top3_notional_share")]
        if any(x is None for x in v+t): return False, "wait_amountful_flow"
        ok = v[0] >= t[0] and v[1] >= t[1] and v[2] <= t[2]; return ok, "capital_velocity_confirmed" if ok else "capital_velocity_below_hypothesis"
    if direction == "effective_breadth":
        v = [_finite(flow.get("effective_breadth")), _finite(flow.get("top1_notional_share"))]; t = [_num(policy, "min_effective_breadth"), _num(policy, "max_top1_notional_share")]
        if any(x is None for x in v+t): return False, "wait_amountful_breadth"
        ok = v[0] >= t[0] and v[1] <= t[1]; return ok, "effective_breadth_confirmed" if ok else "effective_breadth_below_hypothesis"
    if direction == "churn_resistant":
        v = [_finite(flow.get(k)) for k in ("median_trade_notional_usd", "dust_notional_share", "net_quote_flow_usd")]; t = [_num(policy, k) for k in ("min_median_trade_notional_usd", "max_dust_notional_share")]
        if any(x is None for x in v+t): return False, "wait_amountful_churn_features"
        ok = v[0] >= t[0] and v[1] <= t[1] and v[2] > 0; return ok, "churn_resistant_confirmed" if ok else "churn_resistant_below_hypothesis"
    if direction == "bundle_adjusted_breadth":
        c = context.get("coordination"); value = _finite(c.get("adjusted_effective_breadth")) if isinstance(c, Mapping) else None; minimum = _num(policy, "min_adjusted_effective_breadth")
        if not isinstance(c, Mapping) or not _evidence_ok(c, decision, activated) or c.get("same_slot_only") is True or c.get("evidence_complete") is not True or value is None or minimum is None: return False, "wait_real_coordination_evidence"
        return (value >= minimum, "bundle_adjusted_breadth_confirmed" if value >= minimum else "bundle_adjusted_breadth_below_hypothesis")
    if direction == "finite_capital_ranker":
        r = context.get("ranker")
        if not isinstance(r, Mapping) or not _evidence_ok(r, decision, activated) or r.get("all_asof") is not True or not isinstance(r.get("candidates"), list) or not r["candidates"]: return False, "wait_ranker_asof_candidates"
        candidates = r["candidates"]
        if any(not isinstance(x, Mapping) or not x.get("token_id") or not _evidence_ok(x, decision, activated) for x in candidates): return False, "wait_ranker_candidate_provenance"
        if len({x["token_id"] for x in candidates}) != len(candidates): return False, "wait_ranker_candidate_identity"
        scored = [(x, _finite(x.get("score"))) for x in candidates]
        if any(score is None for _, score in scored) or context.get("token_id") not in {x["token_id"] for x in candidates}: return False, "wait_ranker_asof_candidates"
        scored.sort(key=lambda pair: pair[1], reverse=True)
        rank = next(i + 1 for i, (x, _) in enumerate(scored) if x["token_id"] == context["token_id"])
        slots, maximum = _finite(r.get("remaining_slots")), _num(policy, "max_selected_rank")
        if None in (slots, maximum): return False, "wait_ranker_asof_candidates"
        ok = slots > 0 and rank <= maximum; return ok, "finite_capital_ranker_selected" if ok else "finite_capital_ranker_not_selected"
    if direction == "market_regime_throttle":
        r = context.get("regime");
        if not isinstance(r, Mapping) or not _evidence_ok(r, decision, activated): return False, "wait_regime_provenance"
        b, d, mb, md = _finite(r.get("cross_section_breadth")), _finite(r.get("depth_health")), _num(policy, "min_breadth"), _num(policy, "min_depth_health")
        if None in (b, d, mb, md): return False, "wait_regime_asof_sample"
        ok = r.get("throttle") == "allow" and b >= mb and d >= md; return ok, "market_regime_allowed" if ok else "market_regime_throttled"
    if direction == "duration_competing_risk":
        r = context.get("duration_risk") or {}
        cutoff, trained = _time(r.get("cutoff_at")), _time(r.get("trained_at"))
        if (not r.get("sealed") or not _evidence_ok(r, decision, activated)
                or not cutoff or not trained or not cutoff <= trained <= decision
                or r.get("sample_status") != "sufficient_sample"):
            return False, "wait_duration_risk_bin_maturity"
        probabilities = (r.get("gap_sensitivity") or {}).get(str(filt["horizon_seconds"]), {})
        profit, loss, writeoff = (_finite(probabilities.get(k, 0)) for k in ("profit_exit", "loss_exit", "writeoff_exit"))
        if None in (profit, loss, writeoff):
            return False, "wait_duration_risk_probabilities"
        gap = _finite(probabilities.get("observation_gap", 0))
        ok = gap is not None and profit > loss + writeoff + gap
        return ok, "duration_profit_incidence_preferred" if ok else "duration_loss_incidence_preferred"
    if direction == "competing_risk":
        r = context.get("competing_risk"); cutoff = _time(r.get("cutoff_at")) if isinstance(r, Mapping) else None; trained = _time(r.get("trained_at")) if isinstance(r, Mapping) else None; minimum = _num(policy, "min_sealed_samples") if isinstance(r, Mapping) else None; ids = r.get("sealed_sample_ids") if isinstance(r, Mapping) else None
        if not isinstance(r, Mapping) or not _evidence_ok(r, decision, activated) or r.get("sealed") is not True or not cutoff or not trained or cutoff > trained or trained > decision or not isinstance(ids, list) or minimum is None or len(ids) < minimum or r.get("sample_status") != "sufficient_sample": return False, "wait_competing_risk_maturity"
        compare = "p_ordinary_loss" if filt.get("label_scope") == "observed_profit_writeoff_ordinary_loss" else "p_no_route"
        v = [_finite(r.get(k)) for k in ("p_profit", "p_death", compare)]
        if any(x is None for x in v): return False, "wait_competing_risk_features"
        ok = v[0] > v[1] and v[0] > v[2]; return ok, "competing_risk_profit_hazard_preferred" if ok else "competing_risk_hazard_preferred"
    return False, "wait_unsupported_direction"


def capital_observation_signal(history, policy, *, decision_at, activated_at, context):
    """Dispatch new experiments only; never reinterpret an old strategy contract."""
    if policy.get("paired_entry_group"):
        policy = {**policy, "capital_exit_kind": policy["entry_filter"]["paired_entry_kind"]}
    activated = _time(activated_at)
    frames = [h for h in history if activated and _time(h.get("observed_at"))
              and _time(h["observed_at"]) >= activated]
    decision, start, error = _common(frames, policy, decision_at, activated_at, context)
    if error:
        return False, error
    last = frames[-1]
    price, liquidity = _finite(last.get("price")), _finite(last.get("liquidity"))
    if price is None or price <= 0 or liquidity is not None and liquidity < 1:
        return False, "entry_pool_price_or_liquidity_invalid"
    direction = policy["entry_filter"]["direction"]
    if direction == "migration_amount_rate_absorption":
        from .migration_absorption import build_migration_amount_absorption_context, migration_amount_absorption_signal
        own = build_migration_amount_absorption_context(frames, context.get("amountful_flow"),
            context.get("migration_fact"), context.get("surface"),
            decision_at=decision_at, activated_at=activated_at)
        return migration_amount_absorption_signal(frames, policy, decision_at=decision_at,
            activated_at=activated_at, context=own)
    if direction == "common_funding_adjusted_breadth":
        from .capital_common_funding import common_funding_adjusted_breadth_signal
        flow = context.get("amountful_flow") or {}
        windows = flow.get("windows") or []
        resolver = flow.get("resolver") or {}
        if (not _evidence_ok(flow, decision, start) or not flow.get("complete")
                or not flow.get("adjacent") or not flow.get("nonoverlap") or len(windows) != 2
                or resolver.get("pool_address") != context.get("pair_address")
                or resolver.get("base_mint") != str(context.get("token_id")).partition(":")[2]):
            return False, "awaiting_common_funding_actual_windows"
        return common_funding_adjusted_breadth_signal(dict(prior=windows[0], current=windows[1]),
            flow.get("observed_funding_transfers") or [], decision_at, activated_at, policy["entry_filter"])
    if direction == "early_observed_buyer_distribution":
        cohort = context.get("observed_buyer_cohort") or {}
        sealed = _time(cohort.get("sealed_at"))
        flow = context.get("amountful_flow") or {}
        age, buys, sells = (_finite(last.get(k)) for k in ("pool_age_seconds", "buys", "sells"))
        if (not sealed or not start <= sealed <= decision or not cohort.get("buyer_addresses")
                or cohort.get("base_mint") != str(context.get("token_id")).partition(":")[2]
                or cohort.get("pool_address") != context.get("pair_address")
                or flow.get("complete") is not True or not _evidence_ok(flow, decision, start)
                or None in (age, buys, sells) or not 0 <= age <= 900 or buys+sells < 3):
            return False, "awaiting_frozen_observed_buyer_cohort"
        return True, "observed_buyer_cohort_entry_confirmed"
    if direction == "official_event_actual_flow":
        valid, reason = authoritative_event_shock_signal(frames, policy, decision_at, activated_at, context)
        if not valid:
            return False, reason
        flow = context.get("amountful_flow") or {}
        resolver = flow.get("resolver") or {}
        windows = flow.get("windows") or []
        latest = windows[-1] if windows else {}
        begin, end = _time(latest.get("window_start")), _time(latest.get("window_end"))
        event_at = _time(context["event"]["recorded_at"])
        net, gross, breadth = (_finite(latest.get(k)) for k in (
            "net_quote_flow_raw", "gross_quote_flow_raw", "effective_breadth"))
        if (flow.get("complete") is not True or flow.get("scan_complete") is not True
                or flow.get("future_data_rejected") is True or not _evidence_ok(flow, decision, start)
                or resolver.get("status") != "verified"
                or resolver.get("pool_address") != context.get("pair_address")
                or resolver.get("base_mint") != str(context.get("token_id")).partition(":")[2]
                or latest.get("complete") is not True or not _evidence_ok(latest, decision, start)
                or not begin or not end or not event_at <= begin < end <= _time(last["observed_at"])
                or None in (net, gross, breadth) or not 0 < net <= gross
                or breadth < policy["entry_filter"]["min_effective_breadth"]):
            return False, "awaiting_post_event_actual_capital_confirmation"
        return True, "official_event_actual_flow_confirmed"
    if direction == "direct_lp_amount_specific_confirmed":
        direct_policy = {
            **policy,
            "entry_filter": {
                **policy["entry_filter"],
                "direction": "direct_lp_float_constrained",
            },
        }
        direct_ok, direct_reason = direct_lp_float_constrained_signal(
            frames, direct_policy, decision_at, activated_at, context,
        )
        if not direct_ok:
            return False, direct_reason
        flow = context.get("amountful_flow") or {}
        selected_token = str(context.get("token_id") or "")
        selected_pair = str(context.get("pair_address") or "")
        resolver = flow.get("resolver") or {}
        conversion = flow.get("quote_conversion") or {}
        resolver_observed = _time(resolver.get("observed_at"))
        resolver_recorded = _time(resolver.get("recorded_at"))
        conversion_observed = _time(conversion.get("observed_at"))
        conversion_recorded = _time(conversion.get("recorded_at"))
        flow_recorded = _time(flow.get("recorded_at"))
        minimum_flow = _num(policy, "min_actual_net_flow_usd")
        minimum_breadth = _num(policy, "min_effective_breadth")
        net_flow = _finite(flow.get("net_quote_flow_usd"))
        net_flow_raw = _integer(flow.get("net_quote_flow_raw"))
        quote_decimals = resolver.get("quote_decimals")
        usd_per_quote = _finite(conversion.get("usd_per_quote"))
        conversion_max_age = _finite(conversion.get("max_age_seconds"))
        breadth = _finite(flow.get("effective_breadth"))
        if (
            flow.get("complete") is not True
            or flow.get("scan_complete") is not True
            or flow.get("usd_conversion_complete") is not True
            or flow.get("future_data_rejected") is True
            or not _evidence_ok(flow, decision, start)
            or resolver.get("status") != "verified"
            or resolver.get("pool_address") != selected_pair
            or resolver.get("base_mint") != selected_token.partition(":")[2]
            or conversion.get("quote_mint") != resolver.get("quote_mint")
            or None in (resolver_observed, resolver_recorded,
                        conversion_observed, conversion_recorded, flow_recorded)
            or not resolver_observed <= resolver_recorded <= flow_recorded
            or not conversion_observed <= conversion_recorded <= flow_recorded
            or conversion_max_age is None or not 0 < conversion_max_age <= 30
            or (flow_recorded - conversion_observed).total_seconds() > conversion_max_age
            or type(quote_decimals) is not int or not 0 <= quote_decimals <= 18
            or None in (minimum_flow, minimum_breadth, net_flow, net_flow_raw,
                        usd_per_quote, breadth)
            or net_flow_raw <= 0 or usd_per_quote <= 0
            or not math.isclose(net_flow, net_flow_raw * usd_per_quote / 10**quote_decimals,
                                rel_tol=1e-9, abs_tol=1e-9)
            or net_flow <= minimum_flow
            or breadth < minimum_breadth
        ):
            return False, "wait_direct_lp_positive_actual_flow"
        preflight = context.get("direct_lp_preflight") or {}
        preflight_at = _time(preflight.get("completed_at") or preflight.get("recorded_at"))
        max_age = _num(policy, "max_preflight_age_seconds")
        buy_input = _integer(preflight.get("buy_input_amount_raw"))
        buy_minimum = _integer(preflight.get("buy_minimum_output_raw"))
        sell_input = _integer(preflight.get("sell_input_amount_raw"))
        sell_minimum = _integer(preflight.get("sell_minimum_output_raw"))
        if (
            preflight.get("complete") is not True
            or preflight.get("quote_only_pretrade") is not True
            or preflight.get("is_fill") is not False
            or preflight.get("exact_pool_route") is not True
            or preflight.get("token_id") != selected_token
            or preflight.get("pair_address") != selected_pair
            or preflight.get("amountful_evidence_id") != flow.get("evidence_id")
            or preflight.get("surface_evidence_id") != (context.get("surface") or {}).get("evidence_id")
            or buy_input != 5_000_000
            or buy_minimum is None or buy_minimum <= 0
            or sell_input != buy_minimum
            or sell_minimum is None or sell_minimum <= 0
            or not _evidence_ok(preflight, decision, start)
            or not preflight_at
            or max_age is None
            or not 0 <= (decision - preflight_at).total_seconds() <= max_age
            or _time(last.get("observed_at")) <= preflight_at
        ):
            return False, "wait_direct_lp_amount_specific_preflight"
        return True, "direct_lp_amount_specific_actual_flow_confirmed"
    if direction == "no_ca_event_flow_leader":
        ranked = context.get("no_ca_event") or {}
        selected = ranked.get("selected") or {}
        at = _time(ranked.get("decision_at"))
        if (ranked.get("action") != "SELECT" or ranked.get("authoritative_ca") is not False
                or not _evidence_ok(ranked, decision, start)
                or selected.get("token_id") != context.get("token_id")
                or selected.get("pair_address") != context.get("pair_address")
                or not at or _time(last["observed_at"]) <= at):
            return False, "awaiting_frozen_candidates_actual_flow_and_next_frame"
        return True, "no_ca_event_actual_flow_leader_confirmed"
    if direction in {"prebreakout_net_accumulation", "liquidity_leads_price", "fast_stop_reclaim"}:
        return opportunity_signal(frames, policy, decision=decision, activated=start, context=context)
    if direction in {"event_reawakening", "surface_lifecycle_pipeline"}:
        flow = context.get("amountful_flow") or {}
        if not (flow.get("complete") is True and _evidence_ok(flow, decision, start)
                and (_finite(flow.get("net_quote_flow_usd")) or 0) > 0
                and (_finite(flow.get("effective_breadth")) or 0) >= policy["entry_filter"]["min_effective_breadth"]):
            return False, "awaiting_positive_actual_flow_and_breadth"
        age = _finite(last.get("pool_age_seconds"))
        if age is not None and age >= policy["entry_filter"]["min_mature_age_seconds"]:
            valid, reason = authoritative_event_shock_signal(frames, policy, decision_at, activated_at, context)
            if not valid:
                return False, reason
            event_at = _time(context["event"]["recorded_at"])
            post = [h for h in frames if _time(h["observed_at"]) > event_at]
            if len(post) < 2 or post[-1]["price"] <= post[-2]["price"] or (
                    _finite(post[-1].get("liquidity")) is None or _finite(post[-2].get("liquidity")) is None
                    or post[-1]["liquidity"] < post[-2]["liquidity"]):
                return False, "awaiting_post_event_price_and_depth_reclaim"
            return True, "mature_event_reawakening_confirmed"
        if direction == "event_reawakening":
            return False, "awaiting_mature_event_pool"
        surface = context.get("surface") or {}
        if not (surface.get("complete") is True and _evidence_ok(surface, decision, start, fresh=False)):
            return False, "surface_pipeline_awaiting_verified_pool"
        if surface.get("surface") == "NORMAL_DIRECT":
            return direct_lp_float_constrained_signal(frames, policy, decision_at, activated_at, context)
        if surface.get("canonical_migration_pool") is True:
            route = {**policy, "entry_filter": {**policy["entry_filter"], "direction": "migration_absorption"}}
            return capital_entry_signal(frames, route, decision_at, activated_at, context)
        return False, "pregraduation_watch_only_or_unsupported_surface"
    if direction == "direct_lp_float_constrained":
        return direct_lp_float_constrained_signal(frames, policy, decision_at, activated_at, context)
    if direction == "authoritative_event_shock":
        return authoritative_event_shock_signal(frames, policy, decision_at, activated_at, context)
    if policy.get("capital_exit_kind"):
        age = _finite(last.get("pool_age_seconds"))
        count = _finite(last.get("buys")), _finite(last.get("sells"))
        if age is None or not 0 <= age <= 900 or None in count or sum(count) < 3:
            return False, "capital_broad_start_not_ready"
        if direction in {"vault_hazard", "executable_recovery_decay"}:
            surface = context.get("surface") or {}
            if not (surface.get("complete") is True and surface.get("base_decimals") is not None
                    and _evidence_ok(surface, decision, start, fresh=False)):
                return False, "awaiting_exact_surface_for_exit"
        else:
            flow = context.get("amountful_flow") or {}
            if not (flow.get("complete") is True and _evidence_ok(flow, decision, start)):
                return False, "awaiting_actual_capital_flow_for_exit"
            if direction == "creator_early_holder_distribution" and not (
                    flow.get("creator_identity_verified") is True and flow.get("creator_identity_kind") == "token_creator"):
                return False, "awaiting_verified_token_creator"
        return True, "capital_broad_start_confirmed"
    return capital_entry_signal(frames, policy, decision_at, activated_at, context)


def opportunity_signal(frames, policy, *, decision, activated, context):
    cfg = policy["entry_filter"]
    direction = cfg["direction"]
    last = frames[-1]
    span = cfg["min_span_seconds"]
    recent = [f for f in frames if (decision - _time(f["observed_at"])).total_seconds() <= span + 45]
    if direction == "fast_stop_reclaim":
        stop = context.get("recent_stop") or {}
        closed = _time(stop.get("closed_at"))
        if (not closed or not _evidence_ok(stop, decision, activated, fresh=False)
                or not stop.get("clean") or stop.get("status") != "closed"
                or not cfg["stop_min_gap_seconds"] <= (decision-closed).total_seconds() < cfg["stop_max_gap_seconds"]):
            return False, "awaiting_clean_recent_natural_stop"
        recent = [f for f in recent if _time(f["observed_at"]) > closed]
    if (len(recent) < cfg["min_frames"]
            or (_time(recent[-1]["observed_at"]) - _time(recent[0]["observed_at"])).total_seconds() < span
            or any(not 0 < (_time(b["observed_at"]) - _time(a["observed_at"])).total_seconds() <= cfg["max_gap_seconds"]
                   for a, b in zip(recent, recent[1:]))):
        return False, "awaiting_contiguous_opportunity_history"
    prices = [_finite(f.get("price")) for f in recent]
    depths = [_finite(f.get("liquidity")) for f in recent]
    if any(x is None or x <= 0 for x in prices) or any(x is None or x < 1 for x in depths):
        return False, "awaiting_opportunity_price_and_depth"
    if direction == "fast_stop_reclaim":
        entry, stop_price, stop_depth = (_finite(stop.get(k)) for k in ("entry_price", "stop_price", "stop_liquidity"))
        if None in (entry, stop_price, stop_depth):
            return False, "awaiting_stop_price_depth_evidence"
        ok = (prices[-1] > prices[-2] > prices[-3]
              and prices[-1] >= max(stop_price*cfg["stop_reclaim_multiple"], entry*cfg["entry_reclaim_multiple"])
              and depths[-1] >= .8*stop_depth)
        return ok, "fast_stop_reclaim_confirmed" if ok else "awaiting_fast_stop_reclaim"
    if max(prices)/min(prices)-1 > cfg["price_range_max"]:
        return False, "price_already_expanded"
    if direction == "liquidity_leads_price":
        # This is a DEX-reported depth hypothesis, not proof of LP custody or executable depth.
        ok = depths[-1] >= depths[0]*(1+cfg["min_depth_growth"]) and depths[-1] >= depths[-2]
        return ok, "reported_liquidity_leads_price" if ok else "awaiting_depth_expansion"
    flow = context.get("amountful_flow") or {}
    windows = flow.get("windows") or []
    if (flow.get("complete") is not True or not _evidence_ok(flow, decision, activated)
            or not flow.get("adjacent") or not flow.get("nonoverlap") or len(windows) != 2):
        return False, "awaiting_two_complete_actual_flow_windows"
    previous_end = None
    for w in windows:
        begin, end = _time(w.get("window_start")), _time(w.get("window_end"))
        net, gross, breadth, top = (_finite(w.get(k)) for k in (
            "net_quote_flow_raw", "gross_quote_flow_raw", "effective_breadth", "top1_notional_share"))
        if (not begin or not end or not activated <= begin < end <= decision
                or previous_end is not None and begin != previous_end
                or w.get("complete") is not True or not _evidence_ok(w, decision, activated, fresh=False)
                or None in (net, gross, breadth, top)):
            return False, "awaiting_causal_amount_windows"
        if (gross <= 0 or net/gross < cfg["min_net_gross_ratio"]
                or breadth < cfg["min_effective_breadth"] or top > cfg["max_top1_notional_share"]):
            return False, "accumulation_not_broad_or_positive"
        previous_end = end
    ok = prices[-1] >= (max(prices)+min(prices))/2 and depths[-1] >= .9*depths[0]
    return ok, "prebreakout_net_accumulation_confirmed" if ok else "awaiting_accumulation_structure"


def capital_context_from_observations(history, evidence, *, decision_at, migration_fact=None,
                                      first_wave=None, cross_section=None):
    """Small bounded source adapter; caller supplies as-of rows from existing indexes.

    Pool identity, observed transaction groups and human independence are kept
    distinct. Missing actual-flow inputs do not become buy/sell-count proxies.
    """
    if not history:
        return {}
    last, now = history[-1], _time(decision_at)
    context = {"token_id": last["token_id"], "pair_address": last["pair_address"]}
    context["migration_fact"] = migration_fact
    def latest(kind, max_age=None):
        rows = evidence.get(kind) or []
        for row in sorted(rows, key=lambda r: r["recorded_at"], reverse=True):
            seen, recorded = _time(row.get("observed_at")), _time(row.get("recorded_at"))
            if not (seen and recorded and seen <= recorded <= now):
                continue
            if max_age is not None and (now-seen).total_seconds() > max_age:
                continue
            return {**dict(row.get("payload") or {}), "observed_at": row["observed_at"],
                    "recorded_at": row["recorded_at"], "evidence_id": row.get("id")}
        return {}
    flow = latest("amountful_flow", 30)
    if flow.get("complete") is True:
        flow["median_trade_notional_usd"] = flow.get("median_trade_quote_usd")
        # Same-transaction groups are directly observed, not a claim that all
        # hidden multi-transaction bundles or beneficial owners are recovered.
        context["coordination"] = {"observed_at": flow["observed_at"], "recorded_at": flow["recorded_at"],
            "same_slot_only": False, "evidence_complete": True,
            "adjusted_effective_breadth": flow.get("atomic_adjusted_effective_breadth"),
            "coverage": "observed_atomic_transaction_groups_only", "bundle_status": "unknown"}
        rate = (flow.get("quote_conversion") or {}).get("usd_per_quote")
        decimals = (flow.get("resolver") or {}).get("quote_decimals")
        if rate is not None and isinstance(decimals, int):
            latest_trades = (flow.get("windows") or [flow])[-1].get("trades", [])
            buy_amounts = [int(t["quote_amount_raw"]) * float(rate) / 10**decimals
                           for t in latest_trades if t.get("side") == "BUY"
                           and t.get("quote_amount_raw") is not None]
            total = sum(buy_amounts)
            flow["dust_notional_share"] = sum(n for n in buy_amounts if n < 1) / total if total else None
        context["amountful_flow"] = flow
    surface = latest("pool_surface", 120)
    context["surface"] = surface
    if surface.get("complete") is True:
        upper = surface.get("max_single_controller_withdraw_fraction_upper_bound")
        risk = "unknown" if upper is None else "high" if upper > .5 else "low" if upper <= .1 else "medium"
        context["snapshot"] = {**surface, "pool_surface": surface, "lp_custody_risk": risk}
        context["mint_permission"] = {"known": True, "status": "observed",
            "mint_authority": surface.get("mint_authority"), "freeze_authority": surface.get("freeze_authority"),
            "observed_at": surface["observed_at"], "recorded_at": surface["recorded_at"]}
    if migration_fact and surface.get("canonical_migration_pool") is True:
        at = _time(migration_fact.get("recorded_at"))
        post = [h for h in history if at and at < _time(h["observed_at"]) <= now]
        distinct = {p["observed_at"] for p in post}
        if len(distinct) >= 4:
            peak = max(float(p["price"]) for p in post[:-2])
            trough = min(float(p["price"]) for p in post[:-1])
            before, current = post[-2:]
            sell_before, sell_now = _finite(before.get("sells")), _finite(current.get("sells"))
            depth_before, depth_now = _finite(before.get("liquidity")), _finite(current.get("liquidity"))
            context["migration"] = {"observed_at": current["observed_at"], "recorded_at": current["recorded_at"],
                "fact_id": migration_fact.get("id"), "migration_recorded_at": migration_fact["recorded_at"],
                "flush_confirmed": trough <= peak*.85, "absorption_frame_count": 2,
                "sell_pressure_decayed": sell_before is not None and sell_now is not None and sell_now < sell_before,
                "depth_rebuilt": depth_before is not None and depth_now is not None and depth_now >= depth_before,
                "buy_absorption": float(current["price"]) > float(before["price"]) > trough
                    and _finite(flow.get("net_quote_flow_raw")) is not None and flow["net_quote_flow_raw"] > 0}
    if first_wave:
        context["first_wave"] = first_wave
        if len(history) >= 3:
            old, prev, current = history[-3:]
            context["new_episode"] = {"observed_at": current["observed_at"], "recorded_at": current["recorded_at"],
                "fresh_flow": flow.get("complete") is True and float(flow.get("net_quote_flow_raw") or 0) > 0,
                "depth_rebuilt": all(_finite(h.get("liquidity")) is not None for h in (old,current))
                    and current["liquidity"] >= old["liquidity"],
                "structure_reclaimed": current["price"] > max(old["price"], prev["price"])}
    if cross_section:
        context.update(cross_section)
    event = latest("authoritative_event", 300)
    if event:
        context["event"] = event
    ranked = latest("authoritative_no_ca_amount_rank", 300)
    if ranked:
        context["no_ca_event"] = ranked
    preflight = latest("direct_lp_entry_preflight", 35)
    if preflight:
        context["direct_lp_preflight"] = preflight
    cohort = latest("observed_buyer_cohort")
    if cohort:
        context["observed_buyer_cohort"] = cohort
    return context
