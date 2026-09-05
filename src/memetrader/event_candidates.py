"""Pure forward-only handling for authoritative events without an exact CA.

The freeze result and ranking result use the existing
``chain_meme_pattern_evidence`` envelope (``kind``, ``source_key``, identity,
timestamps and ``payload``).  Persistence and market-data retrieval remain the
caller's responsibility.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from itertools import islice
from typing import Any, Iterable, Mapping

from .models import canonical_token_address


MAX_CANDIDATES = 25
MAX_FLOW_ROWS = MAX_CANDIDATES * 2
DEFAULT_FLOW_MAX_AGE_SECONDS = 30.0
FROZEN_SET_KIND = "authoritative_no_ca_candidate_set"
RANK_KIND = "authoritative_no_ca_amount_rank"
IDENTITY_KIND = "frozen_search_candidate_not_official_ca"


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
    value = row.get("payload", row.get("payload_json"))
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return dict(decoded) if isinstance(decoded, Mapping) else {}
    return {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _signed_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    if not text or not text.lstrip("-").isdigit():
        return None
    return int(text)


def _identity(token_id: Any, pair_address: Any) -> tuple[str, str, str] | None:
    text = str(token_id or "").strip()
    if ":" not in text:
        return None
    chain, address = text.split(":", 1)
    chain = chain.strip().lower()
    address = canonical_token_address(chain, address)
    pair = canonical_token_address(chain, str(pair_address or ""))
    if not chain or not address or not pair:
        return None
    return f"{chain}:{address}", chain, pair


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _event_identity(event: Mapping[str, Any]) -> tuple[str, dict[str, Any]] | None:
    identity_status = str(event.get("identity_status") or "").strip().lower()
    if identity_status not in {"no_exact_ca", "missing_exact_ca"}:
        return None
    if str(event.get("contract_address") or "").strip():
        return None
    published = _time(event.get("published_at"))
    observed = _time(event.get("observed_at"))
    ingested = _time(event.get("ingested_at"))
    source = str(event.get("source") or "").strip().lower()
    url = str(event.get("url") or "").strip()
    title = str(event.get("title") or "").strip()
    if not source or not url or not title or not published or not observed or not ingested:
        return None
    if not published <= observed <= ingested:
        return None
    normalized = {
        "source": source,
        "source_kind": str(event.get("source_kind") or "").strip(),
        "event_type": str(event.get("event_type") or "official_listing").strip(),
        "title": title,
        "url": url,
        "published_at": _stamp(published),
        "observed_at": _stamp(observed),
        "ingested_at": _stamp(ingested),
        "identity_status": "no_exact_ca",
        "contract_address": None,
    }
    event_key = f"{source}|{url}|{normalized['published_at']}"
    return event_key, normalized


def _candidate(value: Mapping[str, Any], frozen_at: datetime, index: int) -> dict[str, Any] | None:
    identity = _identity(value.get("token_id"), value.get("pair_address"))
    if not identity:
        return None
    token_id, chain, pair = identity
    supplied_chain = str(value.get("chain") or "").strip().lower()
    address = canonical_token_address(chain, str(value.get("address") or ""))
    observed = _time(value.get("observed_at"))
    recorded = _time(value.get("recorded_at", value.get("ingested_at")))
    if (
        supplied_chain != chain
        or token_id != f"{chain}:{address}"
        or not observed
        or not recorded
        or observed > recorded
        or recorded > frozen_at
        or value.get("authoritative_ca") is True
    ):
        return None
    return {
        "retrieval_index": index,
        "token_id": token_id,
        "chain": chain,
        "address": address,
        "pair_address": pair,
        "snapshot_id": value.get("snapshot_id", value.get("id")),
        "provider": str(value.get("provider") or "").strip(),
        "name": str(value.get("name") or "").strip(),
        "symbol": str(value.get("symbol") or "").strip(),
        "observed_at": _stamp(observed),
        "recorded_at": _stamp(recorded),
        "identity_kind": IDENTITY_KIND,
        "authoritative_ca": False,
    }


def _validated_frozen(value: Any) -> tuple[str, dict[str, Any], list[dict[str, Any]]] | None:
    if not isinstance(value, Mapping) or value.get("kind") != FROZEN_SET_KIND:
        return None
    payload = _payload(value)
    candidates = payload.get("candidates")
    event = payload.get("event")
    event_key = str(payload.get("event_key") or "")
    if (
        payload.get("identity_kind") != IDENTITY_KIND
        or payload.get("authoritative_ca") is not False
        or payload.get("append_policy") != "insert_once_never_merge"
        or not event_key
        or not isinstance(event, Mapping)
        or event.get("identity_status") != "no_exact_ca"
        or event.get("contract_address") is not None
        or not isinstance(candidates, list)
        or not candidates
        or len(candidates) > MAX_CANDIDATES
        or payload.get("candidate_count") != len(candidates)
    ):
        return None
    identities: set[tuple[str, str]] = set()
    normalized: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            return None
        identity = _identity(candidate.get("token_id"), candidate.get("pair_address"))
        if not identity or candidate.get("authoritative_ca") is not False:
            return None
        token_id, chain, pair = identity
        address = canonical_token_address(chain, str(candidate.get("address") or ""))
        key = (token_id, pair)
        if token_id != f"{chain}:{address}" or key in identities:
            return None
        identities.add(key)
        item = dict(candidate)
        item.update(token_id=token_id, chain=chain, address=address, pair_address=pair)
        if item.get("retrieval_index") != index or item.get("identity_kind") != IDENTITY_KIND:
            return None
        normalized.append(item)
    if payload.get("candidate_set_hash") != _hash(normalized):
        return None
    return event_key, payload, normalized


def freeze_event_candidates(
    event: Mapping[str, Any], candidates: Iterable[Mapping[str, Any]], *,
    query: str, frozen_at: Any, existing: Mapping[str, Any] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Freeze one bounded retrieval result without ever merging later results."""
    event_identity = _event_identity(event) if isinstance(event, Mapping) else None
    frozen = _time(frozen_at)
    if not event_identity or not frozen or not str(query or "").strip():
        return "WAIT", "invalid_no_ca_event", {}
    event_key, normalized_event = event_identity
    if frozen < _time(normalized_event["ingested_at"]):
        return "WAIT", "freeze_precedes_event_receipt", {}

    if existing is not None:
        validated = _validated_frozen(existing)
        if not validated or validated[0] != event_key:
            return "WAIT", "invalid_existing_frozen_set", {}
        return "FROZEN", "candidate_set_already_frozen", deepcopy(dict(existing))

    supplied = list(islice(candidates, MAX_CANDIDATES + 1))
    if not supplied or len(supplied) > MAX_CANDIDATES:
        return "WAIT", "empty_or_unbounded_candidate_result", {}
    normalized: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for index, value in enumerate(supplied):
        candidate = _candidate(value, frozen, index) if isinstance(value, Mapping) else None
        if candidate is None:
            return "WAIT", "invalid_candidate_identity_or_time", {}
        key = (candidate["token_id"], candidate["pair_address"])
        if key in identities:
            return "WAIT", "duplicate_candidate_identity", {}
        identities.add(key)
        normalized.append(candidate)

    candidate_hash = _hash(normalized)
    source_key = f"no-ca-event|{_hash(event_key)[:24]}"
    evidence = {
        "kind": FROZEN_SET_KIND,
        "source_key": source_key,
        "token_id": "",
        "pair_address": "",
        "observed_at": _stamp(frozen),
        "recorded_at": _stamp(frozen),
        "payload": {
            "event_key": event_key,
            "event": normalized_event,
            "query": str(query).strip(),
            "frozen_at": _stamp(frozen),
            "candidate_count": len(normalized),
            "candidate_set_hash": candidate_hash,
            "candidates": normalized,
            "identity_kind": IDENTITY_KIND,
            "authoritative_ca": False,
            "append_policy": "insert_once_never_merge",
        },
    }
    return "FROZEN", "candidate_set_frozen", evidence


def event_candidate_source_key(event):
    identity = _event_identity(event)
    return f"no-ca-event|{_hash(identity[0])[:24]}" if identity else None


def _flow(
    row: Mapping[str, Any], token_id: str, pair_address: str,
    round_started: datetime, decision: datetime, max_age_seconds: float,
) -> tuple[datetime, datetime, dict[str, Any]] | None:
    if row.get("id") is None or row.get("kind", "amountful_flow") != "amountful_flow":
        return None
    identity = _identity(row.get("token_id"), row.get("pair_address"))
    observed = _time(row.get("observed_at"))
    recorded = _time(row.get("recorded_at", row.get("available_at")))
    if (
        not identity
        or (identity[0], identity[2]) != (token_id, pair_address)
        or not observed
        or not recorded
        or not round_started <= observed <= recorded <= decision
        or (decision - observed).total_seconds() > max_age_seconds
    ):
        return None
    payload = _payload(row)
    resolver = payload.get("resolver")
    conversion = payload.get("quote_conversion")
    if not isinstance(resolver, Mapping) or not isinstance(conversion, Mapping):
        return None
    chain, token_address = token_id.split(":", 1)
    resolver_identity = _identity(token_id, resolver.get("pool_address"))
    base_mint = canonical_token_address(chain, str(resolver.get("base_mint") or ""))
    quote_mint = str(resolver.get("quote_mint") or "").strip()
    raw = _signed_int(payload.get("net_quote_flow_raw"))
    decimals = resolver.get("quote_decimals")
    rate = _number(conversion.get("usd_per_quote"))
    conversion_max_age = _number(conversion.get("max_age_seconds"))
    flow_decision = _time(payload.get("decision_at")) or recorded
    conversion_observed = _time(conversion.get("observed_at"))
    conversion_recorded = _time(conversion.get("recorded_at", conversion.get("ingested_at")))
    resolver_observed = _time(resolver.get("observed_at"))
    resolver_recorded = _time(resolver.get("recorded_at", resolver.get("ingested_at")))
    valid = bool(
        payload.get("complete") is True
        and payload.get("scan_complete") is True
        and payload.get("future_data_rejected") is not True
        and payload.get("usd_conversion_complete") is True
        and str(payload.get("conversion_basis") or "")
        and resolver.get("status") == "verified"
        and resolver_identity
        and (resolver_identity[0], resolver_identity[2]) == (token_id, pair_address)
        and base_mint == token_address
        and quote_mint
        and str(conversion.get("quote_mint") or "").strip() == quote_mint
        and type(decimals) is int and 0 <= decimals <= 18
        and raw is not None and rate is not None and rate > 0.0
        and conversion_max_age is not None and conversion_max_age >= 0.0
        and flow_decision is not None and observed <= flow_decision <= decision
        and conversion_observed is not None and conversion_recorded is not None
        and resolver_observed is not None and resolver_recorded is not None
        and conversion_observed <= conversion_recorded <= flow_decision
        and resolver_observed <= resolver_recorded <= flow_decision
        and 0.0 <= (flow_decision - conversion_observed).total_seconds() <= conversion_max_age
    )
    if not valid:
        return None
    try:
        usd = Decimal(raw) / (Decimal(10) ** decimals) * Decimal(str(rate))
    except (InvalidOperation, OverflowError):
        return None
    return observed, recorded, {
        "token_id": token_id,
        "pair_address": pair_address,
        "amountful_evidence_id": row["id"],
        "observed_at": _stamp(observed),
        "recorded_at": _stamp(recorded),
        "net_quote_flow_raw": raw,
        "net_quote_flow_native": float(Decimal(raw) / (Decimal(10) ** decimals)),
        "net_quote_flow_usd": float(usd),
        "_net_quote_flow_usd_decimal": usd,
        "flow_semantics": "actual_notional",
        "conversion_basis": str(payload["conversion_basis"]),
    }


def rank_frozen_event_candidates(
    frozen_set: Mapping[str, Any], flow_rows: Iterable[Mapping[str, Any]], *,
    round_id: str, round_started_at: Any, decision_at: Any,
    max_flow_age_seconds: float = DEFAULT_FLOW_MAX_AGE_SECONDS,
) -> tuple[str, str, dict[str, Any]]:
    """Select a unique positive actual-flow leader from one frozen set.

    Every frozen member must have a valid amountful row observed in this round.
    Missing coverage, an exact top-flow tie, or a non-positive leader is WAIT.
    """
    validated = _validated_frozen(frozen_set)
    started, decision = _time(round_started_at), _time(decision_at)
    age = _number(max_flow_age_seconds)
    if (
        not validated
        or not str(round_id or "").strip()
        or not started
        or not decision
        or decision < started
        or age is None
        or age <= 0.0
    ):
        return "WAIT", "invalid_rank_round", {}
    _, frozen_payload, candidates = validated
    supplied = list(islice(flow_rows, MAX_FLOW_ROWS + 1))
    if len(supplied) > MAX_FLOW_ROWS:
        return "WAIT", "unbounded_amountful_rows", {}

    target_identities = {(item["token_id"], item["pair_address"]) for item in candidates}
    by_identity: dict[tuple[str, str], tuple[datetime, datetime, dict[str, Any]]] = {}
    for row in supplied:
        if not isinstance(row, Mapping):
            continue
        identity = _identity(row.get("token_id"), row.get("pair_address"))
        if not identity:
            continue
        key = (identity[0], identity[2])
        if key not in target_identities:
            continue
        parsed = _flow(row, key[0], key[1], started, decision, age)
        if parsed is not None and (key not in by_identity or parsed[1] > by_identity[key][1]):
            by_identity[key] = parsed

    flows: list[dict[str, Any]] = []
    missing: list[str] = []
    for candidate in candidates:
        key = (candidate["token_id"], candidate["pair_address"])
        parsed = by_identity.get(key)
        if parsed is None:
            missing.append(candidate["token_id"])
        else:
            flows.append(parsed[2])

    common = {
        "candidate_set_source_key": frozen_set.get("source_key"),
        "candidate_set_hash": frozen_payload["candidate_set_hash"],
        "round_id": str(round_id).strip(),
        "round_started_at": _stamp(started),
        "decision_at": _stamp(decision),
        "required_candidate_count": len(candidates),
        "covered_candidate_count": len(flows),
        "missing_token_ids": missing,
        "identity_kind": IDENTITY_KIND,
        "authoritative_ca": False,
        "ranking_basis": "same_round_actual_net_quote_flow_usd",
    }
    source_key = f"{frozen_set.get('source_key')}|round|{str(round_id).strip()}"

    def result_evidence(
        action: str, reason: str, payload_changes: Mapping[str, Any],
        *, selected: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "kind": RANK_KIND,
            "source_key": source_key,
            "token_id": str((selected or {}).get("token_id") or ""),
            "pair_address": str((selected or {}).get("pair_address") or ""),
            "observed_at": _stamp(decision),
            "recorded_at": _stamp(decision),
            "payload": {
                **common, "action": action, "reason": reason,
                "next_frame_trade_required": action == "SELECT",
                **dict(payload_changes),
            },
        }

    if missing:
        reason = "incomplete_amountful_coverage"
        return "WAIT", reason, result_evidence("WAIT", reason, {})

    flows.sort(key=lambda item: item["_net_quote_flow_usd_decimal"], reverse=True)
    best = flows[0]["_net_quote_flow_usd_decimal"]
    public_flows = [{key: value for key, value in item.items() if not key.startswith("_")} for item in flows]
    if best <= 0:
        reason = "nonpositive_net_flow_leader"
        return "WAIT", reason, result_evidence("WAIT", reason, {"candidates": public_flows})
    if len(flows) > 1 and flows[1]["_net_quote_flow_usd_decimal"] == best:
        tied = [item["token_id"] for item in flows if item["_net_quote_flow_usd_decimal"] == best]
        reason = "top_actual_flow_tie"
        return "WAIT", reason, result_evidence(
            "WAIT", reason, {"tied_token_ids": tied, "candidates": public_flows},
        )

    selected = {
        "token_id": flows[0]["token_id"],
        "pair_address": flows[0]["pair_address"],
        "amountful_evidence_id": flows[0]["amountful_evidence_id"],
        "identity_kind": IDENTITY_KIND,
        "authoritative_ca": False,
    }
    evidence = result_evidence(
        "SELECT", "unique_positive_actual_flow_leader", {
            "selected": selected,
            "candidates": public_flows,
            "next_frame_rule": {
                "same_token_and_pool": True,
                "market_observed_at_strictly_after": _stamp(decision),
                "cached_same_observation_is_not_new_frame": True,
            },
        }, selected=selected,
    )
    return "SELECT", "unique_positive_actual_flow_leader", evidence


__all__ = [
    "DEFAULT_FLOW_MAX_AGE_SECONDS", "FROZEN_SET_KIND", "IDENTITY_KIND",
    "MAX_CANDIDATES", "MAX_FLOW_ROWS", "RANK_KIND",
    "freeze_event_candidates", "rank_frozen_event_candidates",
]
