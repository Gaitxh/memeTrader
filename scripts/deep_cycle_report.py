"""Bounded, read-only current/archive deep-cycle report (no Store/runtime import)."""
from __future__ import annotations
import argparse, json, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def quantile(xs,p):
    xs=sorted(x for x in xs if x is not None)
    return None if not xs else xs[min(len(xs)-1,int((len(xs)-1)*p))]
def paper_family(arm_id): return 'native_paper' if 'native' in str(arm_id).lower() else 'generic_paper'
def generation_delta(now,old):
    if not old or now.get('client_generation') is None or now.get('client_generation')!=old.get('client_generation'): return {'unknown':'no_previous_report_or_generation_reset'}
    return {k:now[k]-old[k] for k in ('request_cancellations','low_priority_deferred','client_generation_retirements') if isinstance(now.get(k),(int,float)) and isinstance(old.get(k),(int,float))}
def connect(path):
    c=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=30); c.row_factory=sqlite3.Row
    deadline=time.monotonic()+30
    c.execute("PRAGMA query_only=1"); c.set_progress_handler(lambda: 1 if time.monotonic()>=deadline else 0,10_000); return c
def exists(c,t): return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone() is not None
def rows(c,q,a=()): return [dict(x) for x in c.execute(q,a)]
def one(c,q,a=()):
    r=c.execute(q,a).fetchone(); return dict(r) if r else {}
def _summary(c,path,minutes,historical=False):
    cut=f'-{minutes} minute'; clock="datetime('now')" if not historical else "(SELECT MAX(COALESCE(recorded_at,observed_at)) FROM token_discovery_exposures)"; out={'path':str(path),'available':True,'truncated':True,'window_minutes':minutes,'period_basis':'current_wall_clock' if not historical else 'archive_latest_discovery_clock'}
    needed=['token_discovery_exposures','token_snapshots','chain_meme_trader_v6_entry_evaluations']
    if not all(exists(c,t) for t in needed): return {**out,'available':False,'reason':'required_tables_missing'}
    floors={t:max(0,c.execute(f'SELECT COALESCE(MAX(id),0)-200000 FROM {t}').fetchone()[0]) for t in needed}
    out['frontiers']=floors
    out['discovery']=rows(c,f"SELECT chain,COUNT(DISTINCT token_id) tokens,COUNT(*) rows FROM token_discovery_exposures WHERE id>? AND first_local_discovery=1 AND julianday(COALESCE(recorded_at,observed_at))>=julianday({clock},?) GROUP BY chain",(floors['token_discovery_exposures'],cut))
    # Canonical token join; pool/opportunity association is separately stated below.
    q=f"""WITH d AS (SELECT token_id,MIN(COALESCE(recorded_at,observed_at)) t FROM token_discovery_exposures WHERE id>? AND first_local_discovery=1 AND julianday(COALESCE(recorded_at,observed_at))>=julianday({clock},?) GROUP BY token_id), s AS (SELECT token_id,MIN(ingested_at) t FROM token_snapshots WHERE id>? AND ingested_at IS NOT NULL GROUP BY token_id), e AS (SELECT token_id,MIN(evaluated_at) t FROM chain_meme_trader_v6_entry_evaluations WHERE id>? GROUP BY token_id) SELECT d.token_id,(julianday(s.t)-julianday(d.t))*86400 ds,(julianday(e.t)-julianday(d.t))*86400 de FROM d LEFT JOIN s USING(token_id) LEFT JOIN e USING(token_id)"""
    matched=rows(c,q,(floors['token_discovery_exposures'],cut,floors['token_snapshots'],floors['chain_meme_trader_v6_entry_evaluations']))
    funnel=[]
    for ch in ('solana','bsc','robinhood'):
        a=[x for x in matched if x['token_id'].startswith(ch+':')]; ds=[x['ds'] for x in a if x['ds'] is not None and x['ds']>=0]; de=[x['de'] for x in a if x['de'] is not None and x['de']>=0]
        funnel.append({'chain':ch,'discovered_tokens':len(a),'snapshot_ingested_tokens':sum(x['ds'] is not None for x in a),'evaluated_tokens':sum(x['de'] is not None for x in a),'latency_seconds':{'discovery_to_snapshot_ingested':{k:quantile(ds,p) for k,p in [('p50',.5),('p90',.9),('p99',.99)]},'discovery_to_evaluation':{k:quantile(de,p) for k,p in [('p50',.5),('p90',.9),('p99',.99)]}},'negative_or_unavailable_clock_rows':sum(x['ds'] is not None and x['ds']<0 for x in a)})
    out['matched_token_funnel']=funnel
    out['v6_observer_labels']=rows(c,f"SELECT reason,status,COUNT(*) rows,COUNT(DISTINCT token_id) tokens FROM chain_meme_trader_v6_entry_evaluations WHERE id>? AND julianday(evaluated_at)>=julianday({clock},?) AND reason IN ('pattern_observation','cohort_observation') GROUP BY reason,status",(floors['chain_meme_trader_v6_entry_evaluations'],cut))
    out['genuine_evaluation_rejects']=rows(c,f"SELECT reason,COUNT(*) rows,COUNT(DISTINCT token_id) tokens FROM chain_meme_trader_v6_entry_evaluations WHERE id>? AND julianday(evaluated_at)>=julianday({clock},?) AND status='rejected' AND reason NOT IN ('pattern_observation','cohort_observation') GROUP BY reason ORDER BY rows DESC LIMIT 20",(floors['chain_meme_trader_v6_entry_evaluations'],cut))
    out['association_limits']={'unique_token':'measured','unique_pool':'unknown_from_discovery_exposure','unique_cohort':'unknown_unless_v6_cohort_joined','reason':'discovery exposures do not store pair address/cohort id'}
    if exists(c,'chain_meme_trader_v6_cohorts'):
      out['cohorts']=one(c,f"SELECT COUNT(DISTINCT token_id) tokens,COUNT(DISTINCT pair_address) pools,COUNT(*) cohorts FROM chain_meme_trader_v6_cohorts WHERE julianday(decided_at)>=julianday({clock},?)",(cut,))
    for table,key,col in [('chain_meme_trader_entry_decisions','decisions','decided_at'),('chain_meme_trader_positions','positions','opened_at')]:
      if exists(c,table): out[key]=one(c,f"SELECT COUNT(DISTINCT token_id) tokens,COUNT(DISTINCT arm_id) arms,COUNT(*) rows FROM {table} WHERE julianday({col})>=julianday({clock},?)",(cut,))
    if exists(c,'token_detail_hydration'): out['hydration']=rows(c,f"SELECT chain,status,COUNT(*) rows,MAX(attempts) max_attempts,MAX(0,MAX((julianday({clock})-julianday(enqueued_at))*86400)) oldest_age_seconds FROM token_detail_hydration WHERE status IN ('pending','error') GROUP BY chain,status")
    if exists(c,'chain_meme_trader_positions'): out['pnl']=rows(c,f"SELECT CASE WHEN arm_id LIKE '%native%' OR arm_id='pump_native_absorption_fast_v1' THEN 'native_paper' ELSE 'generic_paper' END family,COUNT(*) positions,ROUND(SUM(realized_pnl_usd),2) known_realized_pnl,ROUND(SUM(stake_usd),2) deployed_stake_not_account_capital FROM chain_meme_trader_positions WHERE julianday(COALESCE(closed_at,opened_at))>=julianday({clock},?) GROUP BY family",(cut,))
    if exists(c,'chain_meme_trader_v6_registrations'):
      reg=c.execute("SELECT definition_json,code_registered_at FROM chain_meme_trader_v6_registrations ORDER BY code_registered_at DESC LIMIT 1").fetchone()
      try:
       inv=(json.loads(reg['definition_json']).get('policies') or []) if reg else []
       out['policies_baseline']={'policy_inventory_count':len(inv),'latest_registered_at':reg['code_registered_at'] if reg else None,'control_source':'definition_json.policies'}
      except (TypeError,ValueError): out['policies_baseline']={'unknown':'malformed_definition_json'}
    if exists(c,'chain_meme_trader_policy_additions'):
      out['policies_additions']=one(c,"SELECT COUNT(*) rows,COUNT(DISTINCT arm_id) arms FROM chain_meme_trader_policy_additions")
    if exists(c,'kv'):
      for key in ('runtime-loaded-manifest','forward-review151','cohort-flow:v1'):
       item=c.execute('SELECT value_json,updated_at FROM kv WHERE key=?',(key,)).fetchone()
       if item:
        value=json.loads(item['value_json'])
        if key=='cohort-flow:v1':
         value={k:value.get(k) for k in ('counts','signal_opportunities','unit','scope','started_at','unlinked_receipts')}
        out[key]={'updated_at':item['updated_at'],'value':value}
      control_rows=rows(c,"SELECT key,value_json,updated_at FROM kv WHERE key LIKE 'chain-meme-account-convergence/v1:%' OR key LIKE 'chain-meme-account-loss-retirement/v1:%' ORDER BY updated_at")
      merged={}
      for item in control_rows:
       try: merged.update(json.loads(item['value_json']).get('arms') or {})
       except (TypeError,ValueError): pass
      states={}
      for arm in merged.values(): states[arm.get('state','UNKNOWN')]=states.get(arm.get('state','UNKNOWN'),0)+1
      out['lifecycle_controls']={'source_keys':[x['key'] for x in control_rows],'updated_at':control_rows[-1]['updated_at'] if control_rows else None,'states':states,'merged_arms':len(merged)}
    if exists(c,'system_error_cases'):
      out['error_supervision']=rows(c,"SELECT id,component,error_type,status,occurrence_count,last_seen_at FROM system_error_cases WHERE status IN ('new','in_progress') ORDER BY last_seen_at DESC LIMIT 100")
    if exists(c,'runtime_timing_latest'):
      r=c.execute('SELECT recorded_at,payload_json FROM runtime_timing_latest ORDER BY id DESC LIMIT 1').fetchone()
      try:
       payload=json.loads(r['payload_json']) if r else {}
       out['api_performance']={'recorded_at':r['recorded_at'],'dex_http_capacity':payload.get('dex_http_capacity'),'shared_batch':payload.get('shared_batch_coverage'),'post_exit151':payload.get('post_exit151')} if r else None
       out['runtime_timing_compact']={k:(payload.get('components') or {}).get(k) for k in ('alpha149_features','chain_meme_entry_batch','chain_meme_cohort_observer','chain_meme_market_marks','held_fetch','held_apply_exit')}
       out['passive_queue']=payload.get('passive_queue') or {'unknown':'missing'}; out['held_retrieval']=payload.get('held_retrieval') or {'unknown':'missing'}
      except (ValueError,TypeError): out['api_performance']={'unknown':'malformed_payload'}
    if exists(c,'chain_meme_trader_positions'):
      out['all_period_strategy_economics']=rows(c,"SELECT arm_id,COUNT(*) positions,SUM(realized_pnl_usd IS NOT NULL) realized_known_positions,ROUND(SUM(realized_pnl_usd),2) realized_pnl_known_only,ROUND(SUM(COALESCE(stake_usd,0)),2) stake FROM chain_meme_trader_positions GROUP BY arm_id ORDER BY positions DESC LIMIT 1000")
      out['terminal_economics_by_arm']=rows(c,"SELECT definition_version,arm_id,COUNT(*) terminal_positions,COUNT(DISTINCT token_id) independent_tokens,SUM(status='written_off') writeoffs,SUM(realized_pnl_usd>0) winners,AVG(realized_pnl_usd) mean_net_usd,SUM(realized_pnl_usd) total_net_usd,SUM(CASE WHEN realized_pnl_usd>0 THEN realized_pnl_usd ELSE 0 END) gross_wins_usd,-SUM(CASE WHEN realized_pnl_usd<0 THEN realized_pnl_usd ELSE 0 END) gross_losses_usd,MIN(realized_pnl_usd) worst_position_net_usd,AVG((julianday(closed_at)-julianday(opened_at))*86400) mean_hold_seconds FROM chain_meme_trader_positions WHERE status IN ('closed','written_off') GROUP BY definition_version,arm_id LIMIT 1000")
      out['exit_reasons']=rows(c,"SELECT close_reason,status,COUNT(*) positions,COUNT(DISTINCT token_id) tokens,SUM(realized_pnl_usd) net_usd FROM chain_meme_trader_positions WHERE status IN ('closed','written_off') GROUP BY close_reason,status ORDER BY positions DESC LIMIT 100")
    try:
      from scripts.review_metrics151 import washout, cohort_funnel
    except ModuleNotFoundError:
      from review_metrics151 import washout, cohort_funnel
    cutoff=c.execute(f'SELECT {clock}').fetchone()[0]
    if '+' not in cutoff and not cutoff.endswith('Z'): cutoff+='Z'
    out['data_cutoff']=cutoff
    out['washout_proxy']=washout(c,cutoff)
    out['cohort_funnel']=cohort_funnel(c,cutoff,minutes)
    return out
def summary(path,minutes,historical=False):
    c=connect(path)
    try: return _summary(c,path,minutes,historical)
    finally: c.close()
def main():
 p=argparse.ArgumentParser();p.add_argument('--minutes',type=int,default=120);p.add_argument('--out-dir',default=str(ROOT/'data/reports/deep_cycle_20260913/reviews'));p.add_argument('--label',default='deep_cycle');a=p.parse_args()
 cfg=json.loads((ROOT/'config.json').read_text(encoding='utf8')); current=Path(cfg['database']); current=current if current.is_absolute() else ROOT/current
 archives=sorted((ROOT/'data/archives').glob('*/memetrader_forward.sqlite3'))
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
 previous=None
 for candidate in sorted(out.glob(a.label+'_*.json'),reverse=True):
  try: previous=json.loads(candidate.read_text(encoding='utf8')); break
  except (OSError,ValueError): pass
 report={'generated_at':datetime.now(timezone.utc).isoformat(),'current':summary(current,a.minutes),'archive':summary(archives[-1],a.minutes,True) if archives else {'available':False,'reason':'archive_not_found'},'limits':['Discovery/snapshot/evaluation tables use newest-200k-ID frontiers; cohort funnel <=2000 and exit analysis <=200 positions.','Counts across stages are not additive; source receipt does not prove all strategy signals.','Fixed-horizon rebound candidates are market observations, not executable or cost-net profitability.','No automatic parameter edits, account resets or Live promotion.']}
 nowcap=((report['current'].get('api_performance') or {}).get('dex_http_capacity') or {})
 oldcap=(((previous or {}).get('current') or {}).get('api_performance') or {}).get('dex_http_capacity') or None
 report['api_counter_delta']=generation_delta(nowcap,oldcap)
 stem=f"{a.label}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"; (out/(stem+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 f=report['current']; lines=[f"# 深度循环报告 {report['generated_at']}",'',f"窗口：{a.minutes} 分钟；所有大表为最新 200,000 ID 前沿，结果可能截断。",'', '## 匹配 Token 漏斗']
 for x in f.get('matched_token_funnel',[]): lines.append(f"- {x['chain']}: 发现 {x['discovered_tokens']}，入库快照 {x['snapshot_ingested_tokens']}，评估 {x['evaluated_tokens']}；评估延迟 p50/p90/p99={x['latency_seconds']['discovery_to_evaluation']}")
 for title,key in [('同机会入场路径','cohort_funnel'),('真实拒绝原因','genuine_evaluation_rejects'),('请求与持仓时延','runtime_timing_compact'),('队列','passive_queue'),('策略控制','lifecycle_controls'),('错误监督','error_supervision'),('成本后Paper已实现结果','pnl'),('退出原因','exit_reasons')]:
  lines += ['', '## '+title, '```json', json.dumps(f.get(key),ensure_ascii=False,indent=2), '```']
 lines += ['', '## 固定窗口退出后观察', json.dumps({k:v for k,v in f['washout_proxy'].items() if k!='samples'},ensure_ascii=False), '', '研究采样器：'+json.dumps((f.get('api_performance') or {}).get('post_exit151'),ensure_ascii=False), '', '## 真实性边界', *['- '+x for x in report['limits']], '- 无法恢复的历史发现与池/机会关联不补造；不按事后涨幅认定当时应该买入。']
 (out/(stem+'.md')).write_text('\n'.join(lines)+'\n',encoding='utf8'); print(json.dumps({'json':str(out/(stem+'.json')),'markdown':str(out/(stem+'.md'))},ensure_ascii=False))
if __name__=='__main__': main()
