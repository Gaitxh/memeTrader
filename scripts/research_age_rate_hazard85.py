"""Frozen actual-fill descriptive veto audit. Read-only; no fitted thresholds."""
import collections
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import statistics
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/research/age_rate_hazard85'
ARM = 'resource_age_rate_candidate_v1'
SPEC = dict(catastrophe_return_lte=-.5, tail_return_gte=1,
    age_edges_seconds=[900, 21600], liquidity_edges_usd=[10000, 100000],
    buy_share_edges=[.5, .75, .9], turnover_edges=[1, 10],
    direction_edges=[0], prior_frame_max_gap_seconds=120, max_prior_rows=128,
    trim_fraction=.1, no_threshold_search=True,
    minimum_robustness_gate='No automatic promotion; require cross-date and cross-chain positive evidence, not jackpot exclusion.')


def ts(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def number(value):
    return float(value) if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) else None


def norm(chain, address):
    return str(address or '') if chain == 'solana' else str(address or '').lower()


def frame(row, available):
    if not row:
        return None
    try:
        raw = json.loads(row['raw_json']); pair = raw.get('pair', {})
        chain, address = row['token_id'].split(':', 1)
        obs, ing, rec = (ts(row[k]) for k in ('observed_at', 'ingested_at', 'recorded_at'))
        pool = norm(chain, pair.get('pairAddress'))
        if not pool or pair.get('chainId') != chain or norm(chain, pair.get('baseToken', {}).get('address')) != address:
            return None
        if not obs <= ing <= rec <= available:
            return None
        price, liq = number(row['price_usd']), number(row['liquidity_usd'])
        if price is None or price <= 0:
            return None
        created = number(pair.get('pairCreatedAt'))
        age = obs-created/1000 if created else None
        if age is not None and age < 0:
            return None
        trades = pair.get('txns', {}).get('m5', {})
        buys, sells = number(trades.get('buys')), number(trades.get('sells'))
        volume = number(pair.get('volume', {}).get('m5'))
        return dict(id=row['id'], pool=pool, obs=obs, ing=ing, rec=rec, price=price,
            liq=liq, age=age, buys=buys, sells=sells, volume=volume,
            provider=raw.get('upstream_provider') or row['provider'],
            quote=norm(chain, pair.get('quoteToken', {}).get('address')) or 'UNKNOWN',
            activity_presence='KNOWN' if buys is not None and sells is not None else 'UNKNOWN',
            normalized_activity=[row['buys_5m'], row['sells_5m']])
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def freeze():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'preregistered.json').write_text(json.dumps(SPEC, indent=2), encoding='utf-8')
    cfg = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    c = sqlite3.connect((ROOT/cfg['database']).as_uri()+'?mode=ro', uri=True, timeout=3)
    c.row_factory = sqlite3.Row
    started = time.monotonic()
    c.set_progress_handler(lambda: int(time.monotonic()-started > 25), 1000)
    c.execute('BEGIN')
    cutoff = datetime.now(timezone.utc).isoformat()
    version = c.execute('select definition_version from chain_meme_trader_v6_activations where entry_execution_enabled=1 order by activated_at desc,rowid desc limit 1').fetchone()[0]
    frontier = {t:c.execute('select max(id) from '+t).fetchone()[0] for t in ('token_snapshots', 'chain_meme_trader_trades')}
    positions = [dict(r) for r in c.execute('select * from chain_meme_trader_positions where definition_version=? and arm_id=?', (version, ARM))]
    trades = [dict(r) for r in c.execute('select * from chain_meme_trader_trades where definition_version=? and arm_id=?', (version, ARM))]
    for pos in positions:
        pos['entry_row'] = None
        r = c.execute('select * from token_snapshots where id=?', (pos['entry_snapshot_id'],)).fetchone()
        if r: pos['entry_row'] = dict(r)
        pos['prior_rows'] = [dict(r) for r in c.execute('select * from token_snapshots where token_id=? and observed_at<? order by observed_at desc limit 128', (pos['token_id'], pos['opened_at']))]
        pos['native_facts'] = [dict(r) for r in c.execute('select * from token_launch_facts where token_id=? and recorded_at<=? order by source_observed_at desc limit 20', (pos['token_id'], pos['opened_at']))]
    c.rollback(); c.close()
    result = dict(cutoff=cutoff, version=version, arm=ARM, frontier=frontier,
        read_seconds=time.monotonic()-started, spec=SPEC, positions=positions, trades=trades)
    (OUT/'frozen.json').write_text(json.dumps(result), encoding='utf-8')
    return result


def band(value, edges, labels):
    if value is None:
        return 'UNKNOWN'
    for edge, label in zip(edges, labels):
        if value < edge:
            return label
    return labels[-1]


def direction(value):
    return 'UNKNOWN' if value is None else 'DOWN' if value < 0 else 'UP' if value > 0 else 'FLAT'


def stats(rows):
    closed = [r for r in rows if r['terminal']]
    values = sorted(r['pnl'] for r in closed)
    returns = sorted(r['return'] for r in closed if r['return'] is not None)
    n = len(values); k = int(n*.1); trimmed = values[k:n-k] if k else values
    positive = sum(max(v, 0) for v in values)
    catastrophe = [r for r in closed if r['return'] is not None and r['return'] <= -.5]
    tail = [r for r in closed if r['return'] is not None and r['return'] >= 1]
    return dict(n=n, unique_tokens=len({r['token_id'] for r in closed}), open_censored=len(rows)-n,
        pnl=sum(values), wins=sum(v>0 for v in values), median=statistics.median(values) if n else None,
        mean=statistics.mean(values) if n else None, trim10_mean=statistics.mean(trimmed) if trimmed else None,
        min=min(values) if n else None, max=max(values) if n else None,
        return_median=statistics.median(returns) if returns else None,
        return_mean=statistics.mean(returns) if returns else None,
        positive_profit=positive, all_loss_dollars=-sum(min(v, 0) for v in values),
        catastrophic_n=len(catastrophe), catastrophic_loss_dollars=-sum(r['pnl'] for r in catastrophe),
        tail_n=len(tail), tail_profit=sum(r['pnl'] for r in tail),
        pnl_without_top1=sum(values[:-1]) if n else None,
        pnl_without_top3=sum(values[:-3]) if n>=3 else None,
        top1_positive_concentration=max(values)/positive if positive else None,
        top3_positive_concentration=sum(sorted((max(v,0) for v in values), reverse=True)[:3])/positive if positive else None,
        close_causes=dict(collections.Counter(r['cause'] for r in closed)))


def analyze(data):
    trade_groups = collections.defaultdict(list)
    for t in data['trades']:
        if ts(t['created_at']) <= ts(data['cutoff']) and (not t['recorded_at'] or ts(t['recorded_at']) <= ts(data['cutoff'])):
            trade_groups[(t['token_id'], t['shadow_cohort_id'])].append(t)
    rows=[]; discrepancies=[]
    for p in data['positions']:
        opened=ts(p['opened_at'])
        if opened > ts(data['cutoff']): continue
        terminal=bool(p['closed_at'] and ts(p['closed_at'])<=ts(data['cutoff']) and p['status']!='open')
        trades=trade_groups[(p['token_id'],p['shadow_cohort_id'])]
        buys=[t for t in trades if t['side'].upper()=='BUY']
        cost=-sum(t['net_cash_flow_usd'] for t in buys)
        realized=sum(t['realized_pnl_usd'] or 0 for t in trades)
        cash=sum(t['net_cash_flow_usd'] for t in trades)
        if not math.isclose(realized,p['realized_pnl_usd'] or 0,abs_tol=1e-7) or (terminal and not math.isclose(realized,cash,abs_tol=1e-7)):
            discrepancies.append(dict(token=p['token_id'],cohort=p['shadow_cohort_id'],position_pnl=p['realized_pnl_usd'],trade_pnl=realized,cash=cash))
        if len(buys)!=1 or not p['entry_execution_price_usd'] or not p['paper_quantity_tokens'] or not math.isclose(p['entry_execution_price_usd']*p['paper_quantity_tokens'],cost,abs_tol=1e-7):
            discrepancies.append(dict(token=p['token_id'],cohort=p['shadow_cohort_id'],kind='entry_cost_quantity_mismatch'))
        e=frame(p['entry_row'],opened); previous=[]
        for s in p['prior_rows']:
            f=frame(s,opened)
            if e and f and f['pool']==e['pool'] and e['obs']>f['rec'] and 0<e['obs']-f['obs']<=120:
                previous.append(f)
        previous.sort(key=lambda r:(r['obs'],r['id']),reverse=True)
        prior=previous[0] if previous else None
        earlier=next((r for r in previous[1:] if prior['obs']>r['rec']),None) if prior else None
        continuation=e['price']/prior['price']-1 if prior else None
        growth=e['liq']/prior['liq']-1 if prior and prior['liq'] and e['liq'] is not None else None
        count=lambda r:r['buys']+r['sells'] if r and r['buys'] is not None and r['sells'] is not None else None
        acceleration=None
        if earlier and all(count(r) is not None for r in (e,prior,earlier)):
            acceleration=(count(e)-count(prior))/(e['obs']-prior['obs'])-(count(prior)-count(earlier))/(prior['obs']-earlier['obs'])
        share=e['buys']/count(e) if e and count(e) and e['buys'] is not None else None
        turnover=e['volume']/e['liq'] if e and e['volume'] is not None and e['liq'] and e['liq']>0 else None
        facts=[f for f in p['native_facts'] if ts(f['source_observed_at'])<=ts(f['ingested_at'])<=ts(f['recorded_at'])<=opened]
        reason=p['close_reason'] or 'OPEN_CENSORED'
        cause=next((word for word in ('writeoff','hard_stop','max_hold','trailing') if word in reason.lower()),'OTHER')
        # Keep known source-confounded positions separate; do not silently drop losses.
        confounded=opened<ts('2026-09-08T19:51:47Z') and ts(p['closed_at'] or data['cutoff'])>=ts('2026-09-08T19:06:00Z')
        features=dict(chain=p['token_id'].split(':')[0],date=p['opened_at'][:10],
            provider=e['provider'] if e else 'UNKNOWN',
            age=band(e['age'] if e else None,[900,21600],['EARLY_LT15M','GROWTH_15M_6H','MATURE_GE6H']),
            liquidity=band(e['liq'] if e else None,[10000,100000],['LT10K','10K_100K','GE100K']),
            buy_share=band(share,[.5,.75,.9],['LT50','50_75','75_90','GE90']),
            turnover=band(turnover,[1,10],['LT1','1_10','GE10']),
            entry_continuation=direction(continuation), liquidity_growth=direction(growth),
            rolling_count_acceleration=direction(acceleration),
            source_continuity='UNKNOWN' if not prior else 'SAME' if e['provider']==prior['provider'] else 'CHANGED',
            raw_activity=e['activity_presence'] if e else 'UNKNOWN',
            native_provenance='ASOF_LAUNCH_FACT' if facts else 'UNKNOWN',
            source_period='STORM_CONFOUNDED' if confounded else 'CLEAN')
        rows.append(dict(token_id=p['token_id'],cohort=p['shadow_cohort_id'],terminal=terminal,
            pnl=realized if terminal else None,partial_realized_pnl=realized,cost=cost,stake=p['stake_usd'],
            return_=realized/cost if cost>0 and terminal else None,
            cause=cause,close_reason=reason,opened_at=p['opened_at'],closed_at=p['closed_at'],
            source_entry_fill_id=p['source_entry_fill_id'],entry_snapshot_id=p['entry_snapshot_id'],
            entry_execution_price=p['entry_execution_price_usd'],quantity=p['paper_quantity_tokens'],
            entry=e,prior=prior,earlier=earlier,features=features,asof_native_fact_ids=[f['id'] for f in facts],
            raw_values=dict(buy_share=share,turnover=turnover,continuation=continuation,liquidity_growth=growth,rolling_count_acceleration=acceleration)))
        rows[-1]['return']=rows[-1].pop('return_')
    strata={}
    for feature in rows[0]['features'] if rows else []:
        for value in sorted({r['features'][feature] for r in rows}):
            subset=[r for r in rows if r['features'][feature]==value];s=stats(subset)
            s['by_date']={d:stats([r for r in subset if r['features']['date']==d]) for d in sorted({r['features']['date'] for r in subset})}
            s['by_chain']={d:stats([r for r in subset if r['features']['chain']==d]) for d in sorted({r['features']['chain'] for r in subset})}
            s['by_chain_date']={d:stats([r for r in subset if r['features']['chain']+'/'+r['features']['date']==d]) for d in sorted({r['features']['chain']+'/'+r['features']['date'] for r in subset})}
            s['clean']=stats([r for r in subset if r['features']['source_period']=='CLEAN'])
            s['veto_net_pnl_change']=-s['pnl']
            s['positive_dollars_sacrificed']=s['positive_profit'];s['tail_dollars_sacrificed']=s['tail_profit']
            strata[feature+'='+str(value)]=s
    casebook=json.loads((ROOT/'data/research/today23_78/casebook.json').read_text(encoding='utf-8'))
    case_ids={r['identity']['token_id'] for r in casebook['cases']}
    token_pnl=collections.defaultdict(float)
    for r in rows:
        if r['terminal']:token_pnl[r['token_id']]+=r['pnl']
    values=sorted(token_pnl.values())
    return dict(cutoff=data['cutoff'],frontier=data['frontier'],spec=SPEC,summary=stats(rows),
        clean_summary=stats([r for r in rows if r['features']['source_period']=='CLEAN']),
        unique_token_robustness=dict(n=len(values),median=statistics.median(values),pnl_without_top1=sum(values[:-1]),pnl_without_top3=sum(values[:-3])),
        reconciliation_discrepancies=discrepancies,rows=rows,strata=strata,
        today23_diagnostics=[r for r in rows if r['token_id'] in case_ids])


if __name__=='__main__':
    data=json.loads((OUT/'frozen.json').read_text(encoding='utf-8')) if (OUT/'frozen.json').exists() else freeze()
    result=analyze(data)
    (OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('cutoff','summary','clean_summary','reconciliation_discrepancies')},indent=2))
