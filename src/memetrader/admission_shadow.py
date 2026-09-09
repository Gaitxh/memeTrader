"""Pure, bounded prospective comparator for pattern-watch admission.

This module is intentionally detached from the runtime watch.  Callers supply
already-received, eligibility-filtered compact records and persist the returned
audit record if desired; this class performs no I/O and never requests data.
"""

from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Any, Mapping


class AdmissionShadow:
    """Compare a candidate with a bounded, ephemeral shadow watch state."""

    _CAPS = {"early": 3, "growth": 4, "mature": 3}
    _TTLS = {"early": 15 * 60, "growth": 15 * 60, "mature": 20 * 60}
    _CHAINS = frozenset({"bsc", "robinhood", "solana"})
    _LEASE_SECONDS = 150.0
    _MAX_HELD = 128
    RANKING_VERSION = "admission-shadow-v1"
    _FIELDS = (
        "token_id", "chain", "pool", "bucket", "created_at", "observed_at",
        "recorded_at", "ingested_at", "price", "liquidity", "buys", "sells",
        "provider", "quote_asset", "eligible",
    )

    def __init__(self) -> None:
        # At most ten non-held records for each of the three supported chains.
        # Each record has at most two checkpoint receipts.
        self._watch: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _number(value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)) and isfinite(float(value)):
            return float(value)
        return None

    @classmethod
    def _compact(cls, raw: object) -> dict[str, Any] | None:
        if not isinstance(raw, Mapping):
            return None
        return {field: raw.get(field) for field in cls._FIELDS}

    @staticmethod
    def _actual(raw: object) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            return {"admitted": None, "reason": None, "victim": None}
        admitted = raw.get("admitted")
        return {
            "admitted": admitted if isinstance(admitted, bool) else None,
            "reason": raw.get("reason"),
            "victim": raw.get("victim"),
        }

    def _eligible(self, candidate: dict[str, Any], received_at: float) -> bool:
        if candidate.get("eligible") is not True:
            return False
        if not all(isinstance(candidate.get(key), str) and candidate[key]
                   for key in ("token_id", "chain", "pool", "bucket")):
            return False
        if candidate["chain"] not in self._CHAINS or candidate["bucket"] not in self._CAPS:
            return False
        for key in ("created_at", "observed_at", "recorded_at", "ingested_at"):
            value = self._number(candidate.get(key))
            if value is None or value > received_at:
                return False
            candidate[key] = value
        return True

    @staticmethod
    def _bucket(created_at: float, received_at: float) -> str:
        age = received_at - created_at
        return "early" if age < 900.0 else "growth" if age < 21600.0 else "mature"

    @staticmethod
    def _quiet(item: Mapping[str, Any]) -> bool:
        buys = AdmissionShadow._number(item.get("buys"))
        sells = AdmissionShadow._number(item.get("sells"))
        return buys is not None and sells is not None and buys >= 0 and sells >= 0 and buys + sells <= 3

    @staticmethod
    def _activity(item: Mapping[str, Any]) -> float:
        buys = AdmissionShadow._number(item.get("buys"))
        sells = AdmissionShadow._number(item.get("sells"))
        if buys is None or sells is None:
            return -1.0
        return min(200.0, min(buys, sells))

    @staticmethod
    def _source_quote(item: Mapping[str, Any]) -> tuple[str, str] | None:
        source, quote = item.get("provider"), item.get("quote_asset")
        if not isinstance(source, str) or not source or not isinstance(quote, str) or not quote:
            return None
        return source, quote

    def _prune(self, received_at: float, held: set[str]) -> None:
        for token_id, item in list(self._watch.items()):
            # A held identity survives its watch expiry but consumes no contender
            # capacity.  When it is released, normal expiry pruning resumes.
            if token_id not in held and item["expires_at"] <= received_at:
                self._watch.pop(token_id, None)

    def _refresh_buckets(self, received_at: float, held: set[str]) -> None:
        """Age records without allowing a former early overflow to exceed caps."""
        for item in self._watch.values():
            item["bucket"] = self._bucket(item["created_at"], received_at)
        for chain in self._CHAINS:
            state = self._state(chain, received_at, held)
            for bucket in ("growth", "mature"):
                group = [item for item in state if item["bucket"] == bucket]
                if len(group) <= self._CAPS[bucket]:
                    continue
                keep = set(item["token_id"] for item in sorted(
                    group,
                    # Bucket aging can make a cap impossible to retain.  Preserve
                    # leases first, then the quiet reservation and rank; only an
                    # over-cap set of protected records forces a lease removal.
                    key=lambda item: (
                        0 if item["protected_until"] > received_at else 1,
                        self._rank(item, group, any(self._quiet(row) for row in group)),
                    ),
                )[:self._CAPS[bucket]])
                for item in group:
                    if item["token_id"] not in keep:
                        self._watch.pop(item["token_id"], None)
                state = self._state(chain, received_at, held)
            # This is normally already true, but keeps the comparator bounded
            # if an aged input changes several bucket memberships at once.
            if len(state) > 10:
                for item in sorted(state, key=lambda item: self._rank(item, state, False))[10:]:
                    self._watch.pop(item["token_id"], None)

    def _state(self, chain: str, received_at: float, held: set[str] | None = None) -> list[dict[str, Any]]:
        held = held or set()
        return [item for item in self._watch.values()
                if item["chain"] == chain and item["token_id"] not in held
                and item["expires_at"] > received_at]

    def _summary(self, chain: str, received_at: float, held: set[str] | None = None) -> dict[str, Any]:
        state = self._state(chain, received_at, held)
        by_bucket = {bucket: sum(item["bucket"] == bucket for item in state)
                     for bucket in self._CAPS}
        return {"chain": chain, "nonheld_total": len(state), "by_bucket": by_bucket,
                "cap_total": 10, "caps": dict(self._CAPS)}

    @staticmethod
    def _view(item: Mapping[str, Any], received_at: float) -> dict[str, Any]:
        result = {key: item.get(key) for key in AdmissionShadow._FIELDS}
        result.update({
            "expires_at": item.get("expires_at"),
            "admitted_at": item.get("admitted_at"),
            "protected": item.get("protected_until", 0.0) > received_at,
            "checkpoints": dict(item.get("checkpoints", {})),
        })
        return result

    def _rank(self, item: Mapping[str, Any], universe: list[Mapping[str, Any]],
              quiet_needed: bool) -> tuple[Any, ...]:
        combinations = Counter(self._source_quote(row) for row in universe)
        combo = self._source_quote(item)
        missing = 2 - len(item.get("checkpoints", {}))
        # Unknown provider/quote is an explicit separate category; it is not
        # credited as rare diversity.
        diversity = 1 if combo is None else 0
        frequency = len(universe) + 1 if combo is None else combinations[combo]
        return (
            0 if quiet_needed and self._quiet(item) else 1,
            -missing,
            diversity,
            frequency,
            -self._activity(item),
            item["admitted_at"],
            item["token_id"],
        )

    def _checkpoint(self, item: dict[str, Any], candidate: Mapping[str, Any], received_at: float) -> bool:
        if (candidate["observed_at"] <= item["recorded_at"]
                or candidate["recorded_at"] <= item["recorded_at"]):
            return False
        elapsed = candidate["observed_at"] - item["admitted_at"]
        if 45.0 <= elapsed <= 75.0:
            item["checkpoints"].setdefault("60", received_at)
        elif 105.0 <= elapsed <= 135.0:
            item["checkpoints"].setdefault("120", received_at)
        return True

    def process(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Process one already-received candidate record and return an audit row."""
        received_at = self._number(event.get("received_at")) if isinstance(event, Mapping) else None
        candidate = self._compact(event.get("candidate")) if isinstance(event, Mapping) else None
        empty = {"challenger": None, "admitted": False, "reason": "INVALID_EVENT",
                 "victim": None, "occupancy": None, "pre_state": [],
                 "ranking_version": self.RANKING_VERSION}
        if received_at is None or candidate is None:
            return empty

        held = {token_id for token_id in event.get("held", [])
                if isinstance(token_id, str)}
        self._prune(received_at, held)
        self._refresh_buckets(received_at, held)
        chain = candidate.get("chain")
        pre_state = ([self._view(item, received_at) for item in self._state(chain, received_at, held)]
                     if isinstance(chain, str) else [])
        result: dict[str, Any] = {
            "challenger": candidate.get("token_id"),
            "admitted": False, "reason": None, "victim": None,
            "occupancy": self._summary(chain, received_at, held) if isinstance(chain, str) else None,
            "pre_state": pre_state, "ranking_version": self.RANKING_VERSION,
        }
        if not self._eligible(candidate, received_at):
            result["reason"] = "INELIGIBLE_OR_NONCAUSAL"
            return result
        token_id, chain = candidate["token_id"], candidate["chain"]
        bucket = self._bucket(candidate["created_at"], received_at)
        candidate["bucket"] = bucket
        existing = self._watch.get(token_id)
        if existing is not None:
            if existing["pool"] != candidate["pool"]:
                result["reason"] = "OTHER_POOL_SKIP"
                return result
            if not self._checkpoint(existing, candidate, received_at):
                result["reason"] = "DUPLICATE_OR_STALE_RECEIPT"
                return result
            existing.update({key: candidate[key] for key in (
                "observed_at", "recorded_at", "ingested_at", "price", "liquidity",
                "buys", "sells", "provider", "quote_asset", "eligible")})
            result.update(reason="ALREADY_WATCHED", occupancy=self._summary(chain, received_at, held))
            return result

        candidate_state = dict(candidate, admitted_at=received_at,
                               expires_at=received_at + self._TTLS[bucket],
                               protected_until=received_at + self._LEASE_SECONDS,
                               checkpoints={})
        if token_id in held:
            tracked_held = sum(item["token_id"] in held for item in self._watch.values())
            if tracked_held < self._MAX_HELD:
                self._watch[token_id] = candidate_state
                result["reason"] = "HELD_EXEMPT"
            else:
                result["reason"] = "HELD_EXEMPT_UNTRACKED"
            result.update(admitted=True, occupancy=self._summary(chain, received_at, held))
            return result

        state = self._state(chain, received_at, held)
        same_bucket = [item for item in state if item["bucket"] == bucket]
        by_bucket = {name: sum(item["bucket"] == name for item in state) for name in self._CAPS}
        total = len(state)
        victim_pool: list[dict[str, Any]] = []
        admit_reason = "OPEN_BASE_SLOT"
        if bucket == "early" and by_bucket[bucket] >= self._CAPS[bucket] and total < 10:
            admit_reason = "EARLY_BORROW"
        elif by_bucket[bucket] >= self._CAPS[bucket]:
            victim_pool = same_bucket
            admit_reason = "RANKED_REPLACEMENT"
        elif total >= 10:
            # A base bucket may reclaim only an early-borrowed slot.  Retain the
            # best three early candidates as its reservation.
            early = [item for item in state if item["bucket"] == "early"]
            if len(early) <= self._CAPS["early"]:
                result["reason"] = "CHAIN_CAP_NO_BORROW_TO_RECLAIM"
                return result
            early_sorted = sorted(early, key=lambda item: self._rank(item, early, False))
            victim_pool = early_sorted[self._CAPS["early"]:]
            admit_reason = "BASE_RESERVATION_RECLAIM"
        if not victim_pool:
            self._watch[token_id] = candidate_state
            result.update(admitted=True, reason=admit_reason,
                          occupancy=self._summary(chain, received_at, held))
            return result

        unprotected = [item for item in victim_pool
                       if item["protected_until"] <= received_at]
        if not unprotected:
            result["reason"] = "PROTECTED_LEASE"
            return result
        # Do not evict the one measured quiet reservation from the bucket that
        # actually supplies a victim (early for a base-reservation reclaim).
        quiets = [item for item in victim_pool if self._quiet(item)]
        if len(quiets) == 1:
            unprotected = [item for item in unprotected if item is not quiets[0]]
        if not unprotected:
            result["reason"] = "QUIET_RESERVATION"
            return result
        if admit_reason == "BASE_RESERVATION_RECLAIM":
            victim = max(unprotected, key=lambda item: self._rank(item, victim_pool, False))
            self._watch.pop(victim["token_id"])
            self._watch[token_id] = candidate_state
            result.update(admitted=True, reason=admit_reason, victim=victim["token_id"],
                          occupancy=self._summary(chain, received_at, held))
            return result

        universe = [*state, candidate_state]
        quiet_needed = self._quiet(candidate_state) and not quiets
        victim = max(unprotected, key=lambda item: self._rank(item, universe, quiet_needed))
        if self._rank(candidate_state, universe, quiet_needed) >= self._rank(victim, universe, quiet_needed):
            result["reason"] = "CHALLENGER_NOT_BETTER"
            return result
        self._watch.pop(victim["token_id"])
        self._watch[token_id] = candidate_state
        result.update(admitted=True, reason=admit_reason, victim=victim["token_id"],
                      occupancy=self._summary(chain, received_at, held))
        return result
