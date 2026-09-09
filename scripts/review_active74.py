"""Read-only current effective active-arm economics and dependencies."""
import json,sqlite3,statistics,math
from pathlib import Path
from datetime import datetime,timezone
from memetrader.store import Store
R=Path(__file__).resolve().parents[1];O=R/'data/research/consolidation74';O.mkdir(exist_ok=True)
c=sqlite3.connect((R/'data/memetrader_forward_20260830_r6.sqlite3').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
v='chain-meme-trader/funding-20260906-v002-final-1000';c.execute('BEGIN')
raw=c.execute('select definition_json from chain_meme_trader_v6_registrations where definition_version=?',(v,)).fetchone()[0]
policies=Store.chain_meme_trader_effective_definition_from_connection(c,v,raw)['policies'];out=[]
for p in policies:
 if p.get('entry_paused'):continue
 a=p['arm_id'];positions=[dict(r) for r in c.execute('select * from chain_meme_trader_positions where definition_version=? and arm_id=?',(v,a))];ts=[r for r in positions if r['status'] in ('closed','written_off')];pn=sorted(r['realized_pnl_usd'] for r in ts)
 trades=c.execute('select sum(realized_pnl_usd) from chain_meme_trader_trades where definition_version=? and arm_id=?',(v,a)).fetchone()[0] or 0
 assert math.isclose(trades,sum(r['realized_pnl_usd'] or 0 for r in positions),abs_tol=1e-7)
 out.append(dict(arm=a,n=len(ts),pnl=sum(pn),median=statistics.median(pn) if pn else None,best=max(pn) if pn else None,worst=min(pn) if pn else None,top1_removed=sum(pn[:-1]),top3_removed=sum(pn[:-3]),open=sum(r['status']=='open' for r in positions),policy=p,
                 contamination={t:c.execute('select count(*) from '+t+' where definition_version=? and arm_id=?',(v,a)).fetchone()[0] for t in ('chain_meme_trader_accounting_contaminations','chain_meme_trader_position_voids')}))
c.rollback();result=dict(cutoff=datetime.now(timezone.utc).isoformat(),arms=out,policies=policies)
(O/'active.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
for r in out:print(json.dumps({k:v for k,v in r.items() if k!='policy'}))
