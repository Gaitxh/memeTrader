from datetime import datetime,timedelta,timezone
from copy import deepcopy
import json
import pytest
from memetrader.mode_learning144 import capture,expire,initialize,observe,train,choose,MAX_PENDING
T=datetime(2026,9,10,tzinfo=timezone.utc)
def at(seconds):return (T+timedelta(seconds=seconds)).isoformat()
def cap(s,key='a',time=0):
 return capture(s,episode_key=key,token_id='bsc:'+key,pair_address='p',chain='bsc',age_bucket='0_300',mode='fast',features={},decision_at=at(time),observed_at=at(time),ingested_at=at(time),recorded_at=at(time),paper_terms={'buy_slippage_rate':.04,'sell_slippage_rate':.04,'stake_usd':2})
def frame(seconds,price=2,liq=2000,token='bsc:a'):
 return dict(token_id=token,pair_address='p',price_usd=price,liquidity_usd=liq,observed_at=at(seconds),ingested_at=at(seconds),recorded_at=at(seconds))
def test_strict_entry_costs_and_no_future_or_wrong_identity():
 s=initialize();cap(s)
 assert observe(s,episode_key='a',frame=frame(1,token='bsc:other'),now=at(1))['status']=='ignored_noncausal_or_identity'
 assert observe(s,episode_key='a',frame=frame(0),now=at(1))['status']=='ignored_noncausal_or_identity'
 observe(s,episode_key='a',frame=frame(1),now=at(1))
 for i in range(31,302,30):observe(s,episode_key='a',frame=frame(i),now=at(i))
 label=s['episodes']['a']['results']['5']
 assert label['costed_return']==pytest.approx(.96/1.04-1)
 assert label['target']['observed_at']==at(301)
 assert train(s,cutoff_at=at(300))['consumed']==0
 assert train(s,cutoff_at=at(302))['consumed']==1
 assert 'a' in s['episodes'] # 15/60 remain pending after first training
 restored=json.loads(json.dumps(s));assert train(restored,cutoff_at=at(303))['consumed']==0
 assert restored['episodes']['a']['entry']['observed_at']==at(1)

def test_floor_hazard_then_moon_and_late_gap_are_unknown():
 s=initialize();cap(s);observe(s,episode_key='a',frame=frame(1),now=at(1))
 observe(s,episode_key='a',frame=frame(31,liq=10),now=at(31))
 for i in range(61,302,30):observe(s,episode_key='a',frame=frame(i,price=100),now=at(i))
 e=s['episodes']['a'];assert e['results']['5']['status']=='UNKNOWN' and e['first_floor']
 assert e['results']['5']['first_hits']['plus100']
 cap(s,'late');observe(s,episode_key='late',frame=frame(2,token='bsc:late'),now=at(2))
 observe(s,episode_key='late',frame=frame(500,token='bsc:late'),now=at(500))
 assert s['episodes']['late']['results']['5']['status']=='UNKNOWN'

def test_no_entry_expires_restart_and_capacity_are_bounded():
 s=initialize()
 for i in range(MAX_PENDING+1):result=cap(s,str(i))
 assert result['status']=='pending_capacity'
 expire(s,now=at(122));train(s,cutoff_at=at(122));assert not s['episodes']
 assert cap(json.loads(json.dumps(s)),'1')['status']=='already_captured'
 assert all(len(g['returns'])==0 for g in s['groups'].values())

def test_preregistered_promotion_needs_independent_dates_and_top3_robustness():
 s=initialize()
 for i in range(20):
  e=cap(s,str(i),time=(i%2)*86400)['episode']
  e['results']['5']=dict(status='OBSERVED',available_at=at(200000),costed_return=.1)
 s['actual_groups']['fast']=[dict(token_id='bsc:'+str(i),realized_pnl_usd=.1) for i in range(5)]
 assert train(s,cutoff_at=at(200001))['promoted']
 model=deepcopy(s['model']);assert model['releases']==1
 assert not train(s,cutoff_at=at(200002))['promoted']
 s2=initialize()
 for i in range(20):
  e=cap(s2,str(i))['episode'];e['results']['5']=dict(status='OBSERVED',available_at=at(400),costed_return=.1)
 assert not train(s2,cutoff_at=at(401))['promoted']

def test_same_recorded_frame_cannot_overwrite_last_frame_or_entry():
 s=initialize();cap(s);observe(s,episode_key='a',frame=frame(1),now=at(1))
 stale=frame(1,price=200);stale['recorded_at']=at(3)
 assert observe(s,episode_key='a',frame=stale,now=at(3))['status']=='ignored_noncausal_or_identity'
 assert s['episodes']['a']['entry']['price_usd']==2
