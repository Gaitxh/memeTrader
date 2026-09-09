"""Bounded frozen shape diagnostic. No runtime import, trading or source writes.

Predeclared: first eight strict frames within 15m, gaps <=120s, span >=60s,
one provider. Next strict frame (<=120s) is research entry. Sep7 medians only;
Sep8 unchanged holdout. Price shape is never a scam label.
"""
from __future__ import annotations
import collections
import hashlib
import itertools
import json
import math
import sqlite3
import statistics as st
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/research/universe71'
OUT = ROOT / 'data/research/path_shape101'
DAYS = ('2026-09-07', '2026-09-08')


def med(xs):
    return st.median(xs) if xs else None


def fit(x, y):
    """Theil-Sen line; robust residual scale and ordinary SSE R2 (may be <0)."""
    slope = med([(y[j]-y[i])/(x[j]-x[i]) for i in range(len(x))
                 for j in range(i+1, len(x)) if x[j] > x[i]])
    if slope is None:
        return None, None, None
    intercept = med([b-slope*a for a, b in zip(x, y)])
    residual = [b-(intercept+slope*a) for a, b in zip(x, y)]
    total = sum((v-st.mean(y))**2 for v in y)
    r2 = 1-sum(v*v for v in residual)/total if total else None
    center = med(residual)
    return slope, r2, med([abs(v-center) for v in residual])


def corr(x, y):
    dx = [v-st.mean(x) for v in x]; dy = [v-st.mean(y) for v in y]
    den = math.sqrt(sum(v*v for v in dx)*sum(v*v for v in dy))
    return sum(a*b for a, b in zip(dx, dy))/den if den else None


def shape(frames):
    x = [s['obs']-frames[0]['obs'] for s in frames]
    y = [math.log(s['price']/frames[0]['price']) for s in frames]
    dy = [b-a for a, b in zip(y, y[1:])]
    slope, r2, mad = fit(x, y)
    up = sum(v > 0 for v in dy)/len(dy)
    # Fixed descriptive scales, not searched against outcomes.
    plateau = sum(abs(v) <= math.log(1.001) for v in dy)/len(dy)
    jumps = [(x[i+1], v) for i, v in enumerate(dy) if v >= math.log(1.01)]
    gaps = [b[0]-a[0] for a, b in zip(jumps, jumps[1:])]
    def cv(values):
        return st.pstdev(values)/st.mean(values) if len(values) >= 2 and st.mean(values)>0 else None
    state = 'NORMAL'
    if y[-1] > 0 and r2 is not None and r2 >= .9 and up >= .85:
        state = 'LINEAR_RATCHET'
    elif y[-1] > 0 and plateau >= 2/7 and len(jumps) >= 3 and min(dy) >= -math.log(1.001):
        state = 'STAIRCASE_RATCHET'
    ly = [math.log(s['liq']/frames[0]['liq']) for s in frames]
    return dict(log_slope=slope, robust_r2=r2, residual_mad=mad,
                monotonic_up_fraction=up, plateau_fraction=plateau,
                staircase_score=plateau*len(jumps)/len(dy),
                jump_interval_cv=cv(gaps), jump_size_cv=cv([v for _, v in jumps]),
                liquidity_price_correlation=corr(y, ly),
                liquidity_price_elasticity=ly[-1]/y[-1] if abs(y[-1])>1e-12 else None,
                liquidity_retention=min(s['liq'] for s in frames)/frames[0]['liq'],
                displacement=math.expm1(y[-1])), state


def causal(frames):
    kept = []
    for row in frames:
        if not kept or row['obs'] > kept[-1]['rec']:
            kept.append(row)
    return kept


def outcome(entry, future, horizon):
    prev = entry; gap = False; path = []; first = None; endpoint = None
    for row in future:
        if row['obs'] <= prev['rec']:
            continue
        if row['obs'] > entry['rec']+horizon+120:
            break
        gap |= row['obs']-prev['rec'] > 120
        age = row['obs']-entry['rec']
        value = row['price']*.96/(entry['price']*1.04)-1
        if age <= horizon:
            path.append(value)
            if first is None and (value >= .3 or value <= -.2):
                first = 'UNKNOWN_GAP' if gap else 'POSITIVE_FIRST' if value >= .3 else 'STOP_FIRST'
        if age >= horizon and endpoint is None:
            endpoint = value
        prev = row
    return dict(frames=len(path), tail100=any(v>=1 for v in path) if path else None,
                loss50=any(v<=-.5 for v in path) if path else None,
                first_hit=first or 'UNKNOWN_NO_HIT', endpoint=endpoint,
                mfe=max(path) if path else None, gap_seen=gap,
                floor_failure='UNKNOWN_FILTERED_FROM_FROZEN_INPUT')


def stats(rows):
    out = {'n': len(rows), 'horizons': {}}
    for h in (900, 3600, 14400):
        oo = [r['outcomes'].get(str(h), {}) for r in rows]
        paths = sum(bool(o.get('frames')) for o in oo)
        tails = sum(o.get('tail100') is True for o in oo)
        loss = sum(o.get('loss50') is True for o in oo)
        out['horizons'][str(h)] = dict(paths=paths, unknown=len(rows)-paths,
            endpoints=sum(o.get('endpoint') is not None for o in oo), tails=tails, losses=loss,
            tail_rate_observed=tails/paths if paths else None,
            loss_rate_observed=loss/paths if paths else None,
            tail_rate_all=tails/len(rows) if rows else None,
            loss_rate_all=loss/len(rows) if rows else None,
            first_hit=dict(collections.Counter(o.get('first_hit','UNKNOWN_NO_ENTRY') for o in oo)),
            tail_count_after_top1=max(0,tails-1), tail_count_after_top3=max(0,tails-3))
    return out


def raw_activity(rows):
    """Outcome-blind SHA sample <=300/date; exact PK reads only, max4800 rows."""
    chosen=[]
    for day in DAYS:
        chosen += sorted([r for r in rows if r['day']==day],
                         key=lambda r:hashlib.sha256((r['token']+r['pool']).encode()).digest())[:300]
    ids=sorted({i for r in chosen for i in r['feature_ids']})
    source=ROOT/'data/memetrader_forward_20260830_r6.sqlite3'
    c=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    c.execute('PRAGMA query_only=ON'); raw={}; started=time.monotonic()
    c.set_progress_handler(lambda:int(time.monotonic()-started>20),10000)
    plan=c.execute('EXPLAIN QUERY PLAN SELECT id,raw_json FROM token_snapshots WHERE id IN (1,2)').fetchall()
    for lo in range(0,len(ids),200):
        batch=ids[lo:lo+200]
        for i,j in c.execute('SELECT id,raw_json FROM token_snapshots WHERE id IN ('+','.join('?'*len(batch))+')',batch):
            try: raw[i]=json.loads(j or '{}').get('pair',{})
            except (ValueError,TypeError): raw[i]={}
    c.close(); counts=collections.Counter()
    for r in chosen:
        triples=[]
        for i in r['feature_ids']:
            pair=raw.get(i) or {}; tx=(pair.get('txns') or {}).get('m5') or {}
            values=[(pair.get('volume') or {}).get('m5'),tx.get('buys'),tx.get('sells')]
            if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0 for v in values):
                counts['frame_missing']+=1; break
            counts['explicit_zero_fields']+=sum(v==0 for v in values); triples.append(values)
        if len(triples)!=8: continue
        counts['complete_episodes']+=1
        volume=st.mean(v[0] for v in triples); tx=st.mean(v[1]+v[2] for v in triples)
        r['features'].update(gain_per_reported_volume=r['features']['displacement']/volume if volume else None,
            gain_per_reported_transaction=r['features']['displacement']/tx if tx else None,
            buy_count_share=triples[-1][1]/sum(triples[-1][1:]) if sum(triples[-1][1:]) else None,
            volume_liquidity=volume/r['feature_liq'])
        r['activity_audited']=True
    return dict(sampled_episodes=len(chosen),pk_ids=len(ids),returned_ids=len(raw),counts=counts,
                query_plan=plan,seconds=time.monotonic()-started,
                caveat='Overlapping 5m aggregates are proxies, not gross traded notional or unique buyers.')


def vault_audit(rows):
    """Bounded existing pool index lookup; no historical source table scan."""
    source=ROOT/'data/memetrader_forward_20260830_r6.sqlite3'
    c=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    started=time.monotonic();c.set_progress_handler(lambda:int(time.monotonic()-started>10),10000)
    versions=list(c.execute('SELECT observer_version FROM chain_meme_v21_vault_shadow_registrations LIMIT 20'))
    counts=collections.Counter();examples=[]
    for r in rows:
        # This is the Solana vault observer, not EVM swap reconstruction.
        if r['chain']!='solana': continue
        cutoff=datetime.fromtimestamp(r['feature_rec'],timezone.utc)
        bound=cutoff.replace(microsecond=999999).isoformat().replace('+00:00','Z')
        for version in versions:
            counts['pool_lookups']+=1
            target=c.execute('SELECT * FROM chain_meme_v21_vault_shadow_pool_targets WHERE observer_version=? AND pool_address=?',
                             (version[0],r['pool'])).fetchone()
            if target is None or target['token_id']!=r['token']:continue
            counts['exact_targets']+=1
            if datetime.fromisoformat(target['registered_at'].replace('Z','+00:00'))>cutoff:continue
            candidates=c.execute('SELECT * FROM chain_meme_v21_vault_shadow_frames WHERE observer_version=? AND pool_target_id=? AND observed_at<=? ORDER BY observed_at DESC,id DESC LIMIT 20',
                                 (version[0],target['id'],bound)).fetchall()
            valid=[v for v in candidates if datetime.fromisoformat(v['observed_at'].replace('Z','+00:00'))<=datetime.fromisoformat(v['recorded_at'].replace('Z','+00:00'))<=cutoff]
            if not valid:continue
            v=valid[0];r['combined_vault_state']=v['observer_state'];r['vault_frame_id']=v['id']
            r['vault_features_asof']=json.loads(v['features_json']);r['vault_holder_cohorts_asof']=json.loads(v['holder_cohorts_json'])
            counts['asof_frames']+=1
            if len(examples)<10:examples.append({'token':r['token'],'frame_id':v['id'],'state':v['observer_state']})
    c.close()
    return dict(counts=counts,examples=examples,version_count=len(versions),seconds=time.monotonic()-started,
                unavailable='No eligible frame remains UNKNOWN, never NORMAL or SYNTHETIC.')


def main():
    started=time.monotonic(); u=json.loads((DATA/'universe.json').read_text(encoding='utf-8'))
    assert u['meta']['complete'] and u['meta']['source_frontier']==2194123
    anchors={r['anchor_id']:r for r in u['rows'] if r['original'] and r['day'] in DAYS}
    c=sqlite3.connect((DATA/'normalized_identity.sqlite3').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    rows=[];excluded=collections.Counter()
    for _,group in itertools.groupby(c.execute('SELECT * FROM frames ORDER BY token,pool,rec,id'),lambda r:(r['token'],r['pool'])):
        ss=list(group); meta=anchors.get(ss[0]['id'])
        if meta is None: continue
        seq=causal(ss); fs=seq[:8]
        if len(fs)<8: excluded['less_than_8']+=1;continue
        span=fs[-1]['obs']-fs[0]['obs']
        if span<60 or fs[-1]['rec']-fs[0]['rec']>900 or any(b['obs']-a['rec']>120 for a,b in zip(fs,fs[1:])):
            excluded['span_or_gap']+=1;continue
        if len({s['source'] for s in fs})!=1: excluded['provider_change']+=1;continue
        f,state=shape(fs)
        entry=seq[8] if len(seq)>8 and seq[8]['obs']-fs[-1]['rec']<=120 else None
        rows.append(dict(token=meta['token'],pool=meta['pool'],day=meta['day'],chain=meta['chain'],provider=meta['source'],
            anchor_id=meta['anchor_id'],age=meta['age'],anchor_liq=meta['liq'],feature_ids=[s['id'] for s in fs],
            feature_rec=fs[-1]['rec'],feature_liq=fs[-1]['liq'],span=span,state=state,features=f,
            entry_id=entry['id'] if entry else None,activity_audited=False,
            combined_vault_state='UNKNOWN_NO_FROZEN_JOIN',
            outcomes={str(h):outcome(entry,seq[9:],h) for h in (900,3600,14400)} if entry else {}))
    c.close();audit=raw_activity(rows);vault=vault_audit(rows)
    medians={k:med([r['features'][k] for r in rows if r['day']==DAYS[0] and r['features'].get(k) is not None])
             for k in sorted({k for r in rows for k in r['features']})}
    summaries={};bins={};strata={}
    for day in DAYS:
        rr=[r for r in rows if r['day']==day]
        summaries[day]={'all':stats(rr),**{s:stats([r for r in rr if r['state']==s]) for s in ('NORMAL','LINEAR_RATCHET','STAIRCASE_RATCHET')}}
        bins[day]={k:{label:stats([r for r in rr if r['features'].get(k) is not None and (r['features'][k]>=v)==high])
                     for label,high in [('low',False),('high',True)]} for k,v in medians.items() if v is not None}
        for chain,provider in sorted({(r['chain'],r['provider']) for r in rr}):
            sr=[r for r in rr if (r['chain'],r['provider'])==(chain,provider)]
            strata[f'{day}:{chain}:{provider}']={s:stats([r for r in sr if r['state']==s]) for s in ('NORMAL','LINEAR_RATCHET','STAIRCASE_RATCHET')}
    result=dict(frozen=u['meta'],anchor_denominator=len(anchors),excluded=excluded,feature_episodes=len(rows),
        median_splits_sep7=medians,summary=summaries,bins=bins,strata=strata,raw_audit=audit,vault_audit=vault,seconds=time.monotonic()-started,
        limitations=['No swap-level breadth/concentration or authenticated vault state in frozen input.',
                    'No below-floor rows: writeoff and true unseen first hit remain UNKNOWN.',
                    'Shape availability selects dense paths; no all-market precision or realized-PnL claim.'])
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'rows.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
    (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('anchor_denominator','excluded','feature_episodes','raw_audit','vault_audit','seconds')},ensure_ascii=False))


if __name__=='__main__': main()
