"""Bounded feature-only leases piggybacking on already-due DEX batches.

No network, database or trading calls. Extra identities never displace an
ordinary target and never cause an additional HTTP batch.
"""
from collections import OrderedDict, Counter, deque
from datetime import timedelta
from math import ceil, isfinite

from .models import canonical_token_address, iso, parse_time

MAX_ACTIVE_PER_CHAIN = 2
MAX_WAITING_PER_CHAIN = 12
LEASE_SECONDS = 180
FRESH_SECONDS = 30
CHAINS = frozenset(('bsc', 'solana', 'robinhood'))


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


class SharedBatchCoverage:
    def __init__(self):
        self.waiting = OrderedDict()
        self.active = OrderedDict()
        self.finished = OrderedDict()
        self.counts = Counter()
        self.recent = deque(maxlen=24)
        self.last_batch = {}
        self.enabled = True
        self.disabled_reason = None

    def _finish(self, token_id, reason, now):
        item = self.active.pop(token_id, None) or self.waiting.pop(token_id, None)
        if item is None:
            return
        self.finished[token_id] = now
        while len(self.finished) > 512:
            self.finished.popitem(last=False)
        self.counts[reason] += 1
        self.recent.append({**self._public(item, now), 'reason': reason, 'ended_at': iso(now)})

    def prune(self, now, excluded=()):
        excluded = set(excluded)
        for token_id, item in list(self.active.items()):
            if token_id in excluded:
                self._finish(token_id, 'NORMAL_OR_PRIORITY_TAKEOVER', now)
            elif now >= item['expires_at']:
                self._finish(token_id, 'LEASE_EXPIRED', now)
        for token_id, item in list(self.waiting.items()):
            if token_id in excluded:
                self._finish(token_id, 'NORMAL_OR_PRIORITY_TAKEOVER', now)
            elif (now - item['first_received_at']).total_seconds() > 120:
                self._finish(token_id, 'WAITING_EXPIRED', now)
        for token_id, at in list(self.finished.items()):
            if (now - at).total_seconds() > 900:
                del self.finished[token_id]

    def offer(self, token, snapshot, now, *, floor=1000., excluded=()):
        """Only current, qualified discoveries refused an ordinary seat enter here."""
        self.prune(now, excluded)
        token_id, chain = token.token_id, token.chain
        if (not self.enabled or token_id in set(excluded) or token_id in self.finished
                or token_id in self.active or token_id in self.waiting or chain not in CHAINS):
            return False
        pair = (snapshot.raw or {}).get('pair', snapshot.raw or {})
        pool = canonical_token_address(chain, str(pair.get('pairAddress') or ''))
        base = canonical_token_address(chain, str((pair.get('baseToken') or {}).get('address') or ''))
        created = _finite(pair.get('pairCreatedAt'))
        price, liquidity = _finite(snapshot.price_usd), _finite(snapshot.liquidity_usd)
        volume = _finite(snapshot.volume_5m_usd)
        buys, sells = _finite(snapshot.buys_5m), _finite(snapshot.sells_5m)
        count = buys + sells if buys is not None and sells is not None else None
        if (not pool or pair.get('chainId') != chain or base != canonical_token_address(chain, token.address)
                or 'dexscreener' not in str(snapshot.provider).lower() or created is None
                or not 0 <= snapshot.observed_at.timestamp() - created / 1000 <= 900
                or not 0 <= (now - snapshot.observed_at).total_seconds() <= FRESH_SECONDS
                or price is None or price <= 0 or liquidity is None or liquidity < floor
                or not ((count is not None and count >= 3) or (volume is not None and volume >= 200))):
            return False
        if sum(v['chain'] == chain for v in self.waiting.values()) >= MAX_WAITING_PER_CHAIN:
            self.counts['WAITING_CAPACITY'] += 1
            return False
        self.waiting[token_id] = dict(token_id=token_id, chain=chain, address=token.address,
            pair_address=pool, first_received_at=now, first_observed_at=snapshot.observed_at,
            last_observed_at=snapshot.observed_at, last_received_at=now, frames=1,
            pool_created_at_ms=created, floor=float(floor), coverage_gap=False,
            next_due_at=now, windows={}, frame2_delay_seconds=None, frame3_delay_seconds=None)
        self.counts['OFFERED'] += 1
        return True

    def extend_batch(self, chain, legacy_addresses, now, *, excluded=()):
        """Return unchanged legacy order plus extras fitting its last HTTP batch."""
        # The DEX client deduplicates addresses too; use that same denominator.
        legacy = list(dict.fromkeys(legacy_addresses))
        self.prune(now, excluded)
        if not self.enabled or not legacy:
            return legacy, {}
        spare = (-len(legacy)) % 30
        if not spare:
            return legacy, {}
        normal = {canonical_token_address(chain, x) for x in legacy}
        occupied = sum(v['chain'] == chain for v in self.active.values())
        for token_id, item in list(self.waiting.items()):
            if occupied >= MAX_ACTIVE_PER_CHAIN:
                break
            if item['chain'] != chain or canonical_token_address(chain, item['address']) in normal:
                continue
            if now.timestamp() - item['pool_created_at_ms'] / 1000 > 900:
                self._finish(token_id, 'AGE_EXPIRED', now)
                continue
            item.update(admitted_at=now, expires_at=now + timedelta(seconds=LEASE_SECONDS))
            self.active[token_id] = self.waiting.pop(token_id)
            occupied += 1
            self.counts['ADMITTED'] += 1
        selected = {}
        for token_id, item in sorted(self.active.items(), key=lambda row: (row[1]['next_due_at'], row[1]['admitted_at'], row[0])):
            if len(selected) >= min(spare, MAX_ACTIVE_PER_CHAIN):
                break
            if (item['chain'] == chain and item['next_due_at'] <= now
                    and canonical_token_address(chain, item['address']) not in normal):
                selected[token_id] = item['pair_address']
        extended = legacy + [self.active[k]['address'] for k in selected]
        assert ceil(len(extended) / 30) == ceil(len(legacy) / 30)
        self.last_batch = dict(chain=chain, recorded_at=iso(now), legacy_addresses=len(legacy),
            extra_addresses=len(selected), legacy_http_batches=ceil(len(legacy)/30),
            combined_http_batches=ceil(len(extended)/30), basis='planned_request_shape_not_response_count')
        self.counts['BATCH_EXTRA_IDENTITIES'] += len(selected)
        return extended, selected

    def response(self, quoted, selected, now, snapshot_factory):
        """Keep only the frozen original pool; preserve the real response clocks."""
        result = {k: v for k, v in (quoted or {}).items() if k not in selected}
        for token_id, pool in selected.items():
            item = self.active.get(token_id)
            leased = item is not None
            if leased:
                item['next_due_at'] = now + timedelta(seconds=15)
            value = (quoted or {}).get(token_id)
            if value is None:
                self.counts['SOURCE_NO_TOKEN'] += 1
                continue
            token, snapshot = value
            if token.token_id != token_id:
                self.counts['RESPONSE_IDENTITY_MISMATCH'] += 1
                continue
            if not leased:
                # Normal/priority ownership can change while HTTP is in flight.
                # Keep its identity-bound fresh response, never recreate a lease.
                item = {'chain': token_id.split(':', 1)[0]}
            raw = snapshot.raw or {}
            pairs = raw.get('pairs') or [raw.get('pair', raw)]
            exact = next((p for p in pairs if canonical_token_address(token.chain, str(p.get('pairAddress') or '')) == pool
                and p.get('chainId') == item['chain']
                and canonical_token_address(token.chain, str((p.get('baseToken') or {}).get('address') or '')) == canonical_token_address(token.chain, token.address)), None)
            if exact is None:
                self.counts['SOURCE_NO_EXACT_POOL'] += 1
                continue
            observation = snapshot_factory(exact)
            if observation is None:
                self.counts['SOURCE_UNUSABLE'] += 1
                continue
            observation.observed_at = snapshot.observed_at
            observation.ingested_at = snapshot.ingested_at
            observation.provider = snapshot.provider
            if not 0 <= (now - observation.observed_at).total_seconds() <= FRESH_SECONDS:
                self.counts['STALE_OR_FUTURE'] += 1
                continue
            if not leased:
                result[token_id] = (token, observation)
                self.counts['RELEASED_INFLIGHT_DELIVERED'] += 1
                continue
            if observation.observed_at <= item['last_observed_at']:
                self.counts['DUPLICATE_OBSERVATION'] += 1
                continue
            if (observation.observed_at - item['last_observed_at']).total_seconds() > 60:
                item['coverage_gap'] = True
            item['last_observed_at'], item['last_received_at'] = observation.observed_at, now
            item['frames'] += 1
            elapsed = (observation.observed_at - item['first_observed_at']).total_seconds()
            if item['frames'] in (2, 3):
                item[f"frame{item['frames']}_delay_seconds"] = elapsed
            for horizon in (30, 120):
                if str(horizon) not in item['windows'] and elapsed >= horizon:
                    item['windows'][str(horizon)] = ('OBSERVED' if not item['coverage_gap'] and elapsed <= horizon+30 and item['frames'] >= 3 else 'UNKNOWN_GAP')
            result[token_id] = (token, observation)
            self.counts['EXACT_FRESH_RESPONSES'] += 1
            liquidity = _finite(observation.liquidity_usd)
            if liquidity is not None and liquidity < item['floor']:
                # Still deliver this actual failure to outcome learning; never to BUY.
                self._finish(token_id, 'KNOWN_FLOOR', now)
        return result

    def disable(self, reason, now):
        self.enabled, self.disabled_reason = False, str(reason)
        for token_id in list(self.active):
            self._finish(token_id, 'DISABLED_RESOURCE_GUARD', now)

    @staticmethod
    def _public(item, now):
        return {k: item.get(k) for k in ('token_id', 'chain', 'pair_address', 'frames', 'windows',
            'frame2_delay_seconds', 'frame3_delay_seconds')} | {
            'admitted_at': iso(item['admitted_at']) if item.get('admitted_at') else None,
            'expires_at': iso(item['expires_at']) if item.get('expires_at') else None,
            'quote_age_seconds': max(0., (now-item['last_observed_at']).total_seconds())}

    def snapshot(self, now):
        return dict(schema='shared-batch148/v1', enabled=self.enabled, disabled_reason=self.disabled_reason,
            active=len(self.active), waiting=len(self.waiting), max_active=6, max_active_per_chain=2,
            counts=dict(self.counts), last_batch=dict(self.last_batch),
            opportunities=[self._public(v, now) for v in self.active.values()], recent=list(self.recent),
            additional_http_batches=0, request_contract='extras_only_in_existing_nonempty_batch_spare_capacity')
