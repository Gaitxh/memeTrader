"""Read-only, frozen matching and strict observed-path research; no trading writes."""
import json, math, sqlite3, argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/user_righttail_cases_20260908"
DB = ROOT / "data/memetrader_forward_20260830_r6.sqlite3"
def dt(s): return datetime.fromisoformat(s.replace("Z", "+00:00"))
def family(s): return s.removeprefix("strategy-observer:")
def band(age):
    for upper in (180, 300, 900, 3600, 21600, 86400):
        if age < upper: return upper
    return "older"
def canonical(chain, p): return p if chain == "solana" else p.lower()
FIELDS = """id,token_id,observed_at,ingested_at,recorded_at,provider,price_usd,liquidity_usd,
json_extract(raw_json,'$.pair.pairAddress') AS pool,
json_extract(raw_json,'$.pair.pairCreatedAt') AS created,
json_extract(raw_json,'$.pair.txns.m5.buys') AS buys,
json_extract(raw_json,'$.pair.txns.m5.sells') AS sells,
json_extract(raw_json,'$.pair.volume.m5') AS volume"""
def frame(row):
    r = dict(row)
    try:
        o,i,d = (dt(r[k]) for k in ("observed_at","ingested_at","recorded_at"))
        if not o <= i <= d or not r["pool"] or not r["price_usd"] or r["price_usd"] <= 0 or (r["liquidity_usd"] or 0) < 1000: return None
        age = o.timestamp() - float(r["created"])/1000 if r["created"] is not None else None
        if age is not None and age < 0: return None
        chain = r["token_id"].split(":")[0]
        r.update(chain=chain,pool=canonical(chain,r["pool"]),age=age,date=o.date().isoformat(),family=family(r["provider"]))
        r["trades"] = None if r["buys"] is None or r["sells"] is None else r["buys"]+r["sells"]
        r["buy_share"] = r["buys"]/r["trades"] if r["trades"] else None
        r["volume_liquidity"] = r["volume"]/r["liquidity_usd"] if r["volume"] is not None else None
        r["activity_presence"] = {k: "MISSING" if r[k] is None else ("ZERO" if r[k]==0 else "PRESENT") for k in ("buys","sells","volume")}
        return r
    except (ValueError,TypeError,AttributeError): return None

def main():
    c=sqlite3.connect(f"file:{DB.as_posix()}?mode=ro",uri=True);c.row_factory=sqlite3.Row
    parser=argparse.ArgumentParser()
    parser.add_argument('--cutoff-id', type=int)
    args=parser.parse_args()
    cutoff=c.execute("SELECT id,recorded_at FROM token_snapshots WHERE id=?",(args.cutoff_id,)).fetchone() if args.cutoff_id else c.execute("SELECT id,recorded_at FROM token_snapshots ORDER BY id DESC LIMIT 1").fetchone()
    cases=json.loads((OUT/'independent_casebook_rows_20260909.json').read_text(encoding='utf-8-sig'))['cases']
    anchors={}; scanned=0
    # Iterate fixed PK chunks, releasing each read transaction; first valid exact-pool
    # frame is determined across all prior rows, not only a recent ID neighborhood.
    for lo in range(0,cutoff['id']+1,5000):
        rows=c.execute(f"SELECT {FIELDS} FROM token_snapshots WHERE id>? AND id<=?",(lo,min(lo+5000,cutoff['id']))).fetchall()
        for row in rows:
            f=frame(row)
            if f:
                key=(f['token_id'],f['pool']); old=anchors.get(key)
                if old is None or (dt(f['recorded_at']),f['id']) < (dt(old['recorded_at']),old['id']): anchors[key]=f
        scanned+=len(rows)
    excluded={x['token_id'] for x in cases}
    def path(a):
        deadline=dt(a['recorded_at'])+timedelta(hours=6)
        rows=c.execute(f"SELECT {FIELDS} FROM token_snapshots WHERE token_id=? AND observed_at>? AND observed_at<=? AND id<=? ORDER BY recorded_at,id",(a['token_id'],a['observed_at'],deadline.isoformat().replace('+00:00','Z'),cutoff['id'])).fetchall()
        accepted=[];prior=a
        for row in rows:
            f=frame(row)
            if not f or f['pool']!=a['pool'] or dt(f['recorded_at'])>deadline or dt(f['observed_at'])<=dt(prior['recorded_at']):continue
            accepted.append(f);prior=f
        entry=accepted[0] if accepted else None
        future=accepted[1:]
        nets=[(x['price_usd']*.96/(entry['price_usd']*1.04)-1) for x in future] if entry else []
        # No frame near endpoint means UNKNOWN, never imputed death/zero.
        covered=bool(future and dt(future[-1]['observed_at'])>=deadline-timedelta(minutes=5))
        return {'strict_next':entry,'future_ids':[x['id'] for x in future], 'future_count':len(future),'endpoint_covered':covered,
            'righttail100':True if nets and max(nets)>=1 else (False if covered else 'UNKNOWN'),
            'observed_crash50':True if nets and min(nets)<=-.5 else (False if covered else 'UNKNOWN'),
            'end_loss50':nets[-1]<=-.5 if covered else 'UNKNOWN',
            'max_net':max(nets) if nets else None,'last_net':nets[-1] if nets else None,
            'peak_at':future[nets.index(max(nets))]['observed_at'] if nets else None}
    results=[]
    for case in cases:
        token=case['token_id']; expected=case.get('anchor_pair'); aa=[a for (t,p),a in anchors.items() if t==token and (not expected or p==canonical(token.split(':')[0],expected))]
        a=min(aa,key=lambda f:(dt(f['recorded_at']),f['id'])) if aa else None
        selected=[]
        if a and a['age'] is not None:
            pool=[]
            for b in anchors.values():
                if b['token_id'] in excluded or b['date']!=a['date'] or b['chain']!=a['chain'] or b['family']!=a['family'] or b['age'] is None or band(b['age'])!=band(a['age']):continue
                if not .5<=b['liquidity_usd']/a['liquidity_usd']<=2 or dt(b['recorded_at'])>dt(a['recorded_at']):continue
                score=(abs(b['age']-a['age'])/max(60,a['age'])+abs(math.log2(b['liquidity_usd']/a['liquidity_usd']))+abs((dt(b['recorded_at'])-dt(a['recorded_at'])).total_seconds())/86400)
                pool.append((score,b['id'],b))
            used=set()
            for _,_,b in sorted(pool):
                if b['token_id'] in used:continue
                selected.append(b);used.add(b['token_id'])
                if len(selected)==5:break
        positions=[dict(r) for r in c.execute("SELECT arm_id,shadow_cohort_id,entry_snapshot_id,opened_at,closed_at,status,close_reason,realized_pnl_usd,stake_usd,source_entry_fill_id FROM chain_meme_trader_positions WHERE definition_version=? AND token_id=? ORDER BY opened_at",('chain-meme-trader/funding-20260906-v002-final-1000',token))]
        for position in positions:
            row=c.execute("SELECT json_extract(raw_json,'$.pair.pairAddress') FROM token_snapshots WHERE id=?",(position['entry_snapshot_id'],)).fetchone()
            ep=canonical(token.split(':')[0],row[0]) if row and row[0] else None
            position['entry_pool']=ep
            position['entry_pool_matches_anchor']=ep==a['pool'] if ep and a else None
        ap=path(a) if a else None
        attribution={'positions':positions,'first_buy':positions[0]['opened_at'] if positions else None,'anchor_to_first_buy_s':(dt(positions[0]['opened_at'])-dt(a['recorded_at'])).total_seconds() if positions and a else None,'positions_closed_before_observed_peak':sum(bool(r['closed_at'] and ap and ap['peak_at'] and dt(r['closed_at'])<dt(ap['peak_at'])) for r in positions)}
        results.append({'token_id':token,'symbol':case['symbol'],'anchor':a,'status':'MATCHED' if selected else 'UNMATCHED','path':ap,'controls':[{'anchor':b,'path':path(b)} for b in selected],'actual_system':attribution})
    output={'cutoff':dict(cutoff),'scanned_rows':scanned,'pool_anchor_count':len(anchors),'age_bands_upper_seconds':[180,300,900,3600,21600,86400,'older'],'liquidity_ratio':[.5,2],'horizon_hours':6,'endpoint_tolerance_minutes':5,'results':results}
    (OUT/'matched_corrected47.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps({'cutoff':dict(cutoff),'matched':sum(x['status']=='MATCHED' for x in results),'controls':sum(len(x['controls']) for x in results),'cases':[(x['symbol'],len(x['controls']),x['path']['righttail100'] if x['path'] else 'UNKNOWN') for x in results]}))
if __name__=='__main__':main()

