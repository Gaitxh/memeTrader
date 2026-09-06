"""Pure C01/S05/S06 wallet-observer experiments over participation scans."""
from __future__ import annotations

import copy
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .capital_exits import HOLD, SELL, WAIT, _as_time, _begin, _number, _policy_snapshot
from .l0_experiments import l0_experiment_policies
from .market_flow import _stamp, _time


READY = "READY"
EXPIRED = "EXPIRED"
WalletResult = tuple[str, str, dict[str, Any], dict[str, Any]]

MAX_WATCHLIST_ADDRESSES = 20

WALLET_DISTRIBUTION_POLICY = MappingProxyType({
    "version": "watched-wallet-distribution/v1",
    "maximum_frame_age_seconds": 15.0,
    "minimum_weak_frames": 2,
    "minimum_frame_span_seconds": 5.0,
})

WALLET_CONFIRMED_ENTRY_POLICY = MappingProxyType({
    "version": "watched-wallet-confirmed-entry/v1",
    "ttl_seconds": 600.0,
})


def seal_watchlist(
    candidates: Iterable[Mapping[str, Any]], *, activated_at: Any, now: Any,
) -> dict[str, Any] | None:
    """Freeze at most 20 most recently received seed addresses, without scoring."""
    activated, decision = _time(activated_at), _time(now)
    if activated is None or decision is None or activated > decision:
        return None
    received: dict[str, tuple[float, Mapping[str, Any]]] = {}
    for candidate in candidates:
        address = str(candidate.get("address") or "").strip()
        observed = _time(candidate.get("observed_at"))
        recorded = _time(candidate.get("recorded_at"))
        if not address or observed is None or recorded is None:
            continue
        if not observed <= recorded <= decision:
            continue
        prior = received.get(address)
        if prior is None or recorded > prior[0]:
            received[address] = (recorded, candidate)
    selected = sorted(received.items(), key=lambda item: (-item[1][0], item[0]))[
        :MAX_WATCHLIST_ADDRESSES
    ]
    if not selected:
        return None
    return {
        "version": "wallet-watchlist/v1",
        "activated_at": _stamp(activated),
        "sealed_at": _stamp(decision),
        "addresses": [address for address, _ in selected],
        "candidate_count": len(received),
        "omitted_count": max(0, len(received) - len(selected)),
        "maximum_addresses": MAX_WATCHLIST_ADDRESSES,
        "selection_basis": "latest_locally_received_seed_addresses_no_return_score",
        "identity_unit": "wallet_address_not_human",
        "history_coverage": "forward_observations_only_after_activation",
    }


def wallet_observer_policies() -> list[dict[str, Any]]:
    """Return paired S05 Broad exits and S06 delayed-entry experiments."""
    parent = next(
        policy for policy in l0_experiment_policies()
        if policy["arm_id"] == "l0_continuation_failure_control_v1"
    )
    policies: list[dict[str, Any]] = []
    for role in ("candidate", "control"):
        policy = copy.deepcopy(parent)
        arm_id = f"watched_wallet_distribution_{role}_v1"
        policy.update({
            "arm_id": arm_id,
            "canonical_id": arm_id,
            "name": arm_id,
            "description": "S05同Broad 5U入场；候选仅增加前向观察钱包派发退出。",
            "entry_family": "broad_launch",
            "source_entry_family": "broad_launch",
            "entry_match_mode": "isolated_cohort_observer",
            "entry_gate": "v6_asof_family",
            "paired_opportunity_group": "watched_wallet_distribution_s05",
            "capital_experiment": False,
            "capital_exit_kind": "watched_wallet_distribution" if role == "candidate" else None,
            "notional_usd": 5.0,
            "wallet_exit_kind": (
                "watched_buy_then_sell_l0_weak" if role == "candidate" else None
            ),
            "wallet_exit_policy": (
                dict(WALLET_DISTRIBUTION_POLICY) if role == "candidate" else {}
            ),
            "source_arm_ids": ["l0_continuation_failure_control_v1"],
            "required_inputs": ["broad_launch", "participation_scan", "original_pool_l0_frames"],
            "no_historical_backfill": True,
        })
        policy.pop("paired_entry_group", None)
        policy["entry_filter"] = {
            "direction": "broad_launch",
            "paired_entry_kind": "watched_wallet_distribution_s05",
        }
        policies.append(policy)
    for role in ("candidate", "control"):
        policy = copy.deepcopy(parent)
        arm_id = f"watched_wallet_confirmed_entry_{role}_v1"
        policy.update({
            "arm_id": arm_id,
            "canonical_id": arm_id,
            "name": arm_id,
            "description": (
                "S06冻结同一Broad-like机会；候选等前向watched BUY，对照立即ready。"
            ),
            "entry_family": "wallet_confirmed_broad_opportunity",
            "source_entry_family": "broad_launch",
            "entry_match_mode": "isolated_pattern_observer",
            "entry_gate": (
                "watched_buy_after_opportunity" if role == "candidate"
                else "same_opportunity_immediate_control"
            ),
            "paired_opportunity_group": "watched_wallet_confirmed_entry_s06",
            "capital_experiment": False,
            "notional_usd": 5.0,
            "wallet_entry_role": role,
            "wallet_entry_policy": dict(WALLET_CONFIRMED_ENTRY_POLICY),
            "source_arm_ids": ["l0_continuation_failure_control_v1"],
            "required_inputs": ["broad_launch", "participation_scan"],
            "no_historical_backfill": True,
        })
        policy.pop("paired_entry_group", None)
        policy["entry_filter"] = {
            "direction": "wallet_confirmed_broad_opportunity",
            "paired_entry_kind": "watched_wallet_confirmed_entry_s06",
            "required_market_surface": "solana_pumpswap",
        }
        policies.append(policy)
    return policies


def _result(action, reason, state, evidence) -> WalletResult:
    if action not in {WAIT, HOLD, SELL, READY, EXPIRED}:
        raise ValueError("invalid_wallet_experiment_action")
    return action, reason, state, dict(evidence)


def _watchlist_addresses(watchlist: Mapping[str, Any], now: Any) -> set[str]:
    activated, sealed, decision = map(
        _time, (watchlist.get("activated_at"), watchlist.get("sealed_at"), now)
    )
    addresses = watchlist.get("addresses")
    if (
        activated is None
        or sealed is None
        or decision is None
        or not activated <= sealed <= decision
        or not isinstance(addresses, list)
        or not 0 < len(addresses) <= MAX_WATCHLIST_ADDRESSES
    ):
        return set()
    clean = {str(address).strip() for address in addresses if str(address).strip()}
    return clean if len(clean) == len(addresses) else set()


def participation_hits(
    watchlist: Mapping[str, Any],
    scan: Mapping[str, Any],
    *,
    token_id: str,
    pair_address: str,
    not_before: Any,
    now: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return only positive, decoded, exact-pool post-activation wallet hits."""
    decision = _time(now)
    lower = _time(not_before)
    activated = _time(watchlist.get("activated_at"))
    sealed = _time(watchlist.get("sealed_at"))
    addresses = _watchlist_addresses(watchlist, now)
    base_mint = str(token_id).partition(":")[2]
    hits: list[dict[str, Any]] = []
    rejected = 0
    seen = set()
    for trade in scan.get("trades", ()) if isinstance(scan.get("trades"), list) else ():
        signature = str(trade.get("signature") or "").strip()
        path = str(trade.get("instruction_path") or "").strip()
        side = str(trade.get("side") or "")
        signer = str(trade.get("signer_address") or "").strip()
        block = _time(trade.get("block_time"))
        observed = _time(trade.get("observed_at"))
        recorded = _time(trade.get("recorded_at", trade.get("ingested_at")))
        key = (signature, path)
        valid = bool(
            decision is not None
            and lower is not None
            and activated is not None
            and sealed is not None
            and addresses
            and signature
            and path
            and key not in seen
            and side in {"BUY", "SELL"}
            and signer in addresses
            and str(trade.get("pool_address") or "") == pair_address
            and str(trade.get("base_mint") or "") == base_mint
            and block is not None
            and observed is not None
            and recorded is not None
            and max(lower, activated, sealed) < block <= observed <= recorded <= decision
        )
        seen.add(key)
        if not valid:
            rejected += 1
            continue
        hits.append({
            "signature": signature,
            "instruction_path": path,
            "side": side,
            "signer_address": signer,
            "block_time": _stamp(block),
            "observed_at": _stamp(observed),
            "recorded_at": _stamp(recorded),
            "amount_complete": trade.get("amount_complete") is True,
        })
    hits.sort(key=lambda row: (_time(row["block_time"]), row["signature"], row["instruction_path"]))
    return hits, {
        "positive_hit_count": len(hits),
        "rejected_trade_count": rejected,
        "scan_complete": scan.get("complete") is True,
        "absence_inference": False,
        "coverage_note": "no_positive_hit_never_proves_no_wallet_trade",
    }


def evaluate_wallet_distribution_exit(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = WALLET_DISTRIBUTION_POLICY,
) -> WalletResult:
    """Trigger S05 after same watched participant BUYs then SELLs into two weak L0 frames."""
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "watched_wallet_distribution", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    if frame.get("original_pool") is not True:
        return _result(WAIT, "original_pool_identity_required", new_state, evidence)
    watchlist = frame.get("watchlist") or {}
    scan = frame.get("participation_scan") or {}
    hits, hit_evidence = participation_hits(
        watchlist,
        scan,
        token_id=str(position.get("token_id") or ""),
        pair_address=str(position.get("pair_address") or ""),
        not_before=position.get("opened_at"),
        now=now,
    )
    evidence.update(hit_evidence)
    buyers = dict(new_state.get("watched_buys") or {})
    watched_sell = new_state.get("watched_sell")
    for hit in hits:
        signer = hit["signer_address"]
        if hit["side"] == "BUY" and signer not in buyers:
            buyers[signer] = hit
        elif (
            hit["side"] == "SELL"
            and signer in buyers
            and _time(hit["block_time"]) > _time(buyers[signer]["block_time"])
            and watched_sell is None
        ):
            watched_sell = hit
    new_state["watched_buys"] = buyers
    if watched_sell is not None:
        new_state["watched_sell"] = watched_sell

    price = _number(frame.get("price_usd"))
    liquidity = _number(frame.get("liquidity_usd"))
    if price is None or price <= 0.0 or liquidity is None or liquidity < 0.0:
        return _result(WAIT, "wallet_exit_l0_values_required", new_state, evidence)
    prior = new_state.get("last_l0_frame")
    current_l0 = {
        "frame_id": str(frame["frame_id"]),
        "observed_at": frame["observed_at"],
        "price_usd": price,
        "liquidity_usd": liquidity,
    }
    new_state["last_l0_frame"] = current_l0
    if not buyers:
        return _result(HOLD, "watched_wallet_buy_not_observed", new_state, evidence)
    if watched_sell is None:
        return _result(HOLD, "watched_wallet_sell_not_observed", new_state, evidence)
    if not isinstance(prior, Mapping):
        return _result(HOLD, "wallet_distribution_l0_baseline_recorded", new_state, evidence)
    span = _time(frame["observed_at"]) - _time(prior.get("observed_at"))
    if span < float(policy["minimum_frame_span_seconds"]):
        return _result(WAIT, "wallet_distribution_frame_too_close", new_state, evidence)
    weak = bool(
        price < float(prior["price_usd"])
        and liquidity <= float(prior["liquidity_usd"])
    )
    streak = int(new_state.get("weak_streak") or 0) + 1 if weak else 0
    new_state["weak_streak"] = streak
    evidence.update({
        "watched_buy_addresses": sorted(buyers),
        "watched_sell": watched_sell,
        "l0_weak": weak,
        "weak_streak": streak,
    })
    if streak < int(policy["minimum_weak_frames"]):
        return _result(HOLD, "wallet_distribution_l0_monitoring", new_state, evidence)
    new_state["status"] = "EXIT_TRIGGERED"
    evidence.update({
        "sell_fraction": 1.0,
        "required_fill": "next_fresh_original_pool_frame",
    })
    return _result(SELL, "watched_wallet_distribution_l0_weak", new_state, evidence)


def evaluate_wallet_confirmed_entry(
    opportunity: Mapping[str, Any],
    observation: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    role: str = "candidate",
    policy: Mapping[str, Any] = WALLET_CONFIRMED_ENTRY_POLICY,
) -> WalletResult:
    """Freeze one Broad-like opportunity; control is ready, candidate awaits a later watched BUY."""
    if role not in {"candidate", "control"}:
        raise ValueError("wallet entry role must be candidate or control")
    policy = _policy_snapshot(policy)
    new_state = copy.deepcopy(dict(state or {}))
    decision = _as_time(now)
    observed = _as_time(opportunity.get("observed_at"))
    recorded = _as_time(opportunity.get("recorded_at"))
    opportunity_id = str(opportunity.get("opportunity_id") or "").strip()
    token_id = str(opportunity.get("token_id") or "").strip()
    pair_address = str(opportunity.get("pair_address") or "").strip()
    evidence = {
        "strategy": "watched_wallet_confirmed_entry",
        "policy_version": str(policy["version"]),
        "role": role,
        "opportunity_id": opportunity_id or None,
        "absence_inference": False,
    }
    if (
        decision is None
        or observed is None
        or recorded is None
        or not opportunity_id
        or not token_id
        or not pair_address
        or opportunity.get("broad_like") is not True
        or opportunity.get("original_pool") is not True
        or not observed <= recorded <= decision
    ):
        return _result(WAIT, "invalid_or_future_broad_opportunity", new_state, evidence)
    frozen = new_state.get("opportunity")
    if frozen is None:
        expires = recorded + timedelta(seconds=float(policy["ttl_seconds"]))
        frozen = {
            "opportunity_id": opportunity_id,
            "token_id": token_id,
            "pair_address": pair_address,
            "observed_at": opportunity["observed_at"],
            "recorded_at": opportunity["recorded_at"],
            "expires_at": expires.isoformat(),
        }
        new_state["opportunity"] = frozen
    elif any(
        str(frozen.get(key) or "") != expected
        for key, expected in (
            ("opportunity_id", opportunity_id),
            ("token_id", token_id),
            ("pair_address", pair_address),
        )
    ):
        return _result(WAIT, "frozen_opportunity_identity_changed", new_state, evidence)
    if new_state.get("status") == "READY":
        return _result(HOLD, "wallet_entry_already_ready", new_state, evidence)
    if new_state.get("status") == "EXPIRED" or decision > _as_time(frozen["expires_at"]):
        new_state["status"] = "EXPIRED"
        return _result(EXPIRED, "wallet_confirmation_ttl_expired", new_state, evidence)
    if role == "control":
        new_state["status"] = "READY"
        new_state["ready_at"] = now.isoformat() if hasattr(now, "isoformat") else str(now)
        evidence.update({
            "required_fill": "next_fresh_original_pool_frame",
            "same_initial_opportunity": True,
        })
        return _result(READY, "same_opportunity_control_ready", new_state, evidence)

    hits, hit_evidence = participation_hits(
        observation.get("watchlist") or {},
        observation.get("participation_scan") or {},
        token_id=token_id,
        pair_address=pair_address,
        not_before=frozen["recorded_at"],
        now=now,
    )
    evidence.update(hit_evidence)
    buy = next((hit for hit in hits if hit["side"] == "BUY"), None)
    if buy is None:
        return _result(WAIT, "wallet_buy_not_observed_coverage_unknown", new_state, evidence)
    new_state["status"] = "READY"
    new_state["ready_at"] = now.isoformat() if hasattr(now, "isoformat") else str(now)
    new_state["wallet_buy"] = buy
    evidence.update({
        "wallet_buy": buy,
        "required_fill": "next_fresh_original_pool_frame",
        "same_initial_opportunity": True,
        "same_buy_price_claimed": False,
    })
    return _result(READY, "watched_wallet_buy_confirmed", new_state, evidence)


__all__ = [
    "MAX_WATCHLIST_ADDRESSES",
    "WALLET_DISTRIBUTION_POLICY",
    "WALLET_CONFIRMED_ENTRY_POLICY",
    "seal_watchlist",
    "participation_hits",
    "wallet_observer_policies",
    "evaluate_wallet_distribution_exit",
    "evaluate_wallet_confirmed_entry",
]
