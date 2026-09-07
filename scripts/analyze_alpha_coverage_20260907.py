"""Bounded R2 counter-test: predict future observation coverage, never trade it."""
import gzip
import json
import numpy as np
import pandas as pd
from analyze_alpha_detectability_20260907 import DATA, FULL, SPLITS, clean_json, fit_model, token_metrics


def main():
    df = pd.read_csv(DATA/'opportunities/opportunities_post_repair.csv')
    for k in ['price_usd','liquidity_usd','pool_age_seconds','volume_5m_usd','buys_5m','sells_5m']:
        df['log_'+k] = np.log1p(pd.to_numeric(df[k],errors='coerce').clip(lower=0))
    df['time'] = pd.to_datetime(df.actual_entry_filled_at,utc=True,errors='coerce')
    df['hour'] = df.time.dt.floor('h').astype(str)
    df['mature'] = df.time + pd.Timedelta(minutes=17)
    s = df[(df.primary_strict_eligible==1)&df.h15_coverage_status.isin(['COMPLETE','CENSORED'])].copy()
    s['y'] = (s.h15_coverage_status=='COMPLETE').astype(int)
    s['net'] = np.nan
    results=[]; all_pred=[]
    for start,end in SPLITS:
        ts,te=pd.Timestamp(start),pd.Timestamp(end)
        test=s[(s.time>=ts)&(s.time<te)].copy()
        train=s[(s.mature<ts)&(~s.token_id.isin(test.token_id))].copy()
        if train.y.nunique()<2 or test.y.nunique()<2:
            results.append(dict(start=start,status='INSUFFICIENT_CLASSES')); continue
        test['p']=fit_model(train,test,FULL,'logit')
        metrics=token_metrics(test)
        results.append(dict(start=start,train_tokens=train.token_id.nunique(),test_tokens=test.token_id.nunique(),
                            auc=metrics['auc'],pr_auc=metrics['pr_auc'],base_rate=metrics['base_rate'],brier=metrics['brier']))
        all_pred.append(test[['opportunity_id','token_id','p','y']].assign(test_start=start))
    cp=pd.concat(all_pred,ignore_index=True)
    cp.to_csv(DATA/'detectability/coverage_oos_predictions.csv',index=False)
    alpha=pd.read_csv(DATA/'detectability/oos_predictions.csv')
    alpha=alpha[(alpha.horizon==15)&(alpha.target=='observed_hit')&(alpha.model=='full_logit')]
    joined=alpha.merge(cp.rename(columns={'p':'coverage_p','y':'complete'}),on=['opportunity_id','token_id','test_start'],validate='one_to_one')
    strata=[]
    for start,g in joined.groupby('test_start'):
        for tier,part in g.groupby(pd.cut(g.coverage_p,[-.01,.5,.8,1.01],labels=['0-.5','.5-.8','.8-1'])):
            if len(part):
                m=token_metrics(part)
                strata.append(dict(start=start,tier=str(tier),tokens=m['tokens'],n=len(part),auc=m['auc'],base_rate=m['base_rate']))
    coverage=[]
    for key in ['chain','source_provider','has_strategy_buy']:
        for val,g in s.groupby(key,dropna=False):
            w=1/g.groupby('token_id').token_id.transform('size')
            coverage.append(dict(field=key,value=str(val),rows=len(g),tokens=g.token_id.nunique(),token_weighted_complete=np.average(g.y,weights=w)))
    extract=json.loads(gzip.decompress((DATA/'opportunities/extract.json.gz').read_bytes()))
    negatives=sum(x.get('liquidity_usd') is not None and float(x['liquidity_usd'])<0 for x in extract['token_snapshot_frames_for_filled_tokens'])
    result=dict(models=results,alpha_by_coverage_propensity=strata,coverage=coverage,negative_liquidity_input_frames=negatives,
                limitations='Same-day small Token-disjoint folds; coverage model is a counter-test, not causal correction or deployable alpha. No IPC weighting or model selection.')
    (DATA/'detectability/coverage_diagnostic.json').write_text(json.dumps(clean_json(result),indent=2),encoding='utf-8')
    lines=['# R2 coverage负控：是否主要预测可观察性','',
           '复用冻结master、同一L0特征、固定Logistic与两段时间/Token隔离。仅新增两个覆盖模型，不调参、不重训主模型。标签=成熟窗口COMPLETE而非CENSORED；这是事后诊断目标，不能进入交易特征。','',
           '| 块 | 训练/测试Token | coverage AUC | PR-AUC / 基率 | Brier |','|---|---:|---:|---|---:|']
    for r in results:
        if 'auc' in r: lines.append(f"| {r['start']} | {r['train_tokens']}/{r['test_tokens']} | {r['auc']:.4f} | {r['pr_auc']:.4f}/{r['base_rate']:.4f} | {r['brier']:.4f} |")
    lines += ['', '主alpha预测在覆盖propensity中的分层（复用OOS预测；小Token格不能作稳定性证据）：','',
              '| 块 | coverage分层 | Token/行 | alpha AUC | 正例基率 |','|---|---|---:|---:|---:|']
    for r in strata: lines.append(f"| {r['start']} | {r['tier']} | {r['tokens']}/{r['n']} | {r['auc']} | {r['base_rate']:.4f} |")
    lines += ['', '覆盖模型不能证明MAR，更不能修复未观察路径。即使分层内仍有排序信息，也只属于观察子总体。未知净收益下界−100%，上界不有限；不虚构完整universe双侧EV界。', '',
              f'当前缓存后续快照负流动性值数={negatives}；因此旧评审指出的负值floor问题未在本次输入出现。没有为假想状态改变生产。', '',
              '分链、provider和实际策略BUY覆盖表在原始JSON；共享receipt不等于账户BUY。样本有限，没有声称完成跨日期、钱包实体或全部发现universe检验。']
    (DATA.parents[2]/'docs/PROJECT_CONTEXT/ALPHA_DIAGNOSIS_20260907/COVERAGE_COUNTERTEST.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(clean_json(result)))


if __name__=='__main__': main()
