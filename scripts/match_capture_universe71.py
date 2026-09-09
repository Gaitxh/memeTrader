"""As-of launch attribution, outcome-blind control distance and actual BUY capture."""
import json,sqlite3,collections,math,statistics
from pathlib import Path
from datetime import datetime
R=Path(__file__).resolve().parents[1];O=R/'data/research/universe71';u=json.loads((O/'universe.json').read_text(encoding='utf-8'));rows=[r for r in u['rows'] if r['original']];cut=u['meta']['source_cutoff'];ts=lambda s:datetime.fromisoformat(s.replace('Z','+00:00')).timestamp();c=sqlite3.connect('file:'+str(R/'data/memetrader_forward_20260830_r6.sqlite3').replace('\\','/')+'?mode=ro',uri=True)
launches=collections.defaultdict(list)
for token,provider,at in c.execute('select token_id,launch_provider,recorded_at from token_launch_facts where recorded_at<=?',(cut,)):
 launches[token].append((ts(at),provider))
for token,surface,at in c.execute("select e.token_id,r.surface,e.recorded_at from token_discovery_rounds r join token_discovery_exposures e on e.round_id=r.id where r.provider='native-launch' and e.recorded_at<=?",(cut,)):
 if at:launches[token].append((ts(at),surface))
for r in rows:
 known=[v for t,v in launches[r['token']] if t<=r['anchor_rec']];r['launchpad']=next(iter(set(known))) if len(set(known))==1 else 'AMBIGUOUS' if known else 'UNKNOWN'
positions=collections.defaultdict(list)
for token,arm,opened,pool in c.execute("select p.token_id,p.arm_id,p.opened_at,json_extract(s.raw_json,'$.pair.pairAddress') from chain_meme_trader_positions p join token_snapshots s on s.id=p.entry_snapshot_id where p.opened_at<=?",(cut,)):
 positions[token].append((ts(opened),arm,pool if token.startswith('solana:') else str(pool or '').lower()))
for xs in positions.values():xs.sort()
by=collections.defaultdict(list)
def ageband(age):return 'UNKNOWN' if age is None or age<0 else 0 if age<180 else 1 if age<900 else 2 if age<3600 else 3
def key(r):return r['day'],r['chain'],r['source'],r['launchpad'],r['quote'],ageband(r['age'])
for r in rows:by[key(r)].append(r)
tails=[r for r in rows if r['day']!='2026-09-09' and (r['outcomes'].get('21600',{}).get('mfe') or 0)>=1];matches=[];capture=[]
for r in tails:
 candidates=[x for x in by[key(r)] if x['token']!=r['token'] and .5*r['liq']<=x['liq']<=2*r['liq']]
 candidates.sort(key=lambda x:(abs((x['age'] or 0)-(r['age'] or 0)),abs(math.log(x['liq']/r['liq'])),abs(x['anchor_rec']-r['anchor_rec']),x['token']))
 matches.append({'token':r['token'],'pool':r['pool'],'key':key(r),'strict_known_identity':r['launchpad'] not in ('UNKNOWN','AMBIGUOUS') and bool(r['quote']) and ageband(r['age'])!='UNKNOWN','controls':[{'token':x['token'],'pool':x['pool'],'outcome':x['outcomes'].get('21600',{}),'has_entry':bool(x['entry_id'])} for x in candidates[:3]]})
 buys=[(t,a) for t,a,p in positions[r['token']] if p==r['pool'] and r['anchor_rec']<=t<=r['entry_rec']+21600]
 capture.append({'token':r['token'],'pool':r['pool'],'day':r['day'],'chain':r['chain'],'mfe':r['outcomes']['21600']['mfe'],'first_buy_delay':buys[0][0]-r['anchor_rec'] if buys else None,'arms_before_observed_peak':sorted({a for t,a in buys if t<=r['outcomes']['21600']['peak_observed_at']}),'arms_in_6h':sorted({a for t,a in buys})})
controls=[c for m in matches for c in m['controls']];summary={'tail_tokens':len(tails),'tail_with_buy_in6h':sum(x['first_buy_delay'] is not None for x in capture),'tail_buy_before_peak':sum(bool(x['arms_before_observed_peak']) for x in capture),'matched_cases':sum(bool(m['controls']) for m in matches),'strict_known_launchpad_quote_cases':sum(m['strict_known_identity'] and bool(m['controls']) for m in matches),'control_rows_reusable_not_independent':len(controls),'control_tail100':sum((x['outcome'].get('mfe') or 0)>=1 for x in controls),'control_observed_loss50':sum(x['outcome'].get('loss50') is True for x in controls),'control_missing_path':sum(x['outcome'].get('mfe') is None for x in controls),'control_endpoint_known':sum(x['outcome'].get('endpoint_id') is not None for x in controls),'launchpad_mix':dict(collections.Counter(r['launchpad'] for r in rows))}
(O/'matched_capture.json').write_text(json.dumps({'summary':summary,'matches':matches,'capture':capture},indent=2),encoding='utf-8');print(json.dumps(summary))
