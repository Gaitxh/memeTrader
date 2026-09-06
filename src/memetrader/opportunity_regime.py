"""Pure, label-only opportunity-regime classification for S08 phase 1."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


WINDOW = timedelta(hours=2)
MAX_ROWS = 1000
MIN_SAMPLES = 20
MIN_COVERAGE = 0.8


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if number == number and number not in (float("inf"), float("-inf")) else None
    except (TypeError, ValueError):
        return None


def classify_opportunity_regimes(
    rows: list[Mapping[str, Any]], previous_state: Mapping[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """Classify mature outcome cohorts without trading authority or persistence.

    Rows are expected to be sealed outcome records.  ``previous_state`` is an
    opaque caller-owned snapshot; returned state is suitable for the next call.
    Thresholds are frozen research priors, not fitted optima.
    """
    current = _time(now) or datetime.now(timezone.utc)
    cutoff = current - WINDOW
    usable: list[tuple[datetime, Mapping[str, Any]]] = []
    for row in rows[:MAX_ROWS]:
        observed, recorded, target = _time(row.get("observed_at")), _time(row.get("recorded_at")), _time(row.get("target_at"))
        if (not recorded or not target or max(recorded, target) > current or target < cutoff
                or (observed and (observed > recorded or observed > current))
                or str(row.get("status") or "").upper() not in {"OBSERVED", "UNKNOWN"}):
            continue
        usable.append((recorded, row))
    usable.sort(key=lambda item: (item[0], str(item[1].get("source_cohort_id") or "")))

    # One earliest episode per token inside each chain/lifecycle bucket.
    episodes: dict[tuple[str, str, str], tuple[datetime, Mapping[str, Any]]] = {}
    for recorded, row in usable:
        key = (str(row.get("chain") or "unknown"), str(row.get("lifecycle") or "unknown"), str(row.get("token_id") or ""))
        if key[2] and key not in episodes:
            episodes[key] = (recorded, row)

    grouped: dict[tuple[str, str], list[tuple[datetime, Mapping[str, Any]]]] = defaultdict(list)
    for (chain, lifecycle, _), item in episodes.items():
        grouped[(chain, lifecycle)].append(item)
    old = dict((previous_state or {}).get("groups") or {})
    output_groups: dict[str, Any] = {}
    next_groups: dict[str, Any] = {}

    for (chain, lifecycle), items in sorted(grouped.items()):
        key = f"{chain}|{lifecycle}"
        known = []
        fingerprints = []
        for recorded, row in items:
            fingerprint = f"{row.get('source_cohort_id') or ''}|{row.get('token_id') or ''}|{row.get('pair_address') or ''}|{row.get('target_at') or ''}"
            fingerprints.append(fingerprint)
            p0, p15 = _number(row.get("h0price")), _number(row.get("h15price"))
            l15 = _number(row.get("h15liq"))
            if (str(row.get("status") or "").upper() == "OBSERVED" and _time(row.get("observed_at"))
                    and p0 and p0 > 0 and p15 is not None and p15 >= 0 and l15 is not None and l15 >= 0):
                known.append((((p15 / p0) * 0.96 / 1.04) - 1.0 >= 0, l15 >= 100.0))
        total, count = len(items), len(known)
        coverage = count / total if total else 0.0
        positive = sum(1 for value, _ in known if value) / count if count else None
        survival = sum(1 for _, value in known if value) / count if count else None
        if count < MIN_SAMPLES or coverage < MIN_COVERAGE:
            candidate = "INSUFFICIENT"
        elif positive >= 0.6 and survival >= 0.9:
            candidate = "HOT"
        elif positive <= 0.35 or survival < 0.7:
            candidate = "COLD"
        else:
            candidate = "NORMAL"

        prior = old.get(key) if isinstance(old.get(key), Mapping) else {}
        confirmed = str(prior.get("confirmed") or "")
        seen = set(prior.get("seen") or [])
        new_items = [(t, fp) for t, fp in zip(items, fingerprints) if fp not in seen]
        pending, pending_since = prior.get("pending"), _time(prior.get("pending_since"))
        if candidate == "INSUFFICIENT":
            regime = "INSUFFICIENT"
            pending, pending_since = None, None
        elif confirmed and candidate != confirmed:
            regime = confirmed
            if new_items:
                if pending != candidate:
                    pending, pending_since = candidate, current
                elif pending_since and current - pending_since >= timedelta(seconds=60):
                    regime, pending, pending_since = candidate, None, None
        else:
            regime = candidate
            pending, pending_since = None, None
        next_groups[key] = {"confirmed": confirmed if regime == "INSUFFICIENT" else regime,
                            "seen": fingerprints, "pending": pending,
                            "pending_since": pending_since.isoformat() if pending_since else None}
        output_groups[key] = {
            "chain": chain, "lifecycle": lifecycle, "regime": regime,
            "candidate": candidate, "status": "mature" if candidate != "INSUFFICIENT" else "INSUFFICIENT",
            "total_episodes": total, "known_episodes": count, "coverage": coverage,
            "positive_ratio": positive, "survival_ratio": survival,
            "new_episode_count": len(new_items), "label_only": True,
        }

    return {
        "status": "ok", "generated_at": current.isoformat().replace("+00:00", "Z"),
        "groups": output_groups,
        "state": {"groups": next_groups},
        "thresholds": {"window_hours": 2, "min_samples": MIN_SAMPLES, "min_coverage": MIN_COVERAGE,
                       "positive_hot": 0.6, "survival_hot": 0.9, "positive_cold": 0.35, "survival_cold": 0.7,
                       "survival_liquidity_usd": 100.0, "cost_return": "(h15price/h0price)*.96/1.04-1"},
        "authority": "label_only_no_buy_sell_no_strategy_change",
    }
