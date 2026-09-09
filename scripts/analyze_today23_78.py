"""Disk-only summaries and outcome-blind fixed matching for casebook78."""
import json,collections,math
from pathlib import Path
from datetime import datetime,timezone
from research_today23_78 import O,R,ts,CUT
from research_righttail_match47 import band

def main():
 r=json.loads((O/'casebook.json').read_text(encoding='utf-8'));u=json.loads((R/'data/research/universe71/universe.json').read_text(encoding='utf-8'))
 universe=[v for v in u['rows'] if v['original']];tokens={x['identity']['token_id'] for x in r['cases']};results=[]
 for x in r['cases']:
  ident=x['identity'];a=x['episodes'][0]['anchor'] if x['episodes'] else None;ep=x['episodes'][0] if a else None
  first_local=min([ts(ident['first_seen_at'])]+[ts(d['recorded_at']) for d in x['discovery'] if d['recorded_at']])
  native=[f for f in x['launch_facts'] if a and ts(f['recorded_at'])<=a['rec']]
  provenance='Pump (local PumpPortal launch receipt)' if any(f['launch_provider']=='pumpportal' for f in native) else 'UNKNOWN'
  gates={}
  for arm in r['active_arms_at_read']:
   events=[]
   for e in x['pattern_evaluations']:
    f=json.loads(e['feature_json']);reason=f.get('outcomes',{}).get(arm)
    if reason is not None:events.append(dict(id=e['id'],snapshot=e['source_snapshot_id'],at=e['evaluated_at'],reason=reason,pool=f.get('pair_address')))
   gates[arm]=dict(first=events[0] if events else None,counts=dict(collections.Counter(e['reason'] for e in events)),actual_positions=[p for p in x['positions'] if p['arm_id']==arm],bounded_prefix=len(x['pattern_evaluations'])>=2001)
  controls=[]
  if a and a['age'] is not None:
   day=datetime.fromtimestamp(a['rec'],timezone.utc).date().isoformat();chain=ident['chain']
   def quote(q):return q if chain=='solana' else str(q or '').lower()
   eligible=[v for v in universe if v['token'] not in tokens and v['day']==day and v['chain']==chain and v['source']==a['source'] and v['age'] is not None and band(v['age'])==band(a['age']) and .5<=v['liq']/a['liq']<=2 and quote(v['quote'])==quote(a['quote']) and v['anchor_rec']<=a['rec']]
   eligible.sort(key=lambda v:(abs(v['age']-a['age']),abs(math.log(v['liq']/a['liq'])),abs(v['anchor_rec']-a['rec']),v['anchor_id']))
   seen=set()
   for v in eligible:
    if v['token'] in seen:continue
    seen.add(v['token']);controls.append({k:v[k] for k in ('token','pool','anchor_id','day','age','liq','source','quote','features','outcomes')})
    if len(controls)==3:break
  whole=[]
  if ep and ep['entry']:
   prev=ep['entry']
   for f in x['frames']:
    if f['pool']!=a['pool'] or f['obs']<=prev['rec']:continue
    if f['liq'] is not None and f['liq']>=1000:whole.append(dict(id=f['id'],observed_at=f['obs'],net=f['price']*.96/(ep['entry']['price']*1.04)-1))
    prev=f
  whole_peak=max(whole,key=lambda f:f['net']) if whole else None
  firstbuy=x['positions'][0] if x['positions'] else None
  stage='NO_VALID_FLOOR_ANCHOR' if not a else 'NO_STRICT_NEXT' if not ep['entry'] else 'NO_PATTERN_EVALUATION_RECORDED' if not x['pattern_evaluations'] else 'EVALUATED_NO_BUY' if not firstbuy else 'ACTUAL_BUY'
  results.append(dict(token=ident['token_id'],symbol=ident['symbol'],first_local=first_local,provenance_asof_anchor=provenance,provider_dex_labels_only=sorted({f['dex'] for f in x['frames'] if f['dex']}),first_stage=stage,anchor=a,entry_delay=ep['entry_delay'] if ep else None,first_hit=ep['first_hit'] if ep else None,floor_first=ep.get('floor_first') if ep else None,outcomes=ep['outcomes'] if ep else {},whole_original_pool_peak_to_cutoff=whole_peak,first_buy=firstbuy,first_buy_delay=ts(firstbuy['opened_at'])-a['rec'] if firstbuy and a else None,terminal_pnl_observed=sum(p['realized_pnl_usd'] for p in x['positions'] if p['realized_pnl_usd'] is not None),censored_positions=sum(p['cutoff_censored'] for p in x['positions']),gates=gates,controls=controls,controls_native_provenance_unverified=True))
 summary=dict(addresses=23,found=len(results),missing=r['missing'],stages=dict(collections.Counter(x['first_stage'] for x in results)),matched_cases=sum(bool(x['controls']) for x in results),control_rows=sum(len(x['controls']) for x in results),first_hit100=dict(collections.Counter(x['first_hit']['order100'] if x['first_hit'] else 'NO_ENTRY' for x in results)),parent_capture=sum(bool(x['gates']['resource_age_rate_candidate_v1']['actual_positions']) for x in results),reawakening_capture=sum(bool(x['gates']['event_reawakening_v1']['actual_positions']) for x in results),endpoint6h=sum(x['outcomes'].get('21600',{}).get('endpoint_id') is not None for x in results))
 (O/'analysis.json').write_text(json.dumps(dict(summary=summary,results=results),indent=2),encoding='utf-8')
 lines=['# Today23 strict-forward casebook78','',f'REPLY_TO: C2C-20260909-TODAY-RIGHTTAIL-23-78. Frozen cutoff {CUT}. Research only; no registration/production mutation.','', '## Summary', '',json.dumps(summary,ensure_ascii=False),'','## Method and limits','','Exact address lookup across configured BSC/Robinhood/Solana plus Ethereum/Base;21 local identities,2 unmatched in this lookup (not proof of nonexistence onchain). No address padding, name matching or whitelist. 4s SQLite query budget, bounded per-token rows; final extraction has zero query interruptions. First attempt used an unindexed address query and was cancelled by that budget, then replaced with primary-key lookups. Snapshot limit20001 was not reached. GME20 pattern evaluations reached2001; gate counts are its earliest bounded prefix, not full-period rates.','', 'All market frames verify base token/chain/exact pool and observed<=ingested<=recorded<=cutoff; raw missing activity remains null, distinct from zero. Quote/dex labels are provider descriptors, not authenticated launch provenance. Original pool means first locally valid pool, not first-ever chain pool. Alternative pools remain separate episodes, never implicit successor authorization. First buy hypothesis uses a strictly later frame after anchor recording. Future accepted states are causal;4%/4% proxy; MFE is sampled lower bound, not realized profit. 15m/60m/6h endpoints require horizon..horizon+120s. Missing endpoints remain UNKNOWN. First-hit75 uses60m and labels gaps>120s UNKNOWN; explicit below-floor states are additionally retained as floor_first, and must precede any claimed later positive path. No missing liquidity or missing frame is a death.','', 'Positions use existing actual ledger entries, current status is censored if closed after cutoff; partial realized cashflows on still-open positions are not reconstructed and total is terminal-only. Mutable token.source is not backdated to first receipt; earliest recorded discovery exposure is retained. Current active policy set is read-time, not a reconstruction of historical policy activation. Actual historical gates and BUYs establish what was observed; this is not a counterfactual claim that today’s code would buy at every old frame.','', '## Per-case original-pool path','','|Token/symbol|First missing stage|Strict-next delay s|6h sampled max net|First100 vs stop (60m)|First BUY delay s|Terminal PnL U across all old arms|','|---|---|---:|---:|---|---:|---:|']
 for x in results:
  mfe=x['outcomes'].get('21600',{}).get('mfe');order=x['first_hit']['order100'] if x['first_hit'] else 'NO_ENTRY'
  lines.append(f"|{x['symbol']} `{x['token']}`|{x['first_stage']}|{x['entry_delay']}|{mfe*100 if mfe is not None else 'UNKNOWN'}%|{order}|{x['first_buy_delay']}|{x['terminal_pnl_observed']:.6f}|")
 lines+=['','Missing exact addresses: '+', '.join(r['missing'])+'.','', '## Current survivors and actual gates','']
 for x in results:
  parent=x['gates']['resource_age_rate_candidate_v1'];rea=x['gates']['event_reawakening_v1'];lines.append(f"- {x['symbol']}: parent first={parent['first']}; parent BUYs={len(parent['actual_positions'])}; reawakening first={rea['first']}; reawakening BUYs={len(rea['actual_positions'])}.")
 lines+=['','Whole original-pool peak through cutoff is separately stored in analysis.json (whole_original_pool_peak_to_cutoff). Peaks after6h do not describe the initial6h opportunity or authorize later re-entry. Full per-arm gates, each actual entry/exit/pool/PnL, source row IDs, as-of features, native facts and all alternative-pool episodes: data/research/today23_78/casebook.json and analysis.json.','', '## Controls and earlier evidence','','Outcome-blind controls reuse the completed71 frozen dataset (cutoff04:55:14Z/frontier2194123), never rescan market winners. Fixed same date/chain/provider/age-band/liquidity0.5–2x/quote, rank age/liquidity/time, earlier available anchor only; exclude all23 cases. Up to3 controls with reuse explicit. Native provenance is not independently matched; these are provisional diagnostics, not sufficient strategy controls. Sep9 control outcomes in71 intentionally remain unevaluated. Today’s ex-post cases are not a holdout validation set.','', 'Compared with old16 strict-surface38: both show that first seen, same-token chart rise, exact-pool executable evidence and actual fill are different stages. Old16 reported14 anchors and missing strict second rows for RSTR/ROUTE/PUG/500; no claim these counts share today’s cutoff or sample distribution. Universe71 Sep8 original24748->strict entries9380->60m paths3542->endpoints153; its broad denominator already demonstrates severe sampling attrition. Today’s case study cannot estimate precision or prove a new signal against that universe.','', '## Disposition','','RESEARCH_ONLY / INSUFFICIENT_CAUSAL_COVERAGE. No1–2 strategy arms registered. Parent remains champion77; no fast replacement. Data continuity/identity supply remains first priority, but absent frames alone does not prove a local scheduler bug: no production change is justified without queue/provider/admission trace. Native provenance is only established where actual launch facts exist; Pons/Flap/Raydium labels alone do not authenticate Classic/OpenFour/PonsV2/LaunchLab. Native economics proof76 remains unresolved. No thresholds searched, no retrospective strategy mutation, no funding/reset/history rewrite/Live.']
 (R/'docs/PROJECT_CONTEXT/TODAY_RIGHTTAIL_CASEBOOK_78.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print(json.dumps(summary))
if __name__=='__main__':main()
