from datetime import timedelta
import pytest
from memetrader.safety_veto_shadow import SafetyVetoShadow
from memetrader.models import TokenSnapshot,utcnow,iso


def fixture():
 s=SafetyVetoShadow();now=utcnow()
 item=dict(version='v',cohort_id=1,token_id='solana:T',pool='Pool',requested_at=iso(now),notional=5,
           shadow_costs={'buy_slippage_bps':400,'sell_slippage_bps':400,'additional_fee_usd_each_fill':0,'min_pool_liquidity_usd':1000})
 anchor=dict(price_usd=1,eligible=True,observed_at=iso(now),recorded_at=iso(now))
 s.capture(item,'REJECT',{'reasons':['dangerous_transfer_fee_upgradable'],'source_at':iso(now)},anchor,['arm'],now)
 return s,now,item,anchor


def frame(s,now,minutes,price=2,pool='Pool',liq=2000):
 at=now+timedelta(minutes=minutes)
 snap=TokenSnapshot('solana','T',price,liq,None,0,0,0,observed_at=at,ingested_at=at,provider='fixture',raw={'pair':{'pairAddress':pool}})
 s.observe('solana:T',snap,at,at)


def test_fixed_horizons_exact_pool_and_paper_costs():
 s,n,_,_=fixture()
 frame(s,n,8);frame(s,n,15,pool='pool');frame(s,n,15,liq=1)
 row=next(iter(s.state['pending'].values()));assert not row['results']
 frame(s,n,15)
 assert row['results']['15']['raw_return']==1
 assert row['results']['15']['paper_cost_estimated_return']==pytest.approx(2*.96/1.04-1)
 frame(s,n,16,price=3)
 assert row['results']['15']['raw_return']==1
 frame(s,n,60);frame(s,n,240);s.expire(n+timedelta(minutes=241))
 assert not s.state['pending'] and len(s.state['recent'])==1


def test_missing_horizon_unknown_and_restart_dedup():
 s,n,item,anchor=fixture();s=SafetyVetoShadow(s.snapshot())
 s.capture(item,'REJECT',{},anchor,[],n)
 assert s.state['triggers']==1
 frame(s,n,21)
 s.expire(n+timedelta(minutes=246))
 assert all(v['status']=='UNKNOWN' for v in s.state['recent'][0]['results'].values())


def test_wait_security_excluded_and_no_pre_activation_backfill():
 s,n,item,anchor=fixture()
 for status in ('WAIT_SECURITY','BUY_AUTHORIZED_PASS'):
  s.capture({**item,'cohort_id':2},status,{},anchor,[],n)
 s.capture({**item,'cohort_id':3,'requested_at':iso(n-timedelta(days=1))},'REJECT',{},anchor,[],n)
 assert s.state['triggers']==1
 s.capture({**item,'cohort_id':4},'WAIT_HAZARD',{'soft_hazard':['synthetic']},anchor,[],n)
 assert s.state['triggers']==2


def test_pending_bounded_and_future_ingestion_ignored():
 s,n,item,anchor=fixture()
 for i in range(2,131):s.capture({**item,'cohort_id':i},'REJECT',{},anchor,[],n)
 assert len(s.state['pending'])==128 and s.state['capacity_skipped']==2
 at=n+timedelta(minutes=15)
 snap=TokenSnapshot('solana','T',2,2000,None,0,0,0,observed_at=at,raw={'pairAddress':'Pool'})
 s.observe('solana:T',snap,at+timedelta(seconds=1),at)
 assert not next(iter(s.state['pending'].values()))['results']
