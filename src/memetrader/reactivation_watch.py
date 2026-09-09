"""One short observation lease, within legacy capacity; no BUY authority/I/O."""
import math
from .models import canonical_token_address

LEASE_SECONDS = 120


def eligible(member, token, snapshot, now, floor):
    if not member or 'temporary_slot' in member['seen']:
        return False
    raw = snapshot.raw or {}; pair = raw.get('pair', raw)
    prior = member.get('baseline') or {}
    def valid(value):
        return isinstance(value, (int, float)) and math.isfinite(value)
    fields = (snapshot.price_usd, snapshot.liquidity_usd,
              snapshot.volume_5m_usd, snapshot.buys_5m, snapshot.sells_5m)
    if not all(valid(v) for v in fields) or min(fields) < 0:
        return False
    if not (snapshot.price_usd > 0 and snapshot.liquidity_usd >= floor
            and snapshot.ingested_at is not None
            and member['at'] <= snapshot.observed_at <= snapshot.ingested_at <= now
            and 0 <= (now-snapshot.observed_at).total_seconds() <= 30):
        return False
    address = canonical_token_address(token.chain, str(pair.get('pairAddress') or ''))
    if not address or address != prior.get('pool'):
        return False
    if not all(valid(prior.get(k)) for k in ('price', 'liquidity', 'volume', 'trades')):
        return False
    trades = snapshot.buys_5m + snapshot.sells_5m
    # Existing broad activity floor, plus own known pre-rediscovery surface.
    # Missing prior history stays in the normal lane, never fabricates growth.
    return (prior['price'] > 0 and prior['liquidity'] >= floor
            and snapshot.price_usd >= prior['price']
            and snapshot.liquidity_usd >= prior['liquidity']
            and (trades >= 3 or snapshot.volume_5m_usd >= 200)
            and (trades > prior['trades'] or snapshot.volume_5m_usd > prior['volume']))


def victim(watch, chain, occupied, protected, now):
    """Only sampled early overflow; every legacy base reservation is preserved."""
    if any(v['token'].chain == chain and v.get('reactivation_probe') for v in watch.values()):
        return None
    choices = []
    for key, item in watch.items():
        if key in protected or item['token'].chain != chain or not item.get('sampled_at'):
            continue
        admitted = item.get('admitted_at')
        if admitted is None or (now-admitted).total_seconds() < LEASE_SECONDS:
            continue
        bucket = item['bucket']
        if bucket == 'early' and occupied.get((chain, 'early'), 0) > 3:
            choices.append((bucket != 'early', admitted, key))
    return min(choices)[2] if choices else None
