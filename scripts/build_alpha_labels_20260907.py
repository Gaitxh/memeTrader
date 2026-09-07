"""Build causal diagnostic labels from an immutable offline extract, no DB writes/reads.

The prediction anchor is source availability, not inferred execution decision.
This is a shared-receipt opportunity diagnostic with explicit missing coverage.
"""
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/research/alpha_diagnosis_20260907/opportunities'
DOC=ROOT/'docs/PROJECT_CONTEXT/ALPHA_DIAGNOSIS_20260907'
CUTOFF='2026-09-07T13:38:59.399800Z'
START='2026-09-07T09:19:47Z'
GAP=120


def ts(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
def iso(t): return t.isoformat().replace('+00:00','Z')
def norm(p,token): return p if token.startswith('solana:') else p.lower()
def raw(s): return json.loads(s.get('raw_json') or '{}')
def pool(s): return str((raw(s).get('pair') or {}).get('pairAddress') or '')
def valid(s):
    clocks=[s.get(k) for k in ('observed_at','ingested_at','recorded_at')]
    return bool(all(clocks) and ts(clocks[0])<=ts(clocks[1])<=ts(clocks[2])<=ts(CUTOFF)
                and (ts(clocks[2])-ts(clocks[0])).total_seconds()<=GAP and float(s.get('price_usd') or 0)>0)


def setting(epochs,at):
    rows=[x for x in epochs if ts(x['activated_at'])<=at]
    return rows[-1]['definition_fields'] if rows else None


def label(frames,fill,epochs,h):
    start=ts(fill['filled_at']); end=start+timedelta(minutes=h); limit=end+timedelta(seconds=GAP)
    ep=float(fill['execution_price_usd']); mp=float(fill['entry_market_price_usd'])
    stake=float(fill['input_usdc_raw'])/1e6
    buy_cost=setting(epochs,start)
    prefix=f'h{h}_'
    r={'coverage_status':'CENSORED','censor_seconds':0,'label_mature_at':iso(limit),
       'fixed_net_return':None,'fixed_raw_return':None,'fixed_exit_observed_at':None,
       'fixed_exit_recorded_at':None,'observed_hit':None,'first_threshold_exit_net':None,
       'within_max_net_return_upper_bound':None,'time_to_profit_seconds':None,
       'time_to_stop20_seconds':None,'time_to_known_liq_floor_seconds':None,'fixed_label_status':'UNKNOWN'}
    if not buy_cost: return {prefix+k:v for k,v in r.items()}
    # Current frozen epochs have zero fee; formula explicitly accounts for actual entry notional.
    buy_fee=float(buy_cost.get('additional_fee_usd_each_fill') or 0)
    def net(x):
        cost=setting(epochs,ts(x['recorded_at']))
        if cost is None or x.get('liquidity_usd') is None: return None
        if float(x['liquidity_usd'])<float(cost['min_pool_liquidity_usd']): return -1.0
        proceeds=stake/ep*float(x['price_usd'])*(1-float(cost['sell_slippage_bps'])/10000)
        return (max(0,proceeds-float(cost.get('additional_fee_usd_each_fill') or 0))-(stake+buy_fee))/(stake+buy_fee)
    eligible=[]; last_obs=start
    # Availability order controls execution. A later-arriving old quote cannot rewind market time.
    for x in frames:
        ob,re=ts(x['observed_at']),ts(x['recorded_at'])
        if ob<=last_obs or re>min(limit,ts(CUTOFF)) or x.get('liquidity_usd') is None: continue
        eligible.append(x); last_obs=ob
    until_gap=[]; last=start; gap=False
    for x in eligible:
        ob=ts(x['observed_at'])
        if (ob-last).total_seconds()>GAP:
            gap=True; break
        until_gap.append(x); last=ob
        if ob>end: break
    r['censor_seconds']=max(0,min(h*60,(last-start).total_seconds()))
    target=next((x for x in until_gap if ts(x['observed_at'])>end),None)
    complete=bool(target and ts(target['recorded_at'])<=limit and not gap)
    r['coverage_status']='COMPLETE' if complete else ('NOT_MATURE' if limit>ts(CUTOFF) else 'CENSORED')
    observed=[x for x in until_gap if ts(x['observed_at'])<=end]
    values=[(x,net(x)) for x in observed]
    floor=next((x for x,v in values if v==-1.0),None)
    # The floor is an absorbing Paper writeoff. Later rebound cannot erase it.
    admissible=[(x,v) for x,v in values if v is not None and (floor is None or ts(x['recorded_at'])<=ts(floor['recorded_at']))]
    r['within_max_net_return_upper_bound']=max((v for _,v in admissible),default=None)
    stop=next((x for x,v in admissible if v<=-.20),None)
    if stop: r['time_to_stop20_seconds']=(ts(stop['recorded_at'])-start).total_seconds()
    if floor: r['time_to_known_liq_floor_seconds']=(ts(floor['recorded_at'])-start).total_seconds()
    trigger=next((x for x,v in admissible if v>0),None)
    if trigger:
        # The exit observation must be newer than when the trigger actually became available.
        nxt=next((x for x in eligible if ts(x['observed_at'])>ts(trigger['recorded_at'])),None)
        if nxt and (ts(nxt['recorded_at'])-ts(trigger['recorded_at'])).total_seconds()<=GAP:
            v=net(nxt); r['first_threshold_exit_net']=v
            r['observed_hit']=int(v>0)
            if v>0: r['time_to_profit_seconds']=(ts(nxt['recorded_at'])-start).total_seconds()
    elif complete or floor:
        r['observed_hit']=0
    if floor:
        r['fixed_net_return']=-1.0; r['fixed_label_status']='CONFIRMED_PAPER_FLOOR'
    elif complete:
        r['fixed_net_return']=net(target);r['fixed_raw_return']=float(target['price_usd'])/mp-1
        r['fixed_label_status']='OBSERVED';r['fixed_exit_observed_at']=target['observed_at'];r['fixed_exit_recorded_at']=target['recorded_at']
    return {prefix+k:v for k,v in r.items()}


def main():
    blob=(DATA/'extract.json.gz').read_bytes(); d=json.loads(gzip.decompress(blob))
    cost_file=DATA/'execution_epochs.json'
    if cost_file.exists(): epochs=json.loads(cost_file.read_text(encoding='utf-8'))['epochs']
    else: epochs=json.loads((DATA/'summary.json').read_text(encoding='utf-8'))['cost_epochs']
    epochs=sorted(epochs,key=lambda x:x['activated_at'])
    assert epochs and all(x.get('definition_fields') for x in epochs)
    snaps={s['id']:s for s in d['referenced_snapshots']}
    fills={f['entry_cohort_id']:f for f in d['v6_entry_fills']}
    ledger=json.loads(gzip.decompress((DATA/'positions_and_trades.json.gz').read_bytes()))
    bought={t['shadow_cohort_id'] for t in ledger['trades'] if t['side']=='BUY'}
    paths=defaultdict(list)
    for x in d['token_snapshot_frames_for_filled_tokens']:
        if valid(x) and pool(x): paths[(x['token_id'],norm(pool(x),x['token_id']))].append(x)
    for path in paths.values(): path.sort(key=lambda x:(ts(x['recorded_at']),ts(x['observed_at'])))
    records={}; exclusions=Counter()
    for c in sorted(d['cohorts'],key=lambda x:x['id']):
        f=json.loads(c['feature_json'] or '{}')
        sid=f.get('fill_signal_snapshot_id') or f.get('source_snapshot_id') or c['source_snapshot_id']
        s=snaps.get(sid)
        if not s or not valid(s) or s['token_id']!=c['token_id'] or norm(pool(s),c['token_id'])!=norm(c['pair_address'],c['token_id']):
            exclusions['missing_invalid_source']+=1; continue
        prediction_at=s['recorded_at']
        if not ts(START)<=ts(prediction_at)<=ts(CUTOFF): exclusions['outside_feature_anchor_window']+=1; continue
        fill=fills.get(c['id'])
        if fill and (fill['token_id']!=c['token_id'] or fill['definition_version']!=d['definition_version']): fill=None
        key=(c['token_id'],norm(c['pair_address'],c['token_id']),sid)
        if key in records:
            records[key]['cohort_ids'].append(c['id'])
            # Use earliest actual receipt only; independent of any future outcome.
            old=records[key]['fill']
            if fill and (old is None or ts(fill['filled_at'])<ts(old['filled_at'])): records[key].update(fill=fill,cohort=c)
        else: records[key]=dict(source=s,cohort=c,fill=fill,cohort_ids=[c['id']])
    rows=[]
    for (token,p,sid),rec in records.items():
        s,c,fill=rec['source'],rec['cohort'],rec['fill']; decision=s['recorded_at']
        receipt=snaps.get(c['source_snapshot_id'])
        # Actual receipt frame and reference share token/pool and availability before actual fill.
        strict=bool(fill and receipt and valid(receipt) and receipt['token_id']==token
                    and norm(pool(receipt),token)==p and ts(receipt['observed_at'])>ts(decision)
                    and ts(receipt['recorded_at'])<=ts(fill['filled_at'])
                    and float(fill.get('execution_price_usd') or 0)>0
                    and float(fill.get('entry_market_price_usd') or 0)>0)
        r=dict(opportunity_id=f'{token}|{p}|{sid}',cohort_id=c['id'],cohort_ids=';'.join(map(str,rec['cohort_ids'])),
               token_id=token,pair_address=p,decision_at=decision,decision_time_kind='offline_source_availability_anchor',
               has_strategy_buy=int(any(cid in bought for cid in rec['cohort_ids'])),
               runtime_decision_time_verified=0,signal_snapshot_id=sid,source_available=1,
               chain=token.split(':')[0],source_provider=s['provider'],primary_strict_eligible=int(strict),
               actual_entry_filled=int(bool(fill)),actual_entry_filled_at=fill['filled_at'] if fill else None,
               actual_entry_fill_id=fill['id'] if fill else None,
               actual_entry_execution_price_usd=fill['execution_price_usd'] if fill else None,
               actual_entry_market_price_usd=fill['entry_market_price_usd'] if fill else None,
               receipt_observed_at=receipt['observed_at'] if receipt else None,
               receipt_recorded_at=receipt['recorded_at'] if receipt else None)
        r.update({k:s[k] for k in ['price_usd','liquidity_usd','volume_5m_usd','buys_5m','sells_5m']})
        buys,sells=s['buys_5m'],s['sells_5m'];r['buy_share_5m']=buys/(buys+sells) if buys is not None and sells is not None and buys+sells>0 else None
        created=(raw(s).get('pair') or {}).get('pairCreatedAt')
        r['pool_age_seconds']=max(0,(ts(s['observed_at'])-datetime.fromtimestamp(created/1000,timezone.utc)).total_seconds()) if created else None
        r['source_data_age_seconds']=(ts(decision)-ts(s['observed_at'])).total_seconds()
        r['signal_to_receipt_market_drift']=float(fill['entry_market_price_usd'])/float(s['price_usd'])-1 if fill and fill['entry_market_price_usd'] else None
        for h in (15,30,60):
            if strict: r.update(label(paths[(token,p)],fill,epochs,h))
            else:
                r.update({f'h{h}_'+k:v for k,v in dict(coverage_status='UNKNOWN_ENTRY',censor_seconds=0,observed_hit=None,fixed_net_return=None,fixed_raw_return=None,time_to_profit_seconds=None,time_to_stop20_seconds=None,time_to_known_liq_floor_seconds=None).items()})
        rows.append(r)
    frame=pd.DataFrame(rows).sort_values(['decision_at','opportunity_id'])
    frame.to_csv(DATA/'opportunities_post_repair.csv',index=False)
    summary=dict(extract_sha256=hashlib.sha256(blob).hexdigest(),cutoff=CUTOFF,source_cohorts=len(d['cohorts']),
                 valid_opportunities=len(frame),tokens=frame.token_id.nunique(),exclusions=dict(exclusions),
                 actual_filled=int(frame.actual_entry_filled.sum()),strict_entries=int(frame.primary_strict_eligible.sum()),
                 strict_tokens=frame[frame.primary_strict_eligible==1].token_id.nunique(),coverage={},cost_epochs=epochs)
    for h in (15,30,60):summary['coverage'][h]=dict(frame[f'h{h}_coverage_status'].value_counts())
    (DATA/'summary.json').write_text(json.dumps(summary,indent=2,default=int),encoding='utf-8')
    lines=['# Opportunity master：冻结离线机会', '',
           f"固定截点 {CUTOFF}。全期45872 cohort / 1815 Token、25063仓 /1553 Token。修复后原始纳入{len(d['cohorts'])} cohort；有效源帧合并后{len(frame)}机会/{frame.token_id.nunique()} Token，其中{summary['actual_filled']}有共享v6 receipt记录，只有{int(frame.has_strategy_buy.sum())}个机会存在账户策略BUY；严格三时钟后帧子集{summary['strict_entries']}机会/{summary['strict_tokens']} Token。", '',
           '研究单位=chain/Token/原池/冻结signal snapshot，重复cohort挂接而不复制路径。全期实际交易另有7435个Token/cohort机会，不等于本次修复后可建标签子集。无成交机会留在master，不能因缺标签当失败。', '',
           '预测时刻明确选用信号快照本地recorded_at，即三时钟均已可用的离线信息锚；它不是伪造的原策略decision_at。共享receipt的observed必须严格晚于此锚，receipt recorded不晚于共享fill。模型因此只检验现有observer已选择、可恢复共享receipt且具备后续行情的子总体前置L0信息，不能估计完整发现universe的选择价值，也不是全部已成交账户样本。cohort.decided_at只用于原始纳入，未作信号时间。', '',
           '标签帧按recorded到达顺序，丢弃不能前进的老observed；observed<=ingested<=recorded，年龄<=120秒，原池匹配，流动性字段已知。最大连续观察缺口120秒，超过便删失。EVM池地址忽略大小写，Solana保留。', '',
           '主标签：15分钟内首次净正触发，在trigger真实recorded之后首次严格新observed帧退出，扣当时卖侧成本后是否仍正。失败的首次退出不事后挑第二次高点；先成功后核销也不以未来核销抹掉先前成功。固定15m退出作为独立对照；30/60m仅敏感性。原池fresh低于当期floor是模拟吸收核销，不是链上rug或真实卖出证明。', '',
           '买数量以实际v6 execution_price为锚，不能重复扣买滑点。卖滑点/fee取对应immutable activation；raw return另以entry_market_price计算。原始缓存只使用token_snapshots三时钟，没有用market_mark_history.observed冒充ingested。120秒是分析预注册容差，不是关于真实逐笔市场完整性的保证。', '',
           '标签缺失可能非随机，持仓后采样更密。可观察门槛标签不能被称为真正amount-specific执行利润。研究窗口同一天，未知日期/市场状态不会被填作稳健。', '',
           '覆盖分母：`'+json.dumps(summary['coverage'],ensure_ascii=False,default=int)+'`。', '',
           '可重算输入hash：`'+summary['extract_sha256']+'`。逐机会CSV、raw extract及成本epoch位于data/research/alpha_diagnosis_20260907/opportunities；没有写运行库。']
    (DOC/'OPPORTUNITY_MASTER_SUMMARY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='cost_epochs'},default=int))


if __name__=='__main__':main()
