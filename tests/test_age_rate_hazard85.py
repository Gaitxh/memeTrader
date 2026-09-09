import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location('hazard85', Path(__file__).resolve().parents[1]/'scripts/research_age_rate_hazard85.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def test_frame_rejects_future_and_preserves_missing_activity():
    row=dict(id=1,token_id='solana:CaseMint',observed_at='2026-09-09T00:00:00Z',
        ingested_at='2026-09-09T00:00:01Z',recorded_at='2026-09-09T00:00:02Z',
        provider='dexscreener',price_usd=1,liquidity_usd=5000,buys_5m=0,sells_5m=0,
        raw_json=json.dumps({'pair':{'chainId':'solana','pairAddress':'PoolCase',
            'baseToken':{'address':'CaseMint'}}}))
    assert study.frame(row,study.ts('2026-09-09T00:00:01Z')) is None
    frame=study.frame(row,study.ts('2026-09-09T00:00:03Z'))
    assert frame['pool']=='PoolCase' and frame['buys'] is None and frame['sells'] is None
    assert frame['activity_presence']=='UNKNOWN'
    row['token_id']='solana:casemint'
    assert study.frame(row,study.ts('2026-09-09T00:00:03Z')) is None


def test_veto_accounting_does_not_hide_tail_profit_or_censoring():
    rows=[dict(token_id=str(i),terminal=True,pnl=p,**{'return':p/5},cause='fixture')
          for i,p in enumerate([-5,-1,10])]
    rows.append(dict(token_id='open',terminal=False,pnl=None))
    s=study.stats(rows)
    assert s['catastrophic_loss_dollars']==5 and s['positive_profit']==10
    assert s['tail_profit']==10 and s['pnl']==4 and s['open_censored']==1
    assert s['pnl_without_top1']==-6


def test_frozen_boundaries_and_unknown_are_not_measured_zero():
    assert study.band(None,[1,10],['LT1','1_10','GE10'])=='UNKNOWN'
    assert study.band(1,[1,10],['LT1','1_10','GE10'])=='1_10'
    assert study.direction(None)=='UNKNOWN' and study.direction(0)=='FLAT'
