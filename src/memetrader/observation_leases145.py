"""Small, in-memory lease rules for the 145 pattern observer.

This module deliberately knows nothing about requests, Store, or quotes.  The
runtime keeps its existing watch dictionaries and calls these helpers around
admission, receipt handling, and its existing KV checkpoint.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


EARLY_LEASE_SECONDS = 120
PHASE_LEASE_SECONDS = 300
TARGET_SECONDS = 15
WINDOW_SECONDS = (30, 120, 300)
BASE_CAPS = {"early": 3, "growth": 4, "mature": 3}
CHAIN_CAP = 10


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _chain(item: dict[str, Any]) -> str:
    token = item.get("token")
    return str(item.get("chain") or getattr(token, "chain", "")).lower()


def _identity(token_id: str, item: dict[str, Any]) -> tuple[str, str, str]:
    return token_id, _chain(item), str(item.get("pair_address") or "")


def admit(item: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Set the first 120-second lease without touching the legacy expiry."""
    admitted_at = _time(item.get("admitted_at")) or now
    item["admitted_at"] = admitted_at
    item["min_observe_until"] = max(
        _time(item.get("min_observe_until")) or admitted_at,
        admitted_at + timedelta(seconds=EARLY_LEASE_SECONDS),
    )
    item.setdefault("last_useful_at", None)
    item.setdefault("next_due_at", now)
    item.setdefault("frame_count", 0)
    item.setdefault("window_expired", [])
    return item


def record_frame(
    item: dict[str, Any], observed_at: datetime, now: datetime, *,
    phase: str | None = None, phase_started_at: datetime | None = None,
) -> bool:
    """Record one new exact-pool frame and extend only on a phase transition."""
    admit(item, now)
    prior = _time(item.get("last_useful_at"))
    if observed_at>now or prior is not None and observed_at <= prior:
        return False
    item.setdefault('coverage_start_at',observed_at)
    if prior is not None and (observed_at-prior).total_seconds()>60:item['coverage_gap']=True
    item["last_useful_at"] = observed_at
    item["next_due_at"] = observed_at + timedelta(seconds=TARGET_SECONDS)
    item["frame_count"] = int(item.get("frame_count", 0)) + 1
    count = item["frame_count"]
    delay = max(0.0, (observed_at - _time(item["admitted_at"])).total_seconds())
    if count == 2:
        item["frame2_delay_seconds"] = delay
    elif count == 3:
        item["frame3_delay_seconds"] = delay

    prior_phase = item.get("phase")
    if phase in ('impulse','cool','base') and phase != prior_phase and phase_started_at is not None:
        started = phase_started_at
        item["phase"] = phase
        item["last_phase_at"] = started
        item["min_observe_until"] = max(
            _time(item["min_observe_until"]),
            started + timedelta(seconds=PHASE_LEASE_SECONDS),
        )
    return True


def expire_windows(item: dict[str, Any], now: datetime) -> list[int]:
    """Mark expired availability windows once; pending windows are not failures."""
    admitted = _time(item.get("admitted_at"))
    if admitted is None:
        return []
    seen = {int(value) for value in item.setdefault("window_expired", [])}
    added = [window for window in WINDOW_SECONDS
             if window not in seen and now >= admitted + timedelta(seconds=window)]
    if added:
        item["window_expired"] = sorted(seen | set(added))
    first=_time(item.get('coverage_start_at'));last=_time(item.get('last_useful_at'))
    results=item.setdefault('window_results',{})
    for window in WINDOW_SECONDS:
        if str(window) in results:continue
        target=(first or admitted)+timedelta(seconds=window)
        if last and last>=target:
            results[str(window)]='OBSERVED' if not item.get('coverage_gap') and (last-target).total_seconds()<=30 and item.get('frame_count',0)>=3 else 'UNKNOWN_PATH_GAP'
        elif now>target+timedelta(seconds=30):results[str(window)]='SOURCE_NO_UPDATE'
        else:continue
        item.setdefault('first_block',None)
        if results[str(window)]!='OBSERVED':item['first_block']=item['first_block'] or results[str(window)]
        item['reason']=results[str(window)]
    return added


def account_windows(item, counters, now):
    """One result per matured opportunity/window, including before eviction."""
    expire_windows(item,now)
    counted=item.setdefault('window_counted',[])
    for window,result in item.get('window_results',{}).items():
        if window in counted:continue
        key=window+':'+result;counters[key]=counters.get(key,0)+1;counted.append(window)


def select_due(
    watch: dict[str, dict[str, Any]], now: datetime, *, held: Iterable[str] = (),
    protected: Iterable[str] = (),
) -> list[tuple[str, dict[str, Any]]]:
    """Return due non-held work in deterministic observer target order."""
    blocked = set(held)
    due = []
    for token_id, item in watch.items():
        if token_id in blocked:
            continue
        next_due = _time(item.get("next_due_at")) or now
        if next_due <= now:
            admitted = _time(item.get("admitted_at")) or now
            incomplete = now < (_time(item.get("min_observe_until")) or admitted)
            due.append((token_id, item, next_due, incomplete, admitted))
    due.sort(key=lambda row: (
        row[2],  # most overdue first
        0 if row[3] else 1,  # still-forming 30/120s windows first
        row[4],  # stable first admission
        _identity(row[0], row[1]),
    ))
    return [(token_id, item) for token_id, item, *_ in due]


def replaceable_early(
    watch: dict[str, dict[str, Any]], candidate_id: str, candidate: dict[str, Any],
    now: datetime, *, held: Iterable[str] = (), protected: Iterable[str] = (),
    fresh_seconds: int = 30,
) -> str | None:
    """Choose a stale, completed early lease only for a younger same-chain candidate."""
    blocked = set(held) | set(protected)
    chain = _chain(candidate)
    candidate_age = _age_seconds(candidate, now)
    victims = []
    for token_id, item in watch.items():
        if token_id == candidate_id or token_id in blocked or _chain(item) != chain:
            continue
        if item.get("bucket") != "early":
            continue
        until = _time(item.get("min_observe_until"))
        last = _time(item.get("last_useful_at"))
        if until is None or now < until:
            continue
        age = _age_seconds(item, now)
        if candidate_age is None or age is None or candidate_age >= age:
            continue
        victims.append((age, _time(item.get("admitted_at")) or now, _identity(token_id, item), token_id))
    return min(victims)[-1] if victims else None


def _age_seconds(item: dict[str, Any], now: datetime) -> float | None:
    created = item.get("pool_created_at_ms")
    try:
        return now.timestamp() - float(created) / 1000.0
    except (TypeError, ValueError):
        return None


def membership(watch: dict[str, dict[str, Any]], *, held: Iterable[str] = ()) -> dict[str, Any]:
    """Bounded candidate-seat accounting; held identities do not consume seats."""
    held_ids = set(held)
    per_chain: dict[str, Counter[str]] = {}
    for token_id, item in watch.items():
        if token_id in held_ids:
            continue
        chain = _chain(item)
        per_chain.setdefault(chain, Counter())[str(item.get("bucket") or "mature")] += 1
    return {
        "base_caps": dict(BASE_CAPS), "chain_cap": CHAIN_CAP,
        "chains": {chain: {"total": sum(counts.values()),
                             "buckets": {bucket: int(counts[bucket]) for bucket in BASE_CAPS}}
                   for chain, counts in sorted(per_chain.items())},
    }


def bounded_summary(
    watch: dict[str, dict[str, Any]], now: datetime, *, held: Iterable[str] = (),
    protected: Iterable[str] = (), limit: int = 30,
) -> dict[str, Any]:
    """Return a JSON-safe, capped opportunity status surface."""
    blocked = set(held) | set(protected)
    rows = []
    for token_id, item in watch.items():
        admitted = _time(item.get("admitted_at"))
        if admitted is None:
            continue
        last = _time(item.get("last_useful_at"))
        rows.append({
            "token_id": token_id, "chain": _chain(item), "pair_address": str(item.get("pair_address") or ""),
            "admitted_at": admitted.isoformat(),
            "min_observe_until": (_time(item.get("min_observe_until")) or admitted).isoformat(),
            "last_useful_at": last.isoformat() if last else None,
            "next_due_at": (_time(item.get("next_due_at")) or admitted).isoformat(),
            "frame_count": int(item.get("frame_count", 0)),
            "frame2_delay_seconds": item.get("frame2_delay_seconds"),
            "frame3_delay_seconds": item.get("frame3_delay_seconds"),
            "held": token_id in set(held), "protected": token_id in blocked,
            "first_block": item.get("first_block"), "reason": item.get("reason"),
            "expired_windows": list(item.get("window_expired", [])),
            "windows":dict(item.get('window_results',{})),
        })
    rows.sort(key=lambda row: (row["next_due_at"], row["admitted_at"], row["chain"], row["token_id"], row["pair_address"]))
    return {"as_of": now.isoformat(), "membership": membership(watch, held=held),
            "opportunities": rows[:max(0, limit)], "truncated": max(0, len(rows) - max(0, limit))}


def dump_state(watch: dict[str, dict[str, Any]], now: datetime, *, limit: int = 30) -> dict[str, Any]:
    """Checkpoint only identity and unexpired lease metadata, never quote objects."""
    rows = []
    for token_id, item in watch.items():
        until = _time(item.get("min_observe_until"))
        if until is None or until <= now:
            continue
        rows.append({key: value for key, value in {
            "token_id": token_id, "chain": _chain(item), "pair_address": str(item.get("pair_address") or ""),
            "bucket": item.get("bucket"), "admitted_at": _iso(item.get("admitted_at")),
            "pool_created_at_ms":item.get('pool_created_at_ms'),"expires_at":_iso(item.get('expires_at')),
            "min_observe_until": _iso(until), "last_useful_at": _iso(item.get("last_useful_at")),
            "next_due_at": _iso(item.get("next_due_at")), "phase": item.get("phase"),
            "last_phase_at": _iso(item.get("last_phase_at")), "frame_count": int(item.get("frame_count", 0)),
            "frame2_delay_seconds": item.get("frame2_delay_seconds"), "frame3_delay_seconds": item.get("frame3_delay_seconds"),
            "window_expired": list(item.get("window_expired", [])),
            "coverage_start_at":_iso(item.get('coverage_start_at')),
            "coverage_gap":bool(item.get('coverage_gap')), "window_results":dict(item.get('window_results',{})),
            "window_counted":list(item.get('window_counted',[])),
        }.items() if value is not None})
    rows.sort(key=lambda row: (row["chain"], row["token_id"], row["pair_address"]))
    return {"version": 1, "saved_at": now.isoformat(), "leases": rows[:max(0, limit)]}


def restore_state(payload: dict[str, Any], now: datetime) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Return valid identity/lease data for fresh runtime quotes to reattach."""
    restored = {}
    for row in (payload or {}).get("leases", []):
        if not isinstance(row, dict):
            continue
        until = _time(row.get("min_observe_until"))
        token_id, chain, pair = str(row.get("token_id") or ""), str(row.get("chain") or ""), str(row.get("pair_address") or "")
        if not token_id or not chain or not pair or until is None or until <= now:
            continue
        lease = dict(row)
        for key in ("admitted_at", "min_observe_until", "last_useful_at", "next_due_at", "last_phase_at", "coverage_start_at", "expires_at"):
            if key in lease:
                lease[key] = _time(lease[key])
        restored[(token_id, chain.lower(), pair)] = lease
    return restored


def _iso(value: Any) -> str | None:
    parsed = _time(value)
    return parsed.isoformat() if parsed else None
