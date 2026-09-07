"""Offline ledger arithmetic; causal loss shares remain unidentified."""
import gzip,json
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/research/alpha_diagnosis_20260907/opportunities'
DOC=ROOT/'docs/PROJECT_CONTEXT/ALPHA_DIAGNOSIS_20260907'
C='2026-09-07T13:38:59.399800Z'; REPAIR='2026-09-07T09:19:47Z'


def summary(rows):
    d=pd.DataFrame(rows)
    if d.empty:return {'n':0}
    # Token average payoff is the inference unit; account sums remain descriptive ledger totals.
    by=d.groupby('token_id').agg(pnl=('pnl','sum'),mean_return=('return','mean'))
    v=by.mean_return.to_numpy();rng=np.random.default_rng(20260907)
    ci=np.quantile([rng.choice(v,len(v),replace=True).mean()for _ in range(2000)],[.025,.975]) if len(v)>1 else None
    positive=by.pnl.clip(lower=0).sort_values(ascending=False);den=positive.sum()
    absval=np.sort(np.abs(by.pnl.to_numpy()));n=len(absval)
    gini=(2*np.sum(np.arange(1,n+1)*absval)/(n*absval.sum())-(n+1)/n)if absval.sum() else 0
    return dict(n=len(d),tokens=len(by),net_pnl=d.pnl.sum(),positive_pnl=d.loc[d.pnl>0,'pnl'].sum(),negative_pnl=d.loc[d.pnl<0,'pnl'].sum(),wins=int((d.pnl>0).sum()),losses=int((d.pnl<0).sum()),
                token_mean_return=v.mean(),token_mean_return_ci95=ci.tolist()if ci is not None else None,
                token_pnl_abs_gini=gini,top1_token_positive_share=positive.head(1).sum()/den if den else None,
                top3_token_positive_share=positive.head(3).sum()/den if den else None,
                top10pct_token_positive_share=positive.head(max(1,int(np.ceil(n*.1)))).sum()/den if den else None,
                without_best_token_total=by.pnl.sum()-by.pnl.max(),without_top3_tokens_total=by.pnl.sum()-by.pnl.nlargest(3).sum(),
                categories=d.groupby('category').agg(n=('pnl','size'),pnl=('pnl','sum')).reset_index().to_dict('records'))


def main():
    d=json.loads(gzip.decompress((DATA/'positions_and_trades.json.gz').read_bytes()))
    epochs=json.loads((DATA/'execution_epochs.json').read_text(encoding='utf-8'))['epochs']
    assert len(epochs)==1 and epochs[0]['definition_fields']=={'additional_fee_usd_each_fill':0.0,'buy_slippage_bps':400,'min_pool_liquidity_usd':1000.0,'sell_slippage_bps':400}
    ts=defaultdict(list)
    for t in d['trades']:
        if t['created_at']<=C and (not t.get('recorded_at') or t['recorded_at']<=C):ts[(t['arm_id'],t['shadow_cohort_id'],t['token_id'])].append(t)
    out=[];differences=[]
    for p in d['positions']:
        if p['status'] not in ('closed','written_off') or not p['closed_at'] or p['closed_at']>C:continue
        trades=ts[(p['arm_id'],p['shadow_cohort_id'],p['token_id'])]
        buys=[t for t in trades if t['side']=='BUY'];sells=[t for t in trades if t['side']=='SELL']
        if not buys:continue
        pnl=sum(float(t['net_cash_flow_usd'])for t in trades)
        differences.append(abs(pnl-float(p['realized_pnl_usd'])))
        stake=-sum(float(t['net_cash_flow_usd'])for t in buys)
        proceeds=sum(float(t['net_cash_flow_usd'])for t in sells)
        market_contract=all('dex_mark_paper_fill' in str(t['reason'])for t in buys+sells)
        gross=pnl if not market_contract else proceeds*1.04/.96-stake
        if pnl>=0:cat='PROFIT_OR_FLAT'
        elif market_contract and gross>0:cat='COST_ASSOCIATED_GROSS_POSITIVE_NET_NEGATIVE'
        elif any(t['side']=='WRITEOFF'for t in trades):cat='OBSERVED_PAPER_WRITEOFF_CAUSE_UNIDENTIFIED'
        else:cat='LOSS_CAUSE_UNIDENTIFIED'
        out.append(dict(arm_id=p['arm_id'],cohort_id=p['shadow_cohort_id'],token_id=p['token_id'],opened_at=p['opened_at'],closed_at=p['closed_at'],
                        era='post_repair'if p['opened_at']>=REPAIR else'earlier',stake=stake,pnl=pnl,**{'return':pnl/stake},
                        frozen_path_no_friction_pnl=gross if market_contract else None,category=cat,close_reason=p['close_reason'],
                        causal_selection='UNKNOWN',causal_entry_timing='UNKNOWN',causal_exit='UNKNOWN',irreducible_tail='UNKNOWN'))
    df=pd.DataFrame(out);df.to_csv(DATA/'loss_lifecycles_final.csv',index=False)
    allsum=summary(out);sums={era:summary([r for r in out if r['era']==era])for era in ('earlier','post_repair')}
    report=dict(all_period=allsum,by_era=sums,max_ledger_vs_position_pnl_difference=max(differences),
                unknown_fraction_of_loss_value=sum(-r['pnl']for r in out if r['pnl']<0 and r['category']!='COST_ASSOCIATED_GROSS_POSITIVE_NET_NEGATIVE')/-allsum['negative_pnl'])
    (DATA/'loss_summary_final.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    group=df.groupby(['era','category']).agg(lifecycles=('pnl','size'),tokens=('token_id','nunique'),pnl_usd=('pnl','sum')).reset_index()
    group.to_csv(DOC/'LOSS_ATTRIBUTION.csv',index=False)
    lines=['# Loss attribution：账本算术与因果归因分开', '',
           f"固定截点 {C}；25063仓和51937追加交易分别提取后离线四键连接，不用source_buy_trade_id冒充trade主键。截止前{len(df)}完整终局，净PnL {allsum['net_pnl']:.4f}U；盈利{allsum['positive_pnl']:.4f}U，亏损{allsum['negative_pnl']:.4f}U。这是230个独立账户的算术总计，不是一个可执行组合收益。账本净现金与position终局PnL最大差{max(differences):.3g}U。", '',
           '因果Selection、Entry timing、Exit、不可避免尾险不能从一个终局原因或后验最高价唯一分解。未分配的部分明确UNKNOWN，而不是强行凑100%。已观察Paper核销也不证明rug不可预测。', '',
           '成本关联项只做同一既成卖出时点/数量路径的机械反算：本资金期唯一成本activation为4%/4%、fee0；对真实market-paper买卖把回款乘1.04/0.96后减本金，筛gross>0且实际net<0。它不是重新跑一个零成本策略；去掉成本会改变入场/退出触发，故不声称因果贡献。WRITEOFF余仓仍为零。', '',
           '| 时期 | 终局 / Token | 净PnL U | Token等权平均return | Token bootstrap 95% |',
           '|---|---:|---:|---:|---|']
    for era,s in sums.items():lines.append(f"| {era} | {s['n']} / {s['tokens']} | {s['net_pnl']:.4f} | {s['token_mean_return']:.4f} | {s['token_mean_return_ci95']} |")
    lines += ['',f"全期按Token累计PnL的正收益集中度：top1 {allsum['top1_token_positive_share']:.2%}，top3 {allsum['top3_token_positive_share']:.2%}，top10% Token {allsum['top10pct_token_positive_share']:.2%}；绝对Token-PnL Gini {allsum['token_pnl_abs_gini']:.4f}。删除最佳Token总计 {allsum['without_best_token_total']:.4f}U；删除前三 {allsum['without_top3_tokens_total']:.4f}U。仅敏感性，不设删赢家仍须盈利的门。",'',
              '置信区间以每Token平均生命周期return为单元，避免多账户复制形成虚假精度。此前中间工件的position bootstrap与top1%账户比例已被本报告替代，不用于最终结论。单日清洁窗仍不能提供跨日期检验。', '',
              'LOSS_ATTRIBUTION.csv提供非重叠观察分类摘要；完整逐生命周期记录、时代/尾部统计留在data。旧223306-life历史资料只作分期历史证据；本轮当前总历史计数另只读刷新为239956生命周期/481693交易，仍25期。']
    (DOC/'LOSS_ATTRIBUTION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
