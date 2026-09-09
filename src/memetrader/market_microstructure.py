"""119 research classifier. Caller owns rare-signal admission; no BUY authority.

Frozen mechanistic buckets, not fitted thresholds or identification of humans.
Public latest300 has no documented continuation: incomplete windows stay unknown.
"""
from collections import Counter, OrderedDict
from math import isfinite, sqrt
import asyncio
import time
from urllib.parse import quote

from .models import canonical_token_address, iso, parse_time, utcnow

VERSION = 'market_microstructure_classifier_v3'
# Fixed research definitions, not tuned against case outcomes.
BALANCED_NET_GROSS = .10
EARLY_NET_LIQUIDITY = .01
# Routing intent only, not registration or permission to place a Paper order.
BRANCH_LIMITS = {
    'synthetic_fast_harvest_v1': dict(chain='bsc', stake_usd=1, max_open=1,
                                    absolute_max_hold_seconds=300, narrative=False,
                                    reentry=False, averaging=False),
    'organic_reawakening_flow_v1': dict(stake_usd=5, max_open=2),
    'organic_early_flow_v1': dict(stake_usd=2, max_open=2),
}
HOST = 'api.geckoterminal.com'
NETWORKS = {'bsc': 'bsc', 'robinhood': 'robinhood'}


def unknown(reason, **fields):
    return dict(version=VERSION, state='UNKNOWN', reason=reason,
                decision_eligible=False, affects='none', **fields)


def _cv(values):
    if len(values) < 2 or sum(values) <= 0:
        return None
    mean = sum(values) / len(values)
    return sqrt(sum((x-mean)**2 for x in values)/len(values))/mean


def classify(trades, *, token_id, pool, window_start, window_end,
             received_at, recorded_at, decision_at, coverage_start, coverage_end,
             complete=False, hard_unsellable=False, price_frames=None):
    """Normalized rows must carry exact pool/token, wallet, USD, kind, clocks.

    coverage_* is evidence from the adapter, not min/max selected row shortcuts.
    Empty/partial data never gives positive safety. Repeated transaction rows
    require unique event IDs (transaction hash alone can contain several swaps).
    """
    chain, _ = token_id.split(':', 1)
    pool = canonical_token_address(chain, pool)
    start, end, received, recorded, decision = map(parse_time,
        (window_start, window_end, received_at, recorded_at, decision_at))
    base = dict(token_id=token_id, pool=pool, window_start=iso(start),
                window_end=iso(end), received_at=iso(received), recorded_at=iso(recorded))
    if not pool or not start < end <= received <= recorded <= decision:
        return unknown('INVALID_CLOCKS_OR_IDENTITY', **base)
    if hard_unsellable:
        return {**unknown('EXPLICIT_HARD_EVIDENCE', **base), 'state': 'HARD_UNSELLABLE'}
    if (not complete or coverage_start is None or coverage_end is None
            or parse_time(coverage_start) > start or parse_time(coverage_end) < end):
        return unknown('UNKNOWN_COVERAGE', **base)
    if len(trades) > 300:
        return unknown('ROW_BOUND', **base)
    seen, selected = set(), []
    for t in trades:
        try:
            observed = parse_time(t['observed_at'])
            available = parse_time(t['recorded_at'])
            if (t['token_id'] != token_id or canonical_token_address(chain, t['pool']) != pool
                    or not observed <= available <= recorded):
                return unknown('ROW_IDENTITY_OR_FUTURE', **base)
            value = float(t['usd'])
            wallet = canonical_token_address(chain, t['wallet'])
            if (not t['id'] or not wallet or t['kind'] not in ('buy', 'sell')
                    or not isfinite(value) or value <= 0):
                return unknown('INVALID_TRADE', **base)
        except (KeyError, TypeError, ValueError):
            return unknown('INVALID_TRADE', **base)
        if t['id'] in seen:
            return unknown('DUPLICATE_EVENT', **base)
        seen.add(t['id'])
        if start <= observed <= end:
            selected.append((observed, wallet, t['kind'], value))
    if not selected:
        return unknown('NO_USABLE_TRADES', **base)
    selected.sort()
    gross, buys, sells = Counter(), Counter(), Counter()
    for _, wallet, kind, value in selected:
        gross[wallet] += value
        (buys if kind == 'buy' else sells)[wallet] += value
    total, buy, sell = sum(gross.values()), sum(buys.values()), sum(sells.values())
    ranked = sorted(gross.values(), reverse=True)
    dominant = max(gross, key=gross.get)
    breadth = total**2/sum(v*v for v in gross.values())
    balanced = {w for w in buys.keys() & sells.keys()
                if abs(buys[w]-sells[w])/gross[w] <= BALANCED_NET_GROSS}
    effective = set(gross)-balanced
    effective_net = sum(buys[w]-sells[w] for w in effective)
    external = effective-{dominant}
    metrics = dict(trades=len(selected), buys=sum(t[2]=='buy' for t in selected),
        sells=sum(t[2]=='sell' for t in selected), buy_usd=buy, sell_usd=sell,
        net_usd=buy-sell, gross_usd=total, net_gross_ratio=(buy-sell)/total,
        unique_wallets=len(gross), effective_breadth=breadth,
        top1_notional_share=ranked[0]/total, top3_notional_share=sum(ranked[:3])/total,
        both_side_wallets=len(buys.keys() & sells.keys()),
        dominant_wallet_gross_share=gross[dominant]/total,
        dominant_wallet_buy_share=buys[dominant]/buy if buy else None,
        dominant_wallet_sell_share=sells[dominant]/sell if sell else None,
        dominant_wallet_net_usd=buys[dominant]-sells[dominant],
        dominant_wallet_net_gross_share=(buys[dominant]-sells[dominant])/total,
        dominant_wallet_both_sides=buys[dominant]>0 and sells[dominant]>0,
        balanced_both_side_wallets=len(balanced), effective_wallets=len(effective),
        effective_net_buy_usd=effective_net,
        ex_top1_effective_wallets=len(external),
        ex_top1_net_usd=sum(buys[w]-sells[w] for w in external),
        balanced_net_gross_limit=BALANCED_NET_GROSS,
        size_cv=_cv([t[3] for t in selected]),
        interval_cv=_cv([(b[0]-a[0]).total_seconds() for a,b in zip(selected,selected[1:])]))
    metrics.update(_price_displacement(price_frames, token_id, pool, start, end, recorded,
        buy-sell, sum(buys[w]-sells[w] for w in external)))
    # Descriptive phase only; separate from the frozen v1 entry selector below.
    # No fitted case threshold: >=90% gross, <=1 external effective sender,
    # both sides and >=4 events. Price growth must exceed signed-flow/liquidity
    # scale, with exact aligned causal endpoints. This is NOT calibrated LPI.
    concentrated_cycle = (len(selected)>=4 and gross[dominant]/total>=.9
                          and len(external)<=1 and buys[dominant]>0 and sells[dominant]>0)
    phase = 'UNKNOWN'
    if concentrated_cycle and sell>buy and sells[dominant]>buys[dominant]:
        phase = 'SYNTHETIC_DISTRIBUTING_CYCLE'
    elif (concentrated_cycle and buy>=sell and metrics['price_displacement'] is not None
          and metrics['price_displacement']>0
          and metrics['price_displacement']>abs(metrics['signed_notional_liquidity_ratio'])):
        phase = 'SYNTHETIC_LPI_BUILDING'
    state = 'UNKNOWN'
    # Conservative initial research buckets: one observed sender with BOTH sides
    # and net selling, versus positive net flow with distributed notional.
    if len(selected) >= 4 and len(gross) == 1 and buy > 0 and sell > buy:
        state = 'SYNTHETIC_SINGLE_WALLET_CYCLE'
    elif len(effective) >= 5 and breadth >= 4 and ranked[0]/total <= .5 and effective_net > 0 and buy > sell:
        state = 'ORGANIC_BREADTH_NET_BUY'
    elif len(effective) >= 4 and effective_net > 0 and buy > sell:
        state = 'ORGANIC_BOOTSTRAP_SPREADING'
    elif sell > buy:
        state = 'NET_SELL_DISTRIBUTION'
    return dict(version=VERSION, state=state, phase=phase, reason='MECHANISTIC_BUCKET_NOT_ALPHA',
                decision_eligible=False, affects='none', metrics=metrics,
                signer_is_not_human_identity=True, **base)


def _price_displacement(frames, token_id, pool, start, end, recorded, net, external_net):
    """Optional bounded price evidence, not a price lookup or reconstructed path.

    Exact endpoints align the price change with the signed-flow window. Missing
    liquidity, mismatched endpoints or future receipts invalidate this feature
    group only. Zero net yields an undefined ratio, never infinite support.
    """
    fields = dict(price_displacement=None, price_displacement_per_signed_usd=None,
                  price_displacement_per_external_signed_usd=None,
                  signed_notional_liquidity_ratio=None, liquidity_retention=None,
                  price_monotonic_up_fraction=None, price_step_cv=None,
                  price_feature_status='UNKNOWN')
    if not frames or not 2<=len(frames)<=128:
        return fields
    try:
        stamps=[];prices=[];liquidities=[]
        chain=token_id.split(':')[0]
        for f in frames:
            observed, available = parse_time(f['observed_at']), parse_time(f['recorded_at'])
            p,l=float(f['price_usd']),float(f['liquidity_usd'])
            if (f['token_id']!=token_id or canonical_token_address(chain,f['pool'])!=pool
                    or not start<=observed<=available<=recorded or observed>end
                    or not isfinite(p) or not isfinite(l) or p<=0 or l<=0):return fields
            stamps.append(observed);prices.append(p);liquidities.append(l)
        if stamps[0]!=start or stamps[-1]!=end or any(a>=b for a,b in zip(stamps,stamps[1:])):
            return fields
        gain=prices[-1]/prices[0]-1
        steps=[b/a-1 for a,b in zip(prices,prices[1:])]
        return dict(price_displacement=gain,
            price_displacement_per_signed_usd=gain/net if net else None,
            price_displacement_per_external_signed_usd=gain/external_net if external_net else None,
            signed_notional_liquidity_ratio=net/liquidities[0],
            liquidity_retention=liquidities[-1]/liquidities[0],
            price_monotonic_up_fraction=sum(x>0 for x in steps)/len(steps) if len(steps)>=3 else None,
            price_step_cv=_cv(steps) if len(steps)>=3 else None,
            price_feature_status='ALIGNED_CAUSAL_ENDPOINTS')
    except (KeyError, TypeError, ValueError):
        return fields


def normalize_gecko(payload, *, token_id, pool, received_at):
    """Derive side relative to exact token, never provider default base orientation."""
    chain, address = token_id.split(':', 1)
    address = canonical_token_address(chain, address)
    rows = payload.get('data')
    if not isinstance(rows, list) or len(rows) > 300:
        return None
    normalized = []
    try:
        for row in rows:
            a = row['attributes']
            source = canonical_token_address(chain, a['from_token_address'])
            target = canonical_token_address(chain, a['to_token_address'])
            if (source == address) == (target == address):
                return None
            normalized.append(dict(id=row['id'], token_id=token_id, pool=pool,
                kind='buy' if target == address else 'sell', usd=a['volume_in_usd'],
                wallet=a['tx_from_address'], observed_at=a['block_timestamp'],
                recorded_at=iso(parse_time(received_at))))
    except (KeyError, TypeError, ValueError):
        return None
    return normalized


def classify_amountful(payload, *, token_id, pool, decision_at):
    """Revalidate existing two-window SPL evidence; no RPC or USD parity assumption.

    Conversion is checked at its original local receipt, not refreshed to now.
    The resulting classification remains available only after that receipt.
    """
    from .market_flow import aggregate_market_frames, _time, _stamp
    try:
        received = _time(payload['recorded_at'])
        decision = _time(decision_at)
        resolver = payload['resolver']
        if (not token_id.startswith('solana:') or payload['token_id'] != token_id
                or resolver['base_mint'] != token_id.split(':', 1)[1]
                or resolver['pool_address'] != pool or payload['pool_address'] != pool
                or received is None or decision is None or received > decision):
            return unknown('AMOUNTFUL_IDENTITY_OR_CLOCKS')
        if decision-received > 120:
            return unknown('STALE_AMOUNTFUL')
        flow = aggregate_market_frames(payload['windows'], resolver=resolver,
            quote_conversion=payload.get('quote_conversion'), decision_at=received)
        if not flow['complete'] or not all(w['usd_conversion_complete'] for w in flow['windows']):
            return unknown('AMOUNTFUL_INCOMPLETE_OR_CONVERSION')
        rate = float(payload['quote_conversion']['usd_per_quote'])/10**resolver['quote_decimals']
        rows = [dict(id=f"{t['signature']}:{t['instruction_path']}", token_id=token_id,
                     pool=pool, wallet=t['signer_address'], kind=t['side'].lower(),
                     usd=int(t['quote_amount_raw'])*rate,
                     observed_at=_stamp(_time(t['block_time'])),
                     recorded_at=_stamp(_time(t.get('recorded_at',t.get('ingested_at')))))
                for t in flow['trades']]
        start, end = flow['windows'][0]['window_start'], flow['windows'][-1]['window_end']
        return classify(rows, token_id=token_id, pool=pool, window_start=start, window_end=end,
            received_at=_stamp(received), recorded_at=_stamp(received), decision_at=decision_at,
            coverage_start=start, coverage_end=end, complete=True)
    except (KeyError, TypeError, ValueError, OverflowError):
        return unknown('INVALID_AMOUNTFUL_EVIDENCE')


def classify_page(page, *, token_id, pool, window_start, window_end, decision_at, price_frames=None):
    """Conservative two-boundary coverage; later trades prove recency only.

    Post-cutoff trades never contribute to metrics. Empty quiet tails are not
    assumed complete merely because the HTTP response has a fresh Date header.
    """
    if 'payload' not in page:
        return page
    received = page['received_at']
    rows = normalize_gecko(page['payload'], token_id=token_id, pool=pool, received_at=received)
    if not rows:
        return unknown('UNKNOWN_COVERAGE')
    try:
        stamps = [parse_time(t['observed_at']) for t in rows]
    except (TypeError, ValueError):
        return unknown('INVALID_CLOCKS')
    if stamps != sorted(stamps, reverse=True):
        return unknown('UNVERIFIED_ORDER')
    return classify(rows, token_id=token_id, pool=pool, window_start=window_start,
        window_end=window_end, received_at=received, recorded_at=received,
        decision_at=decision_at, coverage_start=min(stamps), coverage_end=max(stamps), complete=True,
        price_frames=price_frames)


class TradePageClient:
    """Prepared one-page Shadow adapter; disabled unless held guard is supplied.

    No new http client/task/source; shared HttpClient owns transport/backoff.
    Strict start admission must be provided by caller, not a stale idle snapshot.
    """
    def __init__(self, http, *, permit=None, now=utcnow, clock=time.monotonic):
        self.http, self.permit, self.now, self.clock = http, permit, now, clock
        self.cache = OrderedDict()
        self.lock = asyncio.Lock()
        self.next_start = 0.
        self.counts = Counter()

    async def fetch(self, token_id, pool):
        chain, _ = token_id.split(':', 1)
        pool = canonical_token_address(chain, pool)
        if chain not in NETWORKS or not pool:
            return unknown('USE_EXISTING_AMOUNTFUL_OR_UNSUPPORTED')
        key = (chain, pool)
        async with self.lock:
            now = self.clock()
            cached = self.cache.get(key)
            if cached and now < cached[0]:
                self.counts['cache_hit'] += 1
                return cached[1]  # Original receipt preserved, never refreshed.
            if (now < self.next_start or now < self.http._host_backoff_until.get(HOST, 0)):
                self.counts['budget_or_backoff'] += 1
                return unknown('BUDGET_OR_BACKOFF')
            if self.permit is None:
                return unknown('HELD_START_GUARD_UNAVAILABLE')
            # permit is an async context manager implementing shared host start
            # priority; merely testing an idle Event is not sufficient.
            async with self.permit() as allowed:
                if not allowed:
                    return unknown('HELD_PRIORITY')
                self.next_start = now + 60  # <=1 supplemental request/min total.
                self.counts['requests'] += 1
                url = f'https://{HOST}/api/v2/networks/{NETWORKS[chain]}/pools/{quote(pool, safe="")}/trades'
                try:
                    response = await self.http.get(url, retry_429=False)
                    payload = response.json()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    code = getattr(getattr(exc, 'response', None), 'status_code', None)
                    self.counts['rate_limit' if code == 429 else 'error'] += 1
                    if code == 429:
                        self.http._host_backoff_until[HOST] = max(
                            self.http._host_backoff_until.get(HOST, 0), self.clock()+60)
                    return unknown('RATE_LIMIT' if code == 429 else type(exc).__name__)
            received = iso(self.now())
            result = dict(payload=payload, received_at=received, source_url=url,
                          headers={k:response.headers.get(k) for k in ('date','age','etag')})
            self.cache[key] = (self.clock()+60, result)
            while len(self.cache)>128:
                self.cache.popitem(last=False)
            return result


def branch_decision(evidence, *, token_id, pool, frame_observed, frame_recorded,
                    price, liquidity, safety_allow, hard_veto=False,
                    reawakening=False, sell_simulation=None, surface=None,
                    early=False, pool_age_seconds=None):
    """Pure Shadow eligibility. Never registers, fills, clears a hazard or extends hold."""
    if hard_veto or evidence['state']=='HARD_UNSELLABLE':
        return 'REJECT'
    chain = token_id.split(':')[0]
    if (not safety_allow or evidence.get('token_id')!=token_id
            or canonical_token_address(chain,pool)!=evidence.get('pool')
            or not price or not isfinite(price) or price<=0
            or liquidity is None or not isfinite(liquidity) or liquidity<1000
            or not parse_time(evidence['recorded_at'])<parse_time(frame_observed)<=parse_time(frame_recorded)
            or (parse_time(frame_recorded)-parse_time(evidence['recorded_at'])).total_seconds()>120):
        return 'WAIT'
    # A market price is not proof of a native buy/exit/migration lifecycle.
    srf = surface or {}
    if not (srf.get('kind') == 'COMMON_PAPER_EXACT_POOL'
            and srf.get('authenticated') is True and srf.get('buy_sell_lifecycle') is True
            and srf.get('token_id') == token_id
            and canonical_token_address(chain,srf.get('pool','')) == evidence['pool']
            and srf.get('observed_at') and srf.get('recorded_at')
            and parse_time(srf['observed_at']) <= parse_time(srf['recorded_at']) <= parse_time(frame_observed)
            and (parse_time(frame_observed)-parse_time(srf['observed_at'])).total_seconds() <= 120):
        return 'DATA_BLOCKED_SURFACE'
    if evidence['state']=='ORGANIC_BREADTH_NET_BUY' and reawakening:
        return 'ORGANIC_SHADOW_ELIGIBLE'
    if (early and evidence['state'] in {'ORGANIC_BREADTH_NET_BUY','ORGANIC_BOOTSTRAP_SPREADING'}
            and pool_age_seconds is not None and 0 <= pool_age_seconds <= 900
            and evidence['metrics']['effective_wallets'] >= 4
            and evidence['metrics']['effective_net_buy_usd']/liquidity >= EARLY_NET_LIQUIDITY):
        return 'ORGANIC_EARLY_SHADOW_ELIGIBLE'
    if evidence['state']=='SYNTHETIC_SINGLE_WALLET_CYCLE' and chain=='bsc':
        s=sell_simulation or {}
        if (s.get('success') is True and s.get('token_id')==token_id
                and canonical_token_address(chain,s.get('pool',''))==evidence['pool']
                and s.get('recorded_at') and s.get('observed_at')
                and parse_time(s['observed_at'])<=parse_time(s['recorded_at'])<=parse_time(frame_observed)
                and (parse_time(frame_observed)-parse_time(s['observed_at'])).total_seconds()<=60):
            return 'SYNTHETIC_SHADOW_ELIGIBLE'
    return 'WAIT'


class MicrostructureShadow:
    """Bounded receipt/outcome state for existing idle flush/snapshot callbacks.

    Not installed in runtime until the shared request-start guard is available.
    Receipts are frozen even for UNKNOWN/HARD; no historical snapshot query.
    """
    def __init__(self, state=None):
        from .clone_consensus_outcomes import CloneConsensusOutcomes
        state = state or {}
        self.outcomes = CloneConsensusOutcomes(state.get('outcomes'))
        self.receipts = list(state.get('receipts', []))[-128:]
        self.counts = Counter(state.get('counts', {}))

    def capture(self, *, evidence_id, evidence, token_id, pool, anchor, now, costs):
        # evidence_id is a newly inserted unique evidence receipt ID, never a
        # reconstructed old opportunity. Existing outcome seen-state dedupes it.
        before = self.outcomes.state['triggers']
        self.outcomes.capture_signal('micro119:'+str(evidence_id), token_id, pool, anchor, costs, now)
        if self.outcomes.state['triggers'] == before:
            return
        self.receipts = (self.receipts+[dict(evidence_id=evidence_id, **evidence)])[-128:]
        self.counts[evidence['state']] += 1
        phase=evidence.get('phase','UNKNOWN')
        self.counts['phase:'+phase] += 1
        for row in self.outcomes.state['pending'].values():
            if row.get('evidence_id') == 'micro119:'+str(evidence_id):
                row.update(category='MICROSTRUCTURE_SHADOW', reasons=[evidence['state'],'phase:'+phase],
                           hard_veto=['HARD_UNSELLABLE'] if evidence['state']=='HARD_UNSELLABLE' else [],
                           arms=[], classifier_receipt=evidence)

    def observe(self, token_id, snapshot, ingested, recorded):
        self.outcomes.observe(token_id, snapshot, ingested, recorded)

    def snapshot(self, now):
        self.outcomes.expire(now)
        return dict(version=VERSION, decision_eligible=False, affects='none',
                    receipts=self.receipts, counts=dict(self.counts), outcomes=self.outcomes.snapshot())
