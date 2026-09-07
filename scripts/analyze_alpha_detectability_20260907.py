"""Offline diagnostic only. Fixed models, token-disjoint chronological evaluation."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/research/alpha_diagnosis_20260907'
OUT = DATA/'detectability'
DOC = ROOT/'docs/PROJECT_CONTEXT/ALPHA_DIAGNOSIS_20260907/ENTRY_EDGE_DETECTABILITY.md'
BASE = ['log_liquidity_usd','log_pool_age_seconds']
FULL = BASE + ['log_price_usd','log_volume_5m_usd','log_buys_5m','log_sells_5m','buy_share_5m']
SPLITS = [('2026-09-07T10:30:00Z','2026-09-07T12:00:00Z'),
          ('2026-09-07T12:00:00Z','2026-09-07T13:38:59.399800Z')]


def clean_json(obj):
    if isinstance(obj, dict): return {str(k):clean_json(v) for k,v in obj.items()}
    if isinstance(obj, (list,tuple)): return [clean_json(x) for x in obj]
    if isinstance(obj, np.generic): obj = obj.item()
    if isinstance(obj, float) and not np.isfinite(obj): return None
    return obj


def token_metrics(df):
    y, p = df.y.to_numpy(), df.p.to_numpy()
    weights = 1/df.groupby('token_id').token_id.transform('size').to_numpy()
    result = dict(n=len(df),tokens=df.token_id.nunique(),base_rate=np.average(y,weights=weights),
                  auc=roc_auc_score(y,p,sample_weight=weights) if len(set(y))>1 else None,
                  pr_auc=average_precision_score(y,p,sample_weight=weights) if sum(y)>0 else None,
                  brier=brier_score_loss(y,p,sample_weight=weights))
    result['calibration'] = []
    for lo,hi in zip(np.arange(0,1,.2),np.arange(.2,1.01,.2)):
        part=df[(df.p>=lo)&((df.p<hi) if hi<.999 else (df.p<=1))]
        if len(part): result['calibration'].append(dict(bin=[lo,hi],n=len(part),predicted=part.p.mean(),observed=part.y.mean()))
    # First collapse each Token, so an episode-rich Token cannot dominate deciles/EV.
    tk=df.groupby('token_id').agg(p=('p','mean'),net=('net','mean'),y=('y','mean')).sort_values('p',kind='stable')
    n=max(1,int(np.ceil(len(tk)*.1)))
    result['top_decile'] = dict(tokens=n,observed_net_n=tk.tail(n).net.notna().sum(),mean_net=tk.tail(n).net.mean(),median_net=tk.tail(n).net.median())
    result['bottom_decile'] = dict(tokens=n,observed_net_n=tk.head(n).net.notna().sum(),mean_net=tk.head(n).net.mean(),median_net=tk.head(n).net.median())
    v=tk.net.dropna().to_numpy(); rng=np.random.default_rng(20260907)
    result['mean_fixed_horizon_net']=v.mean() if len(v) else None
    result['mean_fixed_horizon_net_ci95']=np.quantile([rng.choice(v,len(v),replace=True).mean() for _ in range(2000)],[.025,.975]).tolist() if len(v)>1 else None
    result['tail_sensitivity']={}
    for k in (1,3):
        remove=set(tk.sort_values('net').tail(k).index)
        remain=df[~df.token_id.isin(remove)]
        result['tail_sensitivity'][f'remove_best_{k}']=dict(tokens=remain.token_id.nunique(),mean_net=tk.drop(index=list(remove)).net.mean(),auc=roc_auc_score(remain.y,remain.p) if remain.y.nunique()>1 else None)
    if len(v)>1: result['leave_one_token_out_mean_range']=[(v.sum()-v.max())/(len(v)-1),(v.sum()-v.min())/(len(v)-1)]
    return result


def fit_model(train,test,features,kind,shuffle=False):
    prep=ColumnTransformer([('numeric',make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler()),features),
                            ('chain',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['chain'])])
    model=LogisticRegression(C=1,max_iter=500,random_state=20260907) if kind=='logit' else DecisionTreeClassifier(max_depth=3,min_samples_leaf=5,random_state=20260907)
    pipe=make_pipeline(prep,model)
    y=train.y.copy()
    if shuffle:
        rng=np.random.default_rng(20260907)
        for _,ix in train.groupby(['chain','hour']).groups.items(): y.loc[ix]=rng.permutation(y.loc[ix].to_numpy())
    weights=1/train.groupby('token_id').token_id.transform('size').to_numpy()
    pipe.fit(train,y,**{pipe.steps[-1][0]+'__sample_weight':weights})
    return pipe.predict_proba(test)[:,1]


def main():
    OUT.mkdir(exist_ok=True)
    source=DATA/'opportunities/opportunities_post_repair.csv'
    df=pd.read_csv(source)
    for k in ['price_usd','liquidity_usd','pool_age_seconds','volume_5m_usd','buys_5m','sells_5m']:
        df['log_'+k]=np.log1p(pd.to_numeric(df[k],errors='coerce').clip(lower=0))
    df['buy_share_5m']=pd.to_numeric(df.buy_share_5m,errors='coerce')
    df['time']=pd.to_datetime(df.actual_entry_filled_at,utc=True,errors='coerce')
    df['hour']=df.time.dt.floor('h').astype(str)
    strict=df.primary_strict_eligible.astype(str).str.lower().isin(['true','1','1.0'])
    results=[]; predictions=[]
    for h in (15,30,60):
        for target in ('observed_hit','fixed_positive'):
            s=df[strict].copy()
            s['net']=pd.to_numeric(s[f'h{h}_fixed_net_return'],errors='coerce')
            if target=='observed_hit': s['y']=pd.to_numeric(s[f'h{h}_observed_hit'],errors='coerce')
            else: s['y']=np.where(s.net.notna(),(s.net>0).astype(int),np.nan)
            s=s[s.y.isin([0,1])].copy()
            s['mature']=s.time+pd.Timedelta(minutes=h,seconds=120)
            for start,end in SPLITS:
                ts,te=pd.Timestamp(start),pd.Timestamp(end)
                test=s[(s.time>=ts)&(s.time<te)].copy()
                train=s[(s.time<ts)&(s.mature<ts)&(~s.token_id.isin(test.token_id))].copy()
                base=dict(horizon=h,target=target,test_start=start,test_end=end,n_train=len(train),n_test=len(test),tokens_train=train.token_id.nunique(),tokens_test=test.token_id.nunique(),train_classes=train.y.value_counts().to_dict())
                assert not set(train.token_id)&set(test.token_id)
                assert train.empty or train.mature.max()<ts
                if len(train)<20 or len(test)<5 or train.y.nunique()<2:
                    results.append({**base,'status':'INSUFFICIENT_FOR_FIXED_MODEL'}); continue
                configurations=[('constant',BASE,'constant',False),('market_baseline',BASE,'logit',False),('full_logit',FULL,'logit',False),('full_tree',FULL,'tree',False),('minus_activity',BASE+['log_price_usd'],'logit',False),('minus_age',[x for x in FULL if 'age' not in x],'logit',False),('within_chain_hour_shuffle',FULL,'logit',True)]
                for name,features,kind,shuffle in configurations:
                    weights=1/train.groupby('token_id').token_id.transform('size').to_numpy()
                    p=np.full(len(test),np.average(train.y,weights=weights)) if kind=='constant' else fit_model(train,test,features,kind,shuffle)
                    pred=test[['opportunity_id','token_id','chain','hour','y','net','liquidity_usd','pool_age_seconds']].copy()
                    pred['p']=p; pred['model']=name; pred['test_start']=start; pred['horizon']=h; pred['target']=target
                    metrics=token_metrics(pred)
                    strata={}
                    for col in ('chain','hour'):
                        strata[col]={str(k):token_metrics(g) for k,g in pred.groupby(col) if len(g)>=2}
                    pred['liquidity_regime']=pd.cut(pd.to_numeric(pred.liquidity_usd),[0,10000,100000,np.inf],labels=['low','medium','high']).astype(str)
                    strata['liquidity_regime']={str(k):token_metrics(g) for k,g in pred.groupby('liquidity_regime') if len(g)>=2}
                    results.append({**base,'model':name,'status':'EVALUATED_DIAGNOSTIC_ONLY','metrics':metrics,'strata':strata})
                    predictions.append(pred)
    summary={'input_rows':len(df),'input_tokens':df.token_id.nunique(),'strict_rows':int(strict.sum()),'strict_tokens':df[strict].token_id.nunique(),
             'coverage':{},'results':results,'model_contract':{'primary':'h15_observed_hit','control':'fixed_horizon_positive','splits':SPLITS,'no_hyperparameter_search':True,'bootstrap_unit':'Token','seed':20260907}}
    for h in (15,30,60): summary['coverage'][h]=df[f'h{h}_coverage_status'].value_counts(dropna=False).to_dict()
    (OUT/'results.json').write_text(json.dumps(clean_json(summary),indent=2),encoding='utf-8')
    if predictions: pd.concat(predictions,ignore_index=True).to_csv(OUT/'oos_predictions.csv',index=False)
    lines=['# Entry edge detectability：离线诊断', '',
           f"输入 {len(df)} 机会 / {df.token_id.nunique()} Token；严格可核验子集 {strict.sum()} 机会 / {df[strict].token_id.nunique()} Token。", '',
           '主标签为15分钟内门槛触发后下一合格原池帧仍净正。固定15分钟结果为独立对照；30/60分钟仅敏感性，不选择最好horizon。缺失标签不填0。所有模型只用信号时可用L0，未来路径仅形成标签。', '',
           '固定10:30、12:00 UTC两次walk-forward；训练的完整标签容差窗在测试前成熟，测试Token从训练彻底删除。预处理仅fit训练。每Token等权训练/主要指标，Logistic C=1；小树depth=3/leaf=5；不寻优。训练小于20、测试小于5或训练单类时标不足；这些是可运行门槛，不是alpha充分性门槛。', '',
           '经济分位使用测试Token平均分数排序，固定horizon的模拟净结果是entry诊断，不是该分类器交易收益；未观测结果不进入EV，完整分母见覆盖表。bootstrap不消除MNAR或单日期局限。', '',
           '| H | 标签 | 测试起点 | 模型 | Train/Test Token | AUC | PR-AUC | Brier | Top10%净均值 | Bottom10%净均值 |',
           '|---:|---|---|---|---|---:|---:|---:|---:|---:|']
    for r in results:
        m=r.get('metrics',{}); fmt=lambda v: '-' if v is None or (isinstance(v,float) and not np.isfinite(v)) else f'{v:.4f}'
        lines.append(f"| {r['horizon']} | {r['target']} | {r['test_start'][11:16]} | {r.get('model',r['status'])} | {r['tokens_train']}/{r['tokens_test']} | {fmt(m.get('auc'))} | {fmt(m.get('pr_auc'))} | {fmt(m.get('brier'))} | {fmt(m.get('top_decile',{}).get('mean_net'))} | {fmt(m.get('bottom_decile',{}).get('mean_net'))} |")
    lines += ['', '校准、按链/小时/流动性层分组、Token bootstrap、leave-one-token-out均值范围、移除top1/top3、特征消融与标签置换全部保存 `data/research/alpha_diagnosis_20260907/detectability/results.json`。原始样本/预测留在data，不写生产DB。', '',
              '仅同一天修复后窗口，不能完成跨日期稳定性验证。测试Token可在两个未来块重复，汇总不能再把跨fold条数当独立Token。任何正分位或漂亮AUC都不是已发现alpha。']
    DOC.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(clean_json({k:v for k,v in summary.items() if k!='results'})))
    print('evaluated_models',sum(r['status']=='EVALUATED_DIAGNOSTIC_ONLY' for r in results))


if __name__=='__main__': main()
