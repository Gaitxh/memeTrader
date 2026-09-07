"""No model refits: aligned economic outcomes, censoring and competing events."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/research/alpha_diagnosis_20260907'
DOC=ROOT/'docs/PROJECT_CONTEXT/ALPHA_DIAGNOSIS_20260907'


def decile(g,field):
    t=g.groupby('token_id').agg(p=('p','mean'),outcome=(field,'mean'))
    n=max(1,int(np.ceil(len(t)*.1)));a=t.p.nsmallest(n).max();b=t.p.nlargest(n).min()
    low=t[t.p<=a];high=t[t.p>=b]
    return dict(top_tokens=len(high),bottom_tokens=len(low),top_mean=high.outcome.mean(),bottom_mean=low.outcome.mean(),
                labelled_top=int(high.outcome.notna().sum()),labelled_bottom=int(low.outcome.notna().sum()))


def main():
    opp=pd.read_csv(DATA/'opportunities/opportunities_post_repair.csv')
    pred=pd.read_csv(DATA/'detectability/oos_predictions.csv')
    joined=pred[pred.horizon==15].merge(opp[['opportunity_id','h15_first_threshold_exit_net','h15_fixed_net_return','has_strategy_buy']],on='opportunity_id',validate='many_to_one')
    joined['aligned_net']=joined.h15_first_threshold_exit_net.fillna(joined.h15_fixed_net_return)
    result=[]
    for (target,start,model),g in joined.groupby(['target','test_start','model']):
        result.append(dict(target=target,test_start=start,model=model,tie_inclusive_fixed=decile(g,'net'),tie_inclusive_aligned=decile(g,'aligned_net')))
    (DATA/'detectability/aligned_economics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    # One earliest strict opportunity per Token. Descriptive competing-event estimates only.
    s=opp[opp.primary_strict_eligible==1].sort_values(['actual_entry_filled_at','opportunity_id']).drop_duplicates('token_id')
    events=[]
    for _,r in s.iterrows():
        profit=r.h15_time_to_profit_seconds
        fail=min([x for x in [r.h15_time_to_stop20_seconds,r.h15_time_to_known_liq_floor_seconds]if pd.notna(x)],default=np.inf)
        censor=min(900,float(r.h15_censor_seconds or 0))
        choices=[(censor,'censored')]
        if pd.notna(profit) and profit<=censor:choices.append((float(profit),'profit'))
        if np.isfinite(fail) and fail<=censor:choices.append((float(fail),'failure'))
        time,kind=min(choices,key=lambda x:(x[0],x[1]=='censored'))
        events.append(dict(token_id=r.token_id,seconds=time,event=kind,chain=r.chain))
    survival=1.;profit_cif=0.;failure_cif=0.;curve=[]
    for t in sorted(set(x['seconds']for x in events)):
        risk=sum(x['seconds']>=t for x in events);dp=sum(x['seconds']==t and x['event']=='profit' for x in events);df=sum(x['seconds']==t and x['event']=='failure'for x in events)
        profit_cif+=survival*dp/risk;failure_cif+=survival*df/risk;survival*=1-(dp+df)/risk
        curve.append(dict(seconds=t,at_risk=risk,profit_cif=profit_cif,failure_cif=failure_cif,survival=survival))
    hazard=dict(n_tokens=len(events),events=pd.Series([x['event']for x in events]).value_counts().to_dict(),curve=curve,rows=events)
    (DATA/'detectability/competing_events.json').write_text(json.dumps(hazard,indent=2),encoding='utf-8')
    cov=opp.groupby(['chain']).agg(opportunities=('token_id','size'),tokens=('token_id','nunique'),strategy_buy_opportunities=('has_strategy_buy','sum'),strict_entries=('primary_strict_eligible','sum'))
    cov['h15_observed_label']=opp.groupby('chain').h15_observed_hit.apply(lambda x:x.notna().sum())
    cov.to_csv(DATA/'detectability/coverage_by_chain.csv')
    lines=['\n## 经济目标对齐与并列分数修正（复用既有预测，无重新训练）','',
           '上表固定horizon净结果不等于主标签的首次阈值退出收益。下表另对齐为首次阈值触发后下一帧退出；未触发则固定15m退出，缺帧仍UNKNOWN。它仍是离线Paper诊断合同，不是现有策略实盘PnL。', '',
           '原上表分位按稳定排序在同分中取前N，会产生任意选择。下表在边界包含全部同分Token，常数模型的高/低组因此都等于全体；这是指标解释修正，不是挑结果或调整模型。', '',
           '| 标签 | 块 | 模型 | Top/Bottom Token(含同分) | 对齐净均值 Top/Bottom | 固定15m净均值 Top/Bottom |','|---|---|---|---:|---|---|']
    for r in result:
        if r['model']not in ('constant','market_baseline','full_logit','full_tree'):continue
        a=r['tie_inclusive_aligned'];f=r['tie_inclusive_fixed']
        lines.append(f"| {r['target']} | {r['test_start'][11:16]} | {r['model']} | {a['top_tokens']}/{a['bottom_tokens']} | {a['top_mean']:.4f}/{a['bottom_mean']:.4f} | {f['top_mean']:.4f}/{f['bottom_mean']:.4f} |")
    lines += ['', '## 覆盖与生存诊断','',f"每Token只取修复后最早严格机会，N={len(events)}；首次事件计数={hazard['events']}。profit=严格后帧净正；failure=先到净−20%或fresh原池floor；否则按首个观察缺口/15m右删失。保存Aalen–Johansen描述曲线，不拟合/部署hazard策略。",'',
              '删失很可能依赖市场/提供商状态，不满足独立删失假设，因此曲线仅描述观测机制，不声称市场总体failure概率。标记间的先后也只是本地观察时钟，不是每笔链上交易时钟。', '',
              f"Master中实际有策略BUY的机会 {int(opp.has_strategy_buy.sum())}，有共享receipt记录 {int(opp.actual_entry_filled.sum())}；这两者不能混称实际成交。未投影到策略账户的共享receipt仍可构造市场诊断标签，但不是已执行交易收益。", '',
              '当前可标记样本来自87个有fill token的已有后续快照，持仓/活跃偏差尚未消除。完整chain/coverage表已保存。未知结果有−100%有限下界、理论上无有限收益上界，因此不能诚实地给出完整universe的双侧EV界。']
    with (DOC/'ENTRY_EDGE_DETECTABILITY.md').open('a',encoding='utf-8')as f:f.write('\n'.join(lines)+'\n')
    print(json.dumps({'hazard_counts':hazard['events'],'actual_buy_opportunities':int(opp.has_strategy_buy.sum()),'primary_economics':[x for x in result if x['target']=='observed_hit'and x['model']=='full_logit']}))


if __name__=='__main__':main()
