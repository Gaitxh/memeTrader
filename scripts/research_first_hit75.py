"""Frozen disk-only sampled first-hit order. No production connection or writes."""
import collections,itertools,json,sqlite3,statistics
from pathlib import Path

R=Path(__file__).resolve().parents[1];D=R/'data/research/universe71'
GAP=120;H=3600

def walk(entry, frames):
    hits={k:None for k in ('stop20','up30','up100')};prev=entry
    gap=False;pending=None;exit_result=None;peak=0;last=entry['rec']
    for s in frames:
        if s['obs']<=prev['rec']:continue
        if s['obs']>entry['rec']+H+GAP:break
        delta=s['obs']-prev['rec'];gap=gap or delta>GAP
        ret=s['price']*.96/(entry['price']*1.04)-1
        age=s['obs']-entry['rec']
        if age<=H:
            for k,yes in [('stop20',ret<=-.2),('up30',ret>=.3),('up100',ret>=1)]:
                if yes and hits[k] is None:hits[k]=dict(id=s['id'],seconds=age,net=ret,gap_before=gap)
        if exit_result is None:
            if pending is not None:
                exit_result=dict(reason=pending['reason'],signal_id=pending['id'],fill_id=s['id'],net=ret,
                                 status='UNKNOWN_GAP' if gap or delta>GAP else 'SAMPLED_NEXT_FRAME')
            else:
                peak=max(peak,ret)
                reason='hard_stop' if ret<=-.2 else 'trailing' if peak>=.3 and (1+ret)/(1+peak)<=.85 else 'max_hold' if age>=900 else None
                if reason:pending=dict(reason=reason,id=s['id'])
        prev=s;last=s['rec']
    def order(k):
        a,b=hits[k],hits['stop20']
        first=min([x for x in (a,b) if x],key=lambda x:x['seconds'],default=None)
        if first is None:return 'UNKNOWN_NO_HIT'
        if first['gap_before']:return 'UNKNOWN_GAP'
        return 'POSITIVE_FIRST' if first is a else 'STOP_FIRST'
    return dict(hits=hits,order30=order('up30'),order100=order('up100'),
                sampled_order30=('POSITIVE_FIRST' if hits['up30'] and (not hits['stop20'] or hits['up30']['seconds']<hits['stop20']['seconds']) else 'STOP_FIRST' if hits['stop20'] else 'UNKNOWN'),
                sampled_order100=('POSITIVE_FIRST' if hits['up100'] and (not hits['stop20'] or hits['up100']['seconds']<hits['stop20']['seconds']) else 'STOP_FIRST' if hits['stop20'] else 'UNKNOWN'),
                replay=exit_result or dict(status='UNKNOWN_MISSING_NEXT_OR_HORIZON'),
                floor_failure='UNKNOWN_NOT_RETAINED_IN_NORMALIZED_INPUT',last_recorded=last)

def summary(rows):
    n=len(rows);out=dict(n=n,entries=sum(r['entry_id'] is not None for r in rows))
    for label in ('order30','order100','sampled_order30','sampled_order100'):
        counts=collections.Counter(r.get(label,'UNKNOWN_NO_ENTRY') for r in rows)
        known=counts['POSITIVE_FIRST']+counts['STOP_FIRST']
        out[label]=dict(counts=counts,positive_per_all=counts['POSITIVE_FIRST']/n if n else None,
                        positive_per_known=counts['POSITIVE_FIRST']/known if known else None)
    out['first_hit_times']={}
    for k in ('stop20','up30','up100'):
        ts=sorted(r['hits'][k]['seconds'] for r in rows if r.get('hits',{}).get(k))
        out['first_hit_times'][k]=dict(n=len(ts),median=statistics.median(ts) if ts else None,p90=ts[int((len(ts)-1)*.9)] if ts else None)
    fills=[r['replay']['net'] for r in rows if r.get('replay',{}).get('status')=='SAMPLED_NEXT_FRAME']
    fills.sort()
    out['replay']=dict(n=len(fills),mean=statistics.mean(fills) if fills else None,median=statistics.median(fills) if fills else None,
                      max=max(fills) if fills else None,top1_removed_sum=sum(fills[:-1]),top3_removed_sum=sum(fills[:-3]),
                      caveat='selected coverage subset; floor failures unavailable; no all-universe PnL estimate')
    return out

def main():
    u=json.loads((D/'universe.json').read_text(encoding='utf-8'));assert u['meta']['source_frontier']==2194123
    anchors={r['anchor_id']:r for r in u['rows'] if r['original'] and r['day'] in ('2026-09-07','2026-09-08')}
    med=json.loads((R/'data/research/features74/result.json').read_text(encoding='utf-8'))['train_medians_fixed_sep7']
    c=sqlite3.connect((D/'normalized_identity.sqlite3').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    rows=[];multi=[]
    for key,group in itertools.groupby(c.execute('select * from frames order by token,pool,rec,id'),lambda s:(s['token'],s['pool'])):
        ss=list(group);a=ss[0];m=anchors.get(a['id'])
        if m is None:continue
        e=next((s for s in ss if s['obs']>a['rec']),None)
        common=dict(day=m['day'],chain=m['chain'],provider=m['source'],token=key[0],pool=key[1],anchor_id=a['id'])
        row=dict(**common,entry_id=e['id'] if e else None,features={k:m['features'][k] for k in ('activity_rate','buy_share','turnover')})
        if e:row.update(walk(e,ss))
        rows.append(row)
        third=next((s for s in ss if e and s['obs']>e['rec']),None)
        if third is None or len({a['source'],e['source'],third['source']})!=1:continue
        # Third-frame features may never classify the earlier second-frame entry.
        fourth=next((s for s in ss if s['obs']>third['rec']),None)
        v=(a['volume']+e['volume']+third['volume'])/3 if all(s['volume'] is not None for s in (a,e,third)) else None
        trades=third['buys']+third['sells'] if third['buys'] is not None and third['sells'] is not None else None
        disp=third['price']/a['price']-1;dist=abs(e['price']-a['price'])+abs(third['price']-e['price'])
        f=dict(volume_to_liquidity=v/third['liq'] if v is not None else None,
               displacement_per_reported_notional_proxy=disp/v if v else None,
               reported_activity_efficiency_proxy=disp/(v/third['liq']) if v else None,
               buy_count_imbalance=(third['buys']-third['sells'])/trades if trades else None,
               liquidity_growth=third['liq']/a['liq']-1,liquidity_retention=min(e['liq'],third['liq'])/a['liq'],
               path_efficiency=abs(third['price']-a['price'])/dist if dist else None,
               second_third_acceleration_per_second=(third['price']/e['price']-1)/(third['rec']-e['rec'])-(e['price']/a['price']-1)/(e['rec']-a['rec']))
        r=dict(**common,feature_id=third['id'],entry_id=fourth['id'] if fourth else None,features=f)
        if fourth:
            assert fourth['obs']>third['rec'];r.update(walk(fourth,ss))
        multi.append(r)
    c.close()
    out=dict(cutoff=u['meta'],gap_seconds=GAP,horizon_seconds=H,
             baseline={d:summary([r for r in rows if r['day']==d]) for d in ('2026-09-07','2026-09-08')},
             strata={str(k):summary([r for r in rows if (r['day'],r['chain'],r['provider'])==k]) for k in sorted({(r['day'],r['chain'],r['provider']) for r in rows})},
             multiframe={d:summary([r for r in multi if r['day']==d]) for d in ('2026-09-07','2026-09-08')},bins={},bin_strata={})
    for family,data,thresholds in [('anchor',rows,{k:u['medians'][k] for k in ('activity_rate','buy_share','turnover')}),('third',multi,med)]:
        for day in ('2026-09-07','2026-09-08'):
            for feature,threshold in thresholds.items():
                for high in (False,True):
                    xs=[r for r in data if r['day']==day and r['features'].get(feature) is not None and (r['features'][feature]>=threshold)==high]
                    out['bins'][f'{family}:{day}:{feature}:{high}']=summary(xs)
                    for chain,provider in sorted({(r['chain'],r['provider']) for r in xs}):
                        out['bin_strata'][f'{family}:{day}:{feature}:{high}:{chain}:{provider}']=summary([r for r in xs if r['chain']==chain and r['provider']==provider])
    path=R/'data/research/first_hit75';path.mkdir(exist_ok=True)
    (path/'result.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    (path/'rows.json').write_text(json.dumps(dict(baseline=rows,multiframe=multi)),encoding='utf-8')
    print(json.dumps(dict(baseline=out['baseline'],multiframe=out['multiframe'])))

if __name__=='__main__':main()
