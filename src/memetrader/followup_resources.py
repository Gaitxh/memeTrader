"""Bounded acquisition retirement, not an entry filter or a settlement rule.

Only fresh, identity-bound observations can release dense watch resources.
Missing data never proves death. A later healthy frame (or a different pool)
can be observed again without changing any strategy's re-entry contract.
"""
from collections import Counter, OrderedDict
from math import isfinite

from .models import canonical_token_address, iso, parse_time


class PoolFollowupResources:
    def __init__(self, saved=None):
        self.frames = OrderedDict()
        self.retired = OrderedDict()
        self.counts = Counter()
        self.dirty = False
        for item in (saved or {}).get("retired", [])[-512:]:
            try:
                parse_time(item["observed_at"])
                self.retired[(item["token_id"], item["pool"])] = dict(item)
            except (KeyError, TypeError, ValueError):
                continue

    def blocked(self, token_id, pool):
        chain = token_id.partition(":")[0]
        return (token_id, canonical_token_address(chain, str(pool))) in self.retired

    def observe(self, token, snapshot, now, *, floor=1000.):
        raw = snapshot.raw or {}
        pair = raw.get("pair", raw)
        pool = canonical_token_address(token.chain, str(pair.get("pairAddress") or ""))
        base = canonical_token_address(token.chain, str((pair.get("baseToken") or {}).get("address") or ""))
        try:
            price, liquidity = float(snapshot.price_usd), float(snapshot.liquidity_usd)
            stamp = snapshot.observed_at
            received = snapshot.ingested_at or stamp
            if (not pool or pair.get("chainId") != token.chain
                    or base != canonical_token_address(token.chain, token.address)
                    or snapshot.token_id != token.token_id
                    or not all(isfinite(x) for x in (price, liquidity))
                    or price <= 0 or liquidity < 0
                    or not stamp <= received <= now
                    or not 0 <= (now - stamp).total_seconds() <= 30):
                return
        except (TypeError, ValueError, OverflowError):
            return
        key = (token.token_id, pool)
        prior = self.frames.get(key, {})
        if prior and stamp <= prior["at"]:
            return  # cached/replayed frames are not independent confirmations
        tombstone = self.retired.get(key)
        if tombstone and stamp <= parse_time(tombstone["observed_at"]):
            return
        peak = max(price, prior.get("peak", price))
        empty = (liquidity == 0 and snapshot.volume_5m_usd == 0
                 and snapshot.buys_5m == 0 and snapshot.sells_5m == 0)
        collapsed = price <= peak * .0001 and liquidity < floor
        reason = "empty_inactive_pool" if empty else "collapsed_thin_pool" if collapsed else None
        elapsed = (stamp - prior["at"]).total_seconds() if prior else 0
        # A single zero print while trading continues must never evict a pool.
        confirmed = bool(reason and prior.get("reason") == reason and 5 <= elapsed <= 300)
        if liquidity >= floor and tombstone:
            del self.retired[key]
            self.counts["healthy_pool_reactivated"] += 1
            self.dirty = True
        elif confirmed and not tombstone:
            self.retired[key] = dict(token_id=token.token_id, pool=pool,
                reason=reason, observed_at=iso(stamp), prior_observed_at=iso(prior["at"]),
                price_usd=price, liquidity_usd=liquidity, peak_observed_price=peak,
                scope="acquisition_only_not_proof_of_fill_or_writeoff")
            while len(self.retired) > 512:
                self.retired.popitem(last=False)
            self.counts["confirmed_" + reason] += 1
            self.dirty = True
        self.frames[key] = dict(at=stamp, peak=peak, reason=reason)
        self.frames.move_to_end(key)
        while len(self.frames) > 4096:
            self.frames.popitem(last=False)

    def state(self):
        return {"version": "pool-followup-resources/v1", "retired": list(self.retired.values()),
                "counts_since_start": dict(self.counts)}
